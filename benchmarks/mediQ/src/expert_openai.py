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


class MultiAgentExpert(Expert):
    """
    Multi-agent expert that uses three specialized agents:
    1. Uncertainty Evaluator: Analyzes what info we know/need
    2. Discriminator: Generates strategic questions
    3. Decision Maker: Makes final diagnosis

    Uses the multi-agent system from src/agents/multi_agent.py
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

        # Initialize the three agents
        self.uncertainty_agent = MultiAgent("uncertainty_evaluator")
        self.discriminator_agent = MultiAgent("discriminator")
        self.decision_agent = MultiAgent("decision_maker")

        # Track episode for logging
        from datetime import datetime
        self.episode_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Track cumulative token usage for this episode
        self.total_usage = {"input_tokens": 0, "output_tokens": 0}

    def respond(self, patient_state):
        """
        Use multi-agent system to decide whether to ask a question or make a diagnosis.

        Args:
            patient_state: Dict with 'initial_info' and 'interaction_history'

        Returns:
            Dict with 'type', 'question'/'letter_choice', 'confidence', 'usage'
        """
        import json

        initial_info = patient_state['initial_info']
        history = patient_state['interaction_history']

        # Build conversation text
        conversation = [initial_info]
        if history:
            for i, qa in enumerate(history):
                conversation.append(f"Q{i+1}: {qa['question']}")
                conversation.append(f"A{i+1}: {qa['answer']}")

        # Format options
        options_text = "\n".join([f"{k}: {v}" for k, v in self.options.items()])

        # Create context for uncertainty evaluator
        context = f"""{initial_info}

Conversation History:
{chr(10).join(conversation[1:]) if len(conversation) > 1 else 'No questions asked yet.'}

Diagnostic Question: {self.inquiry}

Options:
{options_text}"""

        # Step 1: Run uncertainty evaluator
        unc_result = self.uncertainty_agent.run(context, episode_id=self.episode_id)

        # Track token usage
        if "total_tokens" in unc_result:
            self.total_usage["input_tokens"] += unc_result["total_tokens"].get("input", 0)
            self.total_usage["output_tokens"] += unc_result["total_tokens"].get("output", 0)

        if unc_result["type"] != "terminal":
            # Fallback if something went wrong
            return {
                "type": "choice",
                "letter_choice": "F",
                "confidence": 0.25,
                "usage": self.total_usage,
                "error": "Uncertainty agent did not return terminal result"
            }

        eval_data = unc_result["args"]

        # Extract best-guess diagnosis from uncertainty agent (always available as fallback)
        unc_letter_choice = eval_data.get('letter_choice', 'F')
        unc_confidence = eval_data.get('confidence', 50)

        # Step 2: Check if we have enough info
        if eval_data['has_enough_info']:
            # Go to decision maker
            dec_result = self.decision_agent.run(context, episode_id=self.episode_id)

            # Track token usage
            if "total_tokens" in dec_result:
                self.total_usage["input_tokens"] += dec_result["total_tokens"].get("input", 0)
                self.total_usage["output_tokens"] += dec_result["total_tokens"].get("output", 0)

            if dec_result["type"] == "terminal":
                final = dec_result["args"]
                try:
                    confidence = float(final.get('confidence', 80)) / 100.0
                except (ValueError, TypeError):
                    confidence = 0.8

                return {
                    "type": "choice",
                    "letter_choice": final['letter_choice'],
                    "confidence": confidence,
                    "usage": self.total_usage,
                    "reasoning": final.get('reasoning', 'Multi-agent confident in diagnosis')
                }
            else:
                # Fallback if decision agent failed - use uncertainty agent's choice
                try:
                    confidence = float(unc_confidence) / 100.0
                except (ValueError, TypeError):
                    confidence = 0.5

                return {
                    "type": "choice",
                    "letter_choice": unc_letter_choice,
                    "confidence": confidence,
                    "usage": self.total_usage,
                    "reasoning": "Using uncertainty agent's best guess (decision agent failed)"
                }

        # Step 3: Not enough info, ask a question via discriminator
        disc_input = f"""Known Information: {json.dumps(eval_data['known_info'])}
Missing Information: {json.dumps(eval_data['missing_info'])}

Conversation History:
{chr(10).join(conversation[1:]) if len(conversation) > 1 else 'No questions asked yet.'}

Formulate your question based on this context."""

        disc_result = self.discriminator_agent.run(disc_input, episode_id=self.episode_id)

        # Track token usage
        if "total_tokens" in disc_result:
            self.total_usage["input_tokens"] += disc_result["total_tokens"].get("input", 0)
            self.total_usage["output_tokens"] += disc_result["total_tokens"].get("output", 0)

        if disc_result["type"] == "terminal":
            question_data = disc_result["args"]
            try:
                confidence = float(question_data.get('confidence', 50)) / 100.0
            except (ValueError, TypeError):
                confidence = 0.5

            return {
                "type": "question",
                "question": question_data["question"],
                "letter_choice": unc_letter_choice,  # Use uncertainty agent's best guess
                "confidence": confidence,
                "usage": self.total_usage,
                "reasoning": question_data.get('reasoning', 'Need more information')
            }

        # Fallback - use uncertainty agent's best guess
        try:
            confidence = float(unc_confidence) / 100.0
        except (ValueError, TypeError):
            confidence = 0.25

        return {
            "type": "choice",
            "letter_choice": unc_letter_choice,
            "confidence": confidence,
            "usage": self.total_usage,
            "error": "Could not generate question or decision (using uncertainty agent fallback)"
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
        self.uncertainty_agent = NativeToolAgent("universal_agent")

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


