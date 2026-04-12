import csv
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


def collect_single_diagnosis_subjects(icd_lookup):
    subject_order = []
    diagnosis_count = {}
    subject_diagnosis = {}

    with (MIMIC_HOSP_DIR / "diagnoses_icd.csv").open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            subject_id = row["subject_id"]
            if subject_id not in diagnosis_count:
                diagnosis_count[subject_id] = 0
                subject_order.append(subject_id)

            diagnosis_name = icd_lookup.get((row["icd_code"], row["icd_version"]), "")
            if "history" in diagnosis_name.lower():
                continue

            diagnosis_count[subject_id] += 1
            subject_diagnosis[subject_id] = {
                "subject_id": subject_id,
                "hadm_id": row["hadm_id"],
                "icd_code": row["icd_code"],
                "icd_version": row["icd_version"],
                "diagnosis_long_title": diagnosis_name,
            }

    return [
        subject_diagnosis[subject_id]
        for subject_id in subject_order
        if diagnosis_count.get(subject_id, 0) == 1 and subject_id in subject_diagnosis
    ]


def write_csv(path, rows):
    fieldnames = [
        "subject_id",
        "hadm_id",
        "icd_code",
        "icd_version",
        "diagnosis_long_title",
    ]
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    icd_lookup = load_icd_lookup()
    single_diagnosis_subjects = collect_single_diagnosis_subjects(icd_lookup)

    existing_rows = single_diagnosis_subjects[:EXISTING_COUNT]
    non_overlap_rows = single_diagnosis_subjects[EXISTING_COUNT:]

    if len(non_overlap_rows) < MIN_NON_OVERLAP_COUNT:
        raise RuntimeError(
            f"Only found {len(non_overlap_rows)} non-overlapping single-diagnosis patients; "
            f"expected at least {MIN_NON_OVERLAP_COUNT}."
        )

    existing_path = OUTPUT_DIR / "agentclinic_mimiciv_existing_200_patients.csv"
    non_overlap_path = OUTPUT_DIR / "mimiciv_single_diagnosis_nonoverlap_patients.csv"

    write_csv(existing_path, existing_rows)
    write_csv(non_overlap_path, non_overlap_rows)

    print(f"Single-diagnosis subjects: {len(single_diagnosis_subjects)}")
    print(f"Existing inferred AgentClinic patients: {len(existing_rows)} -> {existing_path}")
    print(f"Non-overlapping single-diagnosis patients: {len(non_overlap_rows)} -> {non_overlap_path}")


if __name__ == "__main__":
    main()
