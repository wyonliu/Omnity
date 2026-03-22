"""Skill system — three-tier pluggable skill architecture.

Tiers:
  - builtin: ships with Ome (chat, recall, write, research, schedule)
  - config: user-configured via YAML (custom prompts, tools)
  - developer: pip install ome-skill-xxx

Each skill:
  - Has a min_bond_level requirement
  - Can require user approval before execution
  - Auto-records to GrowthEngine after execution
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from ome.core import Ome

log = logging.getLogger("ome.skills")


@dataclass
class SkillResult:
    """Result of a skill execution."""
    success: bool
    output: str
    output_type: str = "text"  # text | draft | action | report
    needs_approval: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class Skill:
    """Base class for all Ome skills."""

    name: str = "base"
    description: str = ""
    tier: str = "builtin"  # builtin | config | developer
    requires_approval: bool = False
    trust_minimum: int = 0
    min_bond_level: int = 0

    def can_execute(self, ome: "Ome") -> bool:
        """Check if the skill can execute given current state."""
        from ome.engine.permissions import TrustLevel
        return (ome.bond.level >= self.min_bond_level and
                ome.permissions.trust_level >= self.trust_minimum)

    def execute(self, ome: "Ome", **kwargs: Any) -> SkillResult:
        """Execute the skill. Override in subclasses."""
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<Skill:{self.name} tier={self.tier} bond>={self.min_bond_level}>"


class SkillRegistry:
    """Three-tier skill registry.

    Usage:
        registry = SkillRegistry()
        registry.register(ChatSkill())
        results = registry.match("写封邮件")
        skill = registry.get("write")
        result = skill.execute(ome, task="写邮件")
    """

    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        """Register a skill."""
        self._skills[skill.name] = skill

    def get(self, name: str) -> Optional[Skill]:
        """Get a skill by name."""
        return self._skills.get(name)

    def match(self, goal: str) -> list[Skill]:
        """Find skills that might handle a goal (keyword matching)."""
        goal_lower = goal.lower()
        matches = []
        for skill in self._skills.values():
            if skill.name in goal_lower:
                matches.append(skill)
                continue
            # Check if description keywords match
            # len > 2 for ascii, len > 1 for CJK (2-char words like 邮件/写作)
            if skill.description:
                desc_words = skill.description.lower().split()
                if any(w in goal_lower for w in desc_words
                       if (len(w) > 2 or any('\u4e00' <= c <= '\u9fff' for c in w))):
                    matches.append(skill)
        return matches

    def list_all(self) -> list[dict[str, Any]]:
        """List all registered skills."""
        return [
            {
                "name": s.name,
                "description": s.description,
                "tier": s.tier,
                "requires_approval": s.requires_approval,
                "min_bond_level": s.min_bond_level,
            }
            for s in self._skills.values()
        ]

    def execute(self, name: str, ome: "Ome", **kwargs: Any) -> SkillResult:
        """Execute a skill by name, with auto growth recording."""
        skill = self.get(name)
        if not skill:
            return SkillResult(success=False, output=f"Skill '{name}' not found.")

        if not skill.can_execute(ome):
            return SkillResult(
                success=False,
                output=f"Skill '{name}' requires bond level {skill.min_bond_level} "
                       f"(current: {ome.bond.level}).",
            )

        try:
            result = skill.execute(ome, **kwargs)
            # Auto-record to growth
            quality = 0.7 if result.success else 0.2
            ome.growth.record_action(name, success=result.success, quality=quality)
            return result
        except Exception as e:
            log.warning("Skill '%s' failed: %s", name, e)
            ome.growth.record_action(name, success=False, quality=0.0)
            return SkillResult(success=False, output=f"Skill error: {e}")
