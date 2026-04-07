"""L4 Self (Default Mode Network) — Personality maintenance, reflection, value alignment.

The emergence layer: from 'brain' to 'soul'. Maintains a consistent sense of self
across all interactions, detects personality drift, and guards value alignment.
"""

from __future__ import annotations

import json
import time
from typing import Any, Optional

from mindos.config import ModelRouter
from mindos.constants import (
    REFLECTION_MIN_COMMITS, REFLECTION_MAX_COMMITS, REFLECTION_ADAPTIVE_DIVISOR,
    REFLECTION_EPISODES_LIMIT, REFLECTION_MAX_TRAITS, REFLECTION_MAX_TOKENS,
    LOCALE,
)
from mindos.constitution import Constitution
from mindos.damping import WritebackDamper, DampingConfig
from mindos.importance import ImportanceTrigger, estimate_importance
from mindos.store import MemoryStore

_REFLECTION_LOCALE_HINTS: dict[str, str] = {
    "zh": "\n\nIMPORTANT: All output (summary, traits, style, suggestions) MUST be in Chinese (中文).",
    "en": "",
    "ja": "\n\nIMPORTANT: All output MUST be in Japanese (日本語).",
    "ko": "\n\nIMPORTANT: All output MUST be in Korean (한국어).",
}


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

        # v0.7: Constitution — immutable constraints on identity evolution
        anchors = identity.get("anchors", [])
        self.constitution = Constitution.from_anchors(anchors) if anchors else Constitution()

        # v0.7: Writeback damping — prevents personality oscillation
        self.damper = WritebackDamper()

        # v0.7: Importance-triggered reflection (alongside commit-count fallback)
        self.importance_trigger = ImportanceTrigger(threshold=100.0, store=store)

        # Per-trait score history for damping (last N snapshots)
        self._trait_score_history: dict[str, list[float]] = {}

    def on_commit(self, commit_result: Optional[dict[str, Any]] = None) -> Optional[dict[str, Any]]:
        """Called after each commit. Triggers reflection via importance OR commit-count.

        Two parallel triggers (whichever fires first):
        1. Importance accumulator (Stanford Generative Agents pattern):
           accumulate importance of extracted facts → reflect when threshold crossed.
        2. Adaptive commit-count fallback:
           threshold = clamp(total_memories / DIVISOR, MIN, MAX).
        """
        self._commit_count_since_reflect += 1

        # Importance trigger: score the commit result
        if commit_result:
            facts = commit_result.get("facts", [])
            if not facts and commit_result.get("facts_added", 0) > 0:
                # Build minimal fact list from commit result for scoring
                facts = [{"type": "fact", "confidence": 0.8}] * commit_result["facts_added"]
            episode = commit_result.get("episode", "")
            importance = estimate_importance(facts, episode)
            if self.importance_trigger.accumulate(importance):
                return self.reflect()

        # Commit-count fallback
        total = self.store.count()
        threshold = max(
            REFLECTION_MIN_COMMITS,
            min(total // REFLECTION_ADAPTIVE_DIVISOR, REFLECTION_MAX_COMMITS),
        )
        if self._commit_count_since_reflect >= threshold:
            return self.reflect()
        return None

    def reflect(self) -> Optional[dict[str, Any]]:
        """Run a reflection cycle: review recent episodes, detect drift, propose updates.

        NEW in v0.4: writes back trait/style changes to identity (respecting anchors).
        """
        self._commit_count_since_reflect = 0

        episodes = self.store.list_recent(limit=REFLECTION_EPISODES_LIMIT, mem_type="episode")
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

            locale_hint = _REFLECTION_LOCALE_HINTS.get(LOCALE, "")
            raw = self.router.call_llm(
                system=_REFLECTION_SYSTEM + locale_hint, user=user_msg,
                task="reflection", max_tokens=REFLECTION_MAX_TOKENS, json_mode=True,
            )
            if raw is None:
                result = self._reflect_heuristic(episodes)
            else:
                try:
                    result = json.loads(raw)
                except json.JSONDecodeError:
                    result = self._reflect_heuristic(episodes)

        # Writeback: apply trait/style updates with Constitution + Damping
        changed = False
        if result.get("trait_updates"):
            changed = self._apply_trait_updates(result["trait_updates"]) or changed
        if result.get("style_updates"):
            changed = self._apply_style_updates(result["style_updates"]) or changed

        # v0.7: Apply numeric score damping if scores exist in result
        if result.get("score_updates"):
            current_scores = self.identity.get("scores", {})
            proposed_scores = result["score_updates"]
            damped = self.damper.apply_dict(current_scores, proposed_scores, self._trait_score_history)
            self.identity["scores"] = damped
            # Update history for future damping
            for trait, val in damped.items():
                hist = self._trait_score_history.setdefault(trait, [])
                hist.append(val)
                if len(hist) > 10:
                    self._trait_score_history[trait] = hist[-10:]
            changed = True

        # v0.7: Constitution enforcement — validate the full proposed identity
        current_identity = dict(self.identity)
        proposed_identity = dict(self.identity)
        clamped, violations = self.constitution.validate_writeback(current_identity, proposed_identity)
        if violations:
            # Apply clamped values back
            self.identity["traits"] = clamped.get("traits", self.identity.get("traits", []))
            if "scores" in clamped:
                self.identity["scores"] = clamped["scores"]
            if "values" in clamped:
                self.identity["values"] = clamped["values"]
            result["constitution_violations"] = violations

        traits = self.identity.get("traits", [])
        style = self.identity.get("style", "")
        self.store.record_personality(
            snapshot={"traits": traits, "style": style},
            trigger="reflection_cycle",
            diff=json.dumps(result, ensure_ascii=False),
        )

        if changed and self._on_identity_changed:
            self._on_identity_changed()

        # Reset importance accumulator after successful reflection
        self.importance_trigger.reset()

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

        self.identity["traits"] = current[:REFLECTION_MAX_TRAITS]
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
        """Heuristic reflection when no LLM is available.

        Honest about its limitations: cannot detect drift or assess alignment
        without an LLM. Returns topic extraction only.
        """
        from collections import Counter
        word_counts: Counter[str] = Counter()
        for ep in episodes:
            for word in ep.content.split():
                if len(word) > 2:  # skip noise
                    word_counts[word.lower()] += 1

        return {
            "summary": f"Scanned {len(episodes)} recent episodes (heuristic only — no LLM available for deep analysis)",
            "drift_detected": None,  # None = unknown, not False
            "drift_details": "Drift detection requires LLM — skipped",
            "new_traits_observed": [],
            "value_alignment_score": None,  # None = not assessed, not 0.8
            "suggestions": ["Enable an LLM provider for meaningful self-reflection"],
            "method": "heuristic",
            "top_themes": [w for w, _ in word_counts.most_common(REFLECTION_MAX_TRAITS)],
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
