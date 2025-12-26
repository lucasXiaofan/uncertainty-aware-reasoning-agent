import json
import argparse
import os
import sys

def load_results(file_path):
    results = {}
    try:
        with open(file_path, 'r') as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    results[data['id']] = data
    except Exception as e:
        print(f"Error loading {file_path}: {e}")
    return results

def analyze_questions(data):
    """
    Returns metrics on questions: total count, failed count.
    """
    sys_data = data.get('interactive_system', {})
    questions = sys_data.get('questions', [])
    answers = sys_data.get('answers', [])
    
    total = len(questions)
    failed = sum(1 for a in answers if "cannot answer" in a.lower() or "i don't know" in a.lower())
    
    return total, failed, questions, answers

def get_outcome(data):
    """
    Returns (is_correct, final_diagnosis)
    """
    sys_data = data.get('interactive_system', {})
    is_correct = sys_data.get('correct', False)
    # Trying to find the model's final diagnosis. It might be in steps or just inferred from correctness.
    # The 'summary.json' usually has more aggregate info, but here we work with results.jsonl
    # We'll look for the final choice or similar.
    
    # In the provided analysis script, it looks like:
    # final_res = "Correct" if sys_data.get('correct') else "Wrong"
    return is_correct

def compare_runs(no_exp_path, exp_mem_path, exp_dec_path, output_file):
    print(f"Loading data...")
    no_exp_data = load_results(no_exp_path)
    exp_mem_data = load_results(exp_mem_path)
    exp_dec_data = load_results(exp_dec_path)
    
    common_ids = set(no_exp_data.keys()) & set(exp_mem_data.keys()) & set(exp_dec_data.keys())
    print(f"Found {len(common_ids)} common scenarios.")
    
    lines = []
    def p(text=""):
        lines.append(text)
        
    p("# Analysis of Experience Augmentation Impact\n")
    p(f"**Baseline**: {os.path.basename(os.path.dirname(no_exp_path))}")
    p(f"**Exp-Memory**: {os.path.basename(os.path.dirname(exp_mem_path))}")
    p(f"**Exp-Decision**: {os.path.basename(os.path.dirname(exp_dec_path))}\n")
    
    # Metrics
    metrics = {
        'baseline': {'correct': 0, 'questions': 0, 'failed_qs': 0},
        'exp_mem': {'correct': 0, 'questions': 0, 'failed_qs': 0},
        'exp_dec': {'correct': 0, 'questions': 0, 'failed_qs': 0},
    }
    
    improved_cases = [] # Where experience helped (Wrong -> Correct)
    degraded_cases = [] # Where experience hurt (Correct -> Wrong)
    neutral_cases = []
    
    for rid in common_ids:
        # Baseline
        base_res = no_exp_data[rid]
        base_corr = get_outcome(base_res)
        b_q, b_fq, b_qs, b_as = analyze_questions(base_res)
        metrics['baseline']['correct'] += 1 if base_corr else 0
        metrics['baseline']['questions'] += b_q
        metrics['baseline']['failed_qs'] += b_fq
        
        # Exp Memory
        mem_res = exp_mem_data[rid]
        mem_corr = get_outcome(mem_res)
        m_q, m_fq, m_qs, m_as = analyze_questions(mem_res)
        metrics['exp_mem']['correct'] += 1 if mem_corr else 0
        metrics['exp_mem']['questions'] += m_q
        metrics['exp_mem']['failed_qs'] += m_fq
        
        # Exp Decision
        dec_res = exp_dec_data[rid]
        dec_corr = get_outcome(dec_res)
        d_q, d_fq, d_qs, d_as = analyze_questions(dec_res)
        metrics['exp_dec']['correct'] += 1 if dec_corr else 0
        metrics['exp_dec']['questions'] += d_q
        metrics['exp_dec']['failed_qs'] += d_fq
        
        # Comparison logic
        # focus on if ANY experience helped or hurt compared to baseline
        
        # Identify improvements (Baseline Wrong -> Exp Correct)
        if not base_corr and (mem_corr or dec_corr):
            improved_cases.append({
                'id': rid,
                'type': 'Improvement',
                'details': f"Baseline: Wrong, Mem: {'Correct' if mem_corr else 'Wrong'}, Dec: {'Correct' if dec_corr else 'Wrong'}"
            })
            
        # Identify degradation (Baseline Correct -> Exp Wrong)
        if base_corr and (not mem_corr or not dec_corr):
            degraded_cases.append({
                'id': rid,
                'type': 'Degradation',
                'details': f"Baseline: Correct, Mem: {'Correct' if mem_corr else 'Wrong'}, Dec: {'Correct' if dec_corr else 'Wrong'}",
                'base_qs': b_qs,
                'mem_qs': m_qs,
                'dec_qs': d_qs
            })

    # Summary Table
    p("## Overall Performance Summary")
    p("| Setup | Accuracy | Avg Questions | Avg Failed Qs |")
    p("|---|---|---|---|")
    total = len(common_ids)
    if total == 0: total = 1 # avoid div by zero
    
    for name, m in metrics.items():
        acc = (m['correct'] / total) * 100
        avg_q = m['questions'] / total
        avg_fq = m['failed_qs'] / total
        p(f"| {name} | {acc:.1f}% | {avg_q:.1f} | {avg_fq:.1f} |")
        
    p("\n## Impact Analysis")
    
    p(f"\n### 1. Does Experience Help Make Better Decisions?")
    if len(improved_cases) > 0:
        p(f"**YES**, in {len(improved_cases)} cases, adding experience corrected a previously wrong diagnosis.")
        for case in improved_cases:
            p(f"- **Case {case['id']}**: {case['details']}")
    else:
        p(f"**NO**, experience did not turn any wrong diagnoses into correct ones in this batch.")

    p(f"\n### 2. Cases Where Experience Was NOT Helpful (Degradation)")
    if len(degraded_cases) > 0:
        p(f"In {len(degraded_cases)} cases, performance dropped with experience.")
        for case in degraded_cases:
            p(f"\n#### Case {case['id']}")
            p(f"Outcome: {case['details']}")
            p("Reasoning: Comparing questions asked...")
            # Simple heuristic: did they ask fewer relevant questions?
            # We output the first few questions to see difference
            p(f"**Baseline Questions ({len(case['base_qs'])})**:")
            for q in case['base_qs'][:3]: p(f"- {q}")
            
            p(f"**Exp-Mem Questions ({len(case['mem_qs'])})**:")
            for q in case['mem_qs'][:3]: p(f"- {q}")
            
            p(f"**Exp-Dec Questions ({len(case['dec_qs'])})**:")
            for q in case['dec_qs'][:3]: p(f"- {q}")
            
    else:
        p("No cases of degradation found.")
        
    p(f"\n### 3. Does Experience Help Ask Better Questions?")
    # Compare failed question rates
    base_fail_rate = metrics['baseline']['failed_qs'] / metrics['baseline']['questions'] if metrics['baseline']['questions'] else 0
    mem_fail_rate = metrics['exp_mem']['failed_qs'] / metrics['exp_mem']['questions'] if metrics['exp_mem']['questions'] else 0
    dec_fail_rate = metrics['exp_dec']['failed_qs'] / metrics['exp_dec']['questions'] if metrics['exp_dec']['questions'] else 0
    
    p(f"- Baseline Failed Question Rate: {base_fail_rate*100:.1f}%")
    p(f"- Exp-Memory Failed Question Rate: {mem_fail_rate*100:.1f}%")
    p(f"- Exp-Decision Failed Question Rate: {dec_fail_rate*100:.1f}%")
    
    if mem_fail_rate < base_fail_rate or dec_fail_rate < base_fail_rate:
         p("Experience seems to **reduce** the rate of failed/irrelevant questions.")
    else:
         p("Experience **did not** reduce the rate of failed questions.")

    # Write output
    with open(output_file, 'w') as f:
        f.write("\n".join(lines))
    print(f"Analysis complete. Report saved to {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('no_exp', help="Results file for no experience")
    parser.add_argument('exp_mem', help="Results file for experience memory")
    parser.add_argument('exp_dec', help="Results file for experience decision")
    parser.add_argument('--output', default='experience_impact_report.md', help="Output report file")
    
    args = parser.parse_args()
    compare_runs(args.no_exp, args.exp_mem, args.exp_dec, args.output)
