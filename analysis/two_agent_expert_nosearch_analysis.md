# Two-Agent Expert Analysis

**Input File**: `outputs/TwoAgentExpert_deepseek-chat_20251125_190423/results.jsonl`

## 1. Quantitative Overview
*(Based on automated analysis)*

| Metric | Value |
|---|---|
| **Total Questions** | 55 |
| **Redundant Questions** | 1 (1.8%) |
| **Failed Questions (No Info)** | 41 (74.5%) |
| **Average Questions per Problem** | ~3.7 |

**Key Observation**: The **74.5% failure rate** for questions is critically high. This indicates a severe disconnect between the agent's questions and the simulated patient's ability to answer (or the environment's retrieval logic).

## 2. Question Quality Analysis

### High Failure Rate (Case Study: ID 201)
- **Scenario**: A 45-year-old woman with fatigue and irregular menstrual cycles.
- **Agent Behavior**: The agent asked 9 questions, and **all 9 failed** (returned "The patient cannot answer...").
- **Questions Asked**: The agent asked about weight changes, skin changes, muscle weakness, and specific signs of Cushing's (moon facies).
- **Context Availability**: The hidden context contained *explicit* answers to these questions:
    - "Physical examinations shows neck obesity and an enlarged abdomen." (Relevant to weight/Cushing's)
    - "Examination of the skin shows multiple bruises..." (Relevant to skin)
    - "There is generalized weakness and atrophy of the proximal muscles." (Relevant to muscle weakness)
- **Root Cause**: The environment's matching logic appears too strict or the agent's questions are too specific/phrased in a way that doesn't trigger a match. For example, asking for "moon facies" might not match "neck obesity" even if they are related. The agent failed to retrieve the crucial lab values (ACTH, Cortisol) present in the context because it got stuck asking about symptoms that the system claimed were unanswerable.

### Redundancy
- **Observation**: Only 1.8% redundant questions.
- **Assessment**: The agent is generally good at not repeating itself *verbatim*, but it often repeats the *intent* (e.g., asking about symptoms in slightly different ways) when it fails to get an answer.

## 3. Judge Quality Analysis

The "Judge" (Decision Agent) and the "Differential Agent" showed several weaknesses:

1.  **Lack of Failure Awareness**:
    - In ID 201, the agent continued to ask questions for 9 turns despite receiving "cannot answer" every single time.
    - **Flaw**: The agent does not seem to have a mechanism to detect "information starvation" or "strategy failure". It should have pivoted to a different line of questioning (e.g., asking for "lab results" or "past medical history" broadly) or forced a best-guess earlier.

2.  **Confidence Hallucination/Stagnation**:
    - The agent's confidence often hovered around 50-60% ("I need more info").
    - **Flaw**: It failed to adjust its confidence *downward* regarding its ability to solve the case, or *upward* on a best guess when it realized no more info was coming. It simply stayed in a "waiting for info" state until the turn limit or forced end.

3.  **Poor Differential Diagnosis without New Info**:
    - Without new info, the agent's reasoning became circular. It kept listing the same differential (Hypothyroidism vs. Adrenal Adenoma) without any new evidence to shift the probability.

## 4. Framework Improvements

### A. Improve the Simulated Environment (Critical)
- **Fuzzy Matching**: Implement semantic similarity matching (using embeddings) between the agent's question and the context facts, rather than relying on strict keyword or exact matches.
- **Fact Extraction**: Ensure the environment correctly parses the `context` into answerable facts. The current failure rate suggests the environment is "blind" to the rich context available in the ground truth.

### B. Agent Logic Improvements
- **Stop-Loss Mechanism**: If the agent receives "cannot answer" for $N$ consecutive turns (e.g., 2 or 3), it should:
    1.  Stop asking specific symptom questions.
    2.  Try a "catch-all" question like "Please tell me everything else you know." or "Do you have any test results?".
    3.  Force a final diagnosis based on `initial_info` to save tokens.
- **Negative Evidence Usage**: If the system says "cannot answer", the agent *could* potentially interpret this (cautiously) as "not a major complaint" in some contexts, though this is risky. A better approach is to explicitly treat "cannot answer" as a signal to change topics.

### C. Prompt Engineering
- **Instruction Update**: Explicitly instruct the agent: "If the patient says they cannot answer, DO NOT ask the same type of question again. Switch to a different category (e.g., from Symptoms to History, or History to Labs)."

## 5. Conclusion
The **Two-Agent Expert** is currently handicapped by the **interaction environment**. The agent is capable of formulating relevant medical questions (asking about proximal muscle weakness for Cushing's is medically sound), but the environment fails to reward these questions with the available context. The agent's "Judge" component lacks the meta-cognition to realize the interaction is failing. Fixing the environment's retrieval logic is the highest priority to unlock the agent's potential.