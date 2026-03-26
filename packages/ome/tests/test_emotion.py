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
    state = EmotionState(mood="happy", energy=0.8, warmth=0.7, valence=0.5, arousal=0.6)
    state.recent_signals = ["happy", "happy", "excited"]

    data = state.to_dict()
    restored = EmotionState.from_dict(data)
    assert restored.mood == "happy"
    assert restored.energy == 0.8
    assert restored.valence == 0.5
    assert restored.arousal == 0.6
    assert len(restored.recent_signals) == 3


# =============================================================================
# Valence-Arousal Model (Phase 1)
# =============================================================================

def test_valence_arousal_defaults():
    """Default valence is 0.0 (neutral), arousal is 0.3 (calm)."""
    from ome.life.emotion import EmotionState
    state = EmotionState()
    assert state.valence == 0.0
    assert state.arousal == 0.3
    assert state.inertia == 0.7


def test_valence_shifts_positive_on_happy():
    """Happy messages shift valence toward positive."""
    from ome.life.emotion import EmotionState
    state = EmotionState()
    initial_valence = state.valence
    for msg in ["太好了", "开心", "不错哈哈", "谢谢你"]:
        state.update_from_message(msg)
    assert state.valence > initial_valence


def test_valence_shifts_negative_on_stress():
    """Stressed messages shift valence toward negative."""
    from ome.life.emotion import EmotionState
    state = EmotionState()
    initial_valence = state.valence
    for msg in ["焦虑死了", "deadline要到了", "压力好大"]:
        state.update_from_message(msg)
    assert state.valence < initial_valence


def test_arousal_rises_with_excitement():
    """Excited messages raise arousal."""
    from ome.life.emotion import EmotionState
    state = EmotionState()
    initial_arousal = state.arousal
    for msg in ["太棒了！", "绝了！", "incredible! amazing!"]:
        state.update_from_message(msg)
    assert state.arousal > initial_arousal


def test_emotional_momentum_prevents_instant_flip():
    """Mood doesn't flip instantly from happy to sad with inertia."""
    from ome.life.emotion import EmotionState
    # Start with positive valence
    state = EmotionState(valence=0.6, arousal=0.4)
    # Single sad message should NOT flip to full negative
    state.update_from_message("有点难过")
    assert state.valence > 0.0  # still positive due to momentum


def test_momentum_allows_gradual_shift():
    """Repeated sad messages eventually shift mood."""
    from ome.life.emotion import EmotionState
    state = EmotionState(valence=0.6, arousal=0.4)
    for _ in range(10):
        state.update_from_message("好难过 好累 唉")
    assert state.valence < 0.0  # eventually shifts negative


def test_high_inertia_resists_change():
    """Higher inertia means slower mood shifts."""
    from ome.life.emotion import EmotionState
    state_low = EmotionState(inertia=0.3)
    state_high = EmotionState(inertia=0.9)

    for msg in ["太好了！开心！", "太好了！开心！"]:
        state_low.update_from_message(msg)
        state_high.update_from_message(msg)

    # Low inertia should shift more
    assert state_low.valence > state_high.valence


def test_llm_thinking_uses_reduced_inertia():
    """LLM thinking update shifts mood more strongly than keyword matching."""
    from ome.life.emotion import EmotionState
    state_kw = EmotionState()
    state_llm = EmotionState()

    # Both start neutral (valence=0)
    state_kw.update_from_message("太好了 开心")
    state_llm.update_from_llm_thinking("happy", "genuinely delighted")

    # LLM should shift more due to reduced inertia
    assert state_llm.valence > state_kw.valence


def test_mood_derived_from_valence_arousal():
    """Mood is derived from closest point in VA space."""
    from ome.life.emotion import EmotionState
    # High positive valence + high arousal = excited
    state = EmotionState(valence=0.8, arousal=0.9)
    state._recalculate()
    assert state.mood == "excited"

    # Negative valence + low arousal = sad
    state2 = EmotionState(valence=-0.6, arousal=0.2)
    state2._recalculate()
    assert state2.mood == "sad"


def test_describe_for_prompt():
    """describe_for_prompt produces a non-empty natural language description."""
    from ome.life.emotion import EmotionState
    state = EmotionState(mood="happy", valence=0.6, arousal=0.5, energy=0.8, warmth=0.7)
    desc = state.describe_for_prompt()
    assert "happy" in desc
    assert "positive" in desc
    assert len(desc) > 50


def test_describe_for_prompt_negative():
    """Negative valence produces appropriate description."""
    from ome.life.emotion import EmotionState
    state = EmotionState(mood="sad", valence=-0.6, arousal=0.1, energy=0.2, warmth=0.3)
    desc = state.describe_for_prompt()
    assert "heavy" in desc or "down" in desc
    assert "low" in desc.lower() or "quiet" in desc  # low energy or low arousal


def test_serialization_with_va():
    """Valence, arousal, inertia survive serialization."""
    from ome.life.emotion import EmotionState
    state = EmotionState(valence=0.42, arousal=0.73, inertia=0.65)
    data = state.to_dict()
    assert data["valence"] == 0.42
    assert data["arousal"] == 0.73
    assert data["inertia"] == 0.65

    restored = EmotionState.from_dict(data)
    assert restored.valence == 0.42
    assert restored.arousal == 0.73
    assert restored.inertia == 0.65
