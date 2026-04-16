from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None

try:
    from .openai_llm_calling_core import call_openai, call_openai_json
except ImportError:
    import sys

    MODULE_DIR = Path(__file__).resolve().parent
    if str(MODULE_DIR) not in sys.path:
        sys.path.insert(0, str(MODULE_DIR))
    from openai_llm_calling_core import call_openai, call_openai_json


PROMPT_PATH = Path(__file__).with_name("two_agent_prompts.yaml")
TRAJECTORY_DIR = Path(__file__).with_name("trajectory")


def load_two_agent_prompts(path: str | Path = PROMPT_PATH) -> dict[str, str]:
    with Path(path).open("r", encoding="utf-8") as handle:
        raw_text = handle.read()
    if yaml is not None:
        data = yaml.safe_load(raw_text)
    else:
        data = _parse_simple_prompt_yaml(raw_text)
    if not isinstance(data, dict):
        raise ValueError(f"Prompt file must be a mapping: {path}")
    required_keys = {"information_seeking_agent", "diagnosis_agent"}
    missing = required_keys - set(data)
    if missing:
        raise ValueError(f"Prompt file missing required prompts: {sorted(missing)}")
    return {key: str(value).strip() for key, value in data.items()}


class InformationSeekingAgent:
    def __init__(
        self,
        *,
        model: str = "gpt-5-nano",
        temperature: float = 1,
        prompt_path: str | Path = PROMPT_PATH,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.system_prompt = load_two_agent_prompts(prompt_path)["information_seeking_agent"]

    def run(
        self,
        *,
        objective: str,
        incremental_chat_history: str,
        current_round: int,
        max_infs: int,
    ) -> dict[str, str]:
        payload = call_openai_json(
            [
                {"role": "system", "content": self.system_prompt},
                {
                    "role": "user",
                    "content": (
                        f"Objective for doctor:\n{objective.strip()}\n\n"
                        f"Current turn: {current_round + 1} of {max_infs}\n\n"
                        "Incremental chat history between doctor, patient, and measurement:\n"
                        f"{incremental_chat_history.strip() or 'No prior dialogue yet.'}"
                    ),
                },
            ],
            model=self.model,
            temperature=self.temperature,
        )
        return _parse_information_seeking_output(payload)


class DiagnosisAgent:
    def __init__(
        self,
        *,
        model: str = "gpt-5-nano",
        temperature: float = 1,
        prompt_path: str | Path = PROMPT_PATH,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.system_prompt = load_two_agent_prompts(prompt_path)["diagnosis_agent"]

    def run(self, *, osce_note: str, latest_context_message: str) -> dict[str, str]:
        text = call_openai(
            [
                {"role": "system", "content": self.system_prompt},
                {
                    "role": "user",
                    "content": (
                        f"OSCE note:\n{osce_note.strip()}\n\n"
                        f"Latest patient or measurement update:\n{latest_context_message.strip()}"
                    ),
                },
            ],
            model=self.model,
            temperature=self.temperature,
        )
        return _parse_diagnosis_output(text)


class TwoAgentClinicalInterface:
    def __init__(
        self,
        *,
        max_infs: int,
        information_seeking_model: str = "gpt-5-nano",
        diagnosis_model: str = "gpt-5-nano",
        prompt_path: str | Path = PROMPT_PATH,
    ) -> None:
        if max_infs < 1:
            raise ValueError("max_infs must be at least 1")
        self.max_infs = max_infs
        self.information_agent = InformationSeekingAgent(
            model=information_seeking_model,
            prompt_path=prompt_path,
        )
        self.diagnosis_agent = DiagnosisAgent(
            model=diagnosis_model,
            prompt_path=prompt_path,
        )
        self.latest_osce_note = ""
        self.turn_history: list[dict[str, Any]] = []

    def step(
        self,
        *,
        objective: str,
        incremental_chat_history: str,
        latest_context_message: str,
        current_round: int,
    ) -> dict[str, Any]:
        information_input = {
            "objective": objective,
            "incremental_chat_history": incremental_chat_history,
            "current_round": current_round,
            "max_infs": self.max_infs,
        }
        information_output = self.information_agent.run(
            objective=objective,
            incremental_chat_history=incremental_chat_history,
            current_round=current_round,
            max_infs=self.max_infs,
        )
        self.latest_osce_note = information_output["osce_note"]

        diagnosis_triggered = (
            information_output["message"].startswith("DIAGNOSIS READY:")
            or current_round >= self.max_infs - 1
        )
        final_diagnosis = None
        diagnosis_input = None
        if diagnosis_triggered:
            diagnosis_input = {
                "osce_note": self.latest_osce_note,
                "latest_context_message": latest_context_message,
            }
            final_diagnosis = self.diagnosis_agent.run(
                osce_note=self.latest_osce_note,
                latest_context_message=latest_context_message,
            )

        serialized = {
            "information_seeking_input": information_input,
            "information_seeking": information_output,
            "diagnosis_input": diagnosis_input,
            "final_diagnosis": final_diagnosis,
            "diagnosis_triggered": diagnosis_triggered,
        }
        self.turn_history.append(serialized)
        return serialized

    def reset(self) -> None:
        self.latest_osce_note = ""
        self.turn_history.clear()


class CustomDoctorAgent:
    def __init__(
        self,
        scenario,
        backend_str: str = "gpt-5-nano",
        max_infs: int = 20,
        bias_present=None,
        img_request: bool = False,
    ) -> None:
        self.scenario = scenario
        self.backend = backend_str
        self.MAX_INFS = max_infs
        self.bias_present = None if bias_present == "None" else bias_present
        self.img_request = img_request
        self.total_tokens = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.reset()

    def inference_doctor(self, question, image_requested: bool = False, memory_context: str = "") -> str:
        latest_context = str(question).strip()
        incremental_chat_history = self.agent_hist.strip()
        if latest_context:
            next_chunk = f"Patient/Test: {latest_context}"
            incremental_chat_history = f"{incremental_chat_history}\n{next_chunk}".strip() if incremental_chat_history else next_chunk

        result = self.interface.step(
            objective=self.presentation,
            incremental_chat_history=incremental_chat_history,
            latest_context_message=latest_context,
            current_round=self.infs,
        )
        info = result["information_seeking"]
        self.last_uncertainty_reasoning = info["reasoning"]
        self.latest_osce_note = info["osce_note"]

        if result["diagnosis_triggered"] and result["final_diagnosis"]:
            doctor_message = result["final_diagnosis"]["message"]
        else:
            doctor_message = info["message"]

        if latest_context:
            self.agent_hist += f"Patient/Test: {latest_context}\n"
        self.agent_hist += f"Doctor: {doctor_message}\n\n"
        self.trajectory["turns"].append(
            {
                "turn_index": self.infs,
                "latest_context_message": latest_context,
                "doctor_message": doctor_message,
                "information_seeking_input": result["information_seeking_input"],
                "information_seeking_output": result["information_seeking"],
                "diagnosis_triggered": result["diagnosis_triggered"],
                "diagnosis_input": result["diagnosis_input"],
                "diagnosis_output": result["final_diagnosis"],
            }
        )
        self.infs += 1
        self._write_trajectory()
        return doctor_message

    def reset(self) -> None:
        self.infs = 0
        self.agent_hist = ""
        self.last_uncertainty_reasoning = ""
        self.latest_osce_note = ""
        self.presentation = self.scenario.examiner_information()
        self.interface = TwoAgentClinicalInterface(
            max_infs=self.MAX_INFS,
            information_seeking_model=self.backend,
            diagnosis_model=self.backend,
        )
        self.trajectory_path = _build_trajectory_path(self.presentation)
        self.trajectory = {
            "case_id": self.trajectory_path.stem,
            "model": self.backend,
            "max_infs": self.MAX_INFS,
            "objective_for_doctor": self.presentation,
            "turns": [],
        }
        self._write_trajectory()

    def _write_trajectory(self) -> None:
        TRAJECTORY_DIR.mkdir(parents=True, exist_ok=True)
        with self.trajectory_path.open("w", encoding="utf-8") as handle:
            json.dump(self.trajectory, handle, indent=2, ensure_ascii=True)


DoctorAgent = CustomDoctorAgent


def _parse_information_seeking_output(payload: dict[str, Any]) -> dict[str, str]:
    output = {
        "message": str(payload.get("message", "")).strip(),
        "reasoning": str(payload.get("reasoning", "")).strip(),
        "osce_note": str(payload.get("osce_note", "")).strip(),
    }
    if not output["message"]:
        raise ValueError("Information-seeking output missing message")
    if not output["reasoning"]:
        raise ValueError("Information-seeking output missing reasoning")
    if not output["osce_note"]:
        raise ValueError("Information-seeking output missing osce_note")
    if not _is_valid_information_message(output["message"]):
        raise ValueError("message must be a patient question, REQUEST TEST, or DIAGNOSIS READY")
    return output


def _parse_diagnosis_output(text: str) -> dict[str, str]:
    message = text.strip()
    if not message.startswith("DIAGNOSIS READY:"):
        raise ValueError("Diagnosis output must start with 'DIAGNOSIS READY:'")
    return {"message": message}


def _parse_simple_prompt_yaml(raw_text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    current_key = None
    current_lines: list[str] = []
    for line in raw_text.splitlines():
        if not line.strip():
            if current_key is not None:
                current_lines.append("")
            continue
        if not line.startswith(" ") and line.endswith(": |"):
            if current_key is not None:
                result[current_key] = "\n".join(current_lines).rstrip()
            current_key = line.split(":", 1)[0].strip()
            current_lines = []
            continue
        if current_key is not None and line.startswith("  "):
            current_lines.append(line[2:])
    if current_key is not None:
        result[current_key] = "\n".join(current_lines).rstrip()
    return result


def _is_valid_information_message(message: str) -> bool:

    return True


def _build_trajectory_path(presentation: str) -> Path:
    TRAJECTORY_DIR.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(presentation.encode("utf-8")).hexdigest()[:10]
    filename = f"case_{int(time.time() * 1000)}_{os.getpid()}_{digest}.json"
    return TRAJECTORY_DIR / filename
