# MIMIC-IV ICD-10-CM Coverage Report

Input run: `experiments/guideline_based_experience/mimic_cases/gpt5_nano_on_mimic_with_mimic_prompt/agentclinic_mimiciv_openai_gpt-5-nano_selected_20260329_133804.jsonl`

ICD source downloaded for matching: CMS/CDC `april-1-2026-code-descriptions-tabular-order.zip`, using `icd10cm_codes_2026.txt` from the extracted Code Descriptions directory. CMS lists this as the April 1, 2026 ICD-10-CM code description release for encounters from April 1, 2026 through September 30, 2026.

Online references checked before download:

- CMS ICD-10 files page: https://www.cms.gov/medicare/coding-billing/icd-10-codes
- CDC ICD-10-CM files page: https://www.cdc.gov/nchs/icd/icd-10-cm/files.html
- CDC ICD-10-CM overview/browser reference: https://www.cdc.gov/nchs/icd/icd-10-cm/index.html

## Method

- Treated the case `correct_diagnosis` label as the target diagnosis.
- Matched each unique label to a billable ICD-10-CM diagnosis code from the downloaded CMS code description file.
- Used exact normalized title matching where possible; used explicit manual mappings for ICD-9-CM legacy wording and narrative labels; used fuzzy description matching only for remaining labels.
- Rolled the matched ICD-10-CM code up to ICD-10-CM chapter ranges.
- Counts are case counts, not unique diagnosis counts, unless explicitly stated.

## Summary

| Metric | Value |
| --- | --- |
| Total cases | 200 |
| Incorrect model cases (`correct: false`) | 117 |
| Correct model cases | 83 |
| Unique diagnosis labels | 115 |
| ICD-10-CM chapters represented | 16 / 22 |
| ICD-10-CM chapters represented among incorrect cases | 16 / 22 |

## Top Missing ICD Chapter Coverage

The 200-case set does not cover these ICD-10-CM chapters at all. The examples are common diagnosis or coding targets that could be added to improve chapter-level coverage.

| Uncovered ICD-10-CM chapter | Common diagnosis/code examples to add |
| --- | --- |
| Diseases of the blood and immune mechanism | Iron deficiency anemia, Vitamin B12 deficiency anemia, Sickle-cell disease, Thrombocytopenia, Neutropenia |
| Diseases of the eye and adnexa | Conjunctivitis, Cataract, Glaucoma, Retinal detachment, Diabetic retinopathy |
| Certain conditions originating in the perinatal period | Neonatal jaundice, Respiratory distress of newborn, Birth asphyxia, Neonatal sepsis, Prematurity/low birth weight |
| Codes for special purposes | Emergency-use code U07.1 COVID-19, Post COVID-19 condition, Other provisional special-purpose codes |
| External causes of morbidity | Motor vehicle traffic accident, Fall from stairs or steps, Accidental poisoning exposure, Assault-related injury mechanism, Burn/fire exposure mechanism |
| Factors influencing health status and contact with health services | Routine health examination, Personal history of malignant neoplasm, Long-term drug therapy, Encounter for immunization, Social determinants such as housing or food insecurity |

## Overall ICD-10-CM Chapter Distribution

| ICD-10-CM chapter | Cases | % of 200 | Incorrect cases | Incorrect rate in chapter | Unique diagnoses |
| --- | --- | --- | --- | --- | --- |
| Symptoms, signs and abnormal clinical and laboratory findings | 38 | 19.0% | 33 | 86.8% | 10 |
| Mental, behavioral and neurodevelopmental disorders | 36 | 18.0% | 25 | 69.4% | 12 |
| Diseases of the digestive system | 28 | 14.0% | 10 | 35.7% | 18 |
| Diseases of the respiratory system | 18 | 9.0% | 6 | 33.3% | 11 |
| Diseases of the musculoskeletal system and connective tissue | 16 | 8.0% | 10 | 62.5% | 11 |
| Diseases of the skin and subcutaneous tissue | 13 | 6.5% | 6 | 46.2% | 8 |
| Diseases of the genitourinary system | 10 | 5.0% | 7 | 70.0% | 7 |
| Diseases of the circulatory system | 9 | 4.5% | 4 | 44.4% | 9 |
| Neoplasms | 8 | 4.0% | 5 | 62.5% | 6 |
| Diseases of the nervous system | 7 | 3.5% | 4 | 57.1% | 7 |
| Certain infectious and parasitic diseases | 4 | 2.0% | 1 | 25.0% | 4 |
| Diseases of the ear and mastoid process | 4 | 2.0% | 1 | 25.0% | 3 |
| Endocrine, nutritional and metabolic diseases | 4 | 2.0% | 1 | 25.0% | 4 |
| Pregnancy, childbirth and the puerperium | 3 | 1.5% | 2 | 66.7% | 3 |
| Congenital malformations, deformations and chromosomal abnormalities | 1 | 0.5% | 1 | 100.0% | 1 |
| Injury, poisoning and certain other consequences of external causes | 1 | 0.5% | 1 | 100.0% | 1 |

