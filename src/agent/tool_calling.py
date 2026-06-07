"""Tool-call handlers used by the simple agent."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from .working_memory import (
    WorkingMemory,
    memory_object_key_for_tool,
)

TERMINATE_START_TAG = "<terminate>"
TERMINATE_END_TAG = "</terminate>"
TERMINATE_ALT_END_TAG = "<\\terminate>"


def project_root() -> Path:
    """Return this repository root without hard-coding a user-specific path."""
    return Path(__file__).resolve().parents[2]


BASH_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "bash",
        "description": (
            "Run a shell command from the project root. Keep file edits inside the repository. "
            "AgentClinic terminal tools are available with: "
            "python3 src/agent/agentclinic_tools.py '<json>'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "timeout": {"type": "integer", "default": 30},
            },
            "required": ["command"],
        },
    },
}


def run_bash(command: str, *, timeout: int = 30, cwd: Path | None = None) -> dict[str, Any]:
    """Run a Bash command from the repo root and return stdout/stderr/status."""
    root = cwd or project_root()
    completed = subprocess.run(
        ["bash", "-lc", command],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return {
        "cwd": str(root),
        "returncode": completed.returncode,
        "stdout": completed.stdout[-12000:],
        "stderr": completed.stderr[-12000:],
    }


def wrap_termination_output(payload: dict[str, Any]) -> str:
    return f"{TERMINATE_START_TAG}{json.dumps(payload, ensure_ascii=False)}{TERMINATE_END_TAG}"


def extract_termination_output(text: str) -> tuple[dict[str, Any] | None, str]:
    start_index = text.find(TERMINATE_START_TAG)
    if start_index < 0:
        return None, text

    payload_start = start_index + len(TERMINATE_START_TAG)
    end_index = text.find(TERMINATE_END_TAG, payload_start)
    end_tag = TERMINATE_END_TAG
    if end_index < 0:
        end_index = text.find(TERMINATE_ALT_END_TAG, payload_start)
        end_tag = TERMINATE_ALT_END_TAG
    if end_index < 0:
        return None, text

    raw_payload = text[payload_start:end_index].strip()
    payload = json.loads(raw_payload)
    if not isinstance(payload, dict):
        raise ValueError("termination payload must be a JSON dictionary")
    visible_text = text[:start_index] + text[end_index + len(end_tag):]
    return payload, visible_text


def termination_result(tool_result: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(tool_result)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict) or payload.get("terminate") is not True:
        return None
    output = payload.get("output")
    return output if isinstance(output, dict) else None


def update_memory_tool(
    working_memory: WorkingMemory,
    *,
    tool_name: str,
    args: dict[str, Any],
) -> dict[str, Any]:
    """Apply a registered memory tool call and return its tool-message payload."""
    memory_key = memory_object_key_for_tool(tool_name)
    if memory_key is None:
        raise KeyError(f"unknown memory tool: {tool_name}")
    items = args.get("items")
    working_memory.update_memory_object(key=memory_key, items=items)
    return {
        "message": f"{memory_key} updated successfully"
    }


def handle_tool_call(
    name: str,
    arguments: str,
    *,
    working_memory: WorkingMemory | None = None,
) -> str:
    """Dispatch one model tool call and return JSON text for the tool message."""
    try:
        args = json.loads(arguments or "{}")
        if name == "bash":
            if not args.get("command"):
                return json.dumps({"error": "missing command"})
            bash_result = run_bash(
                str(args["command"]),
                timeout=int(args.get("timeout", 30)),
            )
            termination, visible_stdout = extract_termination_output(bash_result["stdout"])
            if termination is not None:
                bash_result["stdout"] = visible_stdout
                return json.dumps(
                    {
                        "terminate": True,
                        "output": termination,
                    },
                    ensure_ascii=False,
                )
            return json.dumps(
                bash_result,
                ensure_ascii=False,
            )
        if memory_object_key_for_tool(name) is not None:
            if working_memory is None:
                raise ValueError("working_memory is required for memory tools")
            return json.dumps(
                update_memory_tool(
                    working_memory,
                    tool_name=name,
                    args=args,
                ),
                ensure_ascii=False,
            )
        return json.dumps({"error": f"unknown tool: {name}"})
    except Exception as exc:
        if memory_object_key_for_tool(name) is not None:
            return json.dumps(
                {
                    "error": "memory update failed",
                    "details": str(exc),
                    "retryable": True,
                },
                ensure_ascii=False,
            )
        return json.dumps({"error": str(exc)})
