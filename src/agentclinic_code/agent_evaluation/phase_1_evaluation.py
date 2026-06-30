#!/usr/bin/env python3
"""Evaluate one AgentClinic experiment from run logs."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
DATA_DIR = SCRIPT_DIR.parent / "data"
DEFAULT_GROUND_TRUTH = SCRIPT_DIR / "mimic_phase1_evaluation.json"
DEFAULT_HELPER_OUTPUT = SCRIPT_DIR / "phase_1_evaluation_results" / "phase_1_evaluation_results.json"
FACT_KEYS = (
    "demographics",
    "medical_history",
    "social_history",
    "symptoms",
    "physical_examination_findings",
    "test_results",
)
_CALL_OPENAI_STRUCTURED_JSON = None


EVAL_SCHEMA: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "agentclinic_experiment_evaluation",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                **{
                    key: {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "fact": {"type": "string"},
                                "included": {"type": "boolean"},
                                "reason": {"type": "string"},
                            },
                            "required": ["fact", "included", "reason"],
                            "additionalProperties": False,
                        },
                    }
                    for key in FACT_KEYS
                },
                "ground_truth_diagnosis": {
                    "type": "object",
                    "properties": {
                        "included": {"type": "boolean"},
                        "reason": {"type": "string"},
                    },
                    "required": ["included", "reason"],
                    "additionalProperties": False,
                },
            },
            "required": [*FACT_KEYS, "ground_truth_diagnosis"],
            "additionalProperties": False,
        },
    },
}


PROMPT = """Evaluate an AgentClinic OSCE note against ground-truth facts.

For each ground-truth fact, decide whether the OSCE note captured the same
clinical fact. Preserve negation and values. Use included=false if the note is
missing, contradicts, or is too vague. The reason must briefly explain why.

