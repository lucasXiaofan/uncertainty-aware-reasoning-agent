import os
import json
import subprocess
from datetime import datetime
from pathlib import Path
def save_conversation(user_query: str, final_response: str, image_path: str = None, log_file_path: str = None) -> None:
    """Save a conversation to the memory log.

    Args:
        user_query: The user's original query
        final_response: The agent's final response
        image_path: Optional path to image used in conversation
        log_file_path: Optional custom path for the conversation log file
    """
    log_file = Path(log_file_path) if log_file_path else MEMORY_DIR / "conversation_log.json"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Load existing conversations
    conversations = []
    if log_file.exists():
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    conversations = json.loads(content)
        except (json.JSONDecodeError, Exception):
            conversations = []

    # Add new conversation
    conversation = {
        "id": len(conversations) + 1,
        "timestamp": datetime.now().isoformat(),
        "user_query": user_query,
        "image_path": image_path,
        "final_response": final_response
    }
    conversations.append(conversation)

    # Save back to file
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(conversations, f, indent=2, ensure_ascii=False)


def load_recent_conversations(limit: int = 5, log_file_path: str = None) -> list[dict]:
    """Load the most recent conversations from memory.

    Args:
        limit: Maximum number of recent conversations to load
        log_file_path: Optional custom path for the conversation log file

    Returns:
        List of recent conversation dictionaries
    """
    log_file = Path(log_file_path) if log_file_path else MEMORY_DIR / "conversation_log.json"

    if not log_file.exists():
        return []

    try:
        with open(log_file, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return []
            conversations = json.loads(content)
    except (json.JSONDecodeError, Exception):
        return []

    # Return most recent conversations
    return conversations[-limit:] if conversations else []