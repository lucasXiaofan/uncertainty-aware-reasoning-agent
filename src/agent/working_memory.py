"""Minimal working-memory objects for the agent loop."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from copy import deepcopy
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROMPTS_DIR = Path(__file__).resolve().with_name("prompts")
PLAN_TOOL_NAME = "update_plan"
EVIDENCE_TOOL_NAME = "update_evidence"
OSCE_NOTE_TOOL_NAME = "update_osce_note"
PLAN_MEMORY_KEY = "plan"
EVIDENCE_MEMORY_KEY = "evidence"
OSCE_NOTE_MEMORY_KEY = "osce_note"

PLAN_TOOL_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": PLAN_TOOL_NAME,
        "description": "Update the plan memory. Use only the required items list.",
        "parameters": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "content": {"type": "string"},
                            "status": {
                                "type": "string",
                                "enum": ["complete", "incomplete", "pass"],
                            },
                            "reason": {"type": "string"},
                        },
                        "required": ["id"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["items"],
            "additionalProperties": False,
        },
    },
}

EVIDENCE_TOOL_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": EVIDENCE_TOOL_NAME,
        "description": "Update the evidence memory. Use only the required items list.",
        "parameters": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "description": {"type": "string"},
                            "is_supported": {"type": "boolean"},
                            "reason": {"type": "string"},
                            "source": {"type": "string"},
                        },
                        "required": ["title"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["items"],
            "additionalProperties": False,
        },
    },
}

OSCE_NOTE_TOOL_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": OSCE_NOTE_TOOL_NAME,
        "description": (
            "Update the OSCE note memory. Most sections append atomic claims; "
            "differential_diagnosis_list overwrites the previous top 3 diagnosis list."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "section": {
                                "type": "string",
                                "enum": [
                                    "patient_demographics",
                                    "patient_medical_history",
                                    "patient_social_history",
                                    "patient_symptoms",
                                    "physical_exmination_findings",
                                    "test_results",
                                    "differential_diagnosis_list",
                                ],
                            },
                            "content": {"type": "string"},
                        },
                        "required": ["section", "content"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["items"],
            "additionalProperties": False,
        },
    },
}

MEMORY_TOOL_REGISTRY: dict[str, dict[str, Any]] = {
    PLAN_TOOL_NAME: {
        "memory_object": PLAN_MEMORY_KEY,
        "schema": PLAN_TOOL_SCHEMA,
    },
    EVIDENCE_TOOL_NAME: {
        "memory_object": EVIDENCE_MEMORY_KEY,
        "schema": EVIDENCE_TOOL_SCHEMA,
    },
    OSCE_NOTE_TOOL_NAME: {
        "memory_object": OSCE_NOTE_MEMORY_KEY,
        "schema": OSCE_NOTE_TOOL_SCHEMA,
    },
}
MEMORY_TOOL_SCHEMAS: list[dict[str, Any]] = [
    PLAN_TOOL_SCHEMA,
    EVIDENCE_TOOL_SCHEMA,
    OSCE_NOTE_TOOL_SCHEMA,
]


def memory_object_key_for_tool(tool_name: str) -> str | None:
    registered = MEMORY_TOOL_REGISTRY.get(tool_name)
    if registered is None:
        return None
    return registered["memory_object"]


def load_prompt(prompt_path: str | Path) -> str:
    """Load a prompt by repo-relative path or path relative to src/agent/prompts."""
    return _resolve_prompt_path(prompt_path).read_text(encoding="utf-8")


def load_prompt_to_working_memory(
    prompt_path: str | Path,
    messages: list[dict[str, Any]] | None = None,
    **working_memory_kwargs: Any,
) -> "WorkingMemory":
    """Create WorkingMemory with a prompt file loaded as the system prompt.

    Examples:
        load_prompt_to_working_memory("agentclinic_differential_diagnosis.md")
        load_prompt_to_working_memory("src/agent/prompts/agentclinic_differential_diagnosis.md")
    """
    system_prompt = load_prompt(prompt_path)
    return WorkingMemory(messages, system_prompt=system_prompt, **working_memory_kwargs)


class memory_object(ABC):
    """Base class for a static memory object.

    Recognition format from LLM tool result is exactly:
    `{"memory_object": self.key, "items": [{...}, ...]}`.
    """

    key = ""

    @abstractmethod
    def update(self, items: list[dict[str, Any]]) -> None:
        """Apply a strict list-of-dictionaries update or raise a clear error."""

    @abstractmethod
    def display(self) -> Any:
        """Return JSON-serializable memory content."""


class Plan(memory_object):
    """Plan memory.

    Tool call: `update_plan({"items": [{"id": "1", "content": "..."}]})`.
    The tool result is `{"memory_object": "plan", "items": [...]}`.
    """

    key = PLAN_MEMORY_KEY
    VALID_STATUSES = {"complete", "incomplete", "pass"}

    def __init__(self, items: list[dict[str, Any]] | None = None) -> None:
        self.items: list[dict[str, str]] = []
        if items:
            self.update(items)

    def update(self, items: list[dict[str, Any]]) -> None:
        _require_items_list(items, self.key)
        for item in items:
            step_id = _required_str(item, "id", self.key)
            step = self._find(step_id)
            if step is None:
                step = {"id": step_id, "content": "", "status": "incomplete", "reason": ""}
                self.items.append(step)

            if "content" in item:
                step["content"] = _optional_str(item, "content", self.key)
            if "status" in item:
                status = _optional_str(item, "status", self.key)
                if status not in self.VALID_STATUSES:
                    raise ValueError(f"plan status must be one of {sorted(self.VALID_STATUSES)}")
                step["status"] = status
            if "reason" in item:
                step["reason"] = _optional_str(item, "reason", self.key)

    def display(self) -> list[dict[str, str]]:
        return deepcopy(self.items)

    def _find(self, step_id: str) -> dict[str, str] | None:
        return next((item for item in self.items if item["id"] == step_id), None)


class Evidence(memory_object):
    """Evidence memory.

    Tool call: `update_evidence({"items": [{"title": "...", "description": "..."}]})`.
    The tool result is `{"memory_object": "evidence", "items": [...]}`.
    """

    key = EVIDENCE_MEMORY_KEY

    def __init__(self, items: list[dict[str, Any]] | None = None) -> None:
        self.items: list[dict[str, Any]] = []
        if items:
            self.update(items)

    def update(self, items: list[dict[str, Any]]) -> None:
        _require_items_list(items, self.key)
        for item in items:
            title = _required_str(item, "title", self.key)
            evidence = self._find(title)
            if evidence is None:
                evidence = {
                    "title": title,
                    "description": "",
                    "is_supported": None,
                    "reason": "",
                    "source": "using self knowledge, no cited case evidence found",
                }
                self.items.append(evidence)

            if "description" in item:
                evidence["description"] = _optional_str(item, "description", self.key)
            if "is_supported" in item:
                if not isinstance(item["is_supported"], bool):
                    raise TypeError("evidence.is_supported must be a boolean")
                evidence["is_supported"] = item["is_supported"]
            if "reason" in item:
                evidence["reason"] = _optional_str(item, "reason", self.key)
            if "source" in item:
                evidence["source"] = _optional_str(item, "source", self.key)

    def display(self) -> list[dict[str, Any]]:
        return deepcopy(self.items)

    def _find(self, title: str) -> dict[str, Any] | None:
        return next((item for item in self.items if item["title"] == title), None)


class OSCENote(memory_object):
    """OSCE note memory.

    Tool call: `update_osce_note({"items": [{"section": "patient_symptoms", "content": "..."}]})`.
    Use `section: "differential_diagnosis_list"` with top 3 diagnoses separated by `;`.
    The tool result is `{"memory_object": "osce_note", "items": [...]}`.
    """

    key = OSCE_NOTE_MEMORY_KEY
    DIFFERENTIAL_SECTION = "differential_diagnosis_list"
    SECTIONS = (
        "patient_demographics",
        "patient_medical_history",
        "patient_social_history",
        "patient_symptoms",
        "physical_exmination_findings",
        "test_results",
        DIFFERENTIAL_SECTION,
    )
    APPEND_SECTIONS = (
        "patient_demographics",
        "patient_medical_history",
        "patient_social_history",
        "patient_symptoms",
        "physical_exmination_findings",
        "test_results",
    )

    def __init__(self, items: list[dict[str, Any]] | None = None) -> None:
        self.sections: dict[str, list[str] | str] = {
            section: [] for section in self.APPEND_SECTIONS
        }
        self.sections[self.DIFFERENTIAL_SECTION] = ""
        if items:
            self.update(items)

    def update(self, items: list[dict[str, Any]]) -> None:
        _require_items_list(items, self.key)
        for item in items:
            section = _required_str(item, "section", self.key)
            content = _required_str(item, "content", self.key)
            if section not in self.sections:
                raise ValueError(f"osce_note.section must be one of {list(self.SECTIONS)}")
            if section == self.DIFFERENTIAL_SECTION:
                self.sections[section] = content
            else:
                section_items = self.sections[section]
                if not isinstance(section_items, list):
                    raise TypeError(f"osce_note.{section} must be a list")
                section_items.append(content)

    def display(self) -> dict[str, list[str] | str]:
        return deepcopy(self.sections)


class WorkingMemory:
    """Static memory objects plus dynamic appended agent trajectory."""

    def __init__(
        self,
        messages: list[dict[str, Any]] | None = None,
        *,
        system_prompt: str = "",
        memory_objects: list[memory_object] | None = None,
        plan: list[dict[str, Any]] | None = None,
        evidence: list[dict[str, Any]] | None = None,
        osce_note: list[dict[str, Any]] | None = None,
    ) -> None:
        self.system_prompt = system_prompt
        objects = memory_objects if memory_objects is not None else [Plan(plan), Evidence(evidence), OSCENote(osce_note)]
        self.memory_objects = self._load_memory_objects(objects)
        self.plan = self.memory_objects.get("plan")
        self.evidence = self.memory_objects.get("evidence")
        self.osce_note = self.memory_objects.get("osce_note")
        self.raw_trajectory: list[dict[str, Any]] = deepcopy(messages or [])

    def update(self, message: dict[str, Any]) -> None:
        """Append one LLM-readable message to the dynamic trajectory."""
        self.raw_trajectory.append(deepcopy(message))

    def update_memory_object(self, *, key: str, items: Any) -> None:
        memory = self.memory_objects.get(key)
        if memory is None:
            raise KeyError(f"unknown memory_object: {key}")
        memory.update(items)

    def get_messages(self) -> list[dict[str, Any]]:
        return [
            {"role": "system", "content": self.display_static()},
            *deepcopy(self.raw_trajectory),
        ]

    def display_static(self) -> str:
        return (
            "STATIC MEMORY\n"
            f"{json.dumps(self.static_memory(), ensure_ascii=False, indent=2)}\n\n"
            "DYNAMIC MEMORY\n"
            "The appended agent trajectory follows as subsequent messages."
        )

    def display(self) -> str:
        return json.dumps(
            {
                "static_memory": self.static_memory(),
                "dynamic_memory": {"appended_agent_trajectory": deepcopy(self.raw_trajectory)},
            },
            ensure_ascii=False,
            indent=2,
        )

    def static_memory(self) -> dict[str, Any]:
        return {
            "system_prompt": self.system_prompt,
            "memory_object": {
                key: memory.display()
                for key, memory in self.memory_objects.items()
            },
        }

    def _load_memory_objects(self, objects: list[memory_object]) -> dict[str, memory_object]:
        if not isinstance(objects, list):
            raise TypeError("memory_objects must be a list")
        loaded: dict[str, memory_object] = {}
        for memory in objects:
            if not isinstance(memory, memory_object):
                raise TypeError("each memory object must inherit memory_object")
            if not memory.key:
                raise ValueError("memory object key cannot be empty")
            if memory.key in loaded:
                raise ValueError(f"duplicate memory object key: {memory.key}")
            loaded[memory.key] = memory
        return loaded


MemoryObject = memory_object
OSCE_note = OSCENote


def _require_items_list(items: Any, memory_key: str) -> None:
    if not isinstance(items, list):
        raise TypeError(f"{memory_key}.items must be a list")
    if not all(isinstance(item, dict) for item in items):
        raise TypeError(f"all {memory_key}.items entries must be dictionaries")


def _required_str(item: dict[str, Any], field: str, memory_key: str) -> str:
    if field not in item:
        raise ValueError(f"{memory_key}.{field} is required")
    value = item[field]
    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"{memory_key}.{field} must be a non-empty string")
    return value.strip()


def _optional_str(item: dict[str, Any], field: str, memory_key: str) -> str:
    value = item[field]
    if not isinstance(value, str):
        raise TypeError(f"{memory_key}.{field} must be a string")
    return value.strip()


def _resolve_prompt_path(prompt_path: str | Path) -> Path:
    path = Path(prompt_path)
    if path.is_absolute():
        raise ValueError("prompt_path must be relative")

    candidates = (PROJECT_ROOT / path, PROMPTS_DIR / path)
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_file():
            return resolved

    checked = ", ".join(str(candidate) for candidate in candidates)
    raise FileNotFoundError(f"prompt file not found: {prompt_path}. Checked: {checked}")
