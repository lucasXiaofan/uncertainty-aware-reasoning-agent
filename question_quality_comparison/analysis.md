# Question Quality Comparison Analysis

## Executive Summary

This analysis examines the performance differences between an uncertainty-aware interactive agent and the MediQ baseline on 10 medical diagnosis questions. We focus on three key cases:
1. **Problem 2 (id 1)**: Agent success, baseline failure
2. **Problem 10 (id 9)**: Agent success, baseline failure
3. **Problem 8 (id 7)**: Both systems failed - a particularly challenging case

---

## Case Study 1: Problem 2 (id 1) - Cyclic Vomiting Syndrome

### Question Details
**Initial Info:** A 5-year-old girl with multiple episodes of nausea and vomiting lasting about 2 hours.

**Correct Answer:** A - Cyclic vomiting syndrome

**Options:**
- A: Cyclic vomiting syndrome
- B: Gastroenteritis
- C: Hypertrophic pyloric stenosis
- D: Gastroesophageal reflux disease

### Agent Performance: ✅ SUCCESS

**Strategy:**
- **Turn 1**: Asked about diarrhea/fever (confidence: 0.7)
  - Answer: No accompanying diarrhea or fever
- **Turn 2**: Asked about similar episodes and migraine history (confidence: 0.7)
  - Answer: Yes, hospitalized 2 times in past 6 months for similar episodes
- **Turn 3**: Asked about frequency and duration details (confidence: 0.7)
  - Answer: Episodes last 2 hours with 6-8 vomiting occurrences each
- **Turn 4**: Made diagnosis with confidence 0.85 → **Correct: A**

**Key Success Factors:**
1. **Pattern recognition through questioning**: Asked about recurrent nature of symptoms
2. **Appropriate information gathering**: Focused on distinguishing cyclic vomiting from acute gastroenteritis
3. **Confidence calibration**: Maintained appropriate uncertainty (0.7) until sufficient information gathered

### MediQ Baseline Performance: ❌ FAILURE

**Strategy:**
- **Turn 1**: Immediate diagnosis with confidence 4.0 → **Incorrect: B (Gastroenteritis)**

**Failure Analysis:**
1. **Overconfidence**: Maximum confidence (4.0) without gathering additional information
2. **Missed key differentiator**: Failed to identify the recurrent, episodic pattern that distinguishes cyclic vomiting syndrome from acute gastroenteritis
3. **No information seeking**: Did not ask questions despite ambiguous initial presentation

### Why Agent Succeeded Where Baseline Failed

**Critical Insight**: The initial presentation could plausibly be gastroenteritis. The key discriminating factors were:
- Recurrent episodes (hospitalized 2x in 6 months)
- Symptom-free intervals between episodes
- No fever or diarrhea (atypical for gastroenteritis)

The agent's question-asking strategy uncovered these critical details, while the baseline made a premature diagnosis based on incomplete information.

---

## Case Study 2: Problem 10 (id 9) - Atenolol for Post-MI Management

### Question Details
**Initial Info:** A 60-year-old woman for wellness checkup with history of hypertension, discharged yesterday after MI management.

**Correct Answer:** A - Atenolol

**Options:**
- A: Atenolol (beta-blocker)
- B: Furosemide (loop diuretic)
- C: Hydrochlorothiazide (thiazide diuretic)
- D: Nitroglycerin (vasodilator)

### Agent Performance: ✅ SUCCESS

**Strategy:**
- **Turn 1**: Asked about current symptoms and cardiac history (confidence: 0.3)
  - Answer: Exertional angina present, history of hypertension confirmed
- **Turn 2**: Attempted to get more details about angina frequency/control (confidence: 0.65)
  - Answer: Information not available
- **Turn 3**: Made diagnosis with confidence 0.85 → **Correct: A**

**Key Success Factors:**
1. **Low initial confidence (0.3)**: Appropriately recognized need for more information
2. **Targeted information gathering**: Focused on symptoms relevant to post-MI management
3. **Clinical reasoning**: Recognized that post-MI patient with hypertension and angina needs beta-blocker for secondary prevention

### MediQ Baseline Performance: ❌ FAILURE

**Strategy:**
- **Turn 1**: Asked about current symptoms (confidence: 1.0)
  - Answer: Exertional angina present
