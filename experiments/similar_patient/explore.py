import csv
import json
import sys

csv.field_size_limit(sys.maxsize)

with open('/Users/xiaofanlu/Documents/github_repos/uncertainty-aware-reasoning-agent/experiments/similar_patient/mimiciv_single_diagnosis_nonoverlap_case_data.csv', 'r') as f:
    reader = csv.reader(f)
    header = next(reader)
    print("Columns:", header)
    
    row1 = next(reader)
    print("\nSample row:")
    for h, v in zip(header, row1):
        print(f"{h}:\n{v[:200]}...")

    # let's write a small counter for missing fields across all rows.
    # We are looking for "Demographics", "History", "Symptoms", etc. and "Physical_Examination_Findings" in SOME column.
    
    missing_history = 0
    missing_physical = 0
    missing_both = 0
    total = 0

    for row in reader:
        total += 1
        # It's likely these fields might be embedded in `case_study_json` if they exist, or maybe the row's `history_json` isn't the dictionary but the whole row has other structure.
        row_str = " ".join(row) # crude way
        
        has_history = "Demographics" in row_str and "History" in row_str and "Social_History" in row_str
        has_physical = "Physical_Examination_Findings" in row_str or "Vital_Signs" in row_str
        
        if not has_history:
            missing_history += 1
        if not has_physical:
            missing_physical += 1
        if not has_history and not has_physical:
            missing_both += 1
            
    print(f"\nTotal rows scanned (after header and 1st row): {total}")
    print(f"Missing history fields: {missing_history}")
    print(f"Missing physical fields: {missing_physical}")
    print(f"Missing both: {missing_both}")
