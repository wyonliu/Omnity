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
  "trait_updates": ["new_trait_to_add"],
  "style_updates": "updated style description or empty string",
  "value_alignment_score": 0.0-1.0,
  "suggestions": ["suggestion for personality model update"]
}"""


class Self:
    """L4: personality model, reflection loop, value alignment.

    Supports personality anchors — immutable principles set by the user
    that L4 reflection will never overwrite.
    """

    def __init__(self, store: MemoryStore, identity: dict[str, Any],
                 model_router: Optional[ModelRouter] = None) -> None:
        self.store = store
        self.identity = identity
        self.router = model_router
        self._commit_count_since_reflect = 0
        # Callback for identity writeback (set by Mindos core)
        self._on_identity_changed: Optional[Any] = None

    def on_commit(self) -> Optional[dict[str, Any]]:
        """Called after each commit. Triggers reflection when threshold reached."""
        self._commit_count_since_reflect += 1
        if self._commit_count_since_reflect >= 20:
            return self.reflect()
        return None

    def reflect(self) -> Optional[dict[str, Any]]:
        """Run a reflection cycle: review recent episodes, detect drift, propose updates.

        NEW in v0.4: writes back trait/style changes to identity (respecting anchors).
        """
        self._commit_count_since_reflect = 0

        episodes = self.store.list_recent(limit=30, mem_type="episode")
        if not episodes:
            return None

        episode_text = "\n".join(f"- {e.content}" for e in episodes)

        if self.router is None:
            result = self._reflect_heuristic(episodes)
        else:
            traits = self.identity.get("traits", [])
            style = self.identity.get("style", "")
            anchors = self.identity.get("anchors", [])
            user_msg = f"""Current personality: {', '.join(traits)}
Communication style: {style}
Anchors (immutable): {', '.join(anchors) if anchors else 'none'}

Recent episodes ({len(episodes)} most recent):
{episode_text}

Analyze for personality consistency and drift. Suggest trait_updates and style_updates if needed."""

            raw = self.router.call_llm(
                system=_REFLECTION_SYSTEM, user=user_msg,
                task="reflection", max_tokens=1024, json_mode=True,
            )
            if raw is None:
                result = self._reflect_heuristic(episodes)
            else:
                try:
                    result = json.loads(raw)
                except json.JSONDecodeError:
                    result = self._reflect_heuristic(episodes)

        # Writeback: apply trait/style updates to identity (respecting anchors)
        changed = False
        if result.get("trait_updates"):
            changed = self._apply_trait_updates(result["trait_updates"]) or changed
        if result.get("style_updates"):
            changed = self._apply_style_updates(result["style_updates"]) or changed

        traits = self.identity.get("traits", [])
        style = self.identity.get("style", "")
        self.store.record_personality(
            snapshot={"traits": traits, "style": style},
            trigger="reflection_cycle",
            diff=json.dumps(result, ensure_ascii=False),
        )

        if changed and self._on_identity_changed:
            self._on_identity_changed()

        result["identity_updated"] = changed
        return result

    def _apply_trait_updates(self, updates: list[str]) -> bool:
        """Safe trait update: append new traits, never delete user-set anchors.

        Rules:
        1. User-set anchors are immutable
        2. New traits append to end
        3. Contradictory traits (vs anchors) are silently dropped
        4. Max 15 traits
        """
        anchors = self.identity.get("anchors", [])
        current = list(self.identity.get("traits", []))
        changed = False

        for trait in updates:
            trait = trait.strip()
            if not trait or trait in current:
                continue
            if self._contradicts_anchors(trait, anchors):
                continue
            current.append(trait)
            changed = True

        # Cap at 15 traits
        self.identity["traits"] = current[:15]
        return changed

    def _apply_style_updates(self, new_style: str) -> bool:
        """Update communication style if non-empty and different."""
        new_style = new_style.strip()
        if not new_style:
            return False
        current = self.identity.get("style", "")
        if new_style == current:
            return False
        self.identity["style"] = new_style
        return True

    @staticmethod
    def _contradicts_anchors(trait: str, anchors: list[str]) -> bool:
        """Check if a trait contradicts any anchor (keyword opposition, CJK+English)."""
        # Pairs of contradictory concepts (cross-language aware)
        _OPPOSITES = [
            ("verbose", "concise"), ("verbose", "简洁"), ("啰嗦", "简洁"), ("啰嗦", "concise"),
            ("reckless", "cautious"), ("reckless", "谨慎"), ("鲁莽", "cautious"), ("鲁莽", "谨慎"),
            ("dishonest", "honest"), ("dishonest", "诚实"), ("不诚实", "honest"), ("不诚实", "诚实"),
            ("lazy", "diligent"), ("lazy", "勤"), ("懒", "diligent"), ("懒", "勤"),
            ("indirect", "direct"), ("indirect", "直接"), ("委婉", "direct"), ("委婉", "直接"),
        ]
        trait_lower = trait.lower()
        for anchor in anchors:
            anchor_lower = anchor.lower()
            for a, b in _OPPOSITES:
                # If trait contains one side and anchor contains the other
                if (a in trait_lower and b in anchor_lower) or \
                   (b in trait_lower and a in anchor_lower):
                    return True
        return False

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