## Incorrect-Case ICD-10-CM Chapter Distribution

| ICD-10-CM chapter | Incorrect cases | % of 117 incorrect | Scenario ids |
| --- | --- | --- | --- |
| Symptoms, signs and abnormal clinical and laboratory findings | 33 | 28.2% | 6, 18, 22, 29, 33, 35, 41, 42, 50, 53, 70, 71, 76, 84, 87, 89, 96, 100, 105, 106, 120, 143, 151, 158, 159, 160, 165, 167, 177, 178, 179, 180, 181 |
| Mental, behavioral and neurodevelopmental disorders | 25 | 21.4% | 40, 44, 49, 59, 67, 91, 93, 94, 102, 103, 111, 116, 117, 122, 132, 133, 142, 148, 153, 155, 157, 164, 194, 196, 197 |
| Diseases of the digestive system | 10 | 8.5% | 7, 12, 54, 88, 124, 131, 170, 174, 176, 198 |
| Diseases of the musculoskeletal system and connective tissue | 10 | 8.5% | 3, 10, 16, 19, 20, 24, 25, 82, 139, 195 |
| Diseases of the genitourinary system | 7 | 6.0% | 51, 56, 69, 129, 183, 187, 190 |
| Diseases of the respiratory system | 6 | 5.1% | 58, 80, 97, 108, 135, 184 |
| Diseases of the skin and subcutaneous tissue | 6 | 5.1% | 45, 134, 138, 145, 162, 175 |
| Neoplasms | 5 | 4.3% | 1, 39, 46, 72, 73 |
| Diseases of the circulatory system | 4 | 3.4% | 92, 98, 149, 154 |
| Diseases of the nervous system | 4 | 3.4% | 47, 101, 123, 126 |
| Pregnancy, childbirth and the puerperium | 2 | 1.7% | 52, 189 |
| Certain infectious and parasitic diseases | 1 | 0.9% | 27 |
| Congenital malformations, deformations and chromosomal abnormalities | 1 | 0.9% | 144 |
| Diseases of the ear and mastoid process | 1 | 0.9% | 112 |
| Endocrine, nutritional and metabolic diseases | 1 | 0.9% | 192 |
| Injury, poisoning and certain other consequences of external causes | 1 | 0.9% | 11 |

## Chapter Details

Each row below shows the scenario ids, original MIMIC diagnosis labels, and matched ICD-10-CM diagnosis codes for the chapter.

### Symptoms, signs and abnormal clinical and laboratory findings

| Cases | Scenario ids | Incorrect scenario ids | MIMIC diagnosis | Matched ICD-10-CM diagnosis |
| --- | --- | --- | --- | --- |
| 25 | 18, 22, 29, 33, 35, 41, 42, 50, 53, 71, 76, 84, 96, 105, 106, 143, 151, 158, 159, 160, 165, 167, 177, 178, 179 | 18, 22, 29, 33, 35, 41, 42, 50, 53, 71, 76, 84, 96, 105, 106, 143, 151, 158, 159, 160, 165, 167, 177, 178, 179 | Chest pain, unspecified | R079 - Chest pain, unspecified |
| 4 | 6, 100, 120, 180 | 6, 100, 120, 180 | Other chest pain | R0789 - Other chest pain |
| 2 | 89, 171 | 89 | Dizziness and giddiness | R42 - Dizziness and giddiness |
| 1 | 163 | - | Abdominal pain, epigastric | R1013 - Epigastric pain |
| 1 | 8 | - | Abdominal pain, right lower quadrant | R1031 - Right lower quadrant pain |
| 1 | 119 | - | Epistaxis | R040 - Epistaxis |
| 1 | 70 | 70 | Other convulsions | R569 - Unspecified convulsions |
| 1 | 181 | 181 | Other respiratory abnormalities | R0689 - Other abnormalities of breathing |
| 1 | 87 | 87 | Suicidal ideation | R45851 - Suicidal ideations |
| 1 | 85 | - | Syncope and collapse | R55 - Syncope and collapse |

