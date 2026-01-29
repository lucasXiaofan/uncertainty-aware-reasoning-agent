#!/usr/bin/env python3
"""
Check for duplicate cases in train and test sets.
"""
import json
import hashlib
from pathlib import Path

def get_case_hash(case):
    """Create a unique hash for a case based on its content."""
    # Use the entire case content to create a hash
    case_str = json.dumps(case, sort_keys=True)
    return hashlib.md5(case_str.encode()).hexdigest()

def load_jsonl(filepath):
    """Load cases from JSONL file."""
    cases = []
    with open(filepath, 'r') as f:
        for line in f:
            if line.strip():
                cases.append(json.loads(line))
    return cases

def check_duplicates(cases, set_name):
    """Check for duplicates within a set."""
    case_hashes = {}
    duplicates = []

    for idx, case in enumerate(cases):
        case_hash = get_case_hash(case)
        if case_hash in case_hashes:
            duplicates.append({
                'first_index': case_hashes[case_hash],
                'duplicate_index': idx,
                'diagnosis': case['OSCE_Examination']['Correct_Diagnosis']
            })
        else:
            case_hashes[case_hash] = idx

    print(f"\n{set_name}:")
    print(f"  Total cases: {len(cases)}")
    print(f"  Unique cases: {len(case_hashes)}")

    if duplicates:
        print(f"  ❌ Found {len(duplicates)} duplicate(s):")
        for dup in duplicates:
            print(f"     - Case {dup['duplicate_index']} is duplicate of case {dup['first_index']} (Diagnosis: {dup['diagnosis']})")
    else:
        print(f"  ✓ No duplicates found")

    return case_hashes

def check_overlap(train_hashes, test_hashes, train_cases, test_cases):
    """Check for overlap between train and test sets."""
    overlap = set(train_hashes.keys()) & set(test_hashes.keys())

    print(f"\nOverlap between Train and Test:")
    if overlap:
        print(f"  ❌ Found {len(overlap)} case(s) in both sets:")
        for case_hash in overlap:
            train_idx = train_hashes[case_hash]
            test_idx = test_hashes[case_hash]
            diagnosis = train_cases[train_idx]['OSCE_Examination']['Correct_Diagnosis']
            print(f"     - Train[{train_idx}] = Test[{test_idx}] (Diagnosis: {diagnosis})")
    else:
        print(f"  ✓ No overlap - all cases are unique between train and test")

def main():
    base_dir = Path("/Users/xiaofanlu/Documents/github_repos/uncertainty-aware-reasoning-agent/benchmarks/AgentClinic/highest_transfer_clusters")

    train_file = base_dir / "train.jsonl"
    test_file = base_dir / "test.jsonl"

    print("="*70)
    print("Checking for Duplicate Cases")
    print("="*70)

    # Load data
    print("\nLoading data...")
    train_cases = load_jsonl(train_file)
    test_cases = load_jsonl(test_file)

    # Check for duplicates within each set
    train_hashes = check_duplicates(train_cases, "Train Set")
    test_hashes = check_duplicates(test_cases, "Test Set")

    # Check for overlap between sets
    check_overlap(train_hashes, test_hashes, train_cases, test_cases)

    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    total_unique = len(set(train_hashes.keys()) | set(test_hashes.keys()))
    total_cases = len(train_cases) + len(test_cases)
    print(f"Total cases (train + test): {total_cases}")
    print(f"Total unique cases: {total_unique}")

    if total_unique == total_cases:
        print("✓ All cases are unique!")
    else:
        print(f"❌ Found {total_cases - total_unique} duplicate(s)")
    print("="*70)

if __name__ == "__main__":
    main()
