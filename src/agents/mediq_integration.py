"""
Integration module for using uncertainty-aware agents with MediQ benchmark.

This module provides a wrapper that adapts the MediQDiagnosisAgent to work
with the MediQ benchmark's expert system interface.
"""

import os
import sys
from pathlib import Path

# Add src to path to import general_agent
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))

from agents.general_agent import MediQDiagnosisAgent


class UncertaintyAwareExpert:
    """
    Expert class compatible with MediQ benchmark that uses uncertainty-aware agents.

    This class implements the Expert interface expected by MediQ's benchmarking system
    while leveraging the UncertaintyAgent and HypothesisGenerationAgent for
    intelligent question generation.
    """

    def __init__(self, args, inquiry, options):
        """
        Initialize the uncertainty-aware expert.

        Args:
            args: MediQ argument namespace containing model configuration
            inquiry: The diagnostic question (e.g., "What is the most likely diagnosis?")
            options: Dictionary mapping letters to diagnosis options
        """
        self.args = args
        self.inquiry = inquiry
        self.options = options

        # Initialize the diagnosis agent
        self.diagnosis_agent = MediQDiagnosisAgent(
            model_name=args.expert_model,
            max_questions=args.max_questions,
            verbose=False  # Set to True for debugging
        )

        # Track state
        self.num_questions_asked = 0
        self.patient_simulator = None

    def respond(self, patient_state):
        """
        Generate expert response based on current patient state.

        This is called by MediQ's benchmarking loop to get the expert's next action.

        Args:
            patient_state: Dict containing:
                - 'initial_info': Initial patient information
                - 'interaction_history': List of {'question': str, 'answer': str}

        Returns:
            Dict containing:
                - 'type': 'question' or 'choice'
                - 'question': Next question to ask (if type='question')
                - 'letter_choice': Diagnosis letter (A/B/C/D)
                - 'confidence': Confidence score
                - 'usage': Token usage info
        """
        # Reset the agent's memory with current state
        self.diagnosis_agent.reset_memory()
        self.diagnosis_agent.memory['patient_info'] = patient_state['initial_info']
        self.diagnosis_agent.memory['inquiry'] = self.inquiry
        self.diagnosis_agent.memory['options'] = self.options
        self.diagnosis_agent.memory['qa_history'] = patient_state['interaction_history']

        # Evaluate uncertainty
        evaluation = self.diagnosis_agent.uncertainty_agent.evaluate(
            patient_info=patient_state['initial_info'],
            qa_history=patient_state['interaction_history'],
            options=self.options,
            inquiry=self.inquiry
        )

        # If confident enough, return diagnosis
        if evaluation['confident'] and evaluation['diagnosis']:
            return {
                'type': 'choice',
                'letter_choice': evaluation['diagnosis'],
                'confidence': evaluation['confidence_score'] / 100.0,
                'reasoning': evaluation['reasoning'],
                'usage': self._get_usage()
            }

        # If max questions reached, force diagnosis
        if len(patient_state['interaction_history']) >= self.args.max_questions:
            best_diagnosis = evaluation['diagnosis'] or 'A'
            return {
                'type': 'choice',
                'letter_choice': best_diagnosis,
                'confidence': evaluation['confidence_score'] / 100.0,
                'reasoning': evaluation['reasoning'],
                'usage': self._get_usage(),
                'forced': True
            }

        # Generate next question using hypothesis agent
        question_result = self.diagnosis_agent.hypothesis_agent.generate_question(
            patient_info=patient_state['initial_info'],
            qa_history=patient_state['interaction_history'],
            options=self.options,
            missing_info=evaluation['missing_info'],
            evidence_summary=evaluation.get('evidence_summary', {}),
            inquiry=self.inquiry
        )

        # Return intermediate diagnosis along with question
        intermediate_diagnosis = evaluation['diagnosis'] or 'A'

        return {
            'type': 'question',
            'question': question_result['question'],
            'letter_choice': intermediate_diagnosis,  # Required by MediQ for intermediate tracking
            'confidence': evaluation['confidence_score'] / 100.0,
            'rationale': question_result['rationale'],
            'usage': self._get_usage()
        }

    def _get_usage(self):
        """Get token usage statistics."""
        # Placeholder - you could track actual token usage if needed
        return {
            'input_tokens': 0,
            'output_tokens': 0
        }