### Mental, behavioral and neurodevelopmental disorders

| Cases | Scenario ids | Incorrect scenario ids | MIMIC diagnosis | Matched ICD-10-CM diagnosis |
| --- | --- | --- | --- | --- |
| 10 | 40, 93, 102, 111, 116, 122, 132, 148, 153, 194 | 40, 93, 102, 111, 116, 122, 132, 148, 153, 194 | Alcohol abuse, unspecified | F1010 - Alcohol abuse, uncomplicated |
| 6 | 59, 91, 117, 142, 155, 157 | 59, 91, 117, 142, 155, 157 | Alcohol abuse with intoxication, unspecified | F10129 - Alcohol abuse with intoxication, unspecified |
| 6 | 75, 90, 109, 133, 186, 197 | 133, 197 | Major depressive disorder, single episode, unspecified | F329 - Major depressive disorder, single episode, unspecified |
| 5 | 34, 49, 110, 113, 137 | 49 | Depressive disorder, not elsewhere classified | F329 - Major depressive disorder, single episode, unspecified |
| 2 | 94, 103 | 94, 103 | Anxiety state, unspecified | F419 - Anxiety disorder, unspecified |
| 1 | 57 | - | Bipolar II Disorder | F3181 - Bipolar II disorder |
| 1 | 37 | - | Major depressive disorder, recurrent severe without psychotic features | F332 - Major depressive disorder, recurrent severe without psychotic features |
| 1 | 44 | 44 | Opioid abuse, continuous | F1120 - Opioid dependence, uncomplicated |
| 1 | 43 | - | Schizoaffective disorder, unspecified | F259 - Schizoaffective disorder, unspecified |
| 1 | 164 | 164 | Unspecified psychosis | F29 - Unspecified psychosis not due to a substance or known physiological condition |
| 1 | 67 | 67 | Unspecified psychosis possibly compounded by substance use (noting the positive opiate screen). However, thorough examination and history are required to exclude other organic causes. | F29 - Unspecified psychosis not due to a substance or known physiological condition |
| 1 | 196 | 196 | Unspecified schizophrenia, unspecified | F209 - Schizophrenia, unspecified |

### Diseases of the digestive system

| Cases | Scenario ids | Incorrect scenario ids | MIMIC diagnosis | Matched ICD-10-CM diagnosis |
| --- | --- | --- | --- | --- |
| 8 | 21, 26, 54, 55, 88, 156, 174, 198 | 54, 88, 174, 198 | Acute appendicitis without mention of peritonitis | K3580 - Unspecified acute appendicitis |
| 3 | 77, 78, 131 | 131 | Diverticulitis of colon (without mention of hemorrhage) | K5732 - Diverticulitis of large intestine without perforation or abscess without bleeding |
| 2 | 65, 188 | - | Unspecified acute appendicitis | K3580 - Unspecified acute appendicitis |
| 1 | 83 | - | Achalasia and cardiospasm | K220 - Achalasia of cardia |
| 1 | 170 | 170 | Acute appendicitis with generalized peritonitis | K35211 - Acute appendicitis with generalized peritonitis, with perforation and abscess |
| 1 | 7 | 7 | Calculus of bile duct without mention of cholecystitis, without mention of obstruction | K8050 - Calculus of bile duct without cholangitis or cholecystitis without obstruction |
| 1 | 199 | - | Calculus of gallbladder and bile duct with other cholecystitis, without mention of obstruction | K8070 - Calculus of gallbladder and bile duct without cholecystitis without obstruction |
| 1 | 172 | - | Calculus of gallbladder with acute and chronic cholecystitis without obstruction | K8012 - Calculus of gallbladder with acute and chronic cholecystitis without obstruction |
| 1 | 30 | - | Calculus of gallbladder with acute cholecystitis, without mention of obstruction | K8000 - Calculus of gallbladder with acute cholecystitis without obstruction |
| 1 | 124 | 124 | Calculus of gallbladder with other cholecystitis, without mention of obstruction | K8010 - Calculus of gallbladder with chronic cholecystitis without obstruction |
| 1 | 182 | - | Epigastric abdominal pain likely due to Gallstones/Cholelithiasis | K8020 - Calculus of gallbladder without cholecystitis without obstruction |
| 1 | 150 | - | Ischiorectal abscess | K6139 - Other ischiorectal abscess |
| 1 | 176 | 176 | Other and unspecified noninfectious gastroenteritis and colitis | K529 - Noninfective gastroenteritis and colitis, unspecified |
| 1 | 161 | - | Peptic Ulcer Disease | K279 - Peptic ulcer, site unspecified, unspecified as acute or chronic, without hemorrhage or perforation |
| 1 | 118 | - | Ulcerative (chronic) enterocolitis | K5190 - Ulcerative colitis, unspecified, without complications |
| 1 | 130 | - | Umbilical hernia with obstruction, without gangrene | K420 - Umbilical hernia with obstruction, without gangrene |
| 1 | 166 | - | Unspecified appendicitis | K37 - Unspecified appendicitis |
| 1 | 12 | 12 | Unspecified intestinal obstruction | K56609 - Unspecified intestinal obstruction, unspecified as to partial versus complete obstruction |

