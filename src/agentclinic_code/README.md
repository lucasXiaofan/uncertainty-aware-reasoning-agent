# AgentClinic Code

This directory is a self-contained AgentClinic runner extracted into `src/agentclinic_code`.

Defaults:
- API provider: `OPENAI_API_KEY`
- Model for doctor, patient, measurement, moderator, and uncertainty-aware runtime: `gpt-5-nano`
- Data directory: `src/agentclinic_code/data`
- Results directory: `src/agentclinic_code/results`

Example:

```bash
export OPENAI_API_KEY=your_key_here
bash src/agentclinic_code/run_experiment_selected.sh \
  --patient_csv src/agentclinic_code/data/mimic_testing.jsonl \
  --folder mimic_test_run \
  --num_cases 5 \
  --workers 2 \
  --custom_doctor_agent_path src/agentclinic_code/two_phased_agent/two_agent_interface.py
```

Input data:
- `agentclinic_api_only.py` now uses one loader for OSCE-format JSONL files.
- Each line must contain `OSCE_Examination` with `Objective_for_Doctor`, `Patient_Actor`, `Physical_Examination_Findings`, `Test_Results`, and `Correct_Diagnosis`.
- Files can be passed as absolute paths, paths relative to the repository root, or basenames under `src/agentclinic_code/data`.
- `--patient_csv` is the runner input flag name, but the expected file format is JSONL.

Runner options:
- `--patient_csv`: OSCE JSONL input file.
- `--folder`: output folder under `src/agentclinic_code/results`.
- `--num_cases`: number of cases to run from the start of the file.
- `--workers`: number of parallel case workers.
- `--custom_doctor_agent_path`: optional doctor agent file or directory containing `two_agent_interface.py`.
- `--model`: model used for doctor, patient, measurement, and moderator.

Optional:
- Slash-prefixed model ids such as `openai/...` still work if `OPENROUTER_API_KEY` is set.

## Two-phase visualized runs

Run the two-phase doctor and generate a viewer-ready trajectory:

```bash
uv run python src/agentclinic_code/two_phased_agent/run_visualized.py \
  --patient_csv src/agentclinic_code/data/mimic_testing.jsonl \
  --num_scenarios 1 \
  --scenario_offset 0 \
  --serve
```

Each run writes:

- legacy trajectory: `src/agentclinic_code/two_phased_agent/trajectory/agentclinic_*.json`
- visualization payload: `logs/agentclinic/<run_id>/run.v1.json`

The wrapper prints a URL like:

```text
http://127.0.0.1:8765/src/agentclinic_code/two_phased_agent/visualization/index.html?run=/logs/agentclinic/<run_id>/run.v1.json
```

Without `--serve`, start a server yourself from the repository root:

```bash
python3 -m http.server 8765
```
