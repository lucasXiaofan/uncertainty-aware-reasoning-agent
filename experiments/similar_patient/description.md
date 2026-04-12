
› in '/Users/xiaofanlu/
  Documents/github_repos/
  uncertainty-aware-reasoning-
  agent/experiments/
  similar_patient' first find
  the patient that is already
  in the '/Users/xiaofanlu/
  Documents/github_repos/
  uncertainty-aware-reasoning-
  agent/experiments/
  similar_patient/
  agentclinic_mimiciv.jsonl'
  the goal is Of the 40,000
  patients in MIMIC-IV
  dataset, the majority of
  patients (∼34,000) contain
  multiple
  diagnoses simultaneously
  (some patients have hundreds
  of diagnoses). Whereas in
  AgentClinic, the
  doctor agent must arrive at
  a singular diagnosis after
  examination. In order to
  present compatibility, we
  select the first 200
  patients out of a total
  ∼6,000 from MIMIC-IV which
  present only one diagnosis.
  We
  also extract all of the
  patient’s corresponding lab
  events, microbiology events,
  and their online medical
  records.  so the '/Users/
  xiaofanlu/Documents/
  github_repos/uncertainty-
  aware-reasoning-agent/
  experiments/similar_patient/
  agentclinic_mimiciv.jsonl'
  contain the 200 patient, I
  want to find at least 4000
  patient that is not overlap
  with the 200 patient, but
  with one diagnosis, give me
  a csv, that have the patient
  id, and their diagnosis in
  icd code and natural
  language all the mimic data
  aware-reasoning-agent/
  mimic_hosp'


next for those 4000 patient, 
make a csv that contain all the necessary information to make a new patient, see the required information to make new patient from experiments/similar_patient/gen_mimic_tutorial.py

then write a new script, that input list of target diagnosis, return the information needed to make a new patient in txt, each item is a prompt to prompt llm geenrate new patient in format described in experiments/similar_patient/gen_mimic_tutorial.py that contain (instruction + example + patient information) the goal is I can load the line of the txt to ask llm generate new OSCE format patient.