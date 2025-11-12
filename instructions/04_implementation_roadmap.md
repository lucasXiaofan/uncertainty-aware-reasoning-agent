# Implementation Roadmap - API-Only Benchmarks

## Overview
This document provides a step-by-step implementation plan for integrating the three medical diagnostic benchmarks using **API-only** approaches (no GPU/CUDA required).

## Pre-requisites Checklist

- [x] Benchmarks cloned (`AgentClinic`, `mediQ`, `simple-evals`)
- [x] Core dependencies installed (`requirements.txt`)
- [x] OpenAI API key configured (`.env`)
- [ ] Baseline DSPy agent tested (`example_usage.py`)
- [ ] Config file reviewed (`config.yaml`)

## Week 1: AgentClinic Integration

### Day 1-2: Data Loading and Parsing

#### Task 1.1: Test Data Loader
```bash
# Create test script
touch test_agentclinic.py
```

```python
# test_agentclinic.py
from src.benchmarks import AgentClinicBenchmark

# Load data
benchmark = AgentClinicBenchmark(
    data_path="./benchmarks/AgentClinic",
    dataset="medqa"
)
cases = benchmark.load_data(limit=5)

# Inspect format
for case in cases[:2]:
    print(f"Case ID: {case['case_id']}")
    print(f"Patient: {case['patient_info']}")
    print(f"Ground Truth: {case['ground_truth']}")
    print("-" * 50)
```

**Success criteria**: Loads 5 cases without errors, data format looks correct

#### Task 1.2: Update Wrapper Code
File: `src/benchmarks/agentclinic_wrapper.py`

- [x] Data loading implemented (DONE)
- [ ] Test with real agent
- [ ] Handle edge cases (missing fields, malformed data)
- [ ] Add data validation

### Day 3-4: Agent Integration

#### Task 1.3: Run Agent on Sample Cases
```python
# test_agentclinic.py (continued)
from src.agents import DSPyReActAgent

agent = DSPyReActAgent(model_name="gpt-4o-mini")

for case in cases:
    result = agent.diagnose(case['patient_info'])
    print(f"\nCase: {case['case_id']}")
    print(f"Agent Diagnosis: {result['diagnosis']}")
    print(f"Ground Truth: {case['ground_truth']}")
    print(f"Confidence: {result['confidence']}")
```

**Success criteria**: Agent produces diagnoses, no errors

#### Task 1.4: Implement Evaluation Logic
File: `src/benchmarks/agentclinic_wrapper.py`

```python
def evaluate(self, agent, test_cases):
    results = []

    for case in test_cases:
        # Run agent
        prediction = agent.diagnose(case['patient_info'])

        # Compare (exact match vs semantic match?)
        correct = self._match_diagnosis(
            prediction['diagnosis'],
            case['ground_truth']
        )

        results.append({
            'case_id': case['case_id'],
            'correct': correct,
            'confidence': prediction['confidence'],
            'prediction': prediction['diagnosis'],
            'ground_truth': case['ground_truth']
        })

    return self._aggregate_results(results)
```

**Challenges**:
- Diagnosis matching: Exact vs fuzzy matching?
- Multiple valid diagnoses?
- Acronyms (e.g., "MI" vs "myocardial infarction")?

**Solutions**:
1. Start with exact match (case-insensitive)
2. Add fuzzy matching with threshold
3. Use LLM to judge equivalence

### Day 5: Testing and Validation

#### Task 1.5: Full Evaluation Run
```bash
python run_baseline.py --benchmark agentclinic
```

**Expected output**:
- Accuracy: ?% (baseline to beat)
- Average confidence: ?
- Cases per minute: ?
- Total cost: ~$1-2 for 50 cases

#### Task 1.6: Results Analysis
- Which cases did agent get wrong?
- Pattern in failures?
- Confidence calibration?

**Deliverables**:
- [ ] Evaluation results saved (`results/agentclinic_*.json`)
- [ ] Summary report with findings
- [ ] Identified improvement areas

---

## Week 2: MediQ Integration

### Day 1-2: Understanding Interactive Loop

#### Task 2.1: Study MediQ Structure
```bash
cd benchmarks/mediQ
head -5 data/all_craft_md.jsonl
cat src/patient.py  # Study patient simulator
cat src/expert.py   # Study expert interface
```

