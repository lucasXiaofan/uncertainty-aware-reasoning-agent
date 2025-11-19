import argparse
import sys
import subprocess
from datetime import datetime
from pathlib import Path


def write_subset(src_path: Path, dest_path: Path, limit: int) -> int:
    """Copy the first `limit` lines from src_path into dest_path."""
    count = 0
    with src_path.open("r", encoding="utf-8") as src, dest_path.open("w", encoding="utf-8") as dst:
        for line in src:
            if not line.strip():
                continue
            dst.write(line if line.endswith("\n") else f"{line}\n")
            count += 1
            if count >= limit:
                break
    return count


def main():
    parser = argparse.ArgumentParser(description="Run MediQ benchmark using OpenAI-compatible APIs.")
    parser.add_argument("--num_patients", type=int, default=14, help="How many patients to evaluate.")
    parser.add_argument(
        "--model_name",
        type=str,
        default="deepseek/deepseek-chat-v3",
        help="Model identifier (e.g., 'deepseek/deepseek-chat-v3' for OpenRouter, 'gpt-4' for OpenAI).",
    )
    parser.add_argument(
        "--api_account",
        type=str,
        default="openrouter",
        help="API provider account name (openrouter, deepseek, openai, etc.).",
    )
    parser.add_argument(
        "--api_base_url",
        type=str,
        default=None,
        help="Custom API base URL (optional, will use default for known providers).",
    )
    parser.add_argument(
        "--data_dir",
        type=Path,
        default=Path("data"),
        help="Directory containing the dev jsonl file (relative to mediQ dir).",
    )
    parser.add_argument("--dev_filename", type=str, default="all_dev_good.jsonl", help="Original dev split filename.")
    parser.add_argument("--output_dir", type=Path, default=Path("outputs"), help="Directory for benchmark outputs.")
    parser.add_argument("--log_dir", type=Path, default=Path("logs"), help="Directory for logs.")
    parser.add_argument(
        "--expert_class",
        type=str,
        default="UncertaintyAwareExpert", #"ScaleExpert", UncertaintyAwareExpert
        help="Expert class to use (RareMethod1LucasVer, ScaleExpert, etc.).",
    )
    parser.add_argument(
        "--max_questions",
        type=int,
        default=7,
        help="Maximum number of questions the expert can ask.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.6,
        help="Sampling temperature.",
    )
    parser.add_argument(
        "--max_tokens",
        type=int,
        default=1500,
        help="Maximum tokens to generate.",
    )
    parser.add_argument(
        "--top_p",
        type=float,
        default=0.9,
        help="Top-p sampling value.",
    )
    parser.add_argument(
        "--python_exec",
        type=str,
        default=sys.executable,
        help="Python executable to invoke mediQ_benchmark (defaults to current env).",
    )
    args = parser.parse_args()

    # Determine paths
    script_dir = Path(__file__).resolve().parent
    mediq_src = script_dir / "src"
    data_dir = args.data_dir if args.data_dir.is_absolute() else script_dir / args.data_dir
    dev_filename = Path(args.dev_filename)
    data_path = dev_filename if dev_filename.is_absolute() else data_dir / dev_filename

    if not data_path.exists():
        raise FileNotFoundError(f"Cannot find data file: {data_path}")

    # Create subset of data
    subset_name = data_path.stem + f"_top{args.num_patients}" + data_path.suffix
    subset_path = data_path.parent / subset_name
    subset_count = write_subset(data_path, subset_path, args.num_patients)
    if subset_count < args.num_patients:
        raise ValueError(f"Requested {args.num_patients} patients but dataset only had {subset_count}.")

    print(f"Created subset with {subset_count} patients: {subset_path}")

    # Create output directories with dedicated folder for this run
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_suffix = args.model_name.replace("/", "_").replace(":", "_")

    # Create dedicated run folder
    run_folder = args.output_dir / f"{args.expert_class}_{model_suffix}_{timestamp}"
    run_folder.mkdir(parents=True, exist_ok=True)
    args.log_dir.mkdir(parents=True, exist_ok=True)

    # Determine output file names
    output_file = run_folder / "results.jsonl"
    summary_file = run_folder / "summary.json"
    log_file = args.log_dir / f"mediq_{model_suffix}_{timestamp}.log"
    history_log = args.log_dir / f"mediq_{model_suffix}_history_{timestamp}.log"
    detail_log = args.log_dir / f"mediq_{model_suffix}_detail_{timestamp}.log"
    message_log = args.log_dir / f"mediq_{model_suffix}_messages_{timestamp}.log"

    # Build command to run MediQ benchmark
    benchmark_data_dir = subset_path.parent
    cmd = [
        args.python_exec,
        str(mediq_src / "mediQ_benchmark.py"),
        "--expert_module",
        "expert_openai",
        "--expert_class",
        args.expert_class,
        "--expert_model",
        args.model_name,
        "--expert_model_question_generator",
        args.model_name,
        "--patient_module",
        "patient_openai",
        "--patient_class",
        "InstructPatient",
        "--patient_model",
        args.model_name,
        "--data_dir",
        str(benchmark_data_dir),
        "--dev_filename",
        "/Users/xiaofanlu/Documents/github_repos/uncertainty-aware-reasoning-agent/question_quality_comparison/context_gap_analysis/success_in_full_fail_in_initial_mediq_top14.jsonl",
        # subset_path.name,
        "--output_filename",
        str(output_file),
        "--log_filename",
        str(log_file),
        "--history_log_filename",
        str(history_log),
        "--detail_log_filename",
        str(detail_log),
        "--message_log_filename",
        str(message_log),
        "--max_questions",
        str(args.max_questions),
        "--temperature",
        str(args.temperature),
        "--max_tokens",
        str(args.max_tokens),
        "--top_p",
        str(args.top_p),
        "--self_consistency",
        "1",
        "--abstain_threshold",
        "3",
        "--use_api",
        args.api_account,  # Use the new helper_openai.py (openrouter, deepseek, openai)
        "--api_account",
        args.api_account,
    ]

    # Add optional base URL if provided
    if args.api_base_url:
        cmd.extend(["--api_base_url", args.api_base_url])

    print("\n" + "="*80)
    print("MediQ Benchmark Configuration")
    print("="*80)
    print(f"Model: {args.model_name}")
    print(f"API Account: {args.api_account}")
    print(f"API Base URL: {args.api_base_url or 'Default for provider'}")
    print(f"Patients: {args.num_patients}")
    print(f"Expert Class: {args.expert_class}")
    print(f"Max Questions: {args.max_questions}")
    print(f"Temperature: {args.temperature}")
    print(f"Max Tokens: {args.max_tokens}")
    print(f"Output Folder: {run_folder}")
    print("="*80 + "\n")

    print("Running command:")
    print(" ".join(cmd))
    print("\n")

    # Track overall runtime
    import time
    start_time = time.time()
    subprocess.run(cmd, check=True)
    total_runtime = time.time() - start_time

    # Calculate aggregate statistics from output file
    import json
    total_input_tokens = 0
    total_output_tokens = 0
    num_samples = 0
    correct_count = 0
    incorrect_patients = []
    correct_patients = []
    patient_details = []

    if output_file.exists():
        with output_file.open('r') as f:
            for line in f:
                result = json.loads(line)
                num_samples += 1
                patient_id = result.get("id")
                is_correct = result["interactive_system"]["correct"]
                letter_choice = result["interactive_system"]["letter_choice"]
                correct_answer = result["info"]["correct_answer_idx"]
                num_questions = result["interactive_system"]["num_questions"]

                if is_correct:
                    correct_count += 1
                    correct_patients.append(patient_id)
                else:
                    incorrect_patients.append(patient_id)

                # Track patient details
                patient_info = {
                    "id": patient_id,
                    "correct": is_correct,
                    "predicted": letter_choice,
                    "actual": correct_answer,
                    "num_questions": num_questions
                }
                patient_details.append(patient_info)

                # Sum up usage from all intermediate steps
                if "interactive_system" in result and "temp_additional_info" in result["interactive_system"]:
                    for info in result["interactive_system"]["temp_additional_info"]:
                        if "usage" in info:
                            total_input_tokens += info["usage"].get("input_tokens", 0)
                            total_output_tokens += info["usage"].get("output_tokens", 0)

    # Calculate accuracy
    accuracy = correct_count / num_samples if num_samples > 0 else 0.0

    # Create summary
    summary = {
        "run_info": {
            "timestamp": timestamp,
            "expert_class": args.expert_class,
            "model": args.model_name,
            "num_patients": num_samples,
            "max_questions": args.max_questions,
        },
        "performance": {
            "accuracy": accuracy,
            "correct_count": correct_count,
            "incorrect_count": len(incorrect_patients),
            "correct_patients": correct_patients,
            "incorrect_patients": incorrect_patients,
        },
        "resources": {
            "total_runtime_seconds": total_runtime,
            "total_runtime_minutes": total_runtime / 60,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_tokens": total_input_tokens + total_output_tokens,
            "avg_runtime_per_sample": total_runtime / num_samples if num_samples > 0 else 0,
            "avg_tokens_per_sample": (total_input_tokens + total_output_tokens) / num_samples if num_samples > 0 else 0,
        },
        "patient_details": patient_details
    }

    # Save summary to file
    with summary_file.open('w') as f:
        json.dump(summary, f, indent=2)

    print("\n" + "="*80)
    print("Run complete!")
    print("="*80)
    print(f"Results folder: {run_folder}")
    print(f"  - results.jsonl: Detailed results")
    print(f"  - summary.json: Summary statistics")
    print(f"Logs stored in: {args.log_dir}")
    print(f"\nPerformance:")
    print(f"  Accuracy: {correct_count}/{num_samples} = {accuracy*100:.1f}%")
    print(f"  Correct patients: {correct_patients}")
    print(f"  Incorrect patients: {incorrect_patients}")
    print(f"\nResources:")
    print(f"  Total Runtime: {total_runtime:.2f}s ({total_runtime/60:.2f} minutes)")
    print(f"  Total Input Tokens: {total_input_tokens:,}")
    print(f"  Total Output Tokens: {total_output_tokens:,}")
    print(f"  Total Tokens: {total_input_tokens + total_output_tokens:,}")
    if num_samples > 0:
        print(f"  Avg Runtime per Sample: {total_runtime/num_samples:.2f}s")
        print(f"  Avg Tokens per Sample: {(total_input_tokens + total_output_tokens)/num_samples:.0f}")
    print("="*80)


if __name__ == "__main__":
    main()
