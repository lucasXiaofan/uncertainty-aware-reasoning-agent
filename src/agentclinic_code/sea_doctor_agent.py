"""
SEA-memory doctor agent for AgentClinic (env-toggled).

Pass this file to run_experiment_selected.sh via:
    --custom_doctor_agent_path src/agentclinic_code/sea_doctor_agent.py

Modes
-----
- Baseline (default): with no env vars set, this agent behaves exactly like the
  built-in DoctorAgent. SEA is never imported and nothing is read from disk.
- Dual-memory (Option 2): set the env vars below to recall past cases + distilled
  rules from a SEA DualMemory state file. The recalled context is injected into the
  system prompt; all reasoning / structured-output / token-tracking logic is reused
  unchanged from the built-in agent, so any accuracy delta is attributable to memory.

      SEA_MEMORY_ENABLED   "1"/"true"/"yes"/"on" turns recall on (default off).
      SEA_MEMORY_STATE     ABSOLUTE path to sea_state.json (built by build_experience.py).
      SEA_PATH             (optional) path to the SEA package; defaults to ../../../SEA.

The agent is strictly READ-ONLY on the state file (the live runner fans out parallel
worker processes; writing is done separately, single-process, by build_experience.py).
Any memory error degrades silently to the baseline so a bad path never breaks a run.

The loader (agentclinic_api_only.py) injects these module globals before exec, so
they are available without importing anything:
    query_model, DoctorAgentBase (the built-in DoctorAgent), CODE_DIR, DATA_DIR.
The loader accepts a class named CustomDoctorAgent or DoctorAgent.
"""

import os
import sys

_TRUTHY = {"1", "true", "yes", "on"}


def _memory_enabled() -> bool:
    return os.environ.get("SEA_MEMORY_ENABLED", "").strip().lower() in _TRUTHY


def _sea_dir() -> str:
    """Locate the SEA dual-memory library: SEA_PATH env override, else the
    vendored copy in ./sea_memory (bundled so a fresh clone works)."""
    env = os.environ.get("SEA_PATH")
    if env:
        return os.path.abspath(env)
    base = globals().get("CODE_DIR") or os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(base, "sea_memory"))


def _log(msg: str) -> None:
    print("[sea_doctor_agent] " + msg, file=sys.stderr)


def _format_memory_context(res: dict) -> str:
    """Render DualMemory.list() output into a compact prompt block."""
    rules = (res or {}).get("rules", []) or []
    cases = (res or {}).get("cases", []) or []
    if not rules and not cases:
        return "(no relevant prior experience yet)"

    lines = []
    if rules:
        lines.append("Learned rules:")
        for r in rules:
            text = str(r.get("text", "")).strip()
            if not text:
                continue
            lines.append("- {} (support {})".format(text, r.get("support", 1)))
    if cases:
        lines.append("Similar past cases:")
        for c in cases:
            summ = str(c.get("case_summary", "")).strip().replace("\n", " ")
            dx = str(c.get("diagnosis", "")).strip()
            outcome = "correct" if c.get("correct") else "incorrect"
            lines.append("- {} -> predicted {!r} ({})".format(summ[:200], dx, outcome))
    return "\n".join(lines)


class CustomDoctorAgent(DoctorAgentBase):  # noqa: F821 - injected by the loader
    """Built-in DoctorAgent + optional read-only SEA dual-memory recall."""

    def __init__(self, scenario, backend_str="gpt-5-nano", max_infs=20,
                 bias_present=None, img_request=False) -> None:
        # super().__init__ calls self.reset(), which sets self._mem_ctx = None.
        super().__init__(scenario, backend_str, max_infs, bias_present, img_request)
        self._mem = None
        self._setup_memory()

    def _setup_memory(self) -> None:
        """Load the SEA memory read-only if enabled. Never raises."""
        if not _memory_enabled():
            return
        try:
            state = os.environ.get("SEA_MEMORY_STATE", "").strip()
            if not state or not os.path.isfile(state):
                _log("memory unavailable (SEA_MEMORY_STATE not found: {!r}); using baseline".format(state))
                return
            sea = _sea_dir()
            if sea not in sys.path:
                sys.path.insert(0, sea)
            from memory import DualMemory  # SEA, stdlib-only
            self._mem = DualMemory.load(state)
            _log("memory loaded ({} cases / {} rules) from {}".format(
                len(self._mem.short_term), len(self._mem.long_term), state))
        except Exception as exc:  # pragma: no cover - safety net
            self._mem = None
            _log("memory unavailable ({}); using baseline".format(exc))

    def _recall(self) -> str:
        """Compute the recalled context once per case (cached, cleared by reset())."""
        if self._mem is None:
            return ""
        if self._mem_ctx is None:
            try:
                res = self._mem.list(query=str(self.presentation), n_cases=5, n_rules=5)
                self._mem_ctx = _format_memory_context(res)
            except Exception as exc:  # pragma: no cover - safety net
                _log("recall failed ({}); using baseline for this case".format(exc))
                self._mem_ctx = ""
        return self._mem_ctx

    def system_prompt(self) -> str:
        base = super().system_prompt()
        if self._mem is None:
            return base
        ctx = self._recall()
        if not ctx:
            return base
        return base + (
            "\n\n## CLINICAL MEMORY - hints from past cases\n"
            "Treat these as hints only; reason from the current case first and do not "
            "quote any case ids in your response.\n" + ctx
        )

    def reset(self) -> None:
        super().reset()
        self._mem_ctx = None


DoctorAgent = CustomDoctorAgent
