"""Emotion State — dual-mode mood inference.

L0: Keyword matching (fast fallback, always runs)
L1: LLM-parsed emotion from <think> block (deep, zero extra cost)

When the conversation strategy engine is active, L1 emotion from the LLM's
structured thinking replaces L0 keyword matching. This gives nuanced
understanding like detecting that "升职了但感觉很空" is lonely, not happy.
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

# Crisis keywords — these indicate the user may be in emotional distress or danger.
# When detected, Ome should prioritize empathetic support over all other behaviors.
_CRISIS_KEYWORDS = [
    # Chinese
    "不想活", "想死", "自杀", "活不下去", "没有意义", "跳下去", "割腕",
    "结束生命", "遗书", "再见了", "对不起大家", "我走了", "活着好累",
    "没人在乎", "世界没有我", "不如死", "去死",
    # English
    "kill myself", "want to die", "end it all", "suicide", "self-harm",
    "no reason to live", "better off dead", "goodbye everyone",
]


def detect_crisis(message: str) -> bool:
    """Detect potential crisis/self-harm signals in a message.

    Returns True if crisis keywords are found. This is a safety net —
    false positives are acceptable, false negatives are not.
    """
    msg_lower = message.lower()
    return any(kw in msg_lower for kw in _CRISIS_KEYWORDS)


@dataclass
class EmotionState:
    """The Ome's current emotional state — derived from interaction patterns."""

    mood: str = "neutral"  # happy, sad, excited, stressed, curious, neutral
    energy: float = 0.5  # 0.0 (dormant) to 1.0 (energized)
    warmth: float = 0.5  # 0.0 (distant) to 1.0 (intimate)
    recent_signals: list[str] = field(default_factory=list)  # Last N mood signals

    _MAX_SIGNALS = 20

    def update_from_message(self, message: str):
        """Update mood based on a user message (L0 keyword matching).

        This is the fast fallback. When strategy engine is active,
        update_from_llm_thinking() provides much deeper understanding.
        """
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

    def update_from_llm_thinking(self, emotion: str, nuance: str = ""):
        """Update mood from LLM's structured thinking (L1 deep understanding).

        This overrides keyword matching with the LLM's nuanced assessment.
        e.g., "升职了但感觉很空" → emotion="lonely", nuance="表面是好消息但内心空虚"

        The emotion comes from the <think> block parsed by conversation_strategy.
        """
        # Map extended emotions to our core set + extras
        emotion_map = {
            "happy": "happy",
            "sad": "sad",
            "excited": "excited",
            "stressed": "stressed",
            "curious": "curious",
            "neutral": "neutral",
            "lonely": "sad",       # lonely maps to sad but with different nuance
            "confused": "curious",  # confused maps to curious
            "grateful": "happy",   # grateful maps to happy
            "angry": "stressed",   # angry maps to stressed
        }
        mapped = emotion_map.get(emotion, "neutral")

        # Override: LLM assessment is authoritative
        self.recent_signals.append(mapped)
        if len(self.recent_signals) > self._MAX_SIGNALS:
            self.recent_signals = self.recent_signals[-self._MAX_SIGNALS:]

        # Direct set — LLM's read is more accurate than voting
        self.mood = mapped

        # Adjust energy/warmth based on nuanced emotion
        if emotion in ("excited", "happy", "grateful"):
            self.energy = min(1.0, self.energy + 0.1)
        elif emotion in ("sad", "lonely"):
            self.energy = max(0.2, self.energy - 0.05)
            self.warmth = min(1.0, self.warmth + 0.05)  # sadness increases warmth need
        elif emotion in ("stressed", "angry"):
            self.energy = max(0.2, self.energy - 0.1)

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
        """Return a style hint for system prompt injection.

        When strategy engine is active, this is less important since the
        LLM already has full emotional context. Kept for backward compat.
        """
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