For ground_truth_diagnosis, decide whether the ground-truth diagnosis or a clear
clinical equivalent appears in the candidate differential list.
"""


def main() -> None:
    args = parse_args()
    ground_truth = load_ground_truth(args.ground_truth_jsonl)
    logs = load_experiment_logs(args.log_dir, args.experiment_id)
    if not logs:
        raise ValueError(f"No logs found for experiment_id={args.experiment_id!r}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    details_path = args.output_dir / f"{args.experiment_id}_reasoning_evaluation.jsonl"
    summary_path = args.output_dir / f"{args.experiment_id}_summary.json"

    results = []
    log_updates = []
    with details_path.open("w", encoding="utf-8") as handle:
        for log_path, log_data in logs:
            case = extract_case(log_data, log_path)
            gt = ground_truth.get(case["patient_id"])
            if gt is None:
                raise KeyError(f"No ground truth for patient_id={case['patient_id']}")
            evaluation = evaluate_case(case, gt, model=args.model)
            record = summarize_case(case, gt, evaluation, log_path)
            results.append(record)
            log_updates.append((log_path, log_data, record))
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            print(
                f"evaluated {case['patient_id']} "
                f"facts={record['overall_fact_coverage']['covered']}/"
                f"{record['overall_fact_coverage']['total']} "
                f"diagnosis={record['ground_truth_diagnosis']['included']}"
            )

    summary = summarize_experiment(args.experiment_id, results)
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.update_logs:
        update_logs(
            log_updates,
            summary,
            model=args.model,
            ground_truth_path=args.ground_truth_jsonl,
        )
    print(f"details_jsonl: {details_path}")
    print(f"summary_json:   {summary_path}")
    if args.update_logs:
        print(f"updated_logs:   {len(log_updates)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate logs for one experiment ID.")
    parser.add_argument("--experiment_id", required=True)
    parser.add_argument("--log_dir", type=Path, required=True)
    parser.add_argument("--ground_truth_jsonl", type=Path, default=DEFAULT_GROUND_TRUTH)
    parser.add_argument("--output_dir", type=Path, default=SCRIPT_DIR)
    parser.add_argument("--model", default="gpt-5.4-nano")
    parser.add_argument(
        "--no_update_logs",
        dest="update_logs",
        action="store_false",
        help="Do not write the evaluation block back into each matched log JSON.",
    )
    parser.set_defaults(update_logs=True)
    return parser.parse_args()


def load_ground_truth(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Ground-truth JSONL not found: {path}")
    rows: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            rows[row["patient_id"]] = row
    return rows


def load_experiment_logs(log_dir: Path, experiment_id: str) -> list[tuple[Path, dict[str, Any]]]:
    matched = []
    for path in sorted(log_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        metadata = data.get("task_visualization", {}).get("metadata", {})
        top_meta = data.get("meta", {})
        if metadata.get("experiment_id") == experiment_id or top_meta.get("experiment_id") == experiment_id:
            matched.append((path, data))
    return matched


def extract_case(log_data: dict[str, Any], log_path: Path) -> dict[str, Any]:
    task = log_data.get("task_visualization", {})
    metadata = task.get("metadata", {})
    top_meta = log_data.get("meta", {})
    result = task.get("result", {})
    patient_id = metadata.get("patient_id") or top_meta.get("patient_id") or result.get("patient_id")
    if not patient_id:
        raise ValueError(f"{log_path} is missing patient_id")
    return {
        "patient_id": str(patient_id),
        "experiment_id": metadata.get("experiment_id") or top_meta.get("experiment_id"),
        "scenario_id": metadata.get("scenario_id"),
        "osce_note": result.get("osce_note", {}),
        "differential_diagnosis_list": result.get("differential_diagnosis_list", ""),
    }


def evaluate_case(case: dict[str, Any], gt: dict[str, Any], *, model: str) -> dict[str, Any]:
    payload = {
        "ground_truth": {key: gt.get(key, []) for key in FACT_KEYS}
        | {"ground_truth_diagnosis": gt.get("ground_truth_diagnosis", "")},
        "osce_note": case["osce_note"],
        "candidate_differential_list": case["differential_diagnosis_list"],
    }
    return load_call_openai_structured_json()(
        [
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=2)},
        ],
        model=model,
        temperature=0.0,
        schema_name=EVAL_SCHEMA["json_schema"]["name"],
        json_schema=EVAL_SCHEMA["json_schema"]["schema"],
        strict=EVAL_SCHEMA["json_schema"]["strict"],
    )


def evaluate_and_save_phase_1_result(
    patient_id: str,
    experiment_id: str,
    osce_note: Any,
    differential_diagnosis_list: Any,
) -> dict[str, Any]:
    patient_id = str(patient_id)
    ground_truth = load_ground_truth(DEFAULT_GROUND_TRUTH)
    gt = ground_truth.get(patient_id)
    if gt is None:
        raise KeyError(f"No ground truth for patient_id={patient_id}")

    case = {
        "patient_id": patient_id,
        "experiment_id": str(experiment_id),
        "scenario_id": None,
        "osce_note": osce_note,
        "differential_diagnosis_list": differential_diagnosis_list,
    }
    evaluation = evaluate_case(case, gt, model="gpt-5.4-nano")
    record = summarize_case(case, gt, evaluation, log_path=None)
    append_json_record(DEFAULT_HELPER_OUTPUT, record)
    return record


def summarize_case(
    case: dict[str, Any],
    gt: dict[str, Any],
    evaluation: dict[str, Any],
    log_path: Path | None,
) -> dict[str, Any]:
    section_coverage = {}
    covered_total = 0
    fact_total = 0
    for key in FACT_KEYS:
        items = evaluation.get(key, [])
        covered = sum(1 for item in items if item.get("included"))
        total = len(gt.get(key, []))
        covered_total += covered
        fact_total += total
        section_coverage[key] = {
            "covered": covered,
            "total": total,
            "coverage": safe_ratio(covered, total),
            "items": items,
        }

    return {
        "patient_id": case["patient_id"],
        "experiment_id": case["experiment_id"],
        "scenario_id": case["scenario_id"],
        "log_path": str(log_path) if log_path is not None else None,
        "ground_truth_diagnosis": evaluation["ground_truth_diagnosis"],
        "section_coverage": section_coverage,
        "overall_fact_coverage": {
            "covered": covered_total,
            "total": fact_total,
            "coverage": safe_ratio(covered_total, fact_total),
        },
    }


def append_json_record(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(existing, list):
            raise ValueError(f"Expected a JSON list in {path}")
    else:
        existing = []
    existing.append(record)
    path.write_text(json.dumps(existing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def summarize_experiment(experiment_id: str, results: list[dict[str, Any]]) -> dict[str, Any]:
    diagnosis_hits = sum(1 for item in results if item["ground_truth_diagnosis"]["included"])
    section_totals = {}
    for key in FACT_KEYS:
        covered = sum(item["section_coverage"][key]["covered"] for item in results)
        total = sum(item["section_coverage"][key]["total"] for item in results)
        section_totals[key] = {
            "covered": covered,
            "total": total,
            "coverage": safe_ratio(covered, total),
        }
    covered_total = sum(item["overall_fact_coverage"]["covered"] for item in results)
    fact_total = sum(item["overall_fact_coverage"]["total"] for item in results)
    return {
        "experiment_id": experiment_id,
        "cases": len(results),
        "ground_truth_in_candidate_list": {
            "included": diagnosis_hits,
            "total": len(results),
            "score": safe_ratio(diagnosis_hits, len(results)),
        },
        "fact_coverage": {
            "covered": covered_total,
            "total": fact_total,
            "coverage": safe_ratio(covered_total, fact_total),
            "by_section": section_totals,
        },
    }


def update_logs(
    log_updates: list[tuple[Path, dict[str, Any], dict[str, Any]]],
    summary: dict[str, Any],
    *,
    model: str,
    ground_truth_path: Path,
) -> None:
    updated_at = datetime.now(timezone.utc).isoformat()
    for log_path, log_data, record in log_updates:
        evaluation_block = {
            "schema_version": "agentclinic_phase1_evaluation.v1",
            "updated_at": updated_at,
            "model": model,
            "ground_truth_jsonl": str(ground_truth_path),
            "case": record,
            "experiment_summary": summary,
        }
        log_data["evaluation"] = evaluation_block
        task = log_data.setdefault("task_visualization", {})
        if isinstance(task, dict):
            task["evaluation"] = evaluation_block
        log_path.write_text(
            json.dumps(log_data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )


def safe_ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def load_call_openai_structured_json():
    global _CALL_OPENAI_STRUCTURED_JSON
    if _CALL_OPENAI_STRUCTURED_JSON is not None:
        return _CALL_OPENAI_STRUCTURED_JSON
    helper_path = PROJECT_ROOT / "src" / "agent" / "openai_llm_calling_core.py"
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    spec = importlib.util.spec_from_file_location("agent_openai_llm_calling_core", helper_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load OpenAI helper from {helper_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _CALL_OPENAI_STRUCTURED_JSON = module.call_openai_structured_json
    return _CALL_OPENAI_STRUCTURED_JSON


if __name__ == "__main__":
    main()
