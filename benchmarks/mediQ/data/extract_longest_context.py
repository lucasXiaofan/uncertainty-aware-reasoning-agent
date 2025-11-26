#!/usr/bin/env python3
"""
Extract the top 30 patients with the longest context from all_dev_good.jsonl
"""
import json
from pathlib import Path

def calculate_context_length(patient_data):
    """Calculate total context length for a patient"""
    context_length = 0

    # Add context field (list of context strings)
    if "context" in patient_data and isinstance(patient_data["context"], list):
        for ctx in patient_data["context"]:
            context_length += len(str(ctx))

    # Add facts field (list of fact strings)
    if "facts" in patient_data and isinstance(patient_data["facts"], list):
        for fact in patient_data["facts"]:
            context_length += len(str(fact))

    # Add question length
    if "question" in patient_data:
        context_length += len(str(patient_data["question"]))

    return context_length

def main():
    input_file = Path(__file__).parent / "all_dev_good.jsonl"
    output_file = Path(__file__).parent / "longest_context_top30.jsonl"

    print(f"Reading from: {input_file}")

    # Read all patients and calculate context lengths
    patients = []
    with open(input_file, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                patient = json.loads(line)
                context_len = calculate_context_length(patient)
                patients.append({
                    'data': patient,
                    'context_length': context_len,
                    'line_num': line_num,
                    'id': patient.get('id', f'unknown_{line_num}')
                })
            except json.JSONDecodeError as e:
                print(f"Error parsing line {line_num}: {e}")
                continue

    print(f"Total patients loaded: {len(patients)}")

    # Sort by context length (descending)
    patients.sort(key=lambda x: x['context_length'], reverse=True)

    # Get top 30
    top_30 = patients[:30]

    print(f"\nTop 30 patients with longest context:")
    for i, p in enumerate(top_30, 1):
        print(f"{i}. ID: {p['id']}, Context Length: {p['context_length']:,} chars, Line: {p['line_num']}")

    # Write to output file
    with open(output_file, 'w', encoding='utf-8') as f:
        for p in top_30:
            json.dump(p['data'], f, ensure_ascii=False)
            f.write('\n')

    print(f"\nTop 30 patients written to: {output_file}")
    print(f"Average context length: {sum(p['context_length'] for p in top_30) / len(top_30):,.0f} chars")
    print(f"Range: {top_30[-1]['context_length']:,} - {top_30[0]['context_length']:,} chars")

if __name__ == "__main__":
    main()
