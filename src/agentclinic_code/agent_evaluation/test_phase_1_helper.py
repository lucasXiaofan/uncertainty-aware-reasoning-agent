#!/usr/bin/env python3
"""Run the phase-1 helper on one saved AgentClinic log."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from phase_1_evaluation import evaluate_and_save_phase_1_result


LOG_PATH = (
    Path(__file__).resolve().parents[1]
    / "two_phased_agent"
    / "log"
    / "mimic_training_20260623_173501_21823_case_1.json"
)


def osce_note_to_string(osce_note: Any) -> str:
    if isinstance(osce_note, str):
        return osce_note
    if not isinstance(osce_note, dict):
        return json.dumps(osce_note, ensure_ascii=False, indent=2)

    sections = []
    for key, value in osce_note.items():
        if key == "differential_diagnosis_list":
            continue
        label = key.replace("_", " ")
        if isinstance(value, list):
            text = "\n".join(str(item) for item in value)
        else:
            text = str(value)
        if text.strip():
            sections.append(f"{label}:\n{text}")
    return "\n\n".join(sections)


def main() -> None:
    log_data = json.loads(LOG_PATH.read_text(encoding="utf-8"))
    result = log_data["task_visualization"]["result"]

    patient_id = result["patient_id"]
    experiment_id = result["experiment_id"]
    osce_note = osce_note_to_string(result["osce_note"])
    differential_diagnosis_list = result["differential_diagnosis_list"]

    print(f"patient_id: {patient_id}")
    print(f"experiment_id: {experiment_id}")
    print("osce_note:")
    print(osce_note)
    print("differential_diagnosis_list:")
    print(differential_diagnosis_list)

    record = evaluate_and_save_phase_1_result(
        patient_id,
        experiment_id,
        osce_note,
        differential_diagnosis_list,
    )
    print("saved evaluation record:")
    print(json.dumps(record, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
