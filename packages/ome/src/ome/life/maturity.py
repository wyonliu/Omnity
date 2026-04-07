"""Maturity Score — read-only diagnostic of soul development.

Computes a 0.0–1.0 maturity score from three orthogonal signals:
  - Reflection depth: how many reflection cycles, trait diversity
  - Memory complexity: type distribution entropy, total volume
  - Behavioral consistency: streak stability, skill competence breadth

This is a *diagnostic*, not a game mechanic — it never gates features.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass
class MaturitySnapshot:
    """Point-in-time maturity assessment."""
    score: float            # 0.0–1.0 composite
    reflection_depth: float # 0.0–1.0
    memory_complexity: float  # 0.0–1.0
    behavioral_consistency: float  # 0.0–1.0
    label: str              # human-readable label

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": round(self.score, 3),
            "reflection_depth": round(self.reflection_depth, 3),
            "memory_complexity": round(self.memory_complexity, 3),
            "behavioral_consistency": round(self.behavioral_consistency, 3),
            "label": self.label,
        }


_LABELS = [
    (0.0, "萌芽"),    # seed
    (0.2, "觉醒"),    # awakening
    (0.4, "成长"),    # growing
    (0.6, "成熟"),    # mature
    (0.8, "圆满"),    # fulfilled
]


def _label_for(score: float) -> str:
    label = _LABELS[0][1]
    for threshold, name in _LABELS:
        if score >= threshold:
            label = name
    return label


class MaturityScorer:
    """Computes maturity from observable state. Stateless — no side effects."""

    # Weights for the three dimensions
    W_REFLECTION = 0.35
    W_MEMORY = 0.35
    W_BEHAVIOR = 0.30

    def score(
        self,
        reflection_count: int,
        trait_count: int,
        memory_total: int,
        memory_by_type: dict[str, int],
        streak_days: int,
        skill_competences: list[float],
        total_interactions: int,
    ) -> MaturitySnapshot:
        rd = self._reflection_depth(reflection_count, trait_count)
        mc = self._memory_complexity(memory_total, memory_by_type)
        bc = self._behavioral_consistency(streak_days, skill_competences, total_interactions)

        composite = (
            self.W_REFLECTION * rd
            + self.W_MEMORY * mc
            + self.W_BEHAVIOR * bc
        )
        composite = min(1.0, composite)

        return MaturitySnapshot(
            score=composite,
            reflection_depth=rd,
            memory_complexity=mc,
            behavioral_consistency=bc,
            label=_label_for(composite),
        )

    @staticmethod
    def _reflection_depth(reflection_count: int, trait_count: int) -> float:
        """Score from reflection history depth and trait diversity."""
        # log scale: 10 reflections ≈ 0.5, 50+ ≈ 1.0
        ref_score = min(1.0, math.log(reflection_count + 1, 50) if reflection_count > 0 else 0.0)
        # Trait diversity: 5 traits ≈ 0.5, 15 ≈ 1.0
        trait_score = min(1.0, trait_count / 15.0)
        return 0.6 * ref_score + 0.4 * trait_score

    @staticmethod
    def _memory_complexity(total: int, by_type: dict[str, int]) -> float:
        """Score from memory volume and type distribution entropy."""
        if total == 0:
            return 0.0
        # Volume: log scale, 100 memories ≈ 0.5, 1000+ ≈ 1.0
        vol_score = min(1.0, math.log(total + 1, 1000) if total > 0 else 0.0)
        # Type entropy (Shannon): max entropy = log(N_types)
        type_counts = [v for v in by_type.values() if v > 0]
        if len(type_counts) <= 1:
            entropy_score = 0.0
        else:
            total_t = sum(type_counts)
            probs = [c / total_t for c in type_counts]
            entropy = -sum(p * math.log(p) for p in probs if p > 0)
            max_entropy = math.log(len(type_counts))
            entropy_score = entropy / max_entropy if max_entropy > 0 else 0.0
        return 0.5 * vol_score + 0.5 * entropy_score

    @staticmethod
    def _behavioral_consistency(streak_days: int, competences: list[float],
                                 total_interactions: int) -> float:
        """Score from interaction consistency and skill breadth."""
        # Streak: 7 days ≈ 0.3, 30 ≈ 0.7, 90+ ≈ 1.0
        streak_score = min(1.0, streak_days / 90.0)
        # Skill breadth: average competence across all skills
        skill_score = sum(competences) / max(len(competences), 1) if competences else 0.0
        # Interaction volume: 50 ≈ 0.3, 200 ≈ 0.7, 500+ ≈ 1.0
        interact_score = min(1.0, total_interactions / 500.0)
        return 0.4 * streak_score + 0.3 * skill_score + 0.3 * interact_score