### Diseases of the respiratory system

| Cases | Scenario ids | Incorrect scenario ids | MIMIC diagnosis | Matched ICD-10-CM diagnosis |
| --- | --- | --- | --- | --- |
| 3 | 38, 66, 104 | - | Acute pharyngitis | J029 - Acute pharyngitis, unspecified |
| 3 | 86, 108, 127 | 108 | Acute Pharyngitis | J029 - Acute pharyngitis, unspecified |
| 3 | 4, 36, 60 | - | Peritonsillar abscess | J36 - Peritonsillar abscess |
| 2 | 9, 58 | 58 | Streptococcal pharyngitis | J020 - Streptococcal pharyngitis |
| 1 | 185 | - | Acute pharyngitis, unspecified | J029 - Acute pharyngitis, unspecified |
| 1 | 135 | 135 | Acute tonsillitis | J0390 - Acute tonsillitis, unspecified |
| 1 | 95 | - | Bacterial Pharyngitis | J020 - Streptococcal pharyngitis |
| 1 | 80 | 80 | Interstitial Emphysema | J982 - Interstitial emphysema |
| 1 | 74 | - | Pneumonia, organism unspecified | J189 - Pneumonia, unspecified organism |
| 1 | 184 | 184 | Streptococcal sore throat | J020 - Streptococcal pharyngitis |
| 1 | 97 | 97 | Unspecified sinusitis (chronic) | J328 - Other chronic sinusitis |

### Diseases of the musculoskeletal system and connective tissue

| Cases | Scenario ids | Incorrect scenario ids | MIMIC diagnosis | Matched ICD-10-CM diagnosis |
| --- | --- | --- | --- | --- |
| 4 | 3, 10, 19, 24 | 3, 10, 19, 24 | Displacement of lumbar intervertebral disc without myelopathy | M5126 - Other intervertebral disc displacement, lumbar region |
| 3 | 63, 81, 128 | - | Rhabdomyolysis | M6282 - Rhabdomyolysis |
| 1 | 82 | 82 | Backache, unspecified | M549 - Dorsalgia, unspecified |
| 1 | 147 | - | Cervical spondylosis with myelopathy | M4712 - Other spondylosis with myelopathy, cervical region |
| 1 | 195 | 195 | Cervical spondylosis without myelopathy | M47812 - Spondylosis without myelopathy or radiculopathy, cervical region |
| 1 | 20 | 20 | Displacement of cervical intervertebral disc without myelopathy | M5020 - Other cervical disc displacement, unspecified cervical region |
| 1 | 31 | - | Intervertebral disc disorders with radiculopathy, lumbosacral region | M5117 - Intervertebral disc disorders with radiculopathy, lumbosacral region |
| 1 | 64 | - | Lumbago | M5450 - Low back pain, unspecified |
| 1 | 16 | 16 | Occipital neuralgia | M5481 - Occipital neuralgia |
| 1 | 25 | 25 | Pain in limb | M79609 - Pain in unspecified limb |
| 1 | 139 | 139 | Pathologic fracture of vertebrae | M8448XA - Pathological fracture, other site, initial encounter for fracture |

