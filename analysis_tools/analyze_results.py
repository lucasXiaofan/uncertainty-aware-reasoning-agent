import json
import difflib
import argparse
import sys
import os

def check_redundancy(questions, threshold=0.85):
    """
    Identifies redundant questions based on sequence matching ratio.
    """
    redundant_indices = []
    seen = []
    for i, q in enumerate(questions):
        is_redundant = False
        for s in seen:
            # Check for high similarity
            if difflib.SequenceMatcher(None, q, s).ratio() > threshold:
                is_redundant = True
                break
        if is_redundant:
            redundant_indices.append(i)
        seen.append(q)
    return redundant_indices

def analyze_trajectory(choices, correct_idx):
    """
    Analyzes how the agent's choice changed over time.
    """
    if not choices:
        return "No choices"
    
    first_correct = choices[0] == correct_idx
    final_correct = choices[-1] == correct_idx
    
    if first_correct and final_correct:
        return "Stable Correct"
    elif not first_correct and not final_correct:
        return "Stable Wrong"
    elif not first_correct and final_correct:
        return "Improved (Wrong -> Correct)"
    elif first_correct and not final_correct:
        return "Degraded (Correct -> Wrong)"
    return "Fluctuating"

def generate_report(input_file, summary_file=None, output_file=None):
    """
    Generates a markdown report from the result jsonl file.
    """
    
    entries = []
    try:
        with open(input_file, 'r') as f:
            for line in f:
                if line.strip():
                    entries.append(json.loads(line))
    except FileNotFoundError:
        print(f"Error: Input file '{input_file}' not found.")
        return

    # Prepare output buffer
    output_lines = []
    def p(text=""):
        output_lines.append(text)

    p("# Analysis Report")
    p(f"**Input File**: `{os.path.basename(input_file)}`")
    if summary_file:
        p(f"**Summary File**: `{os.path.basename(summary_file)}`")
    p("")
    
    # --- Section 1: Question Asking Quality ---
    p("## 1. Question Asking Quality\n")
    
    total_questions = 0
    total_redundant = 0
    total_failed = 0
    
    p("| ID | Total Qs | Redundant Qs | Failed Qs (No Info) | Proactive? | Note |")
    p("|---|---|---|---|---|---|")
    
    for data in entries:
        # Handle cases where interactive_system might be missing or different structure
        if 'interactive_system' not in data:
            continue
            
        sys_data = data['interactive_system']
        q_list = sys_data.get('questions', [])
        a_list = sys_data.get('answers', [])
        
        # Redundancy
        redundant_idxs = check_redundancy(q_list)
        num_redundant = len(redundant_idxs)
        
        # Failed (Patient cannot answer)
        # We look for specific phrases indicating failure to retrieve info
        num_failed = sum(1 for a in a_list if "cannot answer" in a or "I don't know" in a)
        
        total_questions += len(q_list)
        total_redundant += num_redundant
        total_failed += num_failed
        
        is_proactive = len(q_list) > 0
        
        note = ""
        if not is_proactive:
            if sys_data.get('correct'):
                note = "No questions asked, but correct (Initial context likely sufficient)"
            else:
                note = "No questions asked, and incorrect (Premature decision)"
        
        p(f"| {data.get('id', 'N/A')} | {len(q_list)} | {num_redundant} | {num_failed} | {is_proactive} | {note} |")

    p(f"\n**Summary**:")
    p(f"- Total Questions: {total_questions}")
    if total_questions > 0:
        p(f"- Redundant Questions: {total_redundant} ({total_redundant/total_questions*100:.1f}%)")
        p(f"- Failed Questions (No Info): {total_failed} ({total_failed/total_questions*100:.1f}%)")
    else:
        p("- Redundant Questions: 0")
        p("- Failed Questions: 0")
    
    # --- Section 2: Decision Ability & Context Usage ---
    p("\n## 2. Decision Ability & Context Usage\n")
    
    p("| ID | Context % | Trajectory | Final Result | Total Qs | Valid Qs | Input Tokens | Output Tokens |")
    p("|---|---|---|---|---|---|---|---|")
    
    total_input_tokens = 0
    total_output_tokens = 0
    
    for data in entries:
        if 'interactive_system' not in data or 'info' not in data:
            continue
            
        sys_data = data['interactive_system']
        info_data = data['info']
        
        # Questions stats for this section
        q_list = sys_data.get('questions', [])
        a_list = sys_data.get('answers', [])
        num_qs = len(q_list)
        num_failed = sum(1 for a in a_list if "cannot answer" in a or "I don't know" in a)
        num_valid_qs = num_qs - num_failed

        # Context Calculation
        initial_info = info_data.get('initial_info', "")
        # Filter out "cannot answer" responses for context calculation
        valid_answers = [a for a in sys_data.get('answers', []) if "cannot answer" not in a]
        patient_response_context = " ".join(valid_answers)
        
        context_have = initial_info + " " + patient_response_context
        total_context_list = info_data.get('context', [])
        total_context_str = " ".join(total_context_list) if isinstance(total_context_list, list) else str(total_context_list)
        
        # Simple char length ratio
        pct = (len(context_have) / len(total_context_str)) * 100 if total_context_str else 0
        if pct > 100: pct = 100 
        
        # Trajectory
        choices = sys_data.get('intermediate_choices', [])
        correct_idx = info_data.get('correct_answer_idx')
        traj_str = analyze_trajectory(choices, correct_idx)
        
        final_res = "Correct" if sys_data.get('correct') else "Wrong"
        
        # Tokens
        input_tok = 0
        output_tok = 0
        if 'temp_additional_info' in sys_data:
            for item in sys_data['temp_additional_info']:
                if 'usage' in item:
                    input_tok += item['usage'].get('input_tokens', 0)
                    output_tok += item['usage'].get('output_tokens', 0)
        
        total_input_tokens += input_tok
        total_output_tokens += output_tok
        
        p(f"| {data.get('id', 'N/A')} | {pct:.1f}% | {traj_str} | {final_res} | {num_qs} | {num_valid_qs} | {input_tok} | {output_tok} |")

    p(f"\n**Token Usage Summary**:")
    p(f"- Total Input Tokens: {total_input_tokens}")
    p(f"- Total Output Tokens: {total_output_tokens}")
    
    # --- Output ---
    report_content = "\n".join(output_lines)
    
    if output_file:
        with open(output_file, 'w') as f:
            f.write(report_content)
        print(f"Report written to {output_file}")
    else:
        print(report_content)

def main():
    parser = argparse.ArgumentParser(description="Analyze agent reasoning logs.")
    parser.add_argument('input_file', help="Path to the .jsonl results file")
    parser.add_argument('--summary', help="Path to the summary .json file (optional)", default=None)
    parser.add_argument('--output', help="Path to save the output markdown report (optional)", default=None)
    
    args = parser.parse_args()
    
    generate_report(args.input_file, args.summary, args.output)

if __name__ == "__main__":
    main()
