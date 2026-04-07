"""Constitution — immutable constraints on identity evolution.

The Constitution is the highest-authority layer: L4 reflection can propose changes,
but the Constitution validates and clamps them before writeback. Rules are
deterministic (no LLM calls) and auditable.

This generalizes the anchor protection from v0.6 into a formal rule system.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Literal

log = logging.getLogger("mindos.constitution")


@dataclass
class ConstitutionRule:
    """A single constitutional constraint.

    Rule types:
      - trait_immutable: This trait cannot be changed at all.
      - range_lock: Trait value must stay within [min, max].
      - max_delta: Trait can change by at most `delta` per reflection cycle.
      - value_required: This value must always be present in the values list.
    """
    id: str
    type: Literal["trait_immutable", "range_lock", "max_delta", "value_required"]
    target: str  # trait name, or "*" for all traits (max_delta only)
    params: dict[str, Any] = field(default_factory=dict)


class Constitution:
    """Validates L4 writebacks against immutable rules.

    Usage:
        constitution = Constitution([
            ConstitutionRule("empathy-floor", "range_lock", "empathy", {"min": 0.5}),
            ConstitutionRule("honesty-locked", "trait_immutable", "honest", {}),
            ConstitutionRule("slow-change", "max_delta", "*", {"delta": 0.15}),
        ])
        clamped, violations = constitution.validate_writeback(current_traits, proposed_traits)
    """

    def __init__(self, rules: list[ConstitutionRule] | None = None) -> None:
        self.rules = list(rules) if rules else []

    def add_rule(self, rule: ConstitutionRule) -> None:
        self.rules.append(rule)

    def validate_writeback(
        self,
        current: dict[str, Any],
        proposed: dict[str, Any],
    ) -> tuple[dict[str, Any], list[str]]:
        """Validate and clamp a proposed identity change.

        Args:
            current: Current identity dict (traits, style, values, etc.)
            proposed: Proposed identity dict after reflection.

        Returns:
            (clamped_proposed, violation_descriptions)
            Never raises — always returns a valid state.
        """
        result = dict(proposed)
        violations: list[str] = []

        current_traits = current.get("traits", [])
        proposed_traits = list(result.get("traits", []))

        for rule in self.rules:
            if rule.type == "trait_immutable":
                # This trait must remain in the list and cannot be removed
                if rule.target in current_traits and rule.target not in proposed_traits:
                    proposed_traits.append(rule.target)
                    violations.append(
                        f"[{rule.id}] Cannot remove immutable trait '{rule.target}'"
                    )

            elif rule.type == "range_lock":
                # Not applicable to string trait lists, but useful for numeric personality scores
                # Check in a "scores" sub-dict if present
                scores = result.get("scores", {})
                current_scores = current.get("scores", {})
                if rule.target in scores:
                    val = scores[rule.target]
                    lo = rule.params.get("min", float("-inf"))
                    hi = rule.params.get("max", float("inf"))
                    if val < lo:
                        scores[rule.target] = lo
                        violations.append(
                            f"[{rule.id}] Clamped '{rule.target}' from {val:.2f} to min {lo:.2f}"
                        )
                    elif val > hi:
                        scores[rule.target] = hi
                        violations.append(
                            f"[{rule.id}] Clamped '{rule.target}' from {val:.2f} to max {hi:.2f}"
                        )
                result["scores"] = scores

            elif rule.type == "max_delta":
                # Limit how much any numeric score can change per reflection
                delta = rule.params.get("delta", 0.15)
                scores = result.get("scores", {})
                current_scores = current.get("scores", {})
                targets = [rule.target] if rule.target != "*" else list(scores.keys())
                for t in targets:
                    if t in scores and t in current_scores:
                        old = current_scores[t]
                        new = scores[t]
                        if abs(new - old) > delta:
                            clamped = old + delta if new > old else old - delta
                            violations.append(
                                f"[{rule.id}] Clamped '{t}' delta from {abs(new-old):.2f} to {delta:.2f}"
                            )
                            scores[t] = round(clamped, 3)
                result["scores"] = scores

            elif rule.type == "value_required":
                # A value that must always be in the values list
                values = result.get("values", [])
                if rule.target not in values:
                    values.append(rule.target)
                    violations.append(
                        f"[{rule.id}] Re-added required value '{rule.target}'"
                    )
                result["values"] = values

        result["traits"] = proposed_traits

        if violations:
            log.info("Constitution enforced %d rules: %s", len(violations), "; ".join(violations))

        return result, violations

    def is_locked(self, trait: str) -> bool:
        """Check if a trait is immutable."""
        return any(
            r.type == "trait_immutable" and r.target == trait
            for r in self.rules
        )

    def to_dict(self) -> list[dict[str, Any]]:
        return [
            {"id": r.id, "type": r.type, "target": r.target, "params": r.params}
            for r in self.rules
        ]

    @classmethod
    def from_dict(cls, data: list[dict[str, Any]]) -> "Constitution":
        rules = [
            ConstitutionRule(
                id=d["id"], type=d["type"], target=d["target"],
                params=d.get("params", {}),
            )
            for d in data
        ]
        return cls(rules)

    @classmethod
    def from_anchors(cls, anchors: list[str]) -> "Constitution":
        """Build a Constitution from v0.6-style anchor list (backward compat)."""
        rules = [
            ConstitutionRule(
                id=f"anchor-{i}", type="trait_immutable", target=anchor,
            )
            for i, anchor in enumerate(anchors)
        ]
        return cls(rules)
