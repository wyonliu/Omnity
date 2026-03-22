"""Ome Skills — pluggable skill system with three tiers.

Tiers: builtin (ships with Ome) / config (user YAML) / developer (pip install).
"""

from ome.skills.base import Skill, SkillResult, SkillRegistry
from ome.skills.builtins import register_builtins

__all__ = ["Skill", "SkillResult", "SkillRegistry", "register_builtins"]
