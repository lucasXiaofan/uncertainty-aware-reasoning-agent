# AgentClinic Evaluation Data Preparation

This folder contains the first evaluation-prep step: turning source OSCE cases
into structured phase-1 ground-truth fact lists.

## 1. Add stable patient IDs

```bash
python3 src/agentclinic_code/agent_evaluation/assign_mimic_patient_ids.py
```

This updates `data/mimic_training.jsonl` and `data/mimic_testing.jsonl` in place
with a top-level `patient_id`. IDs are derived from the matching source line in
`data/agentclinic_mimiciv.jsonl`, for example `mimic_0004`.

## 2. Generate phase-1 ground truth

```bash
python3 src/agentclinic_code/agent_evaluation/generate_phase_1_ground_truth.py --overwrite
```

The generator uses `phase_1_evaluation_prompt.md` and the shared
`call_openai_structured_json` helper at `src/agent/openai_llm_calling_core.py`.
The default output is:

```text
src/agentclinic_code/agent_evaluation/mimic_phase1_evaluation.json
```

Each output row has the same top-level `patient_id` followed by the prompt's
ground-truth JSON fields.

## 3. Evaluate an experiment

```bash
python3 src/agentclinic_code/agent_evaluation/phase_1_evaluation.py \
  --experiment_id <experiment_id> \
  --log_dir src/agentclinic_code/two_phased_agent/log
```

This reads logs with matching metadata, extracts each OSCE note and differential
list, compares them to the phase-1 ground truth with
`call_openai_structured_json`, and writes detailed reasoning plus
experiment-level scores. By default it also adds the evaluation result back into
each matching log under `evaluation` and `task_visualization.evaluation`, so the
two-phase visualizer can display the scores. Use `--no_update_logs` to disable
in-place log updates.

To evaluate and append one case directly:

```python
from src.agentclinic_code.agent_evaluation.phase_1_evaluation import evaluate_and_save_phase_1_result

record = evaluate_and_save_phase_1_result(
    patient_id,
    experiment_id,
    osce_note,
    differential_diagnosis_list,
)
```

This appends to
`src/agentclinic_code/agent_evaluation/phase_1_evaluation_results/phase_1_evaluation_results.json`.
