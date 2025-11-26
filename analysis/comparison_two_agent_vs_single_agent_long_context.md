# Comparison Analysis: Two-Agent Expert vs. Single Agent (Long Context)

**Reference Files**:
- Two-Agent: `analysis/two_agent_expert_nosearch_analysis.md`
- Single Agent: `analysis/single_agent_long_context_analysis.md`

## 1. Executive Summary

The comparison reveals a **surprising efficiency gap**. Both systems achieved **identical accuracy (80%)**, but the **Single Agent (Long Context)** was **~5x more efficient** in terms of token usage. The Two-Agent system's elaborate internal dialogue and "Differential vs. Decision" separation did *not* yield better results in this specific "No Search" environment, likely because the environment's information retrieval bottleneck (high question failure rate) capped the performance ceiling for both.

| Metric | Two-Agent Expert | Single Agent (Long Context) | Winner |
|---|---|---|---|
| **Accuracy** | **80.0%** (12/15) | **80.0%** (12/15) | **Tie** |
| **Total Questions** | 55 | 24 | Single Agent (More concise) |
| **Question Failure Rate** | 74.5% | 83.3% | Two-Agent (Slightly better) |
| **Total Input Tokens** | ~2,266,819 | ~454,664 | **Single Agent (5x cheaper)** |
| **Total Output Tokens** | ~439,250 | ~82,048 | **Single Agent (5.3x cheaper)** |

## 2. Question Asking Ability

### Quantity & Quality
- **Two-Agent**: Asked **55 questions** (avg ~3.7/problem).
- **Single Agent**: Asked **24 questions** (avg ~1.6/problem).
- **Insight**: The Single Agent was far more conservative. It often asked just 1 or 2 questions before making a decision. The Two-Agent system tended to "over-investigate," asking multiple follow-ups even when getting no answers.

### Failure Rate (The Environment Bottleneck)
- **Two-Agent**: 74.5% failure.
- **Single Agent**: 83.3% failure.
- **Analysis**: Both agents failed miserably at retrieving information from the simulated patient. The Two-Agent system's slightly lower failure rate suggests its questions might have been marginally better phrased or more diverse, but not enough to change the outcome. The environment is the primary limiter for both.

## 3. Final Decision Ability

### Accuracy
- **Tie (12/15 Correct)**: Both systems failed on the exact same difficult cases (e.g., ID 182, ID 7, ID 201/1005).
- **Implication**: The "reasoning power" of the Two-Agent system (separating differential diagnosis) provided **zero marginal benefit** over the Single Agent's reasoning in this specific batch. The Single Agent was able to deduce the correct answer from the `initial_info` just as well as the complex multi-agent system.

### Trajectory
- **Two-Agent**: Showed more "Improved" trajectories (Wrong -> Correct). It started wrong more often but corrected itself.
- **Single Agent**: Often started "Stable Correct" or made fewer moves. It was more decisive.

## 4. Token, Speed, and Reliability

### The Efficiency Gap
- **Cost**: The Two-Agent system is prohibitively expensive compared to the Single Agent for this task.
    - **Input**: 2.2M vs 0.45M tokens.
    - **Output**: 439k vs 82k tokens.
- **Speed**: The Single Agent is significantly faster due to fewer LLM calls and less generated text.

### Reliability
- **Complex Tasks**: While the Two-Agent system is theoretically more robust for complex reasoning, this dataset did not show that advantage. The Single Agent was equally reliable but far more efficient.
- **Over-Engineering**: For this specific benchmark (MediQ with limited retrieval), the Two-Agent architecture appears to be **over-engineered**. The Single Agent with a long context window handles the reasoning just as well without the overhead.

## 5. Conclusion

For the **MediQ Benchmark (No Search)**:
1.  **Use the Single Agent (Long Context)**. It delivers the **same accuracy** at **20% of the cost**.
2.  **Fix the Environment First**: Before optimizing the agents further, the environment's question-answering logic must be improved. The >75% failure rate makes it impossible to truly evaluate the agents' information-gathering capabilities.
3.  **Re-evaluate Two-Agent Later**: Once the environment allows for actual information retrieval, the Two-Agent system might show its value by asking *better* follow-up questions. Currently, both agents are effectively guessing based on `initial_info` most of the time.
