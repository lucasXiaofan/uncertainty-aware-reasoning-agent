import argparse
import csv
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FALSE_CASES = REPO_ROOT / "benchmarks" / "AgentClinic" / "experiment_highest_transfer_clusters" / "results" / "gpt5_nano_on_mimic_with_mimic_prompt" / "agentclinic_mimiciv_openai_gpt-5-nano_selected_20260329_133804.jsonl"
DEFAULT_SOURCE_DATASET = REPO_ROOT / "benchmarks" / "AgentClinic" / "agentclinic_mimiciv.jsonl"
DEFAULT_GUIDELINE_INDEX = REPO_ROOT / "experiments" / "guideline_based_experience" / "cleaned_guidelines" / "cleaned_guideline_index.csv"
DEFAULT_OUTPUT = REPO_ROOT / "experiments" / "train_test_creation" / "agentclinic_mimiciv_false_cases_with_guidelines.jsonl"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build a MIMIC-IV subset from failed AgentClinic cases whose diagnoses have cleaned guideline files."
    )
    parser.add_argument("--false_cases_jsonl", type=Path, default=DEFAULT_FALSE_CASES)
    parser.add_argument("--source_jsonl", type=Path, default=DEFAULT_SOURCE_DATASET)
    parser.add_argument("--guideline_index_csv", type=Path, default=DEFAULT_GUIDELINE_INDEX)
    parser.add_argument("--output_jsonl", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def load_false_case_ids(false_cases_jsonl: Path) -> list[int]:
    scenario_ids = []
    with false_cases_jsonl.open() as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("correct") is False:
                scenario_id = row.get("scenario_id")
                if isinstance(scenario_id, int):
                    scenario_ids.append(scenario_id)
    return sorted(set(scenario_ids))


def load_guideline_diagnoses(guideline_index_csv: Path) -> dict[str, Path]:
    diagnosis_to_guideline = {}
    with guideline_index_csv.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            original_diagnosis = (row.get("original_diagnosis") or "").strip()
            guideline_path_str = (row.get("cleaned_guideline_txt_file") or "").strip()
            if not original_diagnosis or not guideline_path_str:
                continue
            guideline_path = Path(guideline_path_str)
            if guideline_path.exists():
                diagnosis_to_guideline[original_diagnosis] = guideline_path
    return diagnosis_to_guideline


def load_source_rows(source_jsonl: Path) -> list[dict]:
    with source_jsonl.open() as f:
        return [json.loads(line) for line in f if line.strip()]


def main():
    args = parse_args()

    false_case_ids = load_false_case_ids(args.false_cases_jsonl)
    diagnosis_to_guideline = load_guideline_diagnoses(args.guideline_index_csv)
    source_rows = load_source_rows(args.source_jsonl)

    selected_rows = []
    skipped_missing_guideline = []

    for scenario_id in false_case_ids:
        source_row = source_rows[scenario_id]
        diagnosis = source_row["OSCE_Examination"]["Correct_Diagnosis"]
        if diagnosis not in diagnosis_to_guideline:
            skipped_missing_guideline.append((scenario_id, diagnosis))
            continue
        selected_rows.append(source_row)

    args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with args.output_jsonl.open("w") as f:
        for row in selected_rows:
            f.write(json.dumps(row, ensure_ascii=True) + "\n")

    print(f"False cases in source run: {len(false_case_ids)}")
    print(f"Rows written: {len(selected_rows)}")
    print(f"Skipped without cleaned guideline: {len(skipped_missing_guideline)}")
    print(f"Output: {args.output_jsonl}")
    if skipped_missing_guideline:
        print("Missing guideline diagnoses:")
        for scenario_id, diagnosis in skipped_missing_guideline:
            print(f"  - scenario_id={scenario_id}: {diagnosis}")


if __name__ == "__main__":
    main()
