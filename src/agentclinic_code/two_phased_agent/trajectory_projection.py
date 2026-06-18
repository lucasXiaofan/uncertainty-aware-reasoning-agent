"""Project two-phased AgentClinic legacy trajectories into viewer protocol JSON."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from hashlib import sha256
from pathlib import Path
from typing import Any


PROTOCOL = "agent-observability"
PROTOCOL_VERSION = "1.0.0"


def project_trajectory_file(
    trajectory_path: str | Path,
    output_path: str | Path,
    *,
    dataset: str = "AgentClinic",
    scenario_id: int | str | None = None,
    correct_diagnosis: Any = None,
    correct: bool | None = None,
    source: dict[str, Any] | None = None,
) -> Path:
    """Read a legacy trajectory JSON file and write materialized ``run.v1.json``."""
    trajectory_path = Path(trajectory_path)
    legacy = json.loads(trajectory_path.read_text(encoding="utf-8"))
    projection = project_trajectory(
        legacy,
        run_id=trajectory_path.stem,
        dataset=dataset,
        scenario_id=scenario_id,
        correct_diagnosis=correct_diagnosis,
        correct=correct,
        source=source,
    )
    return write_projection(projection, output_path)


def project_trajectory(
    legacy: dict[str, Any],
    *,
    run_id: str,
    dataset: str = "AgentClinic",
    scenario_id: int | str | None = None,
    correct_diagnosis: Any = None,
    correct: bool | None = None,
    source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convert the current ``turns[].raw_trajectory`` log into viewer data."""
    osce_note = _empty_osce_note()
    evidence: list[dict[str, Any]] = []
    agent_records = _empty_agents(legacy.get("model"))
    all_usage: list[dict[str, Any]] = []
    invocation_order: list[str] = []

    turns = legacy.get("turns") or []
    for index, turn in enumerate(turns, start=1):
        phase = turn.get("phase") or "information_seeking"
        agent = agent_records.get(phase) or agent_records["information_seeking"]
        invocation_id = f"inv_{index:04d}"
        invocation_order.append(invocation_id)

        meta = turn.get("meta") or {}
        invocation_usage = _usage(meta)
        all_usage.append(invocation_usage)
        raw_events = turn.get("raw_trajectory") or []
        start_messages = _run_start_messages(raw_events)
        static_memory = _extract_static_memory(start_messages)
        _set_agent_instruction(agent, static_memory)

        if not agent["initial_input"]:
            input_text = turn.get("hospital_response") or legacy.get("objective") or ""
            agent["initial_input"] = {
                "summary": _summarize(input_text),
                "text": input_text,
            }

        invocation = _project_invocation(
            turn,
            invocation_id=invocation_id,
            global_sequence=index,
            agent_sequence=len(agent["invocations"]) + 1,
            start_messages=start_messages,
            osce_note=osce_note,
            evidence=evidence,
            legacy_objective=legacy.get("objective"),
            usage=invocation_usage,
        )
        agent["invocations"].append(invocation)
        agent["final_output"] = invocation["final_output"]

    for agent in agent_records.values():
        tool_names = sorted(
            {
                name
                for invocation in agent["invocations"]
                for name in invocation.get("tool_names", [])
            }
        )
        agent["tools"] = [{"name": name, "schema_sha256": None} for name in tool_names]
        agent["usage"] = _sum_usage(
            invocation["usage"] for invocation in agent["invocations"]
        )
        if not agent["instruction"]["resolved_text"]:
            agent["instruction"]["sha256"] = None

    final_text = _final_output_text(turns)
    final_diagnosis = final_text.removeprefix("DIAGNOSIS READY:").strip() or final_text
    status = "completed" if final_text.startswith("DIAGNOSIS READY:") else "incomplete"
    evaluation = None
    if correct_diagnosis is not None or correct is not None:
        evaluation = {"correct_diagnosis": correct_diagnosis, "correct": correct}

    run_source = {
        "entrypoint": "src/agentclinic_code/agentclinic_api_only.py",
        "doctor_interface": "src/agentclinic_code/two_phased_agent/two_agent_interface.py",
    }
    if source:
        run_source.update(source)

    return {
        "protocol": PROTOCOL,
        "protocol_version": PROTOCOL_VERSION,
        "run": {
            "run_id": run_id,
            "task_type": "agentclinic_patient_run",
            "dataset": dataset,
            "scenario_id": str(scenario_id if scenario_id is not None else run_id),
            "objective": legacy.get("objective"),
            "status": status,
            "started_at": _iso_min((turn.get("meta") or {}).get("started_at") for turn in turns),
            "ended_at": _iso_max((turn.get("meta") or {}).get("ended_at") for turn in turns),
            "duration_ms": None,
            "final_output": {"type": "final_diagnosis", "text": final_text},
            "evaluation": evaluation,
            "source": run_source,
        },
        "orchestration": {
            "strategy": "fixed_sequence",
            "description": (
                "Nine information-seeking invocations followed by one "
                "differential-diagnosis invocation."
            ),
            "planned_steps": [
                {
                    "agent_id": "agent_information_seeking",
                    "repeat": legacy.get("information_rounds", 9),
                    "termination": "respond",
                },
                {
                    "agent_id": "agent_differential_diagnosis",
                    "repeat": 1,
                    "termination": "final_diagnosis",
                },
            ],
            "actual_invocation_order": invocation_order,
        },
        "highlights": _highlights(osce_note, evidence, final_text, final_diagnosis),
        "agents": [
            agent_records["information_seeking"],
            agent_records["differential_diagnosis"],
        ],
        "artifacts": [],
        "metrics": {
            "agent_count": 2,
            "invocation_count": len(invocation_order),
            "round_count": sum(
                len(invocation["rounds"])
                for agent in agent_records.values()
                for invocation in agent["invocations"]
            ),
            "usage": _sum_usage(all_usage),
        },
        "errors": [],
    }


