# Analysis Report: ScaleExpert vs. UncertaintyAwareExpert

This report compares the performance of two agentic methods on 14 "hard" medical diagnosis cases.
*   **Method 1 (ScaleExpert):** `mediq_scaleex_14hard.jsonl`
*   **Method 2 (UncertaintyAwareExpert):** `single_agent_14_hard.jsonl`

---

## 1. Patient-by-Patient Interaction Analysis

| ID | Method | Total Qs | Valid Qs | Result | Interaction Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **9** | ScaleExpert | 1 | 1 | ❌ Fail | Asked about symptoms, got answer (angina), but failed diagnosis. |
| | **Uncertainty** | **7** | **1** | **✅ Pass** | Asked 7 variations of history questions; only 1 valid answer (angina/history). **Solved with same info as ScaleExpert.** |
| **10** | ScaleExpert | 4 | 2 | ❌ Fail | Asked 4 Qs, got 2 valid answers (pain history, weight loss). Still failed. |
| | **Uncertainty** | **0** | **0** | **✅ Pass** | **Solved with ZERO questions.** Demonstrated superior reasoning on initial context alone. |
| **18** | ScaleExpert | 5 | 1 | ❌ Fail | Got lab results (valid). Failed. |
| | **Uncertainty** | 0 | 0 | ❌ Fail | Decided to answer immediately. Failed. |
| **28** | ScaleExpert | 0 | 0 | ❌ Fail | Answered immediately. Failed. |
| | **Uncertainty** | **0** | **0** | **✅ Pass** | **Solved with ZERO questions.** Correctly interpreted initial symptoms (bloody diarrhea). |
| **30** | ScaleExpert | 0 | 0 | ❌ Fail | Answered immediately. Failed. |
| | **Uncertainty** | **3** | **1** | **✅ Pass** | Asked for lab results, **got them (valid)**, and solved the case. Critical info retrieval. |
| **33** | ScaleExpert | 7 | 0 | ❌ Fail | Asked 7 questions, **all invalid** (hallucinated symptoms?). Failed. |
| | **Uncertainty** | 7 | 0 | ❌ Fail | Also asked 7 invalid questions. Failed. |
| **34** | ScaleExpert | 0 | 0 | ❌ Fail | Answered immediately. Failed. |
| | **Uncertainty** | **3** | **2** | **✅ Pass** | Asked about **travel history** and **rash**. Got valid answers. Solved it. |
| **38** | ScaleExpert | 1 | 1 | ❌ Fail | Got chest pain details. Failed. |
| | **Uncertainty** | 7 | 2 | ❌ Fail | Got lab results and chest pain details. Still failed. |
| **41** | ScaleExpert | 4 | 1 | ❌ Fail | Got info on shortness of breath. Failed. |
| | **Uncertainty** | **1** | **1** | **✅ Pass** | Asked 1 targeted question, confirmed symptoms, and **solved it efficiently.** |
| **43** | ScaleExpert | 1 | 1 | **✅ Pass** | Asked about fever/symptoms. Got valid answer. Solved. |
| | **Uncertainty** | **1** | **1** | **✅ Pass** | Similar interaction. Solved. |
| **44** | ScaleExpert | 2 | 1 | ❌ Fail | Got info on breathing difficulty. Failed. |
| | **Uncertainty** | 0 | 0 | ❌ Fail | Answered immediately. Failed. |
| **45** | ScaleExpert | 1 | 1 | ❌ Fail | Got info on initial diagnosis. Failed. |
| | **Uncertainty** | 0 | 0 | ❌ Fail | Answered immediately. Failed. |
| **46** | ScaleExpert | 2 | 2 | ❌ Fail | Got info on mass duration/growth. Failed. |
| | **Uncertainty** | **3** | **1** | **✅ Pass** | Asked about **smoking history**. Got valid answer. Solved it. |
| **49** | ScaleExpert | 0 | 0 | ❌ Fail | Answered immediately. Failed. |
| | **Uncertainty** | 3 | 1 | ❌ Fail | Got info on bruising. Failed. |

---

## 2. Summary & Comparison

| Metric | ScaleExpert (Method 1) | UncertaintyAwareExpert (Method 2) |
| :--- | :--- | :--- |
| **Total Correct** | **1 / 14 (7%)** | **8 / 14 (57%)** |
| **Zero-Shot Success** | 0 | **2** (IDs 10, 28) |
| **Success via Q&A** | 1 | **6** (IDs 9, 30, 34, 41, 43, 46) |
| **Avg Questions Asked** | 2.0 | 2.5 |
| **Question Effectiveness** | Low. Often asks invalid questions or fails to use valid answers. | **High.** Questions are more targeted and results are effectively used for diagnosis. |

## 3. Key Findings

**1. Which method asks better questions?**
*   **UncertaintyAwareExpert is significantly better.**
*   It demonstrates **active information seeking**: In cases like ID 30 (Anemia) and ID 34 (Travel history), it specifically asked for missing lab results or history that were critical for the diagnosis.
*   **ScaleExpert** often asks questions that are either invalid (patient can't answer) or, even when valid answers are received (e.g., ID 10, 41, 46), it fails to update its reasoning to reach the correct conclusion.

**2. Context Gap & Efficiency**
*   **UncertaintyAwareExpert is highly efficient with context.**
    *   **Zero Context Needed:** For IDs 10 and 28, it correctly identified that the *initial info* was sufficient to solve the case, whereas ScaleExpert failed even after asking questions.
    *   **Partial Context Needed:** For IDs 30, 34, and 46, it identified exactly *which* piece of the puzzle was missing (Labs, Travel, Smoking History) and asked for it.
*   **ScaleExpert** appears to suffer from a "reasoning gap" rather than just a context gap. Even when it has the same or more context (e.g., ID 10, 46), it fails to make the correct diagnosis.

## 4. Repetitive Question Analysis

An analysis was performed to check if either method gets "stuck" asking the same question repeatedly when the patient cannot answer.

*   **ScaleExpert (Method 1):**
    *   **Repetitive Questions:** **0**
    *   **Behavior:** Even when the patient replied "The patient cannot answer this question..." multiple times (e.g., ID 10, ID 33), ScaleExpert moved on to ask *different* questions about other symptoms or history. It did not exhibit looping behavior.

*   **UncertaintyAwareExpert (Method 2):**
    *   **Repetitive Questions:** Found in **2 Patients** (ID 9, ID 33).
    *   **Behavior:** This method exhibits a "persistence loop" when it believes a specific piece of information is critical for the diagnosis.
    *   **Specific Examples:**
        *   **Patient ID 9 (Hypertension/MI):** The agent asked **5 variations** of the same question regarding "history of asthma, COPD, or bradycardia" (Questions 3, 4, 5, 6, 7). It correctly identified that this information was needed to safely prescribe Atenolol (the correct answer), but failed to accept that the information was unavailable.
        *   **Patient ID 33 (Knee Pain):** The agent asked **4 variations** of questions regarding "swelling, redness, warmth" and "morning stiffness" (Questions 2, 4, 5, 6).

**Implication:** While UncertaintyAwareExpert is better at identifying *what* information is needed, it needs a mechanism to "give up" on a specific line of inquiry after receiving a "cannot answer" response, rather than rephrasing the same question.

**Conclusion:**
The **UncertaintyAwareExpert** is the superior method. It correctly balances **knowing when to answer immediately** (saving user effort) and **knowing when to ask for specific, high-value evidence** (improving accuracy). ScaleExpert struggles to effectively utilize the interactive capability to improve its diagnosis.
