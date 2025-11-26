# Question Quality and Decision Ability Analysis

## Overview
This report analyzes the performance of the `Improved Single Agent with Search` on 14 medical reasoning problems. The analysis focuses on the quality of questions asked, the agent's ability to gather information, and how its decision-making evolves with new context.

**Source Data**:
- `question_quality_comparison/result-improved_single_agent_with_search.jsonl`
- `question_quality_comparison/summaryimproved_single_agent_with_search.json`

## 1. Question Asking Quality

### Metrics
- **Total Questions Asked**: 32
- **Redundant Questions**: 1 (3.1%)
  - *Definition*: Questions that are semantically identical to previously asked questions.
- **Failed Questions**: 13 (40.6%)
  - *Definition*: Questions where the patient responded "The patient cannot answer this question...", indicating the information was not available in the ground truth context.
- **Proactiveness**: 13/14 (92.9%) cases involved active questioning.

### Detailed Breakdown
| ID | Total Qs | Redundant Qs | Failed Qs | Proactive? | Note |
|---|---|---|---|---|---|
| 9 | 2 | 0 | 1 | Yes | |
| 10 | 0 | 0 | 0 | No | Correctly identified sufficient initial info |
| 18 | 4 | 1 | 3 | Yes | High failure rate, redundant questioning |
| 28 | 6 | 0 | 0 | Yes | Excellent information gathering |
| 30 | 1 | 0 | 0 | Yes | Efficient |
| 33 | 3 | 0 | 2 | Yes | |
| 34 | 3 | 0 | 2 | Yes | |
| 38 | 3 | 0 | 2 | Yes | |
| 41 | 2 | 0 | 2 | Yes | All questions failed |
| 43 | 2 | 0 | 0 | Yes | |
| 44 | 1 | 0 | 0 | Yes | |
| 45 | 1 | 0 | 0 | Yes | |
| 46 | 2 | 0 | 0 | Yes | |
| 49 | 2 | 0 | 1 | Yes | |

### Analysis
- **Redundancy is low**: The agent rarely repeats itself, which is positive.
- **High "Hallucination" of Information Availability**: The 40.6% failure rate suggests the agent frequently asks for information (likely specific lab values or history) that is not present in the vignette. This indicates a mismatch between the agent's expectations of a "patient" (who might know their history) and the static nature of the benchmark vignettes.

## 2. Decision Ability & Context Usage

### Metrics
- **Accuracy**: 11/14 (78.6%)
- **Token Usage**:
  - Total Input: 3,224,223
  - Total Output: 113,079

### Trajectory Analysis
We track how the agent's intermediate choice evolves as it gathers more information.

| ID | Context % | Trajectory | Final Result |
|---|---|---|---|
| 9 | 54.7% | **Improved** (Wrong -> Correct) | Correct |
| 10 | 13.0% | **Stable Correct** | Correct |
| 18 | 20.7% | **Stable Wrong** | Wrong |
| 28 | 100.0% | **Improved** (Wrong -> Correct) | Correct |
| 30 | 48.0% | **Improved** (Wrong -> Correct) | Correct |
| 33 | 38.5% | **Stable Correct** | Correct |
| 34 | 47.2% | **Improved** (Wrong -> Correct) | Correct |
| 38 | 19.1% | **Stable Correct** | Correct |
| 41 | 12.7% | **Stable Correct** | Correct |
| 43 | 49.4% | **Improved** (Wrong -> Correct) | Correct |
| 44 | 37.3% | **Improved** (Wrong -> Correct) | Correct |
| 45 | 57.3% | **Stable Correct** | Correct |
| 46 | 33.5% | **Stable Wrong** | Wrong |
| 49 | 55.4% | **Stable Wrong** | Wrong |

*Note: Context % is an approximation based on character length of revealed info vs total available context.*

### Key Findings
1.  **High Value of Interaction**: In **6 out of 14 cases (43%)**, the agent started with a wrong or uncertain hypothesis and corrected itself after asking questions (The "Improved" trajectory). This validates the multi-turn approach.
2.  **No Degradation**: There were **0 cases** where the agent switched from a Correct to a Wrong answer.
3.  **Stubborn Errors**: In the 3 "Stable Wrong" cases, the agent failed to correct itself despite asking questions. In ID 18, specifically, the high number of failed questions (3/4) suggests the agent was stuck looking for missing info rather than reasoning with what it had.

## 3. Insights & Recommendations

### Insight 1: The "Silent Patient" Problem
The agent wastes significant turns (and tokens) asking questions that yield "The patient cannot answer this".
- **Evidence**: 40.6% of questions failed. ID 18 and 41 had mostly failed questions.
- **Improvement**: Implement a "Vignette Awareness" prompt. The agent should be instructed that it is interacting with a limited case study, not a live patient. It should prioritize extracting details likely to be in the text (symptoms, timeline) over ordering new diagnostics.

### Insight 2: Effective Correction
The system is highly effective at using *successful* information retrieval to correct its reasoning.
- **Evidence**: ID 28 gathered 100% of the context and switched from Wrong to Correct. ID 9, 30, 34, 43, 44 also improved.
- **Improvement**: Reinforce this behavior. Ensure the agent explicitly cites the *new* information that led to the change in opinion (e.g., "Now that I know X, my diagnosis changes to Y").

### Insight 3: Handling "Unknowns"
When the agent hits a wall (multiple "cannot answer" responses), it tends to stick to its initial (wrong) guess (e.g., ID 18).
- **Improvement**: Add a fallback mechanism. If the agent receives >2 "cannot answer" responses, it should trigger a "Reasoning with Partial Info" mode, where it re-evaluates the probability of options based *only* on confirmed facts, acknowledging the missing pieces.

### Insight 4: Token Efficiency
The input token count is high (~230k per sample avg).
- **Improvement**: Summarize history. Instead of feeding the full conversation history every turn, summarize the "Confirmed Facts" and "Ruled Out Hypotheses" to reduce context window usage and potentially focus the model's attention.
