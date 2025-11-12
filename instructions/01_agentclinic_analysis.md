# AgentClinic Benchmark Analysis

## Overview
AgentClinic is a multimodal agent benchmark to evaluate AI in simulated clinical environments. It simulates doctor-patient interactions with multiple agent roles.

## Current Architecture

### Key Components
1. **Doctor Agent**: Makes diagnosis based on patient interaction
2. **Patient Agent**: Simulates patient responses
3. **Moderator Agent**: Controls conversation flow
4. **Measurement Agent**: Simulates medical tests (EKG, blood pressure, imaging)

### Data Format
- **Datasets**:
  - `agentclinic_medqa.jsonl` (215 cases from USMLE)
  - `agentclinic_nejm.jsonl` (120 cases from NEJM)
  - Extended versions available
- **Format**: JSONL with OSCE examination structure
  - Patient demographics, history, symptoms
  - Physical examination findings
  - Test results
  - Correct diagnosis

## API-Only Approach ✅

### Current Dependencies
```
regex==2023.12.25
openai==0.28.0          # ✅ API-only
replicate==0.23.1       # ✅ API-only
argparse
transformers             # ⚠️ Optional (for HuggingFace models)
datasets
anthropic                # ✅ API-only
```

### Supported Models
- **OpenAI**: gpt-4, gpt-4o, gpt-4o-mini, gpt-3.5
- **Anthropic**: Claude 3.5 Sonnet
- **Replicate**: Llama, Mixtral (via API)
- **HuggingFace**: Any model (requires GPU - can skip)

### API-Only Configuration

#### ✅ No CUDA Dependencies Required
AgentClinic **natively supports API-only execution**. Simply use:

```bash
python3 agentclinic.py \
  --openai_api_key "YOUR_KEY" \
  --doctor_llm gpt-4o-mini \
  --patient_llm gpt-4o-mini \
  --moderator_llm gpt-4 \
  --measurement_llm gpt-4 \
  --inf_type llm \
  --num_scenarios 10
```

#### Key Arguments
- `--inf_type`: Set to `"llm"` (vs `"human_doctor"` or `"human_patient"`)
- `--doctor_llm`: Doctor agent model
- `--patient_llm`: Patient agent model
- `--agent_dataset`: `"MedQA"` or `"NEJM"`
- `--doctor_bias`: Optional bias injection (e.g., `"recency"`, `"confirmation"`)
- `--patient_bias`: Optional patient bias (e.g., `"self_diagnosis"`)

## Integration Plan

### Option 1: Direct CLI Wrapper (Recommended)
**Pros**: No code modification needed, use AgentClinic as-is
**Cons**: Less flexible, harder to extract intermediate data

```python
# Run AgentClinic via subprocess
subprocess.run([
    "python3", "benchmarks/AgentClinic/agentclinic.py",
    "--openai_api_key", api_key,
    "--doctor_llm", "gpt-4o-mini",
    "--patient_llm", "gpt-4o-mini",
    "--inf_type", "llm",
    "--num_scenarios", "50"
])
```

### Option 2: Import AgentClinic Components
**Pros**: Full control, can extract detailed metrics
**Cons**: Requires understanding AgentClinic internals

```python
import sys
sys.path.append("./benchmarks/AgentClinic")
from agentclinic import query_model, load_scenario

# Use their query_model function with our agent
```

### Option 3: Bypass AgentClinic Simulation (Custom)
**Pros**: Full control, use only data format
**Cons**: Lose multi-agent simulation benefits

```python
# Load JSONL data directly
# Run our agent on patient_info
# Compare against ground_truth diagnosis
```

## Recommended Approach

### Phase 1: Data-Only Integration
1. **Load AgentClinic JSONL data** (already in `agentclinic_wrapper.py`)
2. **Extract patient information** from OSCE format
3. **Run our DSPy ReAct agent** on patient info
4. **Compare diagnosis** to ground truth
5. **Metrics**: Accuracy, confidence, reasoning quality

**Pros**:
- No dependency on AgentClinic code
- Full control over agent behavior
- Easier debugging and experimentation

**Cons**:
- Missing multi-agent simulation (doctor-patient conversation)
- No moderator or measurement agents
- Less realistic clinical environment

### Phase 2: Full Multi-Agent Integration (Future)
1. Integrate with AgentClinic's multi-agent framework
2. Use our agent as the "doctor" agent
3. Leverage their patient/moderator/measurement agents
4. Evaluate in realistic conversational setting

## Implementation Checklist

- [x] Clone AgentClinic repository
- [x] Understand data format (JSONL with OSCE structure)
- [x] Create data loader in `agentclinic_wrapper.py`
- [ ] Test data loading with sample cases
- [ ] Run DSPy agent on sample cases
- [ ] Implement evaluation metrics
- [ ] Create results visualization
- [ ] (Optional) Integrate with full AgentClinic simulation

## Minimal Dependencies for API-Only

```txt
# Required for API-only execution
openai>=1.0.0
anthropic>=0.25.0

# Optional (skip these for API-only)
# transformers  - only needed for HuggingFace models
# torch         - only needed for local models
```

## Notes
- ⚠️ AgentClinic uses old OpenAI API (v0.28.0) - may need compatibility layer
- ✅ Can use newer OpenAI API by updating model query code
- ✅ No GPU or CUDA dependencies required for API-only mode
- ✅ Data is included in the repository (no separate download needed)
