# Agentic Clinic Test Report

## Overview
Agentic Clinic contains several datasets for testing medical agents. The benchmark simulates a dialogue between a Doctor agent and a Patient agent, with a Measurement agent providing test results and a Moderator agent evaluating the diagnosis.

## Tests and Modalities

| Dataset | Number of Tests | Modality | Description |
| :--- | :--- | :--- | :--- |
| **MedQA** | 107 | Text | OSCE Examination format. Contains patient info, examiner info, physical exams, tests, and correct diagnosis. |
| **MedQA Extended** | 213 | Text | Extended version of MedQA with more scenarios. |
| **NEJM** | 14 | Text + Image | New England Journal of Medicine cases. Includes patient info, physical exams, and an image URL. |
| **NEJM Extended** | 119 | Text + Image | Extended version of NEJM cases. |

## Supported but Missing Data
- **MIMICIV**: The code contains a `ScenarioLoaderMIMICIV` class, but the corresponding data file `agentclinic_mimiciv.jsonl` is not present in the `benchmarks/AgentClinic` directory.

## Configuration
The benchmark can be run with different LLMs for Doctor, Patient, Measurement, and Moderator agents.
The default configuration uses `gpt4`.
Support for `gpt-5-mini` has been added to the codebase.
