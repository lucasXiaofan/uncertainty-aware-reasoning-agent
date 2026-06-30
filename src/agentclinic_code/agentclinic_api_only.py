import argparse
import importlib.util
from openai import OpenAI
import re
import random
import time
import json
import os
import inspect
from dotenv import load_dotenv
load_dotenv()
import sys
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CODE_DIR.parents[1]
DATA_DIR = CODE_DIR / "data"
AGENT_RUNTIME_DIR = CODE_DIR / "agent_runtime"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))
if str(AGENT_RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_RUNTIME_DIR))

from src.agent.logging import AgentRunLogger


# Global client variable
client = None


def _resolve_data_path(path_str: str | None, default_name: str | None = None) -> Path:
    if path_str:
        candidate = Path(path_str).expanduser()
        if candidate.is_absolute():
            return candidate
        if candidate.exists():
            return candidate.resolve()
        data_candidate = DATA_DIR / candidate
        if data_candidate.exists():
            return data_candidate.resolve()
        return candidate.resolve()

    if not default_name:
        raise ValueError("No data file provided and no default configured")
    return (DATA_DIR / default_name).resolve()


def _resolve_custom_agent_path(path_str: str | None) -> Path | None:
    if not path_str:
        return None

    candidate = Path(path_str).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    if candidate.exists():
        return candidate.resolve()

    code_candidate = CODE_DIR / candidate
    if code_candidate.exists():
        return code_candidate.resolve()
    return candidate.resolve()


def _normalize_response_text(content):
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for chunk in content:
            if isinstance(chunk, dict):
                text_value = chunk.get("text")
                if isinstance(text_value, str):
                    parts.append(text_value)
            elif isinstance(chunk, str):
                parts.append(chunk)
        return "".join(parts)
    return str(content)


def _try_parse_json_object(text):
    if not isinstance(text, str):
        return None
    stripped = text.strip()
    if not stripped:
        return None

    try:
        value = json.loads(stripped)
        if isinstance(value, dict):
            return value
    except Exception:
        pass

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and start < end:
        candidate = stripped[start:end + 1]
        try:
            value = json.loads(candidate)
            if isinstance(value, dict):
                return value
        except Exception:
            pass
    return None


def _usage_to_dict(usage) -> dict:
    if not usage:
        return {}
    if hasattr(usage, "model_dump"):
        return usage.model_dump()
    if isinstance(usage, dict):
        return usage
    return {
        "prompt_tokens": getattr(usage, "prompt_tokens", 0),
        "completion_tokens": getattr(usage, "completion_tokens", 0),
        "total_tokens": getattr(usage, "total_tokens", 0),
        "input_tokens": getattr(usage, "input_tokens", getattr(usage, "prompt_tokens", 0)),
        "output_tokens": getattr(usage, "output_tokens", getattr(usage, "completion_tokens", 0)),
    }


