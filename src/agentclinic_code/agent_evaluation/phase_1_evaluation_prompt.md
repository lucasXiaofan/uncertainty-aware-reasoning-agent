Convert the OSCE case into a JSON ground-truth fact list.

Rules:

* Categories: demographics, medical_history, social_history, symptoms, physical_examination_findings, test_results, ground_truth_diagnosis (if provided).
* Each category contains a numbered list of atomic, non-redundant facts.
* Remove phrases like “patient has”, “patient is”, “reports”, etc.
* Keep only explicit facts; do not infer.
* Preserve negations (e.g., “No fever”).
* For tests, create one item per test panel (e.g., one Blood test item, one Urine test item), not one item per lab value.
* If a category has no explicit facts, return [].

Example:

{
  "demographics": [
    "1. 53-year-old",
    "2. Female",
    "3. White"
  ],
  "medical_history": [
    "1. History of tuberculosis",
    "2. History of tobacco use"
  ],
  "symptoms": [
    "1. General malaise",
    "2. No hematuria"
  ],
  "physical_examination_findings": [
    "1. Blood pressure 110/68 mmHg",
    "2. Palpable right flank mass"
  ],
  "test_results": [
    "1. Urine test: blood negative; protein negative",
    "2. Blood test: hemoglobin 13.2; creatinine 0.6"
  ],
  "ground_truth_diagnosis": "the diagnosis"
}