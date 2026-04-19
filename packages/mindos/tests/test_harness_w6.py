"""W6 tests — OmeBench public benchmark driver.

End-to-end runs against the shipped sample fixture at
``packages/mindos/omebench/sample_corpus`` and ``sample_questions.jsonl``.
No LLM, no network — uses ``StubBackend`` with a scripted reply table.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

_here = Path(__file__).resolve()
sys.path.insert(0, str(_here.parent.parent / "src"))

from mindos.harness.models.base import StubBackend
from mindos.harness.omebench import (
    BenchItemResult,
    BenchReport,
    Corpus,
    OmeBench,
    Question,
    RuleScorer,
    load_corpus,
    load_questions,
    score_item,
)
from mindos.harness.omebench.cli import _make_stub_backend, main as cli_main


_PKG_ROOT = _here.parent.parent
_CORPUS_PATH = _PKG_ROOT / "omebench" / "sample_corpus"
_QUESTIONS_PATH = _PKG_ROOT / "omebench" / "sample_questions.jsonl"


# --- load_corpus ----------------------------------------------------------

def test_load_corpus_ships_fixture_with_expected_items():
    c = load_corpus(_CORPUS_PATH)
    assert isinstance(c, Corpus)
    assert c.name == "omebench-sample"
    assert c.description  # meta.json sets it

    counts = c.counts_by_type()
    # 2 interviews + 1 journal → 3 episode; 5 bullet facts → 5 fact
    assert counts["episode"] == 3, counts
    assert counts["fact"] == 5, counts

    # Spot-check content made it through frontmatter stripping (there's
    # none in these fixtures, but the loader must still emit non-empty)
    assert all(item.content.strip() for item in c.items)
    sources = {i.source for i in c.items}
    assert "interview:interview_alice" in sources
    assert "interview:interview_bob" in sources
    assert "journal:2026-04-10" in sources
    print("  PASSED")


def test_load_corpus_rejects_missing_dir():
    try:
        load_corpus(_PKG_ROOT / "no_such_dir_xyz")
    except FileNotFoundError:
        print("  PASSED")
        return
    raise AssertionError("expected FileNotFoundError")


# --- load_questions -------------------------------------------------------

def test_load_questions_parses_shipped_jsonl():
    qs = load_questions(_QUESTIONS_PATH)
    assert len(qs) == 5
    assert all(isinstance(q, Question) for q in qs)
    cats = {q.category for q in qs}
    assert cats == {"single-hop", "temporal", "multi-hop", "forbid"}
    by_id = {q.id: q for q in qs}
    assert by_id["q1"].expected_contains == ["Bob"]
    assert "2026-04-02" in by_id["q2"].expected_contains
    assert "skills.sh" in by_id["q3"].expected_contains
    # q4 has a forbid list
    assert "emacs" in by_id["q4"].forbid_contains
    print("  PASSED")


def test_load_questions_accepts_json_array(tmp_fixture=None):
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "qs.json"
        p.write_text(json.dumps([
            {"id": "a", "question": "?", "expected_contains": ["x"]},
            {"id": "b", "question": "??"},
        ]), encoding="utf-8")
        qs = load_questions(p)
        assert [q.id for q in qs] == ["a", "b"]
        assert qs[0].expected_contains == ["x"]
    print("  PASSED")


# --- score_item rubrics ---------------------------------------------------

def test_score_item_forbid_is_hard_fail():
    q = Question(id="q", question="?", expected_contains=["yes"],
                 forbid_contains=["unknown"])
    s = score_item(q, "yes, but also unknown")
    assert s.correct is False
    assert s.score == 0.0
    assert any("forbidden" in r for r in s.reasons)
    print("  PASSED")


def test_score_item_expected_contains_all_must_hit():
    q = Question(id="q", question="?",
                 expected_contains=["alpha", "beta", "gamma"])
    partial = score_item(q, "alpha and beta are here")
    assert partial.correct is False
    # 2/3 hits → score ~0.667
    assert abs(partial.score - 2 / 3) < 1e-6

    full = score_item(q, "alpha, beta, and gamma walk into a bar")
    assert full.correct is True
    assert full.score == 1.0
    print("  PASSED")


def test_score_item_expected_any_either_or():
    q = Question(id="q", question="?",
                 expected_any=["three", "3"])
    assert score_item(q, "there are 3 teams").correct
    assert score_item(q, "harness team alone").correct is False
    print("  PASSED")


def test_score_item_expected_regex_all_must_match():
    q = Question(id="q", question="?",
                 expected_regex=[r"2026-0\d-\d{2}", r"Bob"])
    hit = score_item(q, "Bob did it on 2026-04-02")
    assert hit.correct is True
    miss = score_item(q, "Bob wasn't around")
    assert miss.correct is False
    print("  PASSED")


def test_score_item_no_rubric_passes_on_non_empty():
    q = Question(id="q", question="?")  # no rubric fields
    assert score_item(q, "anything").correct is True
    assert score_item(q, "").correct is False
    print("  PASSED")


def test_rule_scorer_delegates_to_score_item():
    q = Question(id="q", question="?", expected_contains=["xx"])
    r = RuleScorer().score(q, "xx here")
    assert r.correct is True
    print("  PASSED")


# --- OmeBench end-to-end --------------------------------------------------

def _oracle_reply(messages):
    """Very small oracle: look at the latest user 'question' and serve a
    canned reply tuned to score 5/5 against the sample rubric."""
    text = ""
    for m in reversed(messages):
        if m.get("role") != "user":
            continue
        c = m.get("content", "")
        if isinstance(c, str):
            text = c
        elif isinstance(c, list):
            for b in c:
                if isinstance(b, dict) and b.get("type") == "text":
                    text = b.get("text", "")
                    break
        break
    t = text.lower()
    if "alice report" in t:
        return "Alice reports to Bob."
    if "v0.9 roadmap" in t or "roadmap" in t and "approve" in t:
        return "Bob approved the v0.9 roadmap on 2026-04-02."
    if "backup plan" in t:
        return ("Bob's backup plan is to spin the skills.sh packaging work "
                "out into a separate public library.")
    if "favourite tool" in t or "favorite tool" in t:
        return "Her favourite tool is ripgrep."
    if "how many teams" in t:
        return "Bob manages three teams: harness, infra, and ingest."
    return f"[stub] {text}"


def test_omebench_run_end_to_end_scores_all_five():
    backend = StubBackend(reply_fn=_oracle_reply)
    bench = OmeBench(
        corpus_path=_CORPUS_PATH,
        questions_path=_QUESTIONS_PATH,
        model=backend,
    )
    report = bench.run()

    assert isinstance(report, BenchReport)
    assert report.total == 5
    assert report.correct == 5, [
        (i.question_id, i.score.reasons, i.response) for i in report.items]
    assert report.score == 1.0
    assert all(isinstance(i, BenchItemResult) for i in report.items)

    s = report.summary()
    assert s["accuracy"] == 1.0
    # Every expected category is accounted for
    assert set(s["by_category"]) == {
        "single-hop", "temporal", "multi-hop", "forbid"}
    assert all(d["correct"] == d["total"] for d in s["by_category"].values())
    print("  PASSED")


def test_omebench_partial_failure_still_reports():
    def stingy(_messages):
        return "unknown"
    bench = OmeBench(
        corpus_path=_CORPUS_PATH,
        questions_path=_QUESTIONS_PATH,
        model=StubBackend(reply_fn=stingy),
    )
    report = bench.run()
    assert report.total == 5
    # q4 has forbid_contains → 'unknown' is not in that list, but also not a
    # match for ripgrep. We mostly verify the report survives partial scores.
    assert report.correct < 5
    print("  PASSED")


# --- CLI helpers ----------------------------------------------------------

def test_cli_stub_backend_matches_shipped_questions():
    stub = _make_stub_backend(_QUESTIONS_PATH)
    # Simulate the model being asked question text directly
    # (mirrors how HarnessEngine sends the user's turn).
    msgs = [{"role": "user", "content": "Who does Alice report to?"}]
    out = stub.complete(system="", messages=msgs)
    assert "Bob" in out.text
    print("  PASSED")


def test_cli_main_prints_summary(capfd=None):
    # Runs the CLI with the stub backend against the sample fixture.
    argv = [
        "--corpus", str(_CORPUS_PATH),
        "--questions", str(_QUESTIONS_PATH),
        "--backend", "stub",
        "--json",
    ]
    rc = cli_main(argv)
    assert rc == 0
    print("  PASSED")


# --- run ------------------------------------------------------------------

if __name__ == "__main__":
    test_load_corpus_ships_fixture_with_expected_items()
    test_load_corpus_rejects_missing_dir()
    test_load_questions_parses_shipped_jsonl()
    test_load_questions_accepts_json_array()
    test_score_item_forbid_is_hard_fail()
    test_score_item_expected_contains_all_must_hit()
    test_score_item_expected_any_either_or()
    test_score_item_expected_regex_all_must_match()
    test_score_item_no_rubric_passes_on_non_empty()
    test_rule_scorer_delegates_to_score_item()
    test_omebench_run_end_to_end_scores_all_five()
    test_omebench_partial_failure_still_reports()
    test_cli_stub_backend_matches_shipped_questions()
    test_cli_main_prints_summary()
    print("\n✔ harness W6: 14 tests passed")
