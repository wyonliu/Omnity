"""L4 Self (Default Mode Network) — Personality maintenance, reflection, value alignment.

The emergence layer: from 'brain' to 'soul'. Maintains a consistent sense of self
across all interactions, detects personality drift, and guards value alignment.
"""

from __future__ import annotations

import json
import time
from typing import Any, Optional

from mindos.config import ModelRouter
from mindos.store import MemoryStore


_REFLECTION_SYSTEM = """You are the self-awareness module of a personal AI identity called Mindos.
You periodically review recent experiences and assess whether the person's behavior
aligns with their stated personality and values.

Output JSON:
{
  "summary": "Brief summary of recent patterns",
  "drift_detected": true/false,
  "drift_details": "Description of any personality drift",
  "new_traits_observed": ["trait1", "trait2"],
  "value_alignment_score": 0.0-1.0,
  "suggestions": ["suggestion for personality model update"]
}"""


class Self:
    """L4: personality model, reflection loop, value alignment."""

    def __init__(self, store: MemoryStore, identity: dict[str, Any],
                 model_router: Optional[ModelRouter] = None) -> None:
        self.store = store
        self.identity = identity
        self.router = model_router
        self._commit_count_since_reflect = 0

    def on_commit(self) -> Optional[dict[str, Any]]:
        """Called after each commit. Triggers reflection when threshold reached."""
        self._commit_count_since_reflect += 1
        if self._commit_count_since_reflect >= 20:
            return self.reflect()
        return None

    def reflect(self) -> Optional[dict[str, Any]]:
        """Run a reflection cycle: review recent episodes, detect drift, propose updates."""
        self._commit_count_since_reflect = 0

        episodes = self.store.list_recent(limit=30, mem_type="episode")
        if not episodes:
            return None

        episode_text = "\n".join(f"- {e.content}" for e in episodes)

        if self.router is None:
            return self._reflect_heuristic(episodes)

        traits = self.identity.get("traits", [])
        style = self.identity.get("style", "")
        user_msg = f"""Current personality: {', '.join(traits)}
Communication style: {style}

Recent episodes ({len(episodes)} most recent):
{episode_text}

Analyze for personality consistency and drift."""

        raw = self.router.call_llm(
            system=_REFLECTION_SYSTEM, user=user_msg,
            task="reflection", max_tokens=1024, json_mode=True,
        )
        if raw is None:
            return self._reflect_heuristic(episodes)

        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            return self._reflect_heuristic(episodes)

        self.store.record_personality(
            snapshot={"traits": traits, "style": style},
            trigger="reflection_cycle",
            diff=json.dumps(result, ensure_ascii=False),
        )
        return result

    def _reflect_heuristic(self, episodes: list[Any]) -> dict[str, Any]:
        """Heuristic reflection when no LLM is available."""
        from collections import Counter
        word_counts: Counter[str] = Counter()
        for ep in episodes:
            for word in ep.content.split():
                word_counts[word.lower()] += 1

        return {
            "summary": f"Reviewed {len(episodes)} recent episodes",
            "drift_detected": False,
            "drift_details": "",
            "new_traits_observed": [],
            "value_alignment_score": 0.8,
            "suggestions": [],
            "method": "heuristic",
            "top_themes": [w for w, _ in word_counts.most_common(10)],
        }

    def personality_snapshot(self) -> dict[str, Any]:
        """Current personality state."""
        return {
            "name": self.identity.get("name", ""),
            "traits": self.identity.get("traits", []),
            "style": self.identity.get("style", ""),
            "capabilities": self.identity.get("capabilities", []),
            "history_count": len(self.store.personality_timeline()),
        }

    def cross_platform_anchor(self) -> str:
        """Generate a platform-agnostic identity anchor for Ome spawning."""
        name = self.identity.get("name", "Mindos")
        traits = ", ".join(self.identity.get("traits", []))
        style = self.identity.get("style", "")
        return (
            f"I am {name}. "
            f"My core traits are: {traits}. "
            f"My communication style: {style}. "
            f"This identity persists across platforms and sessions."
        )