### Diseases of the skin and subcutaneous tissue

| Cases | Scenario ids | Incorrect scenario ids | MIMIC diagnosis | Matched ICD-10-CM diagnosis |
| --- | --- | --- | --- | --- |
| 4 | 48, 134, 169, 175 | 134, 175 | Cellulitis and abscess of leg, except foot | L03119 - Cellulitis of unspecified part of limb |
| 2 | 0, 152 | - | Cellulitis and abscess of face | L03211 - Cellulitis of face |
| 2 | 138, 145 | 138, 145 | Cellulitis and abscess of upper arm and forearm | L03119 - Cellulitis of unspecified part of limb |
| 1 | 162 | 162 | Cellulitis and abscess of finger, unspecified | L03019 - Cellulitis of unspecified finger |
| 1 | 45 | 45 | Cellulitis and abscess of foot, except toes | L03119 - Cellulitis of unspecified part of limb |
| 1 | 193 | - | Contact dermatitis and other eczema, unspecified cause | L259 - Unspecified contact dermatitis, unspecified cause |
| 1 | 17 | - | Onychia and paronychia of finger | L03019 - Cellulitis of unspecified finger |
| 1 | 121 | - | Pilonidal cyst with abscess | L0501 - Pilonidal cyst with abscess |

### Diseases of the genitourinary system

| Cases | Scenario ids | Incorrect scenario ids | MIMIC diagnosis | Matched ICD-10-CM diagnosis |
| --- | --- | --- | --- | --- |
| 2 | 125, 183 | 183 | Calculus of kidney | N200 - Calculus of kidney |
| 2 | 56, 190 | 56, 190 | Calculus of ureter | N201 - Calculus of ureter |
| 2 | 99, 136 | - | Torsion of testis, unspecified | N4400 - Torsion of testis, unspecified |
| 1 | 187 | 187 | Bacterial Vaginosis | N760 - Acute vaginitis |
| 1 | 129 | 129 | Hydronephrosis with renal and ureteral calculous obstruction | N132 - Hydronephrosis with renal and ureteral calculous obstruction |
| 1 | 69 | 69 | Pyelonephritis, unspecified | N12 - Tubulo-interstitial nephritis, not specified as acute or chronic |
| 1 | 51 | 51 | Renal colic | N23 - Unspecified renal colic |

### Diseases of the circulatory system

| Cases | Scenario ids | Incorrect scenario ids | MIMIC diagnosis | Matched ICD-10-CM diagnosis |
| --- | --- | --- | --- | --- |
| 1 | 115 | - | Acute pericarditis, unspecified | I309 - Acute pericarditis, unspecified |
| 1 | 68 | - | Acute venous embolism and thrombosis of unspecified deep vessels of lower extremity | I82409 - Acute embolism and thrombosis of unspecified deep veins of unspecified lower extremity |
| 1 | 191 | - | Atherosclerosis of native arteries of the extremities with rest pain | I70222 - Atherosclerosis of native arteries of extremities with rest pain, left leg |
| 1 | 98 | 98 | Atrial fibrillation | I4821 - Permanent atrial fibrillation |
| 1 | 140 | - | Cerebral aneurysm, nonruptured | I671 - Cerebral aneurysm, nonruptured |
| 1 | 28 | - | Cerebral artery occlusion, unspecified with cerebral infarction | I6320 - Cerebral infarction due to unspecified occlusion or stenosis of unspecified precerebral arteries |
| 1 | 92 | 92 | Dissection of vertebral artery | I7774 - Dissection of vertebral artery |
| 1 | 149 | 149 | Occlusion and stenosis of carotid artery without mention of cerebral infarction | I6529 - Occlusion and stenosis of unspecified carotid artery |
| 1 | 154 | 154 | Other pulmonary embolism and infarction | I2699 - Other pulmonary embolism without acute cor pulmonale |

### Neoplasms

