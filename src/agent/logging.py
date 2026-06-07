"""JSON run logging for the simple agent."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_log_path() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return Path(__file__).resolve().parent / "logs" / f"agent_run_{stamp}.json"


class AgentRunLogger:
    """Collect per-turn usage/cost and save a compact JSON trajectory."""

    def __init__(self, *, model: str, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else default_log_path()
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

    def llm_turn(self, round_id: int, reply: dict[str, Any]) -> None:
        usage = reply.get("usage") or {}
        cost = reply.get("cost") or {}
        self.meta["rounds"] = max(self.meta["rounds"], round_id + 1)
        for key in self.meta["token_usage"]:
            self.meta["token_usage"][key] += int(usage.get(key) or 0)
        self.meta["expense_usd"] += float(cost.get("price_usd") or 0)
        self.event("llm_turn", round=round_id, reply=reply)

    def event(self, event: str, **data: Any) -> None:
        self.raw_trajectory.append({"ts": _now(), "event": event, **data})

    def save(self) -> Path:
        self.meta["ended_at"] = _now()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                {"meta": self.meta, "raw_trajectory": self.raw_trajectory},
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return self.path
