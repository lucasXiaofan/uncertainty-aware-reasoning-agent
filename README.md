# uncertainty-aware-reasoning-agent

## Overview

This repository implements and evaluates AI agents for medical diagnostic tasks, with a focus on:

- **Reasoning under uncertainty**: Handling incomplete or ambiguous medical information through probabilistic reasoning and confidence estimation
- **Experience-based learning**: Generating and utilizing memory from past cases to improve diagnostic accuracy
- **Multi-benchmark evaluation**: Testing across diverse medical diagnostic datasets (AgentClinic, MediQ, HealthBench, MAQuE)
- **Multi-round interaction**: Engaging in iterative diagnostic conversations to gather additional information and refine diagnoses
- **Tool usage for uncertainty reduction**: Leveraging external tools (medical databases, calculators, search) to reduce diagnostic uncertainty and validate hypotheses

## Benchmarks

The framework is designed to test against the following medical diagnostic benchmarks:

1. **AgentClinic** - Clinical decision-making scenarios (Need install github repo: https://github.com/SamuelSchmidgall/AgentClinic)
2. **MediQ** - Medical question answering (Need install github repo: https://github.com/stellalisy/mediQ)
3. **HealthBench** - Comprehensive health assessment tasks (Need install github repo: looking for healthbench: https://github.com/openai/simple-evals)
4. **MAQuE** - Medical Question Understanding and Evaluation (current no github available)

## Project Phases

### Phase 1: Baseline Implementation (Current) ✅
- Set up API-based agents using OpenAI API
- Implement DSPy React agent as baseline (https://dspy.ai/tutorials/customer_service_agent/)
- Establish evaluation metrics across benchmarks
- Create reproducible testing pipeline

## Quick Start

### Installation

```bash
# Clone and setup
git clone <your-repo-url>
cd uncertainty-aware-reasoning-agent

# Install dependencies
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure API key
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

### Run Example

```bash
# Test the baseline DSPy ReAct agent
python example_usage.py
```

### Run Evaluations

```bash
# Run baseline evaluation (after benchmark setup)
python run_baseline.py --benchmark all
```

For detailed setup instructions, see [SETUP.md](SETUP.md).

## Repository Structure

```
src/
├── agents/              # Agent implementations
│   ├── base_agent.py   # Abstract base class
│   └── dspy_react_agent.py  # DSPy ReAct baseline
├── benchmarks/          # Benchmark integrations
│   ├── base_benchmark.py
│   ├── agentclinic_wrapper.py
│   └── mediq_wrapper.py
└── utils/               # Utilities

config.yaml              # Configuration
requirements.txt         # Dependencies
example_usage.py        # Example script
run_baseline.py         # Main evaluation script
```
