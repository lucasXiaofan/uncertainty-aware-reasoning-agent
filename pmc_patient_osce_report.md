# PMC Patients OSCE Conversion Report

Source file: `/Users/xiaofanlu/Documents/github_repos/uncertainty-aware-reasoning-agent/PMC-Patients.csv`

This report extracts two patients with enough structured clinical detail to support OSCE-style patient generation. Diagnostic judgments are educational interpretations from the case text, not clinical advice.

## Selection Criteria

- Clear presenting complaint and clinical course.
- Demographics, history, examination, investigations, and diagnosis available in the CSV row.
- Similar-patient links present in the `similar_patients` field.
- Suitable for an OSCE station without needing excessive invented data.

## Patient 1: Transient Small-Bowel Intussusception Presenting as RLQ Pain

### Source Row

- `patient_id`: `75663`
- `patient_uid`: `4064808-1`
- `PMID`: `24982750`
- Title: `Case report: transient small bowel intussusception presenting as right lower quadrant pain in a 6-year-old male`
- Age: `[[6.0, 'year']]`
- Gender: `M`
- Similar patients: `{'7676809-1': 1, '4811016-1': 1, '7263756-1': 1}`
- Relevant article PMID weights: `{'16944032': 1, '27069937': 2, '17875595': 1, '16702451': 1, '32509264': 2, '21512048': 1, '33217271': 2, '11282672': 1, '15467415': 1, '14770321': 1, '20684696': 1, '9486044': 1, '21768232': 1, '24982750': 2}`

### Extracted Full Clinical Information

- Demographics: 6-year-old male.
- Presentation: sudden-onset severe right lower quadrant abdominal pain for 4 hours.
- Pain character: 10/10, constant, sharp, non-radiating.
- Associated symptoms denied: nausea, vomiting, fever, chills, urinary complaints.
- Bowel history: last normal bowel movement 1 day before presentation.
- Exposure history: no rash, sick contacts, or recent travel.
- General appearance: well-developed child in moderate distress.
- Vital signs: blood pressure 107/66 mmHg, pulse 110 bpm, respiratory rate 24/min, temperature 96.9 F, oxygen saturation 95% on room air.
- HEENT: dry/warm skin; erythematous oropharynx without tonsillar enlargement or exudates.
- Cardiovascular: tachycardia; no murmurs, rubs, or gallops.
- Abdominal exam: soft, non-distended abdomen; right lower quadrant tenderness with rebound and guarding; normal active bowel sounds.
- Other exam: no costovertebral angle tenderness; rectal exam normal with hemoccult-negative brown stool; genitourinary exam unremarkable.
- Laboratory findings: potassium 3.3 mmol/L, bicarbonate 17 mmol/L, normal WBC 7 K/uL.
- Urinalysis: trace ketones and few bacteria.
- Point-of-care ultrasound: appendix not visualized; small amount of intraperitoneal free fluid; portion of small bowel with onion-skin target appearance measuring 2.1 cm, suspicious for intussusception.
- CT abdomen/pelvis with oral and IV contrast: normal appendix, small free fluid, short segment of transient ileo-ileal small-bowel intussusception; no bowel wall thickening or obstruction; contrast reached the colon.
- ED treatment: normal saline bolus and IV morphine.
- Initial concern: appendicitis, prompting surgical consultation.
- Clinical course: after CT, abdominal tenderness resolved; tolerated oral fluids; observed through 7-hour ED course without recurrent pain or tenderness.
- Disposition: discharged with close pediatrician follow-up and return precautions.
- Final diagnosis in source: transient intussusception.

### Relevant Similar Patients

#### Similar Patient `7676809-1`

