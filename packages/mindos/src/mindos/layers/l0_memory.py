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

from mindos.constants import (
    HALF_LIFE, HALF_LIFE_DEFAULT,
    RELEVANCE_W_SEMANTIC, RELEVANCE_W_RECENCY, RELEVANCE_W_IMPORTANCE, RELEVANCE_W_FREQUENCY,
    RELEVANCE_REDIST_RECENCY, RELEVANCE_REDIST_IMPORTANCE, RELEVANCE_REDIST_FREQUENCY,
    FREQUENCY_NORM_CEILING, FREQUENCY_BASE_OFFSET,
    HYDRATE_RECALL_TOP_K,
)
from mindos.store import Memory, MemoryStore


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
    half_life = HALF_LIFE.get(mem.type, HALF_LIFE_DEFAULT)
    recency = math.exp(-0.693 * age_days / half_life)

    importance = mem.confidence
    frequency = math.log(mem.access_count + FREQUENCY_BASE_OFFSET)
    frequency = min(frequency / FREQUENCY_NORM_CEILING, 1.0)
    decay = mem.decay_weight

    if vector_score > 0:
        score = (
            RELEVANCE_W_SEMANTIC * vector_score +
            RELEVANCE_W_RECENCY * recency +
            RELEVANCE_W_IMPORTANCE * importance +
            RELEVANCE_W_FREQUENCY * frequency
        )
    else:
        # No vector score available — redistribute weight
        score = (
            (RELEVANCE_W_RECENCY + RELEVANCE_W_SEMANTIC * RELEVANCE_REDIST_RECENCY) * recency +
            (RELEVANCE_W_IMPORTANCE + RELEVANCE_W_SEMANTIC * RELEVANCE_REDIST_IMPORTANCE) * importance +
            (RELEVANCE_W_FREQUENCY + RELEVANCE_W_SEMANTIC * RELEVANCE_REDIST_FREQUENCY) * frequency
        )

    return score * decay


class Hippocampus:
    """L0: memory retrieval with relevance ranking."""

    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def recall(self, query: str, top_k: int = HYDRATE_RECALL_TOP_K,
               query_vec: Any = None, mem_type: Optional[str] = None) -> list[Memory]:
        """Retrieve memories ranked by relevance.

        Hybrid retrieval:
        1. Vector search (if embedding available) — cosine similarity scores
        2. Text search (FTS5 OR-over-tokens) — keyword hits merged in
        3. For keyword-only hits, synthesize a semantic_score from token-overlap
           so they compete fairly with vector hits
        4. Re-rank by composite relevance_score (semantic + recency + importance + frequency)
        """
        import re as _re
        scored: dict[str, float] = {}  # memory_id -> semantic score proxy [0, 1]
        candidates: dict[str, Memory] = {}
        q_raw = (query or "").strip()

        # 1. Vector search
        if query_vec is not None:
            pairs = self.store.search_vector(query_vec, top_k=top_k * 3, return_scores=True)
            for mem, score in pairs:
                candidates[mem.id] = mem
                scored[mem.id] = max(scored.get(mem.id, 0.0), float(score))

        # 2. Text search (always run, not just as fallback)
        if q_raw:
            tokens = [t for t in _re.split(r'\s+', q_raw) if len(t) >= 2]
            text_hits = self.store.search_text(q_raw[:128], limit=top_k * 3)
            # If the multi-token OR query returned nothing, try single tokens
            if not text_hits and len(tokens) > 1:
                for tok in tokens[:3]:
                    text_hits = self.store.search_text(tok, limit=top_k * 2)
                    if text_hits:
                        break
            for mem in text_hits:
                if mem.id not in candidates:
                    candidates[mem.id] = mem
                # Synthesize a semantic-proxy score from token-overlap so
                # keyword-only hits can compete with vector hits
                content = mem.content or ""
                if tokens:
                    hit_count = sum(1 for t in tokens if t in content)
                    overlap = hit_count / len(tokens)
                else:
                    overlap = 1.0 if q_raw and q_raw in content else 0.3
                # Base 0.3 for a text hit, +0.5 scaled by overlap; cap at 0.9
                text_proxy = min(0.3 + 0.5 * overlap, 0.9)
                scored[mem.id] = max(scored.get(mem.id, 0.0), text_proxy)

        results = list(candidates.values())

        # 3. Recent fallback if nothing matched
        if not results and self.store.count() > 0:
            results = self.store.list_recent(limit=top_k, mem_type=mem_type)

        # 4. Re-rank with composite scoring
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
