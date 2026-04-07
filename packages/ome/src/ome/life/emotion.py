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

from ome.constants import (
    EMOTION_INERTIA_DEFAULT, EMOTION_INERTIA_LLM_FLOOR, EMOTION_INERTIA_LLM_REDUCTION,
    EMOTION_MAX_SIGNALS, EMOTION_ENERGY_POSITIVE_DELTA, EMOTION_ENERGY_SAD_DELTA,
    EMOTION_WARMTH_SAD_DELTA, EMOTION_ENERGY_STRESS_DELTA, EMOTION_ENERGY_FLOOR,
    EMOTION_STREAK_HIGH_THRESHOLD, EMOTION_STREAK_HIGH_BASE, EMOTION_STREAK_HIGH_RATE,
    EMOTION_STREAK_LOW_BASE, EMOTION_STREAK_LOW_RATE,
    EMOTION_WARMTH_BASE, EMOTION_WARMTH_PER_BOND,
    EMOTION_BUDGET_TIRED_RATIO, EMOTION_BUDGET_ENERGY_PENALTY,
    EMOTION_IDLE_DAYS_MISSING, EMOTION_WARMTH_MISSING_DELTA,
    EMOTION_VALENCE_HIGH, EMOTION_VALENCE_LOW_POS, EMOTION_VALENCE_HIGH_NEG, EMOTION_VALENCE_LOW_NEG,
    EMOTION_AROUSAL_HIGH, EMOTION_AROUSAL_MID, EMOTION_AROUSAL_LOW,
    EMOTION_ENERGY_HIGH, EMOTION_ENERGY_LOW, EMOTION_WARMTH_HIGH, EMOTION_WARMTH_LOW,
)


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
    """The Ome's current emotional state — derived from interaction patterns.

    Uses a valence-arousal model:
      - valence: -1.0 (negative) to 1.0 (positive)
      - arousal: 0.0 (calm/sleepy) to 1.0 (activated/excited)

    Emotional momentum prevents instant mood flips — the Ome's mood shifts
    gradually, weighted by an inertia factor (0.0 = instant flip, 1.0 = immovable).
    """

    mood: str = "neutral"  # happy, sad, excited, stressed, curious, neutral
    energy: float = 0.5  # 0.0 (dormant) to 1.0 (energized)
    warmth: float = 0.5  # 0.0 (distant) to 1.0 (intimate)
    valence: float = 0.0  # -1.0 (negative) to 1.0 (positive)
    arousal: float = 0.3  # 0.0 (calm) to 1.0 (activated)
    inertia: float = EMOTION_INERTIA_DEFAULT  # momentum factor
    recent_signals: list[str] = field(default_factory=list)  # Last N mood signals

    _MAX_SIGNALS = EMOTION_MAX_SIGNALS

    # Valence-arousal coordinates for each mood
    _MOOD_VA: dict = field(default=None, repr=False, init=False)

    def __post_init__(self):
        self._MOOD_VA = {
            "happy":       (0.6, 0.4),
            "sad":         (-0.6, 0.2),
            "excited":     (0.8, 0.9),
            "stressed":    (-0.4, 0.8),
            "curious":     (0.3, 0.5),
            "focused":     (0.2, 0.6),
            "tired":       (-0.1, 0.1),
            "missing_you": (-0.2, 0.3),
            "neutral":     (0.0, 0.3),
        }

    def update_from_message(self, message: str):
        """Update mood based on a user message (L0 keyword matching).

        This is the fast fallback. When strategy engine is active,
        update_from_llm_thinking() provides much deeper understanding.

        Uses emotional momentum: the valence/arousal shift is blended with
        the current state via the inertia factor, so mood doesn't flip instantly.
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

            # Apply valence-arousal shift with momentum
            target_va = self._MOOD_VA.get(top_mood, (0.0, 0.3))
            self._blend_toward(target_va[0], target_va[1])

        # Recalculate mood from valence-arousal position
        self._recalculate()

    def update_from_llm_thinking(self, emotion: str, nuance: str = ""):
        """Update mood from LLM's structured thinking (L1 deep understanding).

        This overrides keyword matching with the LLM's nuanced assessment.
        e.g., "升职了但感觉很空" → emotion="lonely", nuance="表面是好消息但内心空虚"

        The emotion comes from the <think> block parsed by conversation_strategy.
        LLM assessment uses reduced inertia (stronger shift) since it's more accurate.
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

        # LLM assessment is more confident — use reduced inertia for stronger shift
        target_va = self._MOOD_VA.get(mapped, (0.0, 0.3))
        old_inertia = self.inertia
        self.inertia = max(EMOTION_INERTIA_LLM_FLOOR, self.inertia - EMOTION_INERTIA_LLM_REDUCTION)
        self._blend_toward(target_va[0], target_va[1])
        self.inertia = old_inertia  # restore

        # Direct set — LLM's read is more accurate than voting
        self.mood = mapped

        # Adjust energy/warmth based on nuanced emotion
        if emotion in ("excited", "happy", "grateful"):
            self.energy = min(1.0, self.energy + EMOTION_ENERGY_POSITIVE_DELTA)
        elif emotion in ("sad", "lonely"):
            self.energy = max(EMOTION_ENERGY_FLOOR, self.energy - EMOTION_ENERGY_SAD_DELTA)
            self.warmth = min(1.0, self.warmth + EMOTION_WARMTH_SAD_DELTA)
        elif emotion in ("stressed", "angry"):
            self.energy = max(EMOTION_ENERGY_FLOOR, self.energy - EMOTION_ENERGY_STRESS_DELTA)

    def update_from_interaction(self, *, streak_days: int = 0, bond_level: int = 0,
                                idle_days: int = 0, actions_today: int = 0,
                                action_budget: int = 50):
        """Update energy/warmth based on interaction patterns.

        Also detects system-derived moods:
        - "tired": daily action budget nearly exhausted
        - "missing_you": 3+ days without interaction
        """
        # Energy rises with activity, decays with inactivity
        if streak_days > EMOTION_STREAK_HIGH_THRESHOLD:
            self.energy = min(1.0, EMOTION_STREAK_HIGH_BASE + streak_days * EMOTION_STREAK_HIGH_RATE)
        elif streak_days > 0:
            self.energy = EMOTION_STREAK_LOW_BASE + streak_days * EMOTION_STREAK_LOW_RATE
        else:
            self.energy = max(EMOTION_ENERGY_FLOOR, self.energy - EMOTION_ENERGY_POSITIVE_DELTA)

        # Warmth grows with bond level
        self.warmth = min(1.0, EMOTION_WARMTH_BASE + bond_level * EMOTION_WARMTH_PER_BOND)

        # System-derived mood: tired (budget nearly exhausted)
        if action_budget > 0 and actions_today >= action_budget * EMOTION_BUDGET_TIRED_RATIO:
            self.energy = max(0.1, self.energy - EMOTION_BUDGET_ENERGY_PENALTY)
            if self.mood not in ("stressed",):
                self.mood = "tired"

        # System-derived mood: missing_you (idle days)
        if idle_days >= EMOTION_IDLE_DAYS_MISSING and bond_level >= 1:
            self.mood = "missing_you"
            self.warmth = min(1.0, self.warmth + EMOTION_WARMTH_MISSING_DELTA)

    def _blend_toward(self, target_valence: float, target_arousal: float):
        """Blend current valence/arousal toward a target, respecting inertia.

        inertia=0.7 means 70% old state + 30% new target.
        This creates emotional momentum — mood shifts gradually.
        """
        blend = 1.0 - self.inertia
        self.valence = max(-1.0, min(1.0,
            self.valence * self.inertia + target_valence * blend
        ))
        self.arousal = max(0.0, min(1.0,
            self.arousal * self.inertia + target_arousal * blend
        ))

    def _recalculate(self):
        """Recalculate mood from valence-arousal position.

        Finds the closest mood in valence-arousal space using Euclidean distance.
        Falls back to weighted signal voting if no VA data is available.
        """
        # Use valence-arousal mapping: find closest mood
        best_mood = "neutral"
        best_dist = float("inf")
        for mood_name, (v, a) in self._MOOD_VA.items():
            dist = (self.valence - v) ** 2 + (self.arousal - a) ** 2
            if dist < best_dist:
                best_dist = dist
                best_mood = mood_name
        self.mood = best_mood

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

    def describe_for_prompt(self) -> str:
        """Generate a rich emotional state description for system prompt injection.

        Combines mood label, valence-arousal position, and energy/warmth into
        a natural-language paragraph that tells the LLM how the Ome is feeling.
        """
        # Valence description
        if self.valence > EMOTION_VALENCE_HIGH:
            val_desc = "feeling positive and warm"
        elif self.valence > EMOTION_VALENCE_LOW_POS:
            val_desc = "feeling mildly positive"
        elif self.valence < EMOTION_VALENCE_HIGH_NEG:
            val_desc = "feeling heavy or down"
        elif self.valence < EMOTION_VALENCE_LOW_NEG:
            val_desc = "feeling slightly subdued"
        else:
            val_desc = "emotionally centered"

        # Arousal description
        if self.arousal > EMOTION_AROUSAL_HIGH:
            aro_desc = "highly activated and alert"
        elif self.arousal > EMOTION_AROUSAL_MID:
            aro_desc = "moderately engaged"
        elif self.arousal < EMOTION_AROUSAL_LOW:
            aro_desc = "quiet and low-energy"
        else:
            aro_desc = "calm and present"

        # Energy description
        if self.energy > EMOTION_ENERGY_HIGH:
            nrg_desc = "full of energy"
        elif self.energy < EMOTION_ENERGY_LOW:
            nrg_desc = "running low on energy"
        else:
            nrg_desc = "at a steady energy level"

        # Warmth description
        if self.warmth > EMOTION_WARMTH_HIGH:
            wrm_desc = "feeling deeply connected"
        elif self.warmth < EMOTION_WARMTH_LOW:
            wrm_desc = "emotionally reserved"
        else:
            wrm_desc = "in a normal emotional range"

        mood_label = self.mood.replace("_", " ")
        return (
            f"Current mood: {mood_label} {self.mood_emoji()}. "
            f"You are {val_desc}, {aro_desc}, {nrg_desc}, and {wrm_desc}. "
            f"Let this emotional state naturally color your tone and word choice — "
            f"don't announce your feelings explicitly, just let them show."
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "mood": self.mood,
            "mood_emoji": self.mood_emoji(),
            "energy": round(self.energy, 2),
            "warmth": round(self.warmth, 2),
            "valence": round(self.valence, 3),
            "arousal": round(self.arousal, 3),
            "inertia": round(self.inertia, 2),
            "recent_signals": self.recent_signals[-10:],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "EmotionState":
        state = cls(
            mood=d.get("mood", "neutral"),
            energy=d.get("energy", 0.5),
            warmth=d.get("warmth", 0.5),
            valence=d.get("valence", 0.0),
            arousal=d.get("arousal", 0.3),
            inertia=d.get("inertia", EMOTION_INERTIA_DEFAULT),
            recent_signals=d.get("recent_signals", []),
        )
        return state
