# Benchmark Setup Summary - API-Only Approach

## Executive Summary

All three benchmarks (AgentClinic, MediQ, HealthBench) **support API-only execution**! You don't need GPU, CUDA, or vLLM dependencies.

## Quick Comparison

| Benchmark | API Support | CUDA Required? | Difficulty | Best Approach |
|-----------|-------------|----------------|------------|---------------|
| **AgentClinic** | ✅ Native | ❌ No | Easy | Data-only wrapper |
| **MediQ** | ✅ Native (flag) | ❌ No | Medium | Implement Expert class |
| **HealthBench** | ✅ Native | ❌ No | Easy | Use simple-evals CLI |

## API-Only Dependencies

### Core (Already Have)
```txt
openai>=1.0.0
dspy-ai>=2.5.0
python-dotenv>=1.0.0
pydantic>=2.0.0
pyyaml>=6.0
pandas>=2.0.0
numpy>=1.24.0
```

### Benchmark-Specific
```txt
# For MediQ (if using their code)
# - No additional dependencies!

# For HealthBench
blobfile>=2.0.0     # For data fetching
anthropic>=0.25.0   # Optional, for Claude

# For AgentClinic (if using their simulation)
anthropic>=0.25.0   # Optional, for Claude
regex>=2023.12.25
```

## Dependencies to SKIP (GPU-Only)

```txt
# ❌ DO NOT INSTALL - Only for local GPU models
torch
pytorch
pytorch-cuda
cuda-*
cudnn
vllm
transformers  # Unless you want HuggingFace API usage
```

## Recommended Implementation Order

### Phase 1: AgentClinic (Week 1) ⭐ START HERE
**Why first?**
- Simplest integration
- Data already downloaded
- No additional dependencies
- Good for baseline establishment

**Implementation**:
1. ✅ Load JSONL data (already done)
2. Parse patient information
3. Run DSPy agent on cases
4. Calculate accuracy metrics
5. 🎯 **Target**: 50-100 cases evaluated

### Phase 2: MediQ (Week 2)
**Why second?**
- Interactive evaluation (good for multi-round testing)
- Tests question-asking ability
- Requires patient simulator

**Implementation**:
1. Configure API mode (`--use_api openai`)
2. Implement simple patient simulator OR use theirs
3. Integrate DSPy agent as Expert class
4. Run evaluation on subset
5. 🎯 **Target**: 20-50 interactive cases

### Phase 3: HealthBench (Week 3)
**Why third?**
- Most comprehensive evaluation
- Tests conversational quality
- Requires rubric-based grading

**Implementation**:
1. Install blobfile for data access
2. Test CLI with baseline model
3. Implement sampler wrapper for DSPy agent
4. Run on subset (start with 50 cases)
5. 🎯 **Target**: 50-100 conversations evaluated

## API Costs Estimation

### AgentClinic (per case)
- **Single diagnosis**: 1 API call
- **Multi-agent simulation**: ~20 API calls
- **Cost**: $0.01 - $0.20 per case (with gpt-4o-mini)
- **100 cases**: ~$1-20

### MediQ (per case)
- **Interactive session**: 5-10 API calls (agent + patient)
- **Cost**: $0.05 - $0.10 per case
- **50 cases**: ~$2.50-5

### HealthBench (per case)
- **Completion**: 1 API call
- **Grading**: 1 API call per rubric item (~10-20 items)
- **Cost**: $0.10 - $0.30 per case
- **100 cases**: ~$10-30

**Total for initial evaluation**: ~$15-55 (assuming gpt-4o-mini)

## Setup Instructions

### 1. Update requirements.txt
```bash
# Already have most dependencies
# Add only these:
echo "blobfile>=2.0.0" >> requirements.txt
echo "anthropic>=0.25.0" >> requirements.txt  # Optional

pip install -r requirements.txt
```

### 2. Configure API Keys
```bash
# Update .env file
echo "OPENAI_API_KEY=your-key-here" >> .env
echo "ANTHROPIC_API_KEY=your-key-here" >> .env  # Optional
```

### 3. Test Each Benchmark

#### AgentClinic Test
```python
python run_baseline.py --benchmark agentclinic --config config.yaml
```

#### MediQ Test
```bash
cd benchmarks/mediQ
python src/mediQ_benchmark.py \
  --use_api openai \
  --patient_model gpt-4o-mini \
  --expert_model gpt-4o-mini \
  --max_questions 5 \
  --data_dir data \
  --dev_filename all_craft_md.jsonl
```

#### HealthBench Test
```bash
cd benchmarks/simple-evals
export OPENAI_API_KEY="your-key"
python -m simple_evals.simple_evals \
  --eval=healthbench \
  --model=gpt-4o-mini \
  --max_examples=10
```

## Key Insights from Analysis

### AgentClinic
- ✅ **Ready to use**: Just pass `--inf_type llm`
- ⚠️ Uses old OpenAI API (v0.28) - may need update
- 🎯 **Focus**: Diagnostic accuracy in simulated environment
- 📊 **Metrics**: Diagnosis match, bias effects

### MediQ
- ✅ **Has API mode**: Use `--use_api openai` flag
- ⚠️ environment.yml includes GPU deps (IGNORE them)
- 🎯 **Focus**: Question-asking efficiency and quality
- 📊 **Metrics**: Accuracy, # questions, question relevance

### HealthBench
- ✅ **API-native**: Designed for API-only execution
- ✅ **No setup needed**: Data fetched automatically
- 🎯 **Focus**: Conversational quality and safety
- 📊 **Metrics**: Rubric compliance (48K criteria)

## Common Pitfalls to Avoid

### ❌ DON'T
1. Install conda environment.yml from MediQ (has GPU deps)
2. Try to install vLLM (not needed)
3. Use HuggingFace local models (stick to APIs)
4. Run all benchmarks at once (start small)

### ✅ DO
1. Use API flags (`--use_api openai`, `--inf_type llm`)
2. Start with small subsets (10-50 cases)
3. Use gpt-4o-mini for cost efficiency
4. Track API costs carefully
5. Save intermediate results

## Next Steps

1. **Read detailed analyses**:
   - `01_agentclinic_analysis.md`
   - `02_mediq_analysis.md`
   - `03_healthbench_analysis.md`

2. **Choose implementation approach** for each benchmark

3. **Update config.yaml** with API-only settings

4. **Run pilot tests** (10 cases each)

5. **Iterate and expand** based on results

## Questions to Consider

### For AgentClinic
- Use full multi-agent simulation or just data?
- Which dataset: MedQA (USMLE) or NEJM (case reports)?
- Include bias evaluation?

### For MediQ
- Implement our own patient simulator or use theirs?
- Maximum questions allowed (trade-off: accuracy vs efficiency)?
- Which patient variant: InstructPatient or FactSelectPatient?

### For HealthBench
- Start with consensus set or full dataset?
- Custom grading or use default GPT-4 grader?
- Which conversation categories to focus on?

## Summary

🎉 **Good news**: All benchmarks work with API-only!

🚀 **Recommended path**:
1. AgentClinic (data-only) - Week 1
2. MediQ (API mode) - Week 2
3. HealthBench (CLI) - Week 3

💰 **Budget**: ~$50-100 for comprehensive initial evaluation

📊 **Output**: Baseline metrics for uncertainty-aware reasoning agent
