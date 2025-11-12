# HealthBench Benchmark Analysis

## Overview
HealthBench is OpenAI's benchmark for evaluating LLMs in realistic health scenarios. It contains 5,000 health conversations with custom physician-created rubrics for grading.

## Current Architecture

### Key Components
1. **Conversations**: Realistic health queries from users
2. **Model Completions**: LLM responses to queries
3. **Rubric Grading**: AI-graded against 48,562 physician-written criteria
4. **Meta-Evaluation**: How well the AI grader matches physician graders

### Data Format
- **Data Source**: Hosted on Azure Blob Storage (HTTPS access)
- **Format**: JSONL with conversation and rubric structure
  - `conversation`: List of user/assistant messages
  - `rubric`: List of criteria with descriptions and point values
  - `metadata`: Context about the conversation

## API-Only Approach ✅

### Dependencies (Minimal)
```txt
# HealthBench uses simple-evals framework
blobfile          # For fetching data from Azure
pandas
numpy
openai>=1.0.0     # ✅ API-only
anthropic         # ✅ API-only (optional)
```

### Supported APIs
- **OpenAI**: All GPT models (gpt-4, gpt-4o, gpt-4o-mini, etc.)
- **Anthropic**: Claude models (via sampler)
- **Custom**: Can extend ChatCompletionSampler for other APIs

### API-Only Configuration ✅

#### Native API Support
HealthBench is **designed for API-only execution**:

```python
from simple_evals.sampler.chat_completion_sampler import ChatCompletionSampler

# Create sampler
sampler = ChatCompletionSampler(
    model="gpt-4o-mini",
    system_message="You are a helpful medical assistant."
)

# Run evaluation
python -m simple_evals.simple_evals \
  --eval=healthbench \
  --model=gpt-4o-mini
```

#### Environment Setup
```bash
export OPENAI_API_KEY="your-key-here"
# Optional for Claude
export ANTHROPIC_API_KEY="your-key-here"
```

### Code Structure Analysis

**File**: `healthbench_eval.py`
```python
from .sampler.chat_completion_sampler import ChatCompletionSampler

class HealthBench(Eval):
    def __call__(self, sampler: SamplerBase):
        # Fetch data from URL
        df = pd.read_json(INPUT_PATH, lines=True)

        # For each conversation
        for row in df:
            # Get model completion
            completion = sampler(row['messages'])

            # Grade with rubric using another model
            grades = grade_rubric(completion, row['rubric'])
```

**Key Finding**: Fully API-based, no local model support needed!

## Integration Plan

### Option 1: Use simple-evals CLI (Easiest)
**Pros**: Zero code changes, official implementation
**Cons**: Less control over agent behavior

```bash
cd benchmarks/simple-evals

# Run HealthBench
python -m simple_evals.simple_evals \
  --eval=healthbench \
  --model=gpt-4o-mini \
  --max_examples=100

# Variants
# --eval=healthbench_consensus  (higher agreement cases)
# --eval=healthbench_hard       (more challenging cases)
```

### Option 2: Import HealthBench Class
**Pros**: Integrate with our framework, custom metrics
**Cons**: Must implement sampler interface

```python
import sys
sys.path.append("./benchmarks/simple-evals")

from simple_evals.healthbench_eval import HealthBench
from simple_evals.sampler.chat_completion_sampler import ChatCompletionSampler

# Create our sampler
sampler = ChatCompletionSampler(model="gpt-4o-mini")

# Run evaluation
eval = HealthBench()
results = eval(sampler)
```

### Option 3: Custom Wrapper (Data-Only)
**Pros**: Full control, integrate with our agent
**Cons**: Must re-implement evaluation logic

```python
# Fetch HealthBench data
import pandas as pd
url = "https://openaipublic.blob.core.windows.net/simple-evals/healthbench/..."
df = pd.read_json(url, lines=True)

# Run our agent
for case in df:
    response = our_agent.respond(case['messages'])
    grades = grade_against_rubric(response, case['rubric'])
```

## Recommended Approach

### Phase 1: CLI Integration (Immediate)
1. **Use simple-evals directly** with our model
2. **Run baseline evaluation** to understand performance
3. **Analyze results** to identify areas for improvement

```bash
# Quick test
python -m simple_evals.simple_evals \
  --eval=healthbench \
  --model=gpt-4o-mini \
  --max_examples=50
```

### Phase 2: Custom Sampler (Next)
1. **Implement ChatCompletionSampler for our DSPy agent**
2. **Run through HealthBench evaluation**
3. **Compare against baseline**

```python
class DSPySampler(SamplerBase):
    def __init__(self, agent):
        self.agent = agent

    def __call__(self, messages: MessageList) -> str:
        # Convert messages to agent format
        # Get agent response
        return self.agent.respond(messages)
```

### Phase 3: Rubric Analysis (Future)
1. **Analyze rubric criteria** our agent fails on
2. **Enhance agent** to address weak areas
3. **Implement uncertainty-aware rubric scoring**

## Implementation Checklist

- [x] Clone simple-evals repository
- [ ] Install minimal dependencies (blobfile, pandas, openai)
- [ ] Test CLI evaluation with gpt-4o-mini
- [ ] Understand rubric structure and grading
- [ ] Implement sampler for our DSPy agent
- [ ] Run evaluation on subset
- [ ] Implement custom metrics (confidence, reasoning quality)
- [ ] Analyze failure cases

## Minimal Dependencies for API-Only

### MUST INSTALL:
```txt
# Core dependencies
openai>=1.0.0
anthropic>=0.25.0  # Optional, if using Claude
blobfile>=2.0.0    # For fetching data
pandas>=2.0.0
numpy>=1.24.0

# No need for:
# - torch
# - transformers
# - Any CUDA/GPU libraries
```

### Installation
```bash
cd benchmarks/simple-evals
pip install openai anthropic blobfile pandas numpy
```

## HealthBench Specifics

### Evaluation Metrics
1. **Primary**: Percentage of rubric criteria met
2. **By Category**: Emergency, Clinical Data, Global Health, etc.
3. **By Dimension**: Accuracy, Communication, Instruction Following

### Grading System
- Uses **GPT-4** as auto-grader by default
- Each rubric item: binary pass/fail
- Points: Positive (criteria met) or negative (undesirable behavior)
- Final score: Sum of points / total possible points

### Data Subsets
- **HealthBench**: Full 5,000 conversations
- **HealthBench Consensus**: High physician agreement cases
- **HealthBench Hard**: More challenging cases

## Rubric Example Structure
```json
{
  "conversation_id": "...",
  "messages": [
    {"role": "user", "content": "I have chest pain..."},
    {"role": "assistant", "content": "..."}
  ],
  "rubric": [
    {
      "criteria": "Recommends seeking emergency care",
      "description": "...",
      "points": 5
    },
    {
      "criteria": "Provides reassurance without assessment",
      "description": "...",
      "points": -3
    }
  ]
}
```

## Notes
- ✅ **100% API-based** - no local models needed
- ✅ Data fetched via HTTPS - no manual download
- ✅ Grading uses API (GPT-4 by default)
- ⚠️ Can be **expensive** - 5,000 cases × 2 API calls (completion + grading)
- 💡 **Recommendation**: Start with `--max_examples=50` for testing
- 🎯 **Best for**: Evaluating conversational quality and medical accuracy
- 📊 **Output**: Detailed rubric-level scores + aggregate metrics
