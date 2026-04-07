"""Ome tunable constants — central registry for all magic numbers.

Import from here instead of hardcoding values in logic.
Users can override via environment variables prefixed with OME_.
"""

from __future__ import annotations

import os


def _env_float(key: str, default: float) -> float:
    return float(os.environ.get(key, default))


def _env_int(key: str, default: int) -> int:
    return int(os.environ.get(key, default))


# ── Emotion ────────────────────────────────────────────────────────────

EMOTION_INERTIA_DEFAULT: float        = 0.7   # Momentum: 70% old + 30% new
EMOTION_INERTIA_LLM_FLOOR: float     = 0.3   # Min inertia during LLM override
EMOTION_INERTIA_LLM_REDUCTION: float = 0.2   # How much to reduce inertia for LLM

EMOTION_MAX_SIGNALS: int              = 20    # Rolling mood signal history cap
EMOTION_ENERGY_POSITIVE_DELTA: float  = 0.1   # Energy bump for happy/excited
EMOTION_ENERGY_SAD_DELTA: float       = 0.05  # Energy drain for sad/lonely
EMOTION_WARMTH_SAD_DELTA: float       = 0.05  # Warmth increase for sadness
EMOTION_ENERGY_STRESS_DELTA: float    = 0.1   # Energy drain for stressed/angry
EMOTION_ENERGY_FLOOR: float           = 0.2   # Absolute minimum energy

# Interaction-based emotion adjustments
EMOTION_STREAK_HIGH_THRESHOLD: int    = 7     # Days above which = high streak
EMOTION_STREAK_HIGH_BASE: float       = 0.6   # Base energy for high streak
EMOTION_STREAK_HIGH_RATE: float       = 0.02  # Energy per additional streak day
EMOTION_STREAK_LOW_BASE: float        = 0.4   # Base energy for low streak
EMOTION_STREAK_LOW_RATE: float        = 0.05  # Energy per streak day (low range)

EMOTION_WARMTH_BASE: float            = 0.3   # Warmth starting point
EMOTION_WARMTH_PER_BOND: float        = 0.12  # Warmth increase per bond level

EMOTION_BUDGET_TIRED_RATIO: float     = 0.8   # Action usage ratio triggering tired
EMOTION_BUDGET_ENERGY_PENALTY: float  = 0.3   # Energy penalty when budget exhausted

EMOTION_IDLE_DAYS_MISSING: int        = 3     # Days idle to trigger "missing_you"
EMOTION_WARMTH_MISSING_DELTA: float   = 0.2   # Warmth boost when missing user

# Valence-arousal thresholds for describe_for_prompt
EMOTION_VALENCE_HIGH: float           = 0.4
EMOTION_VALENCE_LOW_POS: float        = 0.1
EMOTION_VALENCE_HIGH_NEG: float       = -0.4
EMOTION_VALENCE_LOW_NEG: float        = -0.1
EMOTION_AROUSAL_HIGH: float           = 0.7
EMOTION_AROUSAL_MID: float            = 0.4
EMOTION_AROUSAL_LOW: float            = 0.2
EMOTION_ENERGY_HIGH: float            = 0.7
EMOTION_ENERGY_LOW: float             = 0.3
EMOTION_WARMTH_HIGH: float            = 0.7
EMOTION_WARMTH_LOW: float             = 0.3


# ── Bond ───────────────────────────────────────────────────────────────

# Bond level thresholds: (interactions, days) — index = level
BOND_INTERACTIONS = [0, 10, 50, 200, 500, 1000, 2000]
BOND_DAYS         = [0, 0, 3, 7, 30, 90, 180]

# Trust escalation thresholds
BOND_TRUST_ASSISTANT_LEVEL: int = 3   # Bond level >= 3 → ASSISTANT trust
BOND_TRUST_DEPUTY_LEVEL: int    = 5   # Bond level >= 5 → DEPUTY trust


# ── Chat ───────────────────────────────────────────────────────────────

CHAT_HISTORY_MAX: int             = _env_int("OME_CHAT_HISTORY_MAX", 500)
CHAT_RECALL_TOP_K: int            = 15    # Memories recalled per chat
CHAT_LOW_ENGAGEMENT_CHARS: int    = 4     # Messages <= this = low engagement
CHAT_DEFAULT_QUALITY: float       = 0.5   # Default action quality for chat
CHAT_REMEMBER_QUALITY: float      = 0.6   # Action quality for manual remember

# Follow-up suggestions
FOLLOW_UP_COUNT: int              = 3
FOLLOW_UP_RECALL_K: int           = 5     # Memories for personalization
FOLLOW_UP_MAX_CHARS: int          = 8     # Max chars per suggestion (Chinese)
FOLLOW_UP_MAX_LINE: int           = 15    # Max line length after cleanup

