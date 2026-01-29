"""Run memory creation agent on failed medical diagnosis cases."""
import json
import argparse
from pathlib import Path
from datetime import datetime

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

    Args:
        case: The case dictionary

    Returns:
        JSON string of the case
    """
    case_id = f"{case.get('dataset', 'unknown')}_{case.get('scenario_id', 'unknown')}"

    # Just pass the case as JSON with the case_id added
    case_data = {
        "case_id": case_id,
        **case
    }

    return json.dumps(case_data, indent=2)


def run_memory_agent_on_cases(
    jsonl_path: str,
    agent_name: str = "memory_creation_agent",
    model_name: str = None,
    output_dir: str = None,
    trajectory_log_dir: str = None,
    conversation_log_path: str = None
) -> dict:
    """Run the memory creation agent on all failed cases in a JSONL file.

    Args:
        jsonl_path: Path to the JSONL file with cases
        agent_name: Name of the agent to use from config
        model_name: Optional model override
        output_dir: Optional output directory for results
        trajectory_log_dir: Optional directory to save trajectory logs
        conversation_log_path: Optional path to conversation log file

    Returns:
        Summary of the run
    """
    # Load and filter cases
    print(f"Loading cases from {jsonl_path}...")
    all_cases = load_jsonl(jsonl_path)
    failed_cases = filter_failed_cases(all_cases)

    print(f"Found {len(all_cases)} total cases, {len(failed_cases)} failed cases")

    if not failed_cases:
        print("No failed cases to process.")
        return {"total_cases": len(all_cases), "failed_cases": 0, "processed": 0}

    # Initialize agent
    agent = SingleAgent(
        agent_name,
        model_name=model_name,
        trajectory_log_dir=trajectory_log_dir,
        conversation_log_path=conversation_log_path
    )

    # Process each failed case
    results = []
    for i, case in enumerate(failed_cases):
        case_id = f"{case.get('dataset', 'unknown')}_{case.get('scenario_id', i)}"
        print(f"\n{'='*60}")
        print(f"Processing case {i+1}/{len(failed_cases)}: {case_id}")
        print(f"Correct: {case.get('correct_diagnosis')} | Model: {case.get('model_diagnosis')}")
        print(f"{'='*60}")

        # Format case for analysis
        prompt = format_case_for_analysis(case)

        # Run agent
        try:
            result = agent.run(prompt, episode_id=case_id)

            results.append({
                "case_id": case_id,
                "correct_diagnosis": case.get("correct_diagnosis"),
                "model_diagnosis": case.get("model_diagnosis"),
                "status": result.get("type", "unknown"),
                "result": result
            })

            print(f"Case {case_id}: Analysis completed")

        except Exception as e:
            print(f"Error processing case {case_id}: {e}")
            results.append({
                "case_id": case_id,
                "status": "error",
                "error": str(e)
            })

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

    args = parser.parse_args()

    run_memory_agent_on_cases(
        jsonl_path=args.jsonl_file,
        agent_name=args.agent,
        model_name=args.model,
        output_dir=args.output,
        trajectory_log_dir=args.trajectory_dir,
        conversation_log_path=args.conversation_log
    )


if __name__ == "__main__":
    main()
