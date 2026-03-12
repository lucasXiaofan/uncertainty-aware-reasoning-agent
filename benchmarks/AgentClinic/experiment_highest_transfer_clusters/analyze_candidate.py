#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = ["openai>=1.0.0", "python-dotenv"]
# ///
"""
Analyze whether doctor uncertainty reasoning contains the correct diagnosis as a candidate.
Uses LLM (deepseek-v3.2 via OpenRouter) for semantic matching since diagnosis names may differ.
"""

import json
import os
import sys
import argparse
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()    

OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "")
MODEL = "deepseek/deepseek-v3.2"

SYSTEM_PROMPT = """You are a medical expert evaluating whether a doctor's differential diagnosis list contains a specific correct diagnosis.

Your task: determine if the "Doctor Uncertainty" text mentions the correct diagnosis as one of the candidates, even if worded differently (e.g., "Congenital rubella syndrome" and "Congenital Rubella Infection" refer to the same condition).

Respond ONLY with a valid JSON object with these fields:
{
  "contains_correct_diagnosis": true/false,
  "matching_candidate_quote": "<exact quote from Doctor Uncertainty that matches the correct diagnosis, or null if not found>",
  "reasoning": "<brief explanation of why it matches or does not match>"
}
"""

USER_TEMPLATE = """Correct Diagnosis: {correct_diagnosis}

Doctor Uncertainty:
{doctor_uncertainty}

Does the Doctor Uncertainty text contain the correct diagnosis as a candidate (possibly under a different but equivalent name)?"""


def extract_doctor_uncertainty(dialogue_history: list) -> str:
    entries = []
    for i, turn in enumerate(dialogue_history):
        if isinstance(turn, str) and turn.startswith("Doctor_Uncertainty:"):
            text = turn[len("Doctor_Uncertainty:"):].strip()
            entries.append(f"[Turn {i}] {text}")
    return "\n\n".join(entries)


def analyze_case(client: OpenAI, case: dict) -> dict:
    correct_diagnosis = case["correct_diagnosis"]
    doctor_uncertainty = extract_doctor_uncertainty(case.get("dialogue_history", []))

    prompt = USER_TEMPLATE.format(
        correct_diagnosis=correct_diagnosis,
        doctor_uncertainty=doctor_uncertainty,
    )

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    try:
        analysis = json.loads(raw)
    except json.JSONDecodeError:
        analysis = {"parse_error": raw}

    return {
        "scenario_id": case.get("scenario_id"),
        "correct": case.get("correct"),
        "correct_diagnosis": correct_diagnosis,
        "doctor_uncertainty": doctor_uncertainty,
        "contains_correct_diagnosis": analysis.get("contains_correct_diagnosis"),
        "matching_candidate_quote": analysis.get("matching_candidate_quote"),
        "reasoning": analysis.get("reasoning"),
        "llm_raw": analysis if "parse_error" in analysis else None,
    }


def main():
    parser = argparse.ArgumentParser(description="Analyze doctor uncertainty for correct diagnosis candidates")
    parser.add_argument("input_jsonl", help="Path to input JSONL file")
    parser.add_argument(
        "-o", "--output",
        help="Output JSON file path (default: <input_stem>_analysis.json)",
        default=None,
    )
    parser.add_argument(
        "--api-key",
        help="OpenRouter API key (default: $OPENROUTER_API_KEY)",
        default=OPENROUTER_KEY,
    )
    args = parser.parse_args()

    if not args.api_key:
        print("ERROR: OpenRouter API key not set. Use --api-key or set OPENROUTER_API_KEY.", file=sys.stderr)
        sys.exit(1)

    if args.output is None:
        stem = args.input_jsonl.rsplit(".", 1)[0]
        args.output = stem + "_analysis.json"

    client = OpenAI(api_key=args.api_key, base_url="https://openrouter.ai/api/v1")

    cases = []
    with open(args.input_jsonl) as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))

    print(f"Processing {len(cases)} cases with {MODEL}...")

    results = []
    for i, case in enumerate(cases):
        sid = case.get("scenario_id", i)
        print(f"  [{i+1}/{len(cases)}] scenario_id={sid} correct={case.get('correct')} diagnosis={case['correct_diagnosis']!r}")
        result = analyze_case(client, case)
        results.append(result)
        found = result.get("contains_correct_diagnosis")
        quote = result.get("matching_candidate_quote", "")
        print(f"    -> in_candidates: {found} | quote: {str(quote)[:100]}")

    # Group into three categories of interest
    # Group A: wrong diagnosis, but correct answer WAS in candidate list (recoverable failure)
    group_wrong_with_candidate = [
        r for r in results
        if r.get("correct") is False and r.get("contains_correct_diagnosis") is True
    ]
    # Group B: wrong diagnosis, correct answer NOT in candidate list (blind spot)
    group_wrong_without_candidate = [
        r for r in results
        if r.get("correct") is False and r.get("contains_correct_diagnosis") is False
    ]
    # Group C: correct diagnosis, but it was NOT listed as a candidate (lucky guess / implicit reasoning)
    group_correct_without_candidate = [
        r for r in results
        if r.get("correct") is True and r.get("contains_correct_diagnosis") is False
    ]
    # Group D (baseline / ideal): correct diagnosis and it WAS in candidate list
    group_correct_with_candidate = [
        r for r in results
        if r.get("correct") is True and r.get("contains_correct_diagnosis") is True
    ]

    total = len(results)
    output_data = {
        "summary": {
            "total_cases": total,
            "group_A_wrong_had_candidate": len(group_wrong_with_candidate),
            "group_B_wrong_missed_candidate": len(group_wrong_without_candidate),
            "group_C_correct_no_candidate": len(group_correct_without_candidate),
            "group_D_correct_had_candidate": len(group_correct_with_candidate),
        },
        "group_A_wrong_diagnosis_correct_was_candidate": {
            "description": "Doctor gave wrong final diagnosis, but the correct diagnosis WAS listed as a candidate in uncertainty",
            "count": len(group_wrong_with_candidate),
            "cases": group_wrong_with_candidate,
        },
        "group_B_wrong_diagnosis_correct_never_candidate": {
            "description": "Doctor gave wrong final diagnosis AND the correct diagnosis was NEVER listed as a candidate",
            "count": len(group_wrong_without_candidate),
            "cases": group_wrong_without_candidate,
        },
        "group_C_correct_diagnosis_not_in_candidates": {
            "description": "Doctor gave correct final diagnosis but it was NOT explicitly listed as a candidate in uncertainty reasoning",
            "count": len(group_correct_without_candidate),
            "cases": group_correct_without_candidate,
        },
        "group_D_correct_diagnosis_was_candidate": {
            "description": "Doctor gave correct final diagnosis and it WAS listed as a candidate (ideal outcome)",
            "count": len(group_correct_with_candidate),
            "cases": group_correct_with_candidate,
        },
    }

    with open(args.output, "w") as f:
        json.dump(output_data, f, indent=2)

    print(f"\nResults saved to: {args.output}")
    print(f"  Group A (wrong dx, had candidate):    {len(group_wrong_with_candidate)}")
    print(f"  Group B (wrong dx, missed candidate): {len(group_wrong_without_candidate)}")
    print(f"  Group C (correct dx, no candidate):   {len(group_correct_without_candidate)}")
    print(f"  Group D (correct dx, had candidate):  {len(group_correct_with_candidate)}")


if __name__ == "__main__":
    main()
