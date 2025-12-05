import json
import argparse
import os
import re

def get_steps(data):
    sys_data = data.get('interactive_system', {})
    steps = []
    if 'steps' in sys_data:
        steps.extend(sys_data['steps'])
    if 'temp_additional_info' in sys_data:
        for item in sys_data['temp_additional_info']:
            if 'trajectory' in item:
                steps.extend(item['trajectory'])
    return steps

def analyze_differential(input_file, output_file=None):
    entries = []
    try:
        with open(input_file, 'r') as f:
            for line in f:
                if line.strip():
                    entries.append(json.loads(line))
    except FileNotFoundError:
        print(f"Error: Input file '{input_file}' not found.")
        return

    analysis_lines = []
    def p(text=""):
        analysis_lines.append(text)

    p("## Differential Agent Accuracy Analysis\n")
    p("This section analyzes whether the Differential Agent correctly kept the true answer in the options or incorrectly ruled it out.\n")
    p("| ID | Correct Answer | Differential Status | Final Decision | Result | Notes |")
    p("|---|---|---|---|---|---|")

    stats = {
        "total": 0,
        "correct_kept": 0,
        "correct_ruled_out": 0,
        "decision_correct_when_kept": 0,
        "decision_correct_when_ruled_out": 0,
        "decision_wrong_when_kept": 0,
        "decision_wrong_when_ruled_out": 0
    }

    for data in entries:
        stats["total"] += 1
        entry_id = data.get('id', 'N/A')
        info = data.get('info', {})
        correct_idx = info.get('correct_answer_idx')
        
        steps = get_steps(data)
        
        # Find the last submit_differential call
        last_diff_step = None
        for step in steps:
            if step.get('tool') == 'submit_differential':
                last_diff_step = step
        
        diff_status = "N/A"
        notes = ""
        
        if last_diff_step:
            args = last_diff_step.get('args', {})
            updated_options = args.get('current_differential_options', args.get('updated_options', ""))
            
            # Heuristic to check if correct_idx is in updated_options
            # Check for "A:", "A)", "Option A", or just the letter if it's a list
            # Also check for "None" or "All"
            
            is_kept = False
            
            if "None of the provided" in updated_options or "None of the above" in updated_options:
                is_kept = False
                notes = "Explicitly ruled out all"
            else:
                # Stricter check for the index
                # Matches: "A:", "A)", "A.", "Option A", "Choice A"
                # Or if the string is exactly "A"
                # Or if the string contains the full correct answer text (if available, but here we use idx)
                
                pattern = rf"(?i)\b(Option|Choice)?\s*{correct_idx}\s*[:.)]"
                
                if re.search(pattern, updated_options):
                    is_kept = True
                elif updated_options.strip() == correct_idx:
                    is_kept = True
                elif f" {correct_idx} " in updated_options: # " A "
                     # Still risky, " A " could be " A patient..."
                     # Let's avoid this unless we are desperate.
                     is_kept = False
                else:
                    # Check rule_out_criteria for explicit rule out
                    rule_out = args.get('rule_out_criteria', "")
                    if re.search(rf"(?i)(Option|Choice)?\s*{correct_idx}\s*[:.)]?\s*ruled out", rule_out) or \
                       re.search(rf"(?i){correct_idx}\s*\(.*ruled out", rule_out):
                        is_kept = False
                        notes = "Explicitly ruled out in criteria"
                    else:
                        # If we can't find the index in a structured way, assume it's NOT kept
                        # UNLESS the updated_options is very short (likely a list like "A, B")
                        if len(updated_options) < 20 and correct_idx in updated_options:
                            is_kept = True
                        else:
                            is_kept = False
            
            if is_kept:
                diff_status = "Kept Correct"
                stats["correct_kept"] += 1
            else:
                diff_status = "Ruled Out Correct"
                stats["correct_ruled_out"] += 1
        else:
            diff_status = "No Differential Step"
            # If no differential step, effectively "Kept" (didn't rule out anything)
            # Or "N/A"
            pass

        # Final Decision
        sys_data = data.get('interactive_system', {})
        final_correct = sys_data.get('correct', False)
        final_res = "Correct" if final_correct else "Wrong"
        
        if diff_status == "Kept Correct":
            if final_correct:
                stats["decision_correct_when_kept"] += 1
            else:
                stats["decision_wrong_when_kept"] += 1
        elif diff_status == "Ruled Out Correct":
            if final_correct:
                stats["decision_correct_when_ruled_out"] += 1
                notes += " (Recovered)"
            else:
                stats["decision_wrong_when_ruled_out"] += 1
        
        p(f"| {entry_id} | {correct_idx} | {diff_status} | {final_res} | {final_res} | {notes} |")

    p(f"\n**Summary**:")
    p(f"- Total Cases: {stats['total']}")
    p(f"- Differential Kept Correct Answer: {stats['correct_kept']} ({stats['correct_kept']/stats['total']*100:.1f}%)")
    p(f"- Differential Ruled Out Correct Answer: {stats['correct_ruled_out']} ({stats['correct_ruled_out']/stats['total']*100:.1f}%)")
    p(f"- Decision Correct when Differential Kept: {stats['decision_correct_when_kept']}")
    p(f"- Decision Wrong when Differential Kept: {stats['decision_wrong_when_kept']}")
    p(f"- Decision Correct when Differential Ruled Out: {stats['decision_correct_when_ruled_out']} (Recovery)")
    p(f"- Decision Wrong when Differential Ruled Out: {stats['decision_wrong_when_ruled_out']} (Propagated Error)")

    report_content = "\n".join(analysis_lines)
    
    if output_file:
        # Append to existing file if it exists, or create new
        mode = 'a' if os.path.exists(output_file) else 'w'
        with open(output_file, mode) as f:
            f.write("\n\n" + report_content)
        print(f"Report appended to {output_file}")
    else:
        print(report_content)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('input_file')
    parser.add_argument('--output')
    args = parser.parse_args()
    analyze_differential(args.input_file, args.output)
