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
cd src/agentclinic_code
./run_experiment_selected.sh --data_file agentclinic_mimiciv_false_cases_with_guidelines.jsonl --count 5
```

MIMIC data:
- JSONL files placed in `src/agentclinic_code/data` can be passed either as a basename such as `agentclinic_mimiciv.jsonl` or as a relative path such as `data/agentclinic_mimiciv.jsonl`.
- Filenames containing `mimiciv` are auto-detected as `MIMICIV`.

Optional:
- Slash-prefixed model ids such as `openai/...` still work if `OPENROUTER_API_KEY` is set.
