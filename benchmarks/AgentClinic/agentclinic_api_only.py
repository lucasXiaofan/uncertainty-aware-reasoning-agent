import argparse
from openai import OpenAI
import re
import random
import time
import json
import os
from dotenv import load_dotenv
load_dotenv()
import sys
from pathlib import Path
# Add src to sys.path to allow importing SingleAgent
src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if src_path not in sys.path:
    sys.path.append(src_path)

try:
    from src.agents.single_agent import SingleAgent
except ImportError as e:
    print(f"Warning: Could not import SingleAgent. CustomDoctorAgent will not work. Error: {e}")
except Exception as e:
    print(f"Warning: Unexpected error importing SingleAgent: {e}")


# Global client variable
client = None

def query_model(model_str, prompt, system_prompt, tries=30, timeout=20.0, image_requested=False, scene=None, max_prompt_len=2**14, clip_prompt=False):
    global client
    # Simplified model check - focusing on API models
    if model_str not in ["gpt4", "gpt3.5", "gpt4o", "gpt-4o-mini", "gpt4v", "o1-preview", "gpt-5-mini"] and "gpt" not in model_str and "/" not in model_str:
         # Allow other gpt models if they follow the same API
         pass

    for _ in range(tries):
        if clip_prompt: prompt = prompt[:max_prompt_len]
        try:
            if not client:
                # Fallback init if not set in main (e.g. env var)
                client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

            if image_requested:
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", 
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url",
                            "image_url": {
                                "url": "{}".format(scene.image_url),
                            },
                        },
                    ]},]
                # Unified chat completion call for vision/multimodal if supported by model
                # For now, mapping specific models to their vision counterparts or just passing through
                model_to_use = model_str
                if model_str == "gpt4v": model_to_use = "gpt-4-vision-preview"
                
                
                # Determine token parameter based on model
                token_param = "max_tokens"
                if "gpt-5" in model_str or "o1" in model_str:
                    token_param = "max_completion_tokens"
                
                kwargs = {
                    "model": model_to_use,
                    "messages": messages,
                    token_param: 5000 if token_param == "max_completion_tokens" else 1000
                }
                
                response = client.chat.completions.create(**kwargs)
                answer = response.choices[0].message.content or ""
                if not answer:
                    print(f"DEBUG: Empty response from model {model_to_use}. Full response: {response}")
            
            else: # Text only
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}]
                
                model_to_use = model_str
                if model_str == "gpt4": model_to_use = "gpt-4-turbo-preview"
                elif model_str == "gpt3.5": model_to_use = "gpt-3.5-turbo"
                elif model_str == "o1-preview": model_to_use = "o1-preview-2024-09-12"
                
                # Special handling for o1-preview which might not support system prompt in the same way or other quirks
                # But keeping it simple as per original code structure
                if model_str == "o1-preview":
                     messages = [{"role": "user", "content": system_prompt + prompt}]

                
                # Determine token parameter based on model
                token_param = "max_tokens"
                if "gpt-5" in model_str or "o1" in model_str:
                    token_param = "max_completion_tokens" # Use compatible parameter for reasoning models
                
                kwargs = {
                    "model": model_to_use,
                    "messages": messages,
                    token_param: 5000 if token_param == "max_completion_tokens" else 1000
                }
                
                # Handle o1-preview special case (no max tokens limit usually or high limit)
                if model_str == "o1-preview":
                     kwargs[token_param] = None

                response = client.chat.completions.create(**kwargs)
                answer = response.choices[0].message.content or ""
                if not answer:
                    print(f"DEBUG: Empty response from model {model_to_use}. Full response: {response}")
                
                answer = re.sub("\s+", " ", answer)

            return answer
        
        except Exception as e:
            print(f"Error querying model {model_str}: {e}")
            time.sleep(timeout)
            continue
    raise Exception("Max retries: timeout")


