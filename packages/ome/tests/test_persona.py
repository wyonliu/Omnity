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
