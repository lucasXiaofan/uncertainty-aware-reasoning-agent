"""Run the two-phased AgentClinic agent and emit viewer-ready trajectories."""

from __future__ import annotations

import argparse
import os
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CODE_DIR = PROJECT_ROOT / "src" / "agentclinic_code"
DOCTOR_AGENT_PATH = CODE_DIR / "two_phased_agent" / "two_agent_interface.py"
VISUALIZATION_INDEX = (
    PROJECT_ROOT / "src" / "agentclinic_code" / "two_phased_agent" / "visualization" / "index.html"
)
RUN_LOG_DIR = PROJECT_ROOT / "logs" / "agentclinic"

if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

import agentclinic_api_only as agentclinic  # noqa: E402


def main() -> None:
    args = _parse_args()
    before = _run_v1_files()
    output_file = Path(args.output_file) if args.output_file else None
    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)

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
        args.agent_dataset,
        args.doctor_image_request,
        10,
        str(output_file) if output_file else None,
        args.scenario_offset,
        False,
        str(DOCTOR_AGENT_PATH),
        args.data_file,
    )

    created = [path for path in _run_v1_files() if path not in before]
    if not created:
        print(f"No new run.v1.json files found under {RUN_LOG_DIR}")
        return

    print("\nViewer-ready trajectories:")
    for path in created:
        print(f"- {path}")
        print(f"  {viewer_url(path, args.port)}")

    if args.serve:
        serve(args.port)


def viewer_url(run_v1_path: Path, port: int) -> str:
    relative_run = "/" + run_v1_path.relative_to(PROJECT_ROOT).as_posix()
    relative_index = "/" + VISUALIZATION_INDEX.relative_to(PROJECT_ROOT).as_posix()
    return f"http://127.0.0.1:{port}{relative_index}?run={quote(relative_run)}"


def serve(port: int) -> None:
    handler = partial(SimpleHTTPRequestHandler, directory=str(PROJECT_ROOT))
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    print(f"\nServing visualization at http://127.0.0.1:{port}/")
    print("Press Ctrl-C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped visualization server.")


def _run_v1_files() -> set[Path]:
    if not RUN_LOG_DIR.exists():
        return set()
    return set(RUN_LOG_DIR.glob("*/run.v1.json"))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run AgentClinic with the two-phase doctor and generate "
            "logs/agentclinic/<run_id>/run.v1.json for visualization."
        )
    )
    parser.add_argument("--openai_api_key", default=os.environ.get("OPENAI_API_KEY"))
    parser.add_argument("--agent_dataset", default="MIMICIV")
    parser.add_argument("--data_file", default=None)
    parser.add_argument("--num_scenarios", type=int, default=1)
    parser.add_argument("--scenario_offset", type=int, default=0)
    parser.add_argument("--doctor_llm", default="gpt-5-nano")
    parser.add_argument("--patient_llm", default="gpt-5-nano")
    parser.add_argument("--measurement_llm", default="gpt-5-nano")
    parser.add_argument("--moderator_llm", default="gpt-5-nano")
    parser.add_argument("--doctor_bias", default="None")
    parser.add_argument("--patient_bias", default="None")
    parser.add_argument("--doctor_image_request", action="store_true")
    parser.add_argument(
        "--output_file",
        default=str(PROJECT_ROOT / "logs" / "agentclinic" / "results.jsonl"),
    )
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--port", type=int, default=8765)
    return parser.parse_args()


if __name__ == "__main__":
    main()
