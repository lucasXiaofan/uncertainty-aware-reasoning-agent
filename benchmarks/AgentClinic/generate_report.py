import json
import argparse
import sys
import os
from pathlib import Path

def generate_report(file_path):
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
        return

    total_cases = 0
    correct_cases = 0
    results = []

    report_lines = []
    
    def log(msg):
        print(msg)
        report_lines.append(msg)

    log(f"Report for: {file_path}")
    log("-" * 100)
    log(f"{'Dataset':<15} | {'ID':<4} | {'Correct?':<10} | {'Correct Diagnosis':<30} | {'Model Diagnosis'}")
    log("-" * 100)

    for line in lines:
        try:
            data = json.loads(line)
            dataset = data.get("dataset", "Unknown")
            scenario_id = data.get("scenario_id", "N/A")
            correct = data.get("correct", False)
            correct_diag = data.get("correct_diagnosis", "N/A")
            model_diag = data.get("model_diagnosis", "N/A")
            
            total_cases += 1
            if correct:
                correct_cases += 1
            
            # Truncate for the one-line summary
            short_model_diag = (model_diag[:42] + '...') if len(model_diag) > 45 else model_diag
            short_correct_diag = (correct_diag[:27] + '...') if len(correct_diag) > 30 else correct_diag
            
            log(f"{dataset:<15} | {str(scenario_id):<4} | {str(correct):<10} | {short_correct_diag:<30} | {short_model_diag}")

            results.append({
                "dataset": dataset,
                "scenario_id": scenario_id,
                "correct": correct,
                "correct_diagnosis": correct_diag,
                "model_diagnosis": model_diag
            })
            
        except json.JSONDecodeError:
            log("Error decoding JSON line")
            continue

    accuracy = (correct_cases / total_cases) * 100 if total_cases > 0 else 0
    
    log("-" * 100)
    log(f"Total Cases: {total_cases}")
    log(f"Correct:     {correct_cases}")
    log(f"Accuracy:    {accuracy:.2f}%")
    log("=" * 100)
    
    log("\nDetailed Diagnoses:")
    for res in results:
        status = "✅ CORRECT" if res['correct'] else "❌ INCORRECT"
        log(f"\n[{res['dataset']} ID: {res['scenario_id']}] {status}")
        log(f"Correct Diagnosis: {res['correct_diagnosis']}")
        log(f"Model Diagnosis:   {res['model_diagnosis']}")
        log("-" * 40)


    # Save to results folder
    try:
        results_dir = Path("results")
        results_dir.mkdir(exist_ok=True)
        
        base_name = Path(file_path).stem
        report_file = results_dir / f"report_{base_name}.txt"
        
        with open(report_file, 'w') as f:
            f.write("\n".join(report_lines))
        print(f"\nReport also saved to: {report_file}")
    except Exception as e:
        print(f"Error saving report to file: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate accuracy report from AgentClinic benchmark JSONL results.")
    parser.add_argument("file_path", help="Path to the .jsonl results file")
    args = parser.parse_args()

    generate_report(args.file_path)