| Cases | Scenario ids | Incorrect scenario ids | MIMIC diagnosis | Matched ICD-10-CM diagnosis |
| --- | --- | --- | --- | --- |
| 2 | 23, 141 | - | Leiomyoma of uterus, unspecified | D259 - Leiomyoma of uterus, unspecified |
| 2 | 46, 73 | 46, 73 | Malignant neoplasm of thyroid gland | C73 - Malignant neoplasm of thyroid gland |
| 1 | 39 | 39 | Benign neoplasm of ovary | D271 - Benign neoplasm of left ovary |
| 1 | 1 | 1 | Malignant neoplasm of kidney, except pelvis | C649 - Malignant neoplasm of unspecified kidney, except renal pelvis |
| 1 | 72 | 72 | Malignant neoplasm of left kidney, except renal pelvis | C642 - Malignant neoplasm of left kidney, except renal pelvis |
| 1 | 107 | - | Malignant neoplasm of prostate | C61 - Malignant neoplasm of prostate |

### Diseases of the nervous system

| Cases | Scenario ids | Incorrect scenario ids | MIMIC diagnosis | Matched ICD-10-CM diagnosis |
| --- | --- | --- | --- | --- |
| 1 | 5 | - | Acute infective polyneuritis | G610 - Guillain-Barre syndrome |
| 1 | 101 | 101 | Chronic paroxysmal hemicrania | G44041 - Chronic paroxysmal hemicrania, intractable |
| 1 | 126 | 126 | Compression of the brain | G935 - Compression of brain |
| 1 | 14 | - | Migraine with aura, not intractable, without status migrainosus | G43109 - Migraine with aura, not intractable, without status migrainosus |
| 1 | 47 | 47 | Other causes of myelitis | G0491 - Myelitis, unspecified |
| 1 | 79 | - | Reaction to spinal or lumbar puncture | G971 - Other reaction to spinal and lumbar puncture |
| 1 | 123 | 123 | Unspecified transient cerebral ischemia | G459 - Transient cerebral ischemic attack, unspecified |

### Certain infectious and parasitic diseases

| Cases | Scenario ids | Incorrect scenario ids | MIMIC diagnosis | Matched ICD-10-CM diagnosis |
| --- | --- | --- | --- | --- |
| 1 | 13 | - | Lyme Disease | A6920 - Lyme disease, unspecified |
| 1 | 2 | - | Mononucleosis (Infectious mononucleosis caused by Epstein-Barr virus) | B2700 - Gammaherpesviral mononucleosis without complication |
| 1 | 27 | 27 | The findings do not strongly indicate a specific acute pathology and may be consistent with a non-specific viral illness or early presentation of a more specific illness. The normal range of most test results suggests that there is no immediate acute disease. Given the generalized symptoms and lack of specific findings, a conservative approach with symptomatic treatment and watchful waiting is recommended with instructions to return or seek further care if symptoms worsen or if more specific symptoms develop. | B349 - Viral infection, unspecified |
| 1 | 15 | - | Unspecified viral meningitis | A879 - Viral meningitis, unspecified |

### Diseases of the ear and mastoid process

| Cases | Scenario ids | Incorrect scenario ids | MIMIC diagnosis | Matched ICD-10-CM diagnosis |
| --- | --- | --- | --- | --- |
| 2 | 61, 112 | 112 | Peripheral vertigo, unspecified | H81399 - Other peripheral vertigo, unspecified ear |
| 1 | 32 | - | Infective otitis externa, unspecified | H60399 - Other infective otitis externa, unspecified ear |
| 1 | 146 | - | Otitis media, unspecified, left ear | H6692 - Otitis media, unspecified, left ear |

### Endocrine, nutritional and metabolic diseases

| Cases | Scenario ids | Incorrect scenario ids | MIMIC diagnosis | Matched ICD-10-CM diagnosis |
| --- | --- | --- | --- | --- |
| 1 | 173 | - | Diabetes Mellitus with possible Diabetic Neuropathy | E1140 - Type 2 diabetes mellitus with diabetic neuropathy, unspecified |
| 1 | 192 | 192 | Diabetes mellitus without mention of complication, type II or unspecified type, not stated as uncontrolled | E119 - Type 2 diabetes mellitus without complications |
| 1 | 62 | - | Toxic diffuse goiter without mention of thyrotoxic crisis or storm | E0500 - Thyrotoxicosis with diffuse goiter without thyrotoxic crisis or storm |
| 1 | 168 | - | Type 2 Diabetes Mellitus with signs of hypertension and microalbuminuria | E1129 - Type 2 diabetes mellitus with other diabetic kidney complication |

