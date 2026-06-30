# Two-Phase AgentClinic Visualization

The visualizer is a static HTML page at:

```text
src/agentclinic_code/two_phased_agent/visualization/index.html
```

It loads JSON logs from `src/agentclinic_code/two_phased_agent/log`. Each log is
one patient run. If `evaluate_experiment.py` has updated the log, the viewer
shows a `Phase-1 Evaluation` panel with diagnosis inclusion, total fact
coverage, section coverage, and fact-level reasons.

## 1. Run evaluation and update logs

```bash
uv run --with 'openai>=1.0.0' --with python-dotenv python \
  src/agentclinic_code/agent_evaluation/evaluate_experiment.py \
  --experiment_id mimic_training_20260623_173501_21823 \
  --log_dir src/agentclinic_code/two_phased_agent/log
```

By default this writes:

```text
src/agentclinic_code/agent_evaluation/<experiment_id>_reasoning_evaluation.jsonl
src/agentclinic_code/agent_evaluation/<experiment_id>_summary.json
```

It also updates every matching log JSON in place by adding:

```text
evaluation
task_visualization.evaluation
```

Pass `--no_update_logs` only when you want standalone evaluation files without
changing the run logs.

## 2. Serve the viewer for an existing experiment

```bash
uv run src/agentclinic_code/two_phased_agent/run_visualized.py \
  --experiment_id mimic_training_20260623_173501_21823 \
  --log_dir src/agentclinic_code/two_phased_agent/log \
  --serve
```

The script prints one viewer URL containing all logs for that experiment. Open
that URL in a browser. The sidebar lets you switch patient runs.

## 3. Check the evaluation in the UI

In either `Developer View` or `Doctor View`, look for the `Phase-1 Evaluation`
panel near the top. If the panel is absent, the selected log has not been
evaluated yet or the log does not contain the `evaluation` field.

You can also load the viewer manually:

```text
http://127.0.0.1:8765/src/agentclinic_code/two_phased_agent/visualization/index.html?logDir=/src/agentclinic_code/two_phased_agent/log/
```

