"""
Offline experience writer for the SEA dual-memory doctor agent.

Reads an AgentClinic *results* JSONL (the output of run_experiment_selected.sh)
and distills each finished case into SEA's DualMemory, producing/updating a
sea_state.json that sea_doctor_agent.py recalls at test time.

This is the "remember" half of the loop. It is intentionally OFFLINE and
SINGLE-PROCESS: the agent never sees ground truth during a live dialogue, and
the live runner fans out up to 10 parallel workers, so writing here (sequential)
avoids racing the state file. The agent only ever READS the state.

Two-phase workflow (run from UAT_Agent/, with an ABSOLUTE --state path):

  # Phase A - generate experience on the training set
  ./src/agentclinic_code/run_experiment_selected.sh \
      --data_file <train.jsonl> --count N \
      --custom_doctor_agent_path src/agentclinic_code/sea_doctor_agent.py --name train_run
  uv run --with 'openai>=1.0.0' --with regex --with python-dotenv --with pyyaml --with requests \
      python src/agentclinic_code/build_experience.py \
      --results results/train_run/<...>.jsonl \
      --state $(pwd)/src/agentclinic_code/sea_state.json --model gpt-5-nano

  # Phase B - measure improvement on the test set
  ./src/agentclinic_code/run_experiment_selected.sh \
      --data_file <test.jsonl> --count M \
      --custom_doctor_agent_path src/agentclinic_code/sea_doctor_agent.py --name test_baseline
  SEA_MEMORY_ENABLED=1 SEA_MEMORY_STATE=$(pwd)/src/agentclinic_code/sea_state.json \
      ./src/agentclinic_code/run_experiment_selected.sh \
      --data_file <test.jsonl> --count M \
      --custom_doctor_agent_path src/agentclinic_code/sea_doctor_agent.py --name test_with_memory
  # compare the **Accuracy:** line in each run's report_v2_*.txt

Usage:
  python build_experience.py --results <results.jsonl> --state <abs path>/sea_state.json
                             [--model gpt-5-nano] [--k 16] [--no-llm]

  --no-llm  use SEA's offline MockSummarizer (deterministic, no API key, no deps
            beyond the standard library). Otherwise an LLM-backed summarizer is
            wired to the same query_model the agents use (needs OPENAI_API_KEY).
"""

import argparse
import json
import os
import sys

CODE_DIR = os.path.dirname(os.path.abspath(__file__))


def _sea_dir() -> str:
    """Locate the SEA dual-memory library: SEA_PATH env override, else the
    vendored copy in ./sea_memory (bundled so a fresh clone works)."""
    env = os.environ.get("SEA_PATH")
    if env:
        return os.path.abspath(env)
    return os.path.abspath(os.path.join(CODE_DIR, "sea_memory"))


def _strip_diagnosis_prefix(text: str) -> str:
    """Return the diagnosis text after a 'DIAGNOSIS READY:' marker, if present."""
    if not text:
        return ""
    marker = "diagnosis ready:"
    low = text.lower()
    idx = low.find(marker)
    if idx != -1:
        return text[idx + len(marker):].strip()
    return text.strip()


def _case_summary(problem_info: dict) -> str:
    """Compact, presentation-only summary built from the SAME field the recall
    query uses (Objective_for_Doctor), so lexical retrieval lines up."""
    osce = (problem_info or {}).get("OSCE_Examination", {}) or {}
    objective = osce.get("Objective_for_Doctor", "")
    if isinstance(objective, (dict, list)):
        objective = json.dumps(objective)
    objective = (objective or "").strip()
    return objective[:800]


def _make_summarizer(use_llm: bool, model: str):
    from llm import MockSummarizer  # SEA, stdlib-only

    if not use_llm:
        return MockSummarizer()

    from llm import InjectedSummarizer
    # Reuse the exact model-query path the agents use. Imported lazily so the
    # --no-llm path stays dependency-free (no openai import).
    sys.path.insert(0, CODE_DIR)
    from agentclinic_api_only import query_model

    sys_prompt = (
        "You distill reusable, generalizable diagnostic RULES from past clinical "
        "cases. Return ONLY JSON of the form {\"rules\": [...]}."
    )

    def chat_fn(prompt: str) -> str:
        out = query_model(model, prompt, sys_prompt)
        return out if isinstance(out, str) else json.dumps(out)

    return InjectedSummarizer(chat_fn)


