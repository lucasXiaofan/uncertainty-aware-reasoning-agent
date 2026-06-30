"""Thread-safe JSON logging for agent runs and AgentClinic visualizations."""

from __future__ import annotations

import csv
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_log_path() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    return (
        Path(__file__).resolve().parent
        / "logs"
        / f"agent_run_{stamp}_{os.getpid()}_{threading.get_ident()}.json"
    )


def _jsonable(value: Any) -> Any:
    """Return a JSON-safe deep copy without requiring all callers to sanitize."""
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return _jsonable(value) if isinstance(value, dict) else {}


def _csv_cell(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return json.dumps(_jsonable(value), ensure_ascii=False)


class AgentRunLogger:
    """Collect and atomically save task, agent, doctor, and highlight logs.

    The class is safe to share between concurrently-running threads. Writes use
    a same-directory temporary file followed by ``os.replace`` so readers never
    observe partial JSON. Separate processes should still use separate log paths
    unless intentionally overwriting a shared latest-log file.
    """

    def __init__(
        self,
        *,
        model: str,
        path: str | Path | None = None,
        agent_name: str = "agent",
        patient_id: str | int | None = None,
        problem: Any = None,
        environment: dict[str, Any] | None = None,
        result: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        autosave: bool = True,
        result_csv_path: str | Path | None = None,
    ) -> None:
        self.path = Path(path) if path else default_log_path()
        self.result_csv_path = Path(result_csv_path) if result_csv_path else None
        self.autosave = autosave
        self._lock = threading.RLock()
        self._active_run_index: int | None = None
        self._local = threading.local()

        self.meta: dict[str, Any] = {
            "model": model,
            "started_at": _now(),
            "rounds": 0,
            "token_usage": {
                "input_tokens": 0,
                "cached_input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
            },
            "expense_usd": 0.0,
        }
        self.raw_trajectory: list[dict[str, Any]] = []

        base_metadata = {
            "date_time": self.meta["started_at"],
            "agent_name": agent_name,
            "patient_id": patient_id,
        }
        if metadata:
            base_metadata.update(_dict_or_empty(metadata))

        self.task_visualization: dict[str, Any] = {
            "problem": _jsonable(problem) if problem is not None else {},
            "environment": _dict_or_empty(environment),
            "result": _dict_or_empty(result),
            "metadata": base_metadata,
        }
        self.agent_visualization: dict[str, Any] = {
            "agent_system_prompt": "",
            "runs": [],
        }
        self.highlight_visualization: dict[str, Any] = {
            "template": {
                "summary": "",
                "key_events": [],
                "notes": {},
            },
            "highlights": [],
        }
        self.doctor_visualization: dict[str, Any] = {
            "template": {
                "doctor_name": agent_name,
                "case_summary": "",
                "diagnostic_reasoning": "",
                "notes": {},
            },
            "turns": [],
        }

    def set_task(
        self,
        *,
        problem: Any | None = None,
        environment: dict[str, Any] | None = None,
        result: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        with self._lock:
            if problem is not None:
                self.task_visualization["problem"] = _jsonable(problem)
            if environment is not None:
                self.task_visualization["environment"] = _dict_or_empty(environment)
            if result is not None:
                self.task_visualization["result"] = _dict_or_empty(result)
            if metadata:
                self.task_visualization["metadata"].update(_dict_or_empty(metadata))
            self._flush_if_needed_locked()

    def update_task_result(self, result: dict[str, Any]) -> None:
        with self._lock:
            self.task_visualization["result"] = _dict_or_empty(result)
            self.event_locked("task_result", result=result)
            self._write_result_csv_locked(self.task_visualization["result"])
            self._flush_if_needed_locked()

    def record_agent_system_prompt(self, system_prompt: Any) -> None:
        with self._lock:
            self.agent_visualization["agent_system_prompt"] = str(system_prompt or "")
            self._flush_if_needed_locked()

    def start_agent_run(
        self,
        messages: list[dict[str, Any]],
        *,
        run_name: str = "agent",
        metadata: dict[str, Any] | None = None,
    ) -> int:
        with self._lock:
            system_prompt = self._first_system_prompt(messages)
            if system_prompt and not self.agent_visualization["agent_system_prompt"]:
                self.agent_visualization["agent_system_prompt"] = system_prompt

            run = {
                "run_id": len(self.agent_visualization["runs"]),
                "run_name": run_name,
                "started_at": _now(),
                "input": _jsonable(messages),
                "turns": [],
                "result": {},
                "metadata": _dict_or_empty(metadata),
            }
            self.agent_visualization["runs"].append(run)
            self._active_run_index = run["run_id"]
            self._local.run_index = run["run_id"]
            self.event_locked("run_start", messages=messages, run_name=run_name)
            self._flush_if_needed_locked()
            return run["run_id"]

    def llm_turn(
        self,
        round_id: int,
        reply: dict[str, Any],
        *,
        input_messages: list[dict[str, Any]] | None = None,
        run_id: int | None = None,
    ) -> None:
        usage = _dict_or_empty(reply.get("usage") or {})
        cost = _dict_or_empty(reply.get("cost") or {})
        with self._lock:
            self.meta["rounds"] = max(self.meta["rounds"], round_id + 1)
            for key in self.meta["token_usage"]:
                self.meta["token_usage"][key] += int(usage.get(key) or 0)
            self.meta["expense_usd"] += float(cost.get("price_usd") or 0)
            self._record_agent_turn_locked(
                round_id=round_id,
                input_messages=input_messages,
                output=reply,
                run_id=run_id,
            )
            self.event_locked("llm_turn", round=round_id, reply=reply)
            self._flush_if_needed_locked()

    def tool_call(
        self,
        round_id: int,
        tool_call: dict[str, Any],
        tool_result: dict[str, Any] | str,
        *,
        run_id: int | None = None,
    ) -> None:
        with self._lock:
            turn = self._ensure_turn_locked(round_id, run_id=run_id)
            turn.setdefault("tool_calls", []).append(
                {
                    "tool_call": _jsonable(tool_call),
                    "tool_result": _jsonable(tool_result),
                }
            )
            self.event_locked(
                "tool_call",
                round=round_id,
                tool_call=tool_call,
                tool_result=tool_result,
            )
            self._flush_if_needed_locked()

    def finish_agent_run(
        self,
        *,
        result: dict[str, Any] | None = None,
        error: str | None = None,
        run_id: int | None = None,
    ) -> None:
        with self._lock:
            active_run_index = self._current_run_index_locked(run_id)
            if active_run_index is not None:
                run = self.agent_visualization["runs"][active_run_index]
                run["ended_at"] = _now()
                if result is not None:
                    run["result"] = _dict_or_empty(result)
                if error is not None:
                    run["error"] = error
            if error is not None:
                self.event_locked("run_error", error=error)
            self._flush_if_needed_locked()

    def doctor_turn(
        self,
        *,
        inference: int | None = None,
        phase: str | None = None,
        task: Any = None,
        environment_source: str | None = None,
        environment_response: Any = None,
        doctor_response: Any = None,
        hospital_response: Any = None,
        doctor_message: Any = None,
        uncertainty_reasoning: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        with self._lock:
            environment_response = (
                hospital_response if environment_response is None else environment_response
            )
            doctor_response = doctor_message if doctor_response is None else doctor_response
            turn = {
                "ts": _now(),
                "inference": inference,
                "phase": phase,
                "task": _jsonable(task),
                "environment_source": environment_source,
                "environment_response": _jsonable(environment_response),
                "doctor_response": _jsonable(doctor_response),
                # Backward-compatible aliases used by existing viewers/tests.
                "hospital_response": _jsonable(hospital_response),
                "doctor_message": _jsonable(doctor_message),
                "uncertainty_reasoning": _jsonable(uncertainty_reasoning),
                "metadata": _dict_or_empty(metadata),
            }
            self.doctor_visualization["turns"].append(turn)
            self.event_locked("doctor_turn", turn=turn)
            self._flush_if_needed_locked()

    def highlight(
        self,
        kind: str,
        *,
        title: str = "",
        data: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        with self._lock:
            item = {
                "ts": _now(),
                "kind": kind,
                "title": title,
                "data": _jsonable(data),
                "metadata": _dict_or_empty(metadata),
            }
            self.highlight_visualization["highlights"].append(item)
            self.event_locked("highlight", highlight=item)
            self._flush_if_needed_locked()

    def event(self, event: str, **data: Any) -> None:
        with self._lock:
            self.event_locked(event, **data)
            self._flush_if_needed_locked()

    def event_locked(self, event: str, **data: Any) -> None:
        self.raw_trajectory.append({"ts": _now(), "event": event, **_jsonable(data)})

    def save(self) -> Path:
        with self._lock:
            self.meta["ended_at"] = _now()
            self._write_locked()
            return self.path

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return self._snapshot_locked()

    def _record_agent_turn_locked(
        self,
        *,
        round_id: int,
        input_messages: list[dict[str, Any]] | None,
        output: dict[str, Any],
        run_id: int | None = None,
    ) -> None:
        turn = self._ensure_turn_locked(round_id, run_id=run_id)
        if input_messages is not None:
            turn["input"] = _jsonable(input_messages)
        turn["output"] = _jsonable(output)

    def _ensure_turn_locked(
        self,
        round_id: int,
        *,
        run_id: int | None = None,
    ) -> dict[str, Any]:
        active_run_index = self._current_run_index_locked(run_id)
        if active_run_index is None:
            active_run_index = self.start_agent_run([], run_name="agent")
        run = self.agent_visualization["runs"][active_run_index]
        for turn in run["turns"]:
            if turn.get("round") == round_id:
                return turn
        turn = {"round": round_id, "input": [], "output": {}, "tool_calls": []}
        run["turns"].append(turn)
        return turn

    def _current_run_index_locked(self, run_id: int | None = None) -> int | None:
        if run_id is not None:
            return run_id
        local_run_index = getattr(self._local, "run_index", None)
        return local_run_index if local_run_index is not None else self._active_run_index

    def _flush_if_needed_locked(self) -> None:
        if self.autosave:
            self.meta["last_saved_at"] = _now()
            self._write_locked()

    def _write_locked(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_name(
            f".{self.path.name}.{os.getpid()}.{threading.get_ident()}.tmp"
        )
        temp_path.write_text(
            json.dumps(self._snapshot_locked(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(temp_path, self.path)

    def _write_result_csv_locked(self, result: dict[str, Any]) -> None:
        if not self.result_csv_path:
            return
        self.result_csv_path.parent.mkdir(parents=True, exist_ok=True)
        row = {key: _csv_cell(value) for key, value in result.items()}
        needs_header = (
            not self.result_csv_path.exists()
            or self.result_csv_path.stat().st_size == 0
        )
        with self.result_csv_path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(row))
            if needs_header:
                writer.writeheader()
            writer.writerow(row)

    def _snapshot_locked(self) -> dict[str, Any]:
        return _jsonable(
            {
                "schema_version": "agent_run_logger.v2",
                "meta": self.meta,
                "task_visualization": self.task_visualization,
                "agent_visualization": self.agent_visualization,
                "highlight_visualization": self.highlight_visualization,
                "doctor_visualization": self.doctor_visualization,
                "raw_trajectory": self.raw_trajectory,
            }
        )

    def _first_system_prompt(self, messages: list[dict[str, Any]]) -> str:
        for message in messages:
            if message.get("role") == "system":
                return str(message.get("content") or "")
        return ""