#### Task 2.2: Test Patient Simulator
```python
# test_mediq.py
import sys
sys.path.append("./benchmarks/mediQ/src")

from patient import InstructPatient
from args import get_args

# Load a case
with open("benchmarks/mediQ/data/all_craft_md.jsonl") as f:
    case = json.loads(f.readline())

# Create patient
args = MockArgs(
    patient_model="gpt-4o-mini",
    use_api="openai",
    use_vllm=False
)
patient = InstructPatient(args, case)

# Ask questions
question = "How long have you had this condition?"
answer = patient.respond(question)
print(f"Q: {question}\nA: {answer}")
```

**Success criteria**: Patient responds to questions using API

### Day 3-4: Expert Implementation

#### Task 2.3: Create DSPy Expert Class
File: `src/benchmarks/mediq_expert.py`

```python
import sys
sys.path.append("./benchmarks/mediQ/src")
from expert import Expert
from src.agents import DSPyReActAgent

class DSPyExpert(Expert):
    def __init__(self, args, sample):
        super().__init__(args, sample)
        self.agent = DSPyReActAgent(
            model_name=args.expert_model
        )
        self.context = {
            'patient_info': {'chief_complaint': sample['initial_info']},
            'previous_questions': [],
            'answers': []
        }

    def respond(self, patient_state):
        """
        Decide: ask question or make decision?
        """
        # Check confidence
        diagnosis_result = self.agent.diagnose(self.context['patient_info'])

        if float(diagnosis_result['confidence']) > 0.8:
            # High confidence -> make decision
            return {
                'action': 'decision',
                'diagnosis': diagnosis_result['diagnosis']
            }
        else:
            # Low confidence -> ask question
            question = self.agent.ask_question(self.context)
            return {
                'action': 'question',
                'question': question
            }

    def update_with_answer(self, question, answer):
        """Update context after patient responds"""
        self.context['previous_questions'].append(question)
        self.context['answers'].append(answer)
        # Update patient_info with new facts
        self.context['patient_info']['symptoms'].append(answer)
```

#### Task 2.4: Integration Test
```bash
cd benchmarks/mediQ

python src/mediQ_benchmark.py \
  --expert_module ../../src/benchmarks/mediq_expert \
  --expert_class DSPyExpert \
  --patient_module patient \
  --patient_class InstructPatient \
  --use_api openai \
  --patient_model gpt-4o-mini \
  --expert_model gpt-4o-mini \
  --data_dir data \
  --dev_filename all_craft_md.jsonl \
  --max_questions 10 \
  --output_filename dspy_results.jsonl
```

**Success criteria**: Runs without errors, produces results

### Day 5: Evaluation and Analysis

#### Task 2.5: Analyze Results
- Average questions asked
- Accuracy vs baseline
- Question quality (relevant?)
- When does agent stop asking?

**Deliverables**:
- [ ] MediQ evaluation results
- [ ] Question quality analysis
- [ ] Confidence threshold tuning

---

## Week 3: HealthBench Integration

### Day 1: Setup and Testing

#### Task 3.1: Test HealthBench CLI
```bash
cd benchmarks/simple-evals
export OPENAI_API_KEY="your-key"

# Quick test (10 cases)
python -m simple_evals.simple_evals \
  --eval=healthbench \
  --model=gpt-4o-mini \
  --max_examples=10
```

**Success criteria**: Completes 10 cases, shows rubric scores

#### Task 3.2: Understand Output Format
```python
# Inspect results
import json

with open("results/healthbench_*.json") as f:
    results = json.load(f)

# Analyze rubric performance
for result in results[:3]:
    print(f"Conversation: {result['conversation_id']}")
    print(f"Score: {result['score']}")
    print(f"Rubric failures: {result['failed_criteria']}")
```

### Day 2-3: Custom Sampler

#### Task 3.3: Implement DSPy Sampler
File: `src/benchmarks/healthbench_sampler.py`

```python
import sys
sys.path.append("./benchmarks/simple-evals")

from simple_evals.types import SamplerBase, MessageList
from src.agents import DSPyReActAgent

class DSPyHealthBenchSampler(SamplerBase):
    def __init__(self, model_name="gpt-4o-mini", **kwargs):
        self.agent = DSPyReActAgent(model_name=model_name)

    def __call__(self, messages: MessageList) -> str:
        """
        Generate response to health query
        """
        # Convert messages to our format
        patient_info = self._extract_patient_info(messages)

        # Get agent response
        result = self.agent.diagnose(patient_info)

        return result['diagnosis']

    def _extract_patient_info(self, messages):
        """Convert message list to patient_info dict"""
        # Last user message is the query
        query = messages[-1]['content']
        return {
            'chief_complaint': query,
            'symptoms': [],  # Could parse from query
            'history': []
        }
```

