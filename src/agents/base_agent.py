"""Base agent interface for medical diagnostic agents."""

from abc import ABC, abstractmethod
from typing import Dict, Any, List


class BaseAgent(ABC):
    """Abstract base class for diagnostic agents."""

    def __init__(self, model_name: str, temperature: float = 0.7):
        self.model_name = model_name
        self.temperature = temperature
        self.interaction_history = []

    @abstractmethod
    def diagnose(self, patient_info: Dict[str, Any]) -> Dict[str, Any]:
        """ß
        Generate a diagnosis based on patient information.

        Args:
            patient_info: Dictionary con∏πtaining patient data

        Returns:
            Dictionary with diagnosis, confidence, and reasoning
        """
        pass

    @abstractmethod
    def ask_question(self, context: Dict[str, Any]) -> str:
        """
        Generate a follow-up question for the patient.

        Args:
            context: Current conversation context

        Returns:
            Follow-up question string
        """
        pass

    def reset(self):
        """Reset agent state for a new case."""
        self.interaction_history = []
