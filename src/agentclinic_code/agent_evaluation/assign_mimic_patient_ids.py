#!/usr/bin/env python3
"""Assign stable top-level patient IDs to MIMIC train/test JSONL cases.

IDs are derived from the matching line in `agentclinic_mimiciv.jsonl`:
source line 4 becomes `mimic_0004`. The script matches by canonical JSON
content, ignoring any existing top-level `patient_id`, so it is idempotent.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
AGENTCLINIC_DIR = SCRIPT_DIR.parent
DATA_DIR = AGENTCLINIC_DIR / "data"
DEFAULT_SOURCE = DATA_DIR / "agentclinic_mimiciv.jsonl"
DEFAULT_TARGETS = (
    DATA_DIR / "mimic_training.jsonl",
    DATA_DIR / "mimic_testing.jsonl",
)


def main() -> None:
    args = parse_args()
    source_index = build_source_index(args.source_jsonl)
    for target_path in args.target_jsonl:
        assign_patient_ids(
            target_path,
            source_index=source_index,
            dry_run=args.dry_run,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add stable top-level mimic_xxxx patient IDs to split JSONL files."
    )
    parser.add_argument(
        "--source_jsonl",
        type=Path,
        default=DEFAULT_SOURCE,
        help="Original AgentClinic MIMIC-IV JSONL file.",
    )
    parser.add_argument(
        "target_jsonl",
        nargs="*",
        type=Path,
        default=list(DEFAULT_TARGETS),
        help="Split JSONL files to update in place.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print assignments without writing files.",
    )
    return parser.parse_args()


def build_source_index(source_path: Path) -> dict[str, str]:
    if not source_path.exists():
        raise FileNotFoundError(f"Source JSONL not found: {source_path}")

    canonical_to_ids: dict[str, list[str]] = defaultdict(list)
    for line_number, row in iter_jsonl(source_path):
        canonical_to_ids[canonical_case(row)].append(f"mimic_{line_number:04d}")

    duplicates = {
        canonical: ids for canonical, ids in canonical_to_ids.items() if len(ids) > 1
    }
    if duplicates:
        examples = list(duplicates.values())[:3]
        raise ValueError(f"Source file has duplicate canonical cases: {examples}")

    return {canonical: ids[0] for canonical, ids in canonical_to_ids.items()}


def assign_patient_ids(
    target_path: Path,
    *,
    source_index: dict[str, str],
    dry_run: bool,
) -> None:
    if not target_path.exists():
        raise FileNotFoundError(f"Target JSONL not found: {target_path}")

    updated_lines: list[str] = []
    assignments: list[str] = []
    for line_number, row, raw_line in iter_jsonl_with_raw_lines(target_path):
        patient_id = source_index.get(canonical_case(row))
        if patient_id is None:
            raise ValueError(
                f"No source match for {target_path} line {line_number}. "
                "Check that the target file originated from agentclinic_mimiciv.jsonl."
            )

        existing_id = row.get("patient_id")
        if existing_id not in (None, patient_id):
            raise ValueError(
                f"{target_path} line {line_number} has patient_id={existing_id!r}, "
                f"but source-derived ID is {patient_id!r}."
            )

        updated_lines.append(line_with_patient_id(raw_line, patient_id, bool(existing_id)))
        assignments.append(f"{line_number}:{patient_id}")

    if dry_run:
        print(f"{target_path}: validated {len(updated_lines)} rows")
        print(", ".join(assignments))
        return

    tmp_path = target_path.with_suffix(target_path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        for line in updated_lines:
            handle.write(line)
    tmp_path.replace(target_path)
    print(f"{target_path}: wrote {len(updated_lines)} patient IDs")


def iter_jsonl(path: Path) -> list[tuple[int, dict[str, Any]]]:
    rows: list[tuple[int, dict[str, Any]]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            row = json.loads(stripped)
            if not isinstance(row, dict):
                raise ValueError(f"{path} line {line_number} is not a JSON object")
            rows.append((line_number, row))
    return rows


def iter_jsonl_with_raw_lines(path: Path) -> list[tuple[int, dict[str, Any], str]]:
    rows: list[tuple[int, dict[str, Any], str]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            row = json.loads(stripped)
            if not isinstance(row, dict):
                raise ValueError(f"{path} line {line_number} is not a JSON object")
            rows.append((line_number, row, stripped))
    return rows


def line_with_patient_id(raw_line: str, patient_id: str, already_present: bool) -> str:
    if already_present:
        return raw_line + "\n"
    if not raw_line.startswith("{"):
        raise ValueError("JSON object line must start with '{'")
    patient_id_json = json.dumps(patient_id, ensure_ascii=False)
    return f'{{"patient_id":{patient_id_json},{raw_line[1:]}\n'


def canonical_case(row: dict[str, Any]) -> str:
    row_without_id = dict(row)
    row_without_id.pop("patient_id", None)
    return json.dumps(row_without_id, sort_keys=True, separators=(",", ":"))


if __name__ == "__main__":
    main()