class CustomDoctorAgent:
    def __init__(self, scenario, backend_str="doctor_grok", max_infs=20, bias_present=None, img_request=False) -> None:
        self.infs = 0
        self.MAX_INFS = max_infs
        self.agent_hist = ""
        self.presentation = ""
        # Initialize SingleAgent
        agent_name = backend_str if backend_str in ["doctor_grok"] else "doctor_grok"
        self.agent = SingleAgent(agent_name=agent_name)
        
        self.bias_present = (None if bias_present == "None" else bias_present)
        self.scenario = scenario
        self.reset()
        self.img_request = img_request
        self.biases = ["recency", "frequency", "false_consensus", "confirmation", "status_quo", "gender", "race", "sexual_orientation", "cultural", "education", "religion", "socioeconomic"]

    def generate_bias(self) -> str:
        # Reusing the bias logic from DoctorAgent
        if self.bias_present == "recency":
            return "\nRecently, you learned that a doctor with similar symptoms to the patient that diagnosed their patient with cancer. This affects how you interact with the patient.\n"
        elif self.bias_present == "frequency":
            return "\nYou recently learned that most frequently, doctors diagnose patients with similar symptoms with cancer based on past cases. This affects how you interact with the patient.\n"
        elif self.bias_present == "false_consensus":
            return "\nMost of your colleagues who heard about the patient's symptoms believe that they have cancer. This affects how you interact with the patient.\n"
        elif self.bias_present == "status_quo":
            return "\nYour hosptial has been diagnosing these patient's symptoms with cancer for the past 10 years. This affects how you interact with the patient.\n"
        elif self.bias_present == "confirmation":
            return "\nYou are initially confident that the patient has cancer. This affects how you interact with the patient.\n"
        elif self.bias_present == "gender":
            return "\nYou are uncomfortable with your patient because you find out that they are a particular gender and you do not trust their judgement. This affects how you interact with them.\n"
        elif self.bias_present == "race":
            return "\nYou are uncomfortable with your patient because you find out that they are a particular race and you do not trust their judgement. This affects how you interact with them.\n"
        elif self.bias_present == "sexual_orientation":
            return "\nYou are uncomfortable with your patient because you find out that they are a particular sexual orientation and you do not trust their judgement. This affects how you interact with them.\n"
        elif self.bias_present == "cultural":
            return "\nYou are uncomfortable with your patient because you find out that they are from a particular culture and you do not trust their judgement. This affects how you interact with them.\n"
        elif self.bias_present == "education":
            return "\nYou are uncomfortable with your patient because you find out that they are uneducated and you do not trust their judgement. This affects how you interact with them.\n"
        elif self.bias_present == "religion":
            return "\nYou are uncomfortable with your patient because you find out that they believe in a particular religion and you do not trust their judgement. This affects how you interact with them.\n"
        elif self.bias_present == "socioeconomic":
            return "\nYou are uncomfortable with your patient because you find out that they are from a particular socioeconomic background and you do not trust their judgement. This affects how you interact with them.\n"
        elif self.bias_present is None:
            pass
        else:
            print("BIAS TYPE {} NOT SUPPORTED, ignoring bias...".format(self.bias_present))
        return ""

    def inference_doctor(self, question, image_requested=False) -> str:
        if self.infs >= self.MAX_INFS: return "Maximum inferences reached"
        
        prompt = "\nHere is a history of your dialogue: " + self.agent_hist + "\n Here was the patient response: " + question + "Now please continue your dialogue\nDoctor: "
        
        image_url = None
        if hasattr(self.scenario, 'image_url') and self.scenario.image_url and image_requested:
            image_url = self.scenario.image_url

        episode_id = f"doctor_grok_scen_{id(self.scenario)}_inf_{self.infs}"
        result = self.agent.run(prompt, image_url=image_url, episode_id=episode_id)
        
        answer = ""
        if result and "result" in result:
             answer = str(result["result"])
        elif result and "tool" in result:
             answer = str(result.get("result", ""))
        else:
             answer = "Error: No response from agent."
             
        self.agent_hist += question + "\n\n" + answer + "\n\n"
        self.infs += 1
        return answer

    def system_prompt(self) -> str:
        return ""

    def reset(self) -> None:
        self.agent_hist = ""
        self.presentation = self.scenario.examiner_information()
        bias_prompt = ""
        if self.bias_present is not None:
            bias_prompt = self.generate_bias()
        
        base_context = "Context:\nYou are a doctor named Dr. Agent questioning a patient.\n" 
        objective = f"Your Objective: {self.presentation}\n"
        limit = f"You have {self.MAX_INFS} questions total.\n"
        
        self.agent_hist = f"{base_context}\n{objective}\n{limit}\n{bias_prompt}\nDialogue History:\n"


