#!/usr/bin/env python3
"""Evaluate AgentClinic phase-1 information gathering outputs.

The input is a run-results JSONL file containing `problem_info`,
`correct_diagnosis`, `differential_diagnosis_list`, and `osce_note`.
The script writes:
- a JSONL file with one structured evaluation record per case
- a Markdown report with diagnosis-in-differential and OSCE-note overlap sections

Run from the repository root:

    uv run python src/agentclinic_code/phase_1_evaluation.py \
      src/agentclinic_code/results/<experiment>/<result_file>.jsonl \
      --output_dir src/agentclinic_code/results/<experiment>

Optional fixed output paths:

    uv run python src/agentclinic_code/phase_1_evaluation.py \
      src/agentclinic_code/results/<experiment>/<result_file>.jsonl \
      --details_jsonl src/agentclinic_code/results/<experiment>/phase_1_details.jsonl \
      --report_md src/agentclinic_code/results/<experiment>/phase_1_report.md

The evaluator calls OpenAI through `src/agent/openai_llm_calling_core.py`, so
`OPENAI_API_KEY` must be set unless an API key is supplied through that helper.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from datetime import datetime
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_CALL_OPENAI_JSON = None

CATEGORY_KEYS = (
    "demographics",
    "medical_history",
    "social_history",
    "symptoms",
    "physical_examination_findings",
    "tests",
)

EVALUATION_SCHEMA: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "phase_1_case_evaluation",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "diagnosis_evaluation": {
                    "type": "object",
                    "properties": {
                        "correct_diagnosis_in_differential": {"type": "boolean"},
                        "matched_differential_diagnosis": {"type": "string"},
                        "rationale": {"type": "string"},
                    },
                    "required": [
                        "correct_diagnosis_in_differential",
                        "matched_differential_diagnosis",
                        "rationale",
                    ],
                    "additionalProperties": False,
                },
                "osce_note_overlap": {
                    "type": "object",
                    "properties": {
                        key: {
                            "type": "object",
                            "properties": {
                                "covered_points": {"type": "integer"},
                                "total_unique_points": {"type": "integer"},
                                "coverage_ratio": {"type": "number"},
                                "points": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "point": {"type": "string"},
                                            "covered": {"type": "boolean"},
                                            "osce_note_evidence": {"type": "string"},
                                        },
                                        "required": [
                                            "point",
                                            "covered",
                                            "osce_note_evidence",
                                        ],
                                        "additionalProperties": False,
                                    },
                                },
                            },
                            "required": [
                                "covered_points",
                                "total_unique_points",
                                "coverage_ratio",
                                "points",
                            ],
                            "additionalProperties": False,
                        }
                        for key in CATEGORY_KEYS
                    },
                    "required": list(CATEGORY_KEYS),
                    "additionalProperties": False,
                },
                "overall_osce_note_overlap": {
                    "type": "object",
                    "properties": {
                        "covered_points": {"type": "integer"},
                        "total_unique_points": {"type": "integer"},
                        "coverage_ratio": {"type": "number"},
                        "summary": {"type": "string"},
                    },
                    "required": [
                        "covered_points",
                        "total_unique_points",
                        "coverage_ratio",
                        "summary",
                    ],
                    "additionalProperties": False,
                },
            },
            "required": [
                "diagnosis_evaluation",
                "osce_note_overlap",
                "overall_osce_note_overlap",
            ],
            "additionalProperties": False,
        },
    },
}

SYSTEM_PROMPT = """You are evaluating AgentClinic phase-1 information gathering.
Return only the requested JSON object.

Part 1: determine whether the correct diagnosis is present in the differential
diagnosis list. Count semantic equivalents, abbreviations, and clinically
equivalent labels as present. Do not count a broad organ-system category unless
it clearly names the target diagnosis.

Part 2: evaluate OSCE-note overlap. Extract concise, unique factual points from
the source case by category. A point is covered only when the OSCE note states
the same clinical fact, including relevant negation and specific values when
important. Do not award credit for vague mentions.

