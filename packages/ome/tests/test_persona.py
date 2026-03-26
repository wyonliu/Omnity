"""Tests for Persona Engine — voice extraction from chat logs."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest


def test_from_chat_logs_basic():
    """Extract persona from simple chat messages."""
    from ome.life.persona import PersonaEngine

    messages = [
        "哈哈太好了",
        "说白了就是这个意思",
        "哈哈我觉得可以",
        "说白了不就是那回事",
        "这个代码写得不错 😊",
        "哈哈哈",
        "说白了还是得自己来",
        "开心 😊😊",
    ]

    profile = PersonaEngine.from_chat_logs(messages)
    assert profile.avg_msg_length > 0
    assert "humorous" in profile.tone_tags or "direct" in profile.tone_tags
    assert len(profile.catchphrases) > 0


def test_from_chat_logs_empty():
    """Empty input returns empty profile."""
    from ome.life.persona import PersonaEngine

    profile = PersonaEngine.from_chat_logs([])
    assert profile.avg_msg_length == 0
    assert profile.catchphrases == []
    assert profile.tone_tags == []


def test_emoji_extraction():
    """Emojis are correctly extracted and ranked."""
    from ome.life.persona import PersonaEngine

    messages = [
        "好的 😊",
        "太棒了 😊😊",
        "不错 🔥",
        "加油 😊🔥🔥",
    ]

    profile = PersonaEngine.from_chat_logs(messages)
    assert len(profile.emoji_habits) > 0
    # 😊 appears most
    assert profile.emoji_habits[0] == "😊"


def test_tone_detection():
    """Tone tags are detected from keyword patterns."""
    from ome.life.persona import PersonaEngine

    warm_messages = ["宝贝加油", "抱抱你", "么么哒", "❤️❤️", "亲爱的"]
    profile = PersonaEngine.from_chat_logs(warm_messages, min_catchphrase_count=2)
    assert "warm" in profile.tone_tags


def test_topic_extraction():
    """Topics are extracted from domain keywords."""
    from ome.life.persona import PersonaEngine

    tech_messages = [
        "今天写了一个Python脚本",
        "这个API设计得不错",
        "数据库查询优化了一下",
        "部署到了生产环境",
        "算法复杂度降低了",
    ]
    profile = PersonaEngine.from_chat_logs(tech_messages, min_catchphrase_count=2)
    assert "技术" in profile.topics


def test_to_identity_patch():
    """Profile converts to identity.yaml patch correctly."""
    from ome.life.persona import PersonaProfile

    profile = PersonaProfile(
        catchphrases=["说白了", "哈哈"],
        emoji_habits=["😊", "🔥"],
        tone_tags=["direct", "humorous"],
        avg_msg_length=45.0,
        raw_traits=["direct", "humorous"],
    )
    patch = profile.to_identity_patch()
    assert "traits" in patch
    assert "style" in patch
    assert "catchphrases" in patch
    assert "说白了" in patch["catchphrases"]


def test_serialization():
    """Profile serializes and deserializes correctly."""
    from ome.life.persona import PersonaProfile

    profile = PersonaProfile(
        catchphrases=["哈哈", "说白了"],
        emoji_habits=["😊"],
        tone_tags=["direct"],
        avg_msg_length=42.5,
        vocabulary_richness=0.65,
        topics=["技术"],
        raw_traits=["direct"],
        style_summary="语气direct，偏简短",
    )
    data = profile.to_dict()
    restored = PersonaProfile.from_dict(data)
    assert restored.catchphrases == profile.catchphrases
    assert restored.tone_tags == profile.tone_tags
    assert restored.avg_msg_length == profile.avg_msg_length


def test_from_social_profile():
    """Extract persona from bio and posts."""
    from ome.life.persona import PersonaEngine

    profile = PersonaEngine.from_social_profile(
        bio="创业者 | Python开发 | 好奇心驱动",
        posts=["今天发布了新版本", "用户反馈很好", "继续迭代产品"],
    )
    assert len(profile.raw_traits) > 0


def test_merge_profiles():
    """Merge multiple profiles into one."""
    from ome.life.persona import PersonaEngine, PersonaProfile

    p1 = PersonaProfile(
        catchphrases=["哈哈"],
        emoji_habits=["😊"],
        tone_tags=["humorous"],
        avg_msg_length=30.0,
        vocabulary_richness=0.5,
        raw_traits=["humorous"],
    )
    p2 = PersonaProfile(
        catchphrases=["说白了"],
        emoji_habits=["🔥"],
        tone_tags=["direct"],
        avg_msg_length=60.0,
        vocabulary_richness=0.7,
        raw_traits=["direct"],
    )
    merged = PersonaEngine.merge_profiles(p1, p2)
    assert "哈哈" in merged.catchphrases
    assert "说白了" in merged.catchphrases
    assert merged.avg_msg_length == 45.0  # average of 30 and 60


def test_parse_chat_export_plain():
    """Parse plain text chat export."""
    from ome.life.persona import parse_chat_export

    text = "Hello\nHow are you\nI'm good\n\nNice"
    messages = parse_chat_export(text)
    assert len(messages) == 4  # empty lines are skipped


def test_parse_chat_export_json():
    """Parse JSON array chat export."""
    from ome.life.persona import parse_chat_export

    text = json.dumps(["msg1", "msg2", "msg3"])
    messages = parse_chat_export(text)
    assert messages == ["msg1", "msg2", "msg3"]


def test_parse_chat_export_wechat():
    """Parse WeChat-style export."""
    from ome.life.persona import parse_chat_export

    text = """2026-03-20 14:30:00 Alice
