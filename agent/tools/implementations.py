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


# =============================================================================
# Uncertainty-Aware Diagnosis Tools
# =============================================================================

from .diagnosis_session import append_step, get_accumulated_notes, load_session, get_current_session


@tool(name="diagnosis_step", description="Record diagnostic reasoning and specify your next action. Returns formatted response to output.")
def diagnosis_step(new_information: str, current_uncertainties: str, next_step_action: str) -> str:
    """Record a diagnostic step and get formatted next action for output.

    This tool serves two purposes:
    1. Records: new information, uncertainties, and planned action to session file
    2. Returns: formatted action string to output to AgentClinic

    Args:
        new_information: str
        current_uncertainties: list[str]
        next_step_action: str
    Returns:
        str
    """
    # Get session from context (set by wrapper)
    session_id = get_current_session()
    if not session_id:
        return "Error: No active diagnosis session. Session must be initialized by wrapper."

    # Parse uncertainties from comma-separated string
    if isinstance(current_uncertainties, str):
        uncertainties_list = [u.strip() for u in current_uncertainties.split(";") if u.strip()]
    else:
        uncertainties_list = current_uncertainties

    # Append step to session (records to file)
    session = append_step(
        session_id=session_id,
        new_information=new_information,
        uncertainties=uncertainties_list,
        next_step_action=next_step_action
    )

    # Format the action for AgentClinic output
    return next_step_action


def _get_diagnosis_client():
    """Get OpenAI client for final diagnosis synthesis.

    Uses gpt-5-mini for focused diagnosis generation.
    """
    from openai import OpenAI

    # Try OpenRouter first (for gpt-5-mini access)
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if openrouter_key:
        return OpenAI(
            api_key=openrouter_key,
            base_url="https://openrouter.ai/api/v1"
        )

    # Fallback to OpenAI directly
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        return OpenAI(api_key=openai_key)

    raise ValueError("No API key found for diagnosis synthesis (need OPENROUTER_API_KEY or OPENAI_API_KEY)")


@tool(name="final_diagnosis", description="Submit your final diagnosis. Uses LLM to synthesize all accumulated information into clean diagnosis.")
def final_diagnosis(reason_ready: str) -> str:
    """Submit the final diagnosis for the case.

    This tool:
    1. Collects all accumulated information from diagnostic steps
    2. Uses gpt-5-mini to synthesize a clean final diagnosis
    3. Returns in AgentClinic-compatible format

    Args:
        reason_ready: Why you are confident enough to diagnose now (1-2 sentences)

    Returns:
        AgentClinic-compatible diagnosis string: "DIAGNOSIS READY: [diagnosis]"
    """
    # Get session from context (set by wrapper)
    session_id = get_current_session()
    if not session_id:
        return "Error: No active diagnosis session. Session must be initialized by wrapper."

    # Load session to get all accumulated information
    session = load_session(session_id)
    steps = session.get("steps", [])

    if not steps:
        return "Error: No diagnostic steps recorded. Cannot make diagnosis without information."

    # Extract all new_information from steps
    accumulated_info = []
    for step in steps:
        info = step.get("new_information", "")
        if info:
            accumulated_info.append(info)

    # Build prompt for diagnosis synthesis
    info_text = "\n".join([f"- {info}" for info in accumulated_info])

    synthesis_prompt = f"""You are a medical diagnosis synthesizer. Based on all the information gathered during a clinical evaluation, provide a single, specific final diagnosis.

## Information Gathered:
{info_text}

## Task:
Provide a single, specific diagnosis (1-3 words). Examples:
- "Acute appendicitis"
- "Community-acquired pneumonia"
- "Type 2 diabetes mellitus"

Diagnosis:"""

    # Call LLM for diagnosis synthesis
    try:
        client = _get_diagnosis_client()
        response = client.chat.completions.create(
            model="openai/gpt-5-mini",
            messages=[
                {"role": "system", "content": "You are a medical expert providing concise final diagnoses. Output only the diagnosis name, nothing else."},
                {"role": "user", "content": synthesis_prompt}
            ],
            temperature=0.1,
            max_tokens=1000
        )
        final_diagnosis_text = response.choices[0].message.content.strip()

        # Clean up any extra text
        if "\n" in final_diagnosis_text:
            final_diagnosis_text = final_diagnosis_text.split("\n")[0]

    except Exception as e:
        return f"Error: Failed to synthesize diagnosis: {str(e)}"

    # Record the final diagnosis step
    final_step = {
        "step_number": len(steps) + 1,
        "new_information": f"Final diagnosis reached: {final_diagnosis_text}",
        "current_uncertainties": [],
        "next_step_action": "DIAGNOSIS READY",
        "reason_ready": reason_ready,
        "final_diagnosis": final_diagnosis_text,
        "synthesis_prompt": synthesis_prompt
    }
    session["steps"].append(final_step)
    session["final_diagnosis"] = final_diagnosis_text
    session["current_uncertainties"] = []

    # Save final session state
    from .diagnosis_session import save_session
    save_session(session_id, session)

    # Return AgentClinic-compatible format
    return f"DIAGNOSIS READY: {final_diagnosis_text}"