- `patient_id`: `28160`
- `PMID`: `33217271`
- Title: `Ureteral Stone Mimics Appendicitis: A Point-of-care Ultrasound Case Report`
- Demographics: 17-year-old male.
- Key presentation: RLQ abdominal pain beginning a few hours before ED arrival with nausea and subjective fever.
- Vitals: heart rate 106 bpm, blood pressure 130/90 mmHg, afebrile, normal oxygen saturation.
- Exam: isolated RLQ tenderness without peritoneal signs; no suprapubic or CVA tenderness.
- Labs: normal WBC, CRP, and creatinine.
- Imaging: RLQ POCUS showed a hyperechoic shadowing focus in a tubular structure, atypical for appendicitis; CT confirmed an 11-mm obstructing ureteral stone with hydroureter and hydronephrosis.
- Outcome: IV fluids and analgesia, admission, cystoscopy and ureteral stent, later lithotripsy and stone extraction.
- Relevance: RLQ pain mimic of appendicitis where POCUS and CT prevented incorrect diagnosis.

#### Similar Patient `4811016-1`

- `patient_id`: `86040`
- `PMID`: `27069937`
- Title: `Diagnostic Dilemma in the Treatment of a Fatal Case of Bloody Diarrhea`
- Demographics: 13-month-old male.
- Key presentation: diarrhea progressing to frank bloody stools, tenesmus, lethargy, abdominal pain behavior with legs drawn up.
- Vitals at ED presentation: rectal temperature 101 F, heart rate 140/min, blood pressure 101/57 mmHg, respiratory rate 28/min, oxygen saturation 100% on room air.
- Exam: tired-appearing, intermittently crying, dry mucous membranes, abdominal tenderness, hypoactive bowel sounds, frankly bloody stool.
- Imaging: abdominal radiographs showed non-obstructive pattern and RLQ density; ultrasound showed peritoneal fluid, rectosigmoid edema and bowel wall thickening, without intussusception or appendicitis.
- Course: transient improvement after fluids, then acute deterioration with shock, respiratory distress, ascites, bowel wall thickening, and suspected infectious abdominal process.
- Relevance: pediatric abdominal pain and bloody stool differential; useful contrast with classic intussusception features and serious mimics.

#### Similar Patient `7263756-1`

- `patient_id`: `98146`
- `PMID`: `32509264`
- Title: `Celiac disease: a rare cause of 'postoperative' ileoileal intussusception after surgical reduction of ileocolic intussusception in a toddler`
- Demographics: 3.5-year-old female.
- Key presentation: abdominal pain, non-bilious non-bloody vomiting for 36 hours, last bowel movement 2 days prior.
- Background: sickle cell anemia; family history of celiac disease.
- Exam/labs: normal initial vitals; hemoglobin 9.3 g/dL; tender distended abdomen.
- Imaging/procedures: ultrasound suggested right iliac fossa intussusception with free fluid; hydrostatic reduction failed; surgical reduction performed. Recurrent postoperative ileoileal intussusception occurred; later investigations found celiac disease on endoscopy and histology.
- Outcome: gluten-free diet, symptom-free at 8-month follow-up.
- Relevance: pediatric ileoileal intussusception and recurrence; emphasizes need to consider lead points or underlying disease.

### Diagnostic Judgment

The best diagnosis is transient ileo-ileal small-bowel intussusception. Appendicitis was clinically plausible because of severe RLQ pain, guarding, and rebound, but the normal WBC, nonvisualized appendix on ultrasound, normal appendix on CT, short segment target lesion, lack of obstruction, and spontaneous resolution support transient small-bowel intussusception rather than appendicitis.

Important differentials for an OSCE station:

- Acute appendicitis.
- Ileocolic intussusception.
- Ureteral stone.
- Mesenteric adenitis.
- Viral gastroenteritis.
- Testicular torsion or other genitourinary cause, although GU exam was unremarkable.

### OSCE Suitability

Can generate OSCE patient: yes.

This is a strong OSCE case because it begins like appendicitis but requires candidates to ask targeted pediatric abdominal-pain questions, examine for peritonism, order appropriate imaging, and interpret discordant ultrasound/CT results. It is also useful for assessing whether the candidate avoids premature surgical anchoring.

Limitations:

- Social history is minimal beyond no recent travel, sick contacts, or rash.
- Family history and medication history are not provided.
- The station should not overstate classic intussusception features because this patient lacked vomiting and bloody stool.

