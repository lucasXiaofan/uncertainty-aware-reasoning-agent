#!/usr/bin/env python3
"""
Script to group patients by their final diagnosis (Correct_Diagnosis).
Creates separate JSONL files for each diagnosis with at least 2 patients.
Generates a report with statistics about the groupings.
"""

import json
import os
from collections import defaultdict
from pathlib import Path


def load_jsonl(file_path):
    """Load JSONL file and return list of records."""
    records = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def extract_diagnosis(record):
    """Extract the Correct_Diagnosis from a record."""
    try:
        return record['OSCE_Examination']['Correct_Diagnosis']
    except KeyError:
        return None


def deduplicate_records(records):
    """Remove duplicate records by comparing JSON serialization."""
    seen = set()
    unique_records = []
    duplicates_removed = 0

    for record in records:
        # Convert record to canonical JSON string for comparison
        record_str = json.dumps(record, sort_keys=True, ensure_ascii=False)

        if record_str not in seen:
            seen.add(record_str)
            unique_records.append(record)
        else:
            duplicates_removed += 1

    return unique_records, duplicates_removed


def group_patients_by_diagnosis(records):
    """Group patients by their Correct_Diagnosis."""
    diagnosis_groups = defaultdict(list)

    for record in records:
        diagnosis = extract_diagnosis(record)
        if diagnosis:
            diagnosis_groups[diagnosis].append(record)

    return diagnosis_groups


def sanitize_filename(diagnosis):
    """Convert diagnosis to a safe filename."""
    # Replace spaces and special characters
    safe_name = diagnosis.lower()
    safe_name = safe_name.replace(' ', '_')
    safe_name = safe_name.replace('(', '')
    safe_name = safe_name.replace(')', '')
    safe_name = safe_name.replace("'", '')
    safe_name = safe_name.replace(',', '')
    safe_name = safe_name.replace('.', '')
    safe_name = safe_name.replace('/', '_')
    return safe_name


def save_diagnosis_groups(diagnosis_groups, output_dir):
    """Save each diagnosis group to a separate JSONL file."""
    os.makedirs(output_dir, exist_ok=True)

    saved_files = []
    for diagnosis, patients in diagnosis_groups.items():
        if len(patients) >= 2:  # Only save if at least 2 patients
            filename = f"{sanitize_filename(diagnosis)}.jsonl"
            file_path = os.path.join(output_dir, filename)

            with open(file_path, 'w', encoding='utf-8') as f:
                for patient in patients:
                    f.write(json.dumps(patient, ensure_ascii=False) + '\n')

            saved_files.append((diagnosis, filename, len(patients)))

    return saved_files


def generate_report(diagnosis_groups, saved_files, output_dir, duplicates_removed=0):
    """Generate a report about the diagnosis groupings."""
    report_path = os.path.join(output_dir, 'diagnosis_grouping_report.txt')

    # Sort by number of patients (descending)
    sorted_groups = sorted(diagnosis_groups.items(), key=lambda x: len(x[1]), reverse=True)

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + '\n')
        f.write("PATIENT GROUPING BY DIAGNOSIS REPORT\n")
        f.write("=" * 80 + '\n\n')

        # Summary statistics
        total_diagnoses = len(diagnosis_groups)
        diagnoses_with_2plus = len([d for d, patients in diagnosis_groups.items() if len(patients) >= 2])
        total_patients = sum(len(patients) for patients in diagnosis_groups.values())

        f.write("SUMMARY STATISTICS\n")
        f.write("-" * 80 + '\n')
        f.write(f"Total unique diagnoses: {total_diagnoses}\n")
        f.write(f"Diagnoses with 2+ patients: {diagnoses_with_2plus}\n")
        f.write(f"Diagnoses with only 1 patient: {total_diagnoses - diagnoses_with_2plus}\n")
        f.write(f"Total unique patients: {total_patients}\n")
        f.write(f"Duplicate patients removed: {duplicates_removed}\n")
        f.write(f"JSONL files created: {len(saved_files)}\n\n")

        # Ranking of diagnoses with 2+ patients
        f.write("RANKING OF DIAGNOSES WITH 2+ PATIENTS\n")
        f.write("-" * 80 + '\n')
        f.write(f"{'Rank':<6} {'Count':<8} {'Diagnosis'}\n")
        f.write("-" * 80 + '\n')

        rank = 1
        for diagnosis, patients in sorted_groups:
            if len(patients) >= 2:
                f.write(f"{rank:<6} {len(patients):<8} {diagnosis}\n")
                rank += 1

        # All diagnoses (including single patient)
        f.write("\n\nCOMPLETE DIAGNOSIS LIST (ALL)\n")
        f.write("-" * 80 + '\n')
        f.write(f"{'Count':<8} {'Diagnosis'}\n")
        f.write("-" * 80 + '\n')

        for diagnosis, patients in sorted_groups:
            f.write(f"{len(patients):<8} {diagnosis}\n")

        # Files created
        f.write("\n\nFILES CREATED\n")
        f.write("-" * 80 + '\n')
        for diagnosis, filename, count in saved_files:
            f.write(f"{filename}\n")
            f.write(f"  Diagnosis: {diagnosis}\n")
            f.write(f"  Patients: {count}\n\n")

    return report_path


def main():
    # File paths
    base_dir = Path(__file__).parent
    file1 = base_dir / 'agentclinic_medqa.jsonl'
    file2 = base_dir / 'agentclinic_medqa_extended.jsonl'
    output_dir = base_dir / 'similar_patient_medqa'

    print("Loading patient data...")
    all_records = []

    # Load first file if exists
    if file1.exists():
        records1 = load_jsonl(file1)
        all_records.extend(records1)
        print(f"Loaded {len(records1)} patients from {file1.name}")
    else:
        print(f"Warning: {file1} not found")

    # Load second file if exists
    if file2.exists():
        records2 = load_jsonl(file2)
        all_records.extend(records2)
        print(f"Loaded {len(records2)} patients from {file2.name}")
    else:
        print(f"Warning: {file2} not found")

    print(f"\nTotal patients loaded: {len(all_records)}")

    # Deduplicate records
    print("\nRemoving duplicate patients...")
    all_records, duplicates_removed = deduplicate_records(all_records)
    print(f"Removed {duplicates_removed} duplicate patients")
    print(f"Unique patients remaining: {len(all_records)}")

    # Group by diagnosis
    print("\nGrouping patients by diagnosis...")
    diagnosis_groups = group_patients_by_diagnosis(all_records)
    print(f"Found {len(diagnosis_groups)} unique diagnoses")

    # Save groups with 2+ patients
    print(f"\nSaving diagnosis groups to {output_dir}...")
    saved_files = save_diagnosis_groups(diagnosis_groups, output_dir)
    print(f"Created {len(saved_files)} JSONL files (diagnoses with 2+ patients)")

    # Generate report
    print("\nGenerating report...")
    report_path = generate_report(diagnosis_groups, saved_files, output_dir, duplicates_removed)
    print(f"Report saved to: {report_path}")

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total unique patients: {len(all_records)}")
    print(f"Duplicate patients removed: {duplicates_removed}")
    print(f"Total unique diagnoses: {len(diagnosis_groups)}")
    print(f"Diagnoses with 2+ patients: {len(saved_files)}")
    print(f"Output directory: {output_dir}")
    print(f"Report: {report_path}")
    print("=" * 80)


if __name__ == '__main__':
    main()
