#!/usr/bin/env python3
"""Generate phase-1 ground-truth fact lists from AgentClinic MIMIC cases.

The script calls the shared OpenAI helper at `src/agent/openai_llm_calling_core.py`
with a strict JSON schema. Each output JSONL row keeps the input `patient_id`
and appends the fact-list structure described in `phase_1_evaluation_prompt.md`.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
AGENTCLINIC_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
DATA_DIR = AGENTCLINIC_DIR / "data"
DEFAULT_INPUT = DATA_DIR / "mimic_training.jsonl"
DEFAULT_PROMPT = SCRIPT_DIR / "phase_1_evaluation_prompt.md"
DEFAULT_OUTPUT = SCRIPT_DIR / "mimic_phase1_evaluation.json"

FACT_LIST_KEYS = (
    "demographics",
    "medical_history",
    "social_history",
    "symptoms",
    "physical_examination_findings",
    "test_results",
)

PHASE_1_GROUND_TRUTH_SCHEMA: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "agentclinic_phase_1_ground_truth",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                **{
                    key: {
                        "type": "array",
                        "items": {"type": "string"},
                    }
                    for key in FACT_LIST_KEYS
                },
                "ground_truth_diagnosis": {"type": "string"},
            },
            "required": [*FACT_LIST_KEYS, "ground_truth_diagnosis"],
            "additionalProperties": False,
        },
    },
}

_CALL_OPENAI_STRUCTURED_JSON = None


def main() -> None:
    args = parse_args()
    rows = load_rows(args.input_jsonl, start=args.start, limit=args.limit)
    prompt = args.prompt_md.read_text(encoding="utf-8")

    if args.output_jsonl.exists() and not args.overwrite:
        raise FileExistsError(
            f"Output already exists: {args.output_jsonl}. Use --overwrite to replace it."
        )
    args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)

    with args.output_jsonl.open("w", encoding="utf-8") as handle:
        for source_line, row in rows:
            patient_id = require_patient_id(row, source_line, args.input_jsonl)
            ground_truth = generate_ground_truth(
                row,
                prompt=prompt,
                model=args.model,
                temperature=args.temperature,
            )
            output_row = {"patient_id": patient_id, **ground_truth}
            handle.write(json.dumps(output_row, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")
            handle.flush()
            print(f"generated patient_id={patient_id} source_line={source_line}")

    print(f"wrote: {args.output_jsonl}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Transform MIMIC training JSONL into phase-1 ground-truth facts."
    )
    parser.add_argument("--input_jsonl", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output_jsonl", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--prompt_md", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--model", default="gpt-5.4-nano")
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--start", type=int, default=0, help="0-based input row offset")
    parser.add_argument("--limit", type=int, default=None, help="Maximum rows to process")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def load_rows(
    input_path: Path,
    *,
    start: int,
    limit: int | None,
) -> list[tuple[int, dict[str, Any]]]:
    if start < 0:
        raise ValueError("--start must be non-negative")
    if limit is not None and limit < 1:
        raise ValueError("--limit must be positive")
    if not input_path.exists():
        raise FileNotFoundError(f"Input JSONL not found: {input_path}")

    rows: list[tuple[int, dict[str, Any]]] = []
    with input_path.open("r", encoding="utf-8") as handle:
        for line_index, line in enumerate(handle):
            if line_index < start:
                continue
            if limit is not None and len(rows) >= limit:
                break
            stripped = line.strip()
            if not stripped:
                continue
            row = json.loads(stripped)
            if not isinstance(row, dict):
                raise ValueError(f"{input_path} line {line_index + 1} is not an object")
            rows.append((line_index + 1, row))
    return rows


def require_patient_id(row: dict[str, Any], source_line: int, input_path: Path) -> str:
    patient_id = row.get("patient_id")
    if not isinstance(patient_id, str) or not patient_id.strip():
        raise ValueError(
            f"{input_path} line {source_line} is missing top-level patient_id. "
            "Run assign_mimic_patient_ids.py first."
        )
    return patient_id.strip()


def generate_ground_truth(
    row: dict[str, Any],
    *,
    prompt: str,
    model: str,
    temperature: float,
) -> dict[str, Any]:
    case_payload = {
        "patient_id": row["patient_id"],
        "OSCE_Examination": row.get("OSCE_Examination", {}),
    }
    payload = load_call_openai_structured_json()(
        [
            {
                "role": "system",
                "content": (
                    prompt
                    + "\n\nReturn only a JSON object matching the requested schema. "
                    "Do not include patient_id in your response."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(case_payload, ensure_ascii=False, indent=2),
            },
        ],
        model=model,
        temperature=temperature,
        schema_name=PHASE_1_GROUND_TRUTH_SCHEMA["json_schema"]["name"],
        json_schema=PHASE_1_GROUND_TRUTH_SCHEMA["json_schema"]["schema"],
        strict=PHASE_1_GROUND_TRUTH_SCHEMA["json_schema"]["strict"],
    )
    return normalize_ground_truth(payload)


def normalize_ground_truth(payload: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key in FACT_LIST_KEYS:
        value = payload.get(key, [])
        if not isinstance(value, list):
            value = []
        facts = [str(item).strip() for item in value if str(item).strip()]
        normalized[key] = ensure_numbered(facts)
    normalized["ground_truth_diagnosis"] = str(
        payload.get("ground_truth_diagnosis", "")
    ).strip()
    return normalized


def ensure_numbered(facts: list[str]) -> list[str]:
    numbered: list[str] = []
    for index, fact in enumerate(facts, start=1):
        prefix = f"{index}. "
        if fact.startswith(prefix):
            numbered.append(fact)
            continue
        without_existing_number = re.sub(r"^\d+\.\s*", "", fact)
        numbered.append(prefix + without_existing_number.strip())
    return numbered


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
