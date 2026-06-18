# MIMIC-IV Small Train/Test Split

Source dataset: `src/agentclinic_code/data/agentclinic_mimiciv.jsonl`

Prioritized false-case source: `benchmarks/AgentClinic/experiment_highest_transfer_clusters/results/gpt5_nano_on_mimic_with_mimic_prompt/agentclinic_mimiciv_openai_gpt-5-nano_selected_20260329_133804.jsonl`

Row numbers below are 1-based line numbers in the 200-row source dataset. Zero-based indices are included for compatibility with AgentClinic scenario IDs. File row is the 1-based row in the generated split file.

## Summary

- Source rows: 200
- Unique final diagnoses in source: 115
- Final diagnoses with more than one source example: 26
- Training rows: 28 (`mimic_training.jsonl`), including 19 prioritized false cases
- Testing rows: 26 (`mimic_testing.jsonl`), including 18 prioritized false cases
- Unique diagnoses in training: 14
- Unique diagnoses in testing: 26
- Testing-only diagnoses: 12
- Training diagnoses missing from testing: 0
- Train/test source row overlap: 0
- Ordering: false cases first in each generated JSONL, then correct cases

## Run Command

The selected runner auto-detects `MIMICIV` from the `mimic_training.jsonl` filename and passes the custom data file directly to the Python loader:

```bash
bash src/agentclinic_code/run_experiment_selected.sh \
  --data_file src/agentclinic_code/data/mimic_training.jsonl \
  --count 2 \
  --workers 2 \
  --custom_doctor_agent_path src/agentclinic_code/two_phased_agent/two_agent_interface.py
```

## Training Rows

| File row | Source row / 200 | Source index | Prior result | Final diagnosis |
|---:|---:|---:|---|---|
| 1 | 4 | 3 | false | Displacement of lumbar intervertebral disc without myelopathy |
| 2 | 7 | 6 | false | Other chest pain |
| 3 | 11 | 10 | false | Displacement of lumbar intervertebral disc without myelopathy |
| 4 | 19 | 18 | false | Chest pain, unspecified |
| 5 | 23 | 22 | false | Chest pain, unspecified |
| 6 | 41 | 40 | false | Alcohol abuse, unspecified |
| 7 | 50 | 49 | false | Depressive disorder, not elsewhere classified |
| 8 | 55 | 54 | false | Acute appendicitis without mention of peritonitis |
| 9 | 60 | 59 | false | Alcohol abuse with intoxication, unspecified |
| 10 | 89 | 88 | false | Acute appendicitis without mention of peritonitis |
| 11 | 92 | 91 | false | Alcohol abuse with intoxication, unspecified |
| 12 | 94 | 93 | false | Alcohol abuse, unspecified |
| 13 | 101 | 100 | false | Other chest pain |
| 14 | 109 | 108 | false | Acute Pharyngitis |
| 15 | 132 | 131 | false | Diverticulitis of colon (without mention of hemorrhage) |
| 16 | 134 | 133 | false | Major depressive disorder, single episode, unspecified |
| 17 | 135 | 134 | false | Cellulitis and abscess of leg, except foot |
| 18 | 176 | 175 | false | Cellulitis and abscess of leg, except foot |
| 19 | 198 | 197 | false | Major depressive disorder, single episode, unspecified |
| 20 | 5 | 4 | true | Peritonsillar abscess |
| 21 | 35 | 34 | true | Depressive disorder, not elsewhere classified |
| 22 | 37 | 36 | true | Peritonsillar abscess |
| 23 | 39 | 38 | true | Acute pharyngitis |
| 24 | 64 | 63 | true | Rhabdomyolysis |
| 25 | 67 | 66 | true | Acute pharyngitis |
| 26 | 78 | 77 | true | Diverticulitis of colon (without mention of hemorrhage) |
| 27 | 82 | 81 | true | Rhabdomyolysis |
| 28 | 87 | 86 | true | Acute Pharyngitis |

## Testing Rows

