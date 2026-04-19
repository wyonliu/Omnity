"""W5 tests — Overnight Soul Sync.

Runs against real Mindos + real MemoryStore. No LLM, no network.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

_here = Path(__file__).resolve()
sys.path.insert(0, str(_here.parent.parent / "src"))

from mindos.core import Mindos
from mindos.store import Memory
from mindos.harness.overnight import (
    OvernightConfig,
    OvernightReport,
    OvernightSoulSync,
    StepReport,
    _coerce_counts,
)


# --- helpers --------------------------------------------------------------

def _fresh_mindos(tmp: str) -> Mindos:
    m = Mindos.init(path=Path(tmp) / "m", name="C",
                    traits=["builder"], style="direct")
    return m


def _seed_fact_dupes(m: Mindos, n: int = 5) -> None:
    # Mostly-duplicate facts so merge_redundant_facts has something to do
    for i in range(n):
        m.store.add(Memory(
            id="", type="fact",
            content="米莱是我 11 岁的女儿",
            source=f"t{i}", confidence=1.0,
        ))
    for i in range(3):
        m.store.add(Memory(
            id="", type="fact",
            content="米莱喜欢打鼓",
            source=f"u{i}", confidence=1.0,
        ))


# --- _coerce_counts -------------------------------------------------------

def test_coerce_counts_handles_dict_int_and_bad():
    assert _coerce_counts({"merged": 3, "scanned": 10}) == {"merged": 3, "scanned": 10}
    assert _coerce_counts(5) == {"count": 5}
    assert _coerce_counts(None) == {}
    # Bools are ints in Python — we keep them deliberately (0/1 counts)
    assert _coerce_counts({"ok": True}) == {"ok": 1}
    # Non-numeric values dropped
    assert _coerce_counts({"msg": "hi", "n": 2}) == {"n": 2}
    print("  PASSED")


# --- step invariants ------------------------------------------------------

def test_run_all_steps_default_config_writes_evolog():
    with tempfile.TemporaryDirectory() as tmp:
        m = _fresh_mindos(tmp)
        _seed_fact_dupes(m)

        sync = OvernightSoulSync(m)
        report = sync.run()

        assert isinstance(report, OvernightReport)
        assert report.finished_at >= report.started_at
        assert [s.name for s in report.steps] == list(
            OvernightSoulSync.STEP_NAMES)
        # reflect is opt-in → it skips (ok but skipped)
        reflect_step = [s for s in report.steps if s.name == "reflect"][0]
        assert reflect_step.skipped or reflect_step.counts.get("skipped") == 1

        # EvoLog row was written
        assert report.evo_log_id is not None
        rows = m.evo_timeline(event_types=["overnight_sync"])
        assert len(rows) == 1
        assert rows[0]["summary"].startswith("overnight sync")
        assert rows[0]["details"]["dry_run"] is False
        assert rows[0]["details"]["steps"][0]["name"] == "consolidate"
    print("  PASSED")


def test_dry_run_does_not_mutate_store_and_logs_evo():
    with tempfile.TemporaryDirectory() as tmp:
        m = _fresh_mindos(tmp)
        _seed_fact_dupes(m)
        before = m.store.count() if hasattr(m.store, "count") else None

        report = OvernightSoulSync(m).run(dry_run=True)
        assert report.dry_run is True
        assert report.ok()

        # counts shouldn't have moved (dry_run is a preview)
        if before is not None:
            after = m.store.count()
            assert after == before

        # still exactly one evolog row with dry_run=True
        rows = m.evo_timeline(event_types=["overnight_sync"])
        assert len(rows) == 1
        assert rows[0]["details"]["dry_run"] is True
    print("  PASSED")


def test_step_allowlist_respected():
    with tempfile.TemporaryDirectory() as tmp:
        m = _fresh_mindos(tmp)
        _seed_fact_dupes(m)
        cfg = OvernightConfig(only={"merge_facts"})
        report = OvernightSoulSync(m, config=cfg).run()
        active = [s for s in report.steps if not s.skipped]
        skipped = [s for s in report.steps if s.skipped]
        assert [s.name for s in active] == ["merge_facts"]
        # The other four are recorded but skipped
        assert {s.name for s in skipped} == {
            "consolidate", "compress_episodes", "archive_stale", "reflect"}
    print("  PASSED")


def test_failing_step_does_not_abort_sync():
    with tempfile.TemporaryDirectory() as tmp:
        m = _fresh_mindos(tmp)

        # Break consolidate() deliberately; other steps still run.
        original = m.store.consolidate

        def exploder(*a, **kw):
            raise RuntimeError("boom on consolidate")
        m.store.consolidate = exploder

        try:
            report = OvernightSoulSync(m).run()
        finally:
            m.store.consolidate = original

        consolidate_step = [s for s in report.steps if s.name == "consolidate"][0]
        assert consolidate_step.ok is False
        assert "boom" in (consolidate_step.error or "")
        # Other steps still ran
        merge = [s for s in report.steps if s.name == "merge_facts"][0]
        assert merge.ok is True
        # EvoLog captured the partial state
        rows = m.evo_timeline(event_types=["overnight_sync"])
        assert len(rows) == 1
    print("  PASSED")


def test_on_event_hook_fires_start_and_finish():
    with tempfile.TemporaryDirectory() as tmp:
        m = _fresh_mindos(tmp)
        events: list[tuple[str, dict]] = []
        sync = OvernightSoulSync(m, on_event=lambda k, p: events.append((k, p)))
        sync.run(dry_run=True)
        kinds = [k for k, _ in events]
        assert kinds == ["overnight_started", "overnight_finished"]
        assert events[0][1]["dry_run"] is True
        assert "duration_ms" in events[1][1]
    print("  PASSED")


def test_on_event_hook_exception_does_not_propagate():
    with tempfile.TemporaryDirectory() as tmp:
        m = _fresh_mindos(tmp)

        def bad_hook(k, p):
            raise RuntimeError("hook boom")
        # Must not raise
        report = OvernightSoulSync(m, on_event=bad_hook).run(dry_run=True)
        assert report.evo_log_id is not None
    print("  PASSED")


def test_missing_store_methods_are_soft_skipped():
    """If a store implements only a subset (e.g. PG+RLS in progress), steps
    missing methods are skipped, not crashed."""
    class PartialStore:
        # Only consolidate is present; other methods absent on purpose.
        def consolidate(self, similarity_threshold=0.9):
            return {"merged": 1}
        def record_evo(self, *, event_type, summary="", layer="", details=None):
            return "ev1"

    class FakeMindos:
        def __init__(self):
            self.store = PartialStore()

    m = FakeMindos()
    report = OvernightSoulSync(m).run()
    consolidate = [s for s in report.steps if s.name == "consolidate"][0]
    assert consolidate.ok and consolidate.counts == {"merged": 1}
    other = [s for s in report.steps
             if s.name in ("merge_facts", "compress_episodes", "archive_stale")]
    assert all(s.counts == {"skipped": 1} for s in other)
    print("  PASSED")


def test_report_totals_aggregates_across_steps():
    s1 = StepReport(name="a", ok=True, counts={"merged": 3, "scanned": 10})
    s2 = StepReport(name="b", ok=True, counts={"merged": 2})
    r = OvernightReport(steps=[s1, s2])
    t = r.totals()
    assert t == {"merged": 5, "scanned": 10}
    print("  PASSED")


if __name__ == "__main__":
    test_coerce_counts_handles_dict_int_and_bad()
    test_run_all_steps_default_config_writes_evolog()
    test_dry_run_does_not_mutate_store_and_logs_evo()
    test_step_allowlist_respected()
    test_failing_step_does_not_abort_sync()
    test_on_event_hook_fires_start_and_finish()
    test_on_event_hook_exception_does_not_propagate()
    test_missing_store_methods_are_soft_skipped()
    test_report_totals_aggregates_across_steps()
    print("\n✔ harness W5: 9 tests passed")
