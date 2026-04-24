import csv
import json
import sys
import os

csv.field_size_limit(sys.maxsize)

stats = {
    'total_records': 0,
    'has_some_history': 0,
    'has_some_physical': 0,
    'has_both': 0
}

header_saved = None
full_rows = []

input_path = '/Users/xiaofanlu/Documents/github_repos/uncertainty-aware-reasoning-agent/experiments/similar_patient/mimiciv_single_diagnosis_nonoverlap_case_data.csv'

with open(input_path, 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    header_saved = next(reader)
    
    for row in reader:
        stats['total_records'] += 1
        row_dict = dict(zip(header_saved, row))
        
        has_history = False
        try:
            history = json.loads(row_dict['history_json'])
            has_history = len(history) > 0
        except:
            pass
            
        has_physical = False
        try:
            tests = json.loads(row_dict['tests_json'])
            has_physical = any(k in tests for k in ['Blood Pressure', 'Temperature Blood', 'Heart Rate', 'Respiratory Rate', 'Weight (Lbs)', 'Height (Inches)'])
        except:
            pass
        
        if has_history:
            stats['has_some_history'] += 1
        if has_physical:
            stats['has_some_physical'] += 1
        if has_history and has_physical:
            stats['has_both'] += 1
            full_rows.append(row)

output_dir = '/Users/xiaofanlu/Documents/github_repos/uncertainty-aware-reasoning-agent/experiments/similar_patient/mimic_data_stats'
os.makedirs(output_dir, exist_ok=True)

report_path = os.path.join(output_dir, 'mimic_data_stats_partial_report.txt')
with open(report_path, 'w', encoding='utf-8') as f:
    f.write("MIMIC-IV Partial Information Stats Report\n")
    f.write("=========================================\n")
    f.write(f"Total records processed: {stats['total_records']}\n")
    f.write(f"Records with *SOME* patient history (non-empty history_json): {stats['has_some_history']}\n")
    f.write(f"Records with *SOME* physical exam vitals (Blood Pressure, Temp, etc. in tests_json): {stats['has_some_physical']}\n")
    f.write(f"Records containing BOTH some history and some physical exams: {stats['has_both']}\n")

csv_path = os.path.join(output_dir, 'filtered_partial_info_data.csv')
with open(csv_path, 'w', encoding='utf-8', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(header_saved)
    writer.writerows(full_rows)

print("Processing complete. Partial report and CSV generated.")