def compare_results(diagnosis, correct_diagnosis, moderator_llm):
    # Use standard query_model for moderator, it's fine.
    answer = query_model(moderator_llm, "\nHere is the correct diagnosis: " + correct_diagnosis + "\n Here was the doctor dialogue: " + diagnosis + "\nAre these the same?", "You are responsible for determining if the corrent diagnosis and the doctor diagnosis are the same disease. Please respond only with Yes or No. Nothing else.")
    return answer.lower()


def main(api_key, inf_type, doctor_bias, patient_bias, doctor_llm, patient_llm, measurement_llm, moderator_llm, num_scenarios, dataset, img_request, total_inferences, output_file=None, scenario_offset=0):
    global client
    if api_key:
        client = OpenAI(api_key=api_key)
    elif os.environ.get("OPENAI_API_KEY"):
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    
    # OpenRouter support
    openrouter_key = os.environ.get("OPENROUTER_API_KEY")
    if openrouter_key and ("/" in doctor_llm or "/" in patient_llm or "/" in measurement_llm or "openrouter" in (str(doctor_llm)+str(patient_llm)).lower()):
        client = OpenAI(api_key=openrouter_key, base_url="https://openrouter.ai/api/v1")
        print("Using OpenRouter API")
    
    if not client:
        print("Warning: No API key provided for OpenAI client.")

    # Load MedQA, MIMICIV or NEJM agent case scenarios
    if dataset == "MedQA":
        scenario_loader = ScenarioLoaderMedQA()
    elif dataset == "MedQA_Ext":
        scenario_loader = ScenarioLoaderMedQAExtended()
    elif dataset == "NEJM":
        scenario_loader = ScenarioLoaderNEJM()
    elif dataset == "NEJM_Ext":
        scenario_loader = ScenarioLoaderNEJMExtended()
    elif dataset == "MIMICIV":
        scenario_loader = ScenarioLoaderMIMICIV()
    else:
        raise Exception("Dataset {} does not exist".format(str(dataset)))
    total_correct = 0
    total_presents = 0

    if num_scenarios is None: num_scenarios = scenario_loader.num_scenarios
    
    start_id = scenario_offset
    end_id = min(scenario_offset + num_scenarios, scenario_loader.num_scenarios)
    
    for _scenario_id in range(start_id, end_id):
        total_presents += 1
        pi_dialogue = str()
        # Initialize scenarios (MedQA/NEJM)
        scenario =  scenario_loader.get_scenario(id=_scenario_id)
        # Initialize agents
        meas_agent = MeasurementAgent(
            scenario=scenario,
            backend_str=measurement_llm)
        patient_agent = PatientAgent(
            scenario=scenario, 
            bias_present=patient_bias,
            backend_str=patient_llm)
        
        # Instantiate Doctor Agent
        if doctor_llm == "doctor_grok" or "custom" in doctor_llm:
            print(f"Initializing CustomDoctorAgent with {doctor_llm}")
            doctor_agent = CustomDoctorAgent(
                scenario=scenario, 
                bias_present=doctor_bias,
                backend_str=doctor_llm,
                max_infs=total_inferences, 
                img_request=img_request)
        else:
            doctor_agent = DoctorAgent(
                scenario=scenario, 
                bias_present=doctor_bias,
                backend_str=doctor_llm,
                max_infs=total_inferences, 
                img_request=img_request)

        print(f"\n\n================================================================")
        print(f"STARTING SCENARIO {_scenario_id}")
        print(f"================================================================")
        print(f"EXAMINER INFO (Goal): {scenario.examiner_information()}")
        print(f"PATIENT INFO (Hidden): {scenario.patient_information()}")
        if dataset in ["NEJM", "NEJM_Ext"] and hasattr(scenario, 'question'):
             print(f"SCENARIO QUESTION: {scenario.question}")
        print(f"================================================================")

        dialogue_log = []

        doctor_dialogue = ""
        for _inf_id in range(total_inferences):
            # Check for medical image request
            if dataset == "NEJM":
                if img_request:
                    imgs = "REQUEST IMAGES" in doctor_dialogue
                else: imgs = True
            else: imgs = False
            # Check if final inference
            if _inf_id == total_inferences - 1:
                pi_dialogue += "This is the final question. Please provide a diagnosis.\n"
            # Obtain doctor dialogue (human or llm agent)
            if inf_type == "human_doctor":
                doctor_dialogue = input("\nQuestion for patient: ")
            else: 
                doctor_dialogue = doctor_agent.inference_doctor(pi_dialogue, image_requested=imgs)
            print("Doctor [{}%]:".format(int(((_inf_id+1)/total_inferences)*100)), doctor_dialogue)
            dialogue_log.append(f"Doctor: {doctor_dialogue}")

            # Doctor has arrived at a diagnosis, check correctness
            if "DIAGNOSIS READY" in doctor_dialogue:
                correctness = compare_results(doctor_dialogue, scenario.diagnosis_information(), moderator_llm) == "yes"
                if correctness: total_correct += 1
                print("\nCorrect answer:", scenario.diagnosis_information())
                print("Scene {}, The diagnosis was ".format(_scenario_id), "CORRECT" if correctness else "INCORRECT", int((total_correct/total_presents)*100))
                
                if output_file:
                    result_record = {
                        "dataset": dataset,
                        "scenario_id": _scenario_id,
                        "problem_info": scenario.scenario_dict,
                        "correct_diagnosis": str(scenario.diagnosis_information()),
                        "model_diagnosis": doctor_dialogue,
                        "correct": correctness,
                        "dialogue_history": dialogue_log
                    }
                    with open(output_file, "a") as f:
                        f.write(json.dumps(result_record) + "\n")
                break
            
            # Obtain medical exam from measurement reader
            if "REQUEST TEST" in doctor_dialogue:
                pi_dialogue = meas_agent.inference_measurement(doctor_dialogue,)
                print("Measurement [{}%]:".format(int(((_inf_id+1)/total_inferences)*100)), pi_dialogue)
                dialogue_log.append(f"Measurement: {pi_dialogue}")
                patient_agent.add_hist(pi_dialogue)
            # Obtain response from patient
            else:
                if inf_type == "human_patient":
                    pi_dialogue = input("\nResponse to doctor: ")
                else:
                    pi_dialogue = patient_agent.inference_patient(doctor_dialogue)
                print("Patient [{}%]:".format(int(((_inf_id+1)/total_inferences)*100)), pi_dialogue)
                dialogue_log.append(f"Patient: {pi_dialogue}")
                meas_agent.add_hist(pi_dialogue)
            
            # Prevent API timeouts
            time.sleep(1.0)
        
        else:
             # Loop finished without diagnosis
            if output_file:
                result_record = {
                    "dataset": dataset,
                    "scenario_id": _scenario_id,
                    "problem_info": scenario.scenario_dict,
                    "correct_diagnosis": str(scenario.diagnosis_information()),
                    "model_diagnosis": "No diagnosis reached",
                    "correct": False,
                    "dialogue_history": dialogue_log
                }
                with open(output_file, "a") as f:
                    f.write(json.dumps(result_record) + "\n")



