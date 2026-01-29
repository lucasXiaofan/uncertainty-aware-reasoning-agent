#!/usr/bin/env python3
"""
Script to create train/test splits for high transfer clusters from AgentClinic data.
Filters clusters with transfer_rate >= 80% and creates 50/50 train/test splits.
"""
import json
import os
import re
import random
from pathlib import Path

# Define paths
BASE_DIR = Path("/Users/xiaofanlu/Documents/github_repos/uncertainty-aware-reasoning-agent/benchmarks/AgentClinic")
CLUSTER_FILE = BASE_DIR / "simiar_patient_cluster.json"
MEDQA_FILE = BASE_DIR / "agentclinic_medqa_extended.jsonl"
OUTPUT_DIR = BASE_DIR / "highest_transfer_clusters"

# Transfer rate threshold
TRANSFER_RATE_THRESHOLD = 80

def parse_transfer_rate(rate_str):
    """Extract numeric transfer rate from string like '~95%' or '~80% (context-dependent)'"""
    match = re.search(r'(\d+)%', rate_str)
    if match:
        return float(match.group(1))
    return 0.0

def load_cluster_data():
    """Load cluster data and filter by transfer rate threshold."""
    with open(CLUSTER_FILE, 'r') as f:
        cluster_data = json.load(f)

    # Filter clusters by transfer rate >= threshold
    high_transfer_clusters = []
    cluster_to_diseases = {}

    for cluster in cluster_data['clusters']:
        transfer_rate_str = cluster['shared_diagnostic_path']['transfer_rate']
        transfer_rate = parse_transfer_rate(transfer_rate_str)

        if transfer_rate >= TRANSFER_RATE_THRESHOLD:
            # Normalize disease names to lowercase for matching
            diseases = [d.lower() for d in cluster['diseases']]
            cluster_key = f"{cluster['name']} ({transfer_rate_str})"

            cluster_to_diseases[cluster_key] = {
                'diseases': diseases,
                'cluster_name': cluster['name'],
                'cluster_id': cluster['cluster_id'],
                'transfer_rate': transfer_rate,
                'full_cluster_info': cluster
            }
            high_transfer_clusters.append(cluster_key)

    print(f"Found {len(high_transfer_clusters)} clusters with transfer_rate >= {TRANSFER_RATE_THRESHOLD}%:")
    for cluster_key in sorted(high_transfer_clusters):
        info = cluster_to_diseases[cluster_key]
        print(f"  - {cluster_key}")

    return cluster_to_diseases, high_transfer_clusters

def load_medqa_cases():
    """Load all cases from JSONL file."""
    cases = []
    with open(MEDQA_FILE, 'r') as f:
        for line in f:
            if line.strip():
                cases.append(json.loads(line))
    return cases

def organize_cases_by_cluster(cases, cluster_to_diseases, high_transfer_clusters):
    """Organize cases by cluster based on diagnosis."""
    cluster_cases = {cluster: [] for cluster in high_transfer_clusters}

    for case in cases:
        diagnosis = case['OSCE_Examination']['Correct_Diagnosis'].lower()

        # Check which cluster this diagnosis belongs to
        for cluster_name, cluster_info in cluster_to_diseases.items():
            if diagnosis in cluster_info['diseases']:
                cluster_cases[cluster_name].append(case)
                break

    return cluster_cases

def create_train_test_split(cases):
    """Split cases evenly into train and test sets."""
    # Shuffle cases for random split
    import random
    random.seed(42)  # For reproducibility
    shuffled_cases = cases.copy()
    random.shuffle(shuffled_cases)

    # Split 50/50
    mid_point = len(shuffled_cases) // 2
    train_cases = shuffled_cases[:mid_point]
    test_cases = shuffled_cases[mid_point:]

    return train_cases, test_cases

def write_jsonl(cases, filepath):
    """Write cases to JSONL file."""
    with open(filepath, 'w') as f:
        for case in cases:
            f.write(json.dumps(case) + '\n')

