import csv
import json
import sys
from collections import Counter

csv.field_size_limit(sys.maxsize)

tests_keys = set()
history_types = set()

with open('/Users/xiaofanlu/Documents/github_repos/uncertainty-aware-reasoning-agent/experiments/similar_patient/mimiciv_single_diagnosis_nonoverlap_case_data.csv', 'r') as f:
    reader = csv.DictReader(f)
    for i, row in enumerate(reader):
        try:
            tests = json.loads(row['tests_json'])
            tests_keys.update(tests.keys())
        except:
            pass
        
        try:
            hist = json.loads(row['history_json'])
            for h in hist:
                history_types.add(h)
        except:
            pass

print(f"Total rows: {i+1}")
print("\nUnique test keys (some):", sorted(list(tests_keys))[:50])
print("\nAny physical exam keys?", [k for k in tests_keys if 'palpation' in k.lower() or 'auscultation' in k.lower() or 'percussion' in k.lower() or 'murphy' in k.lower()])
print("Any vital signs keys?", [k for k in tests_keys if 'temperature' in k.lower() or 'heart rate' in k.lower() or 'respiratory' in k.lower()])
print("\nHistory content samples:", list(history_types)[:10])
