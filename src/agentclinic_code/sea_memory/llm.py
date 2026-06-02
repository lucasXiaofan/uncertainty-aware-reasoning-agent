"""The single LLM seam for the SEA dual-memory module.

Consolidation (distilling evicted cases into reusable rules) is the only
LLM-dependent step. It sits behind the ``RuleSummarizer`` Protocol so the whole
module runs fully offline with the deterministic ``MockSummarizer`` default, and
a real model drops in via ``InjectedSummarizer`` (you supply a ``chat_fn``) with
no vendor SDK bundled here.

``normalize_rule_text`` is the single canonical normalizer shared by the mock
and by ``DualMemory.consolidate`` so deduplication is consistent everywhere.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Callable, Protocol, runtime_checkable

if TYPE_CHECKING:  # avoid a runtime import cycle with memory.py
    from memory import CaseRecord, Rule


def normalize_rule_text(text: str) -> str:
    """Canonical form for rule dedup: lowercase, whitespace-collapsed, depunctuated."""
    collapsed = re.sub(r"\s+", " ", text.strip().lower())
    return collapsed.strip(" .!?,;:")


@runtime_checkable
class RuleSummarizer(Protocol):
    """Turns a batch of evicted cases into zero or more rule strings."""

    def summarize(self, cases: list["CaseRecord"], existing_rules: list["Rule"]) -> list[str]:
        ...


class MockSummarizer:
    """Deterministic, offline distiller — the default. No network, no deps.

    Emits ONE merged rule per batch (exercising the real many->few contraction),
    plus a failure-pattern rule when any case has ``correct is False``. Any rule
    whose normalized text already exists in ``existing_rules`` is skipped.
    """

    def summarize(self, cases: list["CaseRecord"], existing_rules: list["Rule"]) -> list[str]:
        candidate_rules: list[str] = []

        diagnoses = sorted({c.diagnosis for c in cases if c.diagnosis})
        if diagnoses:
            candidate_rules.append(
                "Diagnostic association: cases like these were labeled "
                + ", ".join(diagnoses)
                + "."
            )
        else:
            candidate_rules.append(
                f"Reviewed {len(cases)} case(s) with no recorded diagnosis."
            )

        wrong = sorted({c.diagnosis for c in cases if c.correct is False and c.diagnosis})
        if wrong:
            candidate_rules.append(
                "Failure pattern: predictions of "
                + ", ".join(wrong)
                + " were incorrect; re-examine before committing."
            )

        seen = {normalize_rule_text(r.text) for r in existing_rules}
        out: list[str] = []
        for text in candidate_rules:
            norm = normalize_rule_text(text)
            if norm and norm not in seen:
                seen.add(norm)
                out.append(text)
        return out


_DEFAULT_PROMPT_TEMPLATE = """\
You distill reusable diagnostic RULES from past clinical cases for a dual-memory
diagnostic agent. A rule is one concise, generalizable sentence: a symptom-disease
association, a discriminative cue, or a failure pattern. Do not overfit to a single
patient and do not duplicate an existing rule.

EXISTING RULES (do not duplicate):
{existing_rules}

EVICTED CASES (summary | candidates | predicted | outcome | rationale):
{cases}

Return ONLY JSON of the form {{"rules": ["...", "..."]}} with at most {max_rules} rules.
"""


class InjectedSummarizer:
    """Real-LLM seam. You inject ``chat_fn(prompt: str) -> str``; no SDK imported here."""

    def __init__(self, chat_fn: Callable[[str], str], prompt_template: str | None = None):
        self.chat_fn = chat_fn
        self.prompt_template = prompt_template or _DEFAULT_PROMPT_TEMPLATE

    def build_prompt(
        self, cases: list["CaseRecord"], existing_rules: list["Rule"], max_rules: int
    ) -> str:
        rules_block = (
            "\n".join(f"{i+1}. {r.text}" for i, r in enumerate(existing_rules)) or "none"
        )
        cases_block = "\n".join(
            f"{i+1}. {c.case_summary} | {', '.join(c.candidates)} | {c.diagnosis} | "
            f"{c.feedback} | {c.reasoning}"
            for i, c in enumerate(cases)
        )
        return self.prompt_template.format(
            existing_rules=rules_block, cases=cases_block, max_rules=max_rules
        )

    def summarize(
        self,
        cases: list["CaseRecord"],
        existing_rules: list["Rule"],
        max_rules: int = 3,
    ) -> list[str]:
        prompt = self.build_prompt(cases, existing_rules, max_rules)
        raw = self.chat_fn(prompt)
        return self._parse(raw, max_rules)

    @staticmethod
    def _parse(raw: str, max_rules: int) -> list[str]:
        """Tolerant parse: strip code fences, try JSON, fall back to line split."""
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
            text = re.sub(r"\n?```$", "", text).strip()

        try:
            data = json.loads(text)
            if isinstance(data, dict) and isinstance(data.get("rules"), list):
                rules = [str(r).strip() for r in data["rules"] if str(r).strip()]
                return rules[:max_rules]
            if isinstance(data, list):
                rules = [str(r).strip() for r in data if str(r).strip()]
                return rules[:max_rules]
        except (json.JSONDecodeError, ValueError):
            pass

        lines = [ln.strip(" -*\t") for ln in text.splitlines()]
        return [ln for ln in lines if ln][:max_rules]