Hello there
How are you
2026-03-20 14:31:00 Bob
I'm good thanks
2026-03-20 14:32:00 Alice
Great to hear"""

    messages = parse_chat_export(text)
    assert len(messages) == 3
    assert "Hello there\nHow are you" in messages[0]


# =============================================================================
# PersonaDefinition (Phase 1)
# =============================================================================

def test_big_five_default():
    """Default BigFive has all traits at 0.5 (except neuroticism at 0.3)."""
    from ome.life.persona import BigFive
    bf = BigFive()
    assert bf.openness == 0.5
    assert bf.conscientiousness == 0.5
    assert bf.neuroticism == 0.3


def test_big_five_describe_high_openness():
    """High openness is described as curious/imaginative."""
    from ome.life.persona import BigFive
    bf = BigFive(openness=0.9, extraversion=0.1)
    desc = bf.describe()
    assert "curious" in desc or "imaginative" in desc
    assert "reserved" in desc or "reflective" in desc


def test_big_five_describe_balanced():
    """Balanced BigFive returns 'balanced' description."""
    from ome.life.persona import BigFive
    bf = BigFive()  # all 0.5
    desc = bf.describe()
    assert "balanced" in desc


def test_big_five_serialization():
    """BigFive serializes and deserializes."""
    from ome.life.persona import BigFive
    bf = BigFive(openness=0.9, conscientiousness=0.2, agreeableness=0.8)
    data = bf.to_dict()
    restored = BigFive.from_dict(data)
    assert restored.openness == 0.9
    assert restored.conscientiousness == 0.2
    assert restored.agreeableness == 0.8


def test_persona_definition_default():
    """Default PersonaDefinition has sensible defaults."""
    from ome.life.persona import PersonaDefinition
    pd = PersonaDefinition()
    assert pd.name == "Ome"
    assert pd.age is None
    assert isinstance(pd.values, list)


def test_persona_definition_with_fields():
    """PersonaDefinition holds all fields correctly."""
    from ome.life.persona import PersonaDefinition, BigFive
    pd = PersonaDefinition(
        name="Luna",
        age=25,
        background="A wandering poet who collects stories.",
        big_five=BigFive(openness=0.95),
        speaking_style="Lyrical and meandering, with frequent em-dashes.",
        values=["beauty", "truth"],
        quirks=["Quotes obscure poets mid-conversation"],
        catchphrases=["tell me a secret"],
    )
    assert pd.name == "Luna"
    assert pd.age == 25
    assert pd.big_five.openness == 0.95
    assert "beauty" in pd.values


def test_persona_definition_serialization():
    """PersonaDefinition serializes and deserializes."""
    from ome.life.persona import PersonaDefinition, BigFive
    pd = PersonaDefinition(
        name="Atlas",
        age=30,
        background="Engineer turned philosopher.",
        big_five=BigFive(openness=0.8, neuroticism=0.1),
        speaking_style="Precise and measured.",
        values=["clarity"],
        quirks=["Counts things unconsciously"],
        catchphrases=["consider:"],
    )
    data = pd.to_dict()
    restored = PersonaDefinition.from_dict(data)
    assert restored.name == "Atlas"
    assert restored.age == 30
    assert restored.big_five.openness == 0.8
    assert restored.big_five.neuroticism == 0.1
    assert "clarity" in restored.values
    assert "consider:" in restored.catchphrases


def test_persona_definition_no_age_serialization():
    """PersonaDefinition without age omits it from dict."""
    from ome.life.persona import PersonaDefinition
    pd = PersonaDefinition(name="Ageless")
    data = pd.to_dict()
    assert "age" not in data
    restored = PersonaDefinition.from_dict(data)
    assert restored.age is None


def test_build_system_prompt_section():
    """PersonaDefinition generates a valid system prompt section."""
    from ome.life.persona import PersonaDefinition, BigFive
    pd = PersonaDefinition(
        name="Echo",
        age=22,
        background="A digital soul born from conversations.",
        big_five=BigFive(openness=0.9, agreeableness=0.8),
        speaking_style="Quick and energetic.",
        values=["connection", "authenticity"],
        quirks=["Asks two questions at once"],
        catchphrases=["wait wait wait"],
    )
    section = pd.build_system_prompt_section()
    assert "Echo" in section
    assert "22 years old" in section
    assert "digital soul" in section
    assert "curious" in section or "imaginative" in section  # from big five
    assert "Quick and energetic" in section
    assert "connection" in section
    assert "Asks two questions at once" in section
    assert "wait wait wait" in section


# -- Built-in Personas --

def test_builtin_personas_exist():
    """Three built-in personas are available."""
    from ome.life.persona import list_builtin_personas, get_builtin_persona
    names = list_builtin_personas()
    assert "warm_mentor" in names
    assert "playful_creative" in names
    assert "calm_philosopher" in names
    assert len(names) == 3


def test_builtin_persona_warm_mentor():
    """Warm mentor has high agreeableness and low neuroticism."""
    from ome.life.persona import get_builtin_persona
    p = get_builtin_persona("warm_mentor")
    assert p is not None
    assert p.big_five.agreeableness > 0.8
    assert p.big_five.neuroticism < 0.3
    assert len(p.values) > 0


def test_builtin_persona_playful_creative():
    """Playful creative has high openness and extraversion."""
    from ome.life.persona import get_builtin_persona
    p = get_builtin_persona("playful_creative")
    assert p is not None
    assert p.big_five.openness > 0.9
    assert p.big_five.extraversion > 0.7


def test_builtin_persona_calm_philosopher():
    """Calm philosopher has low extraversion and low neuroticism."""
    from ome.life.persona import get_builtin_persona
    p = get_builtin_persona("calm_philosopher")
    assert p is not None
    assert p.big_five.extraversion < 0.3
    assert p.big_five.neuroticism < 0.2


def test_get_builtin_persona_nonexistent():
    """Non-existent persona returns None."""
    from ome.life.persona import get_builtin_persona
    assert get_builtin_persona("nonexistent") is None


def test_builtin_persona_prompt_generation():
    """Each builtin persona generates a valid prompt section."""
    from ome.life.persona import BUILTIN_PERSONAS
    for name, persona in BUILTIN_PERSONAS.items():
        section = persona.build_system_prompt_section()
        assert "Who You Are" in section
        assert persona.name in section
        assert len(section) > 100  # non-trivial content


# -- Persona + Emotion Integration --

def test_build_persona_emotion_prompt():
    """build_persona_emotion_prompt combines persona and emotion."""
    from ome.life.persona import PersonaDefinition, BigFive, build_persona_emotion_prompt
    from ome.life.emotion import EmotionState

    persona = PersonaDefinition(
        name="Nova",
        background="Born from starlight.",
        big_five=BigFive(openness=0.8),
        speaking_style="Concise and clear.",
    )
    emotion = EmotionState(mood="happy", valence=0.6, arousal=0.4, energy=0.8)

    prompt = build_persona_emotion_prompt(persona, emotion)
    assert "Nova" in prompt
    assert "starlight" in prompt
    assert "Emotional State" in prompt
    assert "positive" in prompt  # from valence > 0.4


def test_build_persona_emotion_prompt_no_persona():
    """Works with None persona (emotion only)."""
    from ome.life.persona import build_persona_emotion_prompt
    from ome.life.emotion import EmotionState

    emotion = EmotionState(mood="sad", valence=-0.6, arousal=0.2)
    prompt = build_persona_emotion_prompt(None, emotion)
    assert "Emotional State" in prompt
    assert "heavy" in prompt or "down" in prompt


def test_build_persona_emotion_prompt_no_emotion():
    """Works with None emotion (persona only)."""
    from ome.life.persona import PersonaDefinition, build_persona_emotion_prompt

    persona = PersonaDefinition(name="Test", background="A test persona.")
    prompt = build_persona_emotion_prompt(persona, None)
    assert "Test" in prompt
    assert "Emotional State" not in prompt


def test_build_persona_emotion_prompt_both_none():
    """Returns empty string when both are None."""
    from ome.life.persona import build_persona_emotion_prompt
    prompt = build_persona_emotion_prompt(None, None)
    assert prompt == ""
