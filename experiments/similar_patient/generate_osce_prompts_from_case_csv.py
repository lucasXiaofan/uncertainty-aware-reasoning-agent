import argparse
import csv
import json
from pathlib import Path


EXAMPLE_OSCE = """
Here is an example of the structure:
{
  "OSCE_Examination": {
    "Objective_for_Doctor": "Assess and diagnose the patient presenting with acute abdominal pain.",
    "Patient_Actor": {
      "Demographics": "30-year-old female",
      "History": "The patient complains of sudden onset of sharp, right lower quadrant abdominal pain since last night. The pain has progressively worsened over the last 12 hours. She mentions that she felt nauseous this morning but has not vomited. No recent changes in bowel habits or urinary symptoms have been reported.",
      "Symptoms": {
        "Primary_Symptom": "Sharp, right lower quadrant abdominal pain",
        "Secondary_Symptoms": ["Nausea", "No vomiting", "No change in bowel habits", "No urinary symptoms"]
      },
      "Past_Medical_History": "No significant past medical history. No previous surgeries.",
      "Social_History": "Non-smoker, occasional alcohol use. Works as a software developer.",
      "Review_of_Systems": "Denies fever, vomiting, diarrhea, dysuria, or flank pain."
    },
    "Physical_Examination_Findings": {
      "Vital_Signs": {
        "Temperature": "37.2°C (99°F)",
        "Blood_Pressure": "120/75 mmHg",
        "Heart_Rate": "78 bpm",
        "Respiratory_Rate": "16 breaths/min"
      },
      "Abdominal_Examination": {
        "Inspection": "No distension or visible masses.",
        "Auscultation": "Normal bowel sounds.",
        "Percussion": "Tympanic throughout, no shifting dullness.",
        "Palpation": "Tenderness in the right lower quadrant. No guarding or rebound tenderness. Rovsing's sign positive, suggesting peritoneal irritation."
      }
    },
    "Test_Results": {
      "Complete_Blood_Count": {
        "WBC": "12,000 /μL (elevated)",
        "Hemoglobin": "13.5 g/dL",
        "Platelets": "250,000 /μL"
      },
      "Urinalysis": {
        "Appearance": "Clear",
        "WBC": "2-5 /HPF",
        "RBC": "0-2 /HPF",
        "Nitrites": "Negative",
        "Leukocyte_Esterase": "Negative"
      },
      "Imaging": {
        "Ultrasound_Abdomen": {
          "Findings": "Enlarged appendix with wall thickening and fluid collection. No evidence of ovarian cyst or ectopic pregnancy."
        }
      }
    },
    "Correct_Diagnosis": "Acute Appendicitis"
  }
}
""".strip()

SYSTEM_INSTRUCTION = (
    'Please generate a sample Objective Structured Clinical Examination (OSCE) for the '
    'patient actor and the doctor, including what the correct diagnosis should be as a '
    'structured json. Only provide the doctor with the objective and provide "test results" '
    "as a separate category. Provide these for a primary care doctor exam."
)


def normalize(text):
    return " ".join(text.strip().lower().split())


def load_targets(target_file, target_values):
    targets = []
    if target_file:
        with open(target_file) as f:
            for line in f:
                value = line.strip()
                if value:
                    targets.append(value)
    targets.extend(target_values)
    if not targets:
        raise ValueError("Provide at least one target diagnosis or ICD code.")
    return targets


def build_prompt(case_study_json):
    return (
        f"System instruction:\n{SYSTEM_INSTRUCTION}\n\n"
        f'User prompt:\nGenerate a OSCE for the following case study {case_study_json}. '
        'Please read the "answer" category for the correct diagnosis.\n\n'
        f"Here is an example of correct the OSCE format\n{EXAMPLE_OSCE}\n\n"
        "Please create a new one here:\n"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--case-csv",
        default=str(Path(__file__).resolve().parent / "mimiciv_single_diagnosis_nonoverlap_case_data.csv"),
    )
    parser.add_argument(
        "--target-file",
        help="Plain text file with one target diagnosis or ICD code per line.",
    )
    parser.add_argument(
        "--target",
        action="append",
        default=[],
        help="Target diagnosis long title, diagnosis text, or ICD code. Repeatable.",
    )
    parser.add_argument(
        "--limit-per-target",
        type=int,
        default=1,
        help="Maximum number of prompts to emit for each target.",
    )
    parser.add_argument(
        "--output",
        default=str(Path(__file__).resolve().parent / "target_diagnosis_osce_prompts.txt"),
    )
    args = parser.parse_args()

    targets = load_targets(args.target_file, args.target)
    remaining = {normalize(target): args.limit_per_target for target in targets}
    matched_rows = []

    with open(args.case_csv, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            candidates = {
                normalize(row["diagnosis_long_title"]),
                normalize(row["diagnosis"]),
                normalize(row["icd_code"]),
                normalize(f'{row["icd_code"]} (icd-{row["icd_version"]})'),
            }
            for target_key in remaining:
                if remaining[target_key] <= 0:
                    continue
                if target_key in candidates:
                    matched_rows.append((target_key, row))
                    remaining[target_key] -= 1
                    break

    output_path = Path(args.output)
    with output_path.open("w") as f:
        for target_key, row in matched_rows:
            prompt = build_prompt(row["case_study_json"])
            record = {
                "target": target_key,
                "subject_id": row["subject_id"],
                "hadm_id": row["hadm_id"],
                "icd_code": row["icd_code"],
                "icd_version": row["icd_version"],
                "diagnosis_long_title": row["diagnosis_long_title"],
                "prompt": prompt,
            }
            f.write(json.dumps(record, ensure_ascii=True) + "\n")

    missing = [target for target in targets if remaining[normalize(target)] > 0]
    print(f"Wrote {len(matched_rows)} prompt records to {output_path}")
    if missing:
        print("Missing targets:")
        for target in missing:
            print(target)


if __name__ == "__main__":
    main()
