import json
import sys

def count_iterations(dialogue_history):
    """Count the number of doctor-patient Q&A iterations."""
    iteration_count = 0
    expecting_patient = False

    for item in dialogue_history:
        clean_item = item.strip()
        if ":" in clean_item:
            role = clean_item.split(":")[0]

            if role == "Doctor":
                expecting_patient = True
            elif role == "Patient" and expecting_patient:
                iteration_count += 1
                expecting_patient = False

    return iteration_count

def format_dict(data, indent=0):
    """Format a dictionary or other data structure as readable text."""
    if data is None:
        return "N/A"

    if isinstance(data, dict):
        lines = []
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                lines.append(f"{'  ' * indent}- **{key}:**")
                lines.append(format_dict(value, indent + 1))
            else:
                lines.append(f"{'  ' * indent}- **{key}:** {value}")
        return '\n'.join(lines)
    elif isinstance(data, list):
        lines = []
        for item in data:
            if isinstance(item, (dict, list)):
                lines.append(format_dict(item, indent))
            else:
                lines.append(f"{'  ' * indent}- {item}")
        return '\n'.join(lines)
    else:
        return str(data)

def parse_and_report(file_path, output_file=None):
    with open(file_path, 'r') as f:
        data = [json.loads(line) for line in f]

    # Sort data for better organization (Dataset -> ID)
    data.sort(key=lambda x: (x.get("dataset", ""), x.get("scenario_id", -1)))

    # Calculate statistics
    total_cases = len(data)
    correct_cases = sum(1 for case in data if case.get("correct", False))
    accuracy = (correct_cases / total_cases * 100) if total_cases > 0 else 0

    report = "# Patient Dialogue Analysis\n\n"
    report += f"**Total Cases:** {total_cases}\n"
    report += f"**Correct Diagnoses:** {correct_cases}/{total_cases}\n"
    report += f"**Accuracy:** {accuracy:.1f}%\n\n"

    # Calculate total token usage
    total_tokens_all = 0
    total_prompt_tokens_all = 0
    total_completion_tokens_all = 0

    for case in data:
        token_usage = case.get("token_usage", {})
        if token_usage and "total" in token_usage:
            total_tokens_all += token_usage["total"].get("total_tokens", 0)
            total_prompt_tokens_all += token_usage["total"].get("prompt_tokens", 0)
            total_completion_tokens_all += token_usage["total"].get("completion_tokens", 0)

    report += f"**Total Token Usage:** {total_tokens_all:,} (Prompt: {total_prompt_tokens_all:,}, Completion: {total_completion_tokens_all:,})\n\n"

    # Summary Table
    report += "## Summary Table\n\n"
    report += "| Dataset | ID | Status | Rounds | Tokens | Correct Diagnosis | Model Diagnosis |\n"
    report += "|---------|----:|:------:|-------:|-------:|:------------------|:----------------|\n"

    for case in data:
        dataset = case.get("dataset", "Unknown")
        scenario_id = case.get("scenario_id", "N/A")
        is_correct = case.get("correct", False)
        status = "✅" if is_correct else "❌"
        correct_diag = case.get("correct_diagnosis", "N/A")
        model_diag = case.get("model_diagnosis", "N/A")

        # Truncate model diagnosis for table
        if len(model_diag) > 50:
            model_diag = model_diag[:47] + "..."

        # Count iterations
        history = case.get("dialogue_history", [])
        rounds = count_iterations(history)

        # Get token usage
        token_usage = case.get("token_usage", {})
        total_tokens = 0
        if token_usage and "total" in token_usage:
            total_tokens = token_usage["total"].get("total_tokens", 0)

        report += f"| {dataset} | {scenario_id} | {status} | {rounds} | {total_tokens:,} | {correct_diag} | {model_diag} |\n"

    report += "\n---\n\n"

    for case in data:
        dataset = case.get("dataset", "Unknown")
        scenario_id = case.get("scenario_id", "Unknown")
        problem_info = case.get("problem_info", {})

        report += f"## Case: {dataset} ID {scenario_id}\n\n"
        report += f"**Status:** {'✅ CORRECT' if case.get('correct') else '❌ INCORRECT'}\n\n"
        report += f"- **Correct Diagnosis:** {case.get('correct_diagnosis')}\n"
        report += f"- **Model Diagnosis:** {case.get('model_diagnosis')}\n"

        # Add token usage for this case
        token_usage = case.get("token_usage", {})
        if token_usage and "total" in token_usage:
            total_tok = token_usage["total"].get("total_tokens", 0)
            prompt_tok = token_usage["total"].get("prompt_tokens", 0)
            completion_tok = token_usage["total"].get("completion_tokens", 0)
            report += f"- **Token Usage:** {total_tok:,} (Prompt: {prompt_tok:,}, Completion: {completion_tok:,})\n"

        report += "\n"

        # Extract Patient Info and Physical Exam based on dataset
        patient_info_data = None
        physical_exams_data = None
        doctor_objective = "N/A"

        if "OSCE_Examination" in problem_info:
            osce = problem_info["OSCE_Examination"]
            patient_info_data = osce.get("Patient_Actor", {})
            physical_exams_data = osce.get("Physical_Examination_Findings", {})
            doctor_objective = osce.get("Objective_for_Doctor", "N/A")
        elif "patient_info" in problem_info:
            # NEJM style
            patient_info_data = problem_info.get("patient_info")
            physical_exams_data = problem_info.get("physical_exams")
            doctor_objective = problem_info.get("question", "N/A")

        # Add Doctor's Objective
        report += f"### 🎯 Doctor's Objective\n{doctor_objective}\n\n"

        # Add Patient Information
        if patient_info_data:
            report += "### 👤 Patient Information / Symptoms\n"
            report += format_dict(patient_info_data) + "\n\n"

        # Add Physical Examination Findings
        if physical_exams_data:
            report += "### 🏥 Physical Examination Findings\n"
            report += format_dict(physical_exams_data) + "\n\n"

        report += "### 💬 Dialogue Breakdown\n\n"

        history = case.get("dialogue_history", [])
        
        iteration = 1
        for item in history:
            # item is a string like "Doctor: ..." or "Patient: ..."
            # In the updated code, dialogue_history seems to be a list of strings
            
            clean_item = item.strip()
            role = clean_item.split(":")[0]
            content = ":".join(clean_item.split(":")[1:]).strip()

            if role == "Doctor":
                report += f"**Iteration {iteration}**\n"
                report += f"- **Doctor**: {content}\n"
                if "REQUEST TEST" in content or "REQUEST IMAGES" in content:
                    # Extract the specific test requested if possible
                    report += f"  - **Testing Requested**: YES ({content})\n"
                
            elif role == "Patient":
                report += f"- **Patient**: {content}\n\n"
                iteration += 1 # Increment after a full turn
            elif role == "Measurement":
                report += f"- **Measurement Agent**: {content}\n"

        report += "---\n\n"

    # Save to file or print to stdout
    if output_file:
        with open(output_file, 'w') as f:
            f.write(report)
        print(f"Report saved to: {output_file}")
    else:
        print(report)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 generate_report_v2.py <input_jsonl_file> [output_file]")
        sys.exit(1)

    file_path = sys.argv[1]

    # Generate output filename if not provided
    if len(sys.argv) >= 3:
        output_file = sys.argv[2]
    else:
        # Generate report filename based on input file
        import os
        base_name = os.path.basename(file_path)
        if base_name.endswith('.jsonl'):
            base_name = base_name[:-6]
        dir_name = os.path.dirname(file_path)
        output_file = os.path.join(dir_name, f"report_v2_{base_name}.txt")

    try:
        parse_and_report(file_path, output_file)
    except FileNotFoundError:
        print(f"Error: File {file_path} not found.")
