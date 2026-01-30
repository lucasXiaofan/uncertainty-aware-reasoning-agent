"""Run memory creation agent on failed medical diagnosis cases."""
import json
import argparse
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from single_agent import SingleAgent


def load_jsonl(file_path: str) -> list[dict]:
    """Load cases from a JSONL file.

    Args:
        file_path: Path to the JSONL file

    Returns:
        List of case dictionaries
    """
    cases = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


def filter_failed_cases(cases: list[dict]) -> list[dict]:
    """Filter cases to only include those where correct is False.

    Args:
        cases: List of all cases

    Returns:
        List of failed cases only
    """
    return [case for case in cases if not case.get("correct", True)]


def format_case_for_analysis(case: dict) -> str:
    """Format a case into a prompt for the memory creation agent.

    Extracts and organizes:
    - Doctor's initial information (what doctor knew at the start)
    - Dialogue trajectory (what doctor asked/tested and learned)
    - Reference answer (complete patient information doctor didn't know)
    - case_id, correct_diagnosis, model_diagnosis

    Args:
        case: The case dictionary

    Returns:
        Formatted string for the memory creation agent
    """
    case_id = f"{case.get('dataset', 'unknown')}_{case.get('scenario_id', 'unknown')}"

    # Extract problem info
    problem_info = case.get('problem_info', {})
    osce = problem_info.get('OSCE_Examination', {})
    patient_actor = osce.get('Patient_Actor', {})

    # Doctor's initial information (what they see at the start)
    initial_info = {
        "objective": osce.get('Objective_for_Doctor', ''),
        "patient_demographics": patient_actor.get('Demographics', ''),
        "chief_complaint": patient_actor.get('History', ''),
        "primary_symptom": patient_actor.get('Symptoms', {}).get('Primary_Symptom', ''),
        "secondary_symptoms": patient_actor.get('Symptoms', {}).get('Secondary_Symptoms', [])
    }

    # Reference answer (complete patient information doctor didn't initially have)
    reference_answer = {
        "past_medical_history": patient_actor.get('Past_Medical_History', ''),
        "social_history": patient_actor.get('Social_History', ''),
        "review_of_systems": patient_actor.get('Review_of_Systems', ''),
        "physical_examination_findings": osce.get('Physical_Examination_Findings', {}),
        "test_results": osce.get('Test_Results', {}),
        "correct_diagnosis": osce.get('Correct_Diagnosis', case.get('correct_diagnosis', ''))
    }

    # Format dialogue trajectory
    dialogue_history = case.get('dialogue_history', [])
    dialogue_trajectory = "\n".join([f"[Turn {i}] {turn}" for i, turn in enumerate(dialogue_history)])

    # Build the formatted prompt
    formatted = f"""## CASE ANALYSIS INPUT

### Case Metadata
- case_id: {case_id}
- correct_diagnosis: {case.get('correct_diagnosis', 'Unknown')}
- model_diagnosis: {case.get('model_diagnosis', 'Unknown')}

### 1. Doctor's Initial Information
{json.dumps(initial_info, indent=2)}

### 2. Dialogue Trajectory
{dialogue_trajectory}

### 3. Reference Answer (Complete Patient Information)
{json.dumps(reference_answer, indent=2)}

---
Extract AT MOST 3 critical decision points where the diagnostic reasoning could be improved.
For each experience, use the save_experience tool with the case_id: {case_id}
"""

    return formatted


def process_single_case(case: dict, case_index: int, total_cases: int,
                        agent_name: str, model_name: str,
                        trajectory_log_dir: str, conversation_log_path: str) -> dict:
    """Process a single case with its own agent instance.

    Args:
        case: The case dictionary to process
        case_index: Index of the case (for logging)
        total_cases: Total number of cases (for logging)
        agent_name: Name of the agent to use
        model_name: Optional model override
        trajectory_log_dir: Optional directory for trajectory logs
        conversation_log_path: Optional path to conversation log

    Returns:
        Result dictionary for this case
    """
    case_id = f"{case.get('dataset', 'unknown')}_{case.get('scenario_id', case_index)}"

    print(f"\n{'='*60}")
    print(f"Processing case {case_index+1}/{total_cases}: {case_id}")
    print(f"Correct: {case.get('correct_diagnosis')} | Model: {case.get('model_diagnosis')}")
    print(f"{'='*60}")

    # Each worker gets its own agent instance
    agent = SingleAgent(
        agent_name,
        model_name=model_name,
        trajectory_log_dir=trajectory_log_dir,
        conversation_log_path=conversation_log_path
    )

    # Format case for analysis
    prompt = format_case_for_analysis(case)

    try:
        result = agent.run(prompt, episode_id=case_id)

        print(f"Case {case_id}: Analysis completed")

        return {
            "case_id": case_id,
            "correct_diagnosis": case.get("correct_diagnosis"),
            "model_diagnosis": case.get("model_diagnosis"),
            "status": result.get("type", "unknown"),
            "result": result
        }

    except Exception as e:
        print(f"Error processing case {case_id}: {e}")
        return {
            "case_id": case_id,
            "status": "error",
            "error": str(e)
        }


