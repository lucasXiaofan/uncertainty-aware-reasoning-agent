#!/usr/bin/env python3
"""Bash-callable AgentClinic terminal tools.

Each call takes one JSON dictionary:
    {"tool_name": "final_diagnosis", "content": "Diagnosis name"}
    {"tool_name": "respond", "content": {"action": "ask_patient", "message": "..."}}
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any


TERMINATE_START_TAG = "<terminate>"
TERMINATE_END_TAG = "</terminate>"
TOOL_NAMES = ("final_diagnosis", "respond")
RESPOND_ACTIONS = ("ask_patient", "request_physical_examination", "request_test")


def load_payload(raw_input: str | None) -> dict[str, Any]:
    if raw_input is None or not raw_input.strip():
        raw_input = sys.stdin.read()
    if not isinstance(raw_input, str) or not raw_input.strip():
        raise ValueError("agentclinic_tools.py requires one JSON dictionary input")
    try:
        payload = json.loads(raw_input)
    except json.JSONDecodeError as exc:
        raise ValueError(f"input must be a valid JSON dictionary: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("input must be a JSON dictionary")
    return payload


def normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    tool_name = require_str(payload.get("tool_name"), "tool_name")
    if tool_name not in TOOL_NAMES:
        raise ValueError("tool_name must be one of: " + ", ".join(TOOL_NAMES))
    if "content" not in payload:
        raise ValueError("content is required")

    content = payload["content"]
    if tool_name == "final_diagnosis":
        normalized_content = require_str(content, "final_diagnosis content")
    else:
        normalized_content = normalize_response(content)

    return {
        "tool_name": tool_name,
        "content": normalized_content,
    }


def normalize_response(content: Any) -> dict[str, str]:
    if not isinstance(content, dict):
        raise ValueError("respond content must be a dictionary")
    action = require_str(content.get("action"), "respond action")
    if action not in RESPOND_ACTIONS:
        raise ValueError("respond action must be one of: " + ", ".join(RESPOND_ACTIONS))
    message = require_str(content.get("message"), "respond message")
    return {
        "action": action,
        "message": message,
    }


def require_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    value = value.strip()
    if not value:
        raise ValueError(f"{field_name} must not be empty")
    return value


def wrap_termination_output(payload: dict[str, Any]) -> str:
    return f"{TERMINATE_START_TAG}{json.dumps(payload, ensure_ascii=False)}{TERMINATE_END_TAG}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bash-callable AgentClinic terminal tools",
        usage=(
            "agentclinic_tools.py "
            '\'{"tool_name":"respond","content":{"action":"ask_patient","message":"..."}}\''
        ),
    )
    parser.add_argument("input", nargs="?", help="JSON dictionary with tool_name and content fields")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        payload = normalize_payload(load_payload(args.input))
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(wrap_termination_output(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
