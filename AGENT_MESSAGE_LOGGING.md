# Agent Message Logging

## Overview
Both `ReActAgent` and `UncertaintyAgent` in `src/agents/general_agent.py` now automatically log all their messages to JSON Lines files. This allows you to track the complete trajectory of how the agent answers questions.

## What Was Changed

### 1. Automatic Default Log Files
- **ReActAgent**: Logs to `logs/react_agent_messages_<timestamp>.jsonl`
- **UncertaintyAgent**: Logs to `logs/uncertainty_agent_messages_<timestamp>.jsonl`

The `logs/` directory is automatically created if it doesn't exist.

### 2. Custom Log File Path (Optional)
You can still specify a custom log file path:

```python
agent = UncertaintyAgent(
    model_name="deepseek/deepseek-chat-v3",
    client=client,
    message_log_file="/path/to/custom/log.jsonl"
)
```

### 3. Log File Format
Each line in the log file is a JSON object containing:

```json
{
    "timestamp": "2025-11-11T18:30:45.123456",
    "iteration": 1,
    "status": "in_progress",  // or "completed" or "max_iterations_reached"
    "model": "deepseek/deepseek-chat-v3",
    "messages": [
        {"role": "system", "content": "..."},
        {"role": "user", "content": "..."},
        {"role": "assistant", "content": "...", "tool_calls": [...]},
        {"role": "tool", "tool_call_id": "...", "content": "..."}
    ]
}
```

### 4. Message Logging Points
Messages are logged:
- **After each iteration** (status: "in_progress")
- **When task completes** (status: "completed")
- **When max iterations reached** (status: "max_iterations_reached")

## Usage Example

```python
from general_agent import UncertaintyAgent
from openai import OpenAI

client = OpenAI(...)
agent = UncertaintyAgent(
    model_name="deepseek/deepseek-chat-v3",
    client=client,
    verbose=True  # Will print log file location
)

result = agent.run("Your task here...")

# Messages are automatically saved to logs/uncertainty_agent_messages_<timestamp>.jsonl
# You can access the path via: agent.message_log_file
print(f"Messages logged to: {agent.message_log_file}")
```

## Analyzing Logs

You can analyze the logs using Python:

```python
import json

# Read all log entries
with open('logs/uncertainty_agent_messages_20251111_183045.jsonl', 'r') as f:
    for line in f:
        entry = json.loads(line)
        print(f"Iteration {entry['iteration']}: {entry['status']}")
        print(f"  Messages count: {len(entry['messages'])}")
```

## Benefits

1. **Full Trajectory Tracking**: See every message exchange between the agent and tools
2. **Debugging**: Understand why the agent made certain decisions
3. **Analysis**: Analyze patterns in how the agent solves problems
4. **Reproducibility**: Replay the exact sequence of events
5. **No Manual Setup**: Works out of the box with sensible defaults
