"""L0 Hippocampus — Memory storage, retrieval, and relevance scoring.

This is the soul's foundation: every other layer reads from or writes to L0.
"""

from __future__ import annotations

import math
import time
from typing import Any, Optional

from mindos.store import Memory, MemoryStore


def relevance_score(mem: Memory, now: Optional[float] = None) -> float:
    """Composite relevance = recency × importance × access_frequency × decay.

    - recency: exponential decay with half-life of 30 days
    - importance: confidence as proxy
    - frequency: log(access_count + 1)
    - decay_weight: user/system adjustable weight
    """
    now = now or time.time()
    age_days = max((now - mem.created_at) / 86400, 0.01)
    half_life = 30.0
    recency = math.exp(-0.693 * age_days / half_life)

    importance = mem.confidence
    frequency = math.log(mem.access_count + 2)  # +2 so brand new memories get > 0
    decay = mem.decay_weight

    return recency * importance * frequency * decay


class Hippocampus:
    """L0: memory retrieval with relevance ranking."""

    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def recall(self, query: str, top_k: int = 15,
               query_vec: Any = None, mem_type: Optional[str] = None) -> list[Memory]:
        """Retrieve memories ranked by relevance.

        1. Vector search (if embedding available)
        2. Keyword fallback (phrase, then first token, then recent)
        3. Re-rank by relevance_score
        """
        results: list[Memory] = []

        if query_vec is not None:
            results = self.store.search_vector(query_vec, top_k=top_k * 2)

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

        # Re-rank
        now = time.time()
        results.sort(key=lambda m: relevance_score(m, now), reverse=True)
        return results[:top_k]

    def recent(self, limit: int = 20, mem_type: Optional[str] = None) -> list[Memory]:
        return self.store.list_recent(limit=limit, mem_type=mem_type)

    def stats(self) -> dict[str, Any]:
        return self.store.stats()
