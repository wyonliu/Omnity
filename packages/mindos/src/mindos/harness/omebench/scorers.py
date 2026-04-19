"""Rule-based scorers for OmeBench.

No LLM-judge by default — public numbers should be reproducible. A plug-in
``Scorer`` interface lets you bring your own judge, but the shipped
:class:`RuleScorer` suffices for every question type the sample bank uses.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from mindos.harness.omebench.questions import Question


@dataclass
class ScoreBreakdown:
    """Per-question scoring detail."""
    correct: bool
    score: float  # 0.0 - 1.0 (fractional credit for partials)
    reasons: list[str]


class Scorer(Protocol):
    def score(self, q: Question, response: str) -> ScoreBreakdown: ...


class RuleScorer:
    """Scorer that honours every rubric field on Question."""

    def score(self, q: Question, response: str) -> ScoreBreakdown:
        return score_item(q, response)


def score_item(q: Question, response: str) -> ScoreBreakdown:
    """Rule-based grader. Returns fractional-credit score + reasons.

    Verdict:
        - fail if any ``forbid_contains`` string appears (case-insensitive)
        - for ``expected_contains`` (CI substring), each hit earns a
          proportional share
        - ``expected_any`` earns its share if ANY listed string appears
        - ``expected_regex`` earns its share if ALL regexes match

    The final score is the mean of each active rubric's share; when a
    question has no rubric, a response of non-empty text counts as correct.
    """
    reasons: list[str] = []
    body = (response or "").strip()
    body_l = body.lower()

    # Hard fail
    for bad in q.forbid_contains:
        if bad.lower() in body_l:
            reasons.append(f"forbidden phrase present: {bad!r}")
            return ScoreBreakdown(correct=False, score=0.0, reasons=reasons)

    rubric_count = 0
    rubric_score = 0.0

    if q.expected_contains:
        rubric_count += 1
        hits = sum(1 for needle in q.expected_contains
                   if needle.lower() in body_l)
        frac = hits / max(1, len(q.expected_contains))
        rubric_score += frac
        reasons.append(
            f"expected_contains: {hits}/{len(q.expected_contains)} hit")

    if q.expected_any:
        rubric_count += 1
        hit = any(needle.lower() in body_l for needle in q.expected_any)
        rubric_score += 1.0 if hit else 0.0
        reasons.append(f"expected_any: {'hit' if hit else 'miss'}")

    if q.expected_regex:
        rubric_count += 1
        hits = sum(1 for pat in q.expected_regex
                   if re.search(pat, body))
        frac = hits / max(1, len(q.expected_regex))
        rubric_score += frac
        reasons.append(f"expected_regex: {hits}/{len(q.expected_regex)} match")

    if rubric_count == 0:
        # No rubric — non-empty response = pass.
        ok = bool(body)
        reasons.append("no rubric; non-empty response" if ok
                       else "no rubric; empty response")
        return ScoreBreakdown(correct=ok, score=1.0 if ok else 0.0,
                              reasons=reasons)

    final = rubric_score / rubric_count
    return ScoreBreakdown(
        correct=(final >= 0.999),  # strict — fractional is a "partial"
        score=final,
        reasons=reasons,
    )
