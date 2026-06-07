"""A concise tool-using OpenAI agent loop."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .logging import AgentRunLogger
from .openai_llm_calling_core import chat_openai
from .tool_calling import BASH_TOOL, handle_tool_call, termination_result
from .working_memory import MEMORY_TOOL_SCHEMAS, WorkingMemory


class Agent:
    """Simple loop: read working memory, call OpenAI, run Bash tool calls, update memory."""

    def __init__(
        self,
        working_memory: WorkingMemory,
        *,
        model: str = "gpt-5.4-nano",
        tools: list[dict[str, Any]] | None = None,
        max_steps: int = 8,
        retries: int = 2,
        temperature: float = 0.2,
        log_path: str | Path | None = None,
    ) -> None:
        self.working_memory = working_memory
        self.model = model
        self.tools = tools or [BASH_TOOL, *MEMORY_TOOL_SCHEMAS]
        self.max_steps = max_steps
        self.retries = retries
        self.temperature = temperature
        self.logger = AgentRunLogger(model=model, path=log_path)

    def run(self) -> dict[str, Any]:
        """Run until a terminating tool result is produced or `max_steps` is reached."""
        try:
            self.logger.event("run_start", messages=self.working_memory.get_messages())
            for step in range(self.max_steps):
                messages = self.working_memory.get_messages()
                reply = self._chat_with_retries(messages, step)
                self.logger.llm_turn(step, reply)
                self.working_memory.update(_assistant_message(reply))

                tool_calls = reply.get("tool_calls") or []
                if not tool_calls:
                    reminder = _termination_required_message()
                    self.working_memory.update(reminder)
                    self.logger.event(
                        "non_terminal_reply",
                        round=step,
                        reply=reply,
                        reminder=reminder,
                    )
                    continue

                for tool_call in tool_calls:
                    tool_result = handle_tool_call(
                        tool_call["function"]["name"],
                        tool_call["function"].get("arguments", "{}"),
                        working_memory=self.working_memory,
                    )
                    termination = termination_result(tool_result)
                    tool_message = {
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": (
                            json.dumps(termination, ensure_ascii=False)
                            if termination is not None
                            else tool_result
                        ),
                    }
                    self.working_memory.update(tool_message)
                    self.logger.event(
                        "tool_call",
                        round=step,
                        tool_call=tool_call,
                        tool_result=tool_message,
                    )
                    if termination is not None:
                        return {
                            "role": "assistant",
                            "content": json.dumps(termination, ensure_ascii=False),
                        }
            raise RuntimeError(f"agent reached max_steps={self.max_steps}")
        except Exception as exc:
            self.logger.event("run_error", error=str(exc))
            raise
        finally:
            self.logger.save()

    def _chat_with_retries(
        self,
        messages: list[dict[str, Any]],
        step: int,
    ) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                return chat_openai(
                    messages,
                    model=self.model,
                    temperature=self.temperature,
                    tools=self.tools,
                )
            except Exception as exc:
                last_error = exc
                self.logger.event(
                    "chat_error",
                    round=step,
                    attempt=attempt,
                    error=str(exc),
                )
        raise RuntimeError(f"OpenAI call failed after {self.retries + 1} attempts") from last_error


def initialize_agent(
    working_memory: WorkingMemory,
    *,
    model: str = "gpt-5.4-nano",
    log_path: str | Path | None = None,
) -> Agent:
    """Create an `Agent` around any object with get_messages/update APIs."""
    return Agent(working_memory, model=model, log_path=log_path)


def _assistant_message(reply: dict[str, Any]) -> dict[str, Any]:
    message = {"role": "assistant", "content": reply.get("content", "")}
    if reply.get("tool_calls"):
        message["tool_calls"] = reply["tool_calls"]
    return message


def _termination_required_message() -> dict[str, str]:
    return {
        "role": "user",
        "content": (
            "This turn is not complete. Updating memory tools such as update_osce_note is not "
            "a terminal action, and plain text must not be returned to the hospital environment. "
            "Now call the bash tool with src/agent/agentclinic_tools.py to produce one AgentClinic "
            "termination payload: respond with ask_patient, request_physical_examination, "
            "request_test, or final_diagnosis."
        ),
    }