- **Turn 2**: Made diagnosis with confidence 4.0 → **Incorrect: D (Nitroglycerin)**

**Failure Analysis:**
1. **Symptom-focused instead of guideline-based**: Focused on treating the angina symptom rather than comprehensive post-MI management
2. **Missed critical context**: Failed to prioritize that this is a POST-MI patient requiring secondary prevention
3. **Incorrect treatment prioritization**: Nitroglycerin is for acute symptom relief, not the best next step in post-MI management

### Why Agent Succeeded Where Baseline Failed

**Clinical Context Matters**: This question tests understanding of post-MI management guidelines:
- Beta-blockers (Atenolol) are indicated for ALL post-MI patients for secondary prevention
- They also help with hypertension and angina
- Nitroglycerin only provides symptomatic relief

The agent demonstrated better clinical reasoning by recognizing the **post-MI context** as the primary driver of treatment choice, while the baseline fixated on the symptom (exertional angina) and chose symptomatic treatment.

**Question Quality Insight**: The agent's first question had very low confidence (0.3), suggesting the initial information was insufficient. The question about "current symptoms and cardiac history" helped contextualize the post-MI status and hypertension, leading to the correct guideline-based choice.

---

## Case Study 3: Problem 8 (id 7) - Non-exertional Heat Stroke (Hard Problem)

### Question Details
**Initial Info:** A 67-year-old man with fever and altered mental status, history of Alzheimer's, typically bed-bound.

**Correct Answer:** C - Non-exertional heat stroke

**Options:**
- A: Exertional heat stroke
- B: Neuroleptic malignant syndrome
- C: Non-exertional heat stroke
- D: Septic shock

### Agent Performance: ❌ FAILURE

**Strategy:** Asked 7 questions but never made a final diagnosis
- **Turn 1**: Asked about antipsychotic medications (confidence: 0.6)
  - Answer: Patient given haloperidol prior to examination
- **Turn 2**: Asked about muscle rigidity, autonomic instability, CK levels (confidence: 0.7)
  - Answer: Cannot answer
- **Turn 3**: Repeated question about muscle rigidity/autonomic instability (confidence: 0.7)
  - Answer: Cannot answer
- **Turn 4**: Rephrased same question about observable signs (confidence: 0.7)
  - Answer: Cannot answer
- **Turn 5**: Asked about CK and WBC levels (confidence: 0.7)
  - Answer: WBC 4,500/mm³, CK not mentioned
- **Turn 6**: Asked specifically about CK level (confidence: 0.65)
  - Answer: Cannot answer
- **Turn 7**: Repeated muscle rigidity question (confidence: 0.6)
  - Answer: No signs mentioned
- **Max turns reached**: Generated one more question about infection/heat exposure → **No final answer**

### MediQ Baseline Performance: ❌ FAILURE

**Strategy:**
- **Turn 1**: Asked about infection history (confidence: 2.0)
  - Answer: Cannot answer
- **Turn 2**: Made diagnosis with confidence 4.0 → **Incorrect: D (Septic shock)**

### Why This Is a Hard Problem

**Diagnostic Challenge Factors:**
1. **Multiple plausible diagnoses**: Could reasonably be NMS, sepsis, or heat stroke
2. **Confounding intervention**: Haloperidol given BEFORE the fever presentation, creating red herring for NMS
3. **Subtle clues required**: Need to recognize:
   - Bed-bound elderly patient (vulnerable to heat stroke)
   - Dry, flushed skin (not sweating)
   - Rapid improvement with cooling (diagnostic response)
   - Normal labs ruling out sepsis (normal WBC, no infection source)
4. **Temporal reasoning**: Need to understand haloperidol was given AFTER presentation, not a chronic medication

### Why Agent Got Stuck in Question Loop

**Fixation on NMS Diagnosis:**
1. Saw haloperidol administration → suspected NMS
2. Tried to confirm NMS criteria: muscle rigidity, autonomic instability, elevated CK
3. These specific findings weren't explicitly stated in the available information
4. Agent kept asking variations of the same question, hoping for confirmation
5. Confidence never exceeded 0.7, preventing final diagnosis

**Question Quality Issues:**
- **Overly specific questions**: Looking for exact NMS criteria rather than broader differential
- **Failure to pivot**: When information wasn't available, didn't switch diagnostic approach
- **Missed available clues**:
  - Didn't focus on "dry and flushed skin"
  - Didn't recognize significance of rapid response to cooling
  - Didn't note the bed-bound status + heat exposure vulnerability

