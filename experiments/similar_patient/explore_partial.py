import csv
import json
import sys

csv.field_size_limit(sys.maxsize)

stats = {
    'total_records': 0,
    'has_some_history': 0,
    'has_vital_signs': 0,
    'has_both_partial': 0,
}

full_rows = []
header_saved = None

input_path = '/Users/xiaofanlu/Documents/github_repos/uncertainty-aware-reasoning-agent/experiments/similar_patient/mimiciv_single_diagnosis_nonoverlap_case_data.csv'

with open(input_path, 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    header_saved = next(reader)
    
    for row in reader:
        stats['total_records'] += 1
        row_dict = dict(zip(header_saved, row))
        
        # Check history_json
        try:
            history = json.loads(row_dict['history_json'])
            has_history = len(history) > 0
        except:
            has_history = False
            
        # Check physical/vitals in tests_json
        try:
            tests = json.loads(row_dict['tests_json'])
            has_vitals = any(k in tests for k in ['Blood Pressure', 'Temperature Blood', 'Heart Rate', 'Respiratory Rate'])
        except:
            has_vitals = False
            
        if has_history:
            stats['has_some_history'] += 1
        if has_vitals:
            stats['has_vital_signs'] += 1
        if has_history and has_vitals:
            stats['has_both_partial'] += 1
            full_rows.append(row)

print("Stats for partial information:")
print(json.dumps(stats, indent=2))

print("\nSample partial row history:")
if full_rows:
    row_dict = dict(zip(header_saved, full_rows[0]))
    print(row_dict['history_json'])
    tests = json.loads(row_dict['tests_json'])
    vitals = {k: tests[k] for k in ['Blood Pressure', 'Temperature Blood'] if k in tests}
    print("Vitals:", vitals)
