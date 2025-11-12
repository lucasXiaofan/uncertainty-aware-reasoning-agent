# MediQ Benchmark Analysis

## Overview
MediQ is a benchmark for evaluating question-asking ability in LLMs through interactive clinical reasoning. It tests whether agents can adaptively ask follow-up questions before making a diagnosis.

## Current Architecture

### Key Components
1. **Expert System**: Your agent that asks questions and makes decisions
2. **Patient System**: Simulates patient responses (provided by benchmark)
3. **Evaluation**: Measures efficiency (# questions) and accuracy (diagnosis)

### Data Format
- **Datasets**:
  - `all_craft_md.jsonl` (140 dermatology cases)
  - `all_dev_good.jsonl` (MedQA-based cases)
- **Format**: JSONL with interactive setup
  - `context`: Full patient information (hidden from agent initially)
  - `initial_info`: Starting information (age, gender, chief complaint)
  - `atomic_facts`: Decomposed facts for patient simulation
  - `answer`: Ground truth diagnosis

## API-Only Approach ⚠️ (Requires Modification)

### Current Dependencies (environment.yml)
```yaml
# GPU/CUDA Dependencies ⚠️
- pytorch=2.5.1=py3.12_cuda12.4_cudnn9.1.0_0
- pytorch-cuda=12.4
- cuda-cudart=12.4.127
- vllm==0.6.6.post1  # ⚠️ Heavy GPU dependency

# API Dependencies ✅
- openai=1.57.4  # ✅ Already included!
```

### Critical Code Analysis (`src/helper.py`)

```python
class ModelCache:
    def __init__(self, model_name, use_vllm=False, use_api=None, **kwargs):
        # ✅ Supports API mode!
        if self.use_api == "openai":
            from openai import OpenAI
            self.client = OpenAI(api_key=mykey[self.api_account])
        elif self.use_vllm:
            # ⚠️ GPU path - skip this
            from vllm import LLM
            self.model = LLM(model=self.model_name)
```

**Key Finding**: MediQ **already supports API-only mode**!

### API-Only Configuration ✅

#### Step 1: Configure API Keys
Edit `benchmarks/mediQ/src/keys.py`:
```python
mykey = {
    "openai": "your-openai-api-key-here"
}
```

#### Step 2: Run with API Mode
```bash
cd benchmarks/mediQ

python src/mediQ_benchmark.py \
  --expert_module expert \
  --expert_class YourExpertClass \
  --patient_module patient \
  --patient_class InstructPatient \
  --data_dir data \
  --dev_filename all_craft_md.jsonl \
  --use_api openai \
  --patient_model gpt-4o-mini \
  --expert_model gpt-4o-mini \
  --max_questions 10
```

#### Key Arguments
- `--use_api openai`: **Critical!** Use OpenAI API instead of local models
- `--use_vllm`: **DO NOT SET** (defaults to False)
- `--patient_model`: Model for patient simulator
- `--expert_model`: Model for expert system (your agent)
- `--patient_variant`: Options: `random`, `direct`, `instruct`, `factselect`

## Integration Plan

### Option 1: Implement Expert Class (Recommended)
**Pros**: Works directly with MediQ framework
**Cons**: Must follow their interface

```python
# Create: src/agents/mediq_expert.py
from benchmarks.mediQ.src.expert import Expert

class DSPyReActExpert(Expert):
    def __init__(self, args, sample):
        super().__init__(args, sample)
        self.dspy_agent = DSPyReActAgent(model_name=args.expert_model)

    def respond(self, patient_state):
        """
        Returns either:
        - A question to ask patient
        - A final diagnosis decision
        """
        # Use DSPy agent to decide action
        return decision
```

### Option 2: Standalone Integration (Data-Only)
**Pros**: Full control, no MediQ code dependency
**Cons**: Must re-implement patient simulator

```python
# Load MediQ data
with open("benchmarks/mediQ/data/all_craft_md.jsonl") as f:
    for line in f:
        case = json.loads(line)

        # Interactive loop
        for turn in range(max_questions):
            question = agent.ask_question(context)
            answer = simulate_patient(question, case['context'])

            if agent_ready_to_decide:
                diagnosis = agent.diagnose(context)
                break
```

### Option 3: Wrapper Approach (Hybrid)
**Pros**: Use MediQ patient simulator, custom agent
**Cons**: Requires understanding both systems

```python
# Import MediQ patient
from benchmarks.mediQ.src.patient import InstructPatient

# Use their patient, our agent
patient = InstructPatient(args, sample)
for turn in range(max_questions):
    question = our_agent.ask_question(context)
    answer = patient.respond(question)
    # Continue...
```

## Recommended Approach

### Phase 1: Standalone Data-Only (Current)
1. **Load MediQ JSONL data** (already in `mediq_wrapper.py`)
2. **Implement simple patient simulator**
   - Start with initial_info only
   - Agent asks questions
   - Simulate answers from context
3. **Run DSPy ReAct agent** in interactive mode
4. **Metrics**: Accuracy, # questions, question quality

**Implementation**:
```python
class SimpleMediQSimulator:
    def __init__(self, case):
        self.initial_info = case['initial_info']
        self.context = case['context']
        self.questions_asked = []

    def simulate_patient_response(self, question):
        # Simple keyword matching in context
        # Return relevant information
        pass
```

### Phase 2: Full MediQ Integration (Future)
1. Create Expert class that wraps our DSPy agent
2. Use MediQ's patient simulators (InstructPatient, FactSelectPatient)
3. Run through MediQ benchmark script
4. Compare with paper baselines

## Implementation Checklist

- [x] Clone MediQ repository
- [x] Understand data format (JSONL with initial_info + context)
- [x] Create data loader in `mediq_wrapper.py`
- [ ] Test API-only mode with simple expert
- [ ] Implement patient simulator (or use theirs)
- [ ] Integrate DSPy agent as Expert class
- [ ] Run on sample cases
- [ ] Implement evaluation metrics
- [ ] Handle edge cases (patient says "cannot answer")

## Minimal Dependencies for API-Only

### DO NOT INSTALL (GPU Dependencies):
```txt
# ❌ Skip these - only for local GPU models
pytorch
pytorch-cuda
cuda-*
vllm
transformers (if not using locally)
```

### MUST INSTALL (API-Only):
```txt
# ✅ Required for API-only
openai>=1.57.0
python-dotenv>=1.0.0
pandas>=2.0.0
pyyaml>=6.0
tqdm>=4.65.0
```

## Critical Configuration

### Modify MediQ Code for API-Only
**File**: `benchmarks/mediQ/src/helper.py`

Ensure this logic is used:
```python
if self.use_api == "openai":
    # ✅ This path works - no GPU needed
    self.client = OpenAI(api_key=mykey["openai"])
```

### API Keys Setup
**File**: `benchmarks/mediQ/src/keys.py`
```python
mykey = {
    "openai": os.getenv("OPENAI_API_KEY", "your-key-here")
}
```

## Notes
- ✅ MediQ supports API-only mode via `--use_api openai`
- ⚠️ Environment.yml includes heavy CUDA dependencies (can skip for API-only)
- ✅ Patient simulator can use API (no local model needed)
- ✅ Expert system can use API (no local model needed)
- 🎯 **Key Insight**: Use `--use_api openai` flag to bypass ALL GPU dependencies
- 📊 Evaluation metrics: Accuracy (diagnosis), Efficiency (# questions), Calibration