| File row | Source row / 200 | Source index | Prior result | Final diagnosis | Coverage role |
|---:|---:|---:|---|---|---|
| 1 | 2 | 1 | false | Malignant neoplasm of kidney, except pelvis | test-only diagnosis |
| 2 | 8 | 7 | false | Calculus of bile duct without mention of cholecystitis, without mention of obstruction | test-only diagnosis |
| 3 | 12 | 11 | false | Anaphylactic reaction due to unspecified food | test-only diagnosis |
| 4 | 13 | 12 | false | Unspecified intestinal obstruction | test-only diagnosis |
| 5 | 17 | 16 | false | Occipital neuralgia | test-only diagnosis |
| 6 | 20 | 19 | false | Displacement of lumbar intervertebral disc without myelopathy | covers training diagnosis |
| 7 | 21 | 20 | false | Displacement of cervical intervertebral disc without myelopathy | test-only diagnosis |
| 8 | 26 | 25 | false | Pain in limb | test-only diagnosis |
| 9 | 28 | 27 | false | The findings do not strongly indicate a specific acute pathology and may be consistent with a non-specific viral illness or early presentation of a more specific illness. The normal range of most test results suggests that there is no immediate acute disease. Given the generalized symptoms and lack of specific findings, a conservative approach with symptomatic treatment and watchful waiting is recommended with instructions to return or seek further care if symptoms worsen or if more specific symptoms develop. | test-only diagnosis |
| 10 | 30 | 29 | false | Chest pain, unspecified | covers training diagnosis |
| 11 | 40 | 39 | false | Benign neoplasm of ovary | test-only diagnosis |
| 12 | 45 | 44 | false | Opioid abuse, continuous | test-only diagnosis |
| 13 | 46 | 45 | false | Cellulitis and abscess of foot, except toes | test-only diagnosis |
| 14 | 47 | 46 | false | Malignant neoplasm of thyroid gland | test-only diagnosis |
| 15 | 103 | 102 | false | Alcohol abuse, unspecified | covers training diagnosis |
| 16 | 118 | 117 | false | Alcohol abuse with intoxication, unspecified | covers training diagnosis |
| 17 | 121 | 120 | false | Other chest pain | covers training diagnosis |
| 18 | 175 | 174 | false | Acute appendicitis without mention of peritonitis | covers training diagnosis |
| 19 | 49 | 48 | true | Cellulitis and abscess of leg, except foot | covers training diagnosis |
| 20 | 61 | 60 | true | Peritonsillar abscess | covers training diagnosis |
| 21 | 76 | 75 | true | Major depressive disorder, single episode, unspecified | covers training diagnosis |
| 22 | 79 | 78 | true | Diverticulitis of colon (without mention of hemorrhage) | covers training diagnosis |
| 23 | 105 | 104 | true | Acute pharyngitis | covers training diagnosis |
| 24 | 111 | 110 | true | Depressive disorder, not elsewhere classified | covers training diagnosis |
| 25 | 128 | 127 | true | Acute Pharyngitis | covers training diagnosis |
| 26 | 129 | 128 | true | Rhabdomyolysis | covers training diagnosis |

## Diagnosis Coverage

| Final diagnosis | Source count | Training source rows | Testing source rows | False-case source rows in selected split | Coverage role |
|---|---:|---|---|---|---|
| Acute appendicitis without mention of peritonitis | 8 | 55, 89 | 175 | 55, 89, 175 | train and test |
| Acute Pharyngitis | 3 | 109, 87 | 128 | 109 | train and test |
| Acute pharyngitis | 3 | 39, 67 | 105 | none | train and test |
| Alcohol abuse with intoxication, unspecified | 6 | 60, 92 | 118 | 60, 92, 118 | train and test |
| Alcohol abuse, unspecified | 10 | 41, 94 | 103 | 41, 94, 103 | train and test |
| Anaphylactic reaction due to unspecified food | 1 | none | 12 | 12 | test-only |
| Benign neoplasm of ovary | 1 | none | 40 | 40 | test-only |
| Calculus of bile duct without mention of cholecystitis, without mention of obstruction | 1 | none | 8 | 8 | test-only |
| Cellulitis and abscess of foot, except toes | 1 | none | 46 | 46 | test-only |
| Cellulitis and abscess of leg, except foot | 4 | 135, 176 | 49 | 135, 176 | train and test |
| Chest pain, unspecified | 25 | 19, 23 | 30 | 19, 23, 30 | train and test |
| Depressive disorder, not elsewhere classified | 5 | 50, 35 | 111 | 50 | train and test |
| Displacement of cervical intervertebral disc without myelopathy | 1 | none | 21 | 21 | test-only |
| Displacement of lumbar intervertebral disc without myelopathy | 4 | 4, 11 | 20 | 4, 11, 20 | train and test |
| Diverticulitis of colon (without mention of hemorrhage) | 3 | 132, 78 | 79 | 132 | train and test |
| Major depressive disorder, single episode, unspecified | 6 | 134, 198 | 76 | 134, 198 | train and test |
| Malignant neoplasm of kidney, except pelvis | 1 | none | 2 | 2 | test-only |
| Malignant neoplasm of thyroid gland | 2 | none | 47 | 47 | test-only |
| Occipital neuralgia | 1 | none | 17 | 17 | test-only |
| Opioid abuse, continuous | 1 | none | 45 | 45 | test-only |
| Other chest pain | 4 | 7, 101 | 121 | 7, 101, 121 | train and test |
| Pain in limb | 1 | none | 26 | 26 | test-only |
| Peritonsillar abscess | 3 | 5, 37 | 61 | none | train and test |
| Rhabdomyolysis | 3 | 64, 82 | 129 | none | train and test |
| The findings do not strongly indicate a specific acute pathology and may be consistent with a non-specific viral illness or early presentation of a more specific illness. The normal range of most test results suggests that there is no immediate acute disease. Given the generalized symptoms and lack of specific findings, a conservative approach with symptomatic treatment and watchful waiting is recommended with instructions to return or seek further care if symptoms worsen or if more specific symptoms develop. | 1 | none | 28 | 28 | test-only |
| Unspecified intestinal obstruction | 1 | none | 13 | 13 | test-only |

