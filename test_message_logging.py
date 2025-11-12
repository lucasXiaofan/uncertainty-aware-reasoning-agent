#!/usr/bin/env python3
"""
Test script to verify message logging in agents.
"""
import sys
from pathlib import Path

# Add src/agents to path
sys.path.insert(0, str(Path(__file__).parent / "src" / "agents"))

from general_agent import ReActAgent

def main():
    # Create a simple agent with default message logging
    agent = ReActAgent(
        model_name="deepseek/deepseek-chat-v3",
        max_iterations=3,
        verbose=True
    )

    # Run a simple task
    task = "What is 2 + 2? Just calculate and return the answer."
    result = agent.run(task)

    print("\n" + "="*60)
    print("Test completed!")
    print(f"Result: {result}")
    print(f"Messages saved to: {agent.message_log_file}")
    print("="*60)

if __name__ == "__main__":
    main()
