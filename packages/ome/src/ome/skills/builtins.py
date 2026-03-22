"""Built-in skills — ships with every Ome installation.

Five core skills:
  1. ChatSkill: conversational AI + auto memory
  2. RecallSkill: cross-platform memory search
  3. WriteSkill: draft emails, articles, code in user's voice
  4. ResearchSkill: search + summarize + store
  5. ScheduleSkill: add / list / remind schedule items
"""

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING, Any

from ome.skills.base import Skill, SkillResult

if TYPE_CHECKING:
    from ome.core import Ome

log = logging.getLogger("ome.skills.builtins")


class ChatSkill(Skill):
    """Conversational chat + auto memory. Wraps Ome.chat()."""
    name = "chat"
    description = "对话 自动记忆 聊天 chat conversation"
    tier = "builtin"
    requires_approval = False
    min_bond_level = 0

    def execute(self, ome: "Ome", *, message: str = "", **kwargs: Any) -> SkillResult:
        if not message:
            return SkillResult(success=False, output="No message provided.")
        reply = ome.chat(message)
        return SkillResult(success=True, output=reply, output_type="text")


class RecallSkill(Skill):
    """Cross-platform memory search. Wraps Ome.recall()."""
    name = "recall"
    description = "记忆 搜索 回忆 recall search memory"
    tier = "builtin"
    requires_approval = False
    min_bond_level = 0

    def execute(self, ome: "Ome", *, query: str = "", top_k: int = 10, **kwargs: Any) -> SkillResult:
        if not query:
            return SkillResult(success=False, output="No query provided.")
        results = ome.recall(query, top_k=top_k)
        if not results:
            return SkillResult(success=True, output="没有找到相关记忆。")
        lines = [f"- [{r.get('type', '?')}] {r.get('content', '')}" for r in results]
        return SkillResult(
            success=True,
            output="\n".join(lines),
            output_type="report",
            metadata={"count": len(results)},
        )


class WriteSkill(Skill):
    """Draft writing in user's voice: emails, articles, code, reports."""
    name = "write"
    description = "写作 邮件 文章 代码 周报 草稿 write email article draft"
    tier = "builtin"
    requires_approval = True  # Draft needs user confirmation
    min_bond_level = 2
    trust_minimum = 2

    def execute(self, ome: "Ome", *, task: str = "", context: str = "", **kwargs: Any) -> SkillResult:
        if not task:
            return SkillResult(success=False, output="No writing task provided.")

        # Hydrate identity + recall relevant memories
        identity = ome.soul.hydrate(context=task, max_tokens=1500)
        memories = ome.recall(task, top_k=5)
        memory_ctx = "\n".join(
            f"- {m.get('content', '')}" for m in memories
        ) if memories else ""

        personality = ome.soul.identity.get("personality", {})
        catchphrases = personality.get("catchphrases", [])

        system = (
            f"你是{ome.name}的写作助手。用{ome.name}的风格来写。\n"
            f"身份信息：\n{identity}\n\n"
        )
        if catchphrases:
            system += f"写作风格要符合这些口头禅：{'、'.join(catchphrases[:5])}\n"
        if memory_ctx:
            system += f"\n相关记忆：\n{memory_ctx}\n"
        if context:
            system += f"\n额外上下文：\n{context}\n"
        system += (
            f"\n## 要求\n"
            f"- 用{ome.name}的第一人称\n"
            f"- 风格与{ome.name}平时说话一致\n"
            f"- 输出完整的草稿内容\n"
        )

        draft = ome._generate(system, task)

        # Commit the writing task to memory
        ome.remember(f"[write_task] {task[:100]}", source="ome-write")

        return SkillResult(
            success=True,
            output=draft,
            output_type="draft",
            needs_approval=True,
            metadata={"task": task},
        )


