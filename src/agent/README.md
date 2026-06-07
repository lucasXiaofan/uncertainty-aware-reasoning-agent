# Agent

Minimal OpenAI agent loop with:

- OpenAI chat calls from `openai_llm_calling_core.py`
- Bash tool calling from the project root
- working memory with static memory objects and appended `raw_trajectory`
- memory tool calling through `update_plan`, `update_evidence`, and `update_osce_note`
- JSON logs saved under `src/agent/logs/agent_run_<time>.json`
- simple retries and error handling

## Install

From the project root:

```bash
uv pip install -e .
```

Use `cd project_root` first if you are outside the repository. The code computes the repository root from file location, so it does not depend on a user-specific absolute path.

## Message Format

Messages are OpenAI-style dictionaries:

```python
[
    {"role": "system", "content": "You are a concise coding agent. Only edit files inside this repository."},
    {"role": "user", "content": "List files under src/agent."},
]
```

The OpenAI wrapper also accepts user messages with `images=[...]`, assistant `tool_calls`, and tool-result messages.

`working_memory.update(message)` takes one LLM-readable message and appends it to the dynamic trajectory:

```python
{"role": "assistant", "content": "..."}
{"role": "assistant", "content": "", "tool_calls": [...]}
{"role": "tool", "tool_call_id": "call_...", "content": "{...}"}
```

Memory tool calls are registered in `working_memory.py` and applied by `tool_calling.py`.
Memory tool result messages look like:

```python
{
    "role": "tool",
    "tool_call_id": "call_...",
    "content": "{\"memory_object\":\"plan\",\"items\":[{\"id\":\"p1\",\"content\":\"Inspect files\"}]}"
}
```

Each log file is JSON:

```python
{
    "meta": {"rounds": 1, "token_usage": {...}, "expense_usd": 0.0001},
    "raw_trajectory": [...]
}
```

## Example

```python
from agent.agent import initialize_agent
from agent.working_memory import WorkingMemory

memory = WorkingMemory([
    {"role": "user", "content": "Run pwd and list src/agent."},
], system_prompt="Use tools when needed. Keep edits inside the project root.")

agent = initialize_agent(memory, model="gpt-5.4-nano")
result = agent.run()
print(result["content"])
print(memory.get_messages())
```

`gpt-5.4-nano` is the default. Use `model="gpt-5.4-mini"` when you want stronger reasoning.
