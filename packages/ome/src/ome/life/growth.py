"""Growth Engine — skill competence tracking and weekly insights.

Skills improve through real usage, not XP grinding. Users see their
Ome get measurably better at specific tasks over time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SkillProgress:
    name: str
    competence: float = 0.0  # 0.0 - 1.0
    uses: int = 0
    successes: int = 0
    min_bond_level: int = 0  # bond level required to unlock

    def record_use(self, success: bool, quality: float = 0.5):
        """Update competence after each use.

        quality: 0.0 (user rejected) to 1.0 (user said "perfect").
        Default 0.5 = user accepted without comment.
        """
        self.uses += 1
        if success:
            self.successes += 1
        delta = (quality - 0.5) * 0.05 if success else -0.02
        self.competence = max(0.0, min(1.0, self.competence + delta))

    @property
    def success_rate(self) -> float:
        return self.successes / max(1, self.uses)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "competence": round(self.competence, 3),
            "uses": self.uses,
            "successes": self.successes,
            "success_rate": round(self.success_rate, 2),
            "min_bond_level": self.min_bond_level,
        }


def _default_skills() -> dict[str, SkillProgress]:
    return {s.name: s for s in [
        SkillProgress("chat",     competence=0.3, min_bond_level=0),
        SkillProgress("write",    competence=0.0, min_bond_level=0),
        SkillProgress("research", competence=0.0, min_bond_level=0),
        SkillProgress("recall",   competence=0.2, min_bond_level=0),
        SkillProgress("schedule", competence=0.0, min_bond_level=2),
        SkillProgress("social",   competence=0.0, min_bond_level=4),
        SkillProgress("spatial",  competence=0.0, min_bond_level=4),
    ]}


@dataclass
class GrowthEngine:
    skills: dict[str, SkillProgress] = field(default_factory=dict)

    def __post_init__(self):
        if not self.skills:
            self.skills = _default_skills()

    def record_action(self, skill_name: str, success: bool, quality: float = 0.5):
        if skill_name in self.skills:
            self.skills[skill_name].record_use(success, quality)

    def available_skills(self, bond_level: int) -> list[SkillProgress]:
        return [s for s in self.skills.values() if bond_level >= s.min_bond_level]

    def locked_skills(self, bond_level: int) -> list[SkillProgress]:
        return [s for s in self.skills.values() if bond_level < s.min_bond_level]

    def to_dict(self) -> dict[str, Any]:
        return {name: sp.to_dict() for name, sp in self.skills.items()}

    @classmethod
    def from_dict(cls, d: dict) -> "GrowthEngine":
        engine = cls()
        for name, data in d.items():
            sp = SkillProgress(
                name=data["name"],
                competence=data.get("competence", 0.0),
                uses=data.get("uses", 0),
                successes=data.get("successes", 0),
                min_bond_level=data.get("min_bond_level", 0),
            )
            engine.skills[name] = sp
        return engine