def query_model(model_str, prompt, system_prompt, tries=30, timeout=20.0, image_requested=False, scene=None, max_prompt_len=2**14, clip_prompt=False, return_usage=False, response_format_schema=None):
    global client
    # Simplified model check - focusing on API models
    if model_str not in ["gpt4", "gpt3.5", "gpt4o", "gpt-4o-mini", "gpt4v", "o1-preview", "gpt-5-mini", "gpt-5-nano"] and "gpt" not in model_str and "/" not in model_str:
         # Allow other gpt models if they follow the same API
         pass

    for _ in range(tries):
        if clip_prompt:
            prompt = prompt[:max_prompt_len]

        structured_modes = ["plain"]
        if response_format_schema is not None:
            structured_modes = ["schema", "prompt_json"]

        for structured_mode in structured_modes:
            try:
                if not client:
                    # Fallback init if not set in main (e.g. env var)
                    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

                active_prompt = prompt
                if structured_mode == "prompt_json":
                    active_prompt = (
                        prompt
                        + "\n\nRespond ONLY as valid JSON with exactly these keys: "
                        + '{"answer": "<doctor dialogue>", "uncertainty_reasoning": "<top 3 likely diagnoses; why likely; what differentiates them>"}'
                    )

                if image_requested:
                    messages = [
                        {"role": "system", "content": system_prompt},
                        {"role": "user",
                        "content": [
                            {"type": "text", "text": active_prompt},
                            {"type": "image_url",
                                "image_url": {
                                    "url": "{}".format(scene.image_url),
                                },
                            },
                        ]},]
                    # Unified chat completion call for vision/multimodal if supported by model
                    # For now, mapping specific models to their vision counterparts or just passing through
                    model_to_use = model_str
                    if model_str == "gpt4v":
                        model_to_use = "gpt-4-vision-preview"

                    # Determine token parameter based on model
                    token_param = "max_tokens"
                    if "gpt-5" in model_str or "o1" in model_str:
                        token_param = "max_completion_tokens"

                    kwargs = {
                        "model": model_to_use,
                        "messages": messages,
                        "temperature": 0.5,
                        token_param: 16000 if token_param == "max_completion_tokens" else 10000
                    }
                    if structured_mode == "schema":
                        kwargs["response_format"] = {
                            "type": "json_schema",
                            "json_schema": {
                                "name": "doctor_structured_turn",
                                "strict": True,
                                "schema": response_format_schema,
                            },
                        }

                    response = client.chat.completions.create(**kwargs)
                    answer = _normalize_response_text(response.choices[0].message.content)
                    if not answer:
                        print(f"DEBUG: Empty response from model {model_to_use}. Full response: {response}")

                    if response_format_schema is not None:
                        structured_answer = _try_parse_json_object(answer)
                        if not structured_answer:
                            raise ValueError("Structured response parsing failed")
                        if return_usage:
                            usage = response.usage if hasattr(response, 'usage') else None
                            return structured_answer, usage
                        return structured_answer

                    # Return usage if requested
                    if return_usage:
                        usage = response.usage if hasattr(response, 'usage') else None
                        return answer, usage

                else: # Text only
                    messages = [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": active_prompt}]

                    model_to_use = model_str
                    if model_str == "gpt4":
                        model_to_use = "gpt-4-turbo-preview"
                    elif model_str == "gpt3.5":
                        model_to_use = "gpt-3.5-turbo"
                    elif model_str == "o1-preview":
                        model_to_use = "o1-preview-2024-09-12"

                    # Special handling for o1-preview which might not support system prompt in the same way or other quirks
                    # But keeping it simple as per original code structure
                    if model_str == "o1-preview":
                        messages = [{"role": "user", "content": system_prompt + active_prompt}]

                    # Determine token parameter based on model
                    token_param = "max_tokens"
                    if "gpt-5" in model_str or "o1" in model_str:
                        token_param = "max_completion_tokens" # Use compatible parameter for reasoning models

                    kwargs = {
                        "model": model_to_use,
                        "messages": messages,
                        token_param: 16000 if token_param == "max_completion_tokens" else 4096
                    }
                    if structured_mode == "schema":
                        kwargs["response_format"] = {
                            "type": "json_schema",
                            "json_schema": {
                                "name": "doctor_structured_turn",
                                "strict": True,
                                "schema": response_format_schema,
                            },
                        }

                    # Handle o1-preview special case (no max tokens limit usually or high limit)
                    if model_str == "o1-preview":
                        kwargs[token_param] = None

                    response = client.chat.completions.create(**kwargs)
                    answer = _normalize_response_text(response.choices[0].message.content)
                    if not answer:
                        print(f"DEBUG: Empty response from model {model_to_use}. Full response: {response}")

                    if response_format_schema is not None:
                        structured_answer = _try_parse_json_object(answer)
                        if not structured_answer:
                            raise ValueError("Structured response parsing failed")
                        if return_usage:
                            usage = response.usage if hasattr(response, 'usage') else None
                            return structured_answer, usage
                        return structured_answer

                    answer = re.sub(r"\s+", " ", answer)

                    # Return usage if requested
                    if return_usage:
                        usage = response.usage if hasattr(response, 'usage') else None
                        return answer, usage

                return answer

            except Exception as e:
                print(f"Error querying model {model_str}: {e}")
                if structured_mode == "schema" and response_format_schema is not None:
                    # fallback to prompt-level JSON request when schema mode is unsupported
                    continue
                time.sleep(timeout)
                break
    raise Exception("Max retries: timeout")


def compare_results(diagnosis, correct_diagnosis, moderator_llm):
    # Use standard query_model for moderator, it's fine.
    answer = query_model(moderator_llm, "\nHere is the correct diagnosis: " + correct_diagnosis + "\n Here was the doctor dialogue: " + diagnosis + "\nAre these the same?", "You are responsible for determining if the corrent diagnosis and the doctor diagnosis are the same disease. Please respond only with Yes or No. Nothing else.")
    return answer.lower()


def _load_doctor_agent_class(custom_agent_path: str | None):
    if not custom_agent_path:
        return DoctorAgent

    agent_path = _resolve_custom_agent_path(custom_agent_path)
    if agent_path is None or not agent_path.exists():
        raise FileNotFoundError(f"Custom doctor agent file not found: {custom_agent_path}")

    spec = importlib.util.spec_from_file_location(f"custom_doctor_agent_{agent_path.stem}", agent_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load custom doctor agent module from {agent_path}")

    module = importlib.util.module_from_spec(spec)
    module.query_model = query_model
    module.DoctorAgentBase = DoctorAgent
    module.CODE_DIR = CODE_DIR
    module.DATA_DIR = DATA_DIR
    spec.loader.exec_module(module)

    agent_cls = getattr(module, "CustomDoctorAgent", None) or getattr(module, "DoctorAgent", None)
    if agent_cls is None:
        raise AttributeError(
            f"Custom doctor agent file {agent_path} must define a CustomDoctorAgent or DoctorAgent class"
        )
    if not hasattr(agent_cls, "inference_doctor"):
        raise TypeError(f"Custom doctor agent class in {agent_path} must define inference_doctor(...)")
    return agent_cls


def _finalize_doctor_visualization(
    doctor_agent,
    *,
    dataset,
    scenario_id,
    correct_diagnosis,
    correct,
) -> None:
    finalize = getattr(doctor_agent, "finalize_visualization", None)
    if not callable(finalize):
        return
    path = finalize(
        dataset=dataset,
        scenario_id=scenario_id,
        correct_diagnosis=correct_diagnosis,
        correct=correct,
    )
    print(f"Viewer-ready trajectory: {path}")


def _scenario_environment(dataset_name, scenario) -> dict:
    environment = {"dataset": dataset_name}
    for key, getter in [
        ("scenario", lambda: getattr(scenario, "scenario_dict", {})),
        ("patient", scenario.patient_information),
        ("exam", scenario.exam_information),
        ("diagnosis", scenario.diagnosis_information),
    ]:
        try:
            environment[key] = getter()
        except Exception as exc:
            environment[key] = {"error": str(exc)}
    if hasattr(scenario, "question"):
        environment["question"] = getattr(scenario, "question")
    if hasattr(scenario, "image_url"):
        environment["image_url"] = getattr(scenario, "image_url")
    return environment


def _build_scenario_logger(
    *,
    model: str,
    agent_name: str,
    dataset_name: str,
    scenario_id: int,
    scenario,
    patient_csv: str,
    experiment_id: str | None = None,
    result_csv_path: str | None = None,
    run_log_path: str | Path | None = None,
) -> AgentRunLogger:
    patient_id = getattr(scenario, "patient_id", None) or f"{dataset_name}:{scenario_id}"
    logger = AgentRunLogger(
        model=model,
        path=run_log_path,
        agent_name=agent_name,
        patient_id=patient_id,
        problem=scenario.examiner_information(),
        environment=_scenario_environment(dataset_name, scenario),
        metadata={
            "dataset": dataset_name,
            "scenario_id": scenario_id,
            "patient_id": patient_id,
            "experiment_id": experiment_id,
            "patient_csv": patient_csv,
        },
        result_csv_path=result_csv_path,
    )
    logger.meta.update(
        {
            "patient_id": patient_id,
            "experiment_id": experiment_id,
        }
    )
    return logger


def _scenario_run_log_path(path: str | Path | None, scenario_id: int, total_scenarios: int) -> Path | None:
    if not path:
        return None
    base = Path(path).expanduser()
    if total_scenarios <= 1:
        return base
    return base.with_name(f"{base.stem}_scenario_{scenario_id}{base.suffix or '.json'}")


def _instantiate_doctor_agent(agent_cls, *, logger: AgentRunLogger, **kwargs):
    signature = inspect.signature(agent_cls)
    supports_logger = (
        "logger" in signature.parameters
        or any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in signature.parameters.values()
        )
    )
    if supports_logger:
        return agent_cls(logger=logger, **kwargs)

    doctor_agent = agent_cls(**kwargs)
    doctor_agent.logger = logger
    return doctor_agent


def _token_counts(agent) -> dict:
    return {
        "total_tokens": getattr(agent, "total_tokens", 0),
        "prompt_tokens": getattr(agent, "prompt_tokens", 0),
        "completion_tokens": getattr(agent, "completion_tokens", 0),
    }


def _token_usage(doctor_agent, patient_agent, meas_agent) -> dict:
    doctor = _token_counts(doctor_agent)
    patient = _token_counts(patient_agent)
    measurement = _token_counts(meas_agent)
    return {
        "doctor": doctor,
        "patient": patient,
        "measurement": measurement,
        "total": {
            key: doctor[key] + patient[key] + measurement[key]
            for key in doctor
        },
    }


def _agent_field(agent, *names: str, default=""):
    for name in names:
        value = getattr(agent, name, None)
        if value:
            return value
    return default


def _build_result_record(
    *,
    dataset_name,
    scenario_id,
    scenario,
    doctor_agent,
    patient_agent,
    meas_agent,
    model_diagnosis,
    correct,
    dialogue_log,
    experiment_id=None,
) -> dict:
    patient_id = getattr(scenario, "patient_id", None) or f"{dataset_name}:{scenario_id}"
    return {
        "dataset": dataset_name,
        "scenario_id": scenario_id,
        "patient_id": patient_id,
        "experiment_id": experiment_id,
        "problem_info": scenario.scenario_dict,
        "correct_diagnosis": str(scenario.diagnosis_information()),
        "model_diagnosis": model_diagnosis,
        "model_uncertainty_reasoning": _agent_field(
            doctor_agent,
            "last_uncertainty_reasoning",
        ),
        "differential_diagnosis_list": _agent_field(
            doctor_agent,
            "differential_diagnosis_list",
            "last_uncertainty_reasoning",
        ),
        "osce_note": _agent_field(doctor_agent, "osce_note", "latest_osce_note"),
        "correct": correct,
        "dialogue_history": dialogue_log,
        "token_usage": _token_usage(doctor_agent, patient_agent, meas_agent),
        "session_id": getattr(doctor_agent, "session_id", None),
    }


def _record_final_state(logger: AgentRunLogger, doctor_agent, result_record: dict) -> None:
    logger.highlight(
        "final_agent_state",
        title="Final OSCE note and differential diagnosis",
        data={
            "osce_note": result_record["osce_note"],
            "differential_diagnosis": result_record["differential_diagnosis_list"],
        },
    )
    logger.update_task_result(result_record)


def main(
    api_key,
    inf_type,
    doctor_bias,
    patient_bias,
    doctor_llm,
    patient_llm,
    measurement_llm,
    moderator_llm,
    num_scenarios,
    patient_csv,
    total_inferences,
    output_file=None,
    scenario_offset=0,
    custom_doctor_agent_path=None,
    dataset_name=None,
    run_log_path=None,
    experiment_id=None,
):
    global client
    if api_key:
        client = OpenAI(api_key=api_key)
    elif os.environ.get("OPENAI_API_KEY"):
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    # Optional OpenRouter support for slash-prefixed model ids.
    openrouter_key = os.environ.get("OPENROUTER_API_KEY")
    uses_openrouter = any("/" in str(model_name) for model_name in [doctor_llm, patient_llm, measurement_llm, moderator_llm])
    if openrouter_key and uses_openrouter:
        client = OpenAI(api_key=openrouter_key, base_url="https://openrouter.ai/api/v1")
        print("Using OpenRouter API")
    
    if not client:
        print("Warning: No API key provided for OpenAI client.")

    scenario_loader = ScenarioLoaderOSCE(patient_csv)
    patient_csv_path = str(scenario_loader.path)
    dataset_name = dataset_name or scenario_loader.path.stem
    total_correct = 0
    total_presents = 0

    if num_scenarios is None: num_scenarios = scenario_loader.num_scenarios
    
    start_id = scenario_offset
    end_id = min(scenario_offset + num_scenarios, scenario_loader.num_scenarios)
    doctor_agent_cls = _load_doctor_agent_class(custom_doctor_agent_path)
    
    for _scenario_id in range(start_id, end_id):
        total_presents += 1
        pi_dialogue = str()
        # Initialize OSCE-format scenario.
        scenario =  scenario_loader.get_scenario(id=_scenario_id)
        scenario_logger = _build_scenario_logger(
            model=doctor_llm,
            agent_name=doctor_agent_cls.__name__,
            dataset_name=dataset_name,
            scenario_id=_scenario_id,
            scenario=scenario,
            patient_csv=patient_csv_path,
            experiment_id=experiment_id,
            result_csv_path=output_file,
            run_log_path=_scenario_run_log_path(
                run_log_path,
                _scenario_id,
                end_id - start_id,
            ),
        )
        scenario_logger.event(
            "scenario_start",
            dataset=dataset_name,
            scenario_id=_scenario_id,
            patient_id=getattr(scenario, "patient_id", None) or f"{dataset_name}:{_scenario_id}",
            experiment_id=experiment_id,
            total_inferences=total_inferences,
            patient_csv=patient_csv_path,
        )
        # Initialize agents
        meas_agent = MeasurementAgent(
            scenario=scenario,
            backend_str=measurement_llm)
        patient_agent = PatientAgent(
            scenario=scenario, 
            bias_present=patient_bias,
            backend_str=patient_llm)

        doctor_agent = _instantiate_doctor_agent(
            doctor_agent_cls,
            logger=scenario_logger,
            scenario=scenario,
            bias_present=doctor_bias,
            backend_str=doctor_llm,
            max_infs=total_inferences,
            img_request=False)

        print(f"\n\n================================================================")
        print(f"STARTING SCENARIO {_scenario_id}")
        print(f"================================================================")
        print(f"EXAMINER INFO (Goal): {scenario.examiner_information()}")
        print(f"PATIENT INFO (Hidden): {scenario.patient_information()}")
        print(f"================================================================")

        dialogue_log = []

        doctor_dialogue = ""
        last_environment_source = "task"
        last_environment_response = scenario.examiner_information()
        for _inf_id in range(total_inferences):
            imgs = False
            # Check if final inference
            if _inf_id == total_inferences - 1:
                pi_dialogue += "This is the final question. Please provide a diagnosis.\n"

            # Get memory context from past experiences (optional)
            memory_context = ""
            turn_environment_source = last_environment_source
            turn_environment_response = pi_dialogue or last_environment_response


            # Obtain doctor dialogue (human or llm agent)
            if inf_type == "human_doctor":
                doctor_dialogue = input("\nQuestion for patient: ")
            else:
                doctor_dialogue = doctor_agent.inference_doctor(pi_dialogue, image_requested=imgs, memory_context=memory_context)

            print("Doctor [{}%]:".format(int(((_inf_id+1)/total_inferences)*100)), doctor_dialogue)
            dialogue_log.append(f"Doctor: {doctor_dialogue}")
            current_uncertainty_reasoning = getattr(doctor_agent, "last_uncertainty_reasoning", "")
            if current_uncertainty_reasoning:
                dialogue_log.append(f"Doctor_Uncertainty: {current_uncertainty_reasoning}")
            scenario_logger.doctor_turn(
                inference=_inf_id,
                task=scenario.examiner_information(),
                environment_source=turn_environment_source,
                environment_response=turn_environment_response,
                doctor_response=doctor_dialogue,
                hospital_response=turn_environment_response,
                doctor_message=doctor_dialogue,
                uncertainty_reasoning=current_uncertainty_reasoning,
                metadata={
                    "image_requested": imgs,
                    "memory_context": memory_context,
                },
            )

            # Doctor has arrived at a diagnosis, check correctness
            if "DIAGNOSIS READY" in doctor_dialogue:
                correctness = compare_results(doctor_dialogue, scenario.diagnosis_information(), moderator_llm) == "yes"
                _finalize_doctor_visualization(
                    doctor_agent,
                    dataset=dataset_name,
                    scenario_id=_scenario_id,
                    correct_diagnosis=scenario.diagnosis_information(),
                    correct=correctness,
                )
                if correctness: total_correct += 1
                print("\nCorrect answer:", scenario.diagnosis_information())
                print("Scene {}, The diagnosis was ".format(_scenario_id), "CORRECT" if correctness else "INCORRECT", int((total_correct/total_presents)*100))
                _record_final_state(
                    scenario_logger,
                    doctor_agent,
                    _build_result_record(
                        dataset_name=dataset_name,
                        scenario_id=_scenario_id,
                        scenario=scenario,
                        doctor_agent=doctor_agent,
                        patient_agent=patient_agent,
                        meas_agent=meas_agent,
                        model_diagnosis=doctor_dialogue,
                        correct=correctness,
                        dialogue_log=dialogue_log,
                        experiment_id=experiment_id,
                    ),
                )
                break
            
            # Obtain medical exam from measurement reader
            if "REQUEST TEST" in doctor_dialogue:
                pi_dialogue = meas_agent.inference_measurement(doctor_dialogue,)
                print("Measurement [{}%]:".format(int(((_inf_id+1)/total_inferences)*100)), pi_dialogue)
                dialogue_log.append(f"Measurement: {pi_dialogue}")
                scenario_logger.event(
                    "environment_response",
                    source="measurement",
                    inference=_inf_id,
                    request=doctor_dialogue,
                    response=pi_dialogue,
                )
                patient_agent.add_hist(pi_dialogue)
                last_environment_source = "examination"
                last_environment_response = pi_dialogue
            # Obtain response from patient
            else:
                if inf_type == "human_patient":
                    pi_dialogue = input("\nResponse to doctor: ")
                else:
                    pi_dialogue = patient_agent.inference_patient(doctor_dialogue)
                print("Patient [{}%]:".format(int(((_inf_id+1)/total_inferences)*100)), pi_dialogue)
                dialogue_log.append(f"Patient: {pi_dialogue}")
                scenario_logger.event(
                    "environment_response",
                    source="patient",
                    inference=_inf_id,
                    doctor_message=doctor_dialogue,
                    response=pi_dialogue,
                )
                meas_agent.add_hist(pi_dialogue)
                last_environment_source = "patient"
                last_environment_response = pi_dialogue
            
            # Prevent API timeouts
            time.sleep(1.0)
        
        else:
             # Loop finished without diagnosis
            _finalize_doctor_visualization(
                doctor_agent,
                dataset=dataset_name,
                scenario_id=_scenario_id,
                correct_diagnosis=scenario.diagnosis_information(),
                correct=False,
            )
            _record_final_state(
                scenario_logger,
                doctor_agent,
                _build_result_record(
                    dataset_name=dataset_name,
                    scenario_id=_scenario_id,
                    scenario=scenario,
                    doctor_agent=doctor_agent,
                    patient_agent=patient_agent,
                    meas_agent=meas_agent,
                    model_diagnosis="No diagnosis reached",
                    correct=False,
                    dialogue_log=dialogue_log,
                    experiment_id=experiment_id,
                ),
            )



class ScenarioOSCE:
    REQUIRED_FIELDS = {
        "Test_Results",
        "Correct_Diagnosis",
        "Patient_Actor",
        "Objective_for_Doctor",
        "Physical_Examination_Findings",
    }

    def __init__(self, scenario_dict) -> None:
        self.scenario_dict = scenario_dict
        self.patient_id = scenario_dict.get("patient_id") if isinstance(scenario_dict, dict) else None
        osce = self._osce_block(scenario_dict)
        self.tests = osce["Test_Results"]
        self.diagnosis = osce["Correct_Diagnosis"]
        self.patient_info = osce["Patient_Actor"]
        self.examiner_info = osce["Objective_for_Doctor"]
        self.physical_exams = osce["Physical_Examination_Findings"]

    @classmethod
    def _osce_block(cls, scenario_dict) -> dict:
        osce = scenario_dict.get("OSCE_Examination") if isinstance(scenario_dict, dict) else None
        if not isinstance(osce, dict):
            raise ValueError("scenario is missing OSCE_Examination")
        missing = sorted(cls.REQUIRED_FIELDS - set(osce))
        if missing:
            raise ValueError(f"OSCE_Examination is missing required fields: {missing}")
        return osce

    def patient_information(self) -> dict:
        return self.patient_info

    def examiner_information(self) -> dict:
        return self.examiner_info

    def exam_information(self) -> dict:
        exams = dict(self.physical_exams) if isinstance(self.physical_exams, dict) else {"physical_examination": self.physical_exams}
        exams["tests"] = self.tests
        return exams

    def diagnosis_information(self) -> str:
        return str(self.diagnosis)


class ScenarioLoaderOSCE:
    def __init__(self, patient_csv) -> None:
        self.path = _resolve_data_path(patient_csv)
        with open(self.path, "r", encoding="utf-8") as f:
            self.scenario_strs = [
                json.loads(line)
                for line in f
                if line.strip()
            ]
        self.scenarios = [
            self._build_scenario(scenario_dict, index)
            for index, scenario_dict in enumerate(self.scenario_strs)
        ]
        self.num_scenarios = len(self.scenarios)

    def _build_scenario(self, scenario_dict, index):
        try:
            return ScenarioOSCE(scenario_dict)
        except Exception as exc:
            raise ValueError(f"Invalid OSCE scenario at line {index + 1} in {self.path}: {exc}") from exc

    def sample_scenario(self):
        return self.scenarios[random.randint(0, len(self.scenarios) - 1)]

    def get_scenario(self, id):
        if id is None:
            return self.sample_scenario()
        return self.scenarios[id]


class PatientAgent:
    def __init__(self, scenario, backend_str="gpt-5-nano", bias_present=None) -> None:
        self.disease = ""
        self.symptoms = ""
        self.agent_hist = ""
        self.backend = backend_str
        self.bias_present = (None if bias_present == "None" else bias_present)
        self.scenario = scenario
        self.reset()
        self.biases = ["recency", "frequency", "false_consensus", "self_diagnosis", "gender", "race", "sexual_orientation", "cultural", "education", "religion", "socioeconomic"]
        self.total_tokens = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0

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
        result = query_model(self.backend, "\nHere is a history of your dialogue: " + self.agent_hist + "\n Here was the doctor response: " + question + "Now please continue your dialogue\nPatient: ", self.system_prompt(), return_usage=True)

        if isinstance(result, tuple):
            answer, usage = result
            if usage:
                self.total_tokens += getattr(usage, 'total_tokens', 0)
                self.prompt_tokens += getattr(usage, 'prompt_tokens', 0)
                self.completion_tokens += getattr(usage, 'completion_tokens', 0)
        else:
            answer = result

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
    def __init__(self, scenario, backend_str="gpt-5-nano", max_infs=20, bias_present=None, img_request=False, logger: AgentRunLogger | None = None) -> None:
        self.infs = 0
        self.MAX_INFS = max_infs
        self.agent_hist = ""
        self.presentation = ""
        self.backend = backend_str
        self.bias_present = (None if bias_present == "None" else bias_present)
        self.scenario = scenario
        self.logger = logger
        self.reset()
        self.img_request = img_request
        self.biases = ["recency", "frequency", "false_consensus", "confirmation", "status_quo", "gender", "race", "sexual_orientation", "cultural", "education", "religion", "socioeconomic"]
        self.total_tokens = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.last_uncertainty_reasoning = ""
        self.differential_diagnosis_list = ""
        self.osce_note = ""
        self._experience_printed = False

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

    def inference_doctor(self, question, image_requested=False, memory_context="") -> str:
        answer = str()
        uncertainty_reasoning = ""

        # Build experience prompt with optional memory context

        # below experience are for mimic now
        experience = """### 
You are a general hospital physician evaluating a real-world clinical case (EHR-style, like MIMIC).
Key assumptions:
- Information may be incomplete or noisy.
- Diagnoses correspond to ICD-style labels
provide a clinically appropriate assessment

SYSTEM & TOOL INSTRUCTIONS 
1. **Unified Test Interface:** Due to system design, Physical Examinations (PE) and Vital Signs are accessed via the test command. You cannot 'see' the patient automatically. - To check Vitals or the physcial information about the patient or do a Physical Exam, you MUST use: "REQUEST TEST: [Name]" (ex "REQUEST TEST: Abdominal_Examination") - To order Tests, you also use: "REQUEST TEST: [Name]", you may also request medical images related to the disease to be returned with \"REQUEST IMAGES\"

2. **Dialogue:** When talking to the patient, focus your questions on: Demographics, History of Present Illness (Symptoms), Past Medical History, and Social History.

### CLINICAL WORKFLOW PROTOCOL Please follow this logical order to simulate a real doctor's reasoning: if necessary,  "REQUEST TEST: Vital_Signs" early in the process to narrow down the scope.
2. **Investigate:** Ask the patient questions to understand the history and symptom range.
If a requested physical exam, laboratory test, or imaging study is unavailable, declined, or its result is unspecified:

1. Do NOT repeat the same request, one test request at a time
2. Do NOT request highly specific or procedure-level tests.
3. Instead, either:
   a) Request a broader category of tests (e.g., CBC, basic metabolic panel, liver function test, urinalysis, coagulation panel, inflammatory markers), or
   b) If the test is unavailable, choose the next-best discriminative test, physical examination or return to high-value questions from history/exam.

4. Avoid redundant clarification questions 
5. do not ask patient question and request test at the same time

### RULES - **Diagnosis:** When you have gathered sufficient evidence to be confident, output "DIAGNOSIS READY: [diagnosis here]". - **Mutually Exclusive:** if you need ask further questions or request tests you are not ready for Diagnosis

"""

        if not self._experience_printed:
            print("\n================ DOCTOR EXPERIENCE PROMPT START ================")
            print(experience)
            print("================= DOCTOR EXPERIENCE PROMPT END =================\n")
            self._experience_printed = True

        if self.infs >= self.MAX_INFS: return "Maximum inferences reached"

        doctor_structured_schema = {
            "type": "object",
            "properties": {
                "answer": {"type": "string"},
                "uncertainty_reasoning": {"type": "string"},
            },
            "required": ["answer", "uncertainty_reasoning"],
            "additionalProperties": False,
        }

        prompt = experience + "\nHere is a history of your dialogue: " + self.agent_hist + "\n Here was the patient response: " + question + "Now please continue your dialogue\nDoctor: "
        system_prompt = (
            self.system_prompt()
            + experience
            + "\n\nFor every response, provide structured output with two fields: "
            + "answer (your normal doctor dialogue, including REQUEST TEST / DIAGNOSIS READY when appropriate) and "
            + "uncertainty_reasoning (top 3 most likely diagnoses, briefly mentionwhat information/test would best differentiate them)."
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]
        run_id = None
        if self.logger is not None:
            run_id = self.logger.start_agent_run(
                messages,
                run_name="doctor_api",
                metadata={"inference": self.infs, "image_requested": image_requested},
            )

        try:
            result = query_model(
                self.backend,
                prompt,
                system_prompt,
                image_requested=image_requested,
                scene=self.scenario,
                return_usage=True,
                response_format_schema=doctor_structured_schema,
            )
        except Exception as exc:
            if self.logger is not None:
                self.logger.finish_agent_run(error=str(exc), run_id=run_id)
            raise

        if isinstance(result, tuple):
            parsed_response, usage = result
            if isinstance(parsed_response, dict):
                answer = str(parsed_response.get("answer", "")).strip()
                uncertainty_reasoning = str(parsed_response.get("uncertainty_reasoning", "")).strip()
            else:
                answer = str(parsed_response)
            if usage:
                self.total_tokens += getattr(usage, 'total_tokens', 0)
                self.prompt_tokens += getattr(usage, 'prompt_tokens', 0)
                self.completion_tokens += getattr(usage, 'completion_tokens', 0)
        else:
            if isinstance(result, dict):
                answer = str(result.get("answer", "")).strip()
                uncertainty_reasoning = str(result.get("uncertainty_reasoning", "")).strip()
            else:
                answer = str(result)

        if self.logger is not None:
            self.logger.llm_turn(
                self.infs,
                {
                    "role": "assistant",
                    "content": answer,
                    "uncertainty_reasoning": uncertainty_reasoning,
                    "usage": _usage_to_dict(usage if isinstance(result, tuple) else None),
                },
                input_messages=messages,
                run_id=run_id,
            )
            self.logger.finish_agent_run(
                result={
                    "answer": answer,
                    "uncertainty_reasoning": uncertainty_reasoning,
                },
                run_id=run_id,
            )
        self.last_uncertainty_reasoning = uncertainty_reasoning
        self.differential_diagnosis_list = uncertainty_reasoning
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
        self.last_uncertainty_reasoning = ""
        self.differential_diagnosis_list = ""
        self.osce_note = ""
        self._experience_printed = False


class MeasurementAgent:
    def __init__(self, scenario, backend_str="gpt-5-nano") -> None:
        self.agent_hist = ""
        self.presentation = ""
        self.backend = backend_str
        self.scenario = scenario
        self.reset()
        self.total_tokens = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0

    def inference_measurement(self, question) -> str:
        answer = str()
        result = query_model(self.backend, "\nHere is a history of the dialogue: " + self.agent_hist + "\n Here was the doctor measurement request: " + question, self.system_prompt(), return_usage=True)

        if isinstance(result, tuple):
            answer, usage = result
            if usage:
                self.total_tokens += getattr(usage, 'total_tokens', 0)
                self.prompt_tokens += getattr(usage, 'prompt_tokens', 0)
                self.completion_tokens += getattr(usage, 'completion_tokens', 0)
        else:
            answer = result

        self.agent_hist += question + "\n\n" + answer + "\n\n"
        return answer

    def system_prompt(self) -> str:
        base = "You are an measurement reader who responds with medical test results. Please respond in the format \"RESULTS: [results here]\""
        presentation = "\n\nBelow is all of the information you have. {}. \n\n If the requested results are not in your data then you can respond with Test unavailable".format(self.information) # suspect "NORMAL READINGS" is misleading llm's diagnosis
        return base + presentation
    
    def add_hist(self, hist_str) -> None:
        self.agent_hist += hist_str + "\n\n"

    def reset(self) -> None:
        self.agent_hist = ""
        self.information = self.scenario.exam_information()




if __name__ == "__main__":
    model_name = "gpt-5-nano"
    parser = argparse.ArgumentParser(description='AgentClinic OSCE JSONL simulation CLI')
    parser.add_argument('--openai_api_key', type=str, required=False, help='OpenAI API Key')
    parser.add_argument('--inf_type', type=str, choices=['llm', 'human_doctor', 'human_patient'], default='llm')
    parser.add_argument('--doctor_bias', type=str, help='Doctor bias type', default='None', choices=["recency", "frequency", "false_consensus", "confirmation", "status_quo", "gender", "race", "sexual_orientation", "cultural", "education", "religion", "socioeconomic"])
    parser.add_argument('--patient_bias', type=str, help='Patient bias type', default='None', choices=["recency", "frequency", "false_consensus", "self_diagnosis", "gender", "race", "sexual_orientation", "cultural", "education", "religion", "socioeconomic"])
    parser.add_argument('--doctor_llm', type=str, default=model_name)
    parser.add_argument('--patient_llm', type=str, default=model_name)
    parser.add_argument('--measurement_llm', type=str, default=model_name)
    parser.add_argument('--moderator_llm', type=str, default=model_name)
    parser.add_argument('--patient_csv', type=str, required=True, help='OSCE-format JSONL input file')
    parser.add_argument('--dataset_name', type=str, default=None, required=False, help='Optional label for logs/results; defaults to patient_csv stem')
    parser.add_argument('--num_scenarios', type=int, default=None, required=False, help='Number of scenarios to simulate')
    parser.add_argument('--total_inferences', type=int, default=30, required=False, help='Number of inferences between patient and doctor')
    
    parser.add_argument('--output_file', type=str, default=None, required=False, help='CSV file to append result rows to')
    parser.add_argument('--run_log_path', type=str, default=None, required=False, help='Path for sectioned AgentRunLogger JSON output')
    parser.add_argument('--scenario_offset', type=int, default=0, required=False, help='Scenario ID to start from')
    parser.add_argument('--custom_doctor_agent_path', type=str, default=None, required=False, help='Path to a Python file that defines a CustomDoctorAgent or DoctorAgent class with the same interface as the built-in DoctorAgent')
    parser.add_argument('--experiment_id', type=str, default=None, required=False, help='Shared experiment ID stored in every case log')
    args = parser.parse_args()

    main(
        args.openai_api_key,
        args.inf_type,
        args.doctor_bias,
        args.patient_bias,
        args.doctor_llm,
        args.patient_llm,
        args.measurement_llm,
        args.moderator_llm,
        args.num_scenarios,
        args.patient_csv,
        args.total_inferences,
        args.output_file,
        args.scenario_offset,
        args.custom_doctor_agent_path,
        args.dataset_name,
        args.run_log_path,
        args.experiment_id,
    )
