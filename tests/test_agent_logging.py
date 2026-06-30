import csv
import json
import threading

from src.agent.logging import AgentRunLogger


def test_agent_logger_saves_visualization_sections_atomically(tmp_path):
    path = tmp_path / "run.json"
    logger = AgentRunLogger(
        model="test-model",
        path=path,
        agent_name="doctor",
        patient_id="patient-1",
        problem={"prompt": "diagnose"},
        environment={"patient": {"age": 42}},
    )

    messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "input"},
    ]
    logger.start_agent_run(messages, run_name="doctor_api")
    logger.llm_turn(
        0,
        {
            "role": "assistant",
            "content": "REQUEST TEST: CBC",
            "usage": {"input_tokens": 3, "output_tokens": 4, "total_tokens": 7},
        },
        input_messages=messages,
    )
    logger.tool_call(0, {"function": {"name": "bash"}}, {"content": "ok"})
    logger.doctor_turn(
        inference=0,
        task={"goal": "diagnose"},
        environment_source="patient",
        environment_response="I feel tired.",
        doctor_response="REQUEST TEST: CBC",
        doctor_message="REQUEST TEST: CBC",
    )
    logger.highlight("doctor_response", data={"message": "REQUEST TEST: CBC"})
    logger.update_task_result({"correct": True})
    logger.save()

    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["schema_version"] == "agent_run_logger.v2"
    assert saved["task_visualization"]["metadata"]["patient_id"] == "patient-1"
    assert saved["agent_visualization"]["agent_system_prompt"] == "system prompt"
    assert saved["agent_visualization"]["runs"][0]["turns"][0]["tool_calls"]
    assert saved["doctor_visualization"]["turns"][0]["doctor_message"] == "REQUEST TEST: CBC"
    assert saved["doctor_visualization"]["turns"][0]["doctor_response"] == "REQUEST TEST: CBC"
    assert saved["doctor_visualization"]["turns"][0]["environment_source"] == "patient"
    assert saved["highlight_visualization"]["highlights"][0]["kind"] == "doctor_response"
    assert saved["meta"]["token_usage"]["total_tokens"] == 7


def test_agent_logger_writes_task_results_to_csv(tmp_path):
    csv_path = tmp_path / "results.csv"
    logger = AgentRunLogger(
        model="test-model",
        path=tmp_path / "run.json",
        result_csv_path=csv_path,
    )

    logger.update_task_result(
        {
            "scenario_id": 1,
            "correct": True,
            "dialogue_history": ["Doctor: hi", "Patient: hello"],
        }
    )

    rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
    assert rows == [
        {
            "scenario_id": "1",
            "correct": "True",
            "dialogue_history": '["Doctor: hi", "Patient: hello"]',
        }
    ]


def test_agent_logger_handles_parallel_events(tmp_path):
    logger = AgentRunLogger(model="test-model", path=tmp_path / "parallel.json")

    def write_events(worker_id):
        for index in range(20):
            logger.event("worker_event", worker_id=worker_id, index=index)

    threads = [
        threading.Thread(target=write_events, args=(worker_id,))
        for worker_id in range(5)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    logger.save()
    saved = json.loads(logger.path.read_text(encoding="utf-8"))
    events = [
        event for event in saved["raw_trajectory"]
        if event["event"] == "worker_event"
    ]
    assert len(events) == 100


def test_agent_logger_keeps_parallel_runs_separate(tmp_path):
    logger = AgentRunLogger(model="test-model", path=tmp_path / "parallel-runs.json")
    barrier = threading.Barrier(2)

    def write_run(name):
        messages = [
            {"role": "system", "content": f"{name} system"},
            {"role": "user", "content": f"{name} input"},
        ]
        run_id = logger.start_agent_run(messages, run_name=name)
        barrier.wait()
        logger.llm_turn(
            0,
            {"role": "assistant", "content": f"{name} output"},
            input_messages=messages,
            run_id=run_id,
        )
        logger.finish_agent_run(
            result={"content": f"{name} result"},
            run_id=run_id,
        )

    threads = [
        threading.Thread(target=write_run, args=("first",)),
        threading.Thread(target=write_run, args=("second",)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    saved = logger.snapshot()
    outputs_by_run = {
        run["run_name"]: run["turns"][0]["output"]["content"]
        for run in saved["agent_visualization"]["runs"]
    }
    assert outputs_by_run == {
        "first": "first output",
        "second": "second output",
    }