class ScenarioMedQA:
    def __init__(self, scenario_dict) -> None:
        self.scenario_dict = scenario_dict
        self.tests = scenario_dict["OSCE_Examination"]["Test_Results"]
        self.diagnosis = scenario_dict["OSCE_Examination"]["Correct_Diagnosis"]
        self.patient_info  = scenario_dict["OSCE_Examination"]["Patient_Actor"]
        self.examiner_info  = scenario_dict["OSCE_Examination"]["Objective_for_Doctor"]
        self.physical_exams = scenario_dict["OSCE_Examination"]["Physical_Examination_Findings"]
    
    def patient_information(self) -> dict:
        return self.patient_info

    def examiner_information(self) -> dict:
        return self.examiner_info
    
    def exam_information(self) -> dict:
        exams = self.physical_exams
        exams["tests"] = self.tests
        return exams
    
    def diagnosis_information(self) -> dict:
        return self.diagnosis


class ScenarioLoaderMedQA:
    def __init__(self) -> None:
        with open("agentclinic_medqa.jsonl", "r") as f:
            self.scenario_strs = [json.loads(line) for line in f]
        self.scenarios = [ScenarioMedQA(_str) for _str in self.scenario_strs]
        self.num_scenarios = len(self.scenarios)
    
    def sample_scenario(self):
        return self.scenarios[random.randint(0, len(self.scenarios)-1)]
    
    def get_scenario(self, id):
        if id is None: return self.sample_scenario()
        return self.scenarios[id]
        

