"""Tests for Ome365 v0.6 API: memory_stats, recall type_filter, emotion_history,
growth_timeline, report_external_stats, enhanced life_dashboard, enhanced chat_rich.
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

import pytest

from ome.core import Ome


@pytest.fixture
def ome(tmp_path):
    """Create a test Ome instance."""
    d = tmp_path / "test_ome"
    return Ome.create(d, name="TestUser", traits=["curious"])


# ── memory_stats() ──────────────────────────────────────────────────

class TestMemoryStats:
    def test_returns_complete_structure(self, ome):
        stats = ome.memory_stats()
        assert "total" in stats
        assert "by_type" in stats
        assert "decay_status" in stats
        assert "recent_7d" in stats
        assert "health" in stats

    def test_empty_ome_zero_total(self, ome):
        stats = ome.memory_stats()
        assert stats["total"] == 0
        assert stats["health"] == 0

    def test_after_remember_total_increases(self, ome):
        ome.remember("用户住在北京", source="manual")
        ome.remember("用户喜欢搏击", source="manual")
        stats = ome.memory_stats()
        assert stats["total"] >= 2
        assert stats["by_type"].get("fact", 0) >= 2

    def test_decay_status_structure(self, ome):
        ome.remember("一条记忆", source="manual")
        stats = ome.memory_stats()
        decay = stats["decay_status"]
        assert "active" in decay
        assert "fading" in decay
        assert "forgotten" in decay
        # Default decay_weight=1.0 → active
        assert decay["active"] >= 1

    def test_recent_7d_counts(self, ome):
        ome.remember("刚添加的记忆", source="manual")
        stats = ome.memory_stats()
        assert stats["recent_7d"]["added"] >= 1

    def test_health_score_range(self, ome):
        ome.remember("test", source="manual")
        stats = ome.memory_stats()
        assert 0 <= stats["health"] <= 1


# ── recall() type_filter ────────────────────────────────────────────

class TestRecallTypeFilter:
    def test_no_filter_returns_all(self, ome):
        ome.remember("事实1", source="manual")  # stored as fact
        results = ome.recall("事实", top_k=10)
        assert len(results) >= 1

    def test_filter_by_fact(self, ome):
        ome.remember("我住在上海", source="manual")
        results = ome.recall("上海", top_k=10, type_filter=["fact"])
        assert all(r.get("type") == "fact" for r in results)

    def test_filter_excludes_other_types(self, ome):
        ome.remember("一个事实", source="manual")
        results = ome.recall("事实", top_k=10, type_filter=["episode"])
        # manual remember stores as "fact", so filtering by "episode" returns empty
        facts_in_results = [r for r in results if r.get("type") == "fact"]
        assert len(facts_in_results) == 0

    def test_filter_multiple_types(self, ome):
        ome.remember("偏好信息", source="manual")
        results = ome.recall("偏好", top_k=10, type_filter=["fact", "preference"])
        for r in results:
            assert r.get("type") in ["fact", "preference"]

    def test_filter_none_same_as_no_filter(self, ome):
        ome.remember("测试数据", source="manual")
        r1 = ome.recall("测试", top_k=10, type_filter=None)
        r2 = ome.recall("测试", top_k=10)
        assert len(r1) == len(r2)


# ── emotion_history() ───────────────────────────────────────────────

class TestEmotionHistory:
    def test_returns_list(self, ome):
        history = ome.emotion_history(30)
        assert isinstance(history, list)

    def test_includes_today(self, ome):
        history = ome.emotion_history(30)
        today = datetime.now().strftime("%Y-%m-%d")
        dates = [e["date"] for e in history]
        assert today in dates

    def test_entry_has_required_fields(self, ome):
        history = ome.emotion_history(30)
        if history:
            entry = history[0]
            assert "date" in entry
            assert "valence" in entry
            assert "arousal" in entry
            assert "mood" in entry
            assert "energy" in entry

    def test_after_chat_emotion_persists(self, ome):
        # Chat to trigger emotion update + snapshot
        ome.chat("太棒了！我今天超开心！")
        history = ome.emotion_history(7)
        assert len(history) >= 1
        # The snapshot should reflect some emotional shift
        today_entry = history[0]
        assert isinstance(today_entry["valence"], float)

    def test_days_limit(self, ome):
        # Manually seed some history
        fake_history = {}
        for i in range(40):
            date_str = f"2026-03-{i+1:02d}" if i < 31 else f"2026-04-{i-30:02d}"
            fake_history[date_str] = {
                "valence": 0.1 * (i % 10), "arousal": 0.3,
                "mood": "neutral", "energy": 0.5,
            }
        ome.soul.store.set_state("ome.emotion_history", json.dumps(fake_history))
        history = ome.emotion_history(10)
        assert len(history) <= 11  # 10 from history + today's live


# ── growth_timeline() ───────────────────────────────────────────────

class TestGrowthTimeline:
    def test_returns_list(self, ome):
        timeline = ome.growth_timeline()
        assert isinstance(timeline, list)

    def test_empty_initially(self, ome):
        timeline = ome.growth_timeline()
        assert len(timeline) == 0

    def test_first_chat_records_event(self, ome):
        ome.chat("Hello!")
        timeline = ome.growth_timeline()
        events = [e["event"] for e in timeline]
        assert "first_chat" in events

    def test_event_structure(self, ome):
        ome.chat("Hi!")
        timeline = ome.growth_timeline()
        if timeline:
            event = timeline[0]
            assert "date" in event
            assert "event" in event
            assert "label" in event
            assert "detail" in event

    def test_first_chat_only_once(self, ome):
        ome.chat("Hello!")
        ome.chat("Hello again!")
        timeline = ome.growth_timeline()
        first_chats = [e for e in timeline if e["event"] == "first_chat"]
        assert len(first_chats) == 1

    def test_limit_parameter(self, ome):
        # Seed many events
        for i in range(25):
            ome._record_growth_event(f"test_{i}", f"Test {i}", f"Detail {i}")
        timeline = ome.growth_timeline(limit=5)
        assert len(timeline) == 5

    def test_newest_first(self, ome):
        ome._record_growth_event("old_event", "Old", "")
        time.sleep(0.01)
        ome._record_growth_event("new_event", "New", "")
        timeline = ome.growth_timeline()
        assert timeline[0]["event"] == "new_event"


# ── report_external_stats() ─────────────────────────────────────────

class TestReportExternalStats:
    def test_returns_ok(self, ome):
        result = ome.report_external_stats({"notes_count": 5, "tasks_done": 3})
        assert result["status"] == "ok"

    def test_persists_stats(self, ome):
        ome.report_external_stats({"notes_count": 42, "tasks_done": 15})
        raw = ome.soul.store.get_state("ome.external_stats")
        assert raw is not None
        data = json.loads(raw)
        assert data["notes_count"] == 42

    def test_triggers_achievements(self, ome):
        ome.report_external_stats({"notes_count": 10})
        unlocked = ome.achievements.unlocked_list()
        ids = [a["id"] for a in unlocked]
        assert "ten_facts" in ids

    def test_multiple_stats(self, ome):
        ome.report_external_stats({
            "notes_count": 42,
            "tasks_done": 15,
            "tasks_total": 28,
            "contacts_count": 10,
            "plan_pct": 25,
            "active_days": 12,
        })
        raw = json.loads(ome.soul.store.get_state("ome.external_stats"))
        assert raw["contacts_count"] == 10


# ── Enhanced life_dashboard() ───────────────────────────────────────

class TestLifeDashboardEnhanced:
    def test_has_new_fields(self, ome):
        dash = ome.life_dashboard()
        assert "daily_challenge" in dash
        assert "memory_stats" in dash
        assert "phase" in dash
        assert "next_milestone" in dash

    def test_daily_challenge_structure(self, ome):
        dash = ome.life_dashboard()
        ch = dash["daily_challenge"]
        assert "id" in ch
        assert "text" in ch
        assert "target" in ch
        assert "progress" in ch
        assert "completed" in ch

    def test_memory_stats_embedded(self, ome):
        ome.remember("测试记忆", source="manual")
        dash = ome.life_dashboard()
        ms = dash["memory_stats"]
        assert ms["total"] >= 1
        assert "health" in ms

    def test_phase_structure(self, ome):
        dash = ome.life_dashboard()
        phase = dash["phase"]
        assert "phase_id" in phase
        assert "name" in phase
        assert "persona" in phase
        assert "strategy_hint" in phase

    def test_next_milestone_structure(self, ome):
        dash = ome.life_dashboard()
        nm = dash["next_milestone"]
        assert "type" in nm
        assert "label" in nm
        assert "progress_pct" in nm
        assert "remaining" in nm

    def test_backward_compat_fields(self, ome):
        """Old fields should still be present."""
        dash = ome.life_dashboard()
        assert "bond" in dash
        assert "achievements" in dash
        assert "skills" in dash
        assert "streak" in dash
        assert "emotion" in dash
        assert "permissions" in dash
        assert "autonomy" in dash
        assert "highlights" in dash


# ── Enhanced chat_rich() ────────────────────────────────────────────

class TestChatRichEnhanced:
    def test_has_follow_ups(self, ome):
        result = ome.chat_rich("你好！")
        assert "follow_ups" in result
        assert isinstance(result["follow_ups"], list)

    def test_has_memory_impact(self, ome):
        result = ome.chat_rich("我住在北京，在龙湖上班")
        assert "memory_impact" in result
        mi = result["memory_impact"]
        assert "facts_added" in mi
        assert "facts" in mi
        assert isinstance(mi["facts"], list)

    def test_backward_compat_fields(self, ome):
        """Old fields should still exist."""
        result = ome.chat_rich("Hi!")
        assert "reply" in result
        assert "memories_recalled" in result
        assert "emotion" in result
        assert "bond" in result
        assert "evolution_pending" in result
        assert "phase" in result
        assert "thinking" in result


# ── store.py new methods ────────────────────────────────────────────

class TestStoreDecayStatus:
    def test_empty_store(self, ome):
        decay = ome.soul.store.decay_status()
        assert decay == {"active": 0, "fading": 0, "forgotten": 0}

    def test_active_memory(self, ome):
        ome.remember("active memory", source="manual")
        decay = ome.soul.store.decay_status()
        assert decay["active"] >= 1

    def test_count_recent(self, ome):
        ome.remember("recent memory", source="manual")
        recent = ome.soul.store.count_recent(7)
        assert recent["added"] >= 1


# ── _save_emotion_snapshot / emotion persistence ─────────────────────

class TestEmotionSnapshotPersistence:
    def test_snapshot_saved_after_chat(self, ome):
        ome.chat("太开心了！")
        raw = ome.soul.store.get_state("ome.emotion_history")
        assert raw is not None
        history = json.loads(raw)
        today = datetime.now().strftime("%Y-%m-%d")
        assert today in history

    def test_snapshot_overwrites_same_day(self, ome):
        ome.chat("开心")
        ome.chat("伤心")
        raw = ome.soul.store.get_state("ome.emotion_history")
        history = json.loads(raw)
        today = datetime.now().strftime("%Y-%m-%d")
        # Only one entry for today (overwritten)
        assert today in history
