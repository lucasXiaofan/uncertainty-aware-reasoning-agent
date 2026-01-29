import json

def extract_correct_diagnoses(file_path):
    diagnoses = []
    with open(file_path, 'r') as f:
        for line in f:
            try:
                data = json.loads(line)
                if "OSCE_Examination" in data and "Correct_Diagnosis" in data["OSCE_Examination"]:
                    diagnoses.append(data["OSCE_Examination"]["Correct_Diagnosis"])
            except json.JSONDecodeError:
                print(f"Skipping invalid JSON line")
    return list(set(diagnoses))

if __name__ == "__main__":
    file_path = "benchmarks/AgentClinic/agentclinic_medqa_extended.jsonl"
    diagnoses_list = extract_correct_diagnoses(file_path)
    print(diagnoses_list)
    print(len(diagnoses_list))
