"""OmeBench CLI entrypoint.

Usage:

    python -m mindos.harness.omebench.cli \
        --corpus    packages/mindos/omebench/sample_corpus \
        --questions packages/mindos/omebench/sample_questions.jsonl \
        --backend   stub

The ``stub`` backend is deterministic and shipped for CI: it answers each
question by looking up a canned reply table keyed by question ID. Use
``--backend claude`` for a real-model run (requires ANTHROPIC_API_KEY).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from mindos.harness.models.base import ModelBackend, StubBackend
from mindos.harness.omebench.driver import OmeBench
from mindos.harness.omebench.questions import load_questions


# Canned replies for --backend stub. Kept in sync with sample_questions.jsonl
# so a bare `--backend stub` against the sample corpus scores 5/5.
_STUB_REPLIES: dict[str, str] = {
    "q1": "Alice reports to Bob, who manages the harness org.",
    "q2": "Bob approved the v0.9 roadmap on 2026-04-02.",
    "q3": (
        "Bob's backup plan is to spin the skills.sh packaging work out into "
        "a separate public library and let the runtime catch up later."
    ),
    "q4": "Alice's favourite tool is ripgrep.",
    "q5": (
        "Bob manages three teams: harness, infra, and ingest."
    ),
}


def _make_stub_backend(questions_path: Path) -> StubBackend:
    """Return a StubBackend whose reply_fn inspects the last user message."""
    qs = load_questions(questions_path)
    by_text = {q.question: _STUB_REPLIES.get(q.id, "") for q in qs}

    def reply_fn(messages: list[dict]) -> str:
        # Walk backwards for the most recent 'user' message text
        for m in reversed(messages):
            if m.get("role") != "user":
                continue
            content = m.get("content", "")
            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                text = ""
                for b in content:
                    if isinstance(b, dict) and b.get("type") == "text":
                        text = b.get("text", "")
                        break
            else:
                text = str(content)
            text = text.strip()
            if text in by_text:
                return by_text[text]
            # Fallback: substring search over question texts
            for q_text, reply in by_text.items():
                if q_text and q_text in text:
                    return reply
            return f"[stub] {text}"
        return "[stub]"

    return StubBackend(reply_fn=reply_fn)


def _make_backend(name: str, *, questions_path: Path) -> ModelBackend:
    name = name.lower()
    if name == "stub":
        return _make_stub_backend(questions_path)
    if name == "claude":
        from mindos.harness.models.claude import ClaudeBackend
        return ClaudeBackend()
    if name == "kimi":
        from mindos.harness.models.kimi import KimiBackend
        return KimiBackend()
    raise SystemExit(f"unknown backend: {name!r}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="omebench",
        description="Run the OmeBench long-life QA benchmark.",
    )
    ap.add_argument("--corpus", required=True, type=Path,
                    help="Path to corpus directory.")
    ap.add_argument("--questions", required=True, type=Path,
                    help="Path to questions JSONL (or JSON array).")
    ap.add_argument("--backend", default="stub",
                    help="Model backend: stub | claude | kimi.")
    ap.add_argument("--max-chars", type=int, default=48_000,
                    help="Max chars for the context window.")
    ap.add_argument("--json", action="store_true",
                    help="Emit machine-readable JSON report on stdout.")
    ap.add_argument("--verbose", "-v", action="store_true",
                    help="Print each question's score as it runs.")
    args = ap.parse_args(argv)

    backend = _make_backend(args.backend, questions_path=args.questions)
    bench = OmeBench(
        corpus_path=args.corpus,
        questions_path=args.questions,
        model=backend,
        max_chars=args.max_chars,
    )
    report = bench.run()

    if args.json:
        payload = {
            **report.summary(),
            "items": [
                {
                    "id": i.question_id,
                    "category": i.category,
                    "correct": i.score.correct,
                    "score": i.score.score,
                    "steps": i.steps,
                    "ms": i.ms,
                } for i in report.items
            ],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    s = report.summary()
    print(f"OmeBench · corpus={s['corpus']}")
    print(f"  total    : {s['total']}")
    print(f"  correct  : {s['correct']}")
    print(f"  accuracy : {s['accuracy']}")
    print("  by category:")
    for cat, d in s["by_category"].items():
        print(f"    - {cat}: {d['correct']}/{d['total']}"
              f" ({d['accuracy']:.2f})")
    if args.verbose:
        print()
        for it in report.items:
            mark = "OK  " if it.score.correct else "FAIL"
            print(f"  {mark} [{it.category}] {it.question_id}"
                  f"  score={it.score.score:.2f}"
                  f"  steps={it.steps}  {it.ms}ms")
            for r in it.score.reasons:
                print(f"        · {r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