class ResearchSkill(Skill):
    """Search memories, summarize, and store findings."""
    name = "research"
    description = "研究 搜索 总结 整理 research search summarize"
    tier = "builtin"
    requires_approval = False
    min_bond_level = 0

    def execute(self, ome: "Ome", *, topic: str = "", **kwargs: Any) -> SkillResult:
        if not topic:
            return SkillResult(success=False, output="No topic provided.")

        # Step 1: Recall existing knowledge
        memories = ome.recall(topic, top_k=10)
        existing = "\n".join(
            f"- [{m.get('type', '?')}] {m.get('content', '')}" for m in memories
        ) if memories else "（暂无相关记忆）"

        # Step 2: Synthesize with LLM
        identity = ome.soul.hydrate(context=topic, max_tokens=800)
        system = (
            f"你是{ome.name}的研究助手。\n"
            f"身份：\n{identity}\n\n"
            f"现有知识：\n{existing}\n\n"
            f"## 任务\n"
            f"根据现有知识，整理出关于「{topic}」的研究报告：\n"
            f"1. 已知信息摘要\n"
            f"2. 关键发现\n"
            f"3. 信息缺口（还需要了解什么）\n"
        )

        report = ome._generate(system, f"请整理关于「{topic}」的研究报告")

        # Step 3: Commit research results to memory
        ome.remember(f"[research] {topic}: {report[:200]}", source="ome-research")

        return SkillResult(
            success=True,
            output=report,
            output_type="report",
            metadata={"topic": topic, "existing_memories": len(memories)},
        )


class ScheduleSkill(Skill):
    """Schedule management: add, list, remind."""
    name = "schedule"
    description = "日程 提醒 计划 安排 schedule remind plan calendar"
    tier = "builtin"
    requires_approval = True
    min_bond_level = 2
    trust_minimum = 2

    def execute(self, ome: "Ome", *, action: str = "list", **kwargs: Any) -> SkillResult:
        """action: add | list | remind | remove"""
        store = ome.soul.store

        if action == "add":
            title = kwargs.get("title", "")
            when = kwargs.get("when", "")
            if not title:
                return SkillResult(success=False, output="请提供日程标题。")

            schedule_data = self._load_schedule(store)
            item = {
                "title": title,
                "when": when,
                "created_at": time.time(),
                "done": False,
            }
            schedule_data.append(item)
            self._save_schedule(store, schedule_data)

            ome.remember(f"[schedule] 添加日程: {title} ({when})", source="ome-schedule")

            # Check first_schedule achievement
            ome.achievements.check_and_unlock("first_schedule")
            ome.bond.record_task_success()

            return SkillResult(
                success=True,
                output=f"已添加日程：{title}" + (f"（{when}）" if when else ""),
                output_type="action",
                metadata={"title": title, "when": when},
            )

        elif action == "list":
            schedule_data = self._load_schedule(store)
            if not schedule_data:
                return SkillResult(success=True, output="暂无日程。")
            lines = []
            for i, item in enumerate(schedule_data):
                status = "✅" if item.get("done") else "⬜"
                line = f"{status} {item['title']}"
                if item.get("when"):
                    line += f" ({item['when']})"
                lines.append(line)
            return SkillResult(
                success=True,
                output="\n".join(lines),
                output_type="report",
                metadata={"count": len(schedule_data)},
            )

        elif action == "remove":
            title = kwargs.get("title", "")
            schedule_data = self._load_schedule(store)
            before = len(schedule_data)
            schedule_data = [s for s in schedule_data if title.lower() not in s["title"].lower()]
            self._save_schedule(store, schedule_data)
            removed = before - len(schedule_data)
            return SkillResult(
                success=removed > 0,
                output=f"已移除 {removed} 条日程。" if removed else "未找到匹配的日程。",
            )

        return SkillResult(success=False, output=f"Unknown action: {action}")

    @staticmethod
    def _load_schedule(store: Any) -> list[dict]:
        raw = store.get_state("ome.schedule")
        if raw:
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                pass
        return []

    @staticmethod
    def _save_schedule(store: Any, data: list[dict]) -> None:
        store.set_state("ome.schedule", json.dumps(data, ensure_ascii=False))


def register_builtins(registry: "SkillRegistry") -> None:
    """Register all built-in skills."""
    from ome.skills.base import SkillRegistry
    registry.register(ChatSkill())
    registry.register(RecallSkill())
    registry.register(WriteSkill())
    registry.register(ResearchSkill())
    registry.register(ScheduleSkill())
