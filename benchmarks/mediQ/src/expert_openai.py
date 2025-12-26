import random
import os
import sys
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
import expert_functions_openai as expert_functions

# Add src/agents to path to import UncertaintyAgent
repo_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(repo_root / "src" / "agents"))

try:
    from general_agent import UncertaintyAgent
    from tools import think_tool, make_choice_tool, ask_question_tool, brave_search_tool
    UNCERTAINTY_AGENT_AVAILABLE = True
except ImportError as e:
    UNCERTAINTY_AGENT_AVAILABLE = False
    print(f"Warning: Could not import UncertaintyAgent: {e}")

try:
    from multi_agent import Agent as MultiAgent
    MULTI_AGENT_AVAILABLE = True
except ImportError as e:
    MULTI_AGENT_AVAILABLE = False
    print(f"Warning: Could not import MultiAgent: {e}")

try:
    from multi_agent_native import NativeToolAgent
    NATIVE_AGENT_AVAILABLE = True
except ImportError as e:
    NATIVE_AGENT_AVAILABLE = False
    print(f"Warning: Could not import NativeToolAgent: {e}")

class Expert:
    """
    Expert system skeleton
    """
    def __init__(self, args, inquiry, options):
        # Initialize the expert with necessary parameters and the initial context or inquiry
        self.args = args
        self.inquiry = inquiry
        self.options = options

    def respond(self, patient_state):
        # Decision-making based on the initial information, history of interactions, current inquiry, and options
        raise NotImplementedError
    
    def ask_question(self, patient_state, prev_messages):
        # Generate a question based on the current patient state
        kwargs = {
            "patient_state": patient_state,
            "inquiry": self.inquiry,
            "options_dict": self.options,
            "messages": prev_messages,
            "independent_modules": self.args.independent_modules,
            "model_name": self.args.expert_model_question_generator,
            "use_vllm": self.args.use_vllm,
            "use_api": self.args.use_api,
            "temperature": self.args.temperature,
            "max_tokens": self.args.max_tokens,
            "top_p": self.args.top_p,
            "top_logprobs": self.args.top_logprobs,
            "api_account": self.args.api_account
        }
        return expert_functions.question_generation(**kwargs)
    
    def get_abstain_kwargs(self, patient_state):
        kwargs = {
            "max_depth": self.args.max_questions,
            "patient_state": patient_state,
            "rationale_generation": self.args.rationale_generation,
            "inquiry": self.inquiry,
            "options_dict": self.options,
            "abstain_threshold": self.args.abstain_threshold,
            "self_consistency": self.args.self_consistency,
            "model_name": self.args.expert_model,
            "use_vllm": self.args.use_vllm,
            "use_api": self.args.use_api,
            "temperature": self.args.temperature,
            "max_tokens": self.args.max_tokens,
            "top_p": self.args.top_p,
            "top_logprobs": self.args.top_logprobs,
            "api_account": self.args.api_account
        }
        return kwargs


class RandomExpert(Expert):
    """
    Below is an example Expert system that randomly asks a question or makes a choice based on the current patient state.
    This should be replaced with a more sophisticated expert system that can make informed decisions based on the patient state.
    """

    def respond(self, patient_state):
        # Decision-making based on the initial information, history of interactions, current inquiry, and options
        initial_info = patient_state['initial_info']  # not use because it's random
        history = patient_state['interaction_history']  # not use because it's random

        # randomly decide to ask a question or make a choice
        abstain = random.random() < 0.5
        toy_question = "Can you describe your symptoms more?"
        toy_decision = self.choice(patient_state)
        conf_score = random.random()/2 if abstain else random.random()

        return {
            "type": "question" if abstain else "choice",
            "question": toy_question,
            "letter_choice": toy_decision,
            "confidence": conf_score,  # Optional confidence score
            "urgent": True,  # Example of another optional flag
            "additional_info": "Check for any recent changes."  # Any other optional data
        }

    def choice(self, patient_state):
        # Generate a choice or intermediate decision based on the current patient state
        # randomly choose an option
        return random.choice(list(self.options.keys()))


