import json
import os
import sys

def dict_to_md(data, level=0):
    md = ""
    prefix = "  " * level + "- "
    
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                md += f"{prefix}**{key}:**\n{dict_to_md(value, level + 1)}"
            else:
                md += f"{prefix}**{key}:** {value}\n"
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, (dict, list)):
                 md += f"{dict_to_md(item, level)}"
            else:
                md += f"{prefix}{item}\n"
    elif isinstance(data, str):
         # Handle multi-line strings
         lines = data.split('\n')
         for line in lines:
             if line.strip():
                 md += f"  " * level + line.strip() + "\n"
    else:
        md += f"  " * level + str(data) + "\n"
    return md

def count_conversations(dialogue_history):
    """
    Count conversation length where one doctor-patient Q&A exchange = 1 conversation.
    Returns the count of doctor-patient exchanges.
    """
    conversation_count = 0
    expecting_patient = False

    for item in dialogue_history:
        clean_item = item.strip()
        if ":" in clean_item:
            role = clean_item.split(":")[0].lower()

            if role == "doctor":
                expecting_patient = True
            elif role == "patient" and expecting_patient:
                conversation_count += 1
                expecting_patient = False

    return conversation_count

def convert_to_md(input_path, output_path):
    print(f"Reading from {input_path}")
    if not os.path.exists(input_path):
        print(f"Error: File {input_path} not found.")
        return

    with open(input_path, 'r') as f:
        data = [json.loads(line) for line in f]

    report = "# AgentClinic Benchmark Results\n\n"
    report += f"**Source File:** `{os.path.basename(input_path)}`\n"
    report += f"**Total Cases:** {len(data)}\n\n"

    # Sort data for better organization (Dataset -> ID)
    data.sort(key=lambda x: (x.get("dataset", ""), x.get("scenario_id", -1)))

    # Collect all unique Physical Examination Findings keys
    all_exam_keys = set()
    for case in data:
        problem_info = case.get("problem_info", {})
        osce = problem_info.get("OSCE_Examination", {})
        exams = osce.get("Physical_Examination_Findings", {})
        if isinstance(exams, dict):
            all_exam_keys.update(exams.keys())
        elif problem_info.get("physical_exams"):
             # Handle NEJM style if it's a dict, though it's often a string or list
             pe = problem_info.get("physical_exams")
             if isinstance(pe, dict):
                 all_exam_keys.update(pe.keys())

    report += "### 📋 Unique Physical Examination Types Found:\n"
    if all_exam_keys:
        for key in sorted(all_exam_keys):
            report += f"- {key}\n"
    else:
        report += "No structured Physical Examination Findings keys found (or format differs).\n"
    report += "\n---\n\n"

    for i, case in enumerate(data):
        dataset = case.get("dataset", "Unknown")
        scenario_id = case.get("scenario_id", "Unknown")
        correct_diag = case.get("correct_diagnosis", "N/A")
        model_diag = case.get("model_diagnosis", "N/A")
        is_correct = case.get("correct", False)
        status = "✅ CORRECT" if is_correct else "❌ INCORRECT"
        
        problem_info = case.get("problem_info", {})
        
        # Extract Patient Info and relevant data based on structure
        patient_info_data = {}
        physical_exams_data = {}
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
        
        # Count conversations (doctor-patient Q&A exchanges)
        history = case.get("dialogue_history", [])
        conversation_count = count_conversations(history)

        report += f"## Case {i+1}: {dataset} (ID: {scenario_id})\n\n"
        report += f"**Status:** {status}\n\n"
        report += f"- **Correct Diagnosis:** {correct_diag}\n"
        report += f"- **Model Diagnosis:** {model_diag}\n"
        report += f"- **Conversation Length:** {conversation_count} doctor-patient Q&A exchanges\n\n"
        
        report += f"### 🎯 Doctor's Objective\n{doctor_objective}\n\n"

        report += "### 👤 Patient Information / Symptoms\n"
        report += dict_to_md(patient_info_data) + "\n"
        
        report += "### 🏥 Physical Examination Findings\n"
        report += dict_to_md(physical_exams_data) + "\n"
        
        report += "### 💬 Dialogue History\n\n"
        if not history:
             report += "*No dialogue history available.*\n\n"
        
        for item in history:
            clean_item = item.strip()
            # Handle standard "Role: Content" format
            if ":" in clean_item:
                role = clean_item.split(":")[0]
                content = ":".join(clean_item.split(":")[1:]).strip()
                
                # Format based on role
                if role.lower() == "doctor":
                    report += f"**👨‍⚕️ Doctor:** {content}\n\n"
                elif role.lower() == "patient":
                    report += f"**👤 Patient:** {content}\n\n"
                elif "measurement" in role.lower():
                     report += f"**📊 Measurement:** {content}\n\n"
                else:
                    # Fallback for other roles or misformatted lines
                    report += f"**{role}:** {content}\n\n"
            else:
                # Fallback for lines without colons
                report += f"> {clean_item}\n\n"

        report += "---\n\n"

    with open(output_path, 'w') as f:
        f.write(report)
    
    print(f"Successfully converted {len(data)} conversations to Markdown.")
    print(f"Saved to: {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python convert_conversations_to_md.py <input_jsonl_file> [output_md_file]")
        print("If output file is not specified, it will use the same name as input with .md extension")
        sys.exit(1)

    input_file = sys.argv[1]

    # Generate output filename from input if not provided
    if len(sys.argv) >= 3:
        output_file = sys.argv[2]
    else:
        # Replace .jsonl with .md, or just append .md if no .jsonl extension
        if input_file.endswith('.jsonl'):
            output_file = input_file[:-6] + '.md'
        else:
            output_file = input_file + '.md'

    convert_to_md(input_file, output_file)
