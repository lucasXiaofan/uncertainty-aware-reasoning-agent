"""Uncertainty-aware doctor agent wrapper for AgentClinic integration.

This module provides UncertaintyAwareDoctorAgent as a drop-in replacement
for DoctorAgent in agentclinic_api_only.py.

Session lifecycle: One session per scenario, created in main() of agentclinic_api_only.py.
Each doctor-patient-measurement conversation belongs to that session.
"""
import os
import sys
import time

# Add paths for imports
src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if src_path not in sys.path:
    sys.path.append(src_path)

agent_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../agent"))
if agent_path not in sys.path:
    sys.path.append(agent_path)

from single_agent import SingleAgent
from tools import get_accumulated_notes, set_current_session
from tools.diagnosis_session import load_session
from tools.implementations import final_diagnosis
from tools.documentation_tools import final_diagnosis_documented, get_current_documented_response


class UncertaintyAwareDoctorAgent:
    """Drop-in replacement for DoctorAgent with explicit uncertainty tracking.

    Each agent turn:
    1. Wrapper sets session context
    2. Agent calls diagnosis_step (records info + returns formatted action)
    3. OR agent calls final_diagnosis (returns "DIAGNOSIS READY: [diagnosis]")

    Session is managed automatically by wrapper - agent doesn't see session_id.
    """

    def __init__(self, scenario, backend_str="x-ai/grok-4.1-fast", max_infs=20,
                 bias_present=None, img_request=False, agent_type="uncertainty_aware_doctor"):
        """Initialize the uncertainty-aware doctor agent.

        Args:
            scenario: The clinical scenario object
            backend_str: Model identifier (for logging)
            max_infs: Maximum number of inference turns
            bias_present: Cognitive bias to simulate (not implemented)
            img_request: Whether image requests are allowed
            agent_type: Which agent configuration to use ("uncertainty_aware_doctor" or "uncertainty_documentation_agent")
        """
        self.scenario = scenario
        self.backend = backend_str
        self.MAX_INFS = max_infs
        self.infs = 0
        self.bias_present = None if bias_present == "None" else bias_present
        self.img_request = img_request
        self.agent_type = agent_type

        # Session ID: unique per scenario
        # Format: scenario_{scenario_id}_{timestamp}
        self.session_id = f"scenario_{id(scenario)}_{int(time.time())}"

        # Initialize the SingleAgent with specified configuration
        self.agent = SingleAgent(agent_type)

        # Track conversation history for context
        self.agent_hist = ""
        self.presentation = scenario.examiner_information()

        # Token tracking (for compatibility with original DoctorAgent interface)
        self.total_tokens = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0

    def inference_doctor(self, patient_response: str, image_requested: bool = False,
                         memory_context: str = "") -> str:
        """Generate doctor's response to patient/measurement input.

        Each call does exactly one tool call (diagnosis_step or final_diagnosis).
        The tool returns the formatted action to output.

        Args:
            patient_response: The patient's response or test results
            image_requested: Whether an image was requested (unused)
            memory_context: Optional context from past diagnostic experiences

        Returns:
            Doctor's response in AgentClinic-compatible format
        """
        # Set session context for this thread (tools will use it automatically)
        set_current_session(self.session_id)

        # Check if max inferences reached - call appropriate final_diagnosis directly
        if self.infs >= self.MAX_INFS:
            reason_msg = "Maximum turns reached - providing diagnosis based on all collected information"

            # Use appropriate final_diagnosis based on agent type
            if self.agent_type == "uncertainty_documentation_agent":
                response = final_diagnosis_documented(reason=reason_msg)
            else:
                response = final_diagnosis(reason_ready=reason_msg)

            return response

        # Build the prompt with context
        prompt = self._build_prompt(patient_response, memory_context)

        # Run the agent (max_turns=1, one tool call per inference)
        result = self.agent.run(
            user_input=prompt,
            episode_id=self.session_id,
            max_turns=5
        )

        # Extract the tool result (diagnosis_step or final_diagnosis output)
        response = self._extract_response(result)

        # Update history
        self.agent_hist += f"Patient/Test: {patient_response}\nDoctor: {response}\n\n"
        self.infs += 1

        # Track tokens
        if "total_tokens" in result:
            self.total_tokens += result["total_tokens"].get("input", 0) + result["total_tokens"].get("output", 0)
            self.prompt_tokens += result["total_tokens"].get("input", 0)
            self.completion_tokens += result["total_tokens"].get("output", 0)

        return response

    def _build_prompt(self, patient_response: str, memory_context: str = "") -> str:
        """Build the prompt for the agent.

        Args:
            patient_response: Latest patient/measurement response
            memory_context: Optional experience context

        Returns:
            Formatted prompt string
        """
        parts = []

        # Clinical objective
        parts.append(f"OBJECTIVE: {self.presentation}")
        parts.append("")

        # Progress - with explicit rounds remaining
        turns_remaining = self.MAX_INFS - self.infs
        parts.append(f"CURRENT TURN: {self.infs + 1} of {self.MAX_INFS}")
        parts.append(f"ACTIONS REMAINING: {turns_remaining}")

        # Conversation history
        if self.agent_hist:
            parts.append("CONVERSATION HISTORY:")
            parts.append(self.agent_hist)
            parts.append("")

        # Latest response to analyze
        parts.append("LATEST RESPONSE:")
        parts.append(patient_response)
        parts.append("")

        return "\n".join(parts)

    def _extract_response(self, result: dict) -> str:
        """Extract the doctor's response from agent result.

        The tool (diagnosis_step/document_step or final_diagnosis/final_diagnosis_documented)
        returns the formatted output directly.

        Args:
            result: The result dictionary from SingleAgent.run()

        Returns:
            The doctor's response string (formatted action or diagnosis)
        """
        # Check if this was a terminal tool (final_diagnosis or final_diagnosis_documented)
        tool_name = result.get("tool", "")
        if result.get("type") == "terminal" and tool_name in ["final_diagnosis", "final_diagnosis_documented"]:
            # Returns "DIAGNOSIS READY: [diagnosis]"
            return result.get("result", "DIAGNOSIS READY: Unable to determine")
        if result.get("type") == "terminal" and tool_name == "document_step":
            raw_result = result.get("result", "")
            if isinstance(raw_result, str) and raw_result.strip():
                return raw_result.strip()
            # Fallback to latest documented action if result is missing or malformed
            try:
                return get_current_documented_response(self.session_id)
            except Exception:
                return "Error: Unable to retrieve documented action."

        # For diagnosis_step or document_step, extract the tool result
        raw_result = result.get("result", "")

        # The tool returns the formatted action directly
        if isinstance(raw_result, str):
            return raw_result.strip()

        # Fallback
        return str(raw_result) if raw_result else "I need more information to proceed."

    def reset(self) -> None:
        """Reset the agent state for a new scenario.

        Note: Sessions are typically not cleared between turns in the same scenario.
        This is only needed if reusing the agent object for multiple scenarios.
        """
        self.agent_hist = ""
        self.presentation = self.scenario.examiner_information()
        self.infs = 0
        # Generate new session ID for new scenario
        self.session_id = f"scenario_{id(self.scenario)}_{int(time.time())}"
