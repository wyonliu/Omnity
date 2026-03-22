"""Tests for Ome Life System — bond, achievements, growth."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def ome_dir(tmp_path):
    return tmp_path / "test_ome"


def test_bond_levels(ome_dir):
    """Bond level advances with interactions."""
    from ome.core import Ome

    ome = Ome.create(ome_dir, name="Test", traits=["curious"])

    assert ome.bond.level == 0
    assert ome.bond.total_interactions == 0

    # Chat 10 times → should reach Lv.1
    for i in range(10):
        ome.remember(f"Fact number {i}")

    # remember doesn't bump bond — only chat does
    assert ome.bond.level == 0

    for i in range(11):
        ome.chat(f"Hello {i}")

    assert ome.bond.total_interactions >= 11
    assert ome.bond.level >= 1


def test_bond_persistence(ome_dir):
    """Bond state persists across load/save cycles."""
    from ome.core import Ome

    ome = Ome.create(ome_dir, name="Test", traits=["curious"])
    for i in range(5):
        ome.chat(f"Hi {i}")

    interactions_before = ome.bond.total_interactions

    # Reload
    ome2 = Ome.load(ome_dir)
    assert ome2.bond.total_interactions == interactions_before


def test_achievements_unlock():
    """Achievement tracker unlocks correctly."""
    from ome.life.achievements import AchievementTracker

    tracker = AchievementTracker()
    assert tracker.unlocked_count() == 0

    ach = tracker.check_and_unlock("first_chat")
    assert ach is not None
    assert ach.name == "破冰"
    assert tracker.unlocked_count() == 1

    # Duplicate unlock returns None
    ach2 = tracker.check_and_unlock("first_chat")
    assert ach2 is None
    assert tracker.unlocked_count() == 1


def test_achievements_serialization():
    """Achievement tracker serializes and deserializes."""
    from ome.life.achievements import AchievementTracker

    tracker = AchievementTracker()
    tracker.check_and_unlock("first_chat")
    tracker.check_and_unlock("first_memory")

    data = tracker.to_dict()
    restored = AchievementTracker.from_dict(data)
    assert restored.unlocked_count() == 2
    assert "first_chat" in restored.unlocked


def test_growth_engine():
    """Skill competence tracks usage."""
    from ome.life.growth import GrowthEngine

    engine = GrowthEngine()
    chat_skill = engine.skills["chat"]
    initial = chat_skill.competence

    engine.record_action("chat", success=True, quality=0.8)
    assert chat_skill.competence > initial
    assert chat_skill.uses == 1
    assert chat_skill.successes == 1

    engine.record_action("chat", success=False, quality=0.0)
    assert chat_skill.uses == 2
    assert chat_skill.successes == 1


def test_growth_serialization():
    """Growth engine serializes and deserializes."""
    from ome.life.growth import GrowthEngine

    engine = GrowthEngine()
    engine.record_action("chat", success=True, quality=0.9)
    engine.record_action("write", success=True, quality=0.7)

    data = engine.to_dict()
    restored = GrowthEngine.from_dict(data)
    assert restored.skills["chat"].uses == 1
    assert restored.skills["write"].uses == 1


def test_bond_streak():
    """Streak counting works correctly."""
    from ome.life.bond import BondState

    bond = BondState()

    bond.record_interaction("2026-03-20")
    assert bond.streak_days == 1

    bond.record_interaction("2026-03-21")
    assert bond.streak_days == 2

    bond.record_interaction("2026-03-22")
    assert bond.streak_days == 3

    # Skip a day — streak resets but no punishment
    bond.record_interaction("2026-03-25")
    assert bond.streak_days == 1  # restarted, not zero
    assert bond.max_streak == 3  # max preserved


def test_life_dashboard(ome_dir):
    """Life dashboard returns structured data."""
    from ome.core import Ome

    ome = Ome.create(ome_dir, name="Test", traits=["curious"])
    ome.chat("Hello!")

    dashboard = ome.life_dashboard()
    assert "bond" in dashboard
    assert "achievements" in dashboard
    assert "skills" in dashboard
    assert "streak" in dashboard
    assert dashboard["bond"]["level"] >= 0
    assert isinstance(dashboard["achievements"]["unlocked"], list)
