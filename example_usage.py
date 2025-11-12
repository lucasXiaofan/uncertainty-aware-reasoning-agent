"""Example usage of the baseline DSPy ReAct agent."""

import os
from dotenv import load_dotenv
from src.agents import DSPyReActAgent
from src.utils import setup_logger

# Load environment variables
load_dotenv()

# Set up logging
logger = setup_logger()


def example_diagnosis():
    """Example: Simple diagnosis task."""
    logger.info("=" * 60)
    logger.info("Example 1: Simple Diagnosis")
    logger.info("=" * 60)

    # Initialize agent
    agent = DSPyReActAgent(model_name="gpt-4o-mini", temperature=0.7)

    # Example patient information
    patient_info = {
        'age': 45,
        'gender': 'male',
        'symptoms': ['chest pain', 'shortness of breath', 'sweating'],
        'history': ['hypertension', 'smoking'],
        'chief_complaint': 'Sudden onset chest pain radiating to left arm'
    }

    # Get diagnosis
    result = agent.diagnose(patient_info)

    # Display results
    logger.info(f"\nDiagnosis: {result['diagnosis']}")
    logger.info(f"Confidence: {result['confidence']}")
    logger.info(f"Reasoning: {result['reasoning']}")
    if result['tool_calls']:
        logger.info(f"Tool calls made: {len(result['tool_calls'])}")


def example_interactive_diagnosis():
    """Example: Interactive diagnosis with follow-up questions."""
    logger.info("\n" + "=" * 60)
    logger.info("Example 2: Interactive Diagnosis")
    logger.info("=" * 60)

    # Initialize agent
    agent = DSPyReActAgent(model_name="gpt-4o-mini", temperature=0.7)

    # Initial patient information (minimal)
    context = {
        'patient_info': {
            'age': 30,
            'gender': 'female',
            'chief_complaint': 'persistent headache for 3 days'
        },
        'previous_questions': [],
        'answers': []
    }

    # Agent asks follow-up questions
    logger.info("\nInitial information:")
    logger.info(f"  Age: {context['patient_info']['age']}")
    logger.info(f"  Chief complaint: {context['patient_info']['chief_complaint']}")

    for i in range(3):
        # Generate follow-up question
        question = agent.ask_question(context)
        logger.info(f"\nAgent Question {i+1}: {question}")

        # Simulate patient response (in real scenario, this comes from patient)
        simulated_answer = "Simulated patient response"
        logger.info(f"Patient Answer: {simulated_answer}")

        context['previous_questions'].append(question)
        context['answers'].append(simulated_answer)

    # Final diagnosis
    result = agent.diagnose(context['patient_info'])
    logger.info(f"\nFinal Diagnosis: {result['diagnosis']}")
    logger.info(f"Confidence: {result['confidence']}")


def main():
    """Run examples."""
    # Check for API key
    if not os.getenv('OPENAI_API_KEY'):
        logger.error("OPENAI_API_KEY not found!")
        logger.error("Please create a .env file with your OpenAI API key:")
        logger.error("  cp .env.example .env")
        logger.error("  # Edit .env and add your API key")
        return

    try:
        # Run examples
        example_diagnosis()
        example_interactive_diagnosis()

        logger.info("\n" + "=" * 60)
        logger.info("Examples completed successfully!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Error running examples: {e}")
        raise


if __name__ == "__main__":
    main()
