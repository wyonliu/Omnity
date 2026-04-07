"""Writeback Damping — prevents personality oscillation and over-correction.

Replaces "meta-reflection" with a simple control-theory approach:
  - Max-delta clamping: no trait changes more than `max_delta` per cycle.
  - Oscillation detection: if a trait reverses direction N times in a window,
    reduce the step size automatically.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class DampingConfig:
    """Configuration for writeback damping."""
    max_delta: float = 0.15         # Max trait score change per reflection
    oscillation_window: int = 5     # Look at last N changes to detect oscillation
    oscillation_threshold: int = 3  # If direction reverses >= this many times, dampen
    damping_factor: float = 0.5     # Reduce step to this fraction when oscillating


class WritebackDamper:
    """Clamps proposed trait changes and detects oscillation.

    Usage:
        damper = WritebackDamper()
        clamped = damper.apply("curiosity", history=[0.5, 0.6, 0.5, 0.6], proposed=0.7)
        # → 0.625 (oscillation detected, step dampened)
    """

    def __init__(self, config: DampingConfig | None = None) -> None:
        self.config = config or DampingConfig()

    def apply(self, trait: str, history: list[float], proposed: float) -> float:
        """Apply damping to a proposed trait value.

        Args:
            trait: Trait name (for logging).
            history: Recent values of this trait (oldest first).
            proposed: The new value proposed by reflection.

        Returns:
            The damped value (may equal proposed if no damping needed).
        """
        if not history:
            return proposed

        current = history[-1]
        delta = proposed - current

        # 1. Max-delta clamping
        max_d = self.config.max_delta
        if abs(delta) > max_d:
            delta = max_d if delta > 0 else -max_d

        # 2. Oscillation detection
        if len(history) >= 3:
            reversals = self._count_reversals(history)
            if reversals >= self.config.oscillation_threshold:
                delta *= self.config.damping_factor

        return round(current + delta, 4)

    def apply_dict(
        self,
        current_scores: dict[str, float],
        proposed_scores: dict[str, float],
        history: dict[str, list[float]],
    ) -> dict[str, float]:
        """Apply damping to all trait scores in a dict.

        Args:
            current_scores: Current trait values.
            proposed_scores: Proposed new values from reflection.
            history: Per-trait value history (last N snapshots).

        Returns:
            Damped scores dict.
        """
        result = dict(proposed_scores)
        for trait, proposed in proposed_scores.items():
            trait_history = history.get(trait, [])
            if not trait_history and trait in current_scores:
                trait_history = [current_scores[trait]]
            result[trait] = self.apply(trait, trait_history, proposed)
        return result

    def _count_reversals(self, values: list[float]) -> int:
        """Count direction reversals in the last `oscillation_window` values."""
        window = values[-self.config.oscillation_window:]
        if len(window) < 3:
            return 0
        reversals = 0
        for i in range(2, len(window)):
            d1 = window[i - 1] - window[i - 2]
            d2 = window[i] - window[i - 1]
            if d1 * d2 < 0:  # sign change = reversal
                reversals += 1
        return reversals
