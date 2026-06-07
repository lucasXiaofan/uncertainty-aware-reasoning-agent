#!/usr/bin/env python3
"""Clinic workflow tools for medical diagnosis agents.

Each call takes one JSON dictionary:
    {"type": "checklist|search|evidence|respond", "input": ...}
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from typing import Any


TOOL_TYPES = ("checklist", "search", "evidence", "respond")
EVIDENCE_ALIASES = {"evidance": "evidence"}
RESPOND_ACTIONS = ("request_test", "ask_patient", "make_diagnosis")
EVIDENCE_ITEM_FIELDS = ("title", "description", "is_supported", "reason", "source")


def log_action(action: str) -> None:
    print("ACTION:")
    print(action)
    print("")


def load_payload(raw_input: str | None) -> dict[str, Any]:
    if not isinstance(raw_input, str) or not raw_input.strip():
        raise ValueError("clinic_tools.py requires one JSON dictionary input")
    try:
        payload = json.loads(raw_input)
    except json.JSONDecodeError as exc:
        raise ValueError(f"input must be a valid JSON dictionary: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("input must be a JSON dictionary")
    return payload


def require_tool_input(payload: dict[str, Any]) -> tuple[str, Any]:
    raw_tool_type = payload.get("type")
    if raw_tool_type is None:
        raise ValueError("input requires top-level field 'type'")

    tool_type = str(raw_tool_type).strip().lower()
    tool_type = EVIDENCE_ALIASES.get(tool_type, tool_type)
    if tool_type not in TOOL_TYPES:
        raise ValueError(
            "type must be one of: "
            + ", ".join(TOOL_TYPES)
            + "; alias accepted: evidance"
        )
    if "input" not in payload:
        raise ValueError("input requires top-level field 'input'")
    return tool_type, payload["input"]


def require_str(value: Any, field_name: str) -> str:
    if value is None:
        raise ValueError(f"{field_name} is required")
    text = str(value).strip()
    if not text:
        raise ValueError(f"{field_name} must not be empty")
    return text


def optional_str(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        raise ValueError(f"{field_name} must not be empty when provided")
    return text


def normalize_bool(value: Any, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    raise ValueError(f"{field_name} must be true or false")


def first_present(item: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in item:
            return item[key]
    return None


def normalize_checklist(input_value: Any) -> list[dict[str, Any]]:
    if isinstance(input_value, dict):
        raw_items = input_value.get("items") or input_value.get("updates") or input_value.get("checklist")
    else:
        raw_items = input_value

    if not isinstance(raw_items, list) or not raw_items:
        raise ValueError("checklist input must be a non-empty list of dictionaries")

    normalized: list[dict[str, Any]] = []
    for index, raw_item in enumerate(raw_items, start=1):
        if not isinstance(raw_item, dict):
            raise ValueError(f"checklist item {index} must be a dictionary")
        raw_id = raw_item.get("id")
        if raw_id is None:
            raise ValueError(f"checklist item {index} requires 'id'")
        try:
            item_id = int(raw_id)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"checklist item {index} id must be a number") from exc

        content = optional_str(raw_item.get("content"), f"checklist item {index} content")
        raw_complete = first_present(
            raw_item,
            (
                "mark_as_complete",
                "mark as complete",
                "mark_complete",
                "complete",
                "is_complete",
                "done",
            ),
        )
        mark_as_complete = None
        if raw_complete is not None:
            mark_as_complete = normalize_bool(raw_complete, f"checklist item {index} mark_as_complete")

        reason_complete = optional_str(
            first_present(
                raw_item,
                ("reason_complete", "reason complete", "completion_reason", "complete_reason"),
            ),
            f"checklist item {index} reason_complete",
        )

        if content is None and mark_as_complete is None and reason_complete is None:
            raise ValueError(
                f"checklist item {index} must provide content, mark_as_complete, or reason_complete"
            )
        if reason_complete is not None and mark_as_complete is not True:
            raise ValueError(
                f"checklist item {index} reason_complete can only be used when mark_as_complete is true"
            )

        item: dict[str, Any] = {"id": item_id}
        if content is not None:
            item["content"] = content
        if mark_as_complete is not None:
            item["mark_as_complete"] = mark_as_complete
        if reason_complete is not None:
            item["reason_complete"] = reason_complete
        normalized.append(item)
    return normalized


def normalize_search(input_value: Any) -> list[str]:
    raw_queries: Any
    if isinstance(input_value, dict):
        raw_queries = (
            input_value.get("queries")
            or input_value.get("query")
            or input_value.get("searches")
            or input_value.get("search")
        )
    else:
        raw_queries = input_value

    if isinstance(raw_queries, str):
        queries = [raw_queries]
    elif isinstance(raw_queries, list):
        queries = raw_queries
    else:
        raise ValueError("search input must be a string, a list of strings, or a dictionary with query/queries")

    normalized = [str(query).strip() for query in queries if str(query).strip()]
    if not normalized:
        raise ValueError("search input must include at least one non-empty query")
    return list(dict.fromkeys(normalized))


def normalize_evidence(input_value: Any) -> list[dict[str, Any]]:
    if isinstance(input_value, dict):
        raw_items = input_value.get("updates") or input_value.get("items") or input_value.get("evidence")
        if raw_items is None and all(field in input_value for field in EVIDENCE_ITEM_FIELDS):
            raw_items = [input_value]
    else:
        raw_items = input_value

    if not isinstance(raw_items, list) or not raw_items:
        raise ValueError("evidence input must be a non-empty evidence item or list of evidence items")

    normalized: list[dict[str, Any]] = []
    for index, raw_item in enumerate(raw_items, start=1):
        if not isinstance(raw_item, dict):
            raise ValueError(f"evidence item {index} must be a dictionary")
        normalized.append(normalize_evidence_item(raw_item, index))
    return normalized


def normalize_evidence_item(item: dict[str, Any], index: int) -> dict[str, Any]:
    missing = [field for field in EVIDENCE_ITEM_FIELDS if field not in item]
    if missing:
        raise ValueError(f"evidence item {index} missing required field(s): {', '.join(missing)}")

    title = require_str(item["title"], f"evidence item {index} title")
    description = require_str(item["description"], f"evidence item {index} description")
    is_supported = normalize_bool(item["is_supported"], f"evidence item {index} is_supported")
    reason = require_str(item["reason"], f"evidence item {index} reason")
    source = require_str(item["source"], f"evidence item {index} source")

    return {
        "title": title,
        "description": description,
        "is_supported": is_supported,
        "reason": reason,
        "source": source,
    }


def normalize_respond(input_value: Any) -> dict[str, str]:
    if not isinstance(input_value, dict):
        raise ValueError("respond input must be a dictionary with action and content")
    action = require_str(input_value.get("action"), "respond action").lower()
    if action not in RESPOND_ACTIONS:
        raise ValueError("respond action must be one of: " + ", ".join(RESPOND_ACTIONS))
    content = require_str(input_value.get("content"), "respond content")
    return {"action": action, "content": content}


def cmd_checklist(input_value: Any) -> int:
    items = normalize_checklist(input_value)
    log_action("checklist")
    print("CHECKLIST_UPDATE:")
    print(json.dumps({"updates": items}, indent=2))
    return 0


def cmd_search(input_value: Any) -> int:
    queries = normalize_search(input_value)
    log_action("search")
    print("GUIDELINE_SEARCH_REQUEST:")
    print(
        json.dumps(
            {
                "queries": queries,
                "note": "Search medical guidelines for each natural-language query.",
            },
            indent=2,
        )
    )
    return 0


def cmd_evidence(input_value: Any) -> int:
    items = normalize_evidence(input_value)
    log_action("evidence")
    print("EVIDENCE_UPDATE:")
    print(json.dumps({"updates": items}, indent=2))
    return 0


def cmd_respond(input_value: Any) -> int:
    response = normalize_respond(input_value)
    log_action("respond " + response["action"])
    print("CLINIC_RESPONSE:")
    print(
        json.dumps(
            {
                **response,
                "timestamp": datetime.now().isoformat(),
            },
            indent=2,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Clinic workflow tools for medical diagnosis agents",
        usage='clinic_tools.py \'{"type":"checklist","input":[{"id":1,"content":"..."}]}\'',
    )
    parser.add_argument("input", help="JSON dictionary with top-level type and input fields")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        payload = load_payload(args.input)
        tool_type, input_value = require_tool_input(payload)
        if tool_type == "checklist":
            return cmd_checklist(input_value)
        if tool_type == "search":
            return cmd_search(input_value)
        if tool_type == "evidence":
            return cmd_evidence(input_value)
        if tool_type == "respond":
            return cmd_respond(input_value)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
