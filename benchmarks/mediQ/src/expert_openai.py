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
    Uncertainty-aware expert that uses iterative tool-calling to:
    1. Evaluate uncertainty and analyze evidence
    2. Search for medical information when needed
    3. Generate hypothesis-driven questions
    4. Make diagnosis when confident (>80%)

    This expert uses the UncertaintyAgent from general_agent.py which employs
    an agentic loop with tools: thinking, search_online, ask_question, make_choice
    """

    def __init__(self, args, inquiry, options):
        super().__init__(args, inquiry, options)

        if not UNCERTAINTY_AGENT_AVAILABLE:
            raise ImportError(
                "UncertaintyAgent not available. Make sure src/agents/general_agent.py "
                "and src/agents/tools.py are accessible."
            )

        # Load environment and initialize OpenAI client for OpenRouter
        load_dotenv()

        # Determine API configuration
        api_base_url = getattr(args, 'api_base_url', None)
        api_key_name = f"{args.api_account.upper()}_API_KEY"
        api_key = os.getenv(api_key_name)

        if not api_key:
            raise ValueError(
                f"API key not found: {api_key_name}. "
                f"Please set it in your .env file."
            )

        # Initialize client
        if api_base_url:
            self.client = OpenAI(api_key=api_key, base_url=api_base_url)
        else:
            # Default URLs for known providers
            if args.api_account == "openrouter":
                self.client = OpenAI(
                    api_key=api_key,
                    base_url="https://openrouter.ai/api/v1"
                )
            elif args.api_account == "deepseek":
                self.client = OpenAI(
                    api_key=api_key,
                    base_url="https://api.deepseek.com"
                )
            else:
                # OpenAI or other
                self.client = OpenAI(api_key=api_key)

        # Initialize UncertaintyAgent with tools
        self.uncertainty_agent = UncertaintyAgent(
            model_name=args.expert_model,
            client=self.client,
            verbose=False,  # Set to True for debugging
            tool=[think_tool, make_choice_tool, ask_question_tool, brave_search_tool],
            max_iterations=10
        )

        # Track token usage
        self.total_usage = {"input_tokens": 0, "output_tokens": 0}

    def respond(self, patient_state):
        """
        Use uncertainty-aware agent to decide whether to ask a question or make a diagnosis.

        Args:
            patient_state: Dict with 'initial_info' and 'interaction_history'

        Returns:
            Dict with 'type', 'question'/'letter_choice', 'confidence', 'usage'
        """
        # Format patient state into task prompt for the agent
        # print(f"what is patient state: {patient_state}")
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
        task = f"""You are diagnosing a medical case. Analyze the information and decide whether to ask the patient a question or make a final diagnosis.

PATIENT INITIAL INFORMATION:
{initial_info}

CONVERSATION HISTORY:
{qa_text}

DIAGNOSTIC QUESTION:
{self.inquiry}

POSSIBLE DIAGNOSES (choose one):
{options_text}

YOUR TASK:
1. Use 'thinking' tool to analyze the evidence for each diagnosis option
2. Use 'search_online' tool if you need medical knowledge about diagnostic criteria
3. Evaluate your confidence in making a diagnosis (0-100%)

If CONFIDENT (≥80%):
- Use 'make_choice' tool with your diagnosis letter (A/B/C/D) and confidence score

If UNCERTAIN (<80%):
- Use 'thinking' to identify what critical information would best differentiate between options
- Use 'search_online' if needed to understand diagnostic features
- Use 'ask_question' tool to ask ONE targeted question that follows differential diagnosis principles

Be systematic and evidence-based in your reasoning."""

        # Run the uncertainty agent
        result = self.uncertainty_agent.run(task)

        # The agent returns either a "choice" or "question" result
        # Format it for MediQ benchmark

        if result["type"] == "choice":
            # Agent made a diagnosis
            return {
                "type": "choice",
                "letter_choice": result["letter_choice"],
                "confidence": result["confidence"] / 100.0,  # Convert to 0-1 scale
                "usage": result.get("usage", {"input_tokens": 0, "output_tokens": 0}),
                "reasoning": "Uncertainty-aware agent confident in diagnosis"
            }

        elif result["type"] == "question":
            # Agent wants to ask a question
            # Need to provide intermediate diagnosis for MediQ tracking
            # Default to 'A' if no diagnosis provided
            intermediate_choice = result.get("letter_choice", "A")

            return {
                "type": "question",
                "question": result["question"],
                "letter_choice": intermediate_choice,
                "confidence": result.get("confidence", 50) / 100.0,  # Convert to 0-1 scale
                "usage": result.get("usage", {"input_tokens": 0, "output_tokens": 0}),
                "reasoning": "Need more information to confidently diagnose"
            }

        else:
            # Fallback in case of unexpected result
            return {
                "type": "choice",
                "letter_choice": "A",
                "confidence": 0.25,
                "usage": {"input_tokens": 0, "output_tokens": 0},
                "error": "Unexpected agent output format"
            }