class ScenarioMedQAExtended:
    def __init__(self, scenario_dict) -> None:
        self.scenario_dict = scenario_dict
        self.tests = scenario_dict["OSCE_Examination"]["Test_Results"]
        self.diagnosis = scenario_dict["OSCE_Examination"]["Correct_Diagnosis"]
        self.patient_info  = scenario_dict["OSCE_Examination"]["Patient_Actor"]
        self.examiner_info  = scenario_dict["OSCE_Examination"]["Objective_for_Doctor"]
        self.physical_exams = scenario_dict["OSCE_Examination"]["Physical_Examination_Findings"]
    
    def patient_information(self) -> dict:
        return self.patient_info

    def examiner_information(self) -> dict:
        return self.examiner_info
    
    def exam_information(self) -> dict:
        exams = self.physical_exams
        exams["tests"] = self.tests
        return exams
    
    def diagnosis_information(self) -> dict:
        return self.diagnosis


class ScenarioLoaderMedQAExtended:
    def __init__(self) -> None:
        with open("agentclinic_medqa_extended.jsonl", "r") as f:
            self.scenario_strs = [json.loads(line) for line in f]
        self.scenarios = [ScenarioMedQAExtended(_str) for _str in self.scenario_strs]
        self.num_scenarios = len(self.scenarios)
    
    def sample_scenario(self):
        return self.scenarios[random.randint(0, len(self.scenarios)-1)]
    
    def get_scenario(self, id):
        if id is None: return self.sample_scenario()
        return self.scenarios[id]
        

class ScenarioMIMICIVQA:
    def __init__(self, scenario_dict) -> None:
        self.scenario_dict = scenario_dict
        self.tests = scenario_dict["OSCE_Examination"]["Test_Results"]
        self.diagnosis = scenario_dict["OSCE_Examination"]["Correct_Diagnosis"]
        self.patient_info  = scenario_dict["OSCE_Examination"]["Patient_Actor"]
        self.examiner_info  = scenario_dict["OSCE_Examination"]["Objective_for_Doctor"]
        self.physical_exams = scenario_dict["OSCE_Examination"]["Physical_Examination_Findings"]
    
    def patient_information(self) -> dict:
        return self.patient_info

    def examiner_information(self) -> dict:
        return self.examiner_info
    
    def exam_information(self) -> dict:
        exams = self.physical_exams
        exams["tests"] = self.tests
        return exams
    
    def diagnosis_information(self) -> dict:
        return self.diagnosis


class ScenarioLoaderMIMICIV:
    def __init__(self) -> None:
        with open("agentclinic_mimiciv.jsonl", "r") as f:
            self.scenario_strs = [json.loads(line) for line in f]
        self.scenarios = [ScenarioMIMICIVQA(_str) for _str in self.scenario_strs]
        self.num_scenarios = len(self.scenarios)
    
    def sample_scenario(self):
        return self.scenarios[random.randint(0, len(self.scenarios)-1)]
    
    def get_scenario(self, id):
        if id is None: return self.sample_scenario()
        return self.scenarios[id]


class ScenarioNEJMExtended:
    def __init__(self, scenario_dict) -> None:
        self.scenario_dict = scenario_dict 
        self.question = scenario_dict["question"] 
        self.image_url = scenario_dict["image_url"] 
        self.diagnosis = [_sd["text"] 
            for _sd in scenario_dict["answers"] if _sd["correct"]][0]
        self.patient_info = scenario_dict["patient_info"]
        self.physical_exams = scenario_dict["physical_exams"]

    def patient_information(self) -> str:
        patient_info = self.patient_info
        return patient_info

    def examiner_information(self) -> str:
        return "What is the most likely diagnosis?"
    
    def exam_information(self) -> str:
        exams = self.physical_exams
        return exams
    
    def diagnosis_information(self) -> str:
        return self.diagnosis


class ScenarioLoaderNEJMExtended:
    def __init__(self) -> None:
        with open("agentclinic_nejm_extended.jsonl", "r") as f:
            self.scenario_strs = [json.loads(line) for line in f]
        self.scenarios = [ScenarioNEJMExtended(_str) for _str in self.scenario_strs]
        self.num_scenarios = len(self.scenarios)
    
    def sample_scenario(self):
        return self.scenarios[random.randint(0, len(self.scenarios)-1)]
    
    def get_scenario(self, id):
        if id is None: return self.sample_scenario()
        return self.scenarios[id]


