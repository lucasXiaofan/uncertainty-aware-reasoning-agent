import os
import json
from openai import OpenAI
from dotenv import load_dotenv
import subprocess
import requests
from datetime import datetime
from pathlib import Path
from tools import *
# Load environment variables and configure client
load_dotenv()
model_name = "deepseek/deepseek-chat-v3"
# model_name = "minimax/minimax-m2:free"  # Alternative free model
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

# Define tools using OpenAI function calling format


class ReActAgent:
    """ReAct agent using proper OpenAI tool calling API."""

    def __init__(self, model_name, max_iterations=15, verbose=True, system_message=None, message_log_file=None):
        self.max_iterations = max_iterations
        self.model_name = model_name
        self.verbose = verbose
        self.tools = [bash_tool, think_tool, brave_search_tool]

        # Set default log file if none provided
        if message_log_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_dir = Path("logs")
            log_dir.mkdir(parents=True, exist_ok=True)
            self.message_log_file = str(log_dir / f"react_agent_messages_{timestamp}.jsonl")
        else:
            self.message_log_file = message_log_file

        self.system_message = system_message or """You are a helpful assistant with access to bash commands on macOS and web search.

Use the bash_command tool to execute shell commands.
Use the brave_search tool to search the web for information.
Use the think tool when you need to reason about your approach.

When the task is complete, provide a final text response (don't call any tools)."""

        # Print log file location
        if self.verbose:
            print(f"📝 Saving agent messages to: {self.message_log_file}")

    def _save_messages(self, messages, iteration=None, status="in_progress"):
        """Save messages to log file."""
        if not self.message_log_file:
            return

        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "iteration": iteration,
            "status": status,
            "model": self.model_name,
            "messages": messages
        }

        # Append to file
        with open(self.message_log_file, 'a') as f:
            f.write(json.dumps(log_entry, default=str) + '\n')

    def run(self, task: str) -> str:
        """
        Run the ReAct agent on a task using tool calling.
        
        Args:
            task: The task description
            
        Returns:
            The final answer or result
        """
        messages = [
            {"role": "system", "content": self.system_message},
            {"role": "user", "content": task}
        ]
        
        for iteration in range(self.max_iterations):
            if self.verbose:
                print(f"\n{'='*60}")
                print(f"ITERATION {iteration + 1}")
                print(f"{'='*60}")
            
            # Get LLM response with tools
            response = client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                tools=self.tools,
                temperature=0
            )
            
            msg = response.choices[0].message
            messages.append(msg)
            
            # Check if assistant made tool calls
            if msg.tool_calls:
                if self.verbose:
                    print(f"Type: TOOL_CALL")
                    print(f"Assistant wants to use {len(msg.tool_calls)} tool(s):")
                
                # Execute each tool
                for tool_call in msg.tool_calls:
                    name = tool_call.function.name
                    args = json.loads(tool_call.function.arguments)
                    
                    if self.verbose:
                        print(f"\n  Tool: {name}")
                        print(f"  Args: {json.dumps(args, indent=8)}")
                    
                    result = execute_tool(name, args)
                    
                    if self.verbose:
                        print(f"  Result: {result}")
                    
                    # Add tool result to messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": str(result)
                    })
            else:
                # Final text response - agent is done
                if self.verbose:
                    print(f"Type: TEXT_RESPONSE")
                    print(f"Content: {msg.content}")
                self._save_messages(messages, iteration=iteration+1, status="completed")
                return msg.content

            # Save messages after each iteration
            self._save_messages(messages, iteration=iteration+1, status="in_progress")

        if self.verbose:
            print(f"\n{'='*60}")
            print("MAX ITERATIONS REACHED")
            print(f"{'='*60}")

        self._save_messages(messages, iteration=self.max_iterations, status="max_iterations_reached")
        return f"[ERROR]: Max iterations ({self.max_iterations}) reached without completing task"


