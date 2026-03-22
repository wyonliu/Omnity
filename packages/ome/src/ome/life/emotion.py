"""Emotion State — L0 rule-based mood inference from recent interactions.

No LLM needed. Uses keyword matching + interaction patterns to infer
the Ome's emotional state, which affects its response style.

This is NOT sentiment analysis of the user — it's the Ome's own mood,
shaped by how the relationship is going.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# Keyword patterns for detecting emotional signals in user messages
_MOOD_SIGNALS = {
    "happy": ["开心", "高兴", "太好了", "哈哈", "不错", "棒", "好的", "谢谢", "感谢",
              "happy", "great", "awesome", "nice", "thanks", "love", "❤", "😊", "🥰", "😄"],
    "sad": ["难过", "伤心", "失望", "不开心", "累了", "烦", "唉", "算了",
            "sad", "tired", "disappointed", "😢", "😔", "💔"],
    "excited": ["太棒了", "绝了", "牛", "厉害", "冲", "加油", "好期待",
                "amazing", "wow", "incredible", "🔥", "🎉", "💪", "🚀"],
    "stressed": ["焦虑", "压力", "来不及", "赶紧", "deadline", "急", "怎么办",
                 "stress", "anxiety", "overwhelm", "😰", "😤"],
    "curious": ["为什么", "怎么", "什么是", "想知道", "好奇", "有意思",
                "why", "how", "what", "curious", "interesting", "🤔"],
    "focused": ["专注", "忙着", "正在做", "别打扰", "赶工", "集中精力", "coding",
                "focus", "working", "deep work", "🎯"],
}


@dataclass
class EmotionState:
    """The Ome's current emotional state — derived from interaction patterns."""

    mood: str = "neutral"  # happy, sad, excited, stressed, curious, neutral
    energy: float = 0.5  # 0.0 (dormant) to 1.0 (energized)
    warmth: float = 0.5  # 0.0 (distant) to 1.0 (intimate)
    recent_signals: list[str] = field(default_factory=list)  # Last N mood signals

    _MAX_SIGNALS = 20

    def update_from_message(self, message: str):
        """Update mood based on a user message (L0 keyword matching)."""
        message_lower = message.lower()
        detected = []

        for mood, keywords in _MOOD_SIGNALS.items():
            score = sum(1 for kw in keywords if kw in message_lower)
            if score > 0:
                detected.append((mood, score))

        if detected:
            # Take the strongest signal
            detected.sort(key=lambda x: -x[1])
            top_mood = detected[0][0]
            self.recent_signals.append(top_mood)
            if len(self.recent_signals) > self._MAX_SIGNALS:
                self.recent_signals = self.recent_signals[-self._MAX_SIGNALS:]

        # Recalculate mood from recent signals
        self._recalculate()

    def update_from_interaction(self, *, streak_days: int = 0, bond_level: int = 0,
                                idle_days: int = 0, actions_today: int = 0,
                                action_budget: int = 50):
        """Update energy/warmth based on interaction patterns.

        Also detects system-derived moods:
        - "tired": daily action budget nearly exhausted
        - "missing_you": 3+ days without interaction
        """
        # Energy rises with activity, decays with inactivity
        if streak_days > 7:
            self.energy = min(1.0, 0.6 + streak_days * 0.02)
        elif streak_days > 0:
            self.energy = 0.4 + streak_days * 0.05
        else:
            self.energy = max(0.2, self.energy - 0.1)

        # Warmth grows with bond level
        self.warmth = min(1.0, 0.3 + bond_level * 0.12)

        # System-derived mood: tired (budget nearly exhausted)
        if action_budget > 0 and actions_today >= action_budget * 0.8:
            self.energy = max(0.1, self.energy - 0.3)
            if self.mood not in ("stressed",):
                self.mood = "tired"

        # System-derived mood: missing_you (3+ days idle)
        if idle_days >= 3 and bond_level >= 1:
            self.mood = "missing_you"
            self.warmth = min(1.0, self.warmth + 0.2)

    def _recalculate(self):
        """Recalculate mood from recent signals using weighted voting."""
        if not self.recent_signals:
            self.mood = "neutral"
            return

        # Recent signals matter more
        from collections import Counter
        weighted: Counter = Counter()
        for i, signal in enumerate(self.recent_signals):
            weight = 1.0 + i * 0.1  # More recent = higher weight
            weighted[signal] += weight

        self.mood = weighted.most_common(1)[0][0] if weighted else "neutral"

    def mood_emoji(self) -> str:
        return {
            "happy": "😊",
            "sad": "😔",
            "excited": "🔥",
            "stressed": "😰",
            "curious": "🤔",
            "focused": "🎯",
            "tired": "😴",
            "missing_you": "🥺",
            "neutral": "😌",
        }.get(self.mood, "😌")

    def style_modifier(self) -> str:
        """Return a style hint that can be injected into the system prompt."""
        modifiers = {
            "happy": "回复时语气温暖愉悦，多用积极的词汇",
            "sad": "回复时语气温柔体贴，表达关心和陪伴",
            "excited": "回复时语气热情有活力，分享用户的兴奋",
            "stressed": "回复时语气沉稳可靠，帮助用户理清思路",
            "curious": "回复时语气积极探索，和用户一起深入思考",
            "focused": "回复时简洁高效，不闲聊，直达要点",
            "tired": "回复时简短温和，表达「我今天有点累了，明天继续吧」",
            "missing_you": "回复时表达温暖想念，说「好久不见，想你了」",
            "neutral": "",
        }
        return modifiers.get(self.mood, "")

    def to_dict(self) -> dict[str, Any]:
        return {
            "mood": self.mood,
            "mood_emoji": self.mood_emoji(),
            "energy": round(self.energy, 2),
            "warmth": round(self.warmth, 2),
            "recent_signals": self.recent_signals[-10:],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "EmotionState":
        state = cls(
            mood=d.get("mood", "neutral"),
            energy=d.get("energy", 0.5),
            warmth=d.get("warmth", 0.5),
            recent_signals=d.get("recent_signals", []),
        )
        return state