### Why Baseline Also Failed

**Premature Closure:**
1. Saw fever + altered mental status → jumped to sepsis
2. One question about infection (unanswerable) didn't deter diagnosis
3. Ignored critical negative findings:
   - Normal WBC count (sepsis unlikely)
   - Clean urinalysis
   - No obvious infection source
   - Unremarkable chest X-ray

**Both Systems' Common Error:**
Failed to recognize the diagnostic significance of the **treatment response**: patient improved rapidly with simple cooling (Ringer's lactate + electric fan), strongly suggesting heat-related illness rather than NMS or sepsis.

---

## Analysis of Question-Asking Quality

### What Makes a Good Diagnostic Question?

Based on the success cases (problems 2 and 10), effective questions:

1. **Distinguish between competing diagnoses**
   - Problem 2: "Does child have diarrhea/fever?" → Rules out gastroenteritis
   - Problem 2: "Similar episodes in past?" → Confirms cyclic pattern

2. **Fill critical information gaps**
   - Problem 10: "Current symptoms + cardiac history?" → Contextualizes post-MI status

3. **Are appropriately scoped**
   - Not too specific (avoiding yes/no dead-ends)
   - Not too broad (getting actionable information)

4. **Build on previous answers**
   - Progressive refinement of diagnostic hypothesis

### What Makes a Poor Diagnostic Question?

Based on the failure case (problem 8), ineffective questions:

1. **Too specific/confirmatory**
   - "Does patient have muscle rigidity?" → Binary question that hits dead end

2. **Repetitive without rephrasing strategically**
   - Asked about muscle rigidity/autonomic instability 4 times with minimal variation

3. **Fixated on single diagnosis**
   - All questions aimed at confirming NMS, didn't explore alternatives

4. **Ignore available information**
   - Didn't ask about significance of dry/flushed skin, bed-bound status, or cooling response

---

## Recommendations for Better Question Generation in MediQ Setup

### 1. Implement Multi-Hypothesis Question Strategy

**Current Problem**: Agent fixates on one diagnosis and asks confirmatory questions

**Proposed Solution**: Generate questions that differentiate between top 2-3 diagnoses simultaneously

**Example for Problem 8:**
Instead of: "Does patient have muscle rigidity?" (NMS-specific)
Better: "Is the patient's environment temperature-controlled, and are there signs of muscle rigidity or infection source?" (covers heat stroke, NMS, sepsis)

### 2. Add Question Diversity Mechanisms

**Current Problem**: Agent repeats similar questions when answers are unavailable

**Proposed Solutions:**
- Track asked questions and penalize semantic similarity
- If information unavailable after 2 attempts, pivot to different diagnostic angle
- Implement "question budget" per diagnostic hypothesis (max 2-3 questions per hypothesis)

**Example for Problem 8:**
After 2 failed attempts to confirm muscle rigidity:
- Pivot to: "What is the environmental temperature and does the patient show signs of adequate hydration?"

### 3. Improve Confidence Calibration for Edge Cases

**Current Problem**: Agent gets stuck with moderate confidence (0.6-0.7), unable to commit

**Proposed Solutions:**
- If confidence plateaus after 3-4 questions, use available evidence to make best diagnosis
- Implement "information saturation" detection: if last 2 questions yield no new information, make diagnosis
- Lower confidence threshold for final answer after maximum questions asked (e.g., accept 0.65 instead of 0.75)

### 4. Incorporate Negative Evidence Reasoning

**Current Problem**: Systems don't adequately weight what's ABSENT

**Proposed Solutions:**
- Explicitly teach model to ask: "What findings would I expect for diagnosis X that are absent?"
- For Problem 8: Should note absence of elevated WBC, infection source, muscle rigidity
- Generate questions about rule-out criteria, not just rule-in criteria

**Example for Problem 8:**
"Given the normal WBC count and absence of infection source on labs/imaging, are there signs suggesting alternative diagnoses like heat exposure or medication reaction?"

### 5. Add Temporal and Causal Reasoning

**Current Problem**: Insufficient attention to timing and causality

**Proposed Solutions:**
- Parse temporal relationships in context (e.g., "given haloperidol PRIOR TO exam" vs "chronic haloperidol use")
- Ask questions about timeline: "When did symptoms start relative to medication administration?"
- Consider treatment response as diagnostic information

**Example for Problem 8:**
"What was the timeline of symptom onset, haloperidol administration, and response to cooling measures?"

### 6. Implement Differential Diagnosis Framework

**Current Problem**: Questions don't systematically work through differential diagnosis

**Proposed Solution**: Use structured approach:
1. Generate top 3 differential diagnoses with probabilities
2. Identify discriminating features for each
3. Ask questions that maximize information gain across the differential
4. Update probabilities after each answer
5. Continue until one diagnosis reaches threshold

**Example for Problem 8:**
```
Initial differential:
- Septic shock (30%): Check infection markers, hemodynamics
- NMS (30%): Check medication history, muscle rigidity, CK
- Heat stroke (25%): Check environment, skin findings, cooling response
- Other (15%)

Question 1: "What are the environmental conditions and is there evidence of infection?"
→ Answer updates probabilities based on information gain
```

### 7. Context-Aware Question Generation

**Current Problem**: Questions don't leverage full clinical context

**Proposed Solutions:**
- Identify patient vulnerability factors (age, bed-bound status, comorbidities)
- Weight diagnoses by base rates for this specific patient population
- Ask questions that account for these risk factors

**Example for Problem 8:**
"Given the patient is bed-bound and elderly, is there adequate environmental cooling and hydration monitoring?"

### 8. Meta-Learning from Question Effectiveness

**Current Problem**: No feedback loop on question quality

**Proposed Solutions:**
- Track which questions led to correct vs incorrect diagnoses
- Analyze correlation between question types and diagnostic accuracy
- Fine-tune question generation model on high-performing question patterns
- Create question template library for common diagnostic scenarios

**Metrics to Track:**
- Questions per correct diagnosis (efficiency)
- Information gain per question (effectiveness)
- Question diversity score (avoid repetition)
- Diagnostic pivot rate (flexibility)

---

## Quantitative Summary

### Overall Performance
| Metric | Agent | MediQ Baseline |
|--------|-------|----------------|
| Correct diagnoses | 7/10 (70%) | 5/10 (50%) |
| Questions asked (total) | 17 | 11 |
| Questions per case (avg) | 1.7 | 1.1 |
| Problems with 0 questions | 4 | 7 |

### Success Case Comparison
| Problem | Agent Result | Agent Questions | Baseline Result | Baseline Questions |
|---------|-------------|-----------------|-----------------|-------------------|
| 2 (id 1) | ✅ Correct | 3 | ❌ Wrong | 0 |
| 10 (id 9) | ✅ Correct | 2 | ❌ Wrong | 1 |

### Hard Problem Analysis
| Problem | Agent Result | Agent Questions | Baseline Result | Baseline Questions |
|---------|-------------|-----------------|-----------------|-------------------|
| 8 (id 7) | ❌ No answer | 7 | ❌ Wrong | 1 |

**Key Insight**: The agent's question-asking capability provides significant value in ambiguous cases, but needs improvement in:
1. Avoiding fixation on single diagnosis
2. Recognizing when to stop asking and make decision with available information
3. Generating questions that explore multiple hypotheses simultaneously

---

## Conclusion

The uncertainty-aware agent demonstrates superior performance when strategic question-asking can disambiguate between competing diagnoses. Success factors include:

1. **Appropriate initial uncertainty**: Low confidence signals need for information gathering
2. **Targeted questions**: Focus on key distinguishing features
3. **Progressive refinement**: Build diagnostic hypothesis through iterative questioning

However, the agent struggles with very difficult cases where:

1. Key information isn't available through questioning
2. Multiple diagnoses remain plausible
3. Fixation on one diagnostic hypothesis prevents exploration of alternatives

For the MediQ setup to improve, focus should be on:
1. Multi-hypothesis question generation
2. Question diversity and anti-repetition mechanisms
3. Better confidence calibration and decision-making under uncertainty
4. Temporal/causal reasoning enhancement
5. Systematic differential diagnosis framework

The difference between success (problems 2, 10) and failure (problem 8) lies not just in asking questions, but in asking the RIGHT questions that maximize information gain across the diagnostic differential.
