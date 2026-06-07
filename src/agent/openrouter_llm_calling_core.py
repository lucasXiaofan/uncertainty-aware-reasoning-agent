from __future__ import annotations

import os
from typing import Any, Sequence

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def _require_message(response: Any, *, model: str) -> Any:
    choices = getattr(response, "choices", None)
    if not choices:
        raise RuntimeError(f"OpenRouter chat returned no choices for model {model}")
    message = choices[0].message
    if message is None:
        raise RuntimeError(f"OpenRouter chat returned an empty message for model {model}")
    return message


def _extract_usage(response: Any) -> dict[str, Any] | None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    if hasattr(usage, "model_dump"):
        raw_usage = usage.model_dump()
    elif hasattr(usage, "dict"):
        raw_usage = usage.dict()
    else:
        raw_usage = {
            key: getattr(usage, key)
            for key in ("prompt_tokens", "completion_tokens", "total_tokens")
            if getattr(usage, key, None) is not None
        }
    return {
        "input_tokens": raw_usage.get("prompt_tokens"),
        "output_tokens": raw_usage.get("completion_tokens"),
        "total_tokens": raw_usage.get("total_tokens"),
        "raw": raw_usage,
    }


def call_openrouter(
    messages: Sequence[dict[str, Any]],
    *,
    model: str,
    temperature: float = 0.5,
    api_key: str | None = None,
    base_url: str = OPENROUTER_BASE_URL,
) -> str:
    if not messages:
        raise ValueError("messages must not be empty")

    api_key = api_key or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENROUTER_API_KEY is not set")

    client = OpenAI(api_key=api_key, base_url=base_url)
    response = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=_to_openai_messages(messages),
    )
    return _require_message(response, model=model).content or ""


def chat_openrouter(
    messages: Sequence[dict[str, Any]],
    *,
    model: str,
    temperature: float = 0.5,
    tools: Sequence[dict[str, Any]] | None = None,
    api_key: str | None = None,
    base_url: str = OPENROUTER_BASE_URL,
) -> dict[str, Any]:
    if not messages:
        raise ValueError("messages must not be empty")

    api_key = api_key or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENROUTER_API_KEY is not set")

    client = OpenAI(api_key=api_key, base_url=base_url)
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
    usage = _extract_usage(response)
    if usage:
        result["usage"] = usage
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
