"""Ome integration tests."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def ome_dir(tmp_path):
    """Create a temp Ome for testing."""
    return tmp_path / "test_ome"


def test_create_and_load(ome_dir):
    """Create an Ome, then load it back."""
    from ome.core import Ome

    ome = Ome.create(
        ome_dir, name="Alice",
        traits=["curious", "builder"],
        style="direct",
        values=["honesty"],
    )
    assert ome.name == "Alice"
    assert "curious" in ome.traits
    assert (ome_dir / "identity.yaml").exists()
    assert (ome_dir / "memory.db").exists()

    # Load it back
    ome2 = Ome.load(ome_dir)
    assert ome2.name == "Alice"
    assert "curious" in ome2.traits


def test_remember_and_recall(ome_dir):
    """Remember something, recall it."""
    from ome.core import Ome

    ome = Ome.create(ome_dir, name="Bob", traits=["analytical"])
    ome.remember("I'm a Python developer working on distributed systems")
    ome.remember("My favorite framework is FastAPI")

    results = ome.recall("Python")
    assert len(results) > 0
    contents = " ".join(r.get("content", "") for r in results)
    assert "Python" in contents


def test_forget(ome_dir):
    """Forget something permanently."""
    from ome.core import Ome

    ome = Ome.create(ome_dir, name="Carol")
    ome.remember("My secret password is hunter2")
    results_before = ome.recall("password")

    ome.forget("password")
    results_after = ome.recall("password")
    assert len(results_after) <= len(results_before)


def test_export_json(ome_dir):
    """Export as full persona JSON."""
    from ome.core import Ome

    ome = Ome.create(ome_dir, name="Dave", traits=["creative"])
    ome.remember("I love painting and music")

    persona = ome.export(context="art")
    assert persona["identity"]["name"] == "Dave"
    assert "creative" in persona["identity"]["traits"]
    assert "ome_version" in persona


def test_export_system_prompt(ome_dir):
    """Export as system prompt text."""
    from ome.core import Ome

    ome = Ome.create(ome_dir, name="Eve", traits=["direct"])
    prompt = ome.export_system_prompt()
    assert "Eve" in prompt
    assert isinstance(prompt, str)


def test_status(ome_dir):
    """Check status after some operations."""
    from ome.core import Ome

    ome = Ome.create(ome_dir, name="Frank", traits=["curious"])
    ome.remember("I work at a startup")

    s = ome.status()
    assert s["ome_version"] == "0.7.0"
    assert "memory" in s


def test_chat_without_llm(ome_dir):
    """Chat without LLM configured returns helpful fallback."""
    from ome.core import Ome

    ome = Ome.create(ome_dir, name="Grace")
    reply = ome.chat("What do you know about Python?")

    # Without LLM, should return user-friendly fallback (no API key exposure)
    assert "抱歉" in reply or "配置" in reply
    # But the conversation should still be committed to memory
    results = ome.recall("Python")
    assert len(results) > 0


def test_chat_commits_to_memory(ome_dir):
    """Chat automatically commits conversations."""
    from ome.core import Ome

    ome = Ome.create(ome_dir, name="Hank")
    ome.chat("I just started learning Rust today")

    results = ome.recall("Rust")
    contents = " ".join(r.get("content", "") for r in results)
    assert "Rust" in contents


# ── Streaming API (Ome v0.8) ───────────────────────────────────────

def test_chat_stream_prepare_returns_prompt_and_meta(ome_dir):
    """chat_stream_prepare builds a system prompt and a meta snapshot."""
    from ome.core import Ome

    ome = Ome.create(ome_dir, name="Ivy", traits=["warm"])
    prep = ome.chat_stream_prepare("hello there")

    assert isinstance(prep["system_prompt"], str)
    assert len(prep["system_prompt"]) > 100  # should contain real prompt content
    assert "Ivy" in prep["system_prompt"]
    assert prep["user_message"] == "hello there"

    meta = prep["meta"]
    assert "mood" in meta
    assert "mood_emoji" in meta
    assert "bond_level" in meta
    assert "streak_days" in meta
    assert "phase_id" in meta
    assert "phase_name" in meta
    assert meta["memories_recalled_count"] == 0  # fresh Ome
    assert meta["is_crisis"] is False


def test_chat_stream_prepare_caches_context_for_finalize(ome_dir):
    """Prepare stashes context that finalize will consume (keyed on id(message))."""
    from ome.core import Ome

    ome = Ome.create(ome_dir, name="Jack")
    msg = "tell me about distributed systems"
    ome.chat_stream_prepare(msg)
    assert hasattr(ome, "_stream_contexts")
    assert id(msg) in ome._stream_contexts
    ctx = ome._stream_contexts[id(msg)]
    assert "phase" in ctx
    assert "memories_recalled" in ctx


def test_chat_stream_finalize_commits_and_updates_life_state(ome_dir):
    """Finalize does commit + bond/streak/emotion updates, just like chat()."""
    from ome.core import Ome

    ome = Ome.create(ome_dir, name="Kate")
    before_interactions = ome.bond.total_interactions

    msg = "I love building distributed databases"
    ome.chat_stream_prepare(msg)
    result = ome.chat_stream_finalize(msg, "That sounds fascinating!")

    assert result["reply"]
    assert "mood" in result
    assert "bond_level" in result
    # Life state advanced
    assert ome.bond.total_interactions == before_interactions + 1
    # Conversation got committed to memory
    found = ome.recall("distributed databases")
    assert any("distributed" in (r.get("content", "") or "") for r in found)
    # Context was consumed (not leaking)
    assert id(msg) not in ome._stream_contexts


def test_chat_stream_finalize_handles_empty_reply(ome_dir):
    """If the LLM stream produced nothing, finalize returns a graceful fallback."""
    from ome.core import Ome

    ome = Ome.create(ome_dir, name="Liam")
    msg = "hello"
    ome.chat_stream_prepare(msg)
    result = ome.chat_stream_finalize(msg, "")

    assert result["reply"]
    assert "抱歉" in result["reply"] or "connected" in result["reply"].lower()


def test_chat_stream_finalize_without_prepare_uses_degraded_path(ome_dir):
    """finalize is robust to being called without a prior prepare (e.g. caller bug)."""
    from ome.core import Ome

    ome = Ome.create(ome_dir, name="Mia")
    result = ome.chat_stream_finalize("orphan message", "a reply")
    assert result["reply"]
    assert "bond_level" in result


def test_stream_tokens_yields_empty_when_no_llm(ome_dir):
    """stream_tokens falls through silently when no LLM is available."""
    from ome.core import Ome

    ome = Ome.create(ome_dir, name="Nina")
    chunks = list(ome.stream_tokens("system", "user"))
    # Without an LLM configured, the router has no candidates → empty stream
    assert chunks == []