class ScenarioNEJM:
    def __init__(self, scenario_dict) -> None:
        self.scenario_dict = scenario_dict 
        self.question = scenario_dict["question"] 
        self.image_url = scenario_dict["image_url"] 
        self.diagnosis = [_sd["text"] 
            for _sd in scenario_dict["answers"] if _sd["correct"]][0]
        self.patient_info = scenario_dict["patient_info"]
        self.physical_exams = scenario_dict["physical_exams"]

    def patient_information(self) -> str:
        patient_info = self.patient_info
        return patient_info

    def examiner_information(self) -> str:
        return "What is the most likely diagnosis?"
    
    def exam_information(self) -> str:
        exams = self.physical_exams
        return exams
    
    def diagnosis_information(self) -> str:
        return self.diagnosis


class ScenarioLoaderNEJM:
    def __init__(self) -> None:
        with open("agentclinic_nejm.jsonl", "r") as f:
            self.scenario_strs = [json.loads(line) for line in f]
        self.scenarios = [ScenarioNEJM(_str) for _str in self.scenario_strs]
        self.num_scenarios = len(self.scenarios)
    
    def sample_scenario(self):
        return self.scenarios[random.randint(0, len(self.scenarios)-1)]
    
    def get_scenario(self, id):
        if id is None: return self.sample_scenario()
        return self.scenarios[id]


class PatientAgent:
    def __init__(self, scenario, backend_str="z-ai/glm-4.6v", bias_present=None) -> None:
        self.disease = ""
        self.symptoms = ""
        self.agent_hist = ""
        self.backend = backend_str
        self.bias_present = (None if bias_present == "None" else bias_present)
        self.scenario = scenario
        self.reset()
        self.biases = ["recency", "frequency", "false_consensus", "self_diagnosis", "gender", "race", "sexual_orientation", "cultural", "education", "religion", "socioeconomic"]

    def generate_bias(self) -> str:
        if self.bias_present == "recency":
            return "\nRecently, you had a friend with similar symptoms to yours that was diagnosed with cancer. This affects how you interact with the doctor.\n"
        elif self.bias_present == "frequency":
            return "\nYou recently learned that most frequently, doctors diagnose this as cancer based on past cases. This affects how you interact with the doctor.\n"
        elif self.bias_present == "false_consensus":
            return "\nMost of your friends who heard about your symptoms believe that you have cancer. This affects how you interact with the doctor.\n"
        elif self.bias_present == "self_diagnosis":
            return "\nYou recently performed a thorough investigation of your symptoms online and have come to the conclusion that you should be diagnosed with cancer. While the doctor may believe otherwise you remain convinced you have cancer. This affects how you interact with the doctor.\n"
        elif self.bias_present == "gender":
            return "\nYou are uncomfortable with your doctor because you find out that they are a particular gender and you do not trust their judgement. This affects how you interact with them.\n"
        elif self.bias_present == "race":
            return "\nYou are uncomfortable with your doctor because you find out that they are a particular race and you do not trust their judgement. This affects how you interact with them.\n"
        elif self.bias_present == "sexual_orientation":
            return "\nYou are uncomfortable with your doctor because you find out that they are a particular sexual orientation and you do not trust their judgement. This affects how you interact with them.\n"
        elif self.bias_present == "cultural":
            return "\nYou are uncomfortable with your doctor because you find out that they are from a particular culture and you do not trust their judgement. This affects how you interact with them.\n"
        elif self.bias_present == "education":
            return "\nYou are uncomfortable with your doctor because you find out that they went to a low ranked medical school and you do not trust their judgement. This affects how you interact with them.\n"
        elif self.bias_present == "religion":
            return "\nYou are uncomfortable with your doctor because you find out that they believe in a particular religion and you do not trust their judgement. This affects how you interact with them.\n"
        elif self.bias_present == "socioeconomic":
            return "\nYou are uncomfortable with your doctor because you find out that they are from a particular socioeconomic background and you do not trust their judgement. This affects how you interact with them.\n"
        elif self.bias_present is None:
            pass
        else:
            print("BIAS TYPE {} NOT SUPPORTED, ignoring bias...".format(self.bias_present))
        return ""

    def inference_patient(self, question) -> str:
        answer = query_model(self.backend, "\nHere is a history of your dialogue: " + self.agent_hist + "\n Here was the doctor response: " + question + "Now please continue your dialogue\nPatient: ", self.system_prompt())
        self.agent_hist += question + "\n\n" + answer + "\n\n"
        return answer

    def system_prompt(self) -> str:
        bias_prompt = ""
        if self.bias_present is not None:
            bias_prompt = self.generate_bias()
        base = """You are a patient in a clinic who only responds in the form of dialogue. You are being inspected by a doctor who will ask you questions and will perform exams on you in order to understand your disease. Your answer will only be 1-3 sentences in length."""
        symptoms = "\n\nBelow is all of your information. {}. \n\n Remember, you must not reveal your disease explicitly but may only convey the symptoms you have in the form of dialogue if you are asked.".format(self.symptoms)
        return base + bias_prompt + symptoms
    
    def reset(self) -> None:
        self.agent_hist = ""
        self.symptoms = self.scenario.patient_information()

    def add_hist(self, hist_str) -> None:
        self.agent_hist += hist_str + "\n\n"


