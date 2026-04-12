import argparse
import csv
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path


def normalize_text(text: str) -> str:
    if text is None:
        return ""
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "", text)
    return text


def load_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def build_coverage_index(coverage_rows):
    exact_index = {}
    normalized_index = {}
    for row in coverage_rows:
        disease_name = (row.get("disease_name") or "").strip()
        if not disease_name:
            continue
        exact_index.setdefault(disease_name.casefold(), row)
        normalized_index.setdefault(normalize_text(disease_name), row)
    return exact_index, normalized_index


def find_coverage_row(disease_name, exact_index, normalized_index):
    exact_match = exact_index.get((disease_name or "").strip().casefold())
    if exact_match:
        return exact_match, "exact"

    normalized_match = normalized_index.get(normalize_text(disease_name))
    if normalized_match:
        return normalized_match, "normalized"

    return None, "unmatched"


def main():
    parser = argparse.ArgumentParser(description="Build combined MedQA failed-case JSONL and disease summary CSV.")
    parser.add_argument("--run-results", required=True, help="JSONL results from the 107-case MedQA run.")
    parser.add_argument("--extra-failed", required=True, help="Existing JSONL of 19 additional failed cases.")
    parser.add_argument("--medqa-source", required=True, help="Original AgentClinic MedQA source JSONL.")
    parser.add_argument("--coverage-csv", required=True, help="Disease coverage CSV.")
    parser.add_argument("--output-jsonl", required=True, help="Combined failed-case JSONL output path.")
    parser.add_argument("--output-csv", required=True, help="Disease summary CSV output path.")
    args = parser.parse_args()

    run_results = load_jsonl(Path(args.run_results))
    extra_failed = load_jsonl(Path(args.extra_failed))
    medqa_source = load_jsonl(Path(args.medqa_source))

    run_failed_cases = []
    seen_source_ids = set()
    for row in run_results:
        if row.get("correct") is not False:
            continue
        scenario_id = row["scenario_id"]
        if scenario_id < 0 or scenario_id >= len(medqa_source):
            raise IndexError(f"Scenario id {scenario_id} is out of range for {args.medqa_source}")
        run_failed_cases.append(medqa_source[scenario_id])
        seen_source_ids.add(scenario_id)

    combined_failed_cases = run_failed_cases + extra_failed

    output_jsonl = Path(args.output_jsonl)
    output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with output_jsonl.open("w", encoding="utf-8") as f:
        for record in combined_failed_cases:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    with Path(args.coverage_csv).open("r", encoding="utf-8", newline="") as f:
        coverage_rows = list(csv.DictReader(f))
    exact_index, normalized_index = build_coverage_index(coverage_rows)

    disease_counts = Counter(
        case["OSCE_Examination"]["Correct_Diagnosis"]
        for case in combined_failed_cases
    )

    output_rows = []
    for disease_name, count in sorted(disease_counts.items(), key=lambda item: (-item[1], item[0].casefold())):
        coverage_row, match_type = find_coverage_row(disease_name, exact_index, normalized_index)
        if coverage_row is None:
            output_rows.append({
                "disease_name": disease_name,
                "failed_case_count": count,
                "guideline_found_in_disease_coverage": "no",
                "match_type": match_type,
                "matched_coverage_disease_name": "",
                "has_mayoclinic": "",
                "has_uptodate": "",
                "coverage_source": "",
            })
            continue

        has_mayoclinic = (coverage_row.get("has_mayoclinic") or "").strip().lower()
        has_uptodate = (coverage_row.get("has_uptodate") or "").strip().lower()
        guideline_found = "yes" if "yes" in {has_mayoclinic, has_uptodate} else "no"
        output_rows.append({
            "disease_name": disease_name,
            "failed_case_count": count,
            "guideline_found_in_disease_coverage": guideline_found,
            "match_type": match_type,
            "matched_coverage_disease_name": coverage_row.get("disease_name", ""),
            "has_mayoclinic": coverage_row.get("has_mayoclinic", ""),
            "has_uptodate": coverage_row.get("has_uptodate", ""),
            "coverage_source": coverage_row.get("source", ""),
        })

    output_csv = Path(args.output_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "disease_name",
                "failed_case_count",
                "guideline_found_in_disease_coverage",
                "match_type",
                "matched_coverage_disease_name",
                "has_mayoclinic",
                "has_uptodate",
                "coverage_source",
            ],
        )
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"Run false cases from MedQA results: {len(run_failed_cases)}")
    print(f"Additional failed cases loaded: {len(extra_failed)}")
    print(f"Combined failed cases written: {len(combined_failed_cases)}")
    print(f"Unique diseases summarized: {len(output_rows)}")
    print(f"Output JSONL: {output_jsonl}")
    print(f"Output CSV: {output_csv}")


if __name__ == "__main__":
    main()
