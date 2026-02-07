#!/usr/bin/env python3
"""Extract a single case from results file for re-running with uncertainty-aware doctor.

Usage:
    python extract_single_case.py <results_file> <scenario_id> [output_file]

Example:
    python extract_single_case.py results/one_case_train_openai_gpt-5-mini_20260128_191845.jsonl 0 single_case_scenario_0.jsonl
"""
import json
import sys
from pathlib import Path


def extract_case(results_file: str, scenario_id: int, output_file: str = None):
    """Extract a single case from results JSONL file."""
    results_path = Path(results_file)

    if not results_path.exists():
        print(f"Error: Results file not found: {results_file}")
        sys.exit(1)

    # Read all cases
    cases = []
    with open(results_path, 'r') as f:
        for line in f:
            if line.strip():
                case = json.loads(line)
                cases.append(case)

    # Find the case
    target_case = None
    for case in cases:
        if case.get('scenario_id') == scenario_id:
            target_case = case
            break

    if not target_case:
        print(f"Error: Scenario {scenario_id} not found in {results_file}")
        print(f"Available scenario IDs: {sorted(set(c['scenario_id'] for c in cases))}")
        sys.exit(1)

    # Extract the original problem_info (OSCE_Examination data)
    problem_info = target_case.get('problem_info', {})

    if not problem_info:
        print(f"Error: No problem_info found for scenario {scenario_id}")
        sys.exit(1)

    # Set output file
    if output_file is None:
        output_file = f"single_case_scenario_{scenario_id}.jsonl"

    output_path = Path(output_file)

    # Write the single case in AgentClinic format
    with open(output_path, 'w') as f:
        json.dump(problem_info, f)
        f.write('\n')

    print(f"Extracted scenario {scenario_id} to {output_path}")
    print(f"Correct diagnosis: {target_case.get('correct_diagnosis', 'Unknown')}")
    print(f"Model diagnosis: {target_case.get('model_diagnosis', 'Unknown')[:100]}...")
    print(f"Was correct: {target_case.get('correct', False)}")
    print(f"\nOriginal dialogue turns: {len(target_case.get('dialogue_history', []))}")

    return str(output_path)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    results_file = sys.argv[1]
    scenario_id = int(sys.argv[2])
    output_file = sys.argv[3] if len(sys.argv) > 3 else None

    extract_case(results_file, scenario_id, output_file)
