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
        # print(f"what is the model name: {args.expert_model}")
        self.uncertainty_agent = UncertaintyAgent(
            # TODO: change this to args.expert_model, now is hard coded to deepseek for experiment purpose
            # model_name="deepseek-chat",
            model_name=args.expert_model,
            client=self.client,
            verbose=False,  # Set to True for debugging
            # tool=[think_tool, make_choice_tool, ask_question_tool, brave_search_tool],
            # TRY without search
            tool=[think_tool, make_choice_tool, ask_question_tool],

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
            try:
                confidence = float(result["confidence"]) / 100.0
            except (ValueError, TypeError):
                confidence = None

            return {
                "type": "choice",
                "letter_choice": result["letter_choice"],
                "confidence": confidence,  # Convert to 0-1 scale
                "usage": result.get("usage", {"input_tokens": 0, "output_tokens": 0}),
                "reasoning": "Uncertainty-aware agent confident in diagnosis"
            }

        elif result["type"] == "question":
            # Agent wants to ask a question
            # Need to provide intermediate diagnosis for MediQ tracking
            # Default to 'A' if no diagnosis provided
            intermediate_choice = result.get("letter_choice", "A")

            try:
                confidence = float(result.get("confidence", 50)) / 100.0
            except (ValueError, TypeError):
                confidence = None

            return {
                "type": "question",
                "question": result["question"],
                "letter_choice": intermediate_choice,
                "confidence": confidence,  # Convert to 0-1 scale
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


