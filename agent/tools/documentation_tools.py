"""Documentation-focused diagnostic tools with structured information tracking.

This module provides enhanced documentation tools that:
1. Record diagnostic steps with structured fields (info, uncertainties, relevance, action, reason)
2. Query past diagnostic experiences via BM25 search
3. Synthesize final diagnosis from clean accumulated information
"""
import os
import re
import json
import math
from pathlib import Path
from typing import Dict, List
from collections import defaultdict
from .registry import tool
from .diagnosis_session import (
    get_current_session,
    load_session,
    save_session,
    _get_session_path
)

EXPERIENCE_V1_FILE = Path(__file__).parent.parent / "memory" / "AgentClinic_experience_v1.json"


@tool(
    name="query_medical_guidelines",
    description="Search past diagnostic experiences for relevant guidelines. Returns top 5 matches based on clinical context and differential diagnoses."
)
def query_medical_guidelines(new_information: str, uncertainties: str) -> str:
    """Search past experiences using BM25 over context and uncertainties fields.

    Args:
        new_information: Current clinical findings (e.g., "25-year-old male with jaundice and ALT 2000")
        uncertainties: Current differential diagnoses ("disease1: reason1; disease2: reason2")

    Returns:
        Formatted top 5 matching experiences with full details, or message if none found.
    """
    # return "No relevant guidelines found."

    if not EXPERIENCE_V1_FILE.exists():
        return "No medical guidelines available."
    with open(EXPERIENCE_V1_FILE, "r", encoding="utf-8") as f:
        experiences = json.load(f)
    if not experiences:
        return "No medical guidelines available."

    # Build query from both inputs
    query = f"{new_information} {uncertainties}"
    query_tokens = re.findall(r'\b[a-z0-9]+\b', query.lower())
    if not query_tokens:
        return "No relevant guidelines found."

    # Tokenize each experience's context + uncertainties as combined index
    doc_tokens = []
    for exp in experiences:
        uncert = exp.get("uncertainties", {})
        uncert_text = " ".join(f"{k} {v}" for k, v in uncert.items()) if isinstance(uncert, dict) else str(uncert)
        combined = f"{exp.get('context', '')} {uncert_text}"
        doc_tokens.append(re.findall(r'\b[a-z0-9]+\b', combined.lower()))

    # BM25 scoring
    N = len(doc_tokens)
    avg_dl = sum(len(d) for d in doc_tokens) / N
    k1, b = 1.5, 0.75

    df = defaultdict(int)
    for d in doc_tokens:
        for term in set(d):
            df[term] += 1

    scores = []
    for i, d in enumerate(doc_tokens):
        tf = defaultdict(int)
        for t in d:
            tf[t] += 1
        score = 0.0
        dl = len(d)
        for t in query_tokens:
            if t not in tf:
                continue
            idf = math.log((N - df[t] + 0.5) / (df[t] + 0.5) + 1)
            score += idf * (tf[t] * (k1 + 1)) / (tf[t] + k1 * (1 - b + b * dl / avg_dl))
        if score > 0:
            scores.append((i, score))

    scores.sort(key=lambda x: x[1], reverse=True)
    top5 = scores[:5]

    if not top5:
        return "No relevant guidelines found."

    results = []
    for idx, score in top5:
        exp = experiences[idx]
        uncert = exp.get("uncertainties", {})
        u_str = "; ".join(f"{k}: {v}" for k, v in uncert.items()) if isinstance(uncert, dict) else str(uncert)
        results.append(
            f"[Experience #{exp.get('id', '?')}]\n"
            f"Context: {exp.get('context', '')}\n"
            f"Uncertainties: {u_str}\n"
            f"Action: {exp.get('action', '')}\n"
            f"Rationale: {exp.get('action_reason', '')}"
        )

    return "\n\n".join(results)


@tool(
    name="document_step",
    description="Document diagnostic step with structured information: new findings, uncertainties with reasoning, guideline relevance, next action, and action rationale"
)
def document_step(
    new_information: str,
    uncertainties: str,
    reference_relevance: str,
    action: str,
    reason: str
) -> str:
    """Document a diagnostic step with comprehensive structured fields.

    This tool records:
    1. New information discovered (clean atomic facts)
    2. Current differential diagnoses with reasoning
    3. Medical guideline relevance assessment
    4. Next action to take
    5. Rationale for why this action helps differentiate

    Args:
        new_information: New findings from patient/test (atomic fact)
        uncertainties: Differential diagnoses in format "disease1: reasoning1; disease2: reasoning2; ..."
        reference_relevance: Assessment of medical guideline relevance (or "No relevant information retrieved")
        action: Next action to take (e.g., "ASK PATIENT: ...", "REQUEST TEST: ...")
        reason: Why this action helps differentiate between uncertainties

    Returns:
        Formatted action string to output (what to say/request next)
    """
    # Get session from context
    session_id = get_current_session()
    if not session_id:
        return "Error: No active diagnosis session. Session must be initialized by wrapper."

    # Parse uncertainties from semicolon-separated "name: reason" format
    uncertainties_dict = {}
    if uncertainties:
        for item in uncertainties.split(";"):
            item = item.strip()
            if ":" in item:
                disease, reasoning = item.split(":", 1)
                uncertainties_dict[disease.strip()] = reasoning.strip()
            elif item:  # Handle case without reasoning
                uncertainties_dict[item] = "under consideration"

    # Load or create session
    session = load_session(session_id)
    if "all_information" not in session:
        session["all_information"] = []

    # Create new step with structured documentation
    step_number = len(session.get("steps", [])) + 1
    new_step = {
        "step_number": step_number,
        "new_information": new_information,
        "uncertainties": uncertainties_dict,
        "reference_relevance": reference_relevance,
        "action": action,
        "action_reason": reason
    }
    session.setdefault("steps", []).append(new_step)

    # Update clean information list (for final diagnosis)
    if new_information:
        session["all_information"].append(new_information)

    # Update current uncertainties
    session["current_uncertainties"] = uncertainties_dict

    # Save session
    save_session(session_id, session)

    # Return the formatted action for output
    return action


