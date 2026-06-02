# SEA-Memory Doctor Agent for AgentClinic

A custom doctor agent that plugs into AgentClinic via `--custom_doctor_agent_path`,
plus an offline tool that distills past cases into a reusable **dual memory**
(short-term cases + long-term rules) using the SEA dual-memory library, which is
**vendored** into `sea_memory/` so a fresh clone works out of the box.

The agent works in two modes from a **single file**:

- **Baseline** (no env vars): behaves exactly like the built-in `DoctorAgent`.
- **Dual-memory**: recalls relevant past cases + distilled rules and injects them
  into the doctor's prompt. Reasoning code is identical in both modes, so any
  accuracy difference is attributable to memory.

## Files

| File | Purpose |
|---|---|
| `sea_doctor_agent.py` | The doctor agent (env-toggled baseline ↔ dual-memory). Pass to `--custom_doctor_agent_path`. |
| `build_experience.py` | Offline "remember" step: turns a results JSONL into `sea_state.json`. |
| `sea_memory/` | Vendored SEA dual-memory library (`memory.py`, `llm.py`). Pure standard library. See `sea_memory/VENDORED.md`. |

## Prerequisites

- Run all commands from the **`UAT_Agent/`** directory.
- Set your OpenAI key (the runner reads `OPENAI_API_KEY`; it also loads a `.env`):
  ```bash
  export OPENAI_API_KEY="sk-..."          # simplest
  # or create UAT_Agent/src/agentclinic_code/.env  with:  OPENAI_API_KEY=sk-...
  ```
  (For OpenRouter instead, set `OPENROUTER_API_KEY`; the runner auto-detects it.)
- `uv` is used to supply Python dependencies for the runs.

## Environment toggles (read by `sea_doctor_agent.py`)

| Variable | Effect |
|---|---|
| `SEA_MEMORY_ENABLED` | `1`/`true`/`yes`/`on` turns recall **on**. Unset/anything else → baseline. |
| `SEA_MEMORY_STATE` | **Absolute** path to `sea_state.json` (built by `build_experience.py`). |
| `SEA_PATH` | Optional. Path to a SEA checkout (for dev). Defaults to the vendored `sea_memory/`. |

The agent is **read-only** on the state file (safe under the runner's parallel
workers). Any memory error degrades silently to baseline, so a bad path never
breaks a run.

---

## Option 1 — Baseline run (smoke test)

Runs the full AgentClinic pipeline with memory **off**. Verifies the agent loads
and the end-to-end flow works.

```bash
./src/agentclinic_code/run_experiment_selected.sh \
  --data_file src/agentclinic_code/data/agentclinic_mimiciv_false_cases_with_guideline.jsonl \
  --count 2 \
  --custom_doctor_agent_path src/agentclinic_code/sea_doctor_agent.py \
  --name cp1_baseline
```

What it does:
1. Selects the first 2 cases; auto-detects the dataset as `MIMICIV`.
2. Spawns one subprocess per case running `agentclinic_api_only.py` with your agent.
3. Simulates the case: Doctor (your agent) ↔ Patient ↔ Measurement over up to 30
   turns, ending in `DIAGNOSIS READY: …`; a Moderator compares it to the
   ground-truth diagnosis → `correct: true/false`.
4. Writes `results/cp1_baseline/…jsonl`, a `report_v2_*.txt` (with an **Accuracy**
   line), and a false-case re-eval. **Note the results JSONL path — Option 2 uses it.**

---

## Option 2 — Add dual memory (two steps)

### Step 1: Build the memory (offline "remember")

Distills the results of a run into `sea_state.json`.

```bash
uv run --with 'openai>=1.0.0' --with regex --with python-dotenv --with pyyaml --with requests \
  python src/agentclinic_code/build_experience.py \
  --results results/cp1_baseline/<...>.jsonl \
  --state $(pwd)/src/agentclinic_code/sea_state.json \
  --model gpt-5-nano
```

