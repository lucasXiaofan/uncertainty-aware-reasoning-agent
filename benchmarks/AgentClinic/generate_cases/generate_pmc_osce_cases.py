#!/usr/bin/env python3
"""Generate AgentClinic OSCE JSONL cases from PMC-Patients.csv.

The pipeline intentionally uses two model calls per candidate:
1. decide whether the raw patient description has a clear final diagnosis;
2. if yes, convert it to the AgentClinic OSCE structure.
"""

from __future__ import annotations

import argparse
import ast
import csv
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.agent.openai_llm_calling_core import call_openai_json


DEFAULT_SOURCE = REPO_ROOT / "PMC-Patients.csv"
DEFAULT_JSONL = REPO_ROOT / "src" / "agentclinic_code" / "data" / "pmc_patients_osce_20.jsonl"
DEFAULT_LOG = REPO_ROOT / "outputs" / "pmc_patients_osce_20_generation_log.md"
TUTORIAL_PROMPT_PATH = REPO_ROOT / "benchmarks" / "AgentClinic" / "generate_cases" / "gen_medqa_tutorial.py"

OSCE_REQUIRED_FIELDS = {
    "Objective_for_Doctor",
    "Patient_Actor",
    "Physical_Examination_Findings",
    "Test_Results",
    "Correct_Diagnosis",
}