@tool(
    name="final_diagnosis_documented",
    description="Synthesize final diagnosis from all documented clean information using LLM"
)
def final_diagnosis_documented(reason: str) -> str:
    """Submit final diagnosis by synthesizing all accumulated clean information.

    This tool:
    1. Loads all new_information from documented steps (clean atomic facts)
    2. Uses LLM (gpt-5-mini) to synthesize final diagnosis
    3. Records final diagnosis step in documentation
    4. Returns AgentClinic-compatible diagnosis format

    Args:
        reason: Why ready for diagnosis OR what would be clarified with more rounds
               Examples:
               - "All differential diagnoses resolved - vital signs and symptoms clearly indicate X"
               - "Maximum rounds used - would clarify serum calcium and PTH levels if given more chances"

    Returns:
        "DIAGNOSIS READY: [diagnosis]" in AgentClinic format
    """
    # Get session from context
    session_id = get_current_session()
    if not session_id:
        return "Error: No active diagnosis session. Session must be initialized by wrapper."

    # Load session to get all documented information
    session = load_session(session_id)

    # Extract clean information list
    all_information = session.get("all_information", [])

    if not all_information:
        # Fallback: extract from steps if all_information not populated
        steps = session.get("steps", [])
        all_information = [
            step.get("new_information", "")
            for step in steps
            if step.get("new_information")
        ]

    if not all_information:
        return "Error: No information documented. Cannot make diagnosis without data."

    # Build synthesis prompt with clean information
    info_text = "\n".join([f"- {info}" for info in all_information])

    synthesis_prompt = f"""You are a medical diagnosis synthesizer. Based on all the information gathered during a clinical evaluation, provide a single, specific final diagnosis.

## Information Gathered:
{info_text}

## Clinician's Assessment:
{reason}

## Task:
Provide a single, specific diagnosis (1-3 words). Examples:
- "Acute appendicitis"
- "Community-acquired pneumonia"
- "Type 2 diabetes mellitus"
- "Atrial fibrillation"

Diagnosis:"""

    # Call LLM for diagnosis synthesis
    try:
        client = _get_diagnosis_client()
        response = client.chat.completions.create(
            model="openai/gpt-5-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a medical expert providing concise final diagnoses. Output only the diagnosis name, nothing else."
                },
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

    # Update session with final diagnosis step
    session = load_session(session_id)
    steps = session.get("steps", [])

    # Create final step
    final_step = {
        "step_number": len(steps) + 1,
        "new_information": f"Final diagnosis: {final_diagnosis_text}",
        "uncertainties": {},
        "reference_relevance": "N/A - Final diagnosis",
        "action": "DIAGNOSIS READY",
        "action_reason": reason,
        "final_diagnosis": final_diagnosis_text,
        "synthesis_prompt": synthesis_prompt
    }
    session["steps"].append(final_step)
    session["final_diagnosis"] = final_diagnosis_text
    session["current_uncertainties"] = {}

    # Save updated session
    save_session(session_id, session)

    # Return AgentClinic-compatible format
    return f"DIAGNOSIS READY: {final_diagnosis_text}"


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


def get_current_documented_response(session_id: str) -> str:
    """Get the current action response from the latest documented step.

    Helper function for inference_doctor to extract the response to output.

    Args:
        session_id: The session identifier

    Returns:
        The action from the latest step, or error message
    """
    session = load_session(session_id)
    steps = session.get("steps", [])

    if not steps:
        return "Error: No steps documented yet."

    latest_step = steps[-1]

    # Check if this is the final diagnosis step
    if latest_step.get("action") == "DIAGNOSIS READY":
        final_diagnosis = latest_step.get("final_diagnosis", "Unknown diagnosis")
        return f"DIAGNOSIS READY: {final_diagnosis}"

    # Return the action
    return latest_step.get("action", "Error: No action found in latest step")
