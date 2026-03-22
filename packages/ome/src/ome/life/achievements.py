"""Achievement System — milestone markers for Ome's growth.

Each achievement unlocks with a ceremony: Ome proactively tells the user.
Three tiers: basic (easy), deep (meaningful), hidden (surprise).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Achievement:
    id: str
    name: str
    icon: str
    description: str
    tier: str  # "basic" | "deep" | "hidden"
    condition: str  # human-readable, checked programmatically


ACHIEVEMENT_CATALOG: list[Achievement] = [
    # Basic
    Achievement("first_chat", "破冰", "🌱", "我们的故事开始了", "basic", "first_interaction"),
    Achievement("first_memory", "初识", "🧠", "我记住了关于你的第一件事", "basic", "first_fact_stored"),
    Achievement("first_schedule", "守时者", "📅", "我第一次提醒你做到了", "basic", "first_schedule_reminder"),
    Achievement("first_draft", "代笔人", "✍️", "我的第一篇作品，你满意吗", "basic", "first_draft_approved"),
    Achievement("cross_platform", "跨界者", "🔗", "我在不同平台之间穿梭了", "basic", "cross_platform_sync"),
    Achievement("ten_facts", "记忆萌芽", "🌿", "我已经记住了 10 件关于你的事", "basic", "facts_count >= 10"),
    Achievement("fifty_chats", "健谈者", "💬", "我们已经聊了 50 次了", "basic", "interactions >= 50"),

    # Deep
    Achievement("mirror", "镜像", "🎭", "我越来越像你了", "deep", "user_said_thats_me"),
    Achievement("morning_7", "晨曦使者", "🌙", "连续 7 天，每天的第一句都是给你的", "deep", "streak >= 7"),
    Achievement("home_iot", "回家了", "🏠", "欢迎回家，灯已经为你点亮", "deep", "first_iot_control"),
    Achievement("social_first", "社交蝴蝶", "🤝", "我替你认识了一个有趣的人", "deep", "first_ome_social"),
    Achievement("weekly_4", "周报达人", "📊", "你的第一个月，我都记得", "deep", "weekly_reports >= 4"),
    Achievement("month_streak", "月度挚友", "🌟", "30 天不间断的陪伴", "deep", "streak >= 30"),

    # Hidden
    Achievement("night_owl", "夜猫子", "🦉", "深夜了还在聊，你是夜猫子吧", "hidden", "chat_after_23_or_before_5"),
    Achievement("deep_talk", "深谈者", "🌊", "一条消息超过500字，你是认真的", "hidden", "single_message > 500_chars"),
    Achievement("know_unsaid", "知音", "🎵", "我懂你没说出口的", "hidden", "proactive_preference_match"),
    Achievement("night_task", "不眠不休", "🔥", "你睡着的时候，我帮你做完了", "hidden", "autonomous_task_while_idle"),
    Achievement("soulmate", "灵魂共振", "💎", "我们已经是灵魂伴侣了", "hidden", "bond_level >= 5"),
]


@dataclass
class AchievementTracker:
    unlocked: dict[str, str] = field(default_factory=dict)  # id → unlock_date

    def check_and_unlock(self, achievement_id: str) -> Achievement | None:
        """Attempt to unlock an achievement. Returns it if newly unlocked."""
        if achievement_id in self.unlocked:
            return None
        for ach in ACHIEVEMENT_CATALOG:
            if ach.id == achievement_id:
                self.unlocked[achievement_id] = datetime.now().strftime("%Y-%m-%d %H:%M")
                return ach
        return None

    def unlocked_count(self) -> int:
        return len(self.unlocked)

    def total_count(self) -> int:
        return len(ACHIEVEMENT_CATALOG)

    def unlocked_list(self) -> list[dict[str, Any]]:
        result = []
        for ach in ACHIEVEMENT_CATALOG:
            if ach.id in self.unlocked:
                result.append({
                    "id": ach.id,
                    "name": ach.name,
                    "icon": ach.icon,
                    "description": ach.description,
                    "tier": ach.tier,
                    "unlocked_at": self.unlocked[ach.id],
                })
        return result

    def locked_visible(self) -> list[dict[str, Any]]:
        """Show locked achievements (except hidden ones)."""
        result = []
        for ach in ACHIEVEMENT_CATALOG:
            if ach.id not in self.unlocked and ach.tier != "hidden":
                result.append({
                    "id": ach.id, "name": ach.name, "icon": "🔒",
                    "description": "???", "tier": ach.tier,
                })
        return result

    def to_dict(self) -> dict:
        return {"unlocked": self.unlocked}

    @classmethod
    def from_dict(cls, d: dict) -> "AchievementTracker":
        return cls(unlocked=d.get("unlocked", {}))
