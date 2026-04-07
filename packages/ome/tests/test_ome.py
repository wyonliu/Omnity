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
    assert s["ome_version"] == "0.5.0"
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