class BasicExpert(Expert):
    def respond(self, patient_state):
        kwargs = self.get_abstain_kwargs(patient_state)
        abstain_response_dict = expert_functions.implicit_abstention_decision(**kwargs)
        return {
            "type": "question" if abstain_response_dict["abstain"] else "choice",
            "question": abstain_response_dict["atomic_question"],
            "letter_choice": abstain_response_dict["letter_choice"],
            "confidence": abstain_response_dict["confidence"],
            "usage": abstain_response_dict["usage"]
        }


class FixedExpert(Expert):
    def respond(self, patient_state):
        # Decision-making based on the initial information, history of interactions, current inquiry, and options
        kwargs = self.get_abstain_kwargs(patient_state)
        abstain_response_dict = expert_functions.fixed_abstention_decision(**kwargs)
        if abstain_response_dict["abstain"] == False:
            return {
                "type": "choice",
                "letter_choice": abstain_response_dict["letter_choice"],
                "confidence": abstain_response_dict["confidence"],
                "usage": abstain_response_dict["usage"]
            }

        question_response_dict = self.ask_question(patient_state, abstain_response_dict["messages"])
        abstain_response_dict["usage"]["input_tokens"] += question_response_dict["usage"]["input_tokens"]
        abstain_response_dict["usage"]["output_tokens"] += question_response_dict["usage"]["output_tokens"]
        return {
            "type": "question",
            "question": question_response_dict["atomic_question"],
            "letter_choice": abstain_response_dict["letter_choice"],
            "confidence": abstain_response_dict["confidence"],
            "usage": abstain_response_dict["usage"]
        }
        

class BinaryExpert(Expert):
    def respond(self, patient_state):
        # Decision-making based on the initial information, history of interactions, current inquiry, and options
        kwargs = self.get_abstain_kwargs(patient_state)
        abstain_response_dict = expert_functions.binary_abstention_decision(**kwargs)
        if abstain_response_dict["abstain"] == False:
            return {
                "type": "choice",
                "letter_choice": abstain_response_dict["letter_choice"],
                "confidence": abstain_response_dict["confidence"],
                "usage": abstain_response_dict["usage"]
            }

        question_response_dict = self.ask_question(patient_state, abstain_response_dict["messages"])
        abstain_response_dict["usage"]["input_tokens"] += question_response_dict["usage"]["input_tokens"]
        abstain_response_dict["usage"]["output_tokens"] += question_response_dict["usage"]["output_tokens"]
        return {
            "type": "question",
            "question": question_response_dict["atomic_question"],
            "letter_choice": abstain_response_dict["letter_choice"],
            "confidence": abstain_response_dict["confidence"],
            "usage": abstain_response_dict["usage"]
        }


class NumericalExpert(Expert):
    def respond(self, patient_state):
        # Decision-making based on the initial information, history of interactions, current inquiry, and options
        kwargs = self.get_abstain_kwargs(patient_state)
        abstain_response_dict = expert_functions.numerical_abstention_decision(**kwargs)
        if abstain_response_dict["abstain"] == False:
            return {
                "type": "choice",
                "letter_choice": abstain_response_dict["letter_choice"],
                "confidence": abstain_response_dict["confidence"],
                "usage": abstain_response_dict["usage"]
            }

        question_response_dict = self.ask_question(patient_state, abstain_response_dict["messages"])
        abstain_response_dict["usage"]["input_tokens"] += question_response_dict["usage"]["input_tokens"]
        abstain_response_dict["usage"]["output_tokens"] += question_response_dict["usage"]["output_tokens"]
        return {
            "type": "question",
            "question": question_response_dict["atomic_question"],
            "letter_choice": abstain_response_dict["letter_choice"],
            "confidence": abstain_response_dict["confidence"],
            "usage": abstain_response_dict["usage"]
        }


