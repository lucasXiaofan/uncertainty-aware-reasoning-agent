import json
import sys

def analyze_results(file_path):
    total_questions = 0
    effective_questions = 0
    redundant_questions_count = 0
    redundant_details = []

    try:
        with open(file_path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    print(f"Error decoding JSON on line {line_num}")
                    continue

                interactive_system = data.get('interactive_system', {})
                questions = interactive_system.get('questions', [])
                answers = interactive_system.get('answers', [])

                # Check for redundancy
                seen_questions = set()
                for i, q in enumerate(questions):
                    q_normalized = q.strip().lower()
                    if q_normalized in seen_questions:
                        redundant_questions_count += 1
                        redundant_details.append({
                            'id': data.get('id'),
                            'question': q,
                            'index': i
                        })
                    else:
                        seen_questions.add(q_normalized)

                # Calculate stats
                num_q = len(questions)
                total_questions += num_q
                
                # Calculate effective questions
                # Effective = Total - (questions where answer is the specific failure string)
                # The failure string is "The patient cannot answer this question, please do not ask this question again."
                # Let's check exact match or substring match
                
                current_effective = 0
                for ans in answers:
                    if "The patient cannot answer this question, please do not ask this question again" not in ans:
                        current_effective += 1
                
                effective_questions += current_effective

        print(f"Total Questions Asked: {total_questions}")
        print(f"Total Effective Questions: {effective_questions}")
        print(f"Redundant Questions Count: {redundant_questions_count}")
        
        if redundant_questions_count > 0:
            print("\nRedundant Questions Details:")
            for item in redundant_details:
                print(f"ID: {item['id']}, Index: {item['index']}, Question: {item['question']}")
        else:
            print("\nNo exact redundant questions found.")

        if effective_questions > 0:
             print(f"\nRatio (Total / Effective): {total_questions / effective_questions:.2f}")

    except FileNotFoundError:
        print(f"File not found: {file_path}")

if __name__ == "__main__":
    file_path = 'outputs/MultiAgentExpert_deepseek_deepseek-chat-v3_20251119_164857/results.jsonl'
    analyze_results(file_path)
