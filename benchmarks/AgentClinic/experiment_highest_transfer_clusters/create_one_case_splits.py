#!/usr/bin/env python3
"""
Create one-case-per-cluster train/test splits.
Takes exactly 2 unique cases from each cluster: 1 for train, 1 for test.
Skips clusters that don't have at least 2 cases.
"""
import json
from pathlib import Path

def main():
    # Directories
    script_dir = Path(__file__).parent
    clusters_dir = script_dir / "clusters"

    output_train = script_dir / "one_case_train.jsonl"
    output_test = script_dir / "one_case_test.jsonl"

    # Get all cluster JSON files
    cluster_files = sorted(clusters_dir.glob("cluster_*.json"))

    if not cluster_files:
        print("Error: No cluster files found in clusters/")
        return

    print("="*70)
    print("Creating One-Case-Per-Cluster Splits")
    print("="*70)
    print(f"Found {len(cluster_files)} cluster files\n")

    train_cases = []
    test_cases = []
    skipped_clusters = []

    for cluster_file in cluster_files:
        with open(cluster_file, 'r') as f:
            cluster_data = json.load(f)

        cluster_id = cluster_data['cluster_id']
        cluster_name = cluster_data['cluster_name']
        train_data = cluster_data.get('train_data', [])
        test_data = cluster_data.get('test_data', [])

        # Combine all cases and ensure we have at least 2
        all_cases = train_data + test_data

        if len(all_cases) < 2:
            skipped_clusters.append(f"Cluster {cluster_id} ({cluster_name})")
            print(f"Cluster {cluster_id:2d} ({cluster_name})")
            print(f"  ⚠ SKIPPED (only {len(all_cases)} case - need at least 2)")
            continue

        # Take first case for train, second for test
        train_cases.append(all_cases[0])
        test_cases.append(all_cases[1])

        print(f"Cluster {cluster_id:2d} ({cluster_name})")
        print(f"  Train: ✓  Test: ✓")

    # Write output files
    print(f"\n{'-'*70}")
    print("Writing output files...")

    with open(output_train, 'w') as f:
        for case in train_cases:
            f.write(json.dumps(case) + '\n')

    with open(output_test, 'w') as f:
        for case in test_cases:
            f.write(json.dumps(case) + '\n')

    print(f"✓ Train: {output_train} ({len(train_cases)} cases)")
    print(f"✓ Test:  {output_test} ({len(test_cases)} cases)")

    print(f"\n{'='*70}")
    print("SUMMARY")
    print("="*70)
    print(f"Total clusters found: {len(cluster_files)}")
    print(f"Clusters used: {len(train_cases)}")
    if skipped_clusters:
        print(f"Clusters skipped: {len(skipped_clusters)}")
        for skipped in skipped_clusters:
            print(f"  - {skipped}")
    print(f"\nTrain cases (1 per cluster): {len(train_cases)}")
    print(f"Test cases (1 per cluster): {len(test_cases)}")
    print(f"Total cases: {len(train_cases) + len(test_cases)}")
    print("="*70)

    # Verify uniqueness between train and test
    train_hashes = set()
    test_hashes = set()

    for case in train_cases:
        case_str = json.dumps(case, sort_keys=True)
        train_hashes.add(hash(case_str))

    for case in test_cases:
        case_str = json.dumps(case, sort_keys=True)
        test_hashes.add(hash(case_str))

    overlap = train_hashes & test_hashes
    if overlap:
        print(f"\n⚠ Warning: {len(overlap)} case(s) appear in both train and test!")
    else:
        print("\n✓ All cases are unique between train and test")

if __name__ == "__main__":
    main()