class NumericalCutOffExpert(Expert):
    def respond(self, patient_state):
        # Decision-making based on the initial information, history of interactions, current inquiry, and options
        kwargs = self.get_abstain_kwargs(patient_state)
        abstain_response_dict = expert_functions.numcutoff_abstention_decision(**kwargs)
        if abstain_response_dict["abstain"] == False:
            return {
                "type": "choice",
                "letter_choice": abstain_response_dict["letter_choice"],
                "confidence": abstain_response_dict["confidence"],
                "usage": abstain_response_dict["usage"]
            }

        question_response_dict = self.ask_question(patient_state, abstain_response_dict["messages"])
        abstain_response_dict["usage"]["input_tokens"] += question_response_dict["usage"]["input_tokens"]
        abstain_response_dict["usage"]["output_tokens"] += question_response_dict["usage"]["output_tokens"]
        return {
            "type": "question",
            "question": question_response_dict["atomic_question"],
            "letter_choice": abstain_response_dict["letter_choice"],
            "confidence": abstain_response_dict["confidence"],
            "usage": abstain_response_dict["usage"]
        }


class ScaleExpert(Expert):
    def respond(self, patient_state):
        # Decision-making based on the initial information, history of interactions, current inquiry, and options
        kwargs = self.get_abstain_kwargs(patient_state)
        abstain_response_dict = expert_functions.scale_abstention_decision(**kwargs)
        if abstain_response_dict["abstain"] == False:
            return {
                "type": "choice",
                "letter_choice": abstain_response_dict["letter_choice"],
                "confidence": abstain_response_dict["confidence"],
                "usage": abstain_response_dict["usage"]
            }

        question_response_dict = self.ask_question(patient_state, abstain_response_dict["messages"])
        abstain_response_dict["usage"]["input_tokens"] += question_response_dict["usage"]["input_tokens"]
        abstain_response_dict["usage"]["output_tokens"] += question_response_dict["usage"]["output_tokens"]
        return {
            "type": "question",
            "question": question_response_dict["atomic_question"],
            "letter_choice": abstain_response_dict["letter_choice"],
            "confidence": abstain_response_dict["confidence"],
            "usage": abstain_response_dict["usage"]
        }


class UncertaintyAwareExpert(Expert):
    """
    Uncertainty-aware expert that uses the Universal Agent (Markdown-based tool calling).
    """

    def __init__(self, args, inquiry, options):
        super().__init__(args, inquiry, options)

        if not MULTI_AGENT_AVAILABLE:
            raise ImportError(
                "MultiAgent not available. Make sure src/agents/multi_agent.py "
                "and src/agents/agent.yaml are accessible."
            )

        # Load environment
        load_dotenv()

        # Initialize the Universal Agent
        self.uncertainty_agent = MultiAgent("universal_agent")
        
        # Override model if specified in args
        if hasattr(args, 'expert_model') and args.expert_model:
             self.uncertainty_agent.update_model(args.expert_model)

        # Track episode for logging
        from datetime import datetime
        self.episode_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Track cumulative token usage
        self.total_usage = {"input_tokens": 0, "output_tokens": 0}

    def respond(self, patient_state):
        """
        Use universal agent to decide whether to ask a question or make a diagnosis.
        """
        initial_info = patient_state['initial_info']
        history = patient_state['interaction_history']

        # Build Q&A history text
        if history:
            qa_text = "\n".join([
                f"Q{i+1}: {qa['question']}\nA{i+1}: {qa['answer']}"
                for i, qa in enumerate(history)
            ])
        else:
            qa_text = "No questions have been asked yet."

        # Format options
        options_text = "\n".join([f"{k}: {v}" for k, v in self.options.items()])

        # Create comprehensive task description
        task = f"""You are diagnosing a medical case.
        
PATIENT INITIAL INFORMATION:
{initial_info}

CONVERSATION HISTORY:
{qa_text}

DIAGNOSTIC QUESTION:
{self.inquiry}

POSSIBLE DIAGNOSES:
{options_text}

YOUR GOAL:
Diagnose the patient correctly. You can ask questions to gather more information or make a final diagnosis.
"""

        # Run the agent
        result = self.uncertainty_agent.run(task, episode_id=self.episode_id)

        # Track token usage
        if "total_tokens" in result:
            self.total_usage["input_tokens"] += result["total_tokens"].get("input", 0)
            self.total_usage["output_tokens"] += result["total_tokens"].get("output", 0)

        # Handle Terminal Result
        if result["type"] == "terminal":
            tool_name = result["tool"]
            args = result["args"]
            
            if tool_name == "ask_question":
                return {
                    "type": "question",
                    "question": args.get("question"),
                    "letter_choice": args.get("letter_choice", "F"), # Use extracted choice or default
                    "confidence": float(args.get("confidence", 0.5)),
                    "usage": self.total_usage,
                    "reasoning": args.get("reasoning", "")
                }
            
            elif tool_name in ["make_choice", "submit_evaluation"]:
                return {
                    "type": "choice",
                    "letter_choice": args.get("letter_choice","F"),
                    "confidence": float(args.get("confidence", 0.9)),
                    "usage": self.total_usage,
                    "reasoning": args.get("reasoning", "")
                }
        
        # Fallback
        return {
            "type": "choice",
            "letter_choice": "F",
            "confidence": 0.1,
            "usage": self.total_usage,
            "error": "Agent failed to produce a terminal tool call."
        }


