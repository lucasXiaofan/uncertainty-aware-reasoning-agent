"""Tool implementations for the agent."""
import os
import json
import subprocess
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

from .registry import tool

# Load environment variables from .env file
load_dotenv()

# Memory directory for conversation logs
MEMORY_DIR = Path(__file__).parent.parent / "memory"
MEMORY_DIR.mkdir(exist_ok=True)


@tool(name="bash_command", description="Execute bash commands in a shell")
def bash_command(command: str) -> str:
    """Execute a bash command and return output."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
            executable='/bin/bash'
        )
        output = result.stdout.strip()
        error = result.stderr.strip()

        if result.returncode == 0:
            return output if output else "Command executed successfully (no output)"
        else:
            return f"Error (exit code {result.returncode}): {error or output}"
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 30 seconds"
    except Exception as e:
        return f"Error: {str(e)}"


@tool(name="think", description="Think step by step about the plan to break down the task")
def think(thought: str) -> str:
    """Record a thought during reasoning. Use this to plan your approach."""
    return f"Thought recorded: {thought}"


@tool(name="brave_search", description="Search the web using Brave Search API")
def brave_search(query: str, count: int = 10) -> str:
    """Search the web for information using Brave Search API.

    Args:
        query: The search query string
        count: Number of results to return (max 20)

    Returns:
        Formatted search results or error message
    """
    try:
        api_key = os.getenv("BRAVE_API_KEY")
        if not api_key:
            return "Error: BRAVE_API_KEY not found in environment variables"

        # Brave Search API endpoint
        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": api_key
        }
        params = {
            "q": query,
            "count": min(count, 20)  # Max 20 results
        }

        response = requests.get(url, headers=headers, params=params, timeout=10)

        if response.status_code == 200:
            data = response.json()
            results = []

            # Extract web results
            if "web" in data and "results" in data["web"]:
                for idx, result in enumerate(data["web"]["results"][:count], 1):
                    results.append({
                        "position": idx,
                        "title": result.get("title", ""),
                        "url": result.get("url", ""),
                        "description": result.get("description", "")
                    })

            if results:
                formatted_results = "\n\n".join([
                    f"{r['position']}. {r['title']}\n   URL: {r['url']}\n   {r['description']}"
                    for r in results
                ])
                return f"Search Results for '{query}':\n\n{formatted_results}"
            else:
                return f"No results found for query: {query}"
        else:
            return f"Error: Brave API returned status code {response.status_code}\n{response.text}"

    except requests.Timeout:
        return "Error: Search request timed out"
    except requests.RequestException as e:
        return f"Error: Network request failed - {str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"


@tool(name="final_answer", description="Submit your final answer choice for a multiple choice question. Use this when you are ready to provide your diagnosis.")
def final_answer(answer: str, reasoning: str) -> str:
    """Submit the final answer for a multiple choice diagnostic question.

    Args:
        answer: The answer choice letter (A, B, C, D, or E)
        reasoning: Brief explanation for why this answer was chosen

    Returns:
        Formatted answer response
    """
    # Normalize answer to uppercase single letter
    answer = answer.strip().upper()
    if len(answer) > 1:
        answer = answer[0]

    if answer not in ['A', 'B', 'C', 'D', 'E']:
        return f"Error: Invalid answer '{answer}'. Must be A, B, C, D, or E."

    return json.dumps({
        "answer": answer,
        "reasoning": reasoning
    })


@tool(name="final_result", description="Format and present the final report to the user. Use this when you have gathered enough information to provide a complete answer.")
def final_result(summary: str, details: str, sources: str = "") -> str:
    """Format the agent's final report to the user.

    Args:
        summary: A brief summary of the findings (1-2 sentences)
        details: Detailed explanation or answer
        sources: Optional sources or references used

    Returns:
        Formatted final report
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    report = f"""
# FINAL REPORT
Generated: {timestamp}

## SUMMARY
{summary}

## DETAILS
{details}
"""

    if sources:
        report += f"""
## SOURCES
{sources}
"""

    return report





# Experience memory file path
EXPERIENCE_FILE = Path(__file__).parent.parent / "memory" / "diagnostic_experiences.json"
EXPERIENCE_FILE.parent.mkdir(parents=True, exist_ok=True)

# Lock file for thread-safe concurrent access
EXPERIENCE_LOCK_FILE = EXPERIENCE_FILE.with_suffix(".lock")

import fcntl
import time


def _acquire_file_lock(lock_file: Path, timeout: float = 30.0) -> int:
    """Acquire an exclusive file lock for thread-safe file access.

    Args:
        lock_file: Path to the lock file
        timeout: Maximum time to wait for lock (seconds)

    Returns:
        File descriptor of the lock file

    Raises:
        TimeoutError: If lock cannot be acquired within timeout
    """
    lock_fd = os.open(str(lock_file), os.O_CREAT | os.O_RDWR)
    start_time = time.time()

    while True:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return lock_fd
        except (IOError, OSError):
            if time.time() - start_time > timeout:
                os.close(lock_fd)
                raise TimeoutError(f"Could not acquire lock on {lock_file} within {timeout}s")
            time.sleep(0.1)


def _release_file_lock(lock_fd: int):
    """Release a file lock.

    Args:
        lock_fd: File descriptor of the lock file
    """
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
    finally:
        os.close(lock_fd)