class DoctorAgent:
    def __init__(self, scenario, backend_str="z-ai/glm-4.6v", max_infs=20, bias_present=None, img_request=False) -> None:
        self.infs = 0
        self.MAX_INFS = max_infs
        self.agent_hist = ""
        self.presentation = ""
        self.backend = backend_str
        self.bias_present = (None if bias_present == "None" else bias_present)
        self.scenario = scenario
        self.reset()
        self.img_request = img_request
        self.biases = ["recency", "frequency", "false_consensus", "confirmation", "status_quo", "gender", "race", "sexual_orientation", "cultural", "education", "religion", "socioeconomic"]

    def generate_bias(self) -> str:
        if self.bias_present == "recency":
            return "\nRecently, you learned that a doctor with similar symptoms to the patient that diagnosed their patient with cancer. This affects how you interact with the patient.\n"
        elif self.bias_present == "frequency":
            return "\nYou recently learned that most frequently, doctors diagnose patients with similar symptoms with cancer based on past cases. This affects how you interact with the patient.\n"
        elif self.bias_present == "false_consensus":
            return "\nMost of your colleagues who heard about the patient's symptoms believe that they have cancer. This affects how you interact with the patient.\n"
        elif self.bias_present == "status_quo":
            return "\nYour hosptial has been diagnosing these patient's symptoms with cancer for the past 10 years. This affects how you interact with the patient.\n"
        elif self.bias_present == "confirmation":
            return "\nYou are initially confident that the patient has cancer. This affects how you interact with the patient.\n"
        elif self.bias_present == "gender":
            return "\nYou are uncomfortable with your patient because you find out that they are a particular gender and you do not trust their judgement. This affects how you interact with them.\n"
        elif self.bias_present == "race":
            return "\nYou are uncomfortable with your patient because you find out that they are a particular race and you do not trust their judgement. This affects how you interact with them.\n"
        elif self.bias_present == "sexual_orientation":
            return "\nYou are uncomfortable with your patient because you find out that they are a particular sexual orientation and you do not trust their judgement. This affects how you interact with them.\n"
        elif self.bias_present == "cultural":
            return "\nYou are uncomfortable with your patient because you find out that they are from a particular culture and you do not trust their judgement. This affects how you interact with them.\n"
        elif self.bias_present == "education":
            return "\nYou are uncomfortable with your patient because you find out that they are uneducated and you do not trust their judgement. This affects how you interact with them.\n"
        elif self.bias_present == "religion":
            return "\nYou are uncomfortable with your patient because you find out that they believe in a particular religion and you do not trust their judgement. This affects how you interact with them.\n"
        elif self.bias_present == "socioeconomic":
            return "\nYou are uncomfortable with your patient because you find out that they are from a particular socioeconomic background and you do not trust their judgement. This affects how you interact with them.\n"
        elif self.bias_present is None:
            pass
        else:
            print("BIAS TYPE {} NOT SUPPORTED, ignoring bias...".format(self.bias_present))
        return ""

    def inference_doctor(self, question, image_requested=False) -> str:
        answer = str()
        if self.infs >= self.MAX_INFS: return "Maximum inferences reached"
        answer = query_model(self.backend, "\nHere is a history of your dialogue: " + self.agent_hist + "\n Here was the patient response: " + question + "Now please continue your dialogue\nDoctor: ", self.system_prompt(), image_requested=image_requested, scene=self.scenario)
        self.agent_hist += question + "\n\n" + answer + "\n\n"
        self.infs += 1
        return answer

    def system_prompt(self) -> str:
        bias_prompt = ""
        if self.bias_present is not None:
            bias_prompt = self.generate_bias()
        base = "You are a doctor named Dr. Agent who only responds in the form of dialogue. You are inspecting a patient who you will ask questions in order to understand their disease. You are only allowed to ask {} questions total before you must make a decision. You have asked {} questions so far. You can request test results using the format \"REQUEST TEST: [test]\". For example, \"REQUEST TEST: Chest_X-Ray\". Your dialogue will only be 1-3 sentences in length. Once you have decided to make a diagnosis please type \"DIAGNOSIS READY: [diagnosis here]\"".format(self.MAX_INFS, self.infs) + ("You may also request medical images related to the disease to be returned with \"REQUEST IMAGES\"." if self.img_request else "")
        presentation = "\n\nBelow is all of the information you have. {}. \n\n Remember, you must discover their disease by asking them questions. You are also able to provide exams.".format(self.presentation)
        return base + bias_prompt + presentation

    def reset(self) -> None:
        self.agent_hist = ""
        self.presentation = self.scenario.examiner_information()