def main():
    """Main function to process and create cluster files."""
    print("="*70)
    print("Creating Train/Test Splits for High Transfer Rate Clusters")
    print(f"Transfer Rate Threshold: >= {TRANSFER_RATE_THRESHOLD}%")
    print("="*70)

    print("\nLoading cluster data...")
    cluster_to_diseases, high_transfer_clusters = load_cluster_data()

    print("\nLoading MedQA cases...")
    all_cases = load_medqa_cases()
    print(f"Total cases loaded: {len(all_cases)}")

    print("\nOrganizing cases by cluster...")
    cluster_cases = organize_cases_by_cluster(all_cases, cluster_to_diseases, high_transfer_clusters)

    # Create output directory
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Combine all cases and create single train/test split
    all_train_cases = []
    all_test_cases = []

    # Create comprehensive output with all cluster information
    output_data = {
        'metadata': {
            'description': f'High-transfer-rate clusters (>= {TRANSFER_RATE_THRESHOLD}%) with train/test splits',
            'transfer_rate_threshold': TRANSFER_RATE_THRESHOLD,
            'split_ratio': '50% train / 50% test',
            'total_clusters': 0,
            'total_cases': 0,
            'total_train_cases': 0,
            'total_test_cases': 0
        },
        'clusters': []
    }

    print("\nProcessing clusters:")
    print("-"*70)

    for cluster_name, cases in cluster_cases.items():
        if len(cases) == 0:
            print(f"\n{cluster_name}: No cases found (skipping)")
            continue

        cluster_info = cluster_to_diseases[cluster_name]
        clean_name = cluster_info['cluster_name'].replace(' ', '_').replace('/', '_')

        print(f"\n{cluster_name}")
        print(f"  Total cases: {len(cases)}")

        # Create train/test split for this cluster
        train_cases, test_cases = create_train_test_split(cases)
        all_train_cases.extend(train_cases)
        all_test_cases.extend(test_cases)

        print(f"  Train: {len(train_cases)} cases")
        print(f"  Test: {len(test_cases)} cases")

        # Save individual cluster file with full information
        cluster_output = {
            'cluster_id': cluster_info['cluster_id'],
            'cluster_name': cluster_info['cluster_name'],
            'transfer_rate': cluster_info['full_cluster_info']['shared_diagnostic_path']['transfer_rate'],
            'diseases': cluster_info['full_cluster_info']['diseases'],
            'transfer_requirements': cluster_info['full_cluster_info']['transfer_requirements'],
            'shared_diagnostic_path': cluster_info['full_cluster_info']['shared_diagnostic_path'],
            'total_cases': len(cases),
            'train_cases_count': len(train_cases),
            'test_cases_count': len(test_cases),
            'train_data': train_cases,
            'test_data': test_cases
        }

        # Save individual cluster JSON file
        cluster_file = OUTPUT_DIR / f"cluster_{cluster_info['cluster_id']:02d}_{clean_name}.json"
        with open(cluster_file, 'w') as f:
            json.dump(cluster_output, f, indent=2)
        print(f"  Saved: {cluster_file.name}")

        # Add to combined output
        output_data['clusters'].append(cluster_output)

    # Update metadata
    output_data['metadata']['total_clusters'] = len(output_data['clusters'])
    output_data['metadata']['total_cases'] = len(all_train_cases) + len(all_test_cases)
    output_data['metadata']['total_train_cases'] = len(all_train_cases)
    output_data['metadata']['total_test_cases'] = len(all_test_cases)

    # Save combined JSON file with all clusters
    combined_file = OUTPUT_DIR / "all_high_transfer_clusters_with_splits.json"
    with open(combined_file, 'w') as f:
        json.dump(output_data, f, indent=2)

    # Write combined train and test JSONL files
    train_file = OUTPUT_DIR / "train.jsonl"
    test_file = OUTPUT_DIR / "test.jsonl"

    write_jsonl(all_train_cases, train_file)
    write_jsonl(all_test_cases, test_file)

    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"Total high-transfer clusters: {len(output_data['clusters'])}")
    print(f"Total cases: {output_data['metadata']['total_cases']}")
    print(f"  Train cases: {len(all_train_cases)}")
    print(f"  Test cases: {len(all_test_cases)}")
    print(f"\nOutput directory: {OUTPUT_DIR}")
    print(f"\nFiles created:")
    print(f"  - {combined_file.name} (all clusters with full data)")
    print(f"  - train.jsonl ({len(all_train_cases)} cases)")
    print(f"  - test.jsonl ({len(all_test_cases)} cases)")
    print(f"  - {len(output_data['clusters'])} individual cluster JSON files")
    print("="*70)

if __name__ == "__main__":
    main()
