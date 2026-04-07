"""Mindos tunable constants — central registry for all magic numbers.

Import from here instead of hardcoding values in logic.
Users can override via environment variables prefixed with MINDOS_.
"""

from __future__ import annotations

import os

def _env_float(key: str, default: float) -> float:
    return float(os.environ.get(key, default))

def _env_int(key: str, default: int) -> int:
    return int(os.environ.get(key, default))


# ── L0 Relevance Scoring ──────────────────────────────────────────────

# Weights for composite relevance score (must sum to 1.0)
RELEVANCE_W_SEMANTIC: float   = _env_float("MINDOS_W_SEMANTIC", 0.40)
RELEVANCE_W_RECENCY: float    = _env_float("MINDOS_W_RECENCY", 0.25)
RELEVANCE_W_IMPORTANCE: float = _env_float("MINDOS_W_IMPORTANCE", 0.20)
RELEVANCE_W_FREQUENCY: float  = _env_float("MINDOS_W_FREQUENCY", 0.15)

# When vector_score=0, semantic weight redistributes to other factors:
RELEVANCE_REDIST_RECENCY: float    = 0.5  # 50% of semantic → recency
RELEVANCE_REDIST_IMPORTANCE: float = 0.3  # 30% of semantic → importance
RELEVANCE_REDIST_FREQUENCY: float  = 0.2  # 20% of semantic → frequency

# Memory type half-lives (days) — how fast each type decays
HALF_LIFE: dict[str, float] = {
    "episode": 14.0,
    "fact": 90.0,
    "preference": 60.0,
    "skill": 180.0,
    "relation": 120.0,
}
HALF_LIFE_DEFAULT: float = 30.0

# Frequency normalization ceiling: log(100 + 2) ≈ 4.62
FREQUENCY_NORM_CEILING: float = 4.62
# Frequency base offset: +2 so brand-new memories (count=0) get log(2)=0.69
FREQUENCY_BASE_OFFSET: int = 2


# ── L1 Hydration & Routing ───────────────────────────────────────────

HYDRATE_MAX_TOKENS: int       = _env_int("MINDOS_HYDRATE_MAX_TOKENS", 2000)
HYDRATE_RECALL_TOP_K: int     = 15
HYDRATE_KG_LIMIT: int         = 30   # Max knowledge graph triples in prompt
TOKEN_EST_CJK: float          = 1.5  # Tokens per CJK character
TOKEN_EST_ASCII: float        = 0.25 # Tokens per ASCII character

# Circadian energy decay rate (per hour)
ENERGY_DECAY_PER_HOUR: float  = 0.02


# ── L2 Commit ────────────────────────────────────────────────────────

COMMIT_MAX_TOKENS: int        = 2048  # LLM budget for fact extraction
COMMIT_EXISTING_FACTS_LIMIT: int = 20 # How many existing facts to provide for dedup


# ── L4 Reflection ────────────────────────────────────────────────────

# Adaptive reflection threshold:
#   threshold = clamp(total_memories / REFLECTION_ADAPTIVE_DIVISOR,
#                     REFLECTION_MIN_COMMITS, REFLECTION_MAX_COMMITS)
# Early soul (few memories): reflects more often to build personality faster.
# Mature soul (many memories): reflects less often (personality is stable).
REFLECTION_MIN_COMMITS: int   = _env_int("MINDOS_REFLECT_MIN", 10)
REFLECTION_MAX_COMMITS: int   = _env_int("MINDOS_REFLECT_MAX", 50)
REFLECTION_ADAPTIVE_DIVISOR: int = 5  # total_memories / 5 = base threshold

REFLECTION_EPISODES_LIMIT: int = 30   # Recent episodes to include in reflection
REFLECTION_MAX_TRAITS: int    = 15    # Cap on total traits
REFLECTION_MAX_TOKENS: int    = 1024  # LLM budget for reflection


# ── Store ─────────────────────────────────────────────────────────────

SQLITE_BUSY_TIMEOUT_MS: int   = _env_int("MINDOS_SQLITE_TIMEOUT", 5000)
SQLITE_CACHE_SIZE: int        = _env_int("MINDOS_SQLITE_CACHE", 2000)  # pages (~2MB)

# Embedding cache: LRU cap to prevent unbounded memory growth
EMBEDDING_CACHE_MAX: int      = _env_int("MINDOS_EMBEDDING_CACHE_MAX", 5000)

# Compression/archival thresholds
COMPRESS_OLDER_THAN_DAYS: int = 90
COMPRESS_MIN_LENGTH: int      = 120   # Only compress content > this length
ARCHIVE_INACTIVE_DAYS: int    = 180
ARCHIVE_MIN_ACCESS: int       = 2
CONSOLIDATE_THRESHOLD: float  = 0.75  # Jaccard similarity for merge
FACT_MERGE_THRESHOLD: float   = 0.80


# ── LLM Cache ────────────────────────────────────────────────────────

LLM_CACHE_TTL: int            = 300   # seconds (5 minutes)
LLM_CACHE_MAX_ENTRIES: int    = 100
LLM_DEFAULT_TIMEOUT: int      = 30    # seconds


# ── Scheduler ────────────────────────────────────────────────────────

SCHEDULER_REFLECT_HOURS: int   = 24
SCHEDULER_COMPRESS_HOURS: int  = 72
SCHEDULER_DIGEST_HOURS: int    = 24
SCHEDULER_INSIGHT_HOURS: int   = 168  # weekly
SCHEDULER_CLEANUP_HOURS: int   = 168
SCHEDULER_MERGE_HOURS: int     = 72


# ── Locale ──────────────────────────────────────────────────────────────

# Default language for LLM output (fact extraction, reflection, prompts).
# Supported: "zh" (中文), "en" (English), "ja", "ko", etc.
# Override via MINDOS_LOCALE env var or set_locale().
LOCALE: str = os.environ.get("MINDOS_LOCALE", "zh")


def set_locale(locale: str) -> None:
    """Set the output language at runtime. e.g. set_locale("en")"""
    import mindos.constants as _c
    _c.LOCALE = locale
