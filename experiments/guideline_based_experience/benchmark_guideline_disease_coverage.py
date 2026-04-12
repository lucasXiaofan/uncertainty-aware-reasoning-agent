#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
import unicodedata
from pathlib import Path


THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = THIS_DIR.parents[1]

BENCHMARK_PATHS = {
    "agentclinic_medqa_extended_fixed": REPO_ROOT
    / "benchmarks/AgentClinic/agentclinic_medqa_extended_fixed.jsonl",
    "agentclinic_mimiciv": REPO_ROOT / "benchmarks/AgentClinic/agentclinic_mimiciv.jsonl",
}
MAYO_PATH = THIS_DIR / "mayoclinical.json"
RESULTS_DIR = THIS_DIR / "结果"
OUTPUT_CSV = THIS_DIR / "benchmark_guideline_disease_coverage.csv"


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def diagnosis_variants(diagnosis: str) -> list[str]:
    candidates = {diagnosis.strip()}

    no_paren = re.sub(r"\([^)]*\)", "", diagnosis).strip(" ,;-")
    if no_paren:
        candidates.add(no_paren)

    for group in re.findall(r"\(([^)]*)\)", diagnosis):
        group = group.strip()
        if group:
            candidates.add(group)

    normalized = {normalize_text(candidate) for candidate in candidates if candidate.strip()}
    return sorted(value for value in normalized if value)


def load_unique_diseases() -> dict[str, dict[str, object]]:
    diseases: dict[str, dict[str, object]] = {}

    for source_name, path in BENCHMARK_PATHS.items():
        with path.open() as handle:
            for line in handle:
                row = json.loads(line)
                diagnosis = row["OSCE_Examination"]["Correct_Diagnosis"].strip()
                if diagnosis not in diseases:
                    diseases[diagnosis] = {
                        "sources": set(),
                        "count": 0,
                        "variants": diagnosis_variants(diagnosis),
                    }
                diseases[diagnosis]["sources"].add(source_name)
                diseases[diagnosis]["count"] += 1

    return diseases


def load_mayo_entries() -> list[dict[str, object]]:
    raw_data = json.loads(MAYO_PATH.read_text())
    entries = []
    for item in raw_data:
        raw_text = item.get("text", "")
        if not raw_text:
            continue

        lines = raw_text.splitlines()
        title = lines[0].strip() if lines else ""
        entries.append(
            {
                "id": item.get("id", ""),
                "title": title,
                "normalized_title": normalize_text(title),
                "normalized_text": normalize_text(raw_text),
            }
        )
    return entries


def find_in_mayo_json(entries: list[dict[str, object]], variants: list[str]) -> dict[str, object]:
    title_match = {
        "found": False,
        "match_type": "",
        "match_id": "",
        "match_title": "",
    }
    text_match = {
        "found": False,
        "match_type": "",
        "match_id": "",
        "match_title": "",
    }

    for item in entries:
        normalized_title = item["normalized_title"]
        normalized_text = item["normalized_text"]

        for variant in variants:
            if variant == normalized_title:
                title_match = {
                    "found": True,
                    "match_type": "title_exact",
                    "match_id": item["id"],
                    "match_title": item["title"],
                }
                return {
                    "found": True,
                    "found_in_title": True,
                    "found_in_text": True,
                    **title_match,
                }
            if variant and variant in normalized_title:
                if not title_match["found"]:
                    title_match = {
                        "found": True,
                        "match_type": "title_contains",
                        "match_id": item["id"],
                        "match_title": item["title"],
                    }
            if variant and variant in normalized_text and not text_match["found"]:
                text_match = {
                    "found": True,
                    "match_type": "text_contains",
                    "match_id": item["id"],
                    "match_title": item["title"],
                }

    if title_match["found"]:
        return {
            "found": True,
            "found_in_title": True,
            "found_in_text": True,
            **title_match,
        }
    if text_match["found"]:
        return {
            "found": True,
            "found_in_title": False,
            "found_in_text": True,
            **text_match,
        }
    return {
        "found": False,
        "found_in_title": False,
        "found_in_text": False,
        "match_type": "",
        "match_id": "",
        "match_title": "",
    }


def find_in_result_txt(all_variants: dict[str, list[str]]) -> dict[str, dict[str, object]]:
    normalized_chunks = []
    file_index = []

    for txt_path in sorted(RESULTS_DIR.glob("*.txt")):
        normalized_text = normalize_text(txt_path.read_text(errors="ignore"))
        normalized_chunks.append(normalized_text)
        file_index.append((txt_path.name, normalized_text))

    combined_corpus = "\n".join(normalized_chunks)
    findings = {}

    for disease, variants in all_variants.items():
        match_file = ""
        found = False

        for variant in variants:
            if not variant or variant not in combined_corpus:
                continue

            found = True
            for file_name, normalized_text in file_index:
                if variant in normalized_text:
                    match_file = file_name
                    break
            if found:
                break

        findings[disease] = {
            "found": found,
            "match_file": match_file,
        }

    return findings


def main() -> None:
    diseases = load_unique_diseases()
    mayo_entries = load_mayo_entries()
    mayo_findings = {}

    for disease, metadata in diseases.items():
        mayo_findings[disease] = find_in_mayo_json(mayo_entries, metadata["variants"])

    result_findings = find_in_result_txt(
        {disease: metadata["variants"] for disease, metadata in diseases.items()}
    )

    with OUTPUT_CSV.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "disease",
                "benchmark_sources",
                "benchmark_count",
                "found_in_mayoclinical_json",
                "found_in_mayoclinical_title",
                "found_in_mayoclinical_text",
                "mayoclinical_match_type",
                "mayoclinical_match_id",
                "mayoclinical_match_title",
                "found_in_results_txt",
                "results_match_file",
            ],
        )
        writer.writeheader()

        for disease in sorted(diseases):
            metadata = diseases[disease]
            mayo = mayo_findings[disease]
            result = result_findings[disease]
            writer.writerow(
                {
                    "disease": disease,
                    "benchmark_sources": "|".join(sorted(metadata["sources"])),
                    "benchmark_count": metadata["count"],
                    "found_in_mayoclinical_json": str(mayo["found"]).lower(),
                    "found_in_mayoclinical_title": str(mayo["found_in_title"]).lower(),
                    "found_in_mayoclinical_text": str(mayo["found_in_text"]).lower(),
                    "mayoclinical_match_type": mayo["match_type"],
                    "mayoclinical_match_id": mayo["match_id"],
                    "mayoclinical_match_title": mayo["match_title"],
                    "found_in_results_txt": str(result["found"]).lower(),
                    "results_match_file": result["match_file"],
                }
            )

    total = len(diseases)
    found_in_mayo = sum(1 for item in mayo_findings.values() if item["found"])
    found_in_results = sum(1 for item in result_findings.values() if item["found"])
    print(f"Wrote {OUTPUT_CSV}")
    print(f"Unique diseases: {total}")
    print(f"Found in mayoclinical.json: {found_in_mayo}/{total}")
    print(f"Found in 结果/*.txt: {found_in_results}/{total}")


if __name__ == "__main__":
    main()
