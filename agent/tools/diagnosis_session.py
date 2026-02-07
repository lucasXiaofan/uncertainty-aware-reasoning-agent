"""Session management module for uncertainty-aware diagnosis tracking.

Provides file-based storage with locking for parallel patient sessions.
Session context is managed automatically - wrapper sets current session,
tools use it without explicit session_id parameter.
"""
import os
import json
import fcntl
import time
from pathlib import Path
from typing import Dict, List, Optional
from threading import local

# Session storage directory
SESSIONS_DIR = Path(__file__).parent.parent / "diagnosis_sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

# Thread-local storage for current session context
_context = local()


def set_current_session(session_id: str):
    """Set the current session ID for this thread.

    Called by the wrapper before agent inference.
    """
    _context.session_id = session_id


def get_current_session() -> Optional[str]:
    """Get the current session ID for this thread.

    Returns None if no session is active.
    """
    return getattr(_context, 'session_id', None)


def _get_session_path(session_id: str) -> Path:
    """Get the file path for a session."""
    # Sanitize session_id to prevent path traversal
    safe_id = "".join(c for c in session_id if c.isalnum() or c in "_-")
    return SESSIONS_DIR / f"{safe_id}.json"


def _get_lock_path(session_id: str) -> Path:
    """Get the lock file path for a session."""
    return _get_session_path(session_id).with_suffix(".lock")


def _acquire_lock(session_id: str, timeout: float = 30.0) -> int:
    """Acquire an exclusive lock for thread-safe session access.

    Args:
        session_id: The session identifier
        timeout: Maximum time to wait for lock (seconds)

    Returns:
        File descriptor of the lock file

    Raises:
        TimeoutError: If lock cannot be acquired within timeout
    """
    lock_path = _get_lock_path(session_id)
    lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR)
    start_time = time.time()

    while True:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return lock_fd
        except (IOError, OSError):
            if time.time() - start_time > timeout:
                os.close(lock_fd)
                raise TimeoutError(f"Could not acquire lock for session {session_id} within {timeout}s")
            time.sleep(0.1)


def _release_lock(lock_fd: int):
    """Release a file lock."""
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
    finally:
        os.close(lock_fd)


def load_session(session_id: str) -> Dict:
    """Load a session from file.

    Args:
        session_id: The session identifier

    Returns:
        Session data dict with keys: session_id, steps, accumulated_notes, current_uncertainties
    """
    session_path = _get_session_path(session_id)

    if session_path.exists():
        lock_fd = _acquire_lock(session_id)
        try:
            with open(session_path, "r", encoding="utf-8") as f:
                return json.load(f)
        finally:
            _release_lock(lock_fd)

    # Return new empty session structure
    return {
        "session_id": session_id,
        "steps": [],
        "accumulated_notes": "",
        "current_uncertainties": []
    }


def save_session(session_id: str, data: Dict) -> None:
    """Save session data to file.

    Args:
        session_id: The session identifier
        data: Session data to save
    """
    session_path = _get_session_path(session_id)
    lock_fd = _acquire_lock(session_id)

    try:
        with open(session_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    finally:
        _release_lock(lock_fd)


def append_step(session_id: str, new_information: str, uncertainties: List[str],
                next_step_action: str) -> Dict:
    """Append a diagnostic step to the session.

    Args:
        session_id: The session identifier
        new_information: New information learned in this step
        uncertainties: Current list of differential diagnoses being considered
        next_step_action: The next action to take (format: "ASK PATIENT: ...",
                         "REQUEST TEST: ...", or "DIAGNOSIS READY")

    Returns:
        Updated session data with accumulated_notes
    """
    lock_fd = _acquire_lock(session_id)

    try:
        session_path = _get_session_path(session_id)

        # Load existing or create new
        if session_path.exists():
            with open(session_path, "r", encoding="utf-8") as f:
                session = json.load(f)
        else:
            session = {
                "session_id": session_id,
                "steps": [],
                "accumulated_notes": "",
                "current_uncertainties": []
            }

        # Create new step
        step_number = len(session["steps"]) + 1
        new_step = {
            "step_number": step_number,
            "new_information": new_information,
            "current_uncertainties": uncertainties,
            "next_step_action": next_step_action
        }
        session["steps"].append(new_step)

        # Update accumulated notes (append-only)
        step_note = f"[Step {step_number}]\nNew Info: {new_information}\nDifferential: {', '.join(uncertainties)}\nNext: {next_step_action}"
        if session["accumulated_notes"]:
            session["accumulated_notes"] += f"\n\n{step_note}"
        else:
            session["accumulated_notes"] = step_note

        # Update current uncertainties
        session["current_uncertainties"] = uncertainties

        # Save
        with open(session_path, "w", encoding="utf-8") as f:
            json.dump(session, f, indent=2, ensure_ascii=False)

        return session

    finally:
        _release_lock(lock_fd)


def get_accumulated_notes(session_id: str) -> str:
    """Get the accumulated diagnostic notes for a session.

    Args:
        session_id: The session identifier

    Returns:
        String containing all accumulated notes from diagnostic steps
    """
    session = load_session(session_id)
    return session.get("accumulated_notes", "")


def get_all_new_information(session_id: str) -> List[str]:
    """Get all new_information entries from a session.

    Args:
        session_id: The session identifier

    Returns:
        List of all new_information strings from each step
    """
    session = load_session(session_id)
    steps = session.get("steps", [])
    return [step.get("new_information", "") for step in steps if step.get("new_information")]


def clear_session(session_id: str) -> bool:
    """Clear/delete a session file.

    Args:
        session_id: The session identifier

    Returns:
        True if session was cleared, False if it didn't exist
    """
    session_path = _get_session_path(session_id)
    lock_path = _get_lock_path(session_id)

    cleared = False
    if session_path.exists():
        lock_fd = _acquire_lock(session_id)
        try:
            session_path.unlink()
            cleared = True
        finally:
            _release_lock(lock_fd)

    # Clean up lock file
    if lock_path.exists():
        try:
            lock_path.unlink()
        except OSError:
            pass  # Ignore if lock file is still in use

    return cleared

if __name__ == "__main__":
    print(get_all_new_information("scenario_4457819792_1769808836"))
