"""Tests for Emotion State."""

from __future__ import annotations

import pytest


def test_emotion_default():
    """Default emotion is neutral."""
    from ome.life.emotion import EmotionState
    state = EmotionState()
    assert state.mood == "neutral"
    assert state.energy == 0.5
    assert state.warmth == 0.5


def test_happy_detection():
    """Happy keywords shift mood to happy."""
    from ome.life.emotion import EmotionState
    state = EmotionState()
    for msg in ["太好了", "开心", "不错哈哈", "谢谢你"]:
        state.update_from_message(msg)
    assert state.mood == "happy"


def test_stressed_detection():
    """Stress keywords shift mood."""
    from ome.life.emotion import EmotionState
    state = EmotionState()
    for msg in ["焦虑死了", "deadline要到了", "压力好大", "怎么办"]:
        state.update_from_message(msg)
    assert state.mood == "stressed"


def test_energy_from_streak():
    """Energy rises with streak days."""
    from ome.life.emotion import EmotionState
    state = EmotionState()
    state.update_from_interaction(streak_days=10, bond_level=2)
    assert state.energy > 0.6


def test_warmth_from_bond():
    """Warmth grows with bond level."""
    from ome.life.emotion import EmotionState
    state = EmotionState()
    state.update_from_interaction(streak_days=1, bond_level=0)
    warmth_0 = state.warmth
    state.update_from_interaction(streak_days=1, bond_level=4)
    assert state.warmth > warmth_0


def test_mood_emoji():
    """Mood emoji is correct."""
    from ome.life.emotion import EmotionState
    state = EmotionState(mood="excited")
    assert state.mood_emoji() == "🔥"


def test_style_modifier():
    """Style modifier returns appropriate text for mood."""
    from ome.life.emotion import EmotionState
    state = EmotionState(mood="sad")
    mod = state.style_modifier()
    assert "温柔" in mod or "关心" in mod


def test_serialization():
    """Emotion state serializes and deserializes."""
    from ome.life.emotion import EmotionState
    state = EmotionState(mood="happy", energy=0.8, warmth=0.7)
    state.recent_signals = ["happy", "happy", "excited"]

    data = state.to_dict()
    restored = EmotionState.from_dict(data)
    assert restored.mood == "happy"
    assert restored.energy == 0.8
    assert len(restored.recent_signals) == 3
