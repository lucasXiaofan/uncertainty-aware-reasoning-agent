import json

from src.agentclinic_code.two_phased_agent import two_agent_interface


class _Scenario:
    def examiner_information(self) -> str:
        return "Find the diagnosis."


class _FakeLogger:
    def __init__(self, path, run_index: int) -> None:
        self.path = path
        self.meta = {
            "model": "test-model",
            "started_at": f"start-{run_index}",
            "ended_at": f"end-{run_index}",
            "rounds": run_index + 1,
            "token_usage": {
                "input_tokens": 10,
                "cached_input_tokens": 1,
                "output_tokens": 2,
                "total_tokens": 12,
            },
            "expense_usd": 0.01,
        }
        self.raw_trajectory = [
            {
                "ts": f"start-{run_index}",
                "event": "run_start",
                "messages": [
                    {"role": "system", "content": "Shared prompt"},
                    *[
                        {"role": "user", "content": f"Response {index}"}
                        for index in range(run_index + 1)
                    ],
                ],
            },
            {"ts": f"turn-{run_index}", "event": "llm_turn", "round": 0},
        ]


class _FakeAgent:
    run_count = 0

    def __init__(self, working_memory, *, log_path, **kwargs) -> None:
        self.run_index = self.__class__.run_count
        self.__class__.run_count += 1
        self.logger = _FakeLogger(log_path, self.run_index)

    def run(self):
        self.logger.path.write_text(
            json.dumps(
                {
                    "meta": self.logger.meta,
                    "raw_trajectory": self.logger.raw_trajectory,
                }
            ),
            encoding="utf-8",
        )
        return {
            "content": json.dumps(
                {
                    "tool_name": "respond",
                    "content": {
                        "action": "ask_patient",
                        "message": f"Question {self.run_index}",
                    },
                }
            )
        }


def test_one_trajectory_file_contains_all_patient_inferences(tmp_path, monkeypatch):
    _FakeAgent.run_count = 0
    monkeypatch.setattr(two_agent_interface, "Agent", _FakeAgent)
    monkeypatch.setattr(two_agent_interface, "LOG_DIR", tmp_path)
    monkeypatch.setattr(two_agent_interface, "VISUALIZATION_LOG_DIR", tmp_path / "runs")

    doctor = two_agent_interface.CustomDoctorAgent(
        _Scenario(),
        backend_str="test-model",
    )

    assert doctor.inference_doctor("First response") == "Question 0"
    assert doctor.inference_doctor("Second response") == "Question 1"

    trajectory_files = list(tmp_path.glob("*.json"))
    assert trajectory_files == [doctor.trajectory_path]

    saved = json.loads(doctor.trajectory_path.read_text(encoding="utf-8"))
    assert len(saved["turns"]) == 2
    assert [turn["inference"] for turn in saved["turns"]] == [0, 1]
    assert [turn["doctor_message"] for turn in saved["turns"]] == [
        "Question 0",
        "Question 1",
    ]
    saved_messages = [
        message
        for turn in saved["turns"]
        for event in turn["raw_trajectory"]
        for message in event.get("messages", [])
    ]
    assert saved_messages == [
        {"role": "system", "content": "Shared prompt"},
        {"role": "user", "content": "Response 0"},
        {"role": "user", "content": "Response 1"},
    ]

    run_v1 = json.loads(doctor.run_v1_path.read_text(encoding="utf-8"))
    assert doctor.run_v1_path == tmp_path / "runs" / doctor.run_id / "run.v1.json"
    assert run_v1["protocol"] == "agent-observability"
    assert run_v1["metrics"]["invocation_count"] == 2
    assert [
        invocation["final_output"]["text"]
        for invocation in run_v1["agents"][0]["invocations"]
    ] == ["Question 0", "Question 1"]