class UncertaintyAwareExpert_native(Expert):
    """
    Uncertainty-aware expert using NativeToolAgent with OpenAI's native tool calling.
    More reliable than Markdown-based parsing.
    """

    def __init__(self, args, inquiry, options):
        super().__init__(args, inquiry, options)

        if not NATIVE_AGENT_AVAILABLE:
            raise ImportError(
                "NativeToolAgent not available. Make sure src/agents/multi_agent_native.py "
                "and src/agents/agent.yaml are accessible."
            )

        # Load environment
        load_dotenv()

        # Initialize the Universal Agent with native tool calling
        # Pass model directly to init
        model_name = args.expert_model if hasattr(args, 'expert_model') and args.expert_model else None
        self.uncertainty_agent = NativeToolAgent("universal_agent", model_name=model_name)

        # Track episode for logging
        from datetime import datetime
        self.episode_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Track cumulative token usage
        self.total_usage = {"input_tokens": 0, "output_tokens": 0}

    def respond(self, patient_state):
        """
        Use native tool agent to decide whether to ask a question or make a diagnosis.
        """
        initial_info = patient_state['initial_info']
        history = patient_state['interaction_history']

        # Build Q&A history text
        if history:
            qa_text = "\n".join([
                f"Q{i+1}: {qa['question']}\nA{i+1}: {qa['answer']}"
                for i, qa in enumerate(history)
            ])
        else:
            qa_text = "No questions have been asked yet."

        # Format options
        options_text = "\n".join([f"{k}: {v}" for k, v in self.options.items()])

        # Create comprehensive task description
        # Explicitly instruct to use FactSelectPatient behavior if needed
        task = f"""You are diagnosing a medical case.

PATIENT INITIAL INFORMATION:
{initial_info}

CONVERSATION HISTORY:
{qa_text}

DIAGNOSTIC QUESTION:
{self.inquiry}

POSSIBLE DIAGNOSES:
{options_text}

"""

        # Run the agent
        result = self.uncertainty_agent.run(task, episode_id=self.episode_id)

        # Track token usage
        if "total_tokens" in result:
            self.total_usage["input_tokens"] += result["total_tokens"].get("input", 0)
            self.total_usage["output_tokens"] += result["total_tokens"].get("output", 0)

        # Handle Terminal Result
        if result["type"] == "terminal":
            tool_name = result["tool"]
            args = result["args"]

            if tool_name == "ask_question":
                return {
                    "type": "question",
                    "question": args.get("question"),
                    "letter_choice": args.get("letter_choice", "F"),
                    "confidence": float(args.get("confidence", 0.5)),
                    "usage": self.total_usage,
                    "reasoning": args.get("reasoning", "")
                }

            elif tool_name in ["make_choice", "submit_evaluation"]:
                return {
                    "type": "choice",
                    "letter_choice": args.get("letter_choice", "F"),
                    "confidence": float(args.get("confidence", 0.9)),
                    "usage": self.total_usage,
                    "reasoning": args.get("reasoning", "")
                }

        # Fallback
        return {
            "type": "choice",
            "letter_choice": "F",
            "confidence": 0.1,
            "usage": self.total_usage,
            "error": "Agent failed to produce a terminal tool call."
        }



