"""Small OpenAI Chat Completions wrapper with multimodal/tool-call support.

Input standard:
- `messages` is a list of OpenAI-style chat messages: `{"role": "...", "content": ...}`.
- `content` may be a string or native multimodal parts. For convenience, user
  messages may also include `images=["base64-or-url"]`; bare base64 is sent as
  `data:image/jpeg;base64,...`.
- Tool calling uses OpenAI's standard `tools=[...]`, assistant `tool_calls`,
  and follow-up `{"role": "tool", "tool_call_id": "...", "content": "..."}`.

Use `chat_openai(...)` for the full result (`role`, `content`, `tool_calls`,
`usage`, and `cost` when the model is priced here). Use `call_openai(...)` for
text-only convenience.

Batch inference: write one JSONL request per line using the same body you would
pass to `client.chat.completions.create`, upload it, create a Batch job for
`/v1/chat/completions`, then read the output file. Set `billing_mode="batch"`
when estimating returned usage. Batch/Flex currently use discounted token rates.

Example:
    messages = [
        {"role": "system", "content": "Answer tersely."},
        {"role": "user", "content": "What is in this image?", "images": [jpg_b64]},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "lookup_patient",
                    "arguments": "{\"id\":\"p1\"}",
                },
            }],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "{\"age\":67}"},
        {"role": "user", "content": "Now combine the image and tool data."},
    ]
    tools = [{
        "type": "function",
        "function": {
            "name": "lookup_patient",
            "description": "Fetch patient metadata.",
            "parameters": {
                "type": "object",
                "properties": {"id": {"type": "string"}},
                "required": ["id"],
            },
        },
    }]
    result = chat_openai(messages, model="gpt-5.4-nano", tools=tools)
"""

from __future__ import annotations

import json
import os
from typing import Any, Literal, Mapping, Sequence

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

BillingMode = Literal["standard", "batch", "flex", "priority"]

# USD per 1M tokens from OpenAI pricing docs, checked 2026-05-20.
MODEL_PRICES_USD_PER_1M: dict[str, dict[BillingMode, dict[str, float]]] = {
    "gpt-5.4-mini": {
        "standard": {"input": 0.75, "cached_input": 0.075, "output": 4.50},
        "batch": {"input": 0.375, "cached_input": 0.0375, "output": 2.25},
        "flex": {"input": 0.375, "cached_input": 0.0375, "output": 2.25},
        "priority": {"input": 1.50, "cached_input": 0.15, "output": 9.00},
    },
    "gpt-5.4-nano": {
        "standard": {"input": 0.20, "cached_input": 0.02, "output": 1.25},
        "batch": {"input": 0.10, "cached_input": 0.01, "output": 0.625},
        "flex": {"input": 0.10, "cached_input": 0.01, "output": 0.625},
    },
}


def call_openai(
    messages: Sequence[dict[str, Any]],
    *,
    model: str,
    temperature: float = 0.5,
    api_key: str | None = None,
) -> str:
    """Return only assistant text; use `chat_openai` for usage/cost/tool calls."""
    return chat_openai(
        messages,
        model=model,
        temperature=temperature,
        api_key=api_key,
    )["content"]