#### Task 3.4: Run Custom Evaluation
```python
# test_healthbench.py
from src.benchmarks.healthbench_sampler import DSPyHealthBenchSampler
from simple_evals.healthbench_eval import HealthBench

sampler = DSPyHealthBenchSampler(model_name="gpt-4o-mini")
eval = HealthBench()

results = eval(sampler, max_examples=50)
print(f"Overall Score: {results['score']}")
```

### Day 4-5: Analysis and Optimization

#### Task 3.5: Rubric Analysis
- Which criteria does agent fail most?
- Safety issues detected?
- Communication quality scores?

#### Task 3.6: Agent Enhancement
Based on failures, enhance:
- Medical accuracy
- Safety warnings
- Communication clarity
- Instruction following

**Deliverables**:
- [ ] HealthBench evaluation results
- [ ] Rubric failure analysis
- [ ] Agent enhancement plan

---

## Week 4: Integration and Comparison

### Unified Evaluation

#### Task 4.1: Update run_baseline.py
```python
# Support all three benchmarks
python run_baseline.py --benchmark all --limit 50
```

#### Task 4.2: Comparative Analysis
- Which benchmark is hardest?
- Different failure modes?
- Confidence calibration across benchmarks?

#### Task 4.3: Documentation
- Update README with results
- Create performance comparison table
- Document setup instructions

**Deliverables**:
- [ ] Unified evaluation script
- [ ] Comparative results report
- [ ] Updated documentation

---

## Troubleshooting Guide

### Common Issues

#### "Module not found" errors
```bash
# Check Python path
python -c "import sys; print('\n'.join(sys.path))"

# Add to PYTHONPATH
export PYTHONPATH=$PYTHONPATH:./benchmarks/mediQ/src
```

#### "API key not found"
```bash
# Verify .env loaded
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('OPENAI_API_KEY'))"
```

#### "Rate limit exceeded"
```python
# Add retry logic
import time
from tenacity import retry, wait_exponential

@retry(wait=wait_exponential(multiplier=1, min=4, max=60))
def call_api_with_retry():
    return agent.diagnose(patient_info)
```

#### "Incorrect diagnosis format"
- Check agent output format
- Add validation before comparison
- Normalize text (lowercase, strip)

---

## Success Metrics

### Week 1 (AgentClinic)
- [ ] 50+ cases evaluated
- [ ] Baseline accuracy established
- [ ] Cost < $5

### Week 2 (MediQ)
- [ ] 20+ interactive cases
- [ ] Question quality assessed
- [ ] Cost < $5

### Week 3 (HealthBench)
- [ ] 50+ conversations evaluated
- [ ] Rubric scores analyzed
- [ ] Cost < $15

### Week 4 (Integration)
- [ ] All benchmarks working
- [ ] Comparison report generated
- [ ] Documentation complete

---

## Cost Management

### Monitor API Usage
```python
# Add cost tracking
class CostTracker:
    def __init__(self):
        self.total_tokens = 0
        self.total_calls = 0

    def track_call(self, response):
        self.total_tokens += response['usage']['total_tokens']
        self.total_calls += 1

    def estimate_cost(self, model="gpt-4o-mini"):
        # gpt-4o-mini: $0.15/1M input, $0.60/1M output
        cost = self.total_tokens * 0.0000004  # Average
        return cost
```

### Budget Allocation
- Week 1: $5 (AgentClinic)
- Week 2: $5 (MediQ)
- Week 3: $15 (HealthBench)
- Week 4: $5 (Additional testing)
- **Total**: ~$30

---

## Next Steps After Week 4

1. **Uncertainty Enhancement**: Add calibrated confidence scoring
2. **Memory Integration**: Experience-based learning from past cases
3. **Tool Integration**: Add external medical knowledge bases
4. **Multi-round Optimization**: Improve question-asking strategy
5. **Publication**: Write up results for paper/blog

## Questions? Issues?

See individual analysis documents:
- `01_agentclinic_analysis.md`
- `02_mediq_analysis.md`
- `03_healthbench_analysis.md`