### OSCE Format Patient

```json
{
  "OSCE_Examination": {
    "Objective_for_Doctor": "Assess a child with acute right lower quadrant abdominal pain, identify urgent differentials, interpret imaging, and determine appropriate management.",
    "Patient_Actor": {
      "Demographics": "6-year-old male, history provided by mother/caregiver",
      "History": "Sudden onset of severe, constant, sharp right lower quadrant abdominal pain for 4 hours. Pain is 10/10 and non-radiating. Last normal bowel movement was yesterday. No nausea, vomiting, fever, chills, urinary symptoms, rash, sick contacts, or recent travel.",
      "Symptoms": {
        "Primary_Symptom": "Severe right lower quadrant abdominal pain",
        "Secondary_Symptoms": [
          "No vomiting",
          "No fever or chills",
          "No urinary symptoms",
          "No recent travel or sick contacts"
        ]
      },
      "Past_Medical_History": "Not provided in source.",
      "Medication_History": "Not provided in source.",
      "Social_History": "Child; no recent travel or sick contacts reported.",
      "Review_of_Systems": "Negative for vomiting, fever, chills, urinary complaints, rash, and recent infectious contacts."
    },
    "Physical_Examination_Findings": {
      "Vital_Signs": {
        "Temperature": "96.9 F",
        "Blood_Pressure": "107/66 mmHg",
        "Heart_Rate": "110 bpm",
        "Respiratory_Rate": "24 breaths/min",
        "Oxygen_Saturation": "95% on room air"
      },
      "Abdominal_Examination": {
        "Inspection": "Soft, non-distended abdomen.",
        "Auscultation": "Normal active bowel sounds.",
        "Palpation": "Right lower quadrant tenderness with rebound and guarding.",
        "Other": "No costovertebral angle tenderness; rectal exam normal with hemoccult-negative brown stool; genitourinary exam unremarkable."
      }
    },
    "Test_Results": {
      "Laboratory": {
        "WBC": "7 K/uL, normal",
        "Potassium": "3.3 mmol/L, low",
        "Bicarbonate": "17 mmol/L, low",
        "Urinalysis": "Trace ketones and few bacteria"
      },
      "Imaging": {
        "POCUS_RLQ": "Appendix not visualized; small amount of free fluid; 2.1 cm onion-skin target appearance in small bowel, suspicious for intussusception.",
        "CT_Abdomen_Pelvis": "Normal appendix, small free fluid, short segment transient ileo-ileal small-bowel intussusception, no obstruction or bowel wall thickening."
      }
    },
    "Correct_Diagnosis": "Transient ileo-ileal small-bowel intussusception",
    "Key_Differentials": [
      "Acute appendicitis",
      "Ileocolic intussusception",
      "Ureteral stone",
      "Mesenteric adenitis",
      "Viral gastroenteritis"
    ],
    "Expected_Management": "Analgesia, fluids, surgical consultation if peritonism or appendicitis concern, imaging confirmation, serial abdominal examinations, oral challenge, discharge only if symptoms resolve with reliable follow-up and return precautions."
  }
}
```

## Patient 2: Ruptured Diaphragmatic Ectopic Pregnancy

### Source Row

- `patient_id`: `92`
- `patient_uid`: `8699918-1`
- `PMID`: `34943579`
- Title: `Ruptured Hemorrhagic Ectopic Pregnancy Implanted in the Diaphragm: A Rare Case Report and Brief Literature Review`
- Age: `[[34.0, 'year']]`
- Gender: `F`
- Similar patients: `{'2737786-1': 1, '2737786-2': 1, '2737786-3': 1, '6438013-1': 1}`
- Relevant article PMID weights: `{'1886705': 1, '20955992': 1, '8981153': 1, '11177167': 1, '19936121': 1, '24101604': 1, '15504077': 1, '30922250': 2, '12601846': 1, '24791968': 1, '8841236': 1, '32852572': 1, '20110090': 1, '31642129': 1, '28672941': 1, '11770598': 1, '26554319': 1, '19876640': 1, '3822281': 1, '22690833': 1, '19229547': 1, '23482340': 1, '19830195': 2, '12418072': 1, '3281075': 1, '27480601': 1, '6792237': 1, '32609376': 1, '15121609': 1, '850569': 1, '17377898': 1, '34943579': 2}`