### Pregnancy, childbirth and the puerperium

| Cases | Scenario ids | Incorrect scenario ids | MIMIC diagnosis | Matched ICD-10-CM diagnosis |
| --- | --- | --- | --- | --- |
| 1 | 52 | 52 | Left tubal pregnancy without intrauterine pregnancy | O00102 - Left tubal pregnancy without intrauterine pregnancy |
| 1 | 114 | - | Right tubal pregnancy without intrauterine pregnancy | O00101 - Right tubal pregnancy without intrauterine pregnancy |
| 1 | 189 | 189 | Threatened premature labor, antepartum condition or complication | O479 - False labor, unspecified |

### Congenital malformations, deformations and chromosomal abnormalities

| Cases | Scenario ids | Incorrect scenario ids | MIMIC diagnosis | Matched ICD-10-CM diagnosis |
| --- | --- | --- | --- | --- |
| 1 | 144 | 144 | Anomalies of other endocrine glands | Q891 - Congenital malformations of adrenal gland |

### Injury, poisoning and certain other consequences of external causes

| Cases | Scenario ids | Incorrect scenario ids | MIMIC diagnosis | Matched ICD-10-CM diagnosis |
| --- | --- | --- | --- | --- |
| 1 | 11 | 11 | Anaphylactic reaction due to unspecified food | T7800XA - Anaphylactic reaction due to unspecified food, initial encounter |

## Coverage Gaps And Example Needs

For full chapter-level coverage across the ICD-10-CM tree, add at least one example in each chapter with zero cases in the 200-case set:

- Diseases of the blood and immune mechanism
- Diseases of the eye and adnexa
- Certain conditions originating in the perinatal period
- Codes for special purposes
- External causes of morbidity
- Factors influencing health status and contact with health services

Note: `External causes of morbidity`, `Factors influencing health status and contact with health services`, and `Codes for special purposes` are useful for full ICD-tree stress testing, but they are often secondary/supporting codes rather than primary diagnosis targets.

For failure-analysis coverage, add or surface incorrect examples in chapters that have no `correct: false` cases:

- Diseases of the blood and immune mechanism
- Diseases of the eye and adnexa
- Certain conditions originating in the perinatal period
- Codes for special purposes
- External causes of morbidity
- Factors influencing health status and contact with health services

Chapters represented by fewer than 3 examples are weakly covered and should receive more examples before treating the set as balanced:

- Congenital malformations, deformations and chromosomal abnormalities: 1 case(s)
- Injury, poisoning and certain other consequences of external causes: 1 case(s)

Among represented chapters with at least 3 cases, the categories most in need of additional training examples because of high error rates are:

| ICD-10-CM chapter | Cases | Incorrect | Incorrect rate |
| --- | --- | --- | --- |
| Symptoms, signs and abnormal clinical and laboratory findings | 38 | 33 | 86.8% |
| Diseases of the genitourinary system | 10 | 7 | 70.0% |
| Mental, behavioral and neurodevelopmental disorders | 36 | 25 | 69.4% |
| Pregnancy, childbirth and the puerperium | 3 | 2 | 66.7% |
| Diseases of the musculoskeletal system and connective tissue | 16 | 10 | 62.5% |
| Neoplasms | 8 | 5 | 62.5% |
| Diseases of the nervous system | 7 | 4 | 57.1% |
| Diseases of the skin and subcutaneous tissue | 13 | 6 | 46.2% |
| Diseases of the circulatory system | 9 | 4 | 44.4% |
| Diseases of the digestive system | 28 | 10 | 35.7% |

## Matching Audit

| Method | Unique diagnoses |
| --- | --- |
| manual_legacy_or_narrative_mapping | 54 |
| exact_normalized_description | 33 |
| fuzzy_description_match | 28 |

Manual mappings are listed in `mimiciv_icd10cm_matches.json` for review. These are the main source of judgment because many source labels use legacy ICD-9 wording such as `without mention of`, `NEC`, or `except pelvis`.