@tool(name="save_experience", description="Save a learning experience extracted from a failed diagnosis case. Each call immediately saves to file. Thread-safe for concurrent access.")
def save_experience(case_id: str, situation: str, uncertainty: str, action: str, rationale: str) -> str:
    """Save a learning experience from a failed diagnosis case directly to JSON file.

    Args:
        case_id: Identifier for the case (e.g., 'MedQA_Ext_2')
        situation: 1-2 sentences describing the clinical context - age, sex, chief complaint,
                   key findings known at this point, what tests/questions have been done.
                   Example: "47-year-old female with 3 weeks of fatigue, fever, RUQ pain.
                   Vitals show fever 38.1°C, liver tender and enlarged on exam."
        uncertainty: 2-4 diseases being considered at this moment (comma-separated or JSON array).
                     Example: "viral epatitis, drug induced hepatitis, acute cholecystitis"
        action: The specific action to take. Must start with type:
                "ASK PATIENT: [specific question]" or
                "PHYSICAL EXAM: [specific exam]" or
                "REQUEST TEST: [test name]" or
                "REQUEST IMAGE: [imaging study]"
        rationale: 1-2 sentences explaining WHY this action helps narrow the differential.
                   Example: "Asking about pleuritic chest pain immediately narrows differential
                   from cardiac causes to pulmonary/pleural causes."

    Returns:
        Confirmation message with file path
    """
    # Acquire exclusive lock for thread-safe access
    lock_fd = _acquire_file_lock(EXPERIENCE_LOCK_FILE)

    try:
        # Load existing experiences
        experiences = []
        if EXPERIENCE_FILE.exists():
            try:
                with open(EXPERIENCE_FILE, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        experiences = json.loads(content)
            except (json.JSONDecodeError, Exception):
                experiences = []

        # Parse uncertainty into list if it's a string
        if isinstance(uncertainty, str):
            # Handle both comma-separated and JSON array formats
            uncertainty = uncertainty.strip()
            if uncertainty.startswith("["):
                try:
                    uncertainty_list = json.loads(uncertainty)
                except json.JSONDecodeError:
                    uncertainty_list = [u.strip() for u in uncertainty.split(",")]
            else:
                uncertainty_list = [u.strip() for u in uncertainty.split(",")]
        else:
            uncertainty_list = uncertainty

        # Create new experience entry with new format
        experience = {
            "id": len(experiences) + 1,
            "case_id": case_id,
            "situation": situation,
            "uncertainty": uncertainty_list,
            "action": action,
            "rationale": rationale,
            "timestamp": datetime.now().isoformat()
        }

        experiences.append(experience)

        # Save immediately to file
        with open(EXPERIENCE_FILE, "w", encoding="utf-8") as f:
            json.dump(experiences, f, indent=2, ensure_ascii=False)

        return f"Experience #{experience['id']} saved to {EXPERIENCE_FILE}"

    finally:
        # Always release the lock
        _release_file_lock(lock_fd)


@tool(name="complete_analysis", description="Signal that you have finished extracting learning experiences from the case.")
def complete_analysis(case_id: str, summary: str) -> str:
    """Complete the analysis for a case.

    Args:
        case_id: Identifier for the case
        summary: Brief summary of the key learning points extracted

    Returns:
        Final status message
    """
    return json.dumps({
        "status": "completed",
        "case_id": case_id,
        "summary": summary,
        "experience_file": str(EXPERIENCE_FILE)
    })


@tool(name="select_experiences", description="Select relevant diagnostic experiences to provide to the doctor. Pick IDs that DIRECTLY match current situation, or 'none' if no match.")
def select_experiences(experience_ids: str, reasoning: str) -> str:
    """Select experiences to provide to doctor.

    Args:
        experience_ids: Comma-separated IDs (e.g., '3, 7') or 'none'
        reasoning: Brief explanation of selection

    Returns:
        JSON with selected experiences
    """
    from .bm25_search import BM25Search

    if experience_ids.lower().strip() == "none" or not experience_ids.strip():
        return json.dumps({
            "status": "no_relevant_experiences",
            "selected": [],
            "reasoning": reasoning,
            "context_for_doctor": ""
        })

    bm25 = BM25Search(str(EXPERIENCE_FILE))
    selected = []
    context_parts = []

    for part in experience_ids.replace(",", " ").split():
        try:
            exp_id = int(part.strip())
            exp = bm25.get_by_id(exp_id)
            if exp and len(selected) < 2:
                # Support both old format (observation/suggestion) and new format (situation/action/rationale)
                action = exp.get("action", exp.get("suggestion", ""))
                situation = exp.get("situation", exp.get("observation", ""))
                rationale = exp.get("rationale", "")

                selected.append({"id": exp_id, "action": action})

                # Build context for doctor with new format
                context = f"[Experience #{exp_id}]\nSituation: {situation}\nAction: {action}"
                if rationale:
                    context += f"\nRationale: {rationale}"
                context_parts.append(context)
        except ValueError:
            continue

    return json.dumps({
        "status": "experiences_selected",
        "selected": selected,
        "reasoning": reasoning,
        "context_for_doctor": "\n\n".join(context_parts)
    })
