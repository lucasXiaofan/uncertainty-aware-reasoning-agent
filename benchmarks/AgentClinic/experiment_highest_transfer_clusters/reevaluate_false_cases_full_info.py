#!/usr/bin/env python3
"""Re-evaluate failed AgentClinic runs using full problem_info.

For each case with "correct": false in an input results JSONL file:
1) Send full problem_info to gpt-5-mini to produce a diagnosis.
2) Use compare_results from agentclinic_api_only.py to judge correctness.
3) Save per-case outcomes to CSV in the results directory.
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from openai import OpenAI
from dotenv import load_dotenv

# Ensure local project imports work regardless of invocation method.
SCRIPT_PATH = Path(__file__).resolve()
AGENTCLINIC_DIR = SCRIPT_PATH.parents[1]
REPO_ROOT = SCRIPT_PATH.parents[3]
if str(AGENTCLINIC_DIR) not in sys.path:
    sys.path.insert(0, str(AGENTCLINIC_DIR))

# Load environment variables from common locations so OPENAI_API_KEY can be read
# without requiring manual export in shell.
load_dotenv(REPO_ROOT / ".env")
load_dotenv(AGENTCLINIC_DIR / ".env")

# Import project evaluator logic
import agentclinic_api_only as agentclinic


SYSTEM_PROMPT = (
    "You are an expert clinician. Given a complete patient case, provide the most likely final diagnosis. "
    "Respond with a concise diagnosis statement only."
)


def load_false_cases(input_jsonl: Path):
    false_cases = []
    with input_jsonl.open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("correct") is False:
                row["_line_index"] = idx
                false_cases.append(row)
    return false_cases


def build_prompt(problem_info: dict) -> str:
    payload = json.dumps(problem_info, ensure_ascii=False, indent=2)
    return (
        "Use the full case information below to determine the single most likely diagnosis.\n\n"
        f"{payload}\n\n"
        "Final diagnosis:"
    )


def resolve_client(provider: str):
    if provider == "openrouter":
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise EnvironmentError("OPENROUTER_API_KEY is required when --provider openrouter")
        return OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY is required when --provider openai")
    return OpenAI(api_key=api_key)


def output_path_for_input(input_jsonl: Path, output_csv: Path | None, ts: str, multiple_inputs: bool) -> Path:
    if output_csv is not None:
        if multiple_inputs:
            raise ValueError("--output_csv can only be used with a single --input_jsonl file")
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        return output_csv
    return input_jsonl.parent / f"{input_jsonl.stem}_false_cases_full_info_eval_{ts}.csv"


def evaluate_one_file(input_jsonl: Path, output_csv: Path, model: str, moderator_model: str):
    false_cases = load_false_cases(input_jsonl)
    rows = []

    for i, case in enumerate(false_cases):
        problem_info = case.get("problem_info", {})
        prompt = build_prompt(problem_info)

        predicted = agentclinic.query_model(
            model,
            prompt,
            SYSTEM_PROMPT,
        )

        correct_diagnosis = str(case.get("correct_diagnosis", ""))
        original_model_diagnosis = str(case.get("model_diagnosis", ""))
        original_uncertainty_reasoning = str(case.get("model_uncertainty_reasoning", ""))

        original_compare_raw = agentclinic.compare_results(
            original_model_diagnosis,
            correct_diagnosis,
            moderator_model,
        )
        original_reevaluated_correct = str(original_compare_raw).strip().lower().startswith("yes")

        compare_raw = agentclinic.compare_results(
            predicted,
            correct_diagnosis,
            moderator_model,
        )
        reevaluated_correct = str(compare_raw).strip().lower().startswith("yes")

        rows.append(
            {
                "reevaluated_correct": reevaluated_correct,
                "input_line_index": case.get("_line_index"),
                "dataset": case.get("dataset"),
                "scenario_id": case.get("scenario_id"),
                "original_model_diagnosis": original_model_diagnosis,
                "original_uncertainty_reasoning": original_uncertainty_reasoning,
                "original_compare_results_raw": original_compare_raw,
                "original_reevaluated_correct": original_reevaluated_correct,
                "correct_diagnosis": correct_diagnosis,
                "full_info_model": model,
                "full_info_prediction": predicted,
                "moderator_model": moderator_model,
                "compare_results_raw": compare_raw,
            }
        )

        print(
            f"[{i + 1}/{len(false_cases)}] {input_jsonl.name} "
            f"scenario_id={case.get('scenario_id')} reevaluated_correct={reevaluated_correct}"
        )

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "reevaluated_correct",
            "input_line_index",
            "dataset",
            "scenario_id",
            "original_model_diagnosis",
            "original_uncertainty_reasoning",
            "original_compare_results_raw",
            "original_reevaluated_correct",
            "correct_diagnosis",
            "full_info_model",
            "full_info_prediction",
            "moderator_model",
            "compare_results_raw",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Processed false cases: {len(false_cases)}")
    print(f"Saved CSV: {output_csv}")


def main():
    parser = argparse.ArgumentParser(description="Re-evaluate false cases using full problem_info and compare_results.")
    parser.add_argument(
        "--input_jsonl",
        type=Path,
        nargs="+",
        required=True,
        help="One or more paths to run-results JSONL files",
    )
    parser.add_argument(
        "--output_csv",
        type=Path,
        default=None,
        help="Optional output CSV path (single input only). For multiple inputs, one CSV is created per input file.",
    )
    parser.add_argument(
        "--provider",
        choices=["openrouter", "openai"],
        default="openrouter",
        help="API provider used by both diagnosis and moderator calls",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="openai/gpt-5-mini",
        help="Model used to answer diagnosis from full problem_info (default OpenRouter model id)",
    )
    parser.add_argument(
        "--moderator_model",
        type=str,
        default="openai/gpt-5-mini",
        help="Model used by compare_results for yes/no grading",
    )
    args = parser.parse_args()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    inputs = [p.resolve() for p in args.input_jsonl]
    multiple_inputs = len(inputs) > 1

    for p in inputs:
        if not p.exists():
            raise FileNotFoundError(f"Input file not found: {p}")

    # Ensure compare_results uses one initialized client from selected provider.
    agentclinic.client = resolve_client(args.provider)

    for input_jsonl in inputs:
        output_csv = output_path_for_input(input_jsonl, args.output_csv, ts, multiple_inputs)
        evaluate_one_file(
            input_jsonl=input_jsonl,
            output_csv=output_csv,
            model=args.model,
            moderator_model=args.moderator_model,
        )


if __name__ == "__main__":
    main()
