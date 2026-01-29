"""Memory Retrieval - simple function to retrieve relevant experiences."""
import json
from pathlib import Path
from typing import List, Dict

from tools.bm25_search import BM25Search, SearchSessionManager
from single_agent import SingleAgent

# Default paths
DEFAULT_EXPERIENCE_FILE = Path(__file__).parent / "memory" / "diagnostic_experiences.json"

# Global session manager
_session_managers: Dict[str, SearchSessionManager] = {}


def retrieve_relevant_experiences(
    conversation_history: List[Dict[str, str]],
    session_id: str,
    experience_file: str = None
) -> str:
    """Retrieve relevant diagnostic experiences for a conversation.

    Args:
        conversation_history: List of {role: 'doctor'|'patient'|'measurement', content: str}
        session_id: Unique session ID for this conversation
        experience_file: Optional path to experiences JSON file

    Returns:
        Formatted experiences string for doctor, or empty string if none relevant
    """
    exp_file = str(experience_file) if experience_file else str(DEFAULT_EXPERIENCE_FILE)

    # Get or create session manager
    if session_id not in _session_managers:
        bm25 = BM25Search(exp_file, search_field="observation", output_field="observation", id_field="id")
        _session_managers[session_id] = SearchSessionManager(bm25, max_results=30)
        _session_managers[session_id].create_session(session_id)

    manager = _session_managers[session_id]

    # Step 1: Auto-search with patient and measurement content
    for turn in conversation_history:
        role = turn.get("role", "").lower()
        content = turn.get("content", "")
        if role in ["patient", "measurement"] and len(content) > 10:
            manager.search_and_add(session_id, content, top_k=5)

    # Step 2: Get all retrieved experiences
    experiences = manager.get_results(session_id)
    if not experiences:
        return ""

    # Step 3: Format conversation and experiences for agent
    conv_text = "\n".join([f"{t['role'].capitalize()}: {t['content']}" for t in conversation_history])
    exp_text = "\n".join([f"ID: {e['id']} | Observation: {e['observation']}" for e in experiences])

    prompt = f"""## Conversation History:
{conv_text}

## Retrieved Experiences (id, observation):
{exp_text}"""
    # Step 4: Run memory_retrieval_agent
    agent = SingleAgent("memory_retrieval_agent")
    result = agent.run(prompt, episode_id=f"memory_{session_id}")

    # Step 5: Extract context_for_doctor from result
    if result and "result" in result:
        try:
            data = json.loads(result["result"]) if isinstance(result["result"], str) else result["result"]
            return data.get("context_for_doctor", "")
        except (json.JSONDecodeError, TypeError):
            pass

    return ""


def clear_session(session_id: str) -> None:
    """Clear a session's search results."""
    if session_id in _session_managers:
        _session_managers[session_id].clear_session(session_id)