Use these categories exactly:
demographics, medical_history, social_history, symptoms,
physical_examination_findings, tests.
"""


def main() -> None:
    args = parse_args()
    input_jsonl = args.input_jsonl.resolve()
    rows = load_result_rows(input_jsonl, start=args.start, limit=args.limit)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = (args.output_dir or input_jsonl.parent).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    details_path = (
        args.details_jsonl
        or output_dir / f"{input_jsonl.stem}_phase_1_evaluation_{timestamp}.jsonl"
    )
    report_path = (
        args.report_md
        or output_dir / f"{input_jsonl.stem}_phase_1_evaluation_{timestamp}.md"
    )
    details_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    evaluations: list[dict[str, Any]] = []
    with details_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            evaluation = evaluate_case(row, model=args.model, temperature=args.temperature)
            evaluations.append(evaluation)
            handle.write(json.dumps(evaluation, ensure_ascii=False) + "\n")
            print(
                "evaluated "
                f"line={evaluation['input_line_index']} "
                f"scenario_id={evaluation.get('scenario_id')} "
                f"diagnosis_in_differential="
                f"{evaluation['diagnosis_evaluation']['correct_diagnosis_in_differential']} "
                f"osce_overlap={format_ratio(evaluation['overall_osce_note_overlap'])}"
            )

    report_path.write_text(
        render_report(
            evaluations,
            input_jsonl=input_jsonl,
            model=args.model,
            details_path=details_path,
        ),
        encoding="utf-8",
    )
    print(f"details_jsonl: {details_path}")
    print(f"report_md:     {report_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate phase-1 diagnosis differential and OSCE-note overlap."
    )
    parser.add_argument("input_jsonl", type=Path, help="AgentClinic result JSONL file")
    parser.add_argument("--model", default="gpt-5.4-nano", help="OpenAI model for evaluation")
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--start", type=int, default=0, help="0-based input line offset")
    parser.add_argument("--limit", type=int, default=None, help="Maximum records to evaluate")
    parser.add_argument("--output_dir", type=Path, default=None)
    parser.add_argument("--details_jsonl", type=Path, default=None)
    parser.add_argument("--report_md", type=Path, default=None)
    return parser.parse_args()


def load_result_rows(input_jsonl: Path, *, start: int, limit: int | None) -> list[dict[str, Any]]:
    if start < 0:
        raise ValueError("--start must be non-negative")
    if limit is not None and limit < 1:
        raise ValueError("--limit must be positive")
    if not input_jsonl.exists():
        raise FileNotFoundError(f"Input JSONL not found: {input_jsonl}")

    rows: list[dict[str, Any]] = []
    with input_jsonl.open("r", encoding="utf-8") as handle:
        for line_index, line in enumerate(handle):
            if line_index < start:
                continue
            if limit is not None and len(rows) >= limit:
                break
            stripped = line.strip()
            if not stripped:
                continue
            row = json.loads(stripped)
            row["_line_index"] = line_index
            rows.append(row)
    return rows


def evaluate_case(row: dict[str, Any], *, model: str, temperature: float) -> dict[str, Any]:
    correct_diagnosis = str(row.get("correct_diagnosis", "")).strip()
    differential = first_non_empty(
        row.get("differential_diagnosis_list"),
        row.get("model_uncertainty_reasoning"),
    )
    osce_note = stringify_osce_note(row.get("osce_note", ""))
    source_categories = extract_source_categories(row.get("problem_info", {}))

    payload = load_call_openai_json()(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "case_metadata": {
                            "dataset": row.get("dataset"),
                            "scenario_id": row.get("scenario_id"),
                            "input_line_index": row.get("_line_index"),
                        },
                        "correct_diagnosis": correct_diagnosis,
                        "differential_diagnosis_list": differential,
                        "osce_note": osce_note,
                        "source_case_by_category": source_categories,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            },
        ],
        model=model,
        temperature=temperature,
        response_format=EVALUATION_SCHEMA,
    )
    normalized = normalize_evaluation(payload)
    return {
        "input_line_index": row.get("_line_index"),
        "dataset": row.get("dataset"),
        "scenario_id": row.get("scenario_id"),
        "correct_diagnosis": correct_diagnosis,
        "differential_diagnosis_list": differential,
        "osce_note": osce_note,
        **normalized,
    }


def load_call_openai_json():
    global _CALL_OPENAI_JSON
    if _CALL_OPENAI_JSON is not None:
        return _CALL_OPENAI_JSON

    helper_path = PROJECT_ROOT / "src" / "agent" / "openai_llm_calling_core.py"
    spec = importlib.util.spec_from_file_location("agent_openai_llm_calling_core", helper_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load OpenAI helper from {helper_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _CALL_OPENAI_JSON = module.call_openai_json
    return _CALL_OPENAI_JSON


def extract_source_categories(problem_info: Any) -> dict[str, Any]:
    if not isinstance(problem_info, dict):
        return {key: "" for key in CATEGORY_KEYS}

    osce = problem_info.get("OSCE_Examination")
    if isinstance(osce, dict):
        patient_actor = osce.get("Patient_Actor") or {}
        if not isinstance(patient_actor, dict):
            patient_actor = {"Patient_Actor": patient_actor}

        return {
            "demographics": pick(patient_actor, "Demographics", "demographics"),
            "medical_history": pick(
                patient_actor,
                "Past_Medical_History",
                "Medical_History",
                "medical_history",
            ),
            "social_history": pick(patient_actor, "Social_History", "social_history"),
            "symptoms": {
                "History": patient_actor.get("History"),
                "Symptoms": patient_actor.get("Symptoms"),
                "Review_of_Systems": patient_actor.get("Review_of_Systems"),
            },
            "physical_examination_findings": osce.get("Physical_Examination_Findings", {}),
            "tests": osce.get("Test_Results", {}),
        }

    return {
        "demographics": pick(problem_info, "Demographics", "demographics"),
        "medical_history": pick(
            problem_info,
            "Past_Medical_History",
            "Medical_History",
            "medical_history",
            "patient_info",
        ),
        "social_history": pick(problem_info, "Social_History", "social_history"),
        "symptoms": pick(problem_info, "Symptoms", "symptoms", "question"),
        "physical_examination_findings": pick(
            problem_info,
            "Physical_Examination_Findings",
            "physical_exams",
            "physical_examination_findings",
        ),
        "tests": pick(problem_info, "Test_Results", "tests", "answers"),
    }


def normalize_evaluation(payload: dict[str, Any]) -> dict[str, Any]:
    overlap = payload.get("osce_note_overlap")
    if not isinstance(overlap, dict):
        overlap = {}
    for key in CATEGORY_KEYS:
        overlap[key] = normalize_category_overlap(overlap.get(key))

    covered_total = sum(overlap[key]["covered_points"] for key in CATEGORY_KEYS)
    unique_total = sum(overlap[key]["total_unique_points"] for key in CATEGORY_KEYS)
    overall = payload.get("overall_osce_note_overlap")
    if not isinstance(overall, dict):
        overall = {}
    overall["covered_points"] = covered_total
    overall["total_unique_points"] = unique_total
    overall["coverage_ratio"] = safe_ratio(covered_total, unique_total)
    overall["summary"] = str(overall.get("summary", "")).strip()

    diagnosis = payload.get("diagnosis_evaluation")
    if not isinstance(diagnosis, dict):
        diagnosis = {}
    diagnosis = {
        "correct_diagnosis_in_differential": bool(
            diagnosis.get("correct_diagnosis_in_differential", False)
        ),
        "matched_differential_diagnosis": str(
            diagnosis.get("matched_differential_diagnosis", "")
        ).strip(),
        "rationale": str(diagnosis.get("rationale", "")).strip(),
    }
    return {
        "diagnosis_evaluation": diagnosis,
        "osce_note_overlap": overlap,
        "overall_osce_note_overlap": overall,
    }


def normalize_category_overlap(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        value = {}
    points = value.get("points")
    if not isinstance(points, list):
        points = []

    normalized_points = []
    for item in points:
        if not isinstance(item, dict):
            continue
        normalized_points.append(
            {
                "point": str(item.get("point", "")).strip(),
                "covered": bool(item.get("covered", False)),
                "osce_note_evidence": str(item.get("osce_note_evidence", "")).strip(),
            }
        )

    total = int_or_zero(value.get("total_unique_points"))
    if total == 0 and normalized_points:
        total = len(normalized_points)
    covered = int_or_zero(value.get("covered_points"))
    if normalized_points:
        covered = sum(1 for item in normalized_points if item["covered"])
    total = max(total, len(normalized_points))
    covered = min(covered, total)
    return {
        "covered_points": covered,
        "total_unique_points": total,
        "coverage_ratio": safe_ratio(covered, total),
        "points": normalized_points,
    }


def render_report(
    evaluations: list[dict[str, Any]],
    *,
    input_jsonl: Path,
    model: str,
    details_path: Path,
) -> str:
    diagnosis_hits = sum(
        1
        for item in evaluations
        if item["diagnosis_evaluation"]["correct_diagnosis_in_differential"]
    )
    total_cases = len(evaluations)
    aggregate = aggregate_overlap(evaluations)

    lines = [
        "# Phase 1 Evaluation Report",
        "",
        f"- Input: `{input_jsonl}`",
        f"- Evaluator model: `{model}`",
        f"- Cases evaluated: {total_cases}",
        f"- Details JSONL: `{details_path}`",
        "",
        "## Summary",
        "",
        f"- Correct diagnosis in differential: {diagnosis_hits}/{total_cases}",
        f"- Overall OSCE-note overlap: {format_ratio(aggregate['overall'])}",
        "",
        "## Part 1: Correct Diagnosis in Differential",
        "",
        "| Line | Dataset | Scenario | Correct diagnosis | In differential | Matched differential | Rationale |",
        "|---:|---|---:|---|---|---|---|",
    ]

    for item in evaluations:
        diagnosis = item["diagnosis_evaluation"]
        lines.append(
            "| "
            f"{item['input_line_index']} | "
            f"{escape_md(item.get('dataset'))} | "
            f"{item.get('scenario_id')} | "
            f"{escape_md(item.get('correct_diagnosis'))} | "
            f"{'yes' if diagnosis['correct_diagnosis_in_differential'] else 'no'} | "
            f"{escape_md(diagnosis['matched_differential_diagnosis'])} | "
            f"{escape_md(diagnosis['rationale'])} |"
        )

    lines.extend(
        [
            "",
            "## Part 2: OSCE Note Overlap",
            "",
            "### Aggregate Coverage",
            "",
            "| Category | Covered / Total | Coverage |",
            "|---|---:|---:|",
        ]
    )
    for key in CATEGORY_KEYS:
        lines.append(
            f"| {key} | {format_ratio(aggregate[key])} | "
            f"{format_percent(aggregate[key]['coverage_ratio'])} |"
        )
    lines.append(
        f"| overall | {format_ratio(aggregate['overall'])} | "
        f"{format_percent(aggregate['overall']['coverage_ratio'])} |"
    )

    lines.extend(
        [
            "",
            "### Per-Case Coverage",
            "",
            "| Line | Scenario | Overall | Demographics | Medical history | Social history | Symptoms | Physical exam | Tests |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for item in evaluations:
        overlap = item["osce_note_overlap"]
        lines.append(
            "| "
            f"{item['input_line_index']} | "
            f"{item.get('scenario_id')} | "
            f"{format_ratio(item['overall_osce_note_overlap'])} | "
            f"{format_ratio(overlap['demographics'])} | "
            f"{format_ratio(overlap['medical_history'])} | "
            f"{format_ratio(overlap['social_history'])} | "
            f"{format_ratio(overlap['symptoms'])} | "
            f"{format_ratio(overlap['physical_examination_findings'])} | "
            f"{format_ratio(overlap['tests'])} |"
        )

    lines.extend(["", "### Case Details", ""])
    for item in evaluations:
        lines.extend(render_case_detail(item))

    return "\n".join(lines) + "\n"


def render_case_detail(item: dict[str, Any]) -> list[str]:
    lines = [
        f"#### Line {item['input_line_index']} / Scenario {item.get('scenario_id')}",
        "",
        f"- Correct diagnosis: {item.get('correct_diagnosis')}",
        f"- Differential diagnosis list: {item.get('differential_diagnosis_list')}",
        f"- Overall overlap: {format_ratio(item['overall_osce_note_overlap'])}",
        "",
    ]
    for key in CATEGORY_KEYS:
        category = item["osce_note_overlap"][key]
        lines.append(f"- {key}: {format_ratio(category)}")
        missed = [point for point in category["points"] if not point["covered"]]
        if missed:
            sample = "; ".join(point["point"] for point in missed[:5])
            lines.append(f"  - missed examples: {sample}")
    lines.append("")
    return lines


def aggregate_overlap(evaluations: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    aggregate: dict[str, dict[str, Any]] = {}
    for key in CATEGORY_KEYS:
        covered = sum(item["osce_note_overlap"][key]["covered_points"] for item in evaluations)
        total = sum(item["osce_note_overlap"][key]["total_unique_points"] for item in evaluations)
        aggregate[key] = {
            "covered_points": covered,
            "total_unique_points": total,
            "coverage_ratio": safe_ratio(covered, total),
        }
    covered_total = sum(aggregate[key]["covered_points"] for key in CATEGORY_KEYS)
    unique_total = sum(aggregate[key]["total_unique_points"] for key in CATEGORY_KEYS)
    aggregate["overall"] = {
        "covered_points": covered_total,
        "total_unique_points": unique_total,
        "coverage_ratio": safe_ratio(covered_total, unique_total),
    }
    return aggregate


def pick(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return ""


def first_non_empty(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def stringify_osce_note(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2)
    if value is None:
        return ""
    return str(value).strip()


def int_or_zero(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def safe_ratio(covered: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(covered / total, 4)


def format_ratio(value: dict[str, Any]) -> str:
    return f"{value.get('covered_points', 0)}/{value.get('total_unique_points', 0)}"


def format_percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def escape_md(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    main()