### Extracted Full Clinical Information

- Demographics/obstetric history: 34-year-old woman, gravida 3 para 3, three spontaneous vaginal deliveries.
- Presentation: transferred from local clinic to Ulsan University Hospital for severe abdominal pain with right flank pain.
- Past medical/surgical history: previously healthy; no specific medical or surgical history.
- Menstrual history: irregular menstruation; last menstruation 5 weeks and 6 days earlier.
- Initial vitals: blood pressure 114/68 mmHg, pulse 71 bpm; described as stable.
- Physical exam: whole abdominal tenderness with muscle guarding.
- Labs: hemoglobin 10.7 g/dL initially, falling to 8.6 g/dL after 8 hours.
- Pregnancy testing: urinary pregnancy test positive; serum beta-HCG 7377.0 mIU/mL.
- Pelvic ultrasound: no intrauterine pregnancy; normal bilateral adnexa; free fluid collection suggesting hemoperitoneum.
- Treatment before surgery: transfused two packs of packed red blood cells.
- Diagnostic reasoning: suspected ruptured ectopic pregnancy because beta-HCG was elevated and no intrauterine pregnancy was seen, but pelvic ultrasound did not identify an ectopic mass.
- APCT: about 2 cm hypervascular mass in the subphrenic region with moderate hemoperitoneum, thought to be the bleeding source.
- Preoperative concern: diaphragmatic ectopic pregnancy or another ruptured unknown hepatic mass.
- Surgery: emergency diagnostic laparoscopy with hepatobiliary surgeon and obstetrician-gynecologist.
- Operative findings: about 400 mL of blood and clots aspirated from pelvic cavity; both adnexa normal; about 20 x 10 cm placenta-like tissue with hematoma covering the diaphragm; 2 cm hypervascular mass attached to diaphragm.
- Treatment: mass completely resected from diaphragm and sent for histology.
- Outcome: discharged without postoperative complications; beta-HCG normalized within 1 month.
- Final pathology: product of conception, consistent with ectopic pregnancy.
- Final diagnosis in source: ruptured hemorrhagic ectopic pregnancy implanted in the diaphragm.

### Relevant Similar Patients

#### Similar Patient `2737786-1`

- `patient_id`: `91817`
- `PMID`: `19830195`
- Title: `Secondary abdominal pregnancy and its associated diagnostic and operative dilemma: three case reports`
- Demographics: 30-year-old woman, G4 P2 L2 A1.
- Presentation: amenorrhea, urinary retention, constipation, abdominal pain.
- Exam: mild pallor, hemodynamically stable, suprapubic mass with tenderness and guarding; vaginal exam showed acutely retroverted uterus and separate tender 16-week mass.
- Imaging: transvaginal ultrasound showed empty uterus and live 16-week fetus in pouch of Douglas; placenta above uterine fundus.
- Diagnosis/treatment: secondary abdominal pregnancy; methotrexate then laparotomy with fetal extraction, partial placental removal, partial omentectomy.
- Outcome: uncomplicated recovery; beta-HCG normalized after 3 weeks.
- Relevance: abdominal ectopic pregnancy with diagnostic and operative complexity.

#### Similar Patient `2737786-2`

