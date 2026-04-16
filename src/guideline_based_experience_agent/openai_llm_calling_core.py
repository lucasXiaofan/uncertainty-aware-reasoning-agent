from __future__ import annotations

import json
import os
from typing import Any, Sequence

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv() -> bool:
        return False


load_dotenv()


def _create_client(api_key: str):
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise ImportError("openai package is required to call the language model") from exc
    return OpenAI(api_key=api_key)


def _require_message(response: Any, *, model: str) -> Any:
    choices = getattr(response, "choices", None)
    if not choices:
        raise RuntimeError(f"OpenAI chat returned no choices for model {model}")
    message = choices[0].message
    if message is None:
        raise RuntimeError(f"OpenAI chat returned an empty message for model {model}")
    return message


def call_openai(
    messages: Sequence[dict[str, Any]],
    *,
    model: str,
    temperature: float = 0.5,
    api_key: str | None = None,
) -> str:
    if not messages:
        raise ValueError("messages must not be empty")

    api_key = api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY is not set")

    client = _create_client(api_key)
    response = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=_to_openai_messages(messages),
    )
    return _require_message(response, model=model).content or ""


def chat_openai(
    messages: Sequence[dict[str, Any]],
    *,
    model: str,
    temperature: float = 0.5,
    tools: Sequence[dict[str, Any]] | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    if not messages:
        raise ValueError("messages must not be empty")

    api_key = api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY is not set")

    client = _create_client(api_key)
    kwargs: dict[str, Any] = {
        "model": model,
        "temperature": temperature,
        "messages": _to_openai_messages(messages),
    }
    if tools:
        kwargs["tools"] = list(tools)

    response = client.chat.completions.create(**kwargs)
    message = _require_message(response, model=model)
    result: dict[str, Any] = {"role": message.role, "content": message.content or ""}
    if message.tool_calls:
        result["tool_calls"] = [
            {
                "id": tool_call.id,
                "type": tool_call.type,
                "function": {
                    "name": tool_call.function.name,
                    "arguments": tool_call.function.arguments,
                },
            }
            for tool_call in message.tool_calls
        ]
    return result


def call_openai_json(
    messages: Sequence[dict[str, Any]],
    *,
    model: str,
    temperature: float = 0.2,
    api_key: str | None = None,
    response_format: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not messages:
        raise ValueError("messages must not be empty")

    api_key = api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY is not set")

    client = _create_client(api_key)
    kwargs: dict[str, Any] = {
        "model": model,
        "temperature": temperature,
        "messages": _to_openai_messages(messages),
        "response_format": response_format or {"type": "json_object"},
    }

    response = client.chat.completions.create(**kwargs)
    content = _require_message(response, model=model).content or "{}"
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Model {model} returned invalid JSON: {content}") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError(f"Model {model} returned non-object JSON: {parsed!r}")
    return parsed


def _to_openai_messages(messages: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    converted: list[dict[str, Any]] = []
    for message in messages:
        role = message["role"]
        content = message.get("content", "")
        images = message.get("images", [])
        payload: dict[str, Any] = {"role": role}
        if role == "tool":
            payload["content"] = content
            if message.get("tool_call_id"):
                payload["tool_call_id"] = message["tool_call_id"]
            if message.get("name"):
                payload["name"] = message["name"]
            converted.append(payload)
            continue
        if images:
            parts: list[dict[str, Any]] = [{"type": "text", "text": content}]
            for image in images:
                parts.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image}"},
                    }
                )
            payload["content"] = parts
        else:
            payload["content"] = content
        if role == "assistant" and message.get("tool_calls"):
            payload["tool_calls"] = message["tool_calls"]
        converted.append(payload)
    return converted
