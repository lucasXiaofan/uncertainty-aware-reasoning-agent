import re
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
            if difflib.SequenceMatcher(None, q, s).ratio() > threshold:
                is_redundant = True
                break
        if is_redundant:
            redundant_indices.append(i)
        seen.append(q)
    return redundant_indices

    return redundant_indices

def parse_differential_options(options_str):
    """
    Parses the options string from differential agent to get a list of available option indices.
    Example input: "A. Option A, B. Option B"
    Returns: ['A', 'B']
    """
    # Regex to find "X. " pattern at start of line or after space
    # Adjust regex to be robust
    matches = re.findall(r'(?:^|\s)([A-Z])\.', options_str)
    return sorted(list(set(matches)))

def analyze_trajectory(choices, correct_idx):
    """
    Analyzes how the agent's choice changed over time.
    """
    if not choices:
        return "No intermediate choices"
    
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

def analyze_memory_agent(steps):
    """
    Analyzes the behavior of the memory agent within the steps.
    """
    memory_interventions = 0
    assess_progress_calls = 0
    strategy_suggestions = []
    
    for step in steps:
        if step.get('agent_type') == 'memory_agent':
            memory_interventions += 1
            if step.get('tool') == 'assess_progress':
                assess_progress_calls += 1
                args = step.get('args', {})
                if args.get('strategy_suggestion'):
                    strategy_suggestions.append(args['strategy_suggestion'])
                    
    return {
        'memory_interventions': memory_interventions,
        'assess_progress_calls': assess_progress_calls,
        'strategy_suggestions': strategy_suggestions
    }

def get_differential_stats(trajectory, correct_idx):
    """
    Analyzes differential agent steps.
    Returns:
    - kept_correct: bool (true if correct answer was never ruled out)
    - ruled_out_step: dict (info about the step where it was ruled out)
    - option_counts: list of ints (number of options in each diff step)
    """
    kept_correct = True
    ruled_out_step = None
    option_counts = []
    
    for step in trajectory:
        if step.get('tool') == 'submit_differential':
            args = step.get('args', {})
            options_str = args.get('current_differential_options', '')
            current_options = parse_differential_options(options_str)
            if current_options:
                option_counts.append(len(current_options))
                
                if correct_idx not in current_options:
                    if kept_correct: # First time it's missing
                        kept_correct = False
                        ruled_out_step = {
                            'reason': args.get('rule_out_criteria', 'No reason provided'),
                            'options_str': options_str
                        }
    
    if not option_counts:
        return None
        
    return {
        'kept_correct': kept_correct,
        'ruled_out_step': ruled_out_step,
        'option_counts': option_counts
    }

def normalize_confidence(conf):
    """
    Normalizes confidence to 0-100 scale.
    Assumes values <= 1.0 are probabilities (0-1), and values > 1.0 are percentages (0-100).
    """
    if conf is None:
        return None
    try:
        val = float(conf)
        if val <= 1.0:
            return val * 100
        return val
    except (ValueError, TypeError):
        return None

def get_confidence_trajectory(trajectory):
    confidences = []
    for step in trajectory:
        tool = step.get('tool')
        if tool in ['make_choice', 'ask_question']:
            conf = step.get('args', {}).get('confidence')
            norm_conf = normalize_confidence(conf)
            if norm_conf is not None:
                confidences.append(norm_conf)
    return confidences

def get_choice_trajectory(trajectory):
    choices = []
    for step in trajectory:
        tool = step.get('tool')
        if tool in ['make_choice', 'ask_question']:
            choice = step.get('args', {}).get('letter_choice')
            if choice:
                choices.append(choice)
    return choices

