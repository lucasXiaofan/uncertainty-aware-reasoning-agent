# uncertainty-aware-reasoning-agent

## Current Focus

This repository is currently focused on OSCE-style multi-round medical diagnosis with:

- a **doctor agent**
- a **patient agent**
- a **measurement/examination agent**

The current main setting is **MIMIC-style data**. The patient generation and interaction logic are derived from **AgentClinic**, then adapted for more challenging MIMIC-like cases.

The active goal is to build an **agentic learning loop** where an LLM:

1. runs on training cases,
2. generates useful experience from those cases,
3. uses those learned experiences to improve on unseen test cases,
4. especially when test patients have similar diagnoses or similar clinical patterns.

## Project History

The direction of the project changed over time:

- Earlier work explored **single-agent** and **multi-agent** approaches on **MediQ**.
- That line was stopped because **MediQ mixes subjective and objective QA together**, which made it a weaker fit for the kind of iterative diagnostic interaction we want.
- The work then moved to **AgentClinic** with **MedQA-style** data.
- The current emphasis is **MIMIC-style data**, because it is more challenging and gives better opportunities to create clinically similar patients for transfer and experience-based improvement.

## Current Behavior

The measurement agent has been adjusted so that when the doctor asks for an examination or test that is **not present in the provided case information**, it returns:

`Test unavailable`

instead of inventing or implying normal findings. This is intended to reduce misleading signals to the doctor agent.

## Main Code

The main working code is under `src/`.

For the current runnable AgentClinic-based setup, use:

- [src/agentclinic_code/README.md](/Users/xiaofanlu/Documents/github_repos/uncertainty-aware-reasoning-agent/src/agentclinic_code/README.md)

That README contains the quickest way to run an experiment.

## Quick Pointer

If you want to run a quick experiment, start in:

```bash
cd src/agentclinic_code
```

and follow the instructions in `src/agentclinic_code/README.md`.
