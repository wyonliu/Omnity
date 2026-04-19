"""OmeBench — reproducible long-context memory benchmark for the harness.

Question-answering on a user's own long-tail context. Designed to measure
what LoCoMo measures (recency / single-hop / multi-hop / open-domain) but
on **authored corpora**, not synthetic dialogues:

    corpus/                       # what the Ome "remembers"
      interviews/*.md
      journal/*.md
      facts/*.md
    questions.jsonl               # what we ask it
    {"id":"q1","question":"...","expected_contains":["X","Y"],"category":"single-hop"}

Runner flow for each question:

    load corpus → ingest into a fresh Mindos → export snapshot →
    harness.run(question) → score response against the rubric

Scoring is **rule-based by default** (no LLM-judge cost, no flattery bias):
    - ``expected_contains`` — all strings must appear (substring, CI)
    - ``expected_regex`` — all regexes must match
    - ``forbid_contains`` — any listed string fails the item
    - ``expected_any`` — at least one string from the list must appear

An LLM judge can be plugged via ``scorer=`` but we don't ship one by
default: the public board reports rule-based scores so readers can
reproduce them.
"""

from __future__ import annotations

from mindos.harness.omebench.driver import (
    BenchItemResult,
    BenchReport,
    OmeBench,
)
from mindos.harness.omebench.corpus import Corpus, load_corpus
from mindos.harness.omebench.questions import Question, load_questions
from mindos.harness.omebench.scorers import (
    RuleScorer,
    Scorer,
    score_item,
)

__all__ = [
    "OmeBench",
    "BenchItemResult",
    "BenchReport",
    "Corpus",
    "load_corpus",
    "Question",
    "load_questions",
    "Scorer",
    "RuleScorer",
    "score_item",
]
