"""Importance-Triggered Reflection — Stanford Generative Agents pattern.

Instead of reflecting every N commits, reflect when cumulative importance
of new memories crosses a threshold. This ensures reflection fires after
meaningful events, not mundane ones.

The commit-count trigger is kept as a fallback: if no LLM is available to
score importance, we fall back to the v0.6 adaptive commit-count method.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

log = logging.getLogger("mindos.importance")


class ImportanceTrigger:
    """Persistent accumulator for importance-triggered reflection.

    Usage:
        trigger = ImportanceTrigger(threshold=100.0, store=store)
        if trigger.accumulate(8.5):  # returns True when threshold crossed
            soul.reflect()
    """

    STATE_KEY = "importance_accumulator"

    def __init__(
        self,
        threshold: float = 100.0,
        store: Any = None,  # MemoryStore — optional for persistence
    ) -> None:
        self.threshold = threshold
        self._store = store
        self._current: float = 0.0
        self._load()

    def accumulate(self, importance: float) -> bool:
        """Add an importance score. Returns True if threshold crossed."""
        self._current += importance
        self._save()
        if self._current >= self.threshold:
            return True
        return False

    def reset(self) -> None:
        """Reset accumulator (call after reflection completes)."""
        self._current = 0.0
        self._save()

    @property
    def current(self) -> float:
        return self._current

    @property
    def progress(self) -> float:
        """Progress toward threshold as 0.0-1.0."""
        return min(self._current / self.threshold, 1.0) if self.threshold > 0 else 0.0

    def _load(self) -> None:
        if self._store:
            raw = self._store.get_state(self.STATE_KEY)
            if raw:
                try:
                    self._current = float(json.loads(raw).get("current", 0.0))
                except (json.JSONDecodeError, TypeError, ValueError):
                    pass

    def _save(self) -> None:
        if self._store:
            self._store.set_state(
                self.STATE_KEY,
                json.dumps({"current": round(self._current, 2), "threshold": self.threshold}),
            )


def estimate_importance(facts: list[dict[str, Any]], episode: str = "") -> float:
    """Estimate importance score for a commit result (no LLM needed).

    Heuristic scoring:
      - Each fact: confidence * type_weight
      - Episode summary: flat 2.0
      - Contradiction: 5.0 (high importance — something changed)

    Type weights: relation=3.0, preference=2.0, fact=1.5, skill=2.5, episode=1.0
    """
    TYPE_WEIGHTS = {
        "relation": 3.0,
        "preference": 2.0,
        "fact": 1.5,
        "skill": 2.5,
        "episode": 1.0,
    }

    score = 0.0
    for f in facts:
        confidence = f.get("confidence", 0.7)
        ftype = f.get("type", "fact")
        score += confidence * TYPE_WEIGHTS.get(ftype, 1.0)

    if episode:
        score += 2.0

    return round(score, 2)