def write_projection(projection: dict[str, Any], output_path: str | Path) -> Path:
    """Atomically write a materialized projection."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    tmp_path.write_text(
        json.dumps(projection, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    tmp_path.replace(output_path)
    return output_path


def _project_invocation(
    turn: dict[str, Any],
    *,
    invocation_id: str,
    global_sequence: int,
    agent_sequence: int,
    start_messages: list[dict[str, Any]],
    osce_note: dict[str, Any],
    evidence: list[dict[str, Any]],
    legacy_objective: Any,
    usage: dict[str, Any],
) -> dict[str, Any]:
    phase = turn.get("phase") or "information_seeking"
    raw_events = turn.get("raw_trajectory") or []
    tool_events = [event for event in raw_events if event.get("event") == "tool_call"]
    rounds: list[dict[str, Any]] = []
    tool_names: list[str] = []
    execution_summary: list[dict[str, Any]] = []

    for round_index, llm_event in enumerate(
        [event for event in raw_events if event.get("event") == "llm_turn"],
        start=1,
    ):
        round_number = llm_event.get("round", round_index - 1)
        round_tool_events = [
            event for event in tool_events if event.get("round") == round_number
        ]
        round_tool_calls, memory_changes = _project_tool_calls(
            round_tool_events,
            osce_note=osce_note,
            evidence=evidence,
            tool_names=tool_names,
            execution_summary=execution_summary,
        )
        reply = llm_event.get("reply") or {}
        assistant_tool_calls = reply.get("tool_calls") or []
        rounds.append(
            {
                "round_id": f"{invocation_id}_round_{round_index:02d}",
                "sequence": round_index,
                "status": "completed",
                "started_at": llm_event.get("ts"),
                "ended_at": (
                    round_tool_events[-1].get("ts")
                    if round_tool_events
                    else llm_event.get("ts")
                ),
                "duration_ms": None,
                "input": {
                    "messages": start_messages if round_index == 1 else [],
                    "message_count": len(start_messages) if round_index == 1 else 0,
                    "artifact_ids": [],
                },
                "assistant": {
                    "content": reply.get("content") or "",
                    "tool_call_ids": [
                        tool_call.get("id") for tool_call in assistant_tool_calls
                    ],
                },
                "tool_calls": round_tool_calls,
                "memory_changes": memory_changes,
                "retries": [],
                "usage": {
                    **_usage(reply.get("usage") or {}),
                    "expense_usd": (reply.get("cost") or {}).get("price_usd"),
                },
            }
        )

    final_payload = _agentclinic_payload_from_tool_event(tool_events[-1]) if tool_events else None
    input_text = turn.get("hospital_response") or legacy_objective or ""
    return {
        "invocation_id": invocation_id,
        "global_sequence": global_sequence,
        "agent_sequence": agent_sequence,
        "phase": phase,
        "status": "completed",
        "started_at": (turn.get("meta") or {}).get("started_at"),
        "ended_at": (turn.get("meta") or {}).get("ended_at"),
        "duration_ms": None,
        "input": {
            "source": "orchestrator" if phase == "differential_diagnosis" else "patient",
            "summary": _summarize(input_text),
            "text": input_text,
            "content_parts": [],
            "artifact_ids": [],
        },
        "state_before": {},
        "execution_summary": execution_summary,
        "tool_names": sorted({name for name in tool_names if name}),
        "final_output": _final_output(turn, final_payload),
        "state_after": {},
        "usage": usage,
        "rounds": rounds,
    }


def _project_tool_calls(
    tool_events: list[dict[str, Any]],
    *,
    osce_note: dict[str, Any],
    evidence: list[dict[str, Any]],
    tool_names: list[str],
    execution_summary: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    projected = []
    memory_changes: list[dict[str, Any]] = []
    for index, event in enumerate(tool_events, start=1):
        tool_call = event.get("tool_call") or {}
        function = tool_call.get("function") or {}
        name = function.get("name")
        arguments = function.get("arguments")
        parsed_arguments = _parse_json(arguments)
        if not isinstance(parsed_arguments, dict):
            parsed_arguments = {"arguments_raw": arguments}
        if name == "bash":
            parsed_arguments = dict(parsed_arguments)
            parsed_arguments["agentclinic_payload"] = _agentclinic_payload_from_bash(arguments)

        result = _tool_result_content(event.get("tool_result"))
        label = _execution_label(name, result)
        tool_names.append(name)
        execution_summary.append(
            {
                "sequence": len(execution_summary) + 1,
                "kind": "tool_call",
                "label": label,
            }
        )
        memory_changes.extend(
            _apply_memory_tool(name, arguments, osce_note=osce_note, evidence=evidence)
        )
        projected.append(
            {
                "tool_call_id": tool_call.get("id") or f"tc_{index:02d}",
                "sequence": index,
                "name": name,
                "arguments": parsed_arguments,
                "status": "completed",
                "result": result,
                "result_artifact_id": None,
                "started_at": event.get("ts"),
                "ended_at": event.get("ts"),
                "duration_ms": None,
            }
        )
    return projected, memory_changes


def _apply_memory_tool(
    name: str | None,
    arguments: Any,
    *,
    osce_note: dict[str, Any],
    evidence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    parsed = _parse_json(arguments)
    if not isinstance(parsed, dict):
        return []

    changes = []
    if name == "update_osce_note":
        for item in parsed.get("items", []):
            section = item.get("section")
            content = item.get("content")
            if not section:
                continue
            if section == "differential_diagnosis_list":
                osce_note[section] = content or ""
            else:
                osce_note.setdefault(section, [])
                if content and content not in osce_note[section]:
                    osce_note[section].append(content)
            changes.append(
                {
                    "memory_type": "osce_note",
                    "operation": "upsert",
                    "section": section,
                    "content": content,
                }
            )
    elif name == "update_evidence":
        for item in parsed.get("items", []):
            evidence.append(item)
            changes.append(
                {"memory_type": "evidence", "operation": "append", "item": item}
            )
    return changes


def _empty_agents(model: str | None) -> dict[str, dict[str, Any]]:
    return {
        "information_seeking": {
            "agent_id": "agent_information_seeking",
            "agent_type": "information_seeking",
            "display_name": "Information Seeking Agent",
            "model": model,
            "instruction": {
                "source_path": "src/agent/prompts/agentclinic_information_gathering.md",
                "sha256": None,
                "resolved_text": "",
                "summary": "Gather clinical information and maintain the OSCE note.",
            },
            "tools": [],
            "status": "completed",
            "initial_input": {},
            "final_output": {},
            "summary": {},
            "usage": {},
            "invocations": [],
        },
        "differential_diagnosis": {
            "agent_id": "agent_differential_diagnosis",
            "agent_type": "differential_diagnosis",
            "display_name": "Differential Diagnosis Agent",
            "model": model,
            "instruction": {
                "source_path": "src/agent/prompts/agentclinic_differential_diagnosis.md",
                "sha256": None,
                "resolved_text": "",
                "summary": "Compare candidates and return one final diagnosis.",
            },
            "tools": [],
            "status": "completed",
            "initial_input": {},
            "final_output": {},
            "summary": {},
            "usage": {},
            "invocations": [],
        },
    }


def _set_agent_instruction(agent: dict[str, Any], static_memory: dict[str, Any]) -> None:
    prompt = static_memory.get("system_prompt")
    if not prompt or agent["instruction"]["resolved_text"]:
        return
    agent["instruction"]["resolved_text"] = prompt
    agent["instruction"]["sha256"] = sha256(prompt.encode("utf-8")).hexdigest()


def _empty_osce_note() -> dict[str, Any]:
    return {
        "patient_demographics": [],
        "patient_medical_history": [],
        "patient_social_history": [],
        "patient_symptoms": [],
        "physical_exmination_findings": [],
        "test_results": [],
        "differential_diagnosis_list": "",
    }


def _highlights(
    osce_note: dict[str, Any],
    evidence: list[dict[str, Any]],
    final_text: str,
    final_diagnosis: str,
) -> list[dict[str, Any]]:
    diagnoses = [
        diagnosis.strip()
        for diagnosis in str(osce_note.get("differential_diagnosis_list", "")).split(";")
        if diagnosis.strip()
    ]
    return [
        {
            "highlight_id": "highlight_final_osce_note",
            "type": "osce_note",
            "title": "Final OSCE Note",
            "producer_agent_id": "agent_information_seeking",
            "source_invocation_id": "inv_0009",
            "is_final": True,
            "updated_at": None,
            "data": osce_note,
        },
        {
            "highlight_id": "highlight_differential",
            "type": "differential_diagnosis_list",
            "title": "Final Differential",
            "producer_agent_id": "agent_information_seeking",
            "source_invocation_id": "inv_0009",
            "is_final": True,
            "updated_at": None,
            "data": {"diagnoses": diagnoses},
        },
        {
            "highlight_id": "highlight_evidence",
            "type": "diagnostic_evidence",
            "title": "Diagnostic Evidence",
            "producer_agent_id": "agent_differential_diagnosis",
            "source_invocation_id": "inv_0010",
            "is_final": True,
            "updated_at": None,
            "data": {"items": evidence},
        },
        {
            "highlight_id": "highlight_final_diagnosis",
            "type": "final_diagnosis",
            "title": "Final Diagnosis",
            "producer_agent_id": "agent_differential_diagnosis",
            "source_invocation_id": "inv_0010",
            "is_final": True,
            "updated_at": None,
            "data": {"diagnosis": final_diagnosis, "display_text": final_text},
        },
    ]


def _run_start_messages(raw_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for event in raw_events:
        if event.get("event") == "run_start":
            return event.get("messages") or []
    return []


def _extract_static_memory(messages: list[dict[str, Any]]) -> dict[str, Any]:
    for message in messages:
        if message.get("role") != "system":
            continue
        content = message.get("content") or ""
        match = re.search(r"STATIC MEMORY\n(.*?)\n\nDYNAMIC MEMORY", content, re.S)
        if not match:
            continue
        parsed = _parse_json(match.group(1))
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _agentclinic_payload_from_tool_event(event: dict[str, Any] | None) -> dict[str, Any] | None:
    if not event:
        return None
    result = _tool_result_content(event.get("tool_result"))
    return result if isinstance(result, dict) and result.get("tool_name") else None


def _agentclinic_payload_from_bash(arguments: Any) -> dict[str, Any] | None:
    parsed = _parse_json(arguments)
    if not isinstance(parsed, dict):
        return None
    command = str(parsed.get("command") or "")
    match = re.search(r"agentclinic_tools\.py\s+'(.*?)'", command)
    if not match:
        return None
    payload = _parse_json(match.group(1))
    return payload if isinstance(payload, dict) else None


def _tool_result_content(tool_result: dict[str, Any] | None) -> Any:
    if not isinstance(tool_result, dict):
        return None
    return _parse_json(tool_result.get("content"))


def _parse_json(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _execution_label(name: str | None, result: Any) -> str:
    if name == "bash" and isinstance(result, dict):
        return str(result.get("tool_name") or name)
    return str(name or "unknown")


def _final_output(turn: dict[str, Any], payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {
            "type": "unknown",
            "text": turn.get("doctor_message") or "",
            "raw_payload": {},
        }
    if payload.get("tool_name") == "respond":
        return {
            "type": (payload.get("content") or {}).get("action"),
            "text": turn.get("doctor_message") or "",
            "raw_payload": payload,
        }
    if payload.get("tool_name") == "final_diagnosis":
        return {
            "type": "final_diagnosis",
            "text": turn.get("doctor_message") or "",
            "raw_payload": payload,
        }
    return {
        "type": str(payload.get("tool_name") or "unknown"),
        "text": turn.get("doctor_message") or "",
        "raw_payload": payload,
    }


def _final_output_text(turns: list[dict[str, Any]]) -> str:
    if not turns:
        return ""
    return str(turns[-1].get("doctor_message") or "")


def _usage(value: dict[str, Any]) -> dict[str, Any]:
    token_usage = value.get("token_usage", value) if isinstance(value, dict) else {}
    return {
        "input_tokens": token_usage.get("input_tokens"),
        "cached_input_tokens": token_usage.get("cached_input_tokens"),
        "output_tokens": token_usage.get("output_tokens"),
        "total_tokens": token_usage.get("total_tokens"),
        "expense_usd": value.get("expense_usd") if isinstance(value, dict) else None,
    }


def _sum_usage(items: Iterable[dict[str, Any]]) -> dict[str, Any]:
    totals = {
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "expense_usd": 0.0,
    }
    for item in items:
        for key in ("input_tokens", "cached_input_tokens", "output_tokens", "total_tokens"):
            totals[key] += int(item.get(key) or 0)
        totals["expense_usd"] += float(item.get("expense_usd") or 0.0)
    return totals


def _iso_min(values: Iterable[str | None]) -> str | None:
    known = [value for value in values if value]
    return min(known) if known else None


def _iso_max(values: Iterable[str | None]) -> str | None:
    known = [value for value in values if value]
    return max(known) if known else None


def _summarize(value: Any, limit: int = 180) -> str:
    text = str(value or "").replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."
