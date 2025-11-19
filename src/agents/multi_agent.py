import yaml
import json
import os
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

# Define terminal tools that stop the agent loop
TERMINAL_TOOLS = {"ask_question", "make_choice", "submit_evaluation"}

# Logging directory
LOG_DIR = Path(__file__).parent.parent.parent / "logs"


class Agent:
    """Simple agent that runs until a terminal tool is called."""

    def __init__(self, name):
        agent_cfg = CONFIG["agents"].get(name)
        if not agent_cfg:
            raise ValueError(f"Agent '{name}' not found in config")

        self.name = name
        self.model = agent_cfg["model"]
        self.system_prompt = agent_cfg["system_prompt"]
        self.temperature = agent_cfg.get("temperature", 0.3)

        # Resolve tool names to tool schemas
        self.tool_schemas = [CONFIG["tools"][t] for t in agent_cfg.get("tools", [])]

        # self.client = OpenAI(
        #     base_url="https://openrouter.ai/api/v1",
        #     api_key=os.getenv("OPENROUTER_API_KEY")
        # )
        self.client = OpenAI(api_key=os.environ.get('DEEPSEEK_API_KEY'), base_url="https://api.deepseek.com")
    def run(self, user_input, episode_id=None, max_turns=10):
        """Run agent and log trajectory."""
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
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.tool_schemas if self.tool_schemas else None,
                temperature=self.temperature
            )

            # Track token usage from OpenRouter response
            if hasattr(response, 'usage') and response.usage:
                trajectory["total_tokens"]["input"] += response.usage.prompt_tokens
                trajectory["total_tokens"]["output"] += response.usage.completion_tokens

            msg = response.choices[0].message

            if not msg.tool_calls:
                result = {
                    "type": "text",
                    "content": msg.content,
                    "total_tokens": trajectory["total_tokens"]
                }
                trajectory["result"] = result
                self._log(episode_id, trajectory)
                return result

            messages.append(msg)
            turn_data = []

            for tool_call in msg.tool_calls:
                fn_name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)
                print(f"🤖 [{self.name}] {fn_name}({json.dumps(args, indent=2)})")

                result = execute_tool(fn_name, args)
                turn_data.append({"tool": fn_name, "args": args, "result": result})

                if fn_name in TERMINAL_TOOLS:
                    trajectory["turns"].append(turn_data)
                    result = {
                        "type": "terminal",
                        "tool": fn_name,
                        "args": args,
                        "result": result,
                        "total_tokens": trajectory["total_tokens"]
                    }
                    trajectory["result"] = result
                    self._log(episode_id, trajectory)
                    return result

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": str(result)
                })

            trajectory["turns"].append(turn_data)

        result = {
            "type": "error",
            "content": f"Max turns reached",
            "total_tokens": trajectory["total_tokens"]
        }
        trajectory["result"] = result
        self._log(episode_id, trajectory)
        return result

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


def run_clinical_reasoning(question_context, max_qa_turns=5):
    """Run multi-agent clinical reasoning with logging."""
    episode_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    uncertainty = Agent("uncertainty_evaluator")
    discriminator = Agent("discriminator")
    decision = Agent("decision_maker")

    conversation = [question_context]

    print(f"\n{'='*60}")
    print(f"Episode: {episode_id}")
    print(f"{'='*60}\n")

    for qa_round in range(max_qa_turns):
        print(f"\n--- Round {qa_round + 1} ---")

        # Step 1: Uncertainty
        conv_text = "\n".join(conversation)
        unc_result = uncertainty.run(conv_text, episode_id)

        if unc_result["type"] != "terminal":
            break

        eval_data = unc_result["args"]
        print(f"\n📊 Known: {eval_data['known_info']}")
        print(f"📊 Missing: {eval_data['missing_info']}")
        print(f"📊 Enough info: {eval_data['has_enough_info']}")

        if eval_data['has_enough_info']:
            break

        # Step 2: Discriminator (with conversation history to prevent redundant questions)
        disc_input = f"""Known Information: {json.dumps(eval_data['known_info'])}
Missing Information: {json.dumps(eval_data['missing_info'])}

Conversation History:
{chr(10).join(conversation[1:])}

Formulate your question based on this context."""
        disc_result = discriminator.run(disc_input, episode_id)

        if disc_result["type"] != "terminal":
            break

        question = disc_result["args"]["question"]
        print(f"\n❓ {question}")

        answer = input("Answer: ").strip()
        if not answer:
            break

        conversation.append(f"Q: {question}")
        conversation.append(f"A: {answer}")

    # Step 3: Decision
    print(f"\n{'='*60}")
    print("Final Decision")
    print(f"{'='*60}\n")

    conv_text = "\n".join(conversation)
    dec_result = decision.run(conv_text, episode_id)

    if dec_result["type"] == "terminal":
        final = dec_result["args"]
        print(f"\n🏁 Choice: {final['letter_choice']}")
        print(f"🏁 Confidence: {final['confidence']}")
        print(f"🏁 Reasoning: {final['reasoning']}")

    return {"episode_id": episode_id, "final_decision": dec_result}


if __name__ == "__main__":
    context = """Patient: 4-year-old boy with rash for 2 days.

Options:
A. Viral exanthem
B. Scarlet fever
C. Kawasaki disease
D. Allergic reaction"""

    result = run_clinical_reasoning(context, max_qa_turns=3)
    print(f"\n\nEpisode ID: {result['episode_id']}")