- `patient_id`: `91818`
- `PMID`: `19830195`
- Title: `Secondary abdominal pregnancy and its associated diagnostic and operative dilemma: three case reports`
- Demographics: 26-year-old woman, third gravida, two prior full-term vaginal deliveries.
- Presentation: positive pregnancy test after tubal ligation and dilatation/evacuation, worsening lower abdominal pain with fever and dysuria.
- Exam: moderate anemia, tachycardia, hypotension, abdominal free fluid, right adnexal tenderness/mass.
- Imaging/procedure: ultrasound showed intraperitoneal fluid, normal-sized uterus, live 14-week fetus in pouch of Douglas; paracentesis confirmed hemoperitoneum.
- Surgery: placenta attached to omentum, bowel, posterior uterus, and right cornua; partial omentectomy and partial retained placenta.
- Outcome: transfused two units of blood; complete placental resorption by approximately 6 weeks.
- Relevance: abdominal pregnancy with hemoperitoneum and shock physiology.

#### Similar Patient `2737786-3`

- `patient_id`: `91819`
- `PMID`: `19830195`
- Title: `Secondary abdominal pregnancy and its associated diagnostic and operative dilemma: three case reports`
- Demographics: 24-year-old primigravida.
- Presentation: recurrent abdominal pain from about 14 weeks, anemia, later loss of fetal movement and failed induction.
- Diagnostic issue: ultrasound misreported an intrauterine pregnancy with placenta previa.
- Intraoperative finding: secondary abdominal pregnancy discovered during surgery; fetus in abdominal cavity; placenta adherent to omentum and bowel.
- Complication: torrential bleeding during attempted placental removal; seven units of whole blood transfused.
- Outcome: discharged postoperative day 20; complete placental absorption took 6 months.
- Relevance: missed abdominal pregnancy and high hemorrhage risk during surgery.

#### Similar Patient `6438013-1`

- `patient_id`: `7357`
- `PMID`: `30922250`
- Title: `Successful laparoscopic management of diaphragmatic pregnancy:a rare case report and brief review of literature`
- Demographics: 33-year-old Chinese woman with previous cesarean section.
- Presentation: 8-week delayed menstruation, increasing right upper quadrant abdominal pain, right shoulder referred pain for 1 day.
- Labs: hCG 3129.94 IU/L, hemoglobin 10.3 g/dL.
- Ultrasound: no intrauterine pregnancy, normal adnexa, large free abdominal fluid.
- CT: 90-mm mixed hypodense mass on upper surface of right liver lobe.
- Deterioration: increasing pain and weakness; pulse 109 bpm, blood pressure 90/50 mmHg; non-coagulable blood on abdominocentesis.
- Surgery: laparoscopy showed about 1500 mL hemoperitoneum, normal uterus and ovaries, bleeding mass 80 x 50 mm on diaphragm; mass completely resected.
- Outcome: pathology confirmed ectopic pregnancy; hCG normalized within 2 weeks.
- Relevance: highly similar diaphragmatic ectopic pregnancy with hemoperitoneum and laparoscopic management.

### Diagnostic Judgment

The best diagnosis is ruptured hemorrhagic diaphragmatic ectopic pregnancy. The combination of positive pregnancy test, beta-HCG above discriminatory levels, empty uterus, free fluid/hemoperitoneum, falling hemoglobin, normal adnexa, and a bleeding subphrenic/diaphragmatic mass is highly consistent with an abdominal ectopic pregnancy implanted on the diaphragm.

Important differentials for an OSCE station:

- Tubal ectopic pregnancy.
- Ruptured ovarian cyst or hemorrhagic corpus luteum.
- Spontaneous abortion with hemoperitoneum from another source.
- Hepatic or subphrenic vascular mass/bleeding lesion.
- Appendicitis or biliary disease if right-sided pain dominates.

### OSCE Suitability

Can generate OSCE patient: yes, with one caveat.

This is a strong advanced OSCE or emergency/OBGYN simulation because it tests early pregnancy abdominal pain, pregnancy-of-unknown-location workup, hemorrhage recognition, interpretation of empty uterus plus elevated beta-HCG, escalation to urgent imaging/surgery, and multidisciplinary management.

Caveat:

- The final implantation site is very rare. For a general OSCE, the expected diagnosis should be "ruptured ectopic pregnancy with hemoperitoneum" rather than requiring the candidate to name "diaphragmatic ectopic pregnancy" before imaging or surgery.

### OSCE Format Patient

