#!/usr/bin/env python3
"""Extract failed cases from results files into separate JSONL datasets.

Usage:
    python extract_failed_cases.py <results_file> <output_file>

Example:
    python extract_failed_cases.py results/one_case_test_openai_gpt-5-mini_20260128_184655.jsonl failed_test.jsonl
    python extract_failed_cases.py results/one_case_train_openai_gpt-5-mini_20260128_191845.jsonl failed_train.jsonl
"""
import json
import sys
from pathlib import Path


def extract_failed_cases(results_file: str, output_file: str) -> int:
    """Extract failed cases from results file.

    Args:
        results_file: Path to the results JSONL file
        output_file: Path to save the failed cases dataset

    Returns:
        Number of failed cases extracted
    """
    failed_cases = []
    total = 0

    with open(results_file, 'r') as f:
        for line in f:
            if not line.strip():
                continue
            case = json.loads(line)
            total += 1

            # Check if case failed
            if not case.get('correct', False):
                # Extract the original problem_info for re-running
                problem_info = case.get('problem_info', {})
                scenario_id = case.get('scenario_id')

                # Create dataset entry matching agentclinic_medqa_extended.jsonl format
                dataset_entry = {
                    'scenario_id': scenario_id,
                    'OSCE_Examination': problem_info.get('OSCE_Examination', {}),
                    # Include original result info for reference
                    '_original_model_diagnosis': case.get('model_diagnosis', ''),
                    '_original_correct': case.get('correct', False)
                }
                failed_cases.append(dataset_entry)

    # Write failed cases to output file
    with open(output_file, 'w') as f:
        for case in failed_cases:
            f.write(json.dumps(case, ensure_ascii=False) + '\n')

    print(f"Total cases: {total}")
    print(f"Failed cases: {len(failed_cases)}")
    print(f"Saved to: {output_file}")
    print()
    print("Failed scenario IDs:")
    for case in failed_cases:
        actual = case.get('OSCE_Examination', {}).get('Correct_Diagnosis', 'Unknown')
        print(f"  {case['scenario_id']}: {actual}")

    return len(failed_cases)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    results_file = sys.argv[1]
    output_file = sys.argv[2]

    if not Path(results_file).exists():
        print(f"Error: Results file not found: {results_file}")
        sys.exit(1)

    extract_failed_cases(results_file, output_file)


if __name__ == "__main__":
    main()
