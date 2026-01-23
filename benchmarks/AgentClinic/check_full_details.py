import json
import os
import time
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

def query_model(prompt, system_prompt, model="z-ai/glm-4.6v"):
    openrouter_key = os.environ.get("OPENROUTER_API_KEY")
    if not openrouter_key:
        print("Error: OPENROUTER_API_KEY not found in environment.")
        return "Error: No API Key"
    
    print(f"DEBUG: Using API Key: {openrouter_key[:5]}...{openrouter_key[-4:]}")
    print(f"DEBUG: Using Base URL: https://openrouter.ai/api/v1")
    
    client = OpenAI(api_key=openrouter_key, base_url="https://openrouter.ai/api/v1")
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]
    
    for attempt in range(3):
        try:
            print(f"DEBUG: Attempt {attempt+1} - Sending request to {model}")
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=2048
            )

            
            if not response.choices:
                print("DEBUG: No choices in response.")
                continue
                
            choice = response.choices[0]            
            message = choice.message
            content = message.content

            if hasattr(message, 'tool_calls'):
                print(f"DEBUG: Tool Calls: {message.tool_calls}")
            
            if content is None:
                print("DEBUG: Content is None.")
                return ""
            return content
        except Exception as e:
            print(f"Error querying model {model}: {e}")
            time.sleep(2)
    return "Error"

def check_correctness(model_output, correct_diagnosis):
    if not model_output or not model_output.strip():
        print("DEBUG: Empty model output, marking as INCORRECT.")
        return False
        
    # Logic from agentclinic_api_only.py:compare_results
    system_prompt = "You are responsible for determining if the corrent diagnosis and the doctor diagnosis are the same disease. Please respond only with Yes or No. Nothing else."
    prompt = f"\nHere is the correct diagnosis: {correct_diagnosis}\n Here was the doctor dialogue: {model_output}\nAre these the same?"
    
    answer = query_model(prompt, system_prompt, model="z-ai/glm-4.6v")
    if "yes" in answer.lower():
        return True
    return False

def dict_to_markdown(data, level=1):
    markdown = ""
    if isinstance(data, dict):
        for key, value in data.items():
            markdown += f"{'#' * level} {key}\n"
            markdown += dict_to_markdown(value, level + 1)
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, (dict, list)):
                markdown += dict_to_markdown(item, level)
            else:
                markdown += f"- {item}\n"
    else:
        markdown += f"{data}\n\n"
    return markdown

def main():
    cases_to_check = [
        ("MedQA", 2), # start with this one
        ("MedQA_Ext", 1), # right 
        ("MedQA_Ext", 2), # right 
        ("MIMICIV", 1),# right 
        ("MIMICIV", 3),# right 
        ("MIMICIV", 4),# right 
        ("NEJM_Ext", 1)# wrong 
    ]
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    dataset_files = {
        "MedQA": os.path.join(base_dir, "agentclinic_medqa.jsonl"),
        "MedQA_Ext": os.path.join(base_dir, "agentclinic_medqa_extended.jsonl"),
        "MIMICIV": os.path.join(base_dir, "agentclinic_mimiciv.jsonl"),
        "NEJM_Ext": os.path.join(base_dir, "agentclinic_nejm_extended.jsonl")
    }

    results = []

    for dataset, scenario_id in cases_to_check:
        file_path = dataset_files[dataset]
        if not os.path.exists(file_path):
            print(f"Warning: {file_path} not found.")
            continue
            
        with open(file_path, "r") as f:
            lines = f.readlines()
            if scenario_id >= len(lines):
                print(f"Warning: ID {scenario_id} out of range for {dataset}.")
                continue
            case_data = json.loads(lines[scenario_id])
            
        if "OSCE_Examination" in case_data:
            osce = case_data["OSCE_Examination"]
            if "Correct_Diagnosis" in osce:
                correct_diag = osce["Correct_Diagnosis"]
                # Remove diagnosis for the prompt
                full_details = {k: v for k, v in osce.items() if k != "Correct_Diagnosis"}
            else:
                print(f"Warning: 'Correct_Diagnosis' missing in OSCE data for {dataset} ID {scenario_id}")
                continue
        elif "question" in case_data and "answers" in case_data:
            # NEJM style
            try:
                correct_diag = next(a["text"] for a in case_data["answers"] if a["correct"])
            except StopIteration:
                 print(f"Warning: No correct diagnosis found in answers for {dataset} ID {scenario_id}")
                 continue
            
            full_details = {
                "question": case_data.get("question"),
                "patient_info": case_data.get("patient_info"),
                "physical_exams": case_data.get("physical_exams")
            }
        else:
             print(f"Warning: Unknown data format for {dataset} ID {scenario_id}")
             continue
        
        prompt = f"Please analyze the following patient case and provide a diagnosis.\n\n"
        prompt += dict_to_markdown(full_details)
        prompt += "\n\nBased on all the information provided above, what is the most likely diagnosis? Please explain your reasoning step by step and end your response EXACTLY with 'DIAGNOSIS READY: [Diagnosis Name]'."
        
        print(f"Checking {dataset} ID {scenario_id}...")
        model_output = query_model(prompt, "You are a highly skilled medical doctor. Analyze the case provided and determine the diagnosis.", model="z-ai/glm-4.6v")

        is_correct = check_correctness(model_output, correct_diag)
        
        results.append({
            "dataset": dataset,
            "id": scenario_id,
            "correct_diag": correct_diag,
            "model_diag": model_output,
            "is_correct": is_correct,
            "full_output": model_output
        })
        
        print(f"Result: {'✅' if is_correct else '❌'} (Expected: {correct_diag}, Got: {model_output})")
        print("-" * 50)

    # Save summary
    os.makedirs("results", exist_ok=True)
    with open("results/full_details_glm_check.txt", "w") as f:
        f.write("Full Details GLM Check Result (Using Moderator Logic, No Regex)\n")
        f.write("=" * 60 + "\n")
        for res in results:
            status = "CORRECT" if res["is_correct"] else "INCORRECT"
            f.write(f"[{res['dataset']} ID {res['id']}] {status}\n")
            f.write(f"  Expected: {res['correct_diag']}\n")
            f.write(f"  Got:      {res['model_diag']}\n")
            f.write("-" * 60 + "\n")

if __name__ == "__main__":
    main()
