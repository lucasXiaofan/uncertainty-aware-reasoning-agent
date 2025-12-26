import json
import os
import hashlib
from pathlib import Path
from datetime import datetime
from multi_agent_native import NativeToolAgent

class MemoryAgent:
    """
    Memory Agent to manage episodic memory for the Two-Agent system.
    Stores differential diagnosis states and conversation history to improve efficiency.
    Uses LLM to assess if new information was gained.
    """
    def __init__(self, log_dir, model_name=None):
        self.log_dir = Path(log_dir)
        self.memory_file = self.log_dir / "memory_agent_storage.json"
        self.memory = self._load_memory()
        
        # Initialize the LLM agent for analysis
        self.agent = NativeToolAgent("memory_agent", model_name=model_name)



    def _load_memory(self):
        if self.memory_file.exists():
            try:
                with open(self.memory_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}

    def _save_memory(self):
        with open(self.memory_file, 'w') as f:
            json.dump(self.memory, f, indent=2)

    def _generate_key(self, question, options):
        """Generate a stable key for the patient based on inquiry and options."""
        # Sort options to ensure stability
        options_str = json.dumps(options, sort_keys=True)
        content = f"{question}_{options_str}"
        return hashlib.md5(content.encode()).hexdigest()

    def get_patient_memory(self, question, options):
        """Retrieve or initialize memory for a specific patient."""
        key = self._generate_key(question, options)
        if key not in self.memory:
            self.memory[key] = {
                "patient_id_hash": key,
                "question": question,
                "initial_options": options,
                "created_at": datetime.now().isoformat(),
                "turns": []
            }
            self._save_memory()
        return self.memory[key]

    def update_turn(self, question, options, turn_data):
        """Record a turn's data."""
        key = self._generate_key(question, options)
        if key not in self.memory:
            self.get_patient_memory(question, options)
        
        self.memory[key]["turns"].append(turn_data)
        self._save_memory()

    def get_latest_differential(self, question, options):
        """Get the most recent differential analysis (updated options) for this patient."""
        key = self._generate_key(question, options)
        if key in self.memory and self.memory[key]["turns"]:
            # Iterate backwards to find the last differential update
            for turn in reversed(self.memory[key]["turns"]):
                if "differential_analysis" in turn and turn["differential_analysis"]:
                    return turn["differential_analysis"]
        return None

    def analyze_turn(self, history):
        """
        Analyze the latest turn to see if new info was gained.
        Returns: (has_new_info, strategy_suggestion, trajectory)
        """
        if not history:
            return True, None, []

        # Get the last Q&A pair
        last_qa = history[-1]
        
        task = f"""Analyze the last interaction:
Question: {last_qa['question']}
Answer: {last_qa['answer']}

Did the patient provide NEW diagnostic information?
"""
        result = self.agent.run(task)
        
        has_new_info = True
        strategy_suggestion = None
        
        if result["type"] == "terminal" and result["tool"] == "assess_progress":
            args = result["args"]
            has_new_info = args.get("has_new_info", True)
            strategy_suggestion = args.get("strategy_suggestion")
            
        return has_new_info, strategy_suggestion, result.get("trajectory", [])
