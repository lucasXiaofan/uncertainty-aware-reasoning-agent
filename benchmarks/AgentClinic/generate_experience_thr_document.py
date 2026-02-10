#!/usr/bin/env python3
"""Generate diagnostic experiences from documented sessions using experience_generation_agent.

Usage:
    python generate_experience_thr_document.py <session_dir> <result_jsonl> [--workers N]

Example:
    python generate_experience_thr_document.py \
        ../../agent/diagnosis_sessions/valid_agentclinic_experience \
        experiment_highest_transfer_clusters/results/generate_experience_fixed_openai_gpt-5-mini_ua_20260207_113516.jsonl
"""
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed

AGENT_DIR = str(Path(__file__).resolve().parent.parent.parent / "agent")
RECORD_FILE = Path(AGENT_DIR) / "memory" / "experience_generation_record.json"


def _load_record():
    """Load existing experience generation record."""
    if RECORD_FILE.exists():
        with open(RECORD_FILE) as f:
            content = f.read().strip()
            return json.loads(content) if content else {}
    return {}


def _save_record(record):
    """Save experience generation record."""
    RECORD_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(RECORD_FILE, "w") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)


def match_sessions_to_results(session_dir, result_file):
    """Match session files to result entries.

    Strategy 1: Use session_id field from result JSONL (direct match).
    Strategy 2: Fallback to comparing last 2 non-diagnosis doctor actions.
    """
    results = []
    with open(result_file) as f:
        for line in f:
            if line.strip():
                results.append(json.loads(line))

    # Load all sessions
    sessions = {}
    for sf in sorted(Path(session_dir).glob("*.json")):
        with open(sf) as f:
            session = json.load(f)
        sessions[sf.stem] = session

    matches = []
    matched_sessions = set()

    # Strategy 1: Direct session_id match
    for result in results:
        sid = result.get("session_id")
        if sid and sid in sessions:
            matches.append({
                "session_id": sid,
                "session": sessions[sid],
                "result": result,
            })
            matched_sessions.add(sid)

    # Strategy 2: Action fingerprint fallback for results without session_id
    unmatched_results = [r for r in results if r.get("session_id") not in sessions]
    if unmatched_results:
        for sid, session in sessions.items():
            if sid in matched_sessions:
                continue
            steps = session.get("steps", [])
            if len(steps) < 3:
                continue
            actions = [s.get("action", "") for s in steps if s.get("action") != "DIAGNOSIS READY"]
            session_fp = [a[:80] for a in actions[-2:]]

            for result in unmatched_results:
                doctor_turns = [h[8:] for h in result.get("dialogue_history", []) if h.startswith("Doctor: ")]
                non_diag = [d for d in doctor_turns if not d.startswith("DIAGNOSIS READY")]
                result_fp = [a[:80] for a in non_diag[-2:]]

                if session_fp == result_fp:
                    matches.append({
                        "session_id": sid,
                        "session": session,
                        "result": result,
                    })
                    matched_sessions.add(sid)
                    break

    return matches


