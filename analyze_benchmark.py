import json
import os

def analyze_results(file_path):
    if not os.path.exists(file_path):
        print(f"File {file_path} not found.")
        return

    data = []
    with open(file_path, 'r') as f:
        for line in f:
            data.append(json.loads(line))

    total_cases = len(data)
    correct_cases = 0
    total_tokens = 0
    total_interactions = 0
    total_subjective_qa = 0
    total_examination = 0
    
    patient_stats = []

    for item in data:
        # Correctness logic
        ground_truth = item["original_data"].get("Final Diagnosis", "").lower()
        predicted_diagnoses = []
        for record in item["patient_records"]:
            if record.get("Recording Department") == "end_of_diagnosis":
                predicted_diagnoses = record.get("final_diagnosis", [])
                break
        
        is_correct = False
        if isinstance(predicted_diagnoses, list):
            for pred in predicted_diagnoses:
                if ground_truth in pred.lower() or pred.lower() in ground_truth:
                    is_correct = True
                    break
        
        if is_correct:
            correct_cases += 1
            
        t_tokens = item.get("total_tokens", 0)
        t_interactions = item.get("total_interactions", 0)
        s_qa = item.get("subjective_qa_interactions", 0)
        e_int = item.get("examination_interactions", 0)
        
        # Count unique lab exams
        lab_exams = []
        for record in item["patient_records"]:
            if record.get("Recording Department") == "diagnostic_test":
                tests_str = record.get("Completed Tests", "[]")
                # Handle string vs list
                if isinstance(tests_str, str):
                    try:
                        # Sometimes it's string representation of list like "['test1', 'test2']"
                        # But json.loads expects double quotes
                        valid_json = tests_str.replace("'", "\"")
                        tests = json.loads(valid_json)
                    except:
                        tests = []
                else:
                    tests = tests_str
                lab_exams.extend(tests)
        
        # Count from diagnosis_reports as well just in case
        reports_count = len(item.get("diagnosis_reports", []))
        
        patient_stats.append({
            "id": item["original_data"]["id"],
            "correct": is_correct,
            "total_tokens": t_tokens,
            "total_interactions": t_interactions,
            "subjective_qa": s_qa,
            "examination": e_int,
            "lab_exams_count": reports_count,
            "lab_exams_list": [r.get("test_name") for r in item.get("diagnosis_reports", [])]
        })
        
        total_tokens += t_tokens
        total_interactions += t_interactions
        total_subjective_qa += s_qa
        total_examination += e_int

    print("=== BENCHMARK SUMMARY ===")
    print(f"Total Cases: {total_cases}")
    print(f"Correct: {correct_cases}")
    print(f"Accuracy: {correct_cases/total_cases:.2%}")
    print(f"Average Total Interactions: {total_interactions/total_cases:.2f}")
    print(f"Average Subjective QA Interactions: {total_subjective_qa/total_cases:.2f}")
    print(f"Average Examination Interactions: {total_examination/total_cases:.2f}")
    print(f"Average Tokens: {total_tokens/total_cases:.2f}")
    print("\n=== PER PATIENT ANALYSIS ===")
    print(f"{'ID':<5} | {'Correct':<8} | {'Subj QA':<8} | {'Exam':<8} | {'Labs':<5} | {'Tokens':<10}")
    print("-" * 60)
    for p in patient_stats:
        print(f"{p['id']:<5} | {'Yes' if p['correct'] else 'No':<8} | {p['subjective_qa']:<8} | {p['examination']:<8} | {p['lab_exams_count']:<5} | {p['total_tokens']:<10}")
        if p['lab_exams_list']:
            print(f"      Exams: {', '.join(p['lab_exams_list'])}")

if __name__ == "__main__":
    analyze_results("benchmarks/CP_ENV/outputs/P_gpt-4o-mini-D_gpt-4o-mini-results.jsonl")