## Training Pairing Rule

| Final diagnosis | Training source rows | Testing source row | Selection note |
|---|---|---:|---|
| Acute appendicitis without mention of peritonitis | 55, 89 | 175 | all selected rows were prior false cases |
| Acute Pharyngitis | 109, 87 | 128 | false cases prioritized; correct cases used only when fewer false cases were available |
| Acute pharyngitis | 39, 67 | 105 | false cases prioritized; correct cases used only when fewer false cases were available |
| Alcohol abuse with intoxication, unspecified | 60, 92 | 118 | all selected rows were prior false cases |
| Alcohol abuse, unspecified | 41, 94 | 103 | all selected rows were prior false cases |
| Cellulitis and abscess of leg, except foot | 135, 176 | 49 | false cases prioritized; correct cases used only when fewer false cases were available |
| Chest pain, unspecified | 19, 23 | 30 | all selected rows were prior false cases |
| Depressive disorder, not elsewhere classified | 50, 35 | 111 | false cases prioritized; correct cases used only when fewer false cases were available |
| Displacement of lumbar intervertebral disc without myelopathy | 4, 11 | 20 | all selected rows were prior false cases |
| Diverticulitis of colon (without mention of hemorrhage) | 132, 78 | 79 | false cases prioritized; correct cases used only when fewer false cases were available |
| Major depressive disorder, single episode, unspecified | 134, 198 | 76 | false cases prioritized; correct cases used only when fewer false cases were available |
| Other chest pain | 7, 101 | 121 | all selected rows were prior false cases |
| Peritonsillar abscess | 5, 37 | 61 | false cases prioritized; correct cases used only when fewer false cases were available |
| Rhabdomyolysis | 64, 82 | 129 | false cases prioritized; correct cases used only when fewer false cases were available |

## Test-Only Diagnoses

| Source row / 200 | Source index | Prior result | Final diagnosis |
|---:|---:|---|---|
| 2 | 1 | false | Malignant neoplasm of kidney, except pelvis |
| 8 | 7 | false | Calculus of bile duct without mention of cholecystitis, without mention of obstruction |
| 12 | 11 | false | Anaphylactic reaction due to unspecified food |
| 13 | 12 | false | Unspecified intestinal obstruction |
| 17 | 16 | false | Occipital neuralgia |
| 21 | 20 | false | Displacement of cervical intervertebral disc without myelopathy |
| 26 | 25 | false | Pain in limb |
| 28 | 27 | false | The findings do not strongly indicate a specific acute pathology and may be consistent with a non-specific viral illness or early presentation of a more specific illness. The normal range of most test results suggests that there is no immediate acute disease. Given the generalized symptoms and lack of specific findings, a conservative approach with symptomatic treatment and watchful waiting is recommended with instructions to return or seek further care if symptoms worsen or if more specific symptoms develop. |
| 40 | 39 | false | Benign neoplasm of ovary |
| 45 | 44 | false | Opioid abuse, continuous |
| 46 | 45 | false | Cellulitis and abscess of foot, except toes |
| 47 | 46 | false | Malignant neoplasm of thyroid gland |