def generate_report(input_file, summary_file=None, output_file=None):
    """
    Generates a markdown report from the result jsonl file, focusing on 3-agent dynamics.
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

    p("# Three-Agent Analysis Report")
    p(f"**Input File**: `{os.path.basename(input_file)}`")
    if summary_file:
        p(f"**Summary File**: `{os.path.basename(summary_file)}`")
    p("")
    
    # --- Section 1: Memory Agent Performance ---
    p("## 1. Memory Agent Performance\n")
    p("This section analyzes how often the Memory Agent intervened and suggested strategies.\n")
    
    p("| ID | Memory Interventions | Assess Progress Calls | Strategy Suggestions | Final Result |")
    p("|---|---|---|---|---|")
    
    total_memory_interventions = 0
    total_assess_calls = 0
    
    for data in entries:
        if 'interactive_system' not in data:
            continue
            
        sys_data = data['interactive_system']
        
        # Collect all steps from various locations
        all_steps = []
        
        # 1. Top-level steps
        if 'steps' in sys_data:
            all_steps.extend(sys_data['steps'])
            
        # 2. Steps inside temp_additional_info -> trajectory
        if 'temp_additional_info' in sys_data:
            for item in sys_data['temp_additional_info']:
                if 'trajectory' in item:
                    all_steps.extend(item['trajectory'])
        
        mem_stats = analyze_memory_agent(all_steps)
        
        total_memory_interventions += mem_stats['memory_interventions']
        total_assess_calls += mem_stats['assess_progress_calls']
        num_suggestions = len(mem_stats['strategy_suggestions'])
        
        final_res = "Correct" if sys_data.get('correct') else "Wrong"
        
        p(f"| {data.get('id', 'N/A')} | {mem_stats['memory_interventions']} | {mem_stats['assess_progress_calls']} | {num_suggestions} | {final_res} |")

    p(f"\n**Summary**:")
    p(f"- Total Memory Interventions: {total_memory_interventions}")
    p(f"- Total Assess Progress Calls: {total_assess_calls}")
    
    # --- Section 2: Question Asking Quality (Standard) ---
    p("\n## 2. Question Asking Quality\n")
    
    total_questions = 0
    total_redundant = 0
    total_failed = 0
    
    p("| ID | Total Qs | Redundant Qs | Failed Qs (No Info) | Proactive? | Note |")
    p("|---|---|---|---|---|---|")
    
    for data in entries:
        if 'interactive_system' not in data:
            continue
            
        sys_data = data['interactive_system']
        q_list = sys_data.get('questions', [])
        a_list = sys_data.get('answers', [])
        
        redundant_idxs = check_redundancy(q_list)
        num_redundant = len(redundant_idxs)
        
        num_failed = sum(1 for a in a_list if "cannot answer" in a or "I don't know" in a)
        
        total_questions += len(q_list)
        total_redundant += num_redundant
        total_failed += num_failed
        
        is_proactive = len(q_list) > 0
        
        note = ""
        if not is_proactive:
            if sys_data.get('correct'):
                note = "No questions asked, but correct"
            else:
                note = "No questions asked, and incorrect"
        
        p(f"| {data.get('id', 'N/A')} | {len(q_list)} | {num_redundant} | {num_failed} | {is_proactive} | {note} |")

    p(f"\n**Summary**:")
    p(f"- Total Questions: {total_questions}")
    if total_questions > 0:
        p(f"- Redundant Questions: {total_redundant} ({total_redundant/total_questions*100:.1f}%)")
        p(f"- Failed Questions: {total_failed} ({total_failed/total_questions*100:.1f}%)")
    
    # --- Section 3: Decision Ability & Context Usage ---
    p("\n## 3. Decision Ability & Context Usage\n")
    
    p("| ID | Context % | Trajectory | Final Result | Total Qs | Valid Qs | Input Tokens | Output Tokens |")
    p("|---|---|---|---|---|---|---|---|")
    
    total_input_tokens = 0
    total_output_tokens = 0
    
    for data in entries:
        if 'interactive_system' not in data or 'info' not in data:
            continue
            
        sys_data = data['interactive_system']
        info_data = data['info']
        
        q_list = sys_data.get('questions', [])
        a_list = sys_data.get('answers', [])
        num_qs = len(q_list)
        num_failed = sum(1 for a in a_list if "cannot answer" in a or "I don't know" in a)
        num_valid_qs = num_qs - num_failed

        initial_info = info_data.get('initial_info', "")
        valid_answers = [a for a in sys_data.get('answers', []) if "cannot answer" not in a]
        patient_response_context = " ".join(valid_answers)
        
        context_have = initial_info + " " + patient_response_context
        total_context_list = info_data.get('context', [])
        total_context_str = " ".join(total_context_list) if isinstance(total_context_list, list) else str(total_context_list)
        
        pct = (len(context_have) / len(total_context_str)) * 100 if total_context_str else 0
        if pct > 100: pct = 100 
        
        choices = sys_data.get('intermediate_choices', [])
        correct_idx = info_data.get('correct_answer_idx')
        traj_str = analyze_trajectory(choices, correct_idx)
        
        final_res = "Correct" if sys_data.get('correct') else "Wrong"
        
        # Tokens - try to get from steps if available, or temp_additional_info
        input_tok = 0
        output_tok = 0
        
        # Check steps for usage
        steps = sys_data.get('steps', [])
        for step in steps:
             # Usage might not be directly in steps, usually it's in the response from the model
             # But in this log format, usage might be at the top level of the step or missing
             pass
        
        # Fallback to temp_additional_info if available
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

    # --- Section 4: Differential Agent Analysis ---
    p("\n## 4. Differential Agent Analysis\n")
    p("This section tracks if the Differential Agent correctly kept the right answer in its options list.\n")
    
    p("| ID | Correct Option | Kept Correct? | Option Count Trajectory | Ruled Out Reason |")
    p("|---|---|---|---|---|")
    
    ruled_out_cases = []
    
    for data in entries:
        if 'interactive_system' not in data or 'info' not in data:
            continue
            
        sys_data = data['interactive_system']
        info_data = data['info']
        correct_idx = info_data.get('correct_answer_idx')
        
        # Collect trajectory
        all_steps = []
        if 'steps' in sys_data:
            all_steps.extend(sys_data['steps'])
        if 'temp_additional_info' in sys_data:
            for item in sys_data['temp_additional_info']:
                if 'trajectory' in item:
                    all_steps.extend(item['trajectory'])
        
        diff_stats = get_differential_stats(all_steps, correct_idx)
        
        if diff_stats:
            kept = "Yes" if diff_stats['kept_correct'] else "No"
            traj = " -> ".join(map(str, diff_stats['option_counts']))
            reason = ""
            if not diff_stats['kept_correct']:
                reason = diff_stats['ruled_out_step']['reason']
                # Truncate reason if too long
                if len(reason) > 100:
                    reason = reason[:97] + "..."
                
                ruled_out_cases.append({
                    'id': data.get('id'),
                    'question': info_data.get('question'),
                    'correct_option': correct_idx,
                    'reason': diff_stats['ruled_out_step']['reason'],
                    'full_reason': diff_stats['ruled_out_step']['reason']
                })
            
            p(f"| {data.get('id', 'N/A')} | {correct_idx} | {kept} | {traj} | {reason} |")
        else:
            p(f"| {data.get('id', 'N/A')} | {correct_idx} | N/A | N/A | No Differential Steps |")

    if ruled_out_cases:
        p("\n### Cases where Correct Answer was Ruled Out\n")
        for case in ruled_out_cases:
            p(f"**ID {case['id']}**")
            p(f"- **Question**: {case['question']}")
            p(f"- **Correct Option**: {case['correct_option']}")
            p(f"- **Reason for Ruling Out**: {case['full_reason']}")
            p("")

    # --- Section 5: High Information Questions ---
    p("\n## 5. High Information Questions\n")
    p("Questions where the patient provided a long response (likely high information gain).\n")
    
    high_info_threshold = 100 # characters
    
    for data in entries:
        if 'interactive_system' not in data or 'info' not in data:
            continue
            
        sys_data = data['interactive_system']
        info_data = data['info']
        q_list = sys_data.get('questions', [])
        a_list = sys_data.get('answers', [])
        
        for q, a in zip(q_list, a_list):
            if len(a) > high_info_threshold:
                p(f"**ID {data.get('id', 'N/A')}**")
                p(f"- **Question**: {q}")
                p(f"- **Patient Answer**: {a}")
                p(f"- **Options**: {json.dumps(info_data.get('options', {}), indent=2)}")
                p("")

    # --- Section 6: Confidence & Choice Analysis ---
    p("\n## 6. Confidence & Choice Analysis\n")
    p("Tracking confidence scores and letter choices from the Decision Agent.\n")
    
    p("| ID | Correct Answer | Final Confidence | Confidence Trajectory | Choice Trajectory | Correct? | Intermediate Choices Correct? |")
    p("|---|---|---|---|---|---|---|")
    
    for data in entries:
        if 'interactive_system' not in data or 'info' not in data:
            continue
            
        sys_data = data['interactive_system']
        info_data = data['info']
        correct_idx = info_data.get('correct_answer_idx')
        
        # Collect trajectory
        all_steps = []
        if 'steps' in sys_data:
            all_steps.extend(sys_data['steps'])
        if 'temp_additional_info' in sys_data:
            for item in sys_data['temp_additional_info']:
                if 'trajectory' in item:
                    all_steps.extend(item['trajectory'])
        
        conf_traj = get_confidence_trajectory(all_steps)
        choice_traj = get_choice_trajectory(all_steps)
        
        # Get final confidence from temp_additional_info if available (it's usually there)
        final_conf = "N/A"
        if 'temp_additional_info' in sys_data and sys_data['temp_additional_info']:
            raw_conf = sys_data['temp_additional_info'][0].get('confidence')
            norm_conf = normalize_confidence(raw_conf)
            if norm_conf is not None:
                final_conf = f"{norm_conf:.1f}"
        
        # Format trajectory
        conf_traj_str = "[" + ", ".join([f"{c:.1f}" for c in conf_traj]) + "]"
        choice_traj_str = "[" + ", ".join(choice_traj) + "]"
        
        inter_choices = sys_data.get('intermediate_choices', [])
        inter_correct = "N/A"
        if inter_choices:
            if correct_idx in inter_choices:
                inter_correct = "Yes"
            else:
                inter_correct = "No"
        
        final_res = "Correct" if sys_data.get('correct') else "Wrong"
        
        p(f"| {data.get('id', 'N/A')} | {correct_idx} | {final_conf} | {conf_traj_str} | {choice_traj_str} | {final_res} | {inter_correct} |")
    
    # --- Output ---
    report_content = "\n".join(output_lines)
    
    if output_file:
        with open(output_file, 'w') as f:
            f.write(report_content)
        print(f"Report written to {output_file}")
    else:
        print(report_content)

def main():
    parser = argparse.ArgumentParser(description="Analyze three-agent reasoning logs.")
    parser.add_argument('input_file', help="Path to the .jsonl results file")
    parser.add_argument('--summary', help="Path to the summary .json file (optional)", default=None)
    parser.add_argument('--output', help="Path to save the output markdown report (optional)", default=None)
    
    args = parser.parse_args()
    
    generate_report(args.input_file, args.summary, args.output)

if __name__ == "__main__":
    main()
