"""OmeBench driver — ingest → run → score → report.

End-to-end:

    bench = OmeBench(
        corpus_path="omebench/sample_corpus",
        questions_path="omebench/sample_questions.jsonl",
        model=StubBackend(reply_fn=my_oracle),
    )
    report = bench.run()
    print(report.summary())

By default we build a **fresh Mindos per run** in a temp dir so runs are
reproducible and hermetic. Override via `mindos_factory=` if you want to
test against a specific in-prod soul.
"""

from __future__ import annotations

import logging
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from mindos.harness.engine import HarnessEngine
from mindos.harness.models.base import ModelBackend
from mindos.harness.omebench.corpus import Corpus, load_corpus
from mindos.harness.omebench.questions import Question, load_questions
from mindos.harness.omebench.scorers import (
    RuleScorer,
    Scorer,
    ScoreBreakdown,
    score_item,
)

log = logging.getLogger("mindos.harness.omebench")


@dataclass
class BenchItemResult:
    question_id: str
    category: str
    question: str
    response: str
    score: ScoreBreakdown
    steps: int
    ms: int


@dataclass
class BenchReport:
    corpus: str
    items: list[BenchItemResult] = field(default_factory=list)
    totals_by_category: dict[str, dict[str, int]] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return len(self.items)

    @property
    def correct(self) -> int:
        return sum(1 for i in self.items if i.score.correct)

    @property
    def score(self) -> float:
        if not self.items:
            return 0.0
        return sum(i.score.score for i in self.items) / len(self.items)

    def summary(self) -> dict:
        return {
            "corpus": self.corpus,
            "total": self.total,
            "correct": self.correct,
            "accuracy": round(self.score, 4),
            "by_category": {
                cat: {
                    "correct": d.get("correct", 0),
                    "total": d.get("total", 0),
                    "accuracy": (d.get("correct", 0) / max(1, d.get("total", 0))),
                } for cat, d in self.totals_by_category.items()
            },
        }


class OmeBench:
    def __init__(
        self,
        *,
        corpus_path: str | Path,
        questions_path: str | Path,
        model: ModelBackend,
        scorer: Optional[Scorer] = None,
        mindos_factory: Optional[Callable[[Path], Any]] = None,
        max_chars: int = 48_000,
    ):
        self.corpus_path = Path(corpus_path)
        self.questions_path = Path(questions_path)
        self.model = model
        self.scorer = scorer or RuleScorer()
        self.mindos_factory = mindos_factory
        self.max_chars = max_chars

    # -- public ---------------------------------------------------------

    def run(self) -> BenchReport:
        corpus = load_corpus(self.corpus_path)
        questions = load_questions(self.questions_path)
        report = BenchReport(corpus=corpus.name)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            mindos = self._build_mindos(tmp_root, corpus)
            snapshot_dir = tmp_root / "snapshot"
            self._export_snapshot(mindos, snapshot_dir, corpus)

            for q in questions:
                item = self._ask(q, snapshot_dir)
                report.items.append(item)
                cat = item.category or "uncategorized"
                bucket = report.totals_by_category.setdefault(
                    cat, {"correct": 0, "total": 0})
                bucket["total"] += 1
                if item.score.correct:
                    bucket["correct"] += 1
        return report

    # -- internals ------------------------------------------------------

    def _build_mindos(self, tmp_root: Path, corpus: Corpus) -> Any:
        if self.mindos_factory:
            return self.mindos_factory(tmp_root)
        # Lazy import so omebench module loads even without store deps
        from mindos.core import Mindos
        from mindos.store import Memory

        m = Mindos.init(
            path=tmp_root / "mindos",
            name=f"bench-{corpus.name}",
            traits=["neutral"],
            style="neutral",
        )
        for c in corpus.items:
            m.store.add(Memory(
                id="", type=c.type, content=c.content,
                source=c.source, confidence=1.0,
            ))
        return m

    def _export_snapshot(self, mindos: Any, snapshot_dir: Path,
                          corpus: Corpus) -> None:
        export = getattr(mindos, "export_md", None)
        if callable(export):
            export(snapshot_dir)
            return
        # Fallback: assemble a minimal snapshot directly from the corpus
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        (snapshot_dir / "IDENTITY.md").write_text(
            f"# Bench Identity\n\nCorpus: {corpus.name}\n", encoding="utf-8")
        (snapshot_dir / "MEMORY.md").write_text(
            "# Memories\n" + "\n".join(f"- {c.content}" for c in corpus.items
                                        if c.type == "episode"),
            encoding="utf-8")
        (snapshot_dir / "FACTS.md").write_text(
            "# Facts\n" + "\n".join(f"- {c.content}" for c in corpus.items
                                     if c.type == "fact"),
            encoding="utf-8")

    def _ask(self, q: Question, snapshot: Path) -> BenchItemResult:
        engine = HarnessEngine(
            context_source=snapshot,
            model=self.model,
            max_chars=self.max_chars,
        )
        t0 = time.time()
        result = engine.run(q.question)
        ms = int((time.time() - t0) * 1000)
        score = score_item(q, result.response)
        return BenchItemResult(
            question_id=q.id,
            category=q.category,
            question=q.question,
            response=result.response,
            score=score,
            steps=result.steps,
            ms=ms,
        )
