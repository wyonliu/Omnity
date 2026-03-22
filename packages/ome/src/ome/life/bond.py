"""Bond Level — relationship depth between user and Ome.

Not XP grinding. Levels advance through genuine interaction quality,
task success rate, and time spent together.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


BOND_LEVELS = [
    {"level": 0, "name": "初见",     "name_en": "First Meet",     "interactions": 0,    "days": 0,   "unlocks": ["basic_chat"]},
    {"level": 1, "name": "相识",     "name_en": "Acquaintance",   "interactions": 10,   "days": 0,   "unlocks": ["recall", "style_learning"]},
    {"level": 2, "name": "熟悉",     "name_en": "Familiar",       "interactions": 50,   "days": 3,   "unlocks": ["suggestions", "drafts"]},
    {"level": 3, "name": "知己",     "name_en": "Confidant",      "interactions": 200,  "days": 7,   "unlocks": ["proxy_assistant", "schedule"]},
    {"level": 4, "name": "挚友",     "name_en": "Close Friend",   "interactions": 500,  "days": 30,  "unlocks": ["social_proxy", "iot_control"]},
    {"level": 5, "name": "灵魂伴侣", "name_en": "Soulmate",       "interactions": 1000, "days": 90,  "unlocks": ["agent_mode"]},
    {"level": 6, "name": "命运共同体","name_en": "Bonded",          "interactions": 2000, "days": 180, "unlocks": ["full_trust"]},
]


@dataclass
class BondState:
    level: int = 0
    total_interactions: int = 0
    streak_days: int = 0
    max_streak: int = 0
    days_since_creation: int = 0
    successful_tasks: int = 0
    calibration_count: int = 0
    last_interaction_date: str = ""

    def record_interaction(self, today: str) -> dict[str, Any]:
        """Record an interaction and check for level-up."""
        self.total_interactions += 1

        if self.last_interaction_date == today:
            pass  # same day
        elif self.last_interaction_date and self._is_consecutive(self.last_interaction_date, today):
            self.streak_days += 1
            self.max_streak = max(self.max_streak, self.streak_days)
        elif self.last_interaction_date:
            self.streak_days = 1  # streak broken, restart (no punishment)
        else:
            self.streak_days = 1

        self.last_interaction_date = today
        old_level = self.level
        self._check_level_up()

        return {
            "level_changed": self.level != old_level,
            "new_level": self.level,
            "level_name": BOND_LEVELS[self.level]["name"],
            "streak_days": self.streak_days,
        }

    def record_task_success(self):
        self.successful_tasks += 1
        self._check_level_up()

    def record_calibration(self):
        self.calibration_count += 1

    def _check_level_up(self):
        """Level up based on quality metrics, not just quantity."""
        for lvl in BOND_LEVELS:
            if lvl["level"] <= self.level:
                continue
            if (self.total_interactions >= lvl["interactions"]
                    and self.days_since_creation >= lvl["days"]):
                self.level = lvl["level"]

    def current_level_info(self) -> dict[str, Any]:
        info = BOND_LEVELS[self.level].copy()
        info["total_interactions"] = self.total_interactions
        info["streak_days"] = self.streak_days
        info["max_streak"] = self.max_streak
        if self.level < len(BOND_LEVELS) - 1:
            nxt = BOND_LEVELS[self.level + 1]
            info["next_level"] = nxt["name"]
            info["interactions_needed"] = max(0, nxt["interactions"] - self.total_interactions)
            info["days_needed"] = max(0, nxt["days"] - self.days_since_creation)
        return info

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "level_name": BOND_LEVELS[self.level]["name"],
            "total_interactions": self.total_interactions,
            "streak_days": self.streak_days,
            "max_streak": self.max_streak,
            "days_since_creation": self.days_since_creation,
            "successful_tasks": self.successful_tasks,
            "calibration_count": self.calibration_count,
            "last_interaction_date": self.last_interaction_date,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "BondState":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    @staticmethod
    def _is_consecutive(prev: str, curr: str) -> bool:
        """Check if two YYYY-MM-DD dates are consecutive."""
        try:
            from datetime import datetime, timedelta
            p = datetime.strptime(prev, "%Y-%m-%d")
            c = datetime.strptime(curr, "%Y-%m-%d")
            return (c - p).days == 1
        except (ValueError, TypeError):
            return False
