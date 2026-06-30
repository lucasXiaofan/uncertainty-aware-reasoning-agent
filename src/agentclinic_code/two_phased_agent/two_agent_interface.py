"""AgentClinic custom doctor interface backed by the src.agent tool loop."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
INFORMATION_PROMPT_PATH = "src/agent/prompts/agentclinic_information_gathering.md"
DIAGNOSIS_PROMPT_PATH = "src/agent/prompts/agentclinic_differential_diagnosis.md"
LOG_DIR = Path(__file__).resolve().parent / "trajectory"
VISUALIZATION_LOG_DIR = PROJECT_ROOT / "logs" / "agentclinic"
INFORMATION_ROUNDS = 9
TOTAL_ROUNDS = 10

import sys

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.agent.agent import Agent
from src.agent.logging import AgentRunLogger
from src.agent.tool_calling import BASH_TOOL
from src.agent.working_memory import (
    EVIDENCE_TOOL_SCHEMA,
    OSCE_NOTE_TOOL_SCHEMA,
    PLAN_TOOL_SCHEMA,
    WorkingMemory,
    load_prompt_to_working_memory,
)
from trajectory_projection import project_trajectory_file


class _PhaseAgent:
    """Keep phase memory across turns while giving each run a fresh logger."""

    def __init__(
        self,
        working_memory: WorkingMemory,
        *,
        model: str,
        tools: list[dict[str, Any]],
        log_path: Path,
        logger: AgentRunLogger | None = None,
    ) -> None:
        self.working_memory = working_memory
        self.model = model
        self.tools = tools
        self.log_path = log_path
        self.shared_logger = logger
        self.runner: Agent | None = None

    def run(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "tools": self.tools,
            "max_steps": 30,
            "temperature": 1,
            "log_path": self.log_path,
        }
        if self.shared_logger is not None:
            kwargs["logger"] = self.shared_logger
        self.runner = Agent(self.working_memory, **kwargs)
        return self.runner.run()

    @property
    def logger(self):
        if self.runner is None:
            raise RuntimeError("phase agent has not run")
        return self.runner.logger


class CustomDoctorAgent:
    def __init__(
        self,
        scenario,
        backend_str: str = "gpt-5-nano",
        max_infs: int = 20,
        bias_present=None,
        img_request: bool = False,
        logger: AgentRunLogger | None = None,
    ) -> None:
        self.scenario = scenario
        self.backend = backend_str
        # AgentClinic may pass its own default, but this two-phase protocol is
        # intentionally fixed at nine gathering rounds plus one diagnosis round.
        self.MAX_INFS = TOTAL_ROUNDS
        self.bias_present = None if bias_present == "None" else bias_present
        self.img_request = img_request
        self.total_tokens = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.last_uncertainty_reasoning = ""
        self.differential_diagnosis_list = ""
        self.osce_note = ""
        self.logger = logger
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
        if self.infs < INFORMATION_ROUNDS:
            if latest_context:
                self.information_working_memory.update(
                    {
                        "role": "user",
                        "content": (
                            "Hospital environment response from the previous action:\n"
                            f"{latest_context}\n\n"
                        ),
                    }
                )
            active_agent = self.information_seeking_agent
            phase = "information_seeking"
        else:
            self._refresh_information_outputs()
            self.diagnosis_working_memory.update(
                {
                    "role": "user",
                    "content": (
                        "This is the final diagnosis round. Read self.osce_note from the "
                        "information-seeking agent below.\n\n"
                        f"self.osce_note:\n{json.dumps(self.osce_note, ensure_ascii=False, indent=2)}\n\n"
                        "Information-seeking agent differential_diagnosis_list:\n"
                        f"{self.differential_diagnosis_list or 'Not recorded'}\n\n"
                        "Latest hospital environment response:\n"
                        f"{latest_context or 'No additional response'}\n\n"
                        "Use update_evidence to cite supporting and contradicting case evidence "
                        "and relevant medical self-knowledge. Then call final_diagnosis with one "
                        "diagnosis name only."
                    ),
                }
            )
            active_agent = self.differential_diagnosis_agent
            phase = "differential_diagnosis"

        result = active_agent.run()
        self._add_usage(active_agent)
        payload = self._parse_agent_payload(result)
        self._validate_phase_payload(payload, phase)
        message = self._agentclinic_message(payload)
        self.agent_hist += f"Hospital: {latest_context}\nDoctor: {message}\n\n"
        if phase == "information_seeking":
            self._refresh_information_outputs()
        self.trajectory["turns"].append(
            {
                "inference": self.infs,
                "phase": phase,
                "hospital_response": latest_context,
                "doctor_message": message,
                "meta": active_agent.logger.meta,
                "raw_trajectory": self._unique_trajectory(active_agent.logger.raw_trajectory),
            }
        )
        self.infs += 1
        self._save_trajectory()
        return message

    def reset(self) -> None:
        self.infs = 0
        self.agent_hist = ""
        self.presentation = self.scenario.examiner_information()
        self.trajectory_path = self._build_log_path()
        self.run_id = self.trajectory_path.stem
        self.run_v1_path = VISUALIZATION_LOG_DIR / self.run_id / "run.v1.json"
        self.information_working_memory = load_prompt_to_working_memory(
            INFORMATION_PROMPT_PATH
        )
        self.diagnosis_working_memory = load_prompt_to_working_memory(
            DIAGNOSIS_PROMPT_PATH
        )
        self.information_seeking_agent = _PhaseAgent(
            self.information_working_memory,
            model=self.backend,
            tools=[BASH_TOOL, OSCE_NOTE_TOOL_SCHEMA, PLAN_TOOL_SCHEMA],
            log_path=self.trajectory_path,
            logger=self.logger,
        )
        self.differential_diagnosis_agent = _PhaseAgent(
            self.diagnosis_working_memory,
            model=self.backend,
            tools=[BASH_TOOL, EVIDENCE_TOOL_SCHEMA],
            log_path=self.trajectory_path,
            logger=self.logger,
        )
        # Backward-compatible alias for callers that inspected the old memory.
        self.working_memory = self.information_working_memory
        self.differential_diagnosis_list = ""
        self.osce_note = {}
        self.trajectory = {
            "model": self.backend,
            "objective": self.presentation,
            "information_rounds": INFORMATION_ROUNDS,
            "total_rounds": TOTAL_ROUNDS,
            "turns": [],
        }
        self._saved_messages: set[str] = set()
        self.information_working_memory.update(
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
            if not isinstance(content, str) or not content.strip():
                raise ValueError("final_diagnosis content must be one diagnosis name")
            diagnosis = content.strip()
            if "\n" in diagnosis or ";" in diagnosis:
                raise ValueError("final_diagnosis content must contain a single diagnosis")
            return f"DIAGNOSIS READY: {diagnosis}"

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
        osce_note = self.information_working_memory.static_memory()["memory_object"].get(
            "osce_note", {}
        )
        if isinstance(osce_note, dict):
            return str(osce_note.get("differential_diagnosis_list", ""))
        return ""

    def _latest_osce_note(self) -> dict[str, Any] | str:
        osce_note = self.information_working_memory.static_memory()["memory_object"].get(
            "osce_note", {}
        )
        return osce_note if isinstance(osce_note, dict) else str(osce_note)

    def _refresh_information_outputs(self) -> None:
        self.last_uncertainty_reasoning = self._latest_differential()
        self.differential_diagnosis_list = self.last_uncertainty_reasoning
        self.osce_note = self._latest_osce_note()

    def _validate_phase_payload(
        self,
        payload: dict[str, Any],
        phase: str,
    ) -> None:
        tool_name = payload.get("tool_name")
        if phase == "information_seeking" and tool_name != "respond":
            raise ValueError("Information-seeking rounds must terminate with a respond action")
        if phase == "differential_diagnosis" and tool_name != "final_diagnosis":
            raise ValueError(
                "The differential-diagnosis round must terminate with final_diagnosis"
            )

    def _build_log_path(self) -> Path:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        return LOG_DIR / f"agentclinic_{os.getpid()}_{time.time_ns()}.json"

    def _save_trajectory(self) -> None:
        self.trajectory_path.write_text(
            json.dumps(self.trajectory, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        self._save_visualization_projection()

    def _save_visualization_projection(
        self,
        *,
        dataset: str = "AgentClinic",
        scenario_id: int | str | None = None,
        correct_diagnosis: Any = None,
        correct: bool | None = None,
    ) -> None:
        project_trajectory_file(
            self.trajectory_path,
            self.run_v1_path,
            dataset=dataset,
            scenario_id=scenario_id,
            correct_diagnosis=correct_diagnosis,
            correct=correct,
        )

    def finalize_visualization(
        self,
        *,
        dataset: str,
        scenario_id: int | str,
        correct_diagnosis: Any = None,
        correct: bool | None = None,
    ) -> Path:
        self._save_visualization_projection(
            dataset=dataset,
            scenario_id=scenario_id,
            correct_diagnosis=correct_diagnosis,
            correct=correct,
        )
        return self.run_v1_path

    def _unique_trajectory(self, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        unique_events = []
        for event in events:
            event_copy = json.loads(json.dumps(event, ensure_ascii=False, default=str))
            if "messages" not in event_copy:
                unique_events.append(event_copy)
                continue
            messages = []
            for message in event_copy["messages"]:
                key = json.dumps(message, sort_keys=True, ensure_ascii=False)
                if key not in self._saved_messages:
                    self._saved_messages.add(key)
                    messages.append(message)
            event_copy["messages"] = messages
            unique_events.append(event_copy)
        return unique_events

    def _add_usage(self, agent: _PhaseAgent) -> None:
        usage = agent.logger.meta.get("token_usage", {})
        self.prompt_tokens += int(usage.get("input_tokens") or 0)
        self.completion_tokens += int(usage.get("output_tokens") or 0)
        self.total_tokens += int(usage.get("total_tokens") or 0)


DoctorAgent = CustomDoctorAgent
