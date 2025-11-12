# Instructions Directory

This directory contains detailed analysis and implementation plans for running medical diagnostic benchmarks using **API-only approaches** (no GPU/CUDA required).

## 📚 Document Overview

### [00_benchmark_summary.md](00_benchmark_summary.md) - START HERE ⭐
Quick reference comparing all three benchmarks with:
- API support status
- Implementation difficulty
- Cost estimates
- Recommended order
- Common pitfalls
- Quick setup commands

### [01_agentclinic_analysis.md](01_agentclinic_analysis.md)
**AgentClinic** - Simulated clinical environment benchmark
- Architecture overview
- Data format (JSONL with OSCE structure)
- API-only setup (✅ native support)
- Integration options (CLI wrapper, import, data-only)
- Implementation checklist

### [02_mediq_analysis.md](02_mediq_analysis.md)
**MediQ** - Interactive question-asking benchmark
- Expert/Patient system architecture
- Data format (initial_info + context)
- API-only setup (✅ use `--use_api openai`)
- How to avoid GPU dependencies
- Expert class implementation guide

### [03_healthbench_analysis.md](03_healthbench_analysis.md)
**HealthBench** - Conversational quality benchmark
- Rubric-based evaluation system
- Data fetching from Azure
- API-only setup (✅ fully native)
- Sampler implementation
- Rubric grading system

### [04_implementation_roadmap.md](04_implementation_roadmap.md)
**4-Week Implementation Plan**
- Week-by-week breakdown
- Daily tasks with code examples
- Testing and validation steps
- Troubleshooting guide
- Success metrics and deliverables

## 🚀 Quick Start

### 1. Read the Summary
```bash
cat instructions/00_benchmark_summary.md
```

### 2. Choose Your Benchmark
- **Starting out?** → AgentClinic (easiest)
- **Testing interactions?** → MediQ (medium)
- **Comprehensive eval?** → HealthBench (most thorough)

### 3. Follow the Roadmap
```bash
cat instructions/04_implementation_roadmap.md
```

## 🎯 Key Findings

### All Three Benchmarks Support API-Only! ✅

| Benchmark | Command Flag | Dependencies |
|-----------|-------------|--------------|
| AgentClinic | `--inf_type llm` | openai, anthropic |
| MediQ | `--use_api openai` | openai |
| HealthBench | (native) | openai, blobfile |

### No GPU/CUDA Required! ❌

Skip these dependencies:
- `pytorch` with CUDA
- `vllm`
- `transformers` (unless using for utilities)
- Any `cuda-*` packages

### Estimated Costs 💰

- AgentClinic: $1-20 for 100 cases
- MediQ: $2.50-5 for 50 cases
- HealthBench: $10-30 for 100 cases

**Total**: ~$15-55 for initial comprehensive evaluation

## 📋 Implementation Checklist

### Pre-Setup
- [x] Clone benchmark repositories
- [ ] Install minimal dependencies
- [ ] Configure API keys in `.env`
- [ ] Test baseline agent

### AgentClinic (Week 1)
- [ ] Load and parse JSONL data
- [ ] Run agent on sample cases
- [ ] Implement evaluation metrics
- [ ] Full evaluation run (50+ cases)
- [ ] Results analysis

### MediQ (Week 2)
- [ ] Test patient simulator with API
- [ ] Implement Expert class wrapper
- [ ] Integration test
- [ ] Interactive evaluation (20+ cases)
- [ ] Question quality analysis

### HealthBench (Week 3)
- [ ] Test simple-evals CLI
- [ ] Implement custom sampler
- [ ] Run evaluation (50+ cases)
- [ ] Analyze rubric failures
- [ ] Agent enhancement

### Integration (Week 4)
- [ ] Unified evaluation script
- [ ] Comparative analysis
- [ ] Documentation updates
- [ ] Results report

## 🔧 Common Commands

### AgentClinic
```bash
python run_baseline.py --benchmark agentclinic --limit 50
```

### MediQ
```bash
cd benchmarks/mediQ
python src/mediQ_benchmark.py \
  --use_api openai \
  --patient_model gpt-4o-mini \
  --expert_model gpt-4o-mini \
  --max_questions 10
```

### HealthBench
```bash
cd benchmarks/simple-evals
python -m simple_evals.simple_evals \
  --eval=healthbench \
  --model=gpt-4o-mini \
  --max_examples=50
```

## 📊 Expected Outputs

### AgentClinic Results
```json
{
  "benchmark": "AgentClinic",
  "accuracy": 0.65,
  "confidence": 0.72,
  "total_cases": 50,
  "detailed_results": [...]
}
```

### MediQ Results
```json
{
  "benchmark": "MediQ",
  "accuracy": 0.58,
  "avg_questions": 6.2,
  "total_cases": 20,
  "question_quality_score": 0.75
}
```

### HealthBench Results
```json
{
  "benchmark": "HealthBench",
  "overall_score": 0.42,
  "rubric_compliance": 0.68,
  "total_conversations": 50,
  "by_category": {...}
}
```

## 🐛 Troubleshooting

### Issue: "Module not found"
**Solution**: Check PYTHONPATH
```bash
export PYTHONPATH=$PYTHONPATH:./benchmarks/mediQ/src
```

### Issue: "CUDA not available" (MediQ)
**Solution**: Use API mode
```bash
--use_api openai --use_vllm False
```

### Issue: "Rate limit exceeded"
**Solution**: Add delays or use exponential backoff
```python
import time
time.sleep(1)  # Between API calls
```

## 📚 Additional Resources

### Benchmark Papers
- [AgentClinic](https://arxiv.org/abs/2405.07960)
- [MediQ](https://arxiv.org/abs/2406.00922)
- [HealthBench](https://openai.com/index/healthbench)

### API Documentation
- [OpenAI API](https://platform.openai.com/docs)
- [Anthropic API](https://docs.anthropic.com)
- [DSPy Documentation](https://dspy.ai)

## 🤝 Contributing

Found issues or improvements? Update these documents:
1. Fix in corresponding markdown file
2. Test the instructions
3. Update checklist if needed

## ❓ Questions

For questions about:
- **Benchmark setup**: See individual analysis files
- **API configuration**: Check `00_benchmark_summary.md`
- **Implementation details**: See `04_implementation_roadmap.md`
- **Costs and budgets**: See summary file section

---

**Last Updated**: November 2025

**Status**: Ready for implementation ✅