def run_memory_agent_on_cases(
    jsonl_path: str,
    agent_name: str = "memory_creation_agent",
    model_name: str = None,
    output_dir: str = None,
    trajectory_log_dir: str = None,
    conversation_log_path: str = None,
    max_workers: int = 5
) -> dict:
    """Run the memory creation agent on all failed cases in a JSONL file.

    Args:
        jsonl_path: Path to the JSONL file with cases
        agent_name: Name of the agent to use from config
        model_name: Optional model override
        output_dir: Optional output directory for results
        trajectory_log_dir: Optional directory to save trajectory logs
        conversation_log_path: Optional path to conversation log file
        max_workers: Maximum number of parallel workers (default: 5)

    Returns:
        Summary of the run
    """
    # Load and filter cases
    print(f"Loading cases from {jsonl_path}...")
    all_cases = load_jsonl(jsonl_path)
    failed_cases = filter_failed_cases(all_cases)

    print(f"Found {len(all_cases)} total cases, {len(failed_cases)} failed cases")
    print(f"Using {max_workers} parallel workers")

    if not failed_cases:
        print("No failed cases to process.")
        return {"total_cases": len(all_cases), "failed_cases": 0, "processed": 0}

    # Process cases in parallel
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_case = {
            executor.submit(
                process_single_case,
                case, i, len(failed_cases),
                agent_name, model_name,
                trajectory_log_dir, conversation_log_path
            ): case
            for i, case in enumerate(failed_cases)
        }

        # Collect results as they complete
        for future in as_completed(future_to_case):
            result = future.result()
            results.append(result)

    # Save summary
    summary = {
        "timestamp": datetime.now().isoformat(),
        "input_file": str(jsonl_path),
        "total_cases": len(all_cases),
        "failed_cases": len(failed_cases),
        "processed": len(results),
        "successful": sum(1 for r in results if r.get("status") != "error"),
        "results": results
    }

    # Save summary to file
    if output_dir:
        output_path = Path(output_dir)
    else:
        output_path = Path(__file__).parent / "memory"

    output_path.mkdir(parents=True, exist_ok=True)
    summary_file = output_path / f"run_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    # Get experience count from file
    experience_file = Path(__file__).parent / "memory" / "diagnostic_experiences.json"
    experience_count = 0
    if experience_file.exists():
        try:
            with open(experience_file, "r") as f:
                content = f.read().strip()
                if content:
                    experience_count = len(json.loads(content))
        except (json.JSONDecodeError, Exception):
            pass

    print(f"\n{'='*60}")
    print("RUN SUMMARY")
    print(f"{'='*60}")
    print(f"Total cases: {summary['total_cases']}")
    print(f"Failed cases: {summary['failed_cases']}")
    print(f"Processed: {summary['processed']}")
    print(f"Successful: {summary['successful']}")
    print(f"Experiences in file: {experience_count}")
    print(f"Summary saved to: {summary_file}")

    return summary


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run memory creation agent on failed medical diagnosis cases"
    )
    parser.add_argument(
        "jsonl_file",
        help="Path to JSONL file containing medical cases"
    )
    parser.add_argument(
        "--agent", "-a",
        default="memory_creation_agent",
        help="Agent name from config (default: memory_creation_agent)"
    )
    parser.add_argument(
        "--model", "-m",
        default=None,
        help="Override model from config"
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output directory for results"
    )
    parser.add_argument(
        "--trajectory-dir", "-t",
        default=None,
        help="Directory to save trajectory logs (default: trajectories_log/)"
    )
    parser.add_argument(
        "--conversation-log", "-c",
        default=None,
        help="Path to conversation log file (default: memory/conversation_log.json)"
    )
    parser.add_argument(
        "--max-workers", "-w",
        type=int,
        default=5,
        help="Maximum number of parallel workers (default: 5)"
    )

    args = parser.parse_args()

    run_memory_agent_on_cases(
        jsonl_path=args.jsonl_file,
        agent_name=args.agent,
        model_name=args.model,
        output_dir=args.output,
        trajectory_log_dir=args.trajectory_dir,
        conversation_log_path=args.conversation_log,
        max_workers=args.max_workers
    )


if __name__ == "__main__":
    main()
