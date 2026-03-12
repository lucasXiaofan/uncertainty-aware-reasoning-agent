#!/usr/bin/env python3
"""Build med_knowledge CSV from cleaned Mayo Clinic JSON."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path


def extract_section(markdown_text: str, heading: str) -> str:
    lines = markdown_text.splitlines()
    start = -1
    for i, line in enumerate(lines):
        if line.strip().lower() == f"## {heading}".lower():
            start = i
            break
    if start == -1:
        return ""

    out: list[str] = [lines[start].strip()]
    for line in lines[start + 1 :]:
        # Stop at the next same-level section.
        if re.match(r"^\s*##\s+\S+", line):
            break
        out.append(line.rstrip())
    return "\n".join(out).strip()


def build_rows(data: dict) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for record in data.get("records", []):
        disease = record.get("disease", "").strip()

        symptoms_obj = record.get("symptoms_causes", {})
        symptoms_text = extract_section(symptoms_obj.get("clean_content", ""), "Symptoms")
        if symptoms_text:
            rows.append(
                {
                    "disease_name": disease,
                    "knowledge_type": "symptoms",
                    "knowledge_content": symptoms_text,
                    "source_url": symptoms_obj.get("final_url")
                    or symptoms_obj.get("source_url", ""),
                }
            )

        diagnosis_obj = record.get("diagnosis_treatment", {})
        diagnosis_text = extract_section(
            diagnosis_obj.get("clean_content", ""), "Diagnosis"
        )
        if diagnosis_text:
            rows.append(
                {
                    "disease_name": disease,
                    "knowledge_type": "diagnosis",
                    "knowledge_content": diagnosis_text,
                    "source_url": diagnosis_obj.get("final_url")
                    or diagnosis_obj.get("source_url", ""),
                }
            )
    return rows


def run(input_json: Path, output_csv: Path) -> None:
    payload = json.loads(input_json.read_text(encoding="utf-8"))
    rows = build_rows(payload)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "disease_name",
                "knowledge_type",
                "knowledge_content",
                "source_url",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {output_csv}")


def main() -> None:
    default_input = (
        Path(__file__).resolve().parent
        / "med_resource"
        / "mayoclinic_disease_pages_clean.json"
    )
    default_output = Path(__file__).resolve().parent / "med_resource" / "med_knowledge.csv"

    parser = argparse.ArgumentParser(description="Build med_knowledge.csv from Mayo JSON.")
    parser.add_argument("input_json", type=Path, nargs="?", default=default_input)
    parser.add_argument("--output", type=Path, default=default_output)
    args = parser.parse_args()

    run(args.input_json, args.output)


if __name__ == "__main__":
    main()
