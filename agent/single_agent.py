"""Single Agent with tool calling capabilities."""
import os
import json
import base64
import mimetypes
from pathlib import Path
from datetime import datetime

import yaml
from openai import OpenAI
from dotenv import load_dotenv

from tools import execute_tool, get_tool_schema
from tools.agent_utils import save_conversation, load_recent_conversations

# Load environment variables
load_dotenv()

# Load config
CONFIG_PATH = Path(__file__).parent / "agent_config.yaml"
with open(CONFIG_PATH, "r") as f:
    CONFIG = yaml.safe_load(f)

# Default directories
DEFAULT_MEMORY_DIR = Path(__file__).parent / "memory"
DEFAULT_TRAJECTORIES_DIR = Path(__file__).parent / "trajectories_log"


class SingleAgent:
    """Simple agent supporting text and image input using OpenAI native tool calling."""

    def __init__(self, agent_name: str, model_name: str = None,
                 trajectory_log_dir: str = None, conversation_log_path: str = None):
        """Initialize the agent.

        Args:
            agent_name: Name of the agent from config
            model_name: Optional model override
            trajectory_log_dir: Directory to save trajectory logs (default: trajectories_log/)
            conversation_log_path: Path to conversation log file (default: memory/conversation_log.json)
        """
        agent_cfg = CONFIG["agents"].get(agent_name)
        if not agent_cfg:
            raise ValueError(f"Agent '{agent_name}' not found in config")

        self.name = agent_name
        self.model = model_name or agent_cfg["model"]
        self.system_prompt = agent_cfg["system_prompt"]
        self.temperature = agent_cfg.get("temperature", 0.3)
        self.max_turns = agent_cfg.get("max_turns", 10)

        # Configure logging paths
        self.trajectory_log_dir = Path(trajectory_log_dir) if trajectory_log_dir else DEFAULT_TRAJECTORIES_DIR
        self.conversation_log_path = conversation_log_path or str(DEFAULT_MEMORY_DIR / "conversation_log.json")

        # Ensure directories exist
        self.trajectory_log_dir.mkdir(parents=True, exist_ok=True)
        Path(self.conversation_log_path).parent.mkdir(parents=True, exist_ok=True)

        # Get tool schemas from registry based on config
        tool_names = agent_cfg.get("tools", [])
        self.tool_schemas = []
        for tool_name in tool_names:
            schema = get_tool_schema(tool_name)
            if schema:
                self.tool_schemas.append(schema)
            else:
                print(f"Warning: Tool '{tool_name}' not found in registry")

        self.terminal_tools = set(agent_cfg.get("terminal_tools", []))

        self.client = self._init_client()
        print(f'[{self.name}] Model: {self.model} | Tools: {[t["function"]["name"] for t in self.tool_schemas]}')

    def _init_client(self):
        """Initialize OpenAI client based on model type."""
        if "deepseek" in self.model.lower() and "chat" in self.model.lower():
            return OpenAI(
                api_key=os.environ.get('DEEPSEEK_API_KEY'),
                base_url="https://api.deepseek.com"
            )
        return OpenAI(
            api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1"
        )

    def _encode_image(self, image_path: str) -> str:
        """Encode local image to base64 data URL."""
        mime_type = mimetypes.guess_type(image_path)[0] or "image/jpeg"
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode('utf-8')
        return f"data:{mime_type};base64,{b64}"

    def _build_conversation_context(self) -> str:
        """Build context from recent conversations."""
        # recent = load_recent_conversations(limit=5)
        # if not recent:
        return ""

        context_parts = ["[RECENT CONVERSATION HISTORY]"]
        for conv in recent:
            context_parts.append(f"\nUser: {conv['user_query']}")
            # Truncate long responses for context
            response = conv['final_response']
            if len(response) > 500:
                response = response[:500] + "..."
            context_parts.append(f"Assistant: {response}")

        context_parts.append("\n[END OF HISTORY]\n")
        return "\n".join(context_parts)

    def _build_user_message(self, text: str, image_url: str = None) -> dict:
        """Build user message with optional image and conversation history."""
        # Add recent conversation context
        context = self._build_conversation_context()
        full_text = f"{context}\n{text}" if context else text

        if not image_url:
            return {"role": "user", "content": full_text}

        url = self._encode_image(image_url) if os.path.isfile(image_url) else image_url
        return {
            "role": "user",
            "content": [
                {"type": "text", "text": full_text},
                {"type": "image_url", "image_url": {"url": url}}
            ]
        }

    def _execute_tool_call(self, tool_call) -> tuple:
        """Execute a single tool call and return (name, args, result)."""
        fn_name = tool_call.function.name
        raw_args = tool_call.function.arguments

        # Handle empty or None arguments
        if not raw_args or raw_args.strip() == "":
            args = {}
        else:
            try:
                args = json.loads(raw_args)
            except (json.JSONDecodeError, TypeError) as e:
                print(f"  [{self.name}] JSON parse error for {fn_name}: {e}, raw: {raw_args!r}")
                return fn_name, {}, {"error": f"Invalid JSON arguments: {e}"}

        print(f"  [{self.name}] {fn_name}({args})")
        try:
            result = execute_tool(fn_name, args)
        except Exception as e:
            result = {"error": str(e)}
        return fn_name, args, result

    def _record_turn(self, trajectory: dict, thinking: str, tool: str = None,
                     args: dict = None, result=None):
        """Record a turn in the trajectory."""
        trajectory["turns"].append({
            "agent_type": self.name,
            "thinking_process": thinking,
            "tool": tool,
            "args": args,
            "result": result if tool == "brave_search" else None
        })

    def _finalize(self, trajectory: dict, result, episode_id: str, args: dict = None) -> dict:
        """Finalize, save conversation to memory, and log trajectory."""
        last_tool = next((t["tool"] for t in reversed(trajectory["turns"]) if t["tool"]), None)
        is_error = isinstance(result, dict) and "error" in result

        # Extract final response for saving
        final_response = result if isinstance(result, str) else json.dumps(result, default=str)

        # Save conversation to memory (only if not an error)
        if not is_error:
            save_conversation(
                user_query=trajectory["input"],
                final_response=final_response,
                image_path=trajectory.get("image_url"),
                log_file_path=self.conversation_log_path
            )
            print(f"[{self.name}] Conversation saved to {self.conversation_log_path}")

        final_result = {
            "type": "error" if is_error else "terminal",
            "tool": last_tool,
            "turns": len(trajectory["turns"]),
            "args": args,
            "result": result,
            "total_tokens": trajectory["total_tokens"],
            "trajectory": trajectory["turns"]
        }
        trajectory["result"] = final_result

        # Save trajectory to file
        trajectory_file = self._save_trajectory(trajectory, episode_id)
        final_result["trajectory_file"] = str(trajectory_file) if trajectory_file else None

        return final_result

    def _save_trajectory(self, trajectory: dict, episode_id: str = None) -> Path:
        """Save trajectory to a timestamped file.

        Args:
            trajectory: The trajectory dictionary to save
            episode_id: Optional episode ID to include in filename

        Returns:
            Path to the saved trajectory file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        episode_suffix = f"_{episode_id}" if episode_id else ""
        filename = f"{self.name}_trajectory_{timestamp}{episode_suffix}.json"
        trajectory_file = self.trajectory_log_dir / filename

        with open(trajectory_file, "w", encoding="utf-8") as f:
            json.dump(trajectory, f, indent=2, ensure_ascii=False, default=str)

        print(f"[{self.name}] Trajectory saved to {trajectory_file}")
        return trajectory_file

    def run(self, user_input: str, image_url: str = None, episode_id: str = None,
            max_turns: int = None) -> dict:
        """Run agent loop with optional image support."""
        max_turns = max_turns or self.max_turns
        messages = [
            {"role": "system", "content": self.system_prompt},
            self._build_user_message(user_input, image_url)
        ]
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
                print(f"[{self.name}] API Error: {e}")
                import traceback
                traceback.print_exc()
                return self._finalize(trajectory, {"error": str(e)}, episode_id)

            if not response.choices:
                print(f"[{self.name}] Empty response from API")
                return self._finalize(trajectory, {"error": "Empty API response"}, episode_id)

            if response.usage:
                trajectory["total_tokens"]["input"] += response.usage.prompt_tokens
                trajectory["total_tokens"]["output"] += response.usage.completion_tokens

            msg = response.choices[0].message

            # Convert message to dict for appending to avoid serialization issues
            msg_dict = {"role": "assistant", "content": msg.content}
            if msg.tool_calls:
                msg_dict["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments or "{}"
                        }
                    }
                    for tc in msg.tool_calls
                ]
            messages.append(msg_dict)

            # No tool calls - record thinking and continue
            if not msg.tool_calls:
                self._record_turn(trajectory, msg.content)
                # If there's content but no tool calls, we're done
                if msg.content:
                    print(f"\n[{self.name}] Response:\n{msg.content}")
                    return self._finalize(trajectory, msg.content, episode_id)
                continue

            # Execute tool calls
            for tool_call in msg.tool_calls:
                fn_name, args, result = self._execute_tool_call(tool_call)
                self._record_turn(trajectory, msg.content, fn_name, args, result)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "args": args,
                    "content": json.dumps(result) if isinstance(result, dict) else str(result)
                })

                if fn_name in self.terminal_tools:
                    if isinstance(result, dict) and "error" in result:
                        print(f"[{self.name}] Terminal tool error, retrying...")
                        continue
                    print(f"[{self.name}] Terminal tool '{fn_name}' succeeded")
                    return self._finalize(trajectory, result, episode_id, args)

        return self._force_terminal(messages, trajectory, episode_id)

    def _force_terminal(self, messages: list, trajectory: dict, episode_id: str) -> dict:
        """Force terminal tool usage when max turns reached."""
        print(f"[{self.name}] Max turns reached, forcing decision...")
        if not self.terminal_tools:
            return self._finalize(trajectory, {"error": "Max turns reached"}, episode_id)

        messages.append({
            "role": "user",
            "content": f"REQUIRED: Use one of these tools now: {list(self.terminal_tools)}"
        })
        terminal_schemas = [
            t for t in self.tool_schemas
            if t["function"]["name"] in self.terminal_tools
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=terminal_schemas,
                tool_choice="required",
                temperature=self.temperature
            )
            if response.choices[0].message.tool_calls:
                tool_call = response.choices[0].message.tool_calls[0]
                fn_name, args, result = self._execute_tool_call(tool_call)
                self._record_turn(
                    trajectory,
                    response.choices[0].message.content,
                    fn_name, args, result
                )
                print(f"[{self.name}] Forced: {fn_name}")
                return self._finalize(trajectory, result, episode_id, args)
        except Exception as e:
            print(f"[{self.name}] Force failed: {e}")

        return self._finalize(trajectory, {"error": "Force terminal tool failed"}, episode_id)


def main():
    """Example usage of the SingleAgent."""
    import argparse

    parser = argparse.ArgumentParser(description="Run a single agent")
    parser.add_argument("query", help="The query or task for the agent")
    parser.add_argument(
        "--agent", "-a",
        default="simple_agent",
        help="Agent name from config (default: simple_agent)"
    )
    parser.add_argument(
        "--model", "-m",
        default=None,
        help="Override model from config"
    )
    parser.add_argument(
        "--image", "-i",
        default=None,
        help="Path to an image file or URL to include in the conversation"
    )
    parser.add_argument(
        "--trajectory-dir", "-t",
        default=None,
        help="Directory to save trajectory logs (default: trajectories_log/)"
    )
    parser.add_argument(
        "--conversation-log", "-c",
        default=None,
        help="Path to conversation log file (default: memory/conversation_log.json)"
    )
    args = parser.parse_args()

    # Validate image path if provided
    if args.image and os.path.isfile(args.image):
        print(f"[main] Including image: {args.image}")
    elif args.image:
        print(f"[main] Including image URL: {args.image}")

    agent = SingleAgent(
        args.agent,
        model_name=args.model,
        trajectory_log_dir=args.trajectory_dir,
        conversation_log_path=args.conversation_log
    )
    result = agent.run(args.query, image_url=args.image)

    print("\n" + "=" * 60)
    print("Final Result:\n")
    print(result["result"] if isinstance(result["result"], str) else json.dumps(result["result"], indent=2, default=str))
    if result.get("trajectory_file"):
        print(f"\nTrajectory saved to: {result['trajectory_file']}")


if __name__ == "__main__":
    main()
