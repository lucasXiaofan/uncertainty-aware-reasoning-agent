"""Run the two-phased AgentClinic agent and emit viewer-ready trajectories."""

from __future__ import annotations

import argparse
import os
import sys
from functools import partial
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CODE_DIR = PROJECT_ROOT / "src" / "agentclinic_code"
DOCTOR_AGENT_PATH = CODE_DIR / "two_phased_agent" / "two_agent_interface.py"
VISUALIZATION_INDEX = (
    PROJECT_ROOT / "src" / "agentclinic_code" / "two_phased_agent" / "visualization" / "index.html"
)
DEFAULT_LOG_DIR = CODE_DIR / "two_phased_agent" / "log"

if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

import agentclinic_api_only as agentclinic  # noqa: E402


def main() -> None:
    args = _parse_args()
    log_dir = Path(args.log_dir).expanduser().resolve()

    if not args.patient_csv:
        show_existing_logs(log_dir, args.experiment_id, args.port)
        if args.serve:
            serve(args.port)
        return

    before = _viewer_log_files(log_dir)
    output_file = Path(args.output_file) if args.output_file else None
    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    run_log_path = log_dir / f"{args.experiment_id or 'visualized_run'}.json"

    agentclinic.main(
        args.openai_api_key,
        "llm",
        args.doctor_bias,
        args.patient_bias,
        args.doctor_llm,
        args.patient_llm,
        args.measurement_llm,
        args.moderator_llm,
        args.num_scenarios,
        args.patient_csv,
        10,
        str(output_file) if output_file else None,
        args.scenario_offset,
        str(DOCTOR_AGENT_PATH),
        args.dataset_name,
        str(run_log_path),
        args.experiment_id,
    )

    created = [path for path in _viewer_log_files(log_dir) if path not in before]
    if not created:
        print(f"No new JSON log files found under {log_dir}")
        return

    print("\nViewer-ready trajectories:")
    for path in created:
        print(f"- {path}")
        print(f"  {viewer_url(path, args.port)}")

    if args.serve:
        serve(args.port)


def viewer_url(run_v1_path: Path, port: int) -> str:
    relative_run = "/" + run_v1_path.resolve().relative_to(PROJECT_ROOT).as_posix()
    relative_index = "/" + VISUALIZATION_INDEX.relative_to(PROJECT_ROOT).as_posix()
    return f"http://127.0.0.1:{port}{relative_index}?run={quote(relative_run)}"


def viewer_runs_url(paths: list[Path], port: int) -> str:
    relative_index = "/" + VISUALIZATION_INDEX.relative_to(PROJECT_ROOT).as_posix()
    runs = ",".join("/" + path.resolve().relative_to(PROJECT_ROOT).as_posix() for path in paths)
    return f"http://127.0.0.1:{port}{relative_index}?runs={quote(runs, safe=',/')}"


def show_existing_logs(log_dir: Path, experiment_id: str | None, port: int) -> None:
    paths = _experiment_files(log_dir, experiment_id) if experiment_id else _viewer_log_files(log_dir)
    if not paths:
        label = f" for experiment_id={experiment_id}" if experiment_id else ""
        print(f"No JSON log files found under {log_dir}{label}")
        return
    print("\nViewer URL:")
    print(viewer_runs_url(paths, port))
    print("\nLogs:")
    for path in paths:
        print(f"- {path}")


def serve(port: int) -> None:
    handler = partial(SimpleHTTPRequestHandler, directory=str(PROJECT_ROOT))
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    print(f"\nServing visualization at http://127.0.0.1:{port}/")
    print("Press Ctrl-C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped visualization server.")


def _viewer_log_files(log_dir: Path) -> set[Path]:
    if not log_dir.exists():
        return set()
    return set(log_dir.glob("*.json")) | set(log_dir.glob("*/run.v1.json"))


def _experiment_files(log_dir: Path, experiment_id: str | None) -> list[Path]:
    if not experiment_id:
        return sorted(_viewer_log_files(log_dir))
    matched = []
    for path in sorted(_viewer_log_files(log_dir)):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        metadata = data.get("task_visualization", {}).get("metadata", {})
        meta = data.get("meta", {})
        if metadata.get("experiment_id") == experiment_id or meta.get("experiment_id") == experiment_id:
            matched.append(path)
    return matched


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run AgentClinic with the two-phase doctor and generate "
            "viewer-ready JSON logs, or serve existing two-phase logs."
        )
    )
    parser.add_argument("--openai_api_key", default=os.environ.get("OPENAI_API_KEY"))
    parser.add_argument("--patient_csv", default=None)
    parser.add_argument("--dataset_name", default=None)
    parser.add_argument("--experiment_id", default=None)
    parser.add_argument("--log_dir", type=Path, default=DEFAULT_LOG_DIR)
    parser.add_argument("--num_scenarios", type=int, default=1)
    parser.add_argument("--scenario_offset", type=int, default=0)
    parser.add_argument("--doctor_llm", default="gpt-5-nano")
    parser.add_argument("--patient_llm", default="gpt-5-nano")
    parser.add_argument("--measurement_llm", default="gpt-5-nano")
    parser.add_argument("--moderator_llm", default="gpt-5-nano")
    parser.add_argument("--doctor_bias", default="None")
    parser.add_argument("--patient_bias", default="None")
    parser.add_argument(
        "--output_file",
        default=str(PROJECT_ROOT / "logs" / "agentclinic" / "results.jsonl"),
    )
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--port", type=int, default=8765)
    return parser.parse_args()


if __name__ == "__main__":
    main()
