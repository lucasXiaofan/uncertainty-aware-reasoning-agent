import yaml
import json
import os
from datetime import datetime
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
from tools import execute_tool

load_dotenv()

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "agent.yaml")
with open(CONFIG_PATH, "r") as f:
    CONFIG = yaml.safe_load(f)

LOG_DIR = Path(__file__).parent.parent.parent / "logs"


class NativeToolAgent:
    """Agent using OpenAI native tool calling, runs until terminal tool is called."""

    def __init__(self, name):
        agent_cfg = CONFIG["agents"].get(name)
        if not agent_cfg:
            raise ValueError(f"Agent '{name}' not found in config")

        self.name = name
        self.model = agent_cfg["model"]
        self.system_prompt = agent_cfg["system_prompt"]
        self.temperature = agent_cfg.get("temperature", 0.3)
        self.tool_schemas = [CONFIG["tools"][t] for t in agent_cfg.get("tools", [])]
        self.terminal_tools = set(agent_cfg.get("terminal_tools", []))

        print(f'[{self.name}] Tools: {[t["function"]["name"] for t in self.tool_schemas]}')
        self._init_client()

    def _init_client(self):
        """Initialize OpenAI client based on model."""
        if "deepseek" in self.model.lower() and "chat" in self.model.lower():
            self.client = OpenAI(
                api_key=os.environ.get('DEEPSEEK_API_KEY'),
                base_url="https://api.deepseek.com"
            )
        else:
            self.client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=os.getenv("OPENROUTER_API_KEY")
            )

    def update_model(self, model_name):
        """Update model and reinitialize client."""
        self.model = model_name
        self._init_client()

    def run(self, user_input, episode_id=None, max_turns=10):
        """Run agent using native OpenAI tool calling."""
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_input}
        ]

        trajectory = {
            "agent": self.name,
            "episode_id": episode_id,
            "input": user_input,
            "turns": [],
            "total_tokens": {"input": 0, "output": 0}
        }

        for turn in range(max_turns):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=self.tool_schemas or None,
                    temperature=self.temperature
                )
            except Exception as e:
                print(f"❌ [{self.name}] API Error: {e}")
                messages.append({"role": "user", "content": f"API Error: {str(e)}. Please try again."})
                continue

            if hasattr(response, 'usage') and response.usage:
                trajectory["total_tokens"]["input"] += response.usage.prompt_tokens
                trajectory["total_tokens"]["output"] += response.usage.completion_tokens

            msg = response.choices[0].message
            messages.append(msg)

            if msg.tool_calls:
                for tool_call in msg.tool_calls:
                    fn_name = tool_call.function.name

                    try:
                        args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError as e:
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": f"Error: Invalid JSON - {str(e)}"
                        })
                        continue

                    print(f"🤖 [{self.name}] {fn_name}({args})")

                    try:
                        result = execute_tool(fn_name, args)
                    except Exception as e:
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": f"Tool execution error: {str(e)}"
                        })
                        continue

                    trajectory["turns"].append({"tool": fn_name, "args": args, "result": result})

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result)
                    })

                    if fn_name in self.terminal_tools:
                        if isinstance(result, dict) and "error" in result:
                            print(f"⚠️ [{self.name}] Terminal tool error, retrying...")
                            continue

                        print(f"✅ [{self.name}] Terminal tool '{fn_name}' succeeded")
                        return self._finalize(trajectory, result, episode_id, args)

            elif response.choices[0].finish_reason == 'stop' and self.terminal_tools:
                messages.append({
                    "role": "user",
                    "content": f"You must use a tool: {list(self.terminal_tools)}"
                })

        # Max turns reached - force terminal tool
        print(f"⚠️ [{self.name}] Max turns reached, forcing decision...")

        if self.terminal_tools:
            terminal_schemas = [t for t in self.tool_schemas if t["function"]["name"] in self.terminal_tools]
            messages.append({
                "role": "user",
                "content": f"REQUIRED: Use one of {list(self.terminal_tools)} now."
            })

            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=terminal_schemas,
                    tool_choice="required",
                    temperature=self.temperature
                )

                if hasattr(response, 'usage') and response.usage:
                    trajectory["total_tokens"]["input"] += response.usage.prompt_tokens
                    trajectory["total_tokens"]["output"] += response.usage.completion_tokens

                msg = response.choices[0].message
                if msg.tool_calls:
                    tool_call = msg.tool_calls[0]
                    fn_name = tool_call.function.name
                    args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}

                    print(f"🤖 [{self.name}] Forced: {fn_name}")
                    result = execute_tool(fn_name, args)
                    trajectory["turns"].append({"tool": fn_name, "args": args, "result": result})
                    return self._finalize(trajectory, result, episode_id, args)
            except Exception as e:
                print(f"❌ [{self.name}] Force failed: {e}")

        # Fallback
        default_result = {
            "error": "Agent failed to terminate",
            "reason": "Max turns exceeded, could not force terminal tool"
        }
        return self._finalize(trajectory, default_result, episode_id)

    def _finalize(self, trajectory, result, episode_id, args=None):
        """Finalize trajectory and return result."""
        final_result = {
            "type": "error" if isinstance(result, dict) and "error" in result else "terminal",
            "tool": trajectory["turns"][-1]["tool"] if trajectory["turns"] else None,
            "turns": len(trajectory["turns"]),
            "args": args,
            "result": result,
            "total_tokens": trajectory["total_tokens"]
        }
        trajectory["result"] = final_result

        log_entry = trajectory.copy()
        log_entry["turns"] = len(trajectory["turns"])
        self._log(episode_id, log_entry)

        return final_result

    def _log(self, episode_id, trajectory):
        """Save trajectory to date-based log file."""
        if not episode_id:
            return

        agent_dir = LOG_DIR / self.name
        agent_dir.mkdir(parents=True, exist_ok=True)

        date_str = f"{episode_id[:4]}-{episode_id[4:6]}-{episode_id[6:8]}" if len(episode_id) >= 8 else datetime.now().strftime("%Y-%m-%d")

        log_file = agent_dir / f"{date_str}.jsonl"
        with open(log_file, 'a') as f:
            f.write(json.dumps(trajectory) + '\n')
