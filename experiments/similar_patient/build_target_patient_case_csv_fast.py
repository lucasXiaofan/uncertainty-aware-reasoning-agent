import argparse
import csv
import json
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
MIMIC_HOSP_DIR = REPO_ROOT / "mimic_hosp"
SIMILAR_PATIENT_DIR = Path(__file__).resolve().parent


def normalize(text):
    return " ".join(text.strip().lower().split())


def clean_text(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def load_targets(target_file):
    with open(target_file) as f:
        targets = [line.strip() for line in f if line.strip()]
    if not targets:
        raise ValueError("Target diagnosis file is empty.")
    return targets


def load_nonoverlap_rows():
    path = SIMILAR_PATIENT_DIR / "mimiciv_single_diagnosis_nonoverlap_patients.csv"
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def choose_target_rows(nonoverlap_rows, targets):
    remaining = {normalize(target): target for target in targets}
    selected = []
    for row in nonoverlap_rows:
        key = normalize(row["diagnosis_long_title"])
        if key in remaining:
            selected.append(
                {
                    "subject_id": row["subject_id"],
                    "hadm_id": row["hadm_id"],
                    "icd_code": row["icd_code"],
                    "icd_version": row["icd_version"],
                    "diagnosis_long_title": row["diagnosis_long_title"],
                    "diagnosis": row["diagnosis_long_title"],
                    "demographics": {},
                    "history": [],
                    "tests": {},
                }
            )
            del remaining[key]
        if not remaining:
            break
    if remaining:
        raise RuntimeError(f"Missing target diagnoses: {sorted(remaining.values())}")
    return selected


def load_history_by_subject(target_subject_ids):
    history = {subject_id: [] for subject_id in target_subject_ids}
    icd_lookup = {}
    with (MIMIC_HOSP_DIR / "d_icd_diagnoses.csv").open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            icd_lookup[(row["icd_code"], row["icd_version"])] = row["long_title"]

    for chunk in pd.read_csv(
        MIMIC_HOSP_DIR / "diagnoses_icd.csv",
        dtype=str,
        usecols=["subject_id", "icd_code", "icd_version"],
        chunksize=200_000,
    ):
        chunk = chunk[chunk["subject_id"].isin(target_subject_ids)]
        if chunk.empty:
            continue
        for row in chunk.itertuples(index=False):
            diagnosis_name = icd_lookup.get((row.icd_code, row.icd_version), "")
            if "history" in diagnosis_name.lower() and diagnosis_name not in history[row.subject_id]:
                history[row.subject_id].append(diagnosis_name)
    return history


def populate_demographics(rows_by_subject):
    target_subject_ids = set(rows_by_subject)

    patients = pd.read_csv(
        MIMIC_HOSP_DIR / "patients.csv",
        dtype=str,
        usecols=["subject_id", "gender", "anchor_age"],
    )
    patients = patients[patients["subject_id"].isin(target_subject_ids)]
    for row in patients.itertuples(index=False):
        rows_by_subject[row.subject_id]["demographics"]["gender"] = row.gender
        rows_by_subject[row.subject_id]["demographics"]["anchor_age"] = row.anchor_age

    admissions = pd.read_csv(
        MIMIC_HOSP_DIR / "admissions.csv",
        dtype=str,
        usecols=["subject_id", "race"],
    )
    admissions = admissions[admissions["subject_id"].isin(target_subject_ids)]
    for row in admissions.drop_duplicates(subset=["subject_id"]).itertuples(index=False):
        rows_by_subject[row.subject_id]["demographics"]["race"] = row.race


def populate_omr_tests(rows_by_subject):
    target_subject_ids = set(rows_by_subject)
    for chunk in pd.read_csv(
        MIMIC_HOSP_DIR / "omr.csv",
        dtype=str,
        usecols=["subject_id", "result_name", "result_value"],
        chunksize=200_000,
    ):
        chunk = chunk[chunk["subject_id"].isin(target_subject_ids)]
        if chunk.empty:
            continue
        for row in chunk.itertuples(index=False):
            tests = rows_by_subject[row.subject_id]["tests"]
            if row.result_name not in tests:
                tests[row.result_name] = row.result_value


def populate_microbiology_tests(rows_by_subject):
    target_subject_ids = set(rows_by_subject)
    for chunk in pd.read_csv(
        MIMIC_HOSP_DIR / "microbiologyevents.csv",
        dtype=str,
        usecols=["subject_id", "test_name", "comments"],
        chunksize=200_000,
    ):
        chunk = chunk[chunk["subject_id"].isin(target_subject_ids)]
        if chunk.empty:
            continue
        for row in chunk.itertuples(index=False):
            test_name = clean_text(row.test_name).lower()
            comments = clean_text(row.comments).lower()
            if not test_name or not comments:
                continue
            tests = rows_by_subject[row.subject_id]["tests"]
            if test_name not in tests:
                tests[test_name] = comments


def load_labitem_lookup():
    lookup = {}
    with (MIMIC_HOSP_DIR / "d_labitems.csv").open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            lookup[row["itemid"]] = f'{row["label"]} {row["fluid"]}'.strip()
    return lookup


def populate_labevents(rows_by_subject):
    target_subject_ids = set(rows_by_subject)
    labitem_lookup = load_labitem_lookup()
    for chunk in pd.read_csv(
        MIMIC_HOSP_DIR / "labevents.csv",
        dtype=str,
        usecols=["subject_id", "itemid", "value"],
        chunksize=500_000,
    ):
        chunk = chunk[chunk["subject_id"].isin(target_subject_ids)]
        if chunk.empty:
            continue
        for row in chunk.itertuples(index=False):
            value = clean_text(row.value)
            if not value or "_" in value:
                continue
            test_name = labitem_lookup.get(row.itemid, "").strip()
            if not test_name:
                continue
            tests = rows_by_subject[row.subject_id]["tests"]
            if test_name not in tests:
                tests[test_name] = value


def write_case_csv(output_path, selected_rows):
    fieldnames = [
        "subject_id",
        "hadm_id",
        "icd_code",
        "icd_version",
        "diagnosis_long_title",
        "diagnosis",
        "demographics_json",
        "history_json",
        "tests_json",
        "case_study_json",
    ]
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in selected_rows:
            writer.writerow(
                {
                    "subject_id": row["subject_id"],
                    "hadm_id": row["hadm_id"],
                    "icd_code": row["icd_code"],
                    "icd_version": row["icd_version"],
                    "diagnosis_long_title": row["diagnosis_long_title"],
                    "diagnosis": row["diagnosis"],
                    "demographics_json": json.dumps(row["demographics"], ensure_ascii=True, sort_keys=True),
                    "history_json": json.dumps(row["history"], ensure_ascii=True),
                    "tests_json": json.dumps(row["tests"], ensure_ascii=True, sort_keys=True),
                    "case_study_json": json.dumps(
                        {
                            "tests": row["tests"],
                            "history": row["history"],
                            "diagnosis": row["diagnosis"],
                            "demographics": row["demographics"],
                        },
                        ensure_ascii=True,
                        sort_keys=True,
                    ),
                }
            )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-file", required=True)
    parser.add_argument(
        "--output",
        default=str(SIMILAR_PATIENT_DIR / "target_diagnosis_case_data.csv"),
    )
    args = parser.parse_args()

    targets = load_targets(args.target_file)
    selected_rows = choose_target_rows(load_nonoverlap_rows(), targets)
    rows_by_subject = {row["subject_id"]: row for row in selected_rows}

    history = load_history_by_subject(set(rows_by_subject))
    for subject_id, entries in history.items():
        rows_by_subject[subject_id]["history"] = entries

    populate_demographics(rows_by_subject)
    populate_omr_tests(rows_by_subject)
    populate_microbiology_tests(rows_by_subject)
    populate_labevents(rows_by_subject)

    ordered_rows = [rows_by_subject[row["subject_id"]] for row in selected_rows]
    write_case_csv(args.output, ordered_rows)
    print(f"Wrote {len(ordered_rows)} case rows to {args.output}")


if __name__ == "__main__":
    main()
