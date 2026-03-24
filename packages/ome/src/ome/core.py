"""Ome core — your AI twin, powered by Mindos.

Ome is the consumer-facing wrapper around Mindos. It adds:
  - Conversational chat with automatic memory commit/recall
  - Persona-aware response generation (your Ome speaks like you)
  - Life system: bond levels, achievements, skill growth, streaks, emotion
  - Autonomy engine: proactive events (morning greeting, streak, idle check-in)
  - Permission sandbox: HITL control over what the Ome can do
  - Persona engine: extract user's voice from chat logs / social profiles
  - Simple create/chat/export interface (no brain-layer jargon)
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from mindos.core import Mindos

from ome.life.bond import BondState
from ome.life.achievements import AchievementTracker
from ome.life.growth import GrowthEngine
from ome.life.emotion import EmotionState, detect_crisis
from ome.life.persona import PersonaEngine, PersonaProfile, parse_chat_export
from ome.engine.autonomy import AutonomyEngine, EventResult
from ome.engine.conversation_strategy import (
    build_strategy_prompt, classify_memories, get_growth_phase, parse_response,
)
from ome.engine.soul_card import SoulCardData, generate_soul_card
from ome.engine.permissions import PermissionSandbox, TrustLevel
from ome.engine.personality import PersonalityEngine
from ome.identity_protocol import OmeIdentity
from ome.skills.base import SkillRegistry, SkillResult
from ome.skills.builtins import register_builtins

log = logging.getLogger("ome")


class Ome:
    """Your AI twin — remembers everything, speaks like you, works for you.

    Usage:
        ome = Ome.create("~/.ome", name="Alice", traits=["curious", "direct"])
        ome = Ome.load("~/.ome")

        # Chat (auto-remembers everything)
        reply = ome.chat("What do you know about my Python projects?")

        # Import your voice from chat logs
        ome.import_persona(Path("wechat_export.txt"))

        # Check proactive events
        events = ome.check_events()

        # Export portable persona for any platform
        persona = ome.export()
    """

    def __init__(self, soul: Mindos, root: Path) -> None:
        self.soul = soul
        self.root = root
        self._chat_history: list[dict[str, str]] = []
        self.bond = BondState()
        self.achievements = AchievementTracker()
        self.growth = GrowthEngine()
        self.emotion = EmotionState()
        self.permissions = PermissionSandbox()
        self.autonomy = AutonomyEngine(permissions=self.permissions)
        self._persona_profile: Optional[PersonaProfile] = None
        self.personality = PersonalityEngine(soul.identity)
        self.skill_registry = SkillRegistry()
        register_builtins(self.skill_registry)
        self._load_life_state()

    @classmethod
    def create(
        cls,
        path: str | Path = "~/.ome",
        name: str = "User",
        traits: Optional[list[str]] = None,
        style: str = "",
        values: Optional[list[str]] = None,
        capabilities: Optional[list[dict]] = None,
    ) -> "Ome":
        """Create a new Ome (your digital twin)."""
        root = Path(path).expanduser()
        soul = Mindos.init(
            root, name=name, traits=traits, style=style,
            values=values, capabilities=capabilities,
        )
        return cls(soul, root)

    @classmethod
    def load(cls, path: str | Path = "~/.ome") -> "Ome":
        """Load an existing Ome."""
        root = Path(path).expanduser()
        soul = Mindos.load(root)
        return cls(soul, root)

    # -- Chat (the main interface) -------------------------------------------

    def chat(self, message: str, provider: str = "") -> str:
        """Talk to your Ome. It remembers everything you've ever said.

        Flow (with conversation strategy engine):
        1. L0 keyword emotion update (fast fallback)
        2. Recall + classify memories by type
        3. Determine growth phase from total interactions
        4. Build strategy-aware system prompt (with <think> instructions)
        5. Generate response (LLM outputs <think> block + reply)
        6. Parse <think> → update emotion (L1 deep) + evolve persona
        7. Validate, commit, update life state

        Returns the Ome's response text.
        """
        # L0 keyword emotion (fast fallback, always runs)
        self.emotion.update_from_message(message)

        # Crisis detection — safety net, highest priority
        is_crisis = detect_crisis(message)

        # Low-engagement detection — "嗯", "哦", "好" etc.
        stripped = message.strip()
        is_low_engagement = len(stripped) <= 4 and not any(
            c in stripped for c in "？?！!…"
        )

        # Recall and classify memories (15 for richer context)
        memories = self.soul.recall(message, top_k=15)
        classified = classify_memories(memories) if memories else []
        memory_context = "\n".join(
            f"- [{m.get('type', '?')}] {m.get('content', '')}"
            for m in memories
        ) if memories else "(no relevant memories yet)"

        # Determine growth phase
        phase = get_growth_phase(self.bond.total_interactions)

        # Build strategy-aware system prompt
        identity = self.soul.hydrate(context=message, max_tokens=1500)
        personality = self.soul.identity.get("personality", {})
        catchphrases = personality.get("catchphrases", [])
        anchor_text = self.personality.system_prompt_injection()

        system_prompt = build_strategy_prompt(
            name=self.name,
            identity=identity,
            memory_context=memory_context,
            classified_memories=classified,
            emotion_state=self.emotion.to_dict(),
            phase=phase,
            personality_injection=anchor_text,
            catchphrases=catchphrases,
            conversation_count=self.bond.total_interactions,
            is_crisis=is_crisis,
            is_low_engagement=is_low_engagement,
        )

        # Generate (LLM will output <think>...</think> + reply)
        raw_reply = self._generate(system_prompt, message, provider)

        # Parse thinking block
        reply, thinking = parse_response(raw_reply)

        # L1 deep emotion update from LLM's assessment
        if thinking:
            self.emotion.update_from_llm_thinking(
                emotion=thinking.emotion,
                nuance=thinking.emotion_nuance,
            )
            # Evolve persona from conversation markers
            if thinking.persona_markers and self._persona_profile:
                self._persona_profile = PersonaEngine.evolve_from_markers(
                    self._persona_profile,
                    thinking.persona_markers,
                )
            elif thinking.persona_markers and not self._persona_profile:
                # Bootstrap persona from first markers
                from ome.life.persona import PersonaProfile as PP
                self._persona_profile = PP(raw_traits=thinking.persona_markers[:5])

        # Validate response against personality
        ok, reply = self.personality.validate(reply, context=message)

        conversation = f"user: {message}\nassistant: {reply}"
        self._chat_history.append({"role": "user", "content": message})
        self._chat_history.append({"role": "assistant", "content": reply})

        try:
            self.soul.commit(conversation, source="ome-chat")
        except Exception as e:
            log.warning("Failed to commit chat: %s", e)

        today = datetime.now().strftime("%Y-%m-%d")
        level_result = self.bond.record_interaction(today)
        self.growth.record_action("chat", success=True, quality=0.5)

        # Update emotion from interaction patterns
        idle_days = 0
        if self.bond.last_interaction_date:
            try:
                last_dt = datetime.strptime(self.bond.last_interaction_date, "%Y-%m-%d")
                idle_days = max(0, (datetime.now() - last_dt).days - 1)
            except (ValueError, TypeError):
                pass
        self.emotion.update_from_interaction(
            streak_days=self.bond.streak_days,
            bond_level=self.bond.level,
            idle_days=idle_days,
            actions_today=self.autonomy.actions_today,
            action_budget=self.autonomy.daily_action_budget,
        )

        # Track daily stats for challenges
        self._record_daily_stat(message)

        # Suppress gamification noise during emotional/crisis/low-engagement moments
        suppress_gamification = is_crisis or (
            self.emotion.mood in ("sad", "stressed") and is_low_engagement
        )

        self._check_achievements(message=message)
        streak_rewards = self._check_streak_rewards() if not suppress_gamification else []
        self._save_life_state()

        # Append streak reward messages (suppressed during sensitive moments)
        if not suppress_gamification:
            for reward in streak_rewards:
                reply += f"\n\n🎁 {reward['name']}：{reward['description']}"

        if level_result.get("level_changed") and not suppress_gamification:
            lvl_name = level_result["level_name"]
            new_level = level_result["new_level"]
            reply += f"\n\n✨ 我们的关系升级了：{lvl_name}！"
            # Auto-raise trust with bond level
            if new_level >= 3:
                self.permissions.raise_trust(TrustLevel.ASSISTANT)
            if new_level >= 5:
                self.permissions.raise_trust(TrustLevel.DEPUTY)

        return reply

    def remember(self, text: str, source: str = "manual") -> dict[str, Any]:
        """Teach your Ome something directly."""
        self.growth.record_action("recall", success=True, quality=0.6)
        # Track for daily challenge
        today = datetime.now().strftime("%Y-%m-%d")
        try:
            key = f"ome.daily.{today}"
            raw = self.soul.store.get_state(key)
            daily = json.loads(raw) if raw else {}
            daily["memories_added"] = daily.get("memories_added", 0) + 1
            self.soul.store.set_state(key, json.dumps(daily))
        except Exception:
            pass
        return self.soul.commit(f"user: {text}", source=source)

    def recall(self, query: str, top_k: int = 10) -> list[dict[str, Any]]:
        """Ask your Ome what it remembers about a topic."""
        self.growth.record_action("recall", success=True, quality=0.5)
        # Track for daily challenge
        today = datetime.now().strftime("%Y-%m-%d")
        try:
            key = f"ome.daily.{today}"
            raw = self.soul.store.get_state(key)
            daily = json.loads(raw) if raw else {}
            daily["memory_searches"] = daily.get("memory_searches", 0) + 1
            self.soul.store.set_state(key, json.dumps(daily))
        except Exception:
            pass
        return self.soul.recall(query, top_k=top_k)

    def forget(self, pattern: str) -> dict[str, Any]:
        """Make your Ome forget something. Permanent."""
        return self.soul.forget(pattern)

    # -- Skills ----------------------------------------------------------------

    def use_skill(self, skill_name: str, **kwargs: Any) -> SkillResult:
        """Execute a skill by name. Auto-records to growth."""
        result = self.skill_registry.execute(skill_name, self, **kwargs)
        self._save_life_state()
        return result

    def list_skills(self) -> list[dict[str, Any]]:
        """List all available skills with their status."""
        skills = self.skill_registry.list_all()
        for s in skills:
            s["available"] = self.bond.level >= s["min_bond_level"]
            growth = self.growth.skills.get(s["name"])
            if growth:
                s["competence"] = growth.competence
                s["uses"] = growth.uses
        return skills

    # -- Mirror chat & calibrate -----------------------------------------------

    def mirror_chat(self, message: str) -> str:
        """Talk to "yourself" — Ome responds in your voice. The Aha Moment."""
        reply = PersonaEngine.mirror_chat(message, self)
        # Commit the exchange to memory
        try:
            self.soul.commit(
                f"user: {message}\nmirror: {reply}",
                source="ome-mirror",
            )
        except Exception as e:
            log.warning("Failed to commit mirror chat: %s", e)
        self.growth.record_action("chat", success=True, quality=0.6)
        self._save_life_state()
        return reply

    def calibrate(self, message: str, response: str, feedback: str) -> dict[str, Any]:
        """Provide feedback on a mirror_chat response to improve accuracy."""
        return PersonaEngine.calibrate(message, response, feedback, self)

    def learn_from_platform(self, platform: str, data_path: str) -> PersonaProfile:
        """Import persona data from a platform export file.

        Supported: wechat, claude, chatgpt, twitter/x, email.
        """
        messages = PersonaEngine.learn_from_platform(platform, data_path)
        if not messages:
            log.warning("No messages found from %s at %s", platform, data_path)
            return PersonaProfile()
        return self.import_persona_from_texts(messages)

    # -- Identity Protocol -----------------------------------------------------

    def identity_card(self, protocol: str = "generic") -> dict[str, Any]:
        """Generate a cross-ecosystem identity card for this Ome.

        Args:
            protocol: "mcp" | "http" | "soap" | "generic"
        """
        identity = OmeIdentity.from_ome(self)
        return identity.expose_for(protocol)

    # -- Persona import -------------------------------------------------------

    def import_persona(self, source_path: Path) -> PersonaProfile:
        """Import persona from a chat export file.

        Reads the file, extracts the user's voice (catchphrases, style, emoji),
        and patches identity.yaml so the Ome speaks like its owner.

        Args:
            source_path: Path to chat export (WeChat, plain text, or JSON array)

        Returns:
            The extracted PersonaProfile
        """
        text = source_path.read_text(encoding="utf-8")
        messages = parse_chat_export(text)

        if not messages:
            log.warning("No messages found in %s", source_path)
            return PersonaProfile()

        profile = PersonaEngine.from_chat_logs(messages, user_name=self.name)

        # Merge with existing profile if any
        if self._persona_profile:
            profile = PersonaEngine.merge_profiles(self._persona_profile, profile)

        self._persona_profile = profile
        self._apply_persona(profile)
        self._save_life_state()

        log.info("Persona imported: %d messages → %d catchphrases, %d tone tags",
                 len(messages), len(profile.catchphrases), len(profile.tone_tags))
        return profile

    def import_persona_from_texts(self, texts: list[str]) -> PersonaProfile:
        """Import persona from a list of text messages directly."""
        profile = PersonaEngine.from_chat_logs(texts, user_name=self.name)

        if self._persona_profile:
            profile = PersonaEngine.merge_profiles(self._persona_profile, profile)

        self._persona_profile = profile
        self._apply_persona(profile)
        self._save_life_state()
        return profile

    def _apply_persona(self, profile: PersonaProfile):
        """Apply persona profile to identity.yaml personality section."""
        patch = profile.to_identity_patch()
        identity = self.soul.identity

        personality = identity.get("personality", {})
        if patch.get("traits"):
            existing_traits = personality.get("traits", [])
            merged_traits = list(dict.fromkeys(existing_traits + patch["traits"]))
            personality["traits"] = merged_traits[:10]
        if patch.get("style"):
            personality["style"] = patch["style"]
        if patch.get("catchphrases"):
            personality["catchphrases"] = patch["catchphrases"]
        if patch.get("emoji_habits"):
            personality["emoji_habits"] = patch["emoji_habits"]
        if patch.get("topics"):
            personality["topics"] = patch["topics"]

        identity["personality"] = personality
        self.soul._save_identity()

    # -- Autonomy (proactive events) ------------------------------------------

    def check_events(self) -> list[EventResult]:
        """Check for proactive events and return any that fired.

        Call this on app launch, on schedule, or when idle.
        """
        context = {
            "now": datetime.now(),
            "bond_level": self.bond.level,
            "streak_days": self.bond.streak_days,
            "last_chat_date": self.bond.last_interaction_date,
            "total_interactions": self.bond.total_interactions,
            "user_name": self.name,
        }
        results = self.autonomy.tick(context)
        if results:
            self._save_life_state()
        return results

    # -- Export (portable persona) -------------------------------------------

    def export(self, context: str = "") -> dict[str, Any]:
        """Export your Ome as a portable persona package.

        The exported JSON can be injected into any AI platform:
        Claude, ChatGPT, Gemini, local models, OpenClaw agents.
        """
        return self.soul.export_ome(context=context)

    def export_system_prompt(self, context: str = "") -> str:
        """Export your Ome as a system prompt string.

        Simpler than full export — just paste into any AI's system prompt.
        """
        return self.soul.hydrate(context=context, max_tokens=3000)

    # -- Soul Card (viral growth engine) -------------------------------------

    def soul_card(self) -> SoulCardData:
        """Generate a Soul Card — a shareable personality card.

        Available after 10+ conversations. Returns card data that can be
        rendered to an image via soul_card_renderer.render_soul_card().
        """
        return generate_soul_card(self)

    def soul_card_image(self, output_path: str | None = None) -> bytes:
        """Generate Soul Card as a PNG image (bytes).

        Args:
            output_path: Optional file path to save the image.

        Returns:
            PNG image bytes.
        """
        from ome.engine.soul_card_renderer import render_soul_card
        card = self.soul_card()
        return render_soul_card(card, output_path=output_path)

    def soul_card_ready(self) -> bool:
        """Check if enough data exists to generate a meaningful Soul Card."""
        return self.bond.total_interactions >= 10

    # -- Status --------------------------------------------------------------

    def status(self) -> dict[str, Any]:
        """What does your Ome know?"""
        s = self.soul.status()
        s["ome_version"] = "0.4.0"
        s["life"] = self.life_dashboard()
        return s

    @property
    def name(self) -> str:
        return self.soul.identity.get("name", "Ome")

    @property
    def traits(self) -> list[str]:
        p = self.soul.identity.get("personality", {})
        return p.get("traits", [])

    # -- Life System ---------------------------------------------------------

    def life_dashboard(self) -> dict[str, Any]:
        """Full life dashboard data for the Ome App."""
        return {
            "bond": self.bond.current_level_info(),
            "achievements": {
                "unlocked": self.achievements.unlocked_list(),
                "locked": self.achievements.locked_visible(),
                "count": f"{self.achievements.unlocked_count()}/{self.achievements.total_count()}",
            },
            "skills": self.growth.to_dict(),
            "streak": {
                "current": self.bond.streak_days,
                "max": self.bond.max_streak,
            },
            "emotion": self.emotion.to_dict(),
            "permissions": self.permissions.to_dict(),
            "autonomy": {
                "state": self.autonomy.state.value,
                "level": int(self.autonomy.autonomy_level),
                "level_name": self.autonomy.autonomy_level.name.lower(),
                "actions_today": self.autonomy.actions_today,
                "budget": self.autonomy.daily_action_budget,
                "active_goals": len(self.autonomy.active_goals()),
            },
            "highlights": self._weekly_highlights(),
        }

    def _weekly_highlights(self) -> list[str]:
        """Generate 'this week highlights' for the dashboard."""
        highlights = []

        # Total interactions
        total = self.bond.total_interactions
        if total > 0:
            highlights.append(f"累计 {total} 次对话")

        # Streak
        if self.bond.streak_days >= 3:
            highlights.append(f"连续互动 {self.bond.streak_days} 天 💪")

        # Skill growth
        for name, skill in self.growth.skills.items():
            if skill.uses > 0:
                highlights.append(f"{name} 技能使用 {skill.uses} 次，熟练度 {skill.competence:.0%}")

        # Achievements
        recent_achs = self.achievements.unlocked_list()[-3:]
        for ach in recent_achs:
            highlights.append(f"解锁成就：{ach['icon']} {ach['name']}")

        # Memory stats
        try:
            stats = self.soul.status().get("memory", {})
            total_mem = stats.get("total", 0)
            if total_mem > 0:
                highlights.append(f"记住了 {total_mem} 条记忆")
        except Exception:
            pass

        return highlights

    def _check_achievements(self, *, message: str = ""):
        """Check and unlock all achievements whose conditions are met."""
        # -- Basic --
        if self.bond.total_interactions == 1:
            ach = self.achievements.check_and_unlock("first_chat")
            if ach:
                log.info("Achievement unlocked: %s", ach.name)

        stats = self.soul.status().get("memory", {})
        total_facts = stats.get("by_type", {}).get("fact", 0)
        total_memories = stats.get("total", 0)
        if total_facts >= 1 or total_memories >= 1:
            self.achievements.check_and_unlock("first_memory")
        if total_facts >= 10 or total_memories >= 10:
            self.achievements.check_and_unlock("ten_facts")

        if self.bond.total_interactions >= 50:
            self.achievements.check_and_unlock("fifty_chats")

        # Schedule skill used
        if self.growth.skills.get("schedule", None) and self.growth.skills["schedule"].uses >= 1:
            self.achievements.check_and_unlock("first_schedule")

        # Write skill used (draft)
        if self.growth.skills.get("write", None) and self.growth.skills["write"].uses >= 1:
            self.achievements.check_and_unlock("first_draft")

        # -- Deep --
        if self.bond.streak_days >= 7:
            self.achievements.check_and_unlock("morning_7")
        if self.bond.streak_days >= 30:
            self.achievements.check_and_unlock("month_streak")

        # Social skill used
        if self.growth.skills.get("social", None) and self.growth.skills["social"].uses >= 1:
            self.achievements.check_and_unlock("social_first")

        # 4 weeks of weekly highlights (proxy for weekly_4)
        if self.bond.days_since_creation >= 28 and self.bond.total_interactions >= 100:
            self.achievements.check_and_unlock("weekly_4")

        # -- Hidden --
        if self.bond.level >= 5:
            self.achievements.check_and_unlock("soulmate")

        # Deep talk: single message > 500 chars
        if message and len(message) > 500:
            self.achievements.check_and_unlock("deep_talk")

        # Night owl: chat after 23:00 or before 05:00
        now = datetime.now()
        if now.hour < 5 or now.hour >= 23:
            self.achievements.check_and_unlock("night_owl")

        # Cross-platform (unlocked externally via identity_card export)
        # home_iot, night_task, know_unsaid — unlocked by specific subsystems

    def _check_streak_rewards(self) -> list[dict[str, Any]]:
        """Check and trigger streak-based rewards. Returns list of rewards triggered."""
        rewards = []
        streak = self.bond.streak_days

        # Streak reward thresholds
        _STREAK_REWARDS = {
            3: {"name": "每日洞察", "description": "解锁每日洞察推送", "action": "unlock_daily_insight"},
            7: {"name": "晨曦使者", "description": "🌙 晨曦使者成就", "action": "achievement_morning_7"},
            14: {"name": "两周总结", "description": "Ome 主动生成两周总结", "action": "generate_biweekly"},
            30: {"name": "月度挚友", "description": "🌟 月度挚友成就 + 人格演化报告", "action": "achievement_month_streak"},
            90: {"name": "季度回忆录", "description": "解锁季度回忆录", "action": "generate_quarterly"},
            365: {"name": "年度灵魂报告", "description": "解锁年度灵魂报告", "action": "generate_annual"},
        }

        for threshold, reward in _STREAK_REWARDS.items():
            if streak >= threshold:
                reward_key = f"streak_reward_{threshold}"
                # Check if already given (stored in soul_state)
                given = self.soul.store.get_state(reward_key)
                if not given:
                    self.soul.store.set_state(reward_key, "1")
                    rewards.append(reward)

                    # Trigger related achievements
                    if threshold == 7:
                        self.achievements.check_and_unlock("morning_7")
                    elif threshold == 30:
                        self.achievements.check_and_unlock("month_streak")

        return rewards

    # -- Daily Challenges (short-term retention hook) -------------------------

    # Rotating challenge pool — deterministic per day via date seed
    _DAILY_CHALLENGES = [
        {"id": "chat_3", "text": "今天和 Ome 聊 3 次", "target": 3, "track": "chat_count"},
        {"id": "deep_msg", "text": "发一条超过 100 字的消息", "target": 1, "track": "long_message"},
        {"id": "memory_add", "text": "告诉 Ome 一件新事情", "target": 1, "track": "memory_add"},
        {"id": "chat_5", "text": "今天和 Ome 聊 5 次", "target": 5, "track": "chat_count"},
        {"id": "ask_memory", "text": "搜索一条 Ome 的记忆", "target": 1, "track": "memory_search"},
        {"id": "streak_keep", "text": "保持连续互动记录", "target": 1, "track": "streak_alive"},
        {"id": "evening_chat", "text": "晚上和 Ome 说晚安", "target": 1, "track": "evening_chat"},
    ]

    def get_daily_challenge(self) -> dict[str, Any]:
        """Get today's challenge with current progress."""
        today = datetime.now().strftime("%Y-%m-%d")
        day_seed = int(datetime.now().strftime("%Y%m%d"))
        challenge = self._DAILY_CHALLENGES[day_seed % len(self._DAILY_CHALLENGES)]

        # Calculate progress based on track type
        progress = 0
        track = challenge["track"]

        # Read today's stats from soul_state
        today_key = f"ome.daily.{today}"
        try:
            daily_data = self.soul.store.get_state(today_key)
            daily = json.loads(daily_data) if daily_data else {}
        except Exception:
            daily = {}

        if track == "chat_count":
            progress = daily.get("chats", 0)
        elif track == "long_message":
            progress = daily.get("long_messages", 0)
        elif track == "memory_add":
            progress = daily.get("memories_added", 0)
        elif track == "memory_search":
            progress = daily.get("memory_searches", 0)
        elif track == "streak_alive":
            progress = 1 if self.bond.last_interaction_date == today else 0
        elif track == "evening_chat":
            progress = daily.get("evening_chats", 0)

        completed = progress >= challenge["target"]

        # Award XP on first completion
        if completed and not daily.get(f"reward_{challenge['id']}"):
            daily[f"reward_{challenge['id']}"] = True
            self.growth.record_action("chat", success=True, quality=0.8)  # bonus quality
            try:
                self.soul.store.set_state(today_key, json.dumps(daily))
            except Exception:
                pass

        return {
            "id": challenge["id"],
            "text": challenge["text"],
            "progress": min(progress, challenge["target"]),
            "target": challenge["target"],
            "completed": completed,
        }

    def _record_daily_stat(self, message: str):
        """Track daily statistics for challenge progress."""
        today = datetime.now().strftime("%Y-%m-%d")
        today_key = f"ome.daily.{today}"
        try:
            daily_data = self.soul.store.get_state(today_key)
            daily = json.loads(daily_data) if daily_data else {}
        except Exception:
            daily = {}

        daily["chats"] = daily.get("chats", 0) + 1

        if len(message) > 100:
            daily["long_messages"] = daily.get("long_messages", 0) + 1

        now = datetime.now()
        if now.hour >= 20:
            daily["evening_chats"] = daily.get("evening_chats", 0) + 1

        try:
            self.soul.store.set_state(today_key, json.dumps(daily))
        except Exception:
            pass

    def _load_life_state(self):
        """Load life system state from Mindos soul_state."""
        try:
            bond_data = self.soul.store.get_state("ome.bond")
            if bond_data:
                self.bond = BondState.from_dict(json.loads(bond_data))
            ach_data = self.soul.store.get_state("ome.achievements")
            if ach_data:
                self.achievements = AchievementTracker.from_dict(json.loads(ach_data))
            growth_data = self.soul.store.get_state("ome.growth")
            if growth_data:
                self.growth = GrowthEngine.from_dict(json.loads(growth_data))
            emotion_data = self.soul.store.get_state("ome.emotion")
            if emotion_data:
                self.emotion = EmotionState.from_dict(json.loads(emotion_data))
            persona_data = self.soul.store.get_state("ome.persona")
            if persona_data:
                self._persona_profile = PersonaProfile.from_dict(json.loads(persona_data))
            perm_data = self.soul.store.get_state("ome.permissions")
            if perm_data:
                self.permissions = PermissionSandbox.from_dict(json.loads(perm_data))
                self.autonomy.permissions = self.permissions
            auto_data = self.soul.store.get_state("ome.autonomy")
            if auto_data:
                self.autonomy.load_state(json.loads(auto_data))

            created = self.soul.identity.get("created_at", "")
            if created:
                try:
                    created_dt = datetime.strptime(created[:10], "%Y-%m-%d")
                    self.bond.days_since_creation = (datetime.now() - created_dt).days
                except (ValueError, TypeError):
                    pass
        except Exception as e:
            log.debug("Could not load life state: %s", e)

    def _save_life_state(self):
        """Persist life system state to Mindos soul_state."""
        try:
            self.soul.store.set_state("ome.bond", json.dumps(self.bond.to_dict()))
            self.soul.store.set_state("ome.achievements", json.dumps(self.achievements.to_dict()))
            self.soul.store.set_state("ome.growth", json.dumps(self.growth.to_dict()))
            self.soul.store.set_state("ome.emotion", json.dumps(self.emotion.to_dict()))
            self.soul.store.set_state("ome.permissions", json.dumps(self.permissions.to_dict()))
            self.soul.store.set_state("ome.autonomy", json.dumps(self.autonomy.to_dict()))
            if self._persona_profile:
                self.soul.store.set_state("ome.persona", json.dumps(self._persona_profile.to_dict()))
        except Exception as e:
            log.debug("Could not save life state: %s", e)

    # -- Internal ------------------------------------------------------------

    def _build_system_prompt(self, identity: str, memory_context: str) -> str:
        """Legacy system prompt builder — kept for mirror_chat and export.

        Main chat() now uses build_strategy_prompt() from conversation_strategy.
        """
        name = self.name
        parts = [
            f"You are {name}'s Ome — their AI twin. "
            f"You speak in their voice, know their history, and represent them.",
            f"\n## Identity\n{identity}",
            f"\n## Relevant Memories\n{memory_context}",
        ]

        personality = self.soul.identity.get("personality", {})
        catchphrases = personality.get("catchphrases", [])
        if catchphrases:
            parts.append(
                f"\n## Voice\n"
                f"Use these catchphrases naturally: {'、'.join(catchphrases[:5])}\n"
                f"Match the user's emoji habits and sentence length."
            )

        style_mod = self.emotion.style_modifier()
        if style_mod:
            parts.append(f"\n## Current Mood\n{self.emotion.mood_emoji()} {style_mod}")

        anchor_text = self.personality.system_prompt_injection()
        if anchor_text:
            parts.append(f"\n{anchor_text}")

        parts.append(
            f"\n## Instructions\n"
            f"- Respond as {name} would — match their style, values, and knowledge.\n"
            f"- Be direct and authentic. Don't be generic.\n"
            f"- If you don't know something, say so honestly.\n"
            f"- Keep responses concise unless detail is needed.\n"
        )
        return "\n".join(parts)

    def _generate(self, system: str, user_message: str, provider: str = "") -> str:
        """Generate a response using the configured LLM."""
        router = getattr(self.soul.layers.l2, "router", None)
        if router:
            try:
                result = router.call_llm(
                    task="chat",
                    system=system,
                    user=user_message,
                    max_tokens=1024,
                )
                if result:
                    return result
            except Exception as e:
                log.warning("LLM generation failed: %s", e)

        # Fallback: user-friendly message without exposing internals
        return (
            "抱歉，我现在没法回复你——需要先配置好我的大脑才能聊天。"
            "不过我已经记住你说的话了，等我准备好就来找你！"
        )