What it does: for each finished case it stores the presentation + predicted
diagnosis + correctness + truth in short-term memory; when capacity fills, it
evicts the oldest and uses the model to **distill reusable rules** into long-term
memory. `$(pwd)/…` makes the state path absolute (required by parallel workers).

Flags: `--k <N>` short-term capacity for a new state (default 16); `--no-llm` uses
SEA's offline `MockSummarizer` (deterministic, no API key) instead of the model —
useful for a dry run, but its rules are generic and recall less well, so use the
default (LLM) path for real experiments.

### Step 2: Re-run with recall (use memory)

Same run as Option 1, but the `SEA_*` env-var prefix turns recall on for this run.

```bash
SEA_MEMORY_ENABLED=1 SEA_MEMORY_STATE=$(pwd)/src/agentclinic_code/sea_state.json \
  ./src/agentclinic_code/run_experiment_selected.sh \
  --data_file src/agentclinic_code/data/agentclinic_mimiciv_false_cases_with_guideline.jsonl \
  --count 2 \
  --custom_doctor_agent_path src/agentclinic_code/sea_doctor_agent.py \
  --name cp3_recall
```

Now, per case, the agent loads `sea_state.json` read-only, retrieves the past
cases + rules most relevant to the current objective, and injects them into the
doctor's system prompt as a `## CLINICAL MEMORY` hints block. Compare the
**Accuracy** lines of `results/cp1_baseline/…` vs `results/cp3_recall/…`.

---

## Full experiment: train → test accuracy delta

Memory should be built from a **training** split and evaluated on a **separate
testing** split. When the real splits are ready:

```bash
# Phase A — generate experience on TRAIN (memory off; it's empty anyway)
./src/agentclinic_code/run_experiment_selected.sh \
  --data_file <train.jsonl> --count N \
  --custom_doctor_agent_path src/agentclinic_code/sea_doctor_agent.py --name train_run

uv run --with 'openai>=1.0.0' --with regex --with python-dotenv --with pyyaml --with requests \
  python src/agentclinic_code/build_experience.py \
  --results results/train_run/<...>.jsonl \
  --state $(pwd)/src/agentclinic_code/sea_state.json --model gpt-5-nano

# Phase B — evaluate on TEST, twice
./src/agentclinic_code/run_experiment_selected.sh \
  --data_file <test.jsonl> --count M \
  --custom_doctor_agent_path src/agentclinic_code/sea_doctor_agent.py --name test_baseline

SEA_MEMORY_ENABLED=1 SEA_MEMORY_STATE=$(pwd)/src/agentclinic_code/sea_state.json \
  ./src/agentclinic_code/run_experiment_selected.sh \
  --data_file <test.jsonl> --count M \
  --custom_doctor_agent_path src/agentclinic_code/sea_doctor_agent.py --name test_with_memory
# compare **Accuracy:** in results/test_baseline/report_v2_*.txt vs results/test_with_memory/report_v2_*.txt
```

**Dry-run before the splits land:** use disjoint slices of the false-cases file —
build from cases `0–14` (`--start 0 --count 15`) and test on `15–29`
(`--start 15 --count 15`).

> Caveat: building memory from the *same* cases you then evaluate on (as in the
> Option 1 → Option 2 smoke test above) only proves the plumbing — the agent would
> partly recall the very cases it's judged on. Use separate train/test sets for a
> meaningful accuracy delta.

## Notes

- **Concurrency:** the runner fans out parallel workers (`--workers`, default 10).
  The agent only *reads* the state, so that's safe. Writing happens only in
  `build_experience.py`, which is single-process. If you use a slow/rate-limited
  free model, add `--workers 1`.
- **Why the LLM summarizer matters:** SEA retrieves by lexical token overlap.
  LLM-distilled rules mention symptoms (e.g. "chest pain"), so they overlap with
  case presentations and actually surface at recall; the offline `MockSummarizer`'s
  generic rules often don't.
