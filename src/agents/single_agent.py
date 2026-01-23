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


import base64
import mimetypes

class SingleAgent:
    """Simple agent supporting text and image input using OpenAI native tool calling."""

    def __init__(self, agent_name, model_name=None):
        agent_cfg = CONFIG["agents"].get(agent_name)
        if not agent_cfg:
            raise ValueError(f"Agent '{agent_name}' not found in config")

        self.name = agent_name
        self.model = model_name or agent_cfg["model"]
        self.system_prompt = agent_cfg["system_prompt"]
        self.temperature = agent_cfg.get("temperature", 0.3)
        self.tool_schemas = [CONFIG["tools"][t] for t in agent_cfg.get("tools", [])]
        self.terminal_tools = set(agent_cfg.get("terminal_tools", []))

        print(f'[{self.name}] Model: {self.model}')
        print(f'[{self.name}] Tools: {[t["function"]["name"] for t in self.tool_schemas]}')
        
        self._init_client()

    def _init_client(self):
        """Initialize OpenAI client."""
        if "deepseek" in self.model.lower() and "chat" in self.model.lower():
            api_key = os.environ.get('DEEPSEEK_API_KEY')
            base_url = "https://api.deepseek.com"
        else:
            api_key = os.getenv("OPENROUTER_API_KEY")
            base_url = "https://openrouter.ai/api/v1"
            
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    # not sure the image url support local image or just online image 
    # max turn should also in the agent config
    # need be clear on the trigger or manager than run the agent
    def run(self, user_input, image_url=None, episode_id=None, max_turns=10):
        """Run agent using native OpenAI tool calling with optional image support."""
        messages = [
            {"role": "system", "content": self.system_prompt}
        ]

        if image_url:
            if os.path.exists(image_url) and os.path.isfile(image_url):
                # Handle local image file
                mime_type, _ = mimetypes.guess_type(image_url)
                if not mime_type:
                    mime_type = "image/jpeg"
                with open(image_url, "rb") as image_file:
                    base64_image = base64.b64encode(image_file.read()).decode('utf-8')
                image_ref = {"url": f"data:{mime_type};base64,{base64_image}"}
            else:
                # Handle public URL
                image_ref = {"url": image_url}

            content = [
                {"type": "text", "text": user_input},
                {"type": "image_url", "image_url": image_ref}
            ]
            messages.append({"role": "user", "content": content})
        else:
            messages.append({"role": "user", "content": user_input})

        trajectory = {
            "agent": self.name,
            "episode_id": episode_id,
            "input": user_input,
            "image_url": image_url,
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
                return self._finalize(trajectory, {"error": str(e)}, episode_id)

            if hasattr(response, 'usage') and response.usage:
                trajectory["total_tokens"]["input"] += response.usage.prompt_tokens
                trajectory["total_tokens"]["output"] += response.usage.completion_tokens

            msg = response.choices[0].message
            messages.append(msg)
            
            thinking_process = msg.content

            if not msg.tool_calls:
                trajectory["turns"].append({
                    "agent_type": self.name,
                    "thinking_process": thinking_process,
                    "tool": None,
                    "args": None,
                    "result": None
                })

                if self.terminal_tools and turn == max_turns - 1:
                     # Force terminal tool if max turns reached
                     return self._force_terminal_tool(messages, trajectory, episode_id)
                continue

            for tool_call in msg.tool_calls:
                fn_name = tool_call.function.name
                try:
                    args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    result = {"error": "Invalid JSON arguments"}
                    messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": json.dumps(result)})
                    continue

                print(f"🤖 [{self.name}] {fn_name}({args})")
                
                try:
                    result = execute_tool(fn_name, args)
                except Exception as e:
                    result = {"error": str(e)}

                # Always save args, only save result for brave_search or similar if needed. 
                # For simplicity saving everything unless it's huge, but let's stick to the pattern.
                saved_result = result if fn_name == "brave_search" else None

                trajectory["turns"].append({
                    "agent_type": self.name,
                    "thinking_process": thinking_process,
                    "tool": fn_name, 
                    "args": args, 
                    "result": saved_result
                })
                
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

        return self._force_terminal_tool(messages, trajectory, episode_id)

    def _force_terminal_tool(self, messages, trajectory, episode_id):
        """Force the agent to use a terminal tool."""
        print(f"⚠️ [{self.name}] Max turns reached, forcing decision...")
        if not self.terminal_tools:
             return self._finalize(trajectory, {"error": "Max turns reached"}, episode_id)

        terminal_schemas = [t for t in self.tool_schemas if t["function"]["name"] in self.terminal_tools]
        messages.append({
            "role": "user", 
            "content": f"REQUIRED: You must now use one of these tools to end the session: {list(self.terminal_tools)}"
        })

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=terminal_schemas,
                tool_choice="required",
                temperature=self.temperature
            )
            
            msg = response.choices[0].message
            if msg.tool_calls:
                tool_call = msg.tool_calls[0]
                fn_name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)
                print(f"🤖 [{self.name}] Forced: {fn_name}")
                result = execute_tool(fn_name, args)
                
                saved_result = result if fn_name == "brave_search" else None
                
                trajectory["turns"].append({
                    "agent_type": self.name,
                    "thinking_process": msg.content,
                    "tool": fn_name, 
                    "args": args, 
                    "result": saved_result
                })
                return self._finalize(trajectory, result, episode_id, args)
        except Exception as e:
            print(f"❌ [{self.name}] Force failed: {e}")

        return self._finalize(trajectory, {"error": "Force terminal tool failed"}, episode_id)

    def _finalize(self, trajectory, result, episode_id, args=None):
        """Finalize trajectory and return result."""
        # Find the last tool used in trajectory
        last_tool = None
        for turn in reversed(trajectory["turns"]):
            if turn["tool"]:
                last_tool = turn["tool"]
                break

        final_result = {
            "type": "error" if isinstance(result, dict) and "error" in result else "terminal",
            "tool": last_tool,
            "turns": len(trajectory["turns"]),
            "args": args,
            "result": result,
            "total_tokens": trajectory["total_tokens"],
            "trajectory": trajectory["turns"] # Saving full trajectory in result for easier debug? Original did this.
        }
        trajectory["result"] = final_result
        self._log(episode_id, trajectory)
        return final_result

    def _log(self, episode_id, trajectory):
        """Save trajectory to log file."""
        if not episode_id: return
        agent_dir = LOG_DIR / self.name
        agent_dir.mkdir(parents=True, exist_ok=True)
        date_str = f"{episode_id[:4]}-{episode_id[4:6]}-{episode_id[6:8]}" if len(episode_id) >= 8 else datetime.now().strftime("%Y-%m-%d")
        with open(agent_dir / f"{date_str}.jsonl", 'a') as f:
            f.write(json.dumps(trajectory) + '\n')
