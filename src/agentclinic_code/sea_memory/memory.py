"""SEA dual-memory architecture.

Implements the dual-memory module from "Joint Optimization of Reasoning and
Dual-Memory for Self-Learning Diagnostic Agent" (arXiv 2604.07269v1):

    state s = (M^S, M^L)

    M^S  short-term case cluster   bounded, append-only list of CaseRecords (capacity K)
    M^L  long-term rule cluster    distilled Rules

The four agent operations map 1:1 to methods on ``DualMemory``:

    list        retrieve relevant cases + rules
    append      insert a case into M^S
    pop         evict & return cases from M^S
    consolidate distill evicted cases into rules in M^L

This module is the memory mechanics only; there is no RL training, no reward
surface, and no network/third-party dependency. Pure standard library.
"""

from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass, field
from uuid import uuid4

from llm import MockSummarizer, RuleSummarizer, normalize_rule_text

_STOPWORDS = {
    "the", "a", "an", "of", "and", "or", "to", "in", "with",
    "is", "was", "for", "on", "at", "by", "as",
}


def _tokenize(text: str) -> set[str]:
    """Lowercase word tokens with a tiny stopword set removed."""
    return {t for t in re.findall(r"\w+", text.lower()) if t not in _STOPWORDS}


@dataclass
class CaseRecord:
    """A concrete case c in the short-term cluster M^S.

    Mirrors the paper's case record ``(x, Y, y_hat, f)`` plus an optional
    rationale snippet:

        case_summary  x        compact patient-case text
        candidates    Y        candidate diagnoses
        diagnosis     y_hat    the prediction that was made
        feedback      f        outcome feedback, e.g. "correct; truth=STEMI"
        reasoning              optional short rationale snippet
    """

    case_summary: str
    candidates: list[str] = field(default_factory=list)
    diagnosis: str = ""
    feedback: str = ""
    reasoning: str = ""
    correct: bool | None = None
    case_id: str = field(default_factory=lambda: uuid4().hex)
    seq: int = -1

    def to_dict(self) -> dict:
        return {
            "case_summary": self.case_summary,
            "candidates": list(self.candidates),
            "diagnosis": self.diagnosis,
            "feedback": self.feedback,
            "reasoning": self.reasoning,
            "correct": self.correct,
            "case_id": self.case_id,
            "seq": self.seq,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CaseRecord":
        return cls(
            case_summary=d["case_summary"],
            candidates=list(d.get("candidates", [])),
            diagnosis=d.get("diagnosis", ""),
            feedback=d.get("feedback", ""),
            reasoning=d.get("reasoning", ""),
            correct=d.get("correct"),
            case_id=d.get("case_id", uuid4().hex),
            seq=d.get("seq", -1),
        )

    def text(self) -> str:
        """Flattened text used for lexical retrieval scoring."""
        parts = [
            self.case_summary,
            " ".join(self.candidates),
            self.diagnosis,
            self.feedback,
            self.reasoning,
        ]
        return " ".join(p for p in parts if p).strip()


@dataclass
class Rule:
    """A distilled, reusable rule r in the long-term cluster M^L.

    A concise statement: a symptom-disease association, a discriminative cue,
    or a failure pattern. ``support`` counts how many cases back the rule and
    is bumped when a near-duplicate rule re-emerges during consolidation.
    """

    text: str
    source_case_ids: list[str] = field(default_factory=list)
    support: int = 1
    rule_id: str = field(default_factory=lambda: uuid4().hex)
    seq: int = -1

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "source_case_ids": list(self.source_case_ids),
            "support": self.support,
            "rule_id": self.rule_id,
            "seq": self.seq,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Rule":
        return cls(
            text=d["text"],
            source_case_ids=list(d.get("source_case_ids", [])),
            support=d.get("support", 1),
            rule_id=d.get("rule_id", uuid4().hex),
            seq=d.get("seq", -1),
        )


class CapacityError(Exception):
    """Raised by ``append`` when the short-term cluster is already at capacity K."""


class DualMemory:
    """The dual-memory module: M^S (short-term cases) + M^L (long-term rules).

    Capacity is enforced internally: ``append`` raises ``CapacityError`` at K, so
    eviction is always an explicit decision (``pop``) — the convenience ``add``
    driver is the only path that auto-evicts.
    """

    def __init__(
        self,
        K: int = 8,
        summarizer: RuleSummarizer | None = None,
        path: str | None = None,
        auto_save: bool = True,
    ):
        if K < 1:
            raise ValueError("K must be >= 1")
        self.K = K
        self.summarizer: RuleSummarizer = summarizer or MockSummarizer()
        self.path = path
        self.auto_save = auto_save
        self.short_term: list[CaseRecord] = []
        self.long_term: list[Rule] = []
        self._seq = 0
        self._last_evicted: list[CaseRecord] = []

    # -- internals ----------------------------------------------------------
    def _next_seq(self) -> int:
        s = self._seq
        self._seq += 1
        return s

    @staticmethod
    def _coerce(case: "CaseRecord | dict") -> CaseRecord:
        if isinstance(case, CaseRecord):
            return case
        if isinstance(case, dict):
            return CaseRecord.from_dict(case)
        raise TypeError(f"expected CaseRecord or dict, got {type(case).__name__}")

    @staticmethod
    def _recency(items, n):
        return sorted(items, key=lambda x: x.seq, reverse=True)[:n]

    def _find_rule_by_norm(self, norm: str) -> "Rule | None":
        for r in self.long_term:
            if normalize_rule_text(r.text) == norm:
                return r
        return None

    def _maybe_save(self) -> None:
        if self.path and self.auto_save:
            self.save()

    # -- capacity predicate (mechanics, not a metric) -----------------------
    def is_full(self) -> bool:
        return len(self.short_term) >= self.K

    def __len__(self) -> int:
        return len(self.short_term)

    # -- the four operations ------------------------------------------------
    def list(self, query: str | None = None, n_cases: int = 5, n_rules: int = 5) -> dict:
        """Read-only retrieval of relevant cases + rules (the ``list`` action)."""
        if query is None:
            cases = self._recency(self.short_term, n_cases)
            rules = self._recency(self.long_term, n_rules)
        else:
            cases, rules = self.retrieve(query, n_cases, n_rules)
        return {
            "cases": [c.to_dict() for c in cases],
            "rules": [r.to_dict() for r in rules],
        }

    def append(self, case: "CaseRecord | dict") -> CaseRecord:
        """Append-only insert into M^S. Raises ``CapacityError`` when at K."""
        if self.is_full():
            raise CapacityError(
                f"short-term memory is full (K={self.K}); pop before appending"
            )
        rec = self._coerce(case)
        if not rec.case_id:
            rec.case_id = uuid4().hex
        rec.seq = self._next_seq()
        self.short_term.append(rec)
        self._maybe_save()
        return rec

    def pop(
        self,
        case_ids: list[str] | None = None,
        n: int | None = None,
    ) -> list[CaseRecord]:
        """Evict and return cases. ``case_ids`` is explicit; else ``n`` oldest (default 1)."""
        if case_ids is not None:
            wanted = set(case_ids)
            evicted = [c for c in self.short_term if c.case_id in wanted]
            self.short_term = [c for c in self.short_term if c.case_id not in wanted]
        else:
            k = 1 if n is None else n
            evicted = sorted(self.short_term, key=lambda c: c.seq)[:k]
            evicted_ids = {c.case_id for c in evicted}
            self.short_term = [c for c in self.short_term if c.case_id not in evicted_ids]
        self._last_evicted = list(evicted)
        self._maybe_save()
        return evicted

    def consolidate(
        self,
        cases: list[CaseRecord] | None = None,
        max_rules: int = 3,
    ) -> list[Rule]:
        """Distill evicted cases into rules (the ``consolidate`` action).

        The sole caller of the summarizer seam. New rule texts are normalized; a
        near-duplicate of an existing rule bumps that rule's ``support`` (and
        extends its provenance) instead of adding a row.
        """
        batch = self._last_evicted if cases is None else cases
        if not batch:
            return []

        rule_texts = self.summarizer.summarize(batch, self.long_term)[:max_rules]
        source_ids = [c.case_id for c in batch]
        new_rules: list[Rule] = []
        for text in rule_texts:
            text = (text or "").strip()
            if not text:
                continue
            norm = normalize_rule_text(text)
            if not norm:
                continue
            existing = self._find_rule_by_norm(norm)
            if existing is not None:
                existing.support += 1
                existing.source_case_ids.extend(source_ids)
            else:
                new_rules.append(
                    Rule(
                        text=text,
                        source_case_ids=list(source_ids),
                        support=len(batch),
                        seq=self._next_seq(),
                    )
                )
        self.long_term.extend(new_rules)
        self._maybe_save()
        return new_rules

    # -- convenience driver (opt-in sugar over the four ops) ----------------
    def add(self, case: "CaseRecord | dict", auto_consolidate: bool = True) -> dict:
        """Drive one round: if full, pop the oldest case (and consolidate it),
        then append ``case``. Returns the evicted cases and any new rules.

        This is the only path that auto-evicts; the four operations stay
        explicit so a caller can manage memory by hand if preferred.
        """
        evicted: list[CaseRecord] = []
        new_rules: list[Rule] = []
        if self.is_full():
            evicted = self.pop(n=1)
            if auto_consolidate:
                new_rules = self.consolidate(evicted)
        appended = self.append(case)
        return {"appended": appended, "evicted": evicted, "new_rules": new_rules}

    # -- retrieval ----------------------------------------------------------
    def retrieve(
        self,
        query: str,
        n_cases: int = 5,
        n_rules: int = 5,
    ) -> "tuple[list[CaseRecord], list[Rule]]":
        """Lexical retrieval of the most relevant cases and rules for ``query``.

        Length-normalized token overlap; rules get a small ``log1p(support)``
        bonus. Zero-overlap items are dropped; ties break toward recency. An
        empty query falls back to pure recency.
        """
        q = _tokenize(query)
        if not q:
            return self._recency(self.short_term, n_cases), self._recency(self.long_term, n_rules)

        cases = self._rank(self.short_term, q, n_cases, lambda c: c.text())
        rules = self._rank(self.long_term, q, n_rules, lambda r: r.text, support=True)
        return cases, rules

    @staticmethod
    def _rank(items, q, n, text_of, support=False):
        scored = []
        for item in items:
            toks = _tokenize(text_of(item))
            if not toks:
                continue
            overlap = len(q & toks)
            if overlap == 0:
                continue
            score = overlap / math.sqrt(len(toks))
            if support:
                score += 0.1 * math.log1p(getattr(item, "support", 1))
            scored.append((score, item.seq, item))
        scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
        return [item for _, _, item in scored[:n]]

    # -- persistence --------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "version": 1,
            "K": self.K,
            "seq": self._seq,
            "short_term": [c.to_dict() for c in self.short_term],
            "long_term": [r.to_dict() for r in self.long_term],
            "last_evicted": [c.to_dict() for c in self._last_evicted],
        }

    def save(self, path: str | None = None) -> None:
        """Atomically write state to JSON (temp file + ``os.replace``)."""
        target = path or self.path
        if not target:
            raise ValueError("no path given and DualMemory has no default path")
        tmp = f"{target}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2, ensure_ascii=False)
        os.replace(tmp, target)

    @classmethod
    def load(
        cls,
        path: str,
        summarizer: RuleSummarizer | None = None,
    ) -> "DualMemory":
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        m = cls(K=data["K"], summarizer=summarizer, path=path)
        m.short_term = [CaseRecord.from_dict(d) for d in data.get("short_term", [])]
        m.long_term = [Rule.from_dict(d) for d in data.get("long_term", [])]
        m._last_evicted = [CaseRecord.from_dict(d) for d in data.get("last_evicted", [])]
        m._seq = data.get("seq", 0)
        return m
