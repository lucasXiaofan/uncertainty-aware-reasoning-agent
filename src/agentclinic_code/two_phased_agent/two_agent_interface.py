"""AgentClinic custom doctor interface backed by the src.agent tool loop."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
PROMPT_PATH = "src/agent/prompts/agentclinic_information_gathering.md"
LOG_DIR = Path(__file__).resolve().parent / "trajectory"

import sys

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agent.agent import Agent
from src.agent.working_memory import load_prompt_to_working_memory


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
        self.last_uncertainty_reasoning = ""
        self.differential_diagnosis_list = ""
        self.osce_note = {}
        self.reset()

    def inference_doctor(
        self,
        question,
        image_requested: bool = False,
        memory_context: str = "",
    ) -> str:
        if self.infs >= self.MAX_INFS:
            return "Maximum inferences reached"

        latest_context = str(question or "").strip()
        if latest_context:
            self.working_memory.update(
                {
                    "role": "user",
                    "content": (
                        "Hospital environment response from the previous action:\n"
                        f"{latest_context}\n\n"
                        "Update the OSCE note, then choose the next AgentClinic action."
                    ),
                }
            )

        agent = Agent(
            self.working_memory,
            model=self.backend,
            max_steps=6,
            temperature=1,
            log_path=self._log_path(),
        )
        result = agent.run()
        self._add_usage(agent)
        self.infs += 1

        payload = self._parse_agent_payload(result)
        message = self._agentclinic_message(payload)
        self.agent_hist += f"Hospital: {latest_context}\nDoctor: {message}\n\n"
        self.last_uncertainty_reasoning = self._latest_differential()
        self.differential_diagnosis_list = self.last_uncertainty_reasoning
        self.osce_note = self._latest_osce_note()
        return message

    def reset(self) -> None:
        self.infs = 0
        self.agent_hist = ""
        self.presentation = self.scenario.examiner_information()
        self.working_memory = load_prompt_to_working_memory(PROMPT_PATH)
        self.differential_diagnosis_list = ""
        self.osce_note = {}
        self.working_memory.update(
            {
                "role": "user",
                "content": (
                    "Doctor-visible case objective/context:\n"
                    f"{self.presentation}\n\n"
                    "Start information gathering. Use AgentClinic respond actions for patient questions, "
                    "physical examination requests, or test requests."
                ),
            }
        )

    def _parse_agent_payload(self, result: dict[str, Any]) -> dict[str, Any]:
        content = result.get("content", "")
        if isinstance(content, str):
            try:
                payload = json.loads(content)
            except json.JSONDecodeError:
                return {
                    "tool_name": "respond",
                    "content": {"action": "ask_patient", "message": content.strip()},
                }
        elif isinstance(content, dict):
            payload = content
        else:
            raise ValueError(f"Unsupported agent content: {content!r}")

        if not isinstance(payload, dict):
            raise ValueError(f"Agent payload must be a dictionary: {payload!r}")
        return payload

    def _agentclinic_message(self, payload: dict[str, Any]) -> str:
        tool_name = payload.get("tool_name")
        content = payload.get("content")
        if tool_name == "final_diagnosis":
            return f"DIAGNOSIS READY: {str(content).strip()}"

        if tool_name != "respond" or not isinstance(content, dict):
            raise ValueError(f"Unsupported AgentClinic payload: {payload!r}")

        action = str(content.get("action", "")).strip()
        message = str(content.get("message", "")).strip()
        if not message:
            raise ValueError(f"AgentClinic respond payload missing message: {payload!r}")
        if action == "ask_patient":
            return message
        if action in {"request_physical_examination", "request_test"}:
            return f"REQUEST TEST: {message}"
        raise ValueError(f"Unsupported AgentClinic respond action: {action}")

    def _latest_differential(self) -> str:
        osce_note = self.working_memory.static_memory()["memory_object"].get("osce_note", {})
        if isinstance(osce_note, dict):
            return str(osce_note.get("differential_diagnosis_list", ""))
        return ""

    def _latest_osce_note(self) -> dict[str, Any] | str:
        osce_note = self.working_memory.static_memory()["memory_object"].get("osce_note", {})
        return osce_note if isinstance(osce_note, dict) else str(osce_note)

    def _log_path(self) -> Path:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        stamp = int(time.time() * 1000)
        return LOG_DIR / f"agentclinic_{os.getpid()}_{stamp}_{self.infs}.json"

    def _add_usage(self, agent: Agent) -> None:
        usage = agent.logger.meta.get("token_usage", {})
        self.prompt_tokens += int(usage.get("input_tokens") or 0)
        self.completion_tokens += int(usage.get("output_tokens") or 0)
        self.total_tokens += int(usage.get("total_tokens") or 0)


DoctorAgent = CustomDoctorAgent