```json
{
  "OSCE_Examination": {
    "Objective_for_Doctor": "Assess and manage a reproductive-age patient with severe abdominal pain, positive pregnancy test, falling hemoglobin, and suspected ruptured ectopic pregnancy.",
    "Patient_Actor": {
      "Demographics": "34-year-old female, gravida 3 para 3",
      "History": "Severe abdominal pain with right flank pain. Irregular menstrual cycles; last menstrual period was 5 weeks and 6 days ago. Previously healthy with no specific medical or surgical history. Three prior spontaneous vaginal deliveries.",
      "Symptoms": {
        "Primary_Symptom": "Severe abdominal pain",
        "Secondary_Symptoms": [
          "Right flank pain",
          "Irregular menstrual history",
          "Positive pregnancy test",
          "No intrauterine pregnancy on sonography"
        ]
      },
      "Past_Medical_History": "Previously healthy; no specific medical or surgical history reported.",
      "Obstetric_History": "Gravida 3, para 3, three spontaneous vaginal deliveries.",
      "Social_History": "Not provided in source.",
      "Review_of_Systems": "Source emphasizes abdominal and right flank pain; other systems not detailed."
    },
    "Physical_Examination_Findings": {
      "Vital_Signs": {
        "Blood_Pressure": "114/68 mmHg initially",
        "Heart_Rate": "71 bpm initially"
      },
      "Abdominal_Examination": {
        "Palpation": "Whole abdominal tenderness with muscle guarding."
      }
    },
    "Test_Results": {
      "Pregnancy_Testing": {
        "Urine_Pregnancy_Test": "Positive",
        "Serum_Beta_HCG": "7377.0 mIU/mL"
      },
      "Blood_Tests": {
        "Hemoglobin_Initial": "10.7 g/dL",
        "Hemoglobin_8_Hours_Later": "8.6 g/dL"
      },
      "Imaging": {
        "Gynecological_Sonography": "No intrauterine pregnancy; normal bilateral adnexa; free fluid suggesting hemoperitoneum.",
        "Abdominopelvic_CT": "About 2 cm hypervascular subphrenic mass with moderate hemoperitoneum."
      },
      "Operative_Findings": {
        "Laparoscopy": "400 mL blood and clots in pelvis; normal adnexa; placenta-like tissue and a 2 cm hypervascular mass attached to diaphragm.",
        "Pathology": "Product of conception, consistent with ectopic pregnancy."
      }
    },
    "Correct_Diagnosis": "Ruptured hemorrhagic diaphragmatic ectopic pregnancy",
    "Acceptable_OSCE_Diagnosis": "Ruptured ectopic pregnancy with hemoperitoneum",
    "Key_Differentials": [
      "Tubal ectopic pregnancy",
      "Ruptured ovarian cyst",
      "Miscarriage with unrelated intra-abdominal bleeding",
      "Hepatic or subphrenic bleeding mass",
      "Appendicitis or biliary disease"
    ],
    "Expected_Management": "Recognize ectopic pregnancy risk, obtain pregnancy testing and beta-HCG, urgent pelvic ultrasound, monitor hemodynamics and hemoglobin, resuscitate and transfuse as needed, escalate to obstetrics/gynecology and surgery, proceed to emergency laparoscopy/laparotomy when rupture or hemoperitoneum is suspected."
  }
}
```

## Overall Judgment

Both selected patients can be converted into OSCE-format cases.

- Patient 1 is best for pediatric emergency medicine or abdominal pain differential diagnosis. It is good for testing appendicitis anchoring and use of imaging plus serial exams.
- Patient 2 is best for emergency medicine, obstetrics/gynecology, or acute care simulation. It is good for testing pregnancy-of-unknown-location, hemoperitoneum, and urgent escalation.

Recommended OSCE design choice:

- Use Patient 1 as a standard OSCE station.
- Use Patient 2 as an advanced OSCE station, accepting "ruptured ectopic pregnancy" as the key diagnosis and reserving "diaphragmatic implantation" for imaging/operative interpretation.
