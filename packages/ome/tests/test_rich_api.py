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

    def test_commits_since_reflection_increments(self, ome):
        ome.remember("fact 1")
        ome.remember("fact 2")
        assert ome.commits_since_reflection >= 2

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
        """Without LLM, should still return the text as a note."""
        result = ome.smart_extract("明天下午3点开会")
        assert len(result["notes"]) >= 1

    def test_commits_to_memory(self, ome):
        ome.smart_extract("I'm a Python developer")
        results = ome.recall("Python")
        assert len(results) > 0