class UncertaintyAgent:
    """Agent that evaluates uncertainty and decides if there's enough information to make a diagnosis."""

    def __init__(self, model_name,
                 client,
                 verbose=True,
                 tool = [think_tool,make_choice_tool,ask_question_tool,brave_search_tool],
                 max_iterations=10,
                 message_log_file=None):
        self.model_name = model_name
        self.client = client
        self.verbose = verbose
        self.max_iterations = max_iterations
        self.tools = tool

        # Set default log file if none provided
        if message_log_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_dir = Path("logs")
            log_dir.mkdir(parents=True, exist_ok=True)
            self.message_log_file = str(log_dir / f"uncertainty_agent_messages_{timestamp}.jsonl")
        else:
            self.message_log_file = message_log_file

        self.system_message = """You are a medical uncertainty evaluation expert following differential diagnosis practice.

Your workflow:
1. **Evaluate Uncertainty**: Use 'thinking' and 'search_online' tools to:
   - Analyze evidence supporting each possible diagnosis
   - Determine what critical information is missing
   - Calculate your confidence level in making a diagnosis

2. **High Uncertainty (confidence < 80%)**:
   - Use 'thinking' to determine what key symptom/information would best differentiate between options
   - Use 'search_online' if needed to understand diagnostic criteria
   - Formulate a specific, targeted question that follows differential diagnosis principles
   - Call 'ask_question' tool with your question to terminate and ask the patient
   - The question should help rule out options or clarify the diagnosis

3. **Low Uncertainty (confidence ≥ 80%)**:
   - Call 'make_choice' tool with your diagnosis letter (A/B/C/D) and confidence score
   - This will terminate the evaluation with your diagnosis

Available Tools:
- thinking: Organize thoughts and analyze evidence
- search_online: Search medical knowledge and guidelines  
- ask_question: Ask patient a targeted question (terminates loop)
- make_choice: Make final diagnosis choice (terminates loop)

Be systematic and evidence-based. Use tools iteratively before making final decision."""

        # Print log file location
        if self.verbose:
            print(f"📝 Saving agent messages to: {self.message_log_file}")

    def _save_messages(self, messages, iteration=None, status="in_progress"):
        """Save messages to log file."""
        if not self.message_log_file:
            return

        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "iteration": iteration,
            "status": status,
            "model": self.model_name,
            "messages": messages
        }

        # Append to file
        with open(self.message_log_file, 'a') as f:
            f.write(json.dumps(log_entry, default=str) + '\n')

    def run(self, task: str) -> dict:
        """
        Run the uncertainty evaluation agent with iterative tool use.

        Args:
            task: Complete task description including patient info, QA history, options, and inquiry

        Returns:
            Either:
            {
                "type": "choice",
                "letter_choice": str (A/B/C/D),
                "confidence": float (0-100),
                "usage": {"input_tokens": int, "output_tokens": int}
            }
            OR:
            {
                "type": "question",
                "question": str,
                "letter_choice": None,
                "confidence": float (0-100),
                "usage": {"input_tokens": int, "output_tokens": int}
            }
        """
        messages = [
            {"role": "system", "content": self.system_message},
            {"role": "user", "content": task}
        ]

        if self.verbose:
            print(f"\n{'='*60}")
            print("UNCERTAINTY EVALUATION - STARTING")
            print(f"{'='*60}")

        for iteration in range(self.max_iterations):
            if self.verbose:
                print(f"\n{'='*60}")
                print(f"ITERATION {iteration + 1}/{self.max_iterations}")
                print(f"{'='*60}")

            # Get LLM response with tools
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                tools=self.tools,
                temperature=0.3
            )

            msg = response.choices[0].message
            messages.append(msg)

            # Check if assistant made tool calls
            if msg.tool_calls:
                if self.verbose:
                    print(f"Type: TOOL_CALL")
                    print(f"Assistant wants to use {len(msg.tool_calls)} tool(s)")

                # Execute each tool
                for tool_call in msg.tool_calls:
                    name = tool_call.function.name
                    args = json.loads(tool_call.function.arguments)

                    if self.verbose:
                        print(f"\n  🔧 Tool: {name}")

                    tool_result = execute_tool(name, args)
                    if name in ['ask_question','make_choice']:
                        if self.verbose:
                            print(f"\n{'='*60}")
                            print("🎯 EVALUATION COMPLETE")
                            print(f"{'='*60}")
                        self._save_messages(f"tool name: {name}, tool args: {args}, tool results: {tool_result}", iteration=iteration+1, status="completed")
                        return tool_result
                    # Add tool result to messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_result
                    })

            else:
                # Final text response without tool calls - should not happen in this design
                if self.verbose:
                    print(f"Type: TEXT_RESPONSE (unexpected)")
                    print(f"Content: {msg.content[:200]}...")
                    print("⚠️  Agent returned text without using terminal tools")

                # Continue loop to give agent another chance
                continue

            # Save messages after each iteration
            self._save_messages(f"tool name: {name}, tool args: {args}, tool results: {tool_result}", iteration=iteration+1, status="in_progress")

        # Max iterations reached without terminal tool call
        if self.verbose:
            print(f"\n{'='*60}")
            print("❌ MAX ITERATIONS REACHED")
            print(f"{'='*60}")

        self._save_messages("max iteration reached", iteration=self.max_iterations, status="max_iterations_reached")
        return {
                "type": "choice",
                "letter_choice": "G",
                "confidence": "exceed loop limit",
                "usage": 0
            }
