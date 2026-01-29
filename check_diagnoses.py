#!/usr/bin/env python3
"""
Script to check what diagnoses are in the medqa file.
"""
import json
from pathlib import Path
from collections import Counter

# Define paths
BASE_DIR = Path("/Users/xiaofanlu/Documents/github_repos/uncertainty-aware-reasoning-agent/benchmarks/AgentClinic")
MEDQA_FILE = BASE_DIR / "agentclinic_medqa_extended.jsonl"
CLUSTER_FILE = BASE_DIR / "simiar_patient_cluster.json"

# Load all diagnoses
diagnoses = []
with open(MEDQA_FILE, 'r') as f:
    for line in f:
        if line.strip():
            case = json.loads(line)
            diagnoses.append(case['OSCE_Examination']['Correct_Diagnosis'])

# Count diagnoses
diagnosis_counts = Counter(diagnoses)

print("All unique diagnoses in medqa file:")
print("=" * 80)
for diag, count in sorted(diagnosis_counts.items()):
    print(f"{diag}: {count}")

print("\n\nNow checking cluster diseases:")
print("=" * 80)
with open(CLUSTER_FILE, 'r') as f:
    cluster_data = json.load(f)

# Focus on the 6 highest transfer clusters
HIGHEST_TRANSFER = [
    "Acute Leukemia Workup",
    "Inherited Bleeding Disorders",
    "Pediatric Viral Exanthems",
    "Autoimmune Blistering Diseases",
    "Syncope Workup",
    "Neonatal Respiratory Distress"
]

for cluster in cluster_data['clusters']:
    if cluster['name'] in HIGHEST_TRANSFER:
        print(f"\n{cluster['name']} ({cluster['shared_diagnostic_path']['transfer_rate']}):")
        for disease in cluster['diseases']:
            # Check if this disease appears in diagnoses (case-insensitive)
            found = False
            for actual_diag in diagnosis_counts.keys():
                if disease.lower() == actual_diag.lower():
                    print(f"  ✓ {disease} -> Found as '{actual_diag}' ({diagnosis_counts[actual_diag]} cases)")
                    found = True
                    break
            if not found:
                # Try partial match
                partial_matches = [d for d in diagnosis_counts.keys() if disease.lower() in d.lower() or d.lower() in disease.lower()]
                if partial_matches:
                    print(f"  ~ {disease} -> Possible matches: {partial_matches}")
                else:
                    print(f"  ✗ {disease} -> NOT FOUND")
