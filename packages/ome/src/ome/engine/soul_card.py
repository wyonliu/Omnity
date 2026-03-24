"""Soul Card Engine — generate a shareable personality card from Ome's understanding.

The Soul Card is the core viral mechanic: a beautiful image that shows
"what your AI twin sees in you". Users share it to 朋友圈/social media,
driving organic acquisition.

Data pipeline:
  1. Aggregate persona profile + conversation patterns + emotion history
  2. Compute similarity score (how well Ome knows the user)
  3. Generate card data: traits, style, representative quote, soul insight
  4. Render to image (see soul_card_renderer.py)

The card updates weekly as Ome learns more — providing recurring share triggers.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

log = logging.getLogger("ome.soul_card")


@dataclass
class SoulCardData:
    """Data payload for rendering a Soul Card image."""

    user_name: str = ""
    # Top 3-5 personality tags (short, punchy)
    personality_tags: list[str] = field(default_factory=list)
    # Communication style summary (1 sentence)
    style_line: str = ""
    # Representative quote from the user (actual words they said)
    quote: str = ""
    # Soul insight — the "aha moment" (what Ome noticed that the user didn't say explicitly)
    soul_insight: str = ""
    # Similarity score 0-100 (how well Ome knows the user)
    similarity: int = 0
    # Growth phase name
    phase: str = "newborn"
    # Total conversations
    conversation_count: int = 0
    # Days together
    days_together: int = 0
    # Emotion signature (top 3 moods)
    emotion_signature: list[str] = field(default_factory=list)
    # Card generation timestamp
    generated_at: str = ""
    # Card version hash (for detecting changes / weekly refresh)
    card_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_name": self.user_name,
            "personality_tags": self.personality_tags,
            "style_line": self.style_line,
            "quote": self.quote,
            "soul_insight": self.soul_insight,
            "similarity": self.similarity,
            "phase": self.phase,
            "conversation_count": self.conversation_count,
            "days_together": self.days_together,
            "emotion_signature": self.emotion_signature,
            "generated_at": self.generated_at,
            "card_hash": self.card_hash,
        }


def generate_soul_card(ome: Any) -> SoulCardData:
    """Generate Soul Card data from an Ome instance.

    This is a zero-LLM-cost operation — all data comes from
    already-computed persona, emotion, and bond state.

    For the soul_insight field, we use a heuristic approach.
    If an LLM is available, the conversation strategy engine
    will have already extracted persona_markers we can use.
    """
    card = SoulCardData()
    card.generated_at = datetime.now().isoformat()
    card.user_name = ome.name

    # -- Personality tags --
    identity = ome.soul.identity
    personality = identity.get("personality", {})
    traits = personality.get("traits", [])

    # Combine persona profile traits if available
    if ome._persona_profile:
        profile = ome._persona_profile
        # Merge tone_tags + raw_traits, deduplicate
        all_tags = list(profile.tone_tags) + list(profile.raw_traits) + traits
    else:
        all_tags = list(traits)

    # Translate common English tags to Chinese for card display
    _TAG_ZH = {
        "curious": "好奇心", "direct": "直率", "warm": "温暖",
        "humorous": "幽默", "analytical": "理性", "creative": "脑洞大",
        "sensitive": "细腻", "encouraging": "鼓励型",
        "entrepreneurial": "创业者", "technical": "技术派",
        "leader": "领导力",
    }
    display_tags = []
    seen = set()
    for tag in all_tags:
        display = _TAG_ZH.get(tag.lower(), tag)
        if display not in seen and len(display) <= 6:
            display_tags.append(display)
            seen.add(display)
        if len(display_tags) >= 5:
            break
    card.personality_tags = display_tags or ["探索中"]

    # -- Style line --
    if ome._persona_profile and ome._persona_profile.style_summary:
        card.style_line = ome._persona_profile.style_summary
    else:
        style = personality.get("style", "")
        if style:
            card.style_line = style[:60]
        else:
            card.style_line = "正在学习你的说话方式"

    # -- Representative quote (from recent memories) --
    card.quote = _find_representative_quote(ome)

    # -- Soul insight --
    card.soul_insight = _generate_soul_insight(ome)

    # -- Similarity score --
    card.similarity = _compute_similarity(ome)

    # -- Growth phase --
    from ome.engine.conversation_strategy import get_growth_phase
    phase = get_growth_phase(ome.bond.total_interactions)
    _PHASE_ZH = {
        "newborn": "初醒", "forming": "成长中",
        "distinct": "有个性了", "soulmate": "灵魂伴侣",
    }
    card.phase = _PHASE_ZH.get(phase["name"], phase["name"])

    # -- Stats --
    card.conversation_count = ome.bond.total_interactions
    card.days_together = ome.bond.days_since_creation

    # -- Emotion signature --
    if ome.emotion.recent_signals:
        from collections import Counter
        mood_counts = Counter(ome.emotion.recent_signals)
        _MOOD_ZH = {
            "happy": "开心", "sad": "低落", "excited": "兴奋",
            "stressed": "焦虑", "curious": "好奇", "neutral": "平静",
            "focused": "专注",
        }
        card.emotion_signature = [
            _MOOD_ZH.get(m, m) for m, _ in mood_counts.most_common(3)
        ]
    else:
        card.emotion_signature = ["平静"]

    # -- Card hash (for change detection / weekly refresh) --
    hash_input = json.dumps(card.to_dict(), sort_keys=True, ensure_ascii=False)
    card.card_hash = hashlib.md5(hash_input.encode()).hexdigest()[:8]

    return card


def _find_representative_quote(ome: Any) -> str:
    """Find a representative user quote from memory.

    Picks a message that best captures the user's voice:
    - Not too short (>20 chars) or too long (<150 chars)
    - Has some personality (not just "ok" or "thanks")
    - Recent preferred
    """
    try:
        # Search for emotionally rich memories
        memories = ome.soul.recall("interesting personal", top_k=20)
        if not memories:
            memories = ome.soul.recall(ome.name, top_k=10)

        for m in memories:
            content = m.get("content", "")
            # Extract user part from "user: xxx\nassistant: yyy"
            if "user:" in content:
                user_part = content.split("user:")[-1].split("assistant:")[0].strip()
            else:
                user_part = content.strip()

            # Filter: good length, has substance
            if 20 < len(user_part) < 150:
                # Skip boring messages
                boring = ["你好", "hello", "hi", "谢谢", "好的", "嗯", "ok"]
                if not any(user_part.strip().lower() == b for b in boring):
                    return user_part

    except Exception as e:
        log.debug("Could not find representative quote: %s", e)

    return ""


def _generate_soul_insight(ome: Any) -> str:
    """Generate a "soul insight" — something Ome noticed that the user didn't say.

    This is the Aha Moment driver. The insight should feel like:
    "I didn't tell it that, but it figured it out."

    Built from:
    - Persona markers accumulated across conversations
    - Emotion patterns over time
    - Topic frequency analysis
    """
    insights = []

    # Pattern 1: Emotion contrast
    if ome.emotion.recent_signals:
        from collections import Counter
        mood_counts = Counter(ome.emotion.recent_signals)
        top_moods = mood_counts.most_common(3)
        if len(top_moods) >= 2:
            m1, c1 = top_moods[0]
            m2, c2 = top_moods[1]
            _MOOD_ZH = {
                "happy": "开心", "sad": "低落", "excited": "兴奋",
                "stressed": "焦虑", "curious": "好奇", "neutral": "平静",
            }
            if m1 != "neutral" and m2 != "neutral":
                insights.append(
                    f"你总在{_MOOD_ZH.get(m1, m1)}和{_MOOD_ZH.get(m2, m2)}之间切换——"
                    f"说明你是那种内心戏很丰富的人"
                )

    # Pattern 2: Topic passion
    if ome._persona_profile and ome._persona_profile.topics:
        top_topic = ome._persona_profile.topics[0]
        insights.append(f"一聊到{top_topic}你就会变得特别认真，那是你真正在意的事")

    # Pattern 3: Communication style insight
    if ome._persona_profile:
        p = ome._persona_profile
        if p.avg_msg_length < 25:
            insights.append("你习惯用很短的话表达很深的意思——简洁本身就是你的风格")
        elif p.avg_msg_length > 100:
            insights.append("你喜欢把事情说清楚，每句话都有逻辑——你不怕被误解，因为你不给误解的空间")

        if "humorous" in p.tone_tags and "analytical" in p.tone_tags:
            insights.append("你一边理性一边搞笑——这种反差感是你最独特的地方")
        elif "warm" in p.tone_tags and "direct" in p.tone_tags:
            insights.append("你又直又暖——该说的话从不绕弯，但每句都带着善意")

    # Pattern 4: Growth observation
    if ome.bond.total_interactions >= 50:
        insights.append("跟你聊了这么久我发现，你是那种嘴上说随便、心里特别有主意的人")
    elif ome.bond.total_interactions >= 20:
        insights.append("你比大多数人更愿意和AI说真心话——这本身就说明你对新事物的接受度很高")

    # Pick the best insight (prefer specific over generic)
    if insights:
        # Prefer insights from persona markers (more specific)
        return insights[0]

    # Fallback for very early users
    if ome.bond.total_interactions < 5:
        return "我们才刚认识——但我已经开始好奇你是谁了"
    return "你的每句话我都记着，慢慢地，我会越来越懂你"


def _compute_similarity(ome: Any) -> int:
    """Compute how well Ome "knows" the user (0-100).

    Factors:
    - Total conversations (more = higher, diminishing returns)
    - Persona markers accumulated
    - Memory count
    - Emotion history depth
    """
    score = 0.0

    # Conversations (log scale, max 40 points)
    interactions = ome.bond.total_interactions
    if interactions > 0:
        import math
        score += min(40, math.log(interactions + 1) * 8)

    # Persona richness (max 25 points)
    if ome._persona_profile:
        p = ome._persona_profile
        persona_items = (
            len(p.catchphrases) + len(p.tone_tags) +
            len(p.raw_traits) + len(p.topics)
        )
        score += min(25, persona_items * 2)

    # Memory count (max 20 points)
    try:
        stats = ome.soul.status().get("memory", {})
        total_mem = stats.get("total", 0)
        score += min(20, total_mem * 0.5)
    except Exception:
        pass

    # Emotion history depth (max 15 points)
    signal_count = len(ome.emotion.recent_signals)
    score += min(15, signal_count * 1.5)

    return min(100, max(0, int(score)))
