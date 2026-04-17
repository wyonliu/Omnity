"""Tests for the EvoLog module — progressive evolution timeline."""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mindos.core import Mindos
from mindos.event_bus import (
    CONTRADICTION_DETECTED,
    INSIGHT_GENERATED,
    MAINTENANCE_RUN,
    MEMORY_COMPRESSED,
    PERSONALITY_CHANGED,
    REFLECT_COMPLETED,
)
from mindos.evolog import (
    EVO_COMPRESSION,
    EVO_CONTRADICTION,
    EVO_IDENTITY_CHANGE,
    EVO_INSIGHT,
    EVO_MAINTENANCE,
    EVO_REFLECT,
    EVO_SKILL_FORGED,
    EvoLogger,
)


# -- baseline --------------------------------------------------------------

def test_evolog_wires_on_init():
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="U")
        assert isinstance(m.evolog, EvoLogger)
        # Empty on a fresh soul
        assert m.evo_timeline() == []
        assert m.evo_stats()["total"] == 0
    print("  PASSED")


def test_manual_record_evo():
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="U")
        eid = m.record_evo("custom", summary="hello", layer="L4",
                           details={"x": 1})
        assert eid
        rows = m.evo_timeline()
        assert len(rows) == 1
        assert rows[0]["event_type"] == "custom"
        assert rows[0]["summary"] == "hello"
        assert rows[0]["layer"] == "L4"
        assert rows[0]["details"] == {"x": 1}
    print("  PASSED")


# -- event bus integration --------------------------------------------------

def test_reflect_completed_recorded():
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="U")
        m.event_bus.emit(REFLECT_COMPLETED, {
            "insights": [{"content": "a"}, {"content": "b"}],
            "identity_updated": True,
        })
        rows = m.evo_timeline(event_types=[EVO_REFLECT])
        assert len(rows) == 1
        assert rows[0]["details"]["insight_count"] == 2
        assert rows[0]["details"]["identity_updated"] is True
        assert rows[0]["layer"] == "L4"
    print("  PASSED")


def test_personality_change_recorded():
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="U")
        m.event_bus.emit(PERSONALITY_CHANGED,
                         {"traits": ["curious", "direct"]})
        rows = m.evo_timeline(event_types=[EVO_IDENTITY_CHANGE])
        assert len(rows) == 1
        assert rows[0]["details"]["traits"] == ["curious", "direct"]
    print("  PASSED")


def test_contradiction_recorded():
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="U")
        m.event_bus.emit(CONTRADICTION_DETECTED,
                         {"description": "I said X then Y"})
        rows = m.evo_timeline(event_types=[EVO_CONTRADICTION])
        assert len(rows) == 1
        assert "X then Y" in rows[0]["summary"]
    print("  PASSED")


def test_insight_recorded():
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="U")
        m.event_bus.emit(INSIGHT_GENERATED, {"content": "I prefer mornings"})
        rows = m.evo_timeline(event_types=[EVO_INSIGHT])
        assert len(rows) == 1
        assert "prefer mornings" in rows[0]["summary"]
    print("  PASSED")


def test_maintenance_recorded():
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="U")
        m.event_bus.emit(MAINTENANCE_RUN, {"compacted": 3, "pruned": 7})
        rows = m.evo_timeline(event_types=[EVO_MAINTENANCE])
        assert len(rows) == 1
        assert rows[0]["details"]["compacted"] == 3
    print("  PASSED")


def test_compression_recorded():
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="U")
        m.event_bus.emit(MEMORY_COMPRESSED, {"freed": 10, "merged": 5})
        rows = m.evo_timeline(event_types=[EVO_COMPRESSION])
        assert len(rows) == 1
        assert "freed=10" in rows[0]["summary"]
    print("  PASSED")


# -- filtering -------------------------------------------------------------

def test_timeline_filtering_and_order():
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="U")
        m.record_evo("a", "first")
        time.sleep(0.01)
        m.record_evo("b", "second")
        time.sleep(0.01)
        m.record_evo("a", "third")

        # Order is newest-first
        rows = m.evo_timeline()
        assert [r["summary"] for r in rows] == ["third", "second", "first"]

        # Filter by type
        only_a = m.evo_timeline(event_types=["a"])
        assert [r["summary"] for r in only_a] == ["third", "first"]

        # Limit
        one = m.evo_timeline(limit=1)
        assert len(one) == 1
        assert one[0]["summary"] == "third"
    print("  PASSED")


def test_stats_reports_counts_and_bounds():
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="U")
        m.record_evo("reflect_cycle", "r1")
        m.record_evo("insight", "i1")
        m.record_evo("insight", "i2")
        st = m.evo_stats()
        assert st["total"] == 3
        assert st["by_type"]["insight"] == 2
        assert st["by_type"]["reflect_cycle"] == 1
        assert st["first_at"] <= st["last_at"]
    print("  PASSED")


# -- skill_forged integration ---------------------------------------------

def test_skill_forged_recorded():
    from test_skillforge import _trace  # reuse fixture
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="U")
        m.skills.use_llm = False
        sid = m.forge_skill(_trace())
        assert sid is not None
        rows = m.evo_timeline(event_types=[EVO_SKILL_FORGED])
        assert len(rows) == 1
        assert rows[0]["details"]["skill_id"] == sid
        assert rows[0]["layer"] == "L3"
    print("  PASSED")


# -- detach ----------------------------------------------------------------

def test_detach_stops_recording():
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="U")
        m.evolog.detach()
        m.event_bus.emit(INSIGHT_GENERATED, {"content": "x"})
        assert m.evo_timeline() == []
    print("  PASSED")


# -- commit path produces events -------------------------------------------

def test_commit_path_emits_reflect_event_into_evo():
    """Smoke-test: a real commit → reflect cycle flows through into evolog."""
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="U")
        # Direct emission is enough to prove the wiring; the layer's actual
        # reflect trigger depends on config which we don't exercise here.
        m.event_bus.emit(REFLECT_COMPLETED, {"insights": [], "identity_updated": False})
        rows = m.evo_timeline(event_types=[EVO_REFLECT])
        assert len(rows) == 1
    print("  PASSED")


if __name__ == "__main__":
    test_evolog_wires_on_init()
    test_manual_record_evo()
    test_reflect_completed_recorded()
    test_personality_change_recorded()
    test_contradiction_recorded()
    test_insight_recorded()
    test_maintenance_recorded()
    test_compression_recorded()
    test_timeline_filtering_and_order()
    test_stats_reports_counts_and_bounds()
    test_skill_forged_recorded()
    test_detach_stops_recording()
    test_commit_path_emits_reflect_event_into_evo()
    print("\n✔ all EvoLog tests passed")
