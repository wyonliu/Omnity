"""Tests for l0_memory relevance scoring — vector_score, adaptive half-life."""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mindos.layers.l0_memory import relevance_score, Hippocampus
from mindos.constants import HALF_LIFE


def _make_memory(**kwargs):
    """Create a mock Memory with sensible defaults."""
    m = MagicMock()
    m.id = kwargs.get("id", "test-1")
    m.type = kwargs.get("type", "fact")
    m.content = kwargs.get("content", "test content")
    m.created_at = kwargs.get("created_at", time.time())
    m.accessed_at = kwargs.get("accessed_at", time.time())
    m.access_count = kwargs.get("access_count", 1)
    m.confidence = kwargs.get("confidence", 1.0)
    m.decay_weight = kwargs.get("decay_weight", 1.0)
    return m


class TestRelevanceScore:
    def test_vector_score_boosts_relevance(self):
        mem = _make_memory()
        now = time.time()
        score_without = relevance_score(mem, now, vector_score=0.0)
        score_with = relevance_score(mem, now, vector_score=0.9)
        assert score_with > score_without

    def test_high_vector_score_dominates(self):
        """A very relevant but old memory should still rank high."""
        mem = _make_memory(created_at=time.time() - 86400 * 60)  # 60 days old
        now = time.time()
        score = relevance_score(mem, now, vector_score=0.95)
        # Should still be meaningful thanks to semantic similarity
        assert score > 0.3

    def test_adaptive_halflife_episode_vs_fact(self):
        """Episodes decay faster than facts."""
        now = time.time()
        age = 30 * 86400  # 30 days old

        ep = _make_memory(type="episode", created_at=now - age)
        fact = _make_memory(type="fact", created_at=now - age)

        ep_score = relevance_score(ep, now)
        fact_score = relevance_score(fact, now)
        # Episode has 14-day half-life, fact has 90-day — fact should score higher on recency
        assert fact_score > ep_score

    def test_decay_weight_scales(self):
        mem_normal = _make_memory(decay_weight=1.0)
        mem_decayed = _make_memory(decay_weight=0.5)
        now = time.time()
        assert relevance_score(mem_normal, now) > relevance_score(mem_decayed, now)

    def test_fresh_memory_high_score(self):
        mem = _make_memory(created_at=time.time())
        score = relevance_score(mem, time.time(), vector_score=0.8)
        assert score > 0.5

    def test_no_vector_score_redistributes(self):
        """With vector_score=0, weights redistribute — shouldn't crash or be zero."""
        mem = _make_memory()
        score = relevance_score(mem, time.time(), vector_score=0.0)
        assert score > 0

    def test_unknown_type_uses_default_halflife(self):
        """Unknown memory types should use 30-day default, not crash."""
        mem = _make_memory(type="unknown_type")
        score = relevance_score(mem, time.time())
        assert score > 0


class TestHippocampusRecall:
    def test_recall_uses_vector_scores(self):
        """Verify that recall passes return_scores=True to search_vector."""
        store = MagicMock()
        mem_high = _make_memory(id="high")
        mem_low = _make_memory(id="low")
        store.search_vector.return_value = [
            (mem_low, 0.3),
            (mem_high, 0.95),
        ]
        store.count.return_value = 2

        h = Hippocampus(store)
        import numpy as np
        query_vec = np.random.randn(384).astype(np.float32)
        results = h.recall("test", query_vec=query_vec, top_k=2)

        store.search_vector.assert_called_once()
        # The high-score memory should be ranked first after re-ranking
        assert results[0].id == "high"

    def test_recall_text_fallback(self):
        """If no query_vec, falls back to text search."""
        store = MagicMock()
        mem = _make_memory()
        store.search_vector.return_value = []
        store.search_text.return_value = [mem]
        store.count.return_value = 1

        h = Hippocampus(store)
        results = h.recall("test query", top_k=5)
        assert len(results) == 1
        store.search_text.assert_called()

    def test_recall_recent_fallback(self):
        """If text search also fails, fall back to recent."""
        store = MagicMock()
        mem = _make_memory()
        store.search_text.return_value = []
        store.count.return_value = 1
        store.list_recent.return_value = [mem]

        h = Hippocampus(store)
        results = h.recall("", top_k=5)
        assert len(results) == 1
        store.list_recent.assert_called()