def call_openai_json(
    messages: Sequence[dict[str, Any]],
    *,
    model: str,
    temperature: float = 0.2,
    api_key: str | None = None,
    response_format: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a parsed JSON object from the assistant response."""
    result = chat_openai(
        messages,
        model=model,
        temperature=temperature,
        api_key=api_key,
        response_format=response_format or {"type": "json_object"},
    )
    content = result["content"] or "{}"
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Model {model} returned invalid JSON: {content}") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError(f"Model {model} returned non-object JSON: {parsed!r}")
    return parsed


def chat_openai(
    messages: Sequence[dict[str, Any]],
    *,
    model: str,
    temperature: float = 0.5,
    tools: Sequence[dict[str, Any]] | None = None,
    api_key: str | None = None,
    billing_mode: BillingMode = "standard",
    response_format: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create one chat completion and return message, tool calls, usage, and cost."""
    if not messages:
        raise ValueError("messages must not be empty")

    client = OpenAI(api_key=_api_key(api_key))
    kwargs: dict[str, Any] = {
        "model": model,
        "temperature": temperature,
        "messages": _to_openai_messages(messages),
    }
    if tools:
        kwargs["tools"] = list(tools)
    if response_format:
        kwargs["response_format"] = response_format

    response = client.chat.completions.create(**kwargs)
    message = _require_message(response, model)
    usage = _usage(response)
    result: dict[str, Any] = {"role": message.role, "content": message.content or ""}
    if message.tool_calls:
        result["tool_calls"] = [_tool_call_dict(call) for call in message.tool_calls]
    if usage:
        result["usage"] = usage
        result["cost"] = calculate_cost(model, usage, billing_mode=billing_mode)
    return result


def calculate_cost(
    model: str,
    usage: Mapping[str, Any],
    *,
    billing_mode: BillingMode = "standard",
) -> dict[str, Any]:
    """Estimate USD cost from token usage; returns `price_usd=None` if unknown."""
    rates = MODEL_PRICES_USD_PER_1M.get(model, {}).get(billing_mode)
    if not rates:
        return {"price_usd": None, "billing_mode": billing_mode, "reason": "unknown_rate"}

    details = usage.get("prompt_tokens_details") or {}
    input_tokens = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
    cached_tokens = int(
        usage.get("cached_input_tokens") or details.get("cached_tokens") or 0
    )
    output_tokens = int(
        usage.get("output_tokens") or usage.get("completion_tokens") or 0
    )
    billable_input = max(input_tokens - cached_tokens, 0)
    price = (
        billable_input * rates["input"]
        + cached_tokens * rates["cached_input"]
        + output_tokens * rates["output"]
    ) / 1_000_000
    return {
        "price_usd": price,
        "billing_mode": billing_mode,
        "rates_usd_per_1m": rates,
        "billable_tokens": {
            "input": billable_input,
            "cached_input": cached_tokens,
            "output": output_tokens,
        },
    }


def _api_key(api_key: str | None) -> str:
    key = api_key or os.getenv("OPENAI_API_KEY")
    if not key:
        raise EnvironmentError("OPENAI_API_KEY is not set")
    return key


def _require_message(response: Any, model: str) -> Any:
    if not getattr(response, "choices", None):
        raise RuntimeError(f"OpenAI chat returned no choices for model {model}")
    message = response.choices[0].message
    if message is None:
        raise RuntimeError(f"OpenAI chat returned an empty message for model {model}")
    return message


def _usage(response: Any) -> dict[str, Any] | None:
    raw = _dump(getattr(response, "usage", None))
    if not raw:
        return None
    details = raw.get("prompt_tokens_details") or {}
    return {
        "input_tokens": raw.get("prompt_tokens"),
        "cached_input_tokens": details.get("cached_tokens", 0),
        "output_tokens": raw.get("completion_tokens"),
        "total_tokens": raw.get("total_tokens"),
        "raw": raw,
    }


def _dump(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    return {
        key: getattr(obj, key)
        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
        if getattr(obj, key, None) is not None
    }


def _tool_call_dict(tool_call: Any) -> dict[str, Any]:
    return {
        "id": tool_call.id,
        "type": tool_call.type,
        "function": {
            "name": tool_call.function.name,
            "arguments": tool_call.function.arguments,
        },
    }


def _to_openai_messages(messages: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    converted: list[dict[str, Any]] = []
    for message in messages:
        payload = {key: value for key, value in message.items() if key != "images"}
        images = message.get("images") or []
        if images:
            content = message.get("content", "")
            parts = (
                content
                if isinstance(content, list)
                else [{"type": "text", "text": content}]
            )
            payload["content"] = [*parts, *(_image_part(image) for image in images)]
        converted.append(payload)
    return converted


def _image_part(image: str | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(image, Mapping):
        return {"type": "image_url", "image_url": dict(image)}
    url = (
        image
        if image.startswith(("http://", "https://", "data:"))
        else f"data:image/jpeg;base64,{image}"
    )
    return {"type": "image_url", "image_url": {"url": url}}
