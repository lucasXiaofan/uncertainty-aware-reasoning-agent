import csv
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MIMIC_HOSP_DIR = REPO_ROOT / "mimic_hosp"
OUTPUT_DIR = Path(__file__).resolve().parent

EXISTING_COUNT = 200
MIN_NON_OVERLAP_COUNT = 4000


def load_icd_lookup():
    lookup = {}
    with (MIMIC_HOSP_DIR / "d_icd_diagnoses.csv").open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            lookup[(row["icd_code"], row["icd_version"])] = row["long_title"]
    return lookup


def load_labitem_lookup():
    lookup = {}
    with (MIMIC_HOSP_DIR / "d_labitems.csv").open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            lookup[row["itemid"]] = f'{row["label"]} {row["fluid"]}'.strip()
    return lookup


def collect_single_diagnosis_subjects(icd_lookup):
    subject_order = []
    diagnosis_count = {}
    subject_case = {}

    with (MIMIC_HOSP_DIR / "diagnoses_icd.csv").open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            subject_id = row["subject_id"]
            if subject_id not in diagnosis_count:
                diagnosis_count[subject_id] = 0
                subject_order.append(subject_id)
                subject_case[subject_id] = {
                    "subject_id": subject_id,
                    "hadm_id": row["hadm_id"],
                    "icd_code": row["icd_code"],
                    "icd_version": row["icd_version"],
                    "diagnosis_long_title": "",
                    "diagnosis": "",
                    "demographics": {},
                    "history": [],
                    "tests": {},
                }

            diagnosis_name = icd_lookup.get((row["icd_code"], row["icd_version"]), "")
            if "history" in diagnosis_name.lower():
                if diagnosis_name and diagnosis_name not in subject_case[subject_id]["history"]:
                    subject_case[subject_id]["history"].append(diagnosis_name)
                continue

            diagnosis_count[subject_id] += 1
            subject_case[subject_id]["hadm_id"] = row["hadm_id"]
            subject_case[subject_id]["icd_code"] = row["icd_code"]
            subject_case[subject_id]["icd_version"] = row["icd_version"]
            subject_case[subject_id]["diagnosis_long_title"] = diagnosis_name
            subject_case[subject_id]["diagnosis"] = diagnosis_name

    return [
        subject_case[subject_id]
        for subject_id in subject_order
        if diagnosis_count.get(subject_id, 0) == 1 and subject_id in subject_case
    ]


def index_cases(case_rows):
    cases_by_subject = {row["subject_id"]: row for row in case_rows}
    subject_ids = set(cases_by_subject)
    return cases_by_subject, subject_ids


def populate_demographics(cases_by_subject, subject_ids):
    with (MIMIC_HOSP_DIR / "patients.csv").open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            subject_id = row["subject_id"]
            if subject_id not in subject_ids:
                continue
            cases_by_subject[subject_id]["demographics"] = {
                "gender": row["gender"],
                "anchor_age": row["anchor_age"],
            }

    with (MIMIC_HOSP_DIR / "admissions.csv").open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            subject_id = row["subject_id"]
            if subject_id not in subject_ids:
                continue
            if "race" not in cases_by_subject[subject_id]["demographics"]:
                cases_by_subject[subject_id]["demographics"]["race"] = row["race"]


def populate_omr_tests(cases_by_subject, subject_ids):
    with (MIMIC_HOSP_DIR / "omr.csv").open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            subject_id = row["subject_id"]
            if subject_id not in subject_ids:
                continue
            tests = cases_by_subject[subject_id]["tests"]
            if row["result_name"] not in tests:
                tests[row["result_name"]] = row["result_value"]


def populate_microbiology_tests(cases_by_subject, subject_ids):
    with (MIMIC_HOSP_DIR / "microbiologyevents.csv").open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            subject_id = row["subject_id"]
            if subject_id not in subject_ids:
                continue
            test_name = row["test_name"].strip().lower()
            comments = row["comments"].strip().lower()
            if not test_name or not comments:
                continue
            tests = cases_by_subject[subject_id]["tests"]
            if test_name not in tests:
                tests[test_name] = comments


def populate_labevents(cases_by_subject, subject_ids, labitem_lookup):
    with (MIMIC_HOSP_DIR / "labevents.csv").open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            subject_id = row["subject_id"]
            if subject_id not in subject_ids:
                continue
            value = row["value"].strip()
            if not value or "_" in value:
                continue
            test_name = labitem_lookup.get(row["itemid"], "").strip()
            if not test_name:
                continue
            tests = cases_by_subject[subject_id]["tests"]
            if test_name not in tests:
                tests[test_name] = value


def serialize_case_row(case_row):
    return {
        "subject_id": case_row["subject_id"],
        "hadm_id": case_row["hadm_id"],
        "icd_code": case_row["icd_code"],
        "icd_version": case_row["icd_version"],
        "diagnosis_long_title": case_row["diagnosis_long_title"],
        "diagnosis": case_row["diagnosis"],
        "demographics_json": json.dumps(case_row["demographics"], ensure_ascii=True, sort_keys=True),
        "history_json": json.dumps(case_row["history"], ensure_ascii=True),
        "tests_json": json.dumps(case_row["tests"], ensure_ascii=True, sort_keys=True),
        "case_study_json": json.dumps(
            {
                "tests": case_row["tests"],
                "history": case_row["history"],
                "diagnosis": case_row["diagnosis"],
                "demographics": case_row["demographics"],
            },
            ensure_ascii=True,
            sort_keys=True,
        ),
    }


def write_case_csv(path, case_rows):
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
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in case_rows:
            writer.writerow(serialize_case_row(row))


def main():
    icd_lookup = load_icd_lookup()
    labitem_lookup = load_labitem_lookup()

    single_diagnosis_subjects = collect_single_diagnosis_subjects(icd_lookup)
    non_overlap_rows = single_diagnosis_subjects[EXISTING_COUNT:]
    if len(non_overlap_rows) < MIN_NON_OVERLAP_COUNT:
        raise RuntimeError(
            f"Only found {len(non_overlap_rows)} non-overlapping single-diagnosis patients; "
            f"expected at least {MIN_NON_OVERLAP_COUNT}."
        )

    cases_by_subject, subject_ids = index_cases(non_overlap_rows)
    populate_demographics(cases_by_subject, subject_ids)
    populate_omr_tests(cases_by_subject, subject_ids)
    populate_microbiology_tests(cases_by_subject, subject_ids)
    populate_labevents(cases_by_subject, subject_ids, labitem_lookup)

    output_path = OUTPUT_DIR / "mimiciv_single_diagnosis_nonoverlap_case_data.csv"
    ordered_rows = [cases_by_subject[row["subject_id"]] for row in non_overlap_rows]
    write_case_csv(output_path, ordered_rows)

    print(f"Non-overlapping single-diagnosis case rows: {len(ordered_rows)}")
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
