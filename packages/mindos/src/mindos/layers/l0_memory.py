"""L0 Hippocampus — Memory storage, retrieval, and relevance scoring.

This is the soul's foundation: every other layer reads from or writes to L0.

Relevance 2.0:
  - Semantic similarity from vector search (40% weight)
  - Adaptive half-life by memory type (not fixed 30 days)
  - Importance = confidence × (1 + |valence| × arousal)
  - Frequency dampened by log scale
"""

from __future__ import annotations

import math
import time
from typing import Any, Optional

from mindos.store import Memory, MemoryStore

# Adaptive half-life by memory type (days)
_HALF_LIFE: dict[str, float] = {
    "episode": 14.0,
    "fact": 90.0,
    "preference": 60.0,
    "skill": 180.0,
    "relation": 120.0,
}
_DEFAULT_HALF_LIFE = 30.0

# Scoring weights — sum to 1.0
W_SEMANTIC = 0.40
W_RECENCY = 0.25
W_IMPORTANCE = 0.20
W_FREQUENCY = 0.15


def relevance_score(mem: Memory, now: Optional[float] = None,
                    vector_score: float = 0.0) -> float:
    """Composite relevance with semantic similarity.

    Args:
        mem: The memory to score.
        now: Current timestamp (defaults to time.time()).
        vector_score: Cosine similarity from vector search [0, 1].
                      If 0.0, the semantic weight redistributes to other factors.
    """
    now = now or time.time()
    age_days = max((now - mem.created_at) / 86400, 0.01)
    half_life = _HALF_LIFE.get(mem.type, _DEFAULT_HALF_LIFE)
    recency = math.exp(-0.693 * age_days / half_life)

    importance = mem.confidence
    frequency = math.log(mem.access_count + 2)  # +2 so brand new memories get > 0
    # Normalize frequency to ~[0, 1] range (log(2)=0.69 to log(102)=4.62)
    frequency = min(frequency / 4.62, 1.0)
    decay = mem.decay_weight

    if vector_score > 0:
        score = (
            W_SEMANTIC * vector_score +
            W_RECENCY * recency +
            W_IMPORTANCE * importance +
            W_FREQUENCY * frequency
        )
    else:
        # No vector score available — redistribute weight
        score = (
            (W_RECENCY + W_SEMANTIC * 0.5) * recency +
            (W_IMPORTANCE + W_SEMANTIC * 0.3) * importance +
            (W_FREQUENCY + W_SEMANTIC * 0.2) * frequency
        )

    return score * decay


class Hippocampus:
    """L0: memory retrieval with relevance ranking."""

    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def recall(self, query: str, top_k: int = 15,
               query_vec: Any = None, mem_type: Optional[str] = None) -> list[Memory]:
        """Retrieve memories ranked by relevance.

        1. Vector search (if embedding available) — gets cosine similarity scores
        2. Keyword fallback (phrase, then first token, then recent)
        3. Re-rank by composite relevance_score (semantic + recency + importance + frequency)
        """
        scored: dict[str, float] = {}  # memory_id -> vector cosine score
        results: list[Memory] = []

        if query_vec is not None:
            pairs = self.store.search_vector(query_vec, top_k=top_k * 2, return_scores=True)
            if pairs:
                results = [mem for mem, _ in pairs]
                scored = {mem.id: score for mem, score in pairs}

        if not results and query.strip():
            q = query.strip()
            results = self.store.search_text(q[:64], limit=top_k * 2)
            if not results and " " in q:
                for token in q.split()[:3]:
                    results = self.store.search_text(token, limit=top_k)
                    if results:
                        break

        if not results and self.store.count() > 0:
            results = self.store.list_recent(limit=top_k, mem_type=mem_type)

        # Re-rank with composite scoring
        now = time.time()
        results.sort(
            key=lambda m: relevance_score(m, now, vector_score=scored.get(m.id, 0.0)),
            reverse=True,
        )
        return results[:top_k]

    def recent(self, limit: int = 20, mem_type: Optional[str] = None) -> list[Memory]:
        return self.store.list_recent(limit=limit, mem_type=mem_type)

    def stats(self) -> dict[str, Any]:
        return self.store.stats()