class ThreeAgentExpert(Expert):
    """
    Three-agent expert system:
    1. Memory Agent: Analyzes conversation progress and routes flow.
    2. Differential Agent: Rules out options and refines the list.
    3. Decision Agent: Makes a choice or asks a question based on the refined list.
    """

    def __init__(self, args, inquiry, options):
        super().__init__(args, inquiry, options)

        if not NATIVE_AGENT_AVAILABLE:
            raise ImportError(
                "NativeToolAgent not available. Make sure src/agents/multi_agent_native.py "
                "and src/agents/agent.yaml are accessible."
            )

        # Import MemoryAgent
        try:
            from memory_agent import MemoryAgent
        except ImportError:
            # Fallback if not in path, though it should be if src/agents is in path
            import sys
            sys.path.append(os.path.join(os.path.dirname(__file__), "../../../src/agents"))
            from memory_agent import MemoryAgent

        # Load environment
        load_dotenv()

        # Initialize agents
        model_name = args.expert_model if hasattr(args, 'expert_model') and args.expert_model else None
        self.differential_agent = NativeToolAgent("differential_agent", model_name=model_name)
        self.decision_agent = NativeToolAgent("decision_agent", model_name=model_name)

        # Initialize Memory Agent
        # args.output_filename is the path to results.jsonl, so we get the directory
        output_dir = os.path.dirname(args.output_filename) if hasattr(args, 'output_filename') else "outputs"
        self.memory_agent = MemoryAgent(output_dir, model_name=model_name)

        # Track episode for logging
        from datetime import datetime
        self.episode_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Track cumulative token usage
        self.total_usage = {"input_tokens": 0, "output_tokens": 0}

    def respond(self, patient_state):
        """
        Execute the three-agent flow with Memory Agent support.
        """
        initial_info = patient_state['initial_info']
        history = patient_state['interaction_history']

        # Build Q&A history text
        if history:
            qa_text = "\n".join([
                f"Q{i+1}: {qa['question']}\nA{i+1}: {qa['answer']}"
                for i, qa in enumerate(history)
            ])
        else:
            qa_text = "No questions have been asked yet."

        # --- Step 0: Memory Agent Analysis ---
        print(f"\n--- Running Memory Agent ---")
        has_new_info, strategy_suggestion, memory_trajectory = self.memory_agent.analyze_turn(history)
        
        full_trajectory = []
        if memory_trajectory:
            full_trajectory.extend(memory_trajectory)

        # Check Memory for previous differential
        latest_diff = self.memory_agent.get_latest_differential(self.inquiry, self.options)
        
        differential_data = None
        differential_analysis = "No analysis provided."
        diff_result = {}

        # --- Step 1: Differential Agent (Conditional) ---
        run_differential = has_new_info or not latest_diff
        
        if run_differential:
            # Determine options to present to Differential Agent
            if latest_diff and "current_differential_options" in latest_diff:
                current_options_text = latest_diff["current_differential_options"]
                print(f"[{self.episode_id}] Using refined options from memory.")
            else:
                current_options_text = "\n".join([f"{k}: {v}" for k, v in self.options.items()])
                print(f"[{self.episode_id}] Using initial options.")

            diff_task = f"""You are diagnosing a medical case.

PATIENT INITIAL INFORMATION:
{initial_info}

CONVERSATION HISTORY:
{qa_text}

DIAGNOSTIC QUESTION:
{self.inquiry}

CURRENT POSSIBLE DIAGNOSES (Refined from previous turns if applicable):
{current_options_text}
"""
            print(f"\n--- Running Differential Agent ---")
            diff_result = self.differential_agent.run(diff_task, episode_id=self.episode_id)

            # Track usage
            if "total_tokens" in diff_result:
                self.total_usage["input_tokens"] += diff_result["total_tokens"].get("input", 0)
                self.total_usage["output_tokens"] += diff_result["total_tokens"].get("output", 0)

            # Extract differential analysis
            if diff_result["type"] == "terminal" and diff_result["tool"] == "submit_differential":
                args = diff_result["args"]
                differential_data = args
                differential_analysis = f"""Updated Options:
{args.get('current_differential_options')}

Rule Out Criteria:
{args.get('rule_out_criteria')}

Confirmation Criteria:
{args.get('confirmation_criteria')}
"""
            else:
                print(f"Warning: Differential agent did not submit differential. Result: {diff_result}")
                differential_analysis = f"Agent failed to submit differential. Raw result: {diff_result}"
                
            if "trajectory" in diff_result:
                full_trajectory.extend(diff_result["trajectory"])
        
        else:
            print(f"[{self.episode_id}] No new info. Skipping Differential Agent and using cached analysis.")
            # Use cached differential
            if latest_diff:
                differential_data = latest_diff
                differential_analysis = f"""Updated Options:
{latest_diff.get('current_differential_options')}

Rule Out Criteria:
{latest_diff.get('rule_out_criteria')}

Confirmation Criteria:
{latest_diff.get('confirmation_criteria')}
"""

        # --- Step 2: Decision Agent ---
        strategy_context = ""
        if not has_new_info and strategy_suggestion:
            strategy_context = f"\nADVICE FROM MEMORY AGENT:\nThe patient did not provide new information in the last turn. Suggestion: {strategy_suggestion}\n"

        dec_task = f"""You are diagnosing a medical case.
DIAGNOSTIC QUESTION:
{self.inquiry}

PATIENT INITIAL INFORMATION:
{initial_info}

CONVERSATION HISTORY:
{qa_text}

DIFFERENTIAL AGENT ANALYSIS:
{differential_analysis}
{strategy_context}
YOUR GOAL:
Based on the analysis above, either ask a targeted question to differentiate further, or make a final diagnosis if you are confident.
"""
        print(f"\n--- Running Decision Agent ---")
        dec_result = self.decision_agent.run(dec_task, episode_id=self.episode_id)

        # Track usage
        if "total_tokens" in dec_result:
            self.total_usage["input_tokens"] += dec_result["total_tokens"].get("input", 0)
            self.total_usage["output_tokens"] += dec_result["total_tokens"].get("output", 0)

        if "trajectory" in dec_result:
            full_trajectory.extend(dec_result["trajectory"])

        # Save to Memory Agent
        turn_data = {
            "turn_index": len(history),
            "has_new_info": has_new_info,
            "differential_analysis": differential_data,
            "decision_result": dec_result.get("result"),
            "trajectory": full_trajectory
        }
        self.memory_agent.update_turn(self.inquiry, self.options, turn_data)

        # Handle Terminal Result
        if dec_result["type"] == "terminal":
            tool_name = dec_result["tool"]
            args = dec_result["args"]

            if tool_name == "ask_question":
                return {
                    "type": "question",
                    "question": args.get("question"),
                    "letter_choice": args.get("letter_choice", "F"),
                    "confidence": float(args.get("confidence", 0.5)),
                    "usage": self.total_usage,
                    "reasoning": args.get("reasoning", ""),
                    "trajectory": full_trajectory
                }

            elif tool_name == "make_choice":
                return {
                    "type": "choice",
                    "letter_choice": args.get("letter_choice", "F"),
                    "confidence": float(args.get("confidence", 0.9)),
                    "usage": self.total_usage,
                    "reasoning": args.get("reasoning", ""),
                    "trajectory": full_trajectory
                }

        # Fallback
        return {
            "type": "choice",
            "letter_choice": "F",
            "confidence": 0.1,
            "usage": self.total_usage,
            "error": "Agent failed to produce a terminal tool call.",
            "trajectory": full_trajectory
        }