# Prompt generation
PROMPT_COUNT: int                 = 3
PROMPT_RECALL_K: int              = 5
PROMPT_MAX_CHARS: int             = 20
PROMPT_MAX_LINE: int              = 40

# Greeting
GREETING_RECALL_K: int            = 3
GREETING_MAX_CHARS: int           = 40
GREETING_MORNING_HOUR: int        = 12
GREETING_AFTERNOON_HOUR: int      = 18


# ── Recall ─────────────────────────────────────────────────────────────

RECALL_DEFAULT_TOP_K: int         = 10
RECALL_TYPE_FILTER_MULT: int      = 3     # Fetch top_k * N when filtering by type


# ── Memory Stats ───────────────────────────────────────────────────────

MEMORY_HEALTH_ACTIVE_WEIGHT: float   = 0.6
MEMORY_HEALTH_RECALL_WEIGHT: float   = 0.4
MEMORY_HEALTH_RECALL_NORM: float     = 5.0   # Normalization factor for recall frequency


# ── Emotion History ────────────────────────────────────────────────────

EMOTION_HISTORY_DEFAULT_DAYS: int = 30
EMOTION_HISTORY_MAX_DAYS: int     = 365


# ── Growth Timeline ────────────────────────────────────────────────────

GROWTH_TIMELINE_DEFAULT_LIMIT: int = 20
GROWTH_TIMELINE_MAX_EVENTS: int    = 200


# ── Achievements ───────────────────────────────────────────────────────

ACHIEVEMENT_NOTES_THRESHOLD: int      = 10
ACHIEVEMENT_TASKS_THRESHOLD: int      = 50
ACHIEVEMENT_CONTACTS_THRESHOLD: int   = 5
ACHIEVEMENT_FIRST_MEMORY_COUNT: int   = 1
ACHIEVEMENT_TEN_FACTS_COUNT: int      = 10
ACHIEVEMENT_FIFTY_CHATS: int          = 50
ACHIEVEMENT_STREAK_7: int             = 7
ACHIEVEMENT_STREAK_30: int            = 30
ACHIEVEMENT_WEEKLY_4_DAYS: int        = 28
ACHIEVEMENT_WEEKLY_4_INTERACTIONS: int = 100
ACHIEVEMENT_SOULMATE_LEVEL: int       = 5
ACHIEVEMENT_DEEP_TALK_CHARS: int      = 500
ACHIEVEMENT_NIGHT_OWL_EARLY: int      = 5    # hour < 5
ACHIEVEMENT_NIGHT_OWL_LATE: int       = 23   # hour >= 23


# ── Streak ─────────────────────────────────────────────────────────────

STREAK_MILESTONES: list[int]      = [3, 7, 14, 30, 90, 365]
STREAK_REWARD_THRESHOLDS: list[int] = [3, 7, 14, 30, 90, 365]
STREAK_HIGHLIGHT_MIN: int         = 3


# ── Daily Challenge ────────────────────────────────────────────────────

# (id_suffix, text, target) tuples — rotated daily
DAILY_CHALLENGES: list[tuple[str, str, int]] = [
    ("chat_3", "今天和 Ome 聊 3 次", 3),
    ("remember_1", "让 Ome 记住一件事", 1),
    ("recall_5", "回忆 5 条记忆", 5),
    ("long_msg_1", "写一条超过 100 字的消息", 1),
    ("task_1", "完成一个任务", 1),
    ("explore_1", "问一个你从没问过的问题", 1),
]


# ── Soul Card ──────────────────────────────────────────────────────────

SOUL_CARD_MIN_INTERACTIONS: int   = 10


# ── Evolution ──────────────────────────────────────────────────────────

EVOLUTION_COMMITS_THRESHOLD: int  = 20    # Commits since last reflect


# ── LLM Budgets ────────────────────────────────────────────────────────

LLM_EXTRACT_MAX_TOKENS: int       = 512
LLM_GENERATION_MAX_TOKENS: int    = 1024


# ── Content Detection ──────────────────────────────────────────────────

LONG_MESSAGE_CHARS: int           = 100
EVENING_HOUR: int                 = 20
TASK_CONTEXT_WINDOW: int          = 30    # Chars around time keywords for task extraction


# ── Locale ─────────────────────────────────────────────────────────────

# Default language for Ome chat, follow-ups, prompts, greeting.
# Override via OME_LOCALE env var or set_locale().
LOCALE: str = os.environ.get("OME_LOCALE", "zh")


def set_locale(locale: str) -> None:
    """Set the output language at runtime. e.g. set_locale("en")"""
    import ome.constants as _c
    _c.LOCALE = locale
    # Also propagate to mindos
    try:
        from mindos.constants import set_locale as _mindos_set_locale
        _mindos_set_locale(locale)
    except ImportError:
        pass
