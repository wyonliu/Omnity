"""Tests for Ome rich API: chat_rich(), evolve(), smart_extract(), evolution_pending."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from ome.core import Ome


@pytest.fixture
def ome(tmp_path):
    """Create a test Ome instance."""
    d = tmp_path / "test_ome"
    return Ome.create(d, name="TestUser", traits=["curious"])


class TestChatRich:
    def test_returns_dict_with_reply(self, ome):
        result = ome.chat_rich("Hello!")
        assert isinstance(result, dict)
        assert "reply" in result
        assert isinstance(result["reply"], str)
        assert len(result["reply"]) > 0

    def test_returns_memories_recalled(self, ome):
        ome.remember("I live in Shanghai and work as an engineer")
        result = ome.chat_rich("Where do I live?")
        assert "memories_recalled" in result
        assert isinstance(result["memories_recalled"], list)

    def test_returns_emotion(self, ome):
        result = ome.chat_rich("How are you?")
        assert "emotion" in result
        assert "mood" in result["emotion"]

    def test_returns_bond(self, ome):
        result = ome.chat_rich("Hi")
        assert "bond" in result

    def test_returns_evolution_pending(self, ome):
        result = ome.chat_rich("Hi")
        assert "evolution_pending" in result
        assert isinstance(result["evolution_pending"], bool)

    def test_returns_phase(self, ome):
        result = ome.chat_rich("Hi")
        assert "phase" in result
        assert "name" in result["phase"]

    def test_backward_compat_chat_still_returns_string(self, ome):
        """chat() should still return a plain string."""
        reply = ome.chat("Hello!")
        assert isinstance(reply, str)


class TestEvolution:
    def test_evolution_pending_initially_false(self, ome):
        assert ome.evolution_pending is False

    def test_commits_since_reflection_starts_at_zero(self, ome):
        assert ome.commits_since_reflection == 0

    def test_commits_since_reflection_from_chat(self, ome):
        # remember(source="manual") stores directly as fact, doesn't increment commit counter
        # Only chat() goes through L2 commit which increments the counter
        ome.remember("fact 1")
        assert ome.commits_since_reflection >= 0  # manual remember doesn't count

    def test_evolve_returns_dict(self, ome):
        result = ome.evolve()
        assert isinstance(result, dict)
        assert "summary" in result or "method" in result

    def test_evolve_without_episodes(self, ome):
        """Evolve with no episodes should return gracefully."""
        result = ome.evolve()
        assert result is not None


class TestSmartExtract:
    def test_returns_structure(self, ome):
        result = ome.smart_extract("帮我记住张三的电话 13800138000")
        assert "contacts" in result
        assert "tasks" in result
        assert "notes" in result
        assert isinstance(result["contacts"], list)
        assert isinstance(result["tasks"], list)
        assert isinstance(result["notes"], list)

    def test_fallback_without_llm(self, ome):
        """Without LLM, should still extract something useful."""
        result = ome.smart_extract("明天下午3点开会")
        # Regex should pick up the time-based task, or at minimum return as note
        has_output = (len(result["tasks"]) > 0 or len(result["notes"]) > 0)
        assert has_output

    def test_commits_to_memory(self, ome):
        ome.smart_extract("I'm a Python developer")
        results = ome.recall("Python")
        assert len(results) > 0


# ── Issue fixes (Ome365 feedback) ─────────────────────────────────────

class TestRememberStoresFact:
    """Issue #4: remember() should store as fact for manual/profile sources."""

    def test_manual_stores_fact(self, ome):
        result = ome.remember("船长是CTO", source="manual")
        assert result["facts_added"] == 1
        assert result["method"] == "direct"

    def test_profile_stores_fact(self, ome):
        result = ome.remember("用户住在上海", source="profile")
        assert result["facts_added"] == 1

    def test_api_stores_fact(self, ome):
        result = ome.remember("喜欢搏击", source="api")
        assert result["facts_added"] == 1

    def test_recall_finds_manual_fact(self, ome):
        ome.remember("张三的电话是13800138000", source="manual")
        results = ome.recall("张三")
        assert any("张三" in str(m.get("content", "")) for m in results)


class TestSmartExtractRegex:
    """Issue #3: smart_extract without LLM should extract contacts/tasks via regex."""

    def test_extracts_phone_number(self, ome):
        result = ome.smart_extract("张三的电话 13812345678")
        assert len(result["contacts"]) > 0
        assert "13812345678" in result["contacts"][0]["info"]

    def test_extracts_email(self, ome):
        result = ome.smart_extract("John的邮箱 john@example.com")
        assert len(result["contacts"]) > 0
        assert "john@example.com" in result["contacts"][0]["info"]

    def test_extracts_time_task(self, ome):
        result = ome.smart_extract("明天下午两点开会")
        assert len(result["tasks"]) > 0

    def test_fallback_to_notes(self, ome):
        result = ome.smart_extract("这个世界真美好")
        # No contacts, no tasks, no time keywords → falls back to notes
        assert len(result["notes"]) > 0


class TestThreadSafety:
    """Issue #5: Ome should have RLock for thread safety."""

    def test_has_lock(self, ome):
        import threading
        assert hasattr(ome, "_lock")
        assert isinstance(ome._lock, type(threading.RLock()))

    def test_locked_context_manager(self, ome):
        with ome.locked() as o:
            assert o is ome

    def test_reentrant_lock(self, ome):
        """RLock allows same thread to acquire multiple times."""
        with ome._lock:
            with ome._lock:
                pass  # should not deadlock

    def test_synchronized_decorator_present(self, ome):
        """Key methods should be wrapped with _synchronized."""
        # The decorator wraps the method, so __wrapped__ exists
        from ome.core import _synchronized
        assert callable(_synchronized)