def main() -> int:
    ap = argparse.ArgumentParser(description="Distill an AgentClinic results JSONL into SEA dual-memory.")
    ap.add_argument("--results", required=True, help="Path to a results JSONL produced by a run.")
    ap.add_argument("--state", required=True, help="Path to sea_state.json (use an ABSOLUTE path).")
    ap.add_argument("--model", default="gpt-5-nano", help="Model for LLM rule distillation.")
    ap.add_argument("--k", type=int, default=16, help="Short-term capacity K (new state only).")
    ap.add_argument("--no-llm", action="store_true", help="Use the offline MockSummarizer instead of an LLM.")
    args = ap.parse_args()

    if not os.path.isfile(args.results):
        print("ERROR: results file not found: {}".format(args.results), file=sys.stderr)
        return 1
    if not os.path.isabs(args.state):
        print("WARNING: --state is not absolute; the agent's parallel workers may run from a different cwd. "
              "Consider an absolute path.", file=sys.stderr)

    sys.path.insert(0, _sea_dir())
    try:
        from memory import DualMemory  # noqa: F401
    except Exception as exc:  # pragma: no cover - environment guard
        print("ERROR: could not import SEA from {} ({}). Set SEA_PATH.".format(_sea_dir(), exc), file=sys.stderr)
        return 1

    summarizer = _make_summarizer(use_llm=not args.no_llm, model=args.model)

    if os.path.isfile(args.state):
        mem = DualMemory.load(args.state, summarizer=summarizer)
        print("Loaded existing memory: {} (K={}, {} cases, {} rules)".format(
            args.state, mem.K, len(mem.short_term), len(mem.long_term)))
    else:
        mem = DualMemory(K=args.k, summarizer=summarizer, path=args.state, auto_save=True)
        print("Created new memory at {} (K={}, summarizer={})".format(
            args.state, args.k, type(summarizer).__name__))

    stored = 0
    skipped = 0
    new_rules_total = 0
    with open(args.results, "r") as fh:
        for line_no, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as exc:
                print("  [line {}] skipped (bad JSON: {})".format(line_no, exc))
                skipped += 1
                continue

            summary = _case_summary(rec.get("problem_info", {}))
            diagnosis = _strip_diagnosis_prefix(rec.get("model_diagnosis", ""))
            if not summary and not diagnosis:
                print("  [line {}] skipped (no objective and no diagnosis)".format(line_no))
                skipped += 1
                continue

            correct = bool(rec.get("correct", False))
            truth = str(rec.get("correct_diagnosis", "")).strip()
            feedback = "{}; truth={}".format("correct" if correct else "incorrect", truth)

            res = mem.add({
                "case_summary": summary or "(no objective recorded)",
                "candidates": [],  # MIMIC diagnoses are free-text
                "diagnosis": diagnosis,
                "correct": correct,
                "feedback": feedback,
                "reasoning": str(rec.get("model_uncertainty_reasoning", "")).strip(),
            })
            stored += 1
            new_rules = res.get("new_rules", []) or []
            new_rules_total += len(new_rules)
            tag = "OK " if correct else "MISS"
            print("  [{}] stored ({}) dx={!r} truth={!r}".format(stored, tag, diagnosis[:60], truth[:60]))
            for r in new_rules:
                print("       + learned rule: {}".format(getattr(r, "text", r)))

    print("-" * 56)
    print("Done. stored={} skipped={} new_rules_this_run={}".format(stored, skipped, new_rules_total))
    print("Memory now: {} cases (M^S), {} rules (M^L)".format(len(mem.short_term), len(mem.long_term)))
    print("State: {}".format(os.path.abspath(args.state)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
