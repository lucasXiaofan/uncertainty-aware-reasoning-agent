import yaml
import json
import os
import re
from datetime import datetime
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
from tools import execute_tool

load_dotenv()

# Load YAML Config
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "agent.yaml")
with open(CONFIG_PATH, "r") as f:
    CONFIG = yaml.safe_load(f)

# Logging directory
LOG_DIR = Path(__file__).parent.parent.parent / "logs"


class Agent:
    """Agent that runs until a terminal tool is called, supporting both native and MD-based tool calling."""

    def __init__(self, name):
        agent_cfg = CONFIG["agents"].get(name)
        if not agent_cfg:
            raise ValueError(f"Agent '{name}' not found in config")

        self.name = name
        self.model = agent_cfg["model"]
        self.raw_system_prompt = agent_cfg["system_prompt"]
        self.temperature = agent_cfg.get("temperature", 0.3)
        
        # Resolve tool names to tool schemas
        self.tool_names = agent_cfg.get("tools", [])
        self.tool_schemas = [CONFIG["tools"][t] for t in self.tool_names]
        
        print(f'checking tool schemas: {self.tool_schemas}')

        # Load terminal tools from config, default to empty set if not provided
        self.terminal_tools = set(agent_cfg.get("terminal_tools", []))

        # Initialize Client based on Model
        if "deepseek" in self.model.lower() and "chat" in self.model.lower():
             # Assumes "deepseek-chat" or similar maps to DeepSeek API
            self.client = OpenAI(
                api_key=os.environ.get('DEEPSEEK_API_KEY'), 
                base_url="https://api.deepseek.com"
            )
        else:
            # Default to OpenRouter for other models
            self.client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=os.getenv("OPENROUTER_API_KEY")
            )

    def update_model(self, model_name):
        """Update the model and re-initialize the client."""
        self.model = model_name
        if "deepseek" in self.model.lower() and "chat" in self.model.lower():
             # Assumes "deepseek-chat" or similar maps to DeepSeek API
            self.client = OpenAI(
                api_key=os.environ.get('DEEPSEEK_API_KEY'), 
                base_url="https://api.deepseek.com"
            )
        else:
            # Default to OpenRouter for other models
            self.client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=os.getenv("OPENROUTER_API_KEY")
            )

    def _get_system_prompt(self):
        """Inject tool schemas and terminal tools into system prompt if placeholders exist."""
        prompt = self.raw_system_prompt
        
        if "{{TOOL_SCHEMAS}}" in prompt:
            schemas_str = json.dumps(self.tool_schemas, indent=2)
            prompt = prompt.replace("{{TOOL_SCHEMAS}}", schemas_str)
            
        if "{{TERMINAL_TOOLS}}" in prompt:
            terminal_tools_str = json.dumps(list(self.terminal_tools), indent=2)
            prompt = prompt.replace("{{TERMINAL_TOOLS}}", terminal_tools_str)
            
        return prompt

    def _parse_json_from_md(self, content):
        """Extract JSON block from Markdown or raw text."""
        # 1. Try finding ```json ... ``` block
        pattern = r"```json\s*(\{.*?\})\s*```"
        match = re.search(pattern, content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        
        # 2. Try finding raw JSON object { ... }
        # Find the first '{' and the last '}'
        start = content.find('{')
        end = content.rfind('}')
        
        if start != -1 and end != -1 and end > start:
            json_str = content[start:end+1]
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass
                
        return None

    def run(self, user_input, episode_id=None, max_turns=10):
        """Run agent and log trajectory."""
        system_prompt = self._get_system_prompt()
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ]

        trajectory = {
            "agent": self.name,
            "episode_id": episode_id,
            "input": user_input,
            "turns": [],
            "total_tokens": {"input": 0, "output": 0}
        }

        def process_response(response):
            if hasattr(response, 'usage') and response.usage:
                trajectory["total_tokens"]["input"] += response.usage.prompt_tokens
                trajectory["total_tokens"]["output"] += response.usage.completion_tokens
            
            msg = response.choices[0].message
            content = msg.content or ""
            messages.append(msg)
            
            parsed = self._parse_json_from_md(content)
            return parsed

        # Main Loop
        for turn in range(max_turns):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature
                )
            except Exception as e:
                print(f"❌ [{self.name}] API Error: {e}")
                messages.append({"role": "user", "content": f"API Error: {str(e)}. Please try again."})
                continue

            try:
                parsed = process_response(response)
            except Exception as e:
                print(f"❌ [{self.name}] Processing Error: {e}")
                try:
                    raw_content = response.choices[0].message.content
                    print(f"Raw Content: {raw_content}")
                except:
                    pass
                messages.append({"role": "user", "content": f"Error processing response: {str(e)}. Please ensure valid JSON output."})
                continue
            
            if parsed and "tool" in parsed:
                fn_name = parsed["tool"]
                args = parsed.get("arguments", {})
                print(f"🤖 [{self.name}] Tool: {fn_name}")
                
                try:
                    result = execute_tool(fn_name, args)
                except Exception as e:
                    print(f"❌ [{self.name}] Tool Execution Error: {e}")
                    messages.append({"role": "user", "content": f"Tool execution error: {str(e)}. Please try again."})
                    continue

                turn_info = {"tool": fn_name, "args": args, "result": result}
                trajectory["turns"].append(turn_info)
                
                if fn_name in self.terminal_tools:
                    # Check if result indicates an error (and we want to retry)
                    if isinstance(result, dict) and "error" in result:
                        print(f"⚠️ [{self.name}] Terminal tool error: {result['error']}. Retrying.")
                        messages.append({"role": "user", "content": f"Error in tool '{fn_name}': {result['error']}. Please correct your arguments and try again."})
                        print(f"problematic raw_content: {response.choices[0].message.content}")
                        trajectory["error_response"] = f"Tool execution error, Raw content: {response.choices[0].message.content}"
                        continue
                    return self._finalize_trajectory(trajectory, result, episode_id, args)
                
                messages.append({"role": "user", "content": f"Tool '{fn_name}' Output: {result}"})
            
            # If no tool, it's just reasoning, continue to next turn.

        # Force Decision
        print(f"⚠️ [{self.name}] Max turns reached. Forcing decision.")
        terminal_tools_list = list(self.terminal_tools)
        messages.append({"role": "user", "content": f"You have exceeded the maximum turns. You MUST make a final decision now using one of these terminal tools: {terminal_tools_list}."})
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature
        )
        
        parsed = process_response(response)
        
        if parsed and "tool" in parsed and parsed["tool"] in self.terminal_tools:
             fn_name = parsed["tool"]
             args = parsed.get("arguments", {})
             result = execute_tool(fn_name, args)
             turn_info = {"tool": fn_name, "args": args, "result": result}
             trajectory["turns"].append(turn_info)
             return self._finalize_trajectory(trajectory, result, episode_id, args)

        # Fallback Failure
        return self._finalize_trajectory(trajectory, {"error": "Failed to terminate after forced decision"}, episode_id)

    def _finalize_trajectory(self, trajectory, result, episode_id, args=None):
        is_error = isinstance(result, dict) and "error" in result
        turns_count = len(trajectory["turns"])
        final_result = {
            "type": "error" if is_error else "terminal",
            "tool": trajectory["turns"][-1]["tool"] if trajectory["turns"] else None,
            "turns": turns_count,
            "args": args,
            "result": result,
            "total_tokens": trajectory["total_tokens"]
        }
        trajectory["result"] = final_result
        
        # Create concise log entry
        log_entry = trajectory.copy()
        log_entry["turns"] = turns_count
        
        self._log(episode_id, log_entry)
        return final_result

    def _log(self, episode_id, trajectory):
        """Save trajectory to date-based log file (all episodes from same day in one file)."""
        if not episode_id:
            return

        agent_dir = LOG_DIR / self.name
        agent_dir.mkdir(parents=True, exist_ok=True)

        # Use date from episode_id (YYYYMMDD_HHMMSS -> YYYY-MM-DD)
        if len(episode_id) >= 8:
            date_str = f"{episode_id[:4]}-{episode_id[4:6]}-{episode_id[6:8]}"
        else:
            # Fallback to current date
            date_str = datetime.now().strftime("%Y-%m-%d")

        log_file = agent_dir / f"{date_str}.jsonl"
        with open(log_file, 'a') as f:
            f.write(json.dumps(trajectory) + '\n')