def load_tutorial_example() -> str:
    tree = ast.parse(TUTORIAL_PROMPT_PATH.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "examples":
                    value = ast.literal_eval(node.value)
                    if isinstance(value, str):
                        return value
    raise RuntimeError(f"Could not find examples string in {TUTORIAL_PROMPT_PATH}")


def load_rows(source_path: Path) -> tuple[list[dict[str, str]], dict[str, dict[str, str]]]:
    csv.field_size_limit(sys.maxsize)
    with source_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return rows, {row["patient_uid"]: row for row in rows}


def parse_mapping(value: str) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = ast.literal_eval(value)
    except (SyntaxError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def prompt_safe_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    head_chars = max_chars * 2 // 3
    tail_chars = max_chars - head_chars
    return (
        text[:head_chars]
        + "\n\n[...middle of source text omitted for prompt length...]\n\n"
        + text[-tail_chars:]
    )


def row_metadata(row: dict[str, str]) -> dict[str, str]:
    return {
        "patient_id": row.get("patient_id", ""),
        "patient_uid": row.get("patient_uid", ""),
        "PMID": row.get("PMID", ""),
        "title": row.get("title", ""),
        "age": row.get("age", ""),
        "gender": row.get("gender", ""),
        "file_path": row.get("file_path", ""),
    }


def diagnosis_check(row: dict[str, str], *, model: str, max_chars: int) -> dict[str, Any]:
    metadata = row_metadata(row)
    source_text = prompt_safe_text(row.get("patient", ""), max_chars)
    messages = [
        {
            "role": "system",
            "content": (
                "You are a clinical dataset curator. Decide whether a PMC case "
                "description contains a clear final diagnosis suitable for an OSCE. "
                "Return only valid JSON. A clear diagnosis may be explicitly stated "
                "in the case text, title, pathology, imaging conclusion, operative "
                "finding, or treatment outcome. Reject vague rehabilitation summaries, "
                "lists of symptoms without a final disease, or cases where multiple "
                "competing final diagnoses remain unresolved. For ICD-10-CM, provide "
                "the single most relevant code if reasonably inferable; otherwise use UNKNOWN."
            ),
        },
        {
            "role": "user",
            "content": (
                "Evaluate this patient case.\n\n"
                f"Metadata:\n{json.dumps(metadata, indent=2)}\n\n"
                f"Patient text:\n{source_text}\n\n"
                "Return JSON with exactly these keys:\n"
                "- has_clear_final_diagnosis: boolean\n"
                "- normalized_final_diagnosis: string\n"
                "- diagnosis_evidence: string\n"
                "- reason_if_rejected: string\n"
                "- most_relevant_icd_10_code: string\n"
            ),
        },
    ]
    return call_openai_json(messages, model=model, temperature=0.1)


def generate_osce(
    row: dict[str, str],
    *,
    diagnosis: str,
    model: str,
    examples: str,
    max_chars: int,
) -> dict[str, Any]:
    metadata = row_metadata(row)
    source_text = prompt_safe_text(row.get("patient", ""), max_chars)
    messages = [
        {
            "role": "system",
            "content": (
                "Please generate a sample Objective Structured Clinical Examination "
                "(OSCE) for the patient actor and the doctor, including what the "
                "correct diagnosis should be as a structured json. Only provide the "
                "doctor with the objective and provide test results as a separate "
                "category. Provide these for a primary care doctor exam. Return only "
                "valid JSON."
            ),
        },
        {
            "role": "user",
            "content": (
                "Generate an OSCE for the following PMC patient case. Use the provided "
                "diagnosis as the Correct_Diagnosis. Preserve source-supported details "
                "and avoid inventing specific normal findings when the source does not "
                "support them; use 'Not specified in source' when needed.\n\n"
                f"Correct diagnosis: {diagnosis}\n\n"
                f"Metadata:\n{json.dumps(metadata, indent=2)}\n\n"
                f"Patient text:\n{source_text}\n\n"
                "Here is an example of the correct OSCE format:\n"
                f"{examples}\n\n"
                "Please create a new one here. Return a JSON object with the top-level "
                "key OSCE_Examination only."
            ),
        },
    ]
    osce = call_openai_json(messages, model=model, temperature=0.2)
    if "OSCE_Examination" not in osce or not isinstance(osce["OSCE_Examination"], dict):
        raise RuntimeError("Generated OSCE is missing OSCE_Examination")
    missing = sorted(OSCE_REQUIRED_FIELDS - set(osce["OSCE_Examination"]))
    if missing:
        raise RuntimeError(f"Generated OSCE is missing required fields: {missing}")
    osce["OSCE_Examination"]["Correct_Diagnosis"] = diagnosis
    return osce


def build_record(
    row: dict[str, str],
    osce: dict[str, Any],
    check: dict[str, Any],
    *,
    relevant_row: dict[str, str] | None,
    source_kind: str,
) -> dict[str, Any]:
    record = {
        "patient_id": row.get("patient_id", ""),
        "relevant_patient_id": relevant_row.get("patient_id", "") if relevant_row else None,
        "most_relevant_icd_10_code": check.get("most_relevant_icd_10_code", "UNKNOWN") or "UNKNOWN",
        "OSCE_Examination": osce["OSCE_Examination"],
        "patient_uid": row.get("patient_uid", ""),
        "relevant_patient_uid": relevant_row.get("patient_uid", "") if relevant_row else None,
        "source_kind": source_kind,
        "PMID": row.get("PMID", ""),
        "title": row.get("title", ""),
        "diagnosis_evidence": check.get("diagnosis_evidence", ""),
    }
    return record


def md_escape_fence(text: str) -> str:
    return text.replace("```", "'''")


def append_log_for_candidate(
    parts: list[str],
    *,
    index: int,
    row: dict[str, str],
    source_kind: str,
    relevant_row: dict[str, str] | None,
    check: dict[str, Any],
    record: dict[str, Any] | None,
) -> None:
    metadata = row_metadata(row)
    parts.append(f"## Candidate {index}: `{metadata['patient_uid']}` ({source_kind})")
    parts.append("### Metadata")
    parts.append(f"- `patient_id`: `{metadata['patient_id']}`")
    parts.append(f"- `patient_uid`: `{metadata['patient_uid']}`")
    if relevant_row:
        parts.append(f"- `relevant_patient_id`: `{relevant_row.get('patient_id', '')}`")
        parts.append(f"- `relevant_patient_uid`: `{relevant_row.get('patient_uid', '')}`")
    else:
        parts.append("- `relevant_patient_id`: `null`")
    parts.append(f"- `PMID`: `{metadata['PMID']}`")
    parts.append(f"- Title: {metadata['title']}")
    parts.append(f"- Age: `{metadata['age']}`")
    parts.append(f"- Gender: `{metadata['gender']}`")
    parts.append("")
    parts.append("### Step 1: Clear Diagnosis Check")
    parts.append("```json")
    parts.append(json.dumps(check, indent=2, ensure_ascii=False))
    parts.append("```")
    parts.append("")
    parts.append("### Raw Patient Text")
    parts.append("```text")
    parts.append(md_escape_fence(row.get("patient", "")))
    parts.append("```")
    parts.append("")
    if record is None:
        parts.append("### Step 2: OSCE Transform")
        parts.append("Skipped because the diagnosis check did not pass.")
    else:
        parts.append("### Step 2: Generated AgentClinic Record")
        parts.append("```json")
        parts.append(json.dumps(record, indent=2, ensure_ascii=False))
        parts.append("```")
    parts.append("")


def similar_rows_for(row: dict[str, str], by_uid: dict[str, dict[str, str]]) -> list[dict[str, str]]:
    mapping = parse_mapping(row.get("similar_patients", ""))
    sorted_uids = sorted(mapping, key=lambda uid: (-float(mapping.get(uid, 0)), uid))
    return [by_uid[uid] for uid in sorted_uids if uid in by_uid]


def validate_record(record: dict[str, Any]) -> None:
    osce = record.get("OSCE_Examination")
    if not isinstance(osce, dict):
        raise RuntimeError("record missing OSCE_Examination")
    missing = sorted(OSCE_REQUIRED_FIELDS - set(osce))
    if missing:
        raise RuntimeError(f"record missing OSCE fields: {missing}")


def iter_candidates(rows: list[dict[str, str]], by_uid: dict[str, dict[str, str]]):
    seen: set[str] = set()
    for row in rows:
        uid = row.get("patient_uid", "")
        if uid in seen:
            continue
        seen.add(uid)
        yield row, None, "primary"
        for similar_row in similar_rows_for(row, by_uid):
            similar_uid = similar_row.get("patient_uid", "")
            if similar_uid in seen:
                continue
            seen.add(similar_uid)
            yield similar_row, row, "similar"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-jsonl", type=Path, default=DEFAULT_JSONL)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--model", default="gpt-5.4-mini")
    parser.add_argument("--num-cases", type=int, default=20)
    parser.add_argument("--max-evaluated", type=int, default=120)
    parser.add_argument("--max-prompt-chars", type=int, default=12000)
    parser.add_argument("--sleep", type=float, default=0.2)
    args = parser.parse_args()

    load_dotenv(REPO_ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise EnvironmentError("OPENAI_API_KEY is not set; add it to .env or the environment")

    examples = load_tutorial_example()
    rows, by_uid = load_rows(args.source)

    args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)

    accepted: list[dict[str, Any]] = []
    log_parts = [
        "# PMC Patients to AgentClinic OSCE Generation Log",
        "",
        f"- Source: `{args.source}`",
        f"- Output JSONL: `{args.output_jsonl}`",
        f"- Model: `{args.model}`",
        f"- Target accepted cases: `{args.num_cases}`",
        f"- Max evaluated candidates: `{args.max_evaluated}`",
        "",
    ]

    evaluated = 0
    for row, relevant_row, source_kind in iter_candidates(rows, by_uid):
        if len(accepted) >= args.num_cases or evaluated >= args.max_evaluated:
            break
        evaluated += 1
        print(
            f"[{evaluated}] checking {source_kind} patient_uid={row.get('patient_uid')} "
            f"accepted={len(accepted)}/{args.num_cases}",
            flush=True,
        )
        try:
            check = diagnosis_check(row, model=args.model, max_chars=args.max_prompt_chars)
        except Exception as exc:
            check = {
                "has_clear_final_diagnosis": False,
                "normalized_final_diagnosis": "",
                "diagnosis_evidence": "",
                "reason_if_rejected": f"diagnosis check failed: {exc}",
                "most_relevant_icd_10_code": "UNKNOWN",
            }
            append_log_for_candidate(
                log_parts,
                index=evaluated,
                row=row,
                source_kind=source_kind,
                relevant_row=relevant_row,
                check=check,
                record=None,
            )
            continue

        if not bool(check.get("has_clear_final_diagnosis")):
            append_log_for_candidate(
                log_parts,
                index=evaluated,
                row=row,
                source_kind=source_kind,
                relevant_row=relevant_row,
                check=check,
                record=None,
            )
            time.sleep(args.sleep)
            continue

        diagnosis = str(check.get("normalized_final_diagnosis") or "").strip()
        if not diagnosis:
            check["has_clear_final_diagnosis"] = False
            check["reason_if_rejected"] = "accepted check lacked normalized_final_diagnosis"
            append_log_for_candidate(
                log_parts,
                index=evaluated,
                row=row,
                source_kind=source_kind,
                relevant_row=relevant_row,
                check=check,
                record=None,
            )
            continue

        print(f"    transforming diagnosis={diagnosis}", flush=True)
        try:
            osce = generate_osce(
                row,
                diagnosis=diagnosis,
                model=args.model,
                examples=examples,
                max_chars=args.max_prompt_chars,
            )
            record = build_record(
                row,
                osce,
                check,
                relevant_row=relevant_row,
                source_kind=source_kind,
            )
            validate_record(record)
        except Exception as exc:
            check["reason_if_rejected"] = f"OSCE transform failed: {exc}"
            append_log_for_candidate(
                log_parts,
                index=evaluated,
                row=row,
                source_kind=source_kind,
                relevant_row=relevant_row,
                check=check,
                record=None,
            )
            continue

        accepted.append(record)
        append_log_for_candidate(
            log_parts,
            index=evaluated,
            row=row,
            source_kind=source_kind,
            relevant_row=relevant_row,
            check=check,
            record=record,
        )
        with args.output_jsonl.open("w", encoding="utf-8") as handle:
            for accepted_record in accepted:
                handle.write(json.dumps(accepted_record, ensure_ascii=False) + "\n")
        args.output_md.write_text("\n".join(log_parts), encoding="utf-8")
        time.sleep(args.sleep)

    with args.output_jsonl.open("w", encoding="utf-8") as handle:
        for accepted_record in accepted:
            handle.write(json.dumps(accepted_record, ensure_ascii=False) + "\n")

    summary = [
        "## Summary",
        "",
        f"- Evaluated candidates: `{evaluated}`",
        f"- Accepted OSCE cases: `{len(accepted)}`",
        f"- Output JSONL: `{args.output_jsonl}`",
    ]
    log_parts[7:7] = summary + [""]
    args.output_md.write_text("\n".join(log_parts), encoding="utf-8")
    print(f"accepted={len(accepted)} evaluated={evaluated} jsonl={args.output_jsonl} md={args.output_md}")


if __name__ == "__main__":
    main()