class MeasurementAgent:
    def __init__(self, scenario, backend_str="z-ai/glm-4.6v") -> None:
        self.agent_hist = ""
        self.presentation = ""
        self.backend = backend_str
        self.scenario = scenario
        self.reset()

    def inference_measurement(self, question) -> str:
        answer = str()
        answer = query_model(self.backend, "\nHere is a history of the dialogue: " + self.agent_hist + "\n Here was the doctor measurement request: " + question, self.system_prompt())
        self.agent_hist += question + "\n\n" + answer + "\n\n"
        return answer

    def system_prompt(self) -> str:
        base = "You are an measurement reader who responds with medical test results. Please respond in the format \"RESULTS: [results here]\""
        presentation = "\n\nBelow is all of the information you have. {}. \n\n If the requested results are not in your data then you can respond with NORMAL READINGS.".format(self.information)
        return base + presentation
    
    def add_hist(self, hist_str) -> None:
        self.agent_hist += hist_str + "\n\n"

    def reset(self) -> None:
        self.agent_hist = ""
        self.information = self.scenario.exam_information()




if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Medical Diagnosis Simulation CLI')
    parser.add_argument('--openai_api_key', type=str, required=False, help='OpenAI API Key')
    parser.add_argument('--inf_type', type=str, choices=['llm', 'human_doctor', 'human_patient'], default='llm')
    parser.add_argument('--doctor_bias', type=str, help='Doctor bias type', default='None', choices=["recency", "frequency", "false_consensus", "confirmation", "status_quo", "gender", "race", "sexual_orientation", "cultural", "education", "religion", "socioeconomic"])
    parser.add_argument('--patient_bias', type=str, help='Patient bias type', default='None', choices=["recency", "frequency", "false_consensus", "self_diagnosis", "gender", "race", "sexual_orientation", "cultural", "education", "religion", "socioeconomic"])
    parser.add_argument('--doctor_llm', type=str, default='z-ai/glm-4.6v')
    parser.add_argument('--patient_llm', type=str, default='z-ai/glm-4.6v')
    parser.add_argument('--measurement_llm', type=str, default='z-ai/glm-4.6v')
    parser.add_argument('--moderator_llm', type=str, default='z-ai/glm-4.6v')
    parser.add_argument('--agent_dataset', type=str, default='MedQA') # MedQA, MIMICIV or NEJM
    parser.add_argument('--doctor_image_request', type=bool, default=False) # whether images must be requested or are provided
    parser.add_argument('--num_scenarios', type=int, default=None, required=False, help='Number of scenarios to simulate')
    parser.add_argument('--total_inferences', type=int, default=20, required=False, help='Number of inferences between patient and doctor')
    
    parser.add_argument('--output_file', type=str, default=None, required=False, help='File to append results to')
    parser.add_argument('--scenario_offset', type=int, default=0, required=False, help='Scenario ID to start from')
    args = parser.parse_args()

    main(args.openai_api_key, args.inf_type, args.doctor_bias, args.patient_bias, args.doctor_llm, args.patient_llm, args.measurement_llm, args.moderator_llm, args.num_scenarios, args.agent_dataset, args.doctor_image_request, args.total_inferences, args.output_file, args.scenario_offset)