def run_agent(session_id, session, ground_truth, session_dir, agent_dir):
    """Worker: run experience_generation_agent for one session.

    Returns dict with agent result and collected experience_ids.
    """
    if agent_dir not in sys.path:
        sys.path.insert(0, agent_dir)

    from tools.diagnosis_session import set_current_session
    from tools.implementations import set_experience_session_dir
    from single_agent import SingleAgent

    set_current_session(session_id)
    set_experience_session_dir(session_dir)

    # Build prompt with session steps + ground truth
    steps_text = []
    for s in session.get("steps", []):
        sn = s.get("step_number", "?")
        uncert = s.get("uncertainties", {})
        u_str = ("; ".join(f"{k}: {v}" for k, v in uncert.items())
                 if isinstance(uncert, dict) else str(uncert))
        steps_text.append(
            f"Step {sn}: Info: {s.get('new_information', '')} | "
            f"Uncertainties: {u_str} | Action: {s.get('action', '')} | "
            f"Reason: {s.get('action_reason', '')}"
        )

    pi = ground_truth.get("problem_info", {}).get("OSCE_Examination", {})
    prompt = (
        f"## DIAGNOSTIC SESSION\n"
        f"{chr(10).join(steps_text)}\n\n"
        f"## GROUND TRUTH\n"
        f"Correct Diagnosis: {ground_truth.get('correct_diagnosis', '')}\n"
        f"Objective: {pi.get('Objective_for_Doctor', '')}\n"
        f"Patient: {json.dumps(pi.get('Patient_Actor', {}), indent=2)}\n"
        f"Physical Exam: {json.dumps(pi.get('Physical_Examination_Findings', {}), indent=2)}\n"
        f"Tests: {json.dumps(pi.get('Test_Results', {}), indent=2)}\n\n"
        f"Note: REQUEST TEST covers both physical exams and lab tests in AgentClinic.\n"
        f"Find 3 key steps to improve. Call generate_experience for each, "
        f"then complete_analysis with case_id=\"{session_id}\"."
    )

    agent = SingleAgent("experience_generation_agent")
    result = agent.run(prompt, episode_id=session_id)

    # Extract experience_ids from trajectory tool calls
    experience_ids = []
    for turn in result.get("trajectory", []):
        if turn.get("tool") == "generate_experience" and turn.get("result"):
            try:
                r = json.loads(turn["result"]) if isinstance(turn["result"], str) else turn["result"]
                if isinstance(r, dict) and "experience_id" in r:
                    experience_ids.append(r["experience_id"])
            except (json.JSONDecodeError, TypeError):
                pass

    result["experience_ids"] = experience_ids
    return result


def main():
    parser = argparse.ArgumentParser(description="Generate experiences from documented sessions")
    parser.add_argument("session_dir", help="Directory with session JSON files")
    parser.add_argument("result_file", help="Result JSONL file with ground truth")
    parser.add_argument("--workers", type=int, default=5, help="Parallel workers (default: 5)")
    args = parser.parse_args()

    # Load existing record to skip already-processed cases
    record = _load_record()

    print(f"Matching sessions from {args.session_dir} to {args.result_file}...")
    matches = match_sessions_to_results(args.session_dir, args.result_file)
    print(f"Matched {len(matches)} sessions to results")

    # Filter out already-processed cases
    new_matches = []
    for m in matches:
        key = f"{m['result'].get('dataset', 'unknown')}_{m['result'].get('scenario_id', '?')}"
        if key in record:
            print(f"  Skipping {key} (already processed)")
        else:
            new_matches.append(m)

    if not new_matches:
        print("No new cases to process.")
        return

    print(f"Processing {len(new_matches)} new cases...")
    session_dir = str(Path(args.session_dir).resolve())

    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(run_agent, m["session_id"], m["session"], m["result"],
                        session_dir, AGENT_DIR): m
            for m in new_matches
        }
        for f in as_completed(futures):
            m = futures[f]
            sid = m["session_id"]
            result = m["result"]
            key = f"{result.get('dataset', 'unknown')}_{result.get('scenario_id', '?')}"
            try:
                res = f.result()
                status = "OK" if res.get("type") != "error" else "ERROR"
                exp_ids = res.get("experience_ids", [])
                print(f"[{status}] {sid} ({res.get('turns', '?')} turns, exp_ids={exp_ids})")

                # Record this case with experience IDs
                record[key] = {
                    "dataset": result.get("dataset"),
                    "scenario_id": result.get("scenario_id"),
                    "session_id": sid,
                    "correct_diagnosis": result.get("correct_diagnosis"),
                    "model_correct": result.get("correct"),
                    "experience_ids": exp_ids,
                    "timestamp": datetime.now().isoformat(),
                }
                _save_record(record)
            except Exception as e:
                print(f"[FAIL] {sid}: {e}")

    exp_file = Path(AGENT_DIR) / "memory" / "AgentClinic_experience_v1.json"
    if exp_file.exists():
        with open(exp_file) as f:
            exps = json.load(f)
        print(f"\nTotal experiences generated: {len(exps)}")
    print(f"Record file: {RECORD_FILE}")


if __name__ == "__main__":
    main()
