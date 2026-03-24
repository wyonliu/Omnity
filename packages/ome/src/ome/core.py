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
from ome.life.emotion import EmotionState
from ome.life.persona import PersonaEngine, PersonaProfile, parse_chat_export
from ome.engine.autonomy import AutonomyEngine, EventResult
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

        1. Recalls relevant memories based on your message
        2. Assembles identity + context + emotion
        3. Generates a response (via LLM)
        4. Commits the exchange to long-term memory
        5. Updates life state (bond, achievements, skills, emotion)

        Returns the Ome's response text.
        """
        # Update emotion from user message
        self.emotion.update_from_message(message)

        memories = self.soul.recall(message, top_k=5)
        memory_context = "\n".join(
            f"- [{m.get('type', '?')}] {m.get('content', '')}"
            for m in memories
        ) if memories else "(no relevant memories yet)"

        identity = self.soul.hydrate(context=message, max_tokens=1500)
        system_prompt = self._build_system_prompt(identity, memory_context)
        reply = self._generate(system_prompt, message, provider)

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

        # Check time-based achievements
        now = datetime.now()
        if now.hour < 5 or now.hour >= 23:
            self.achievements.check_and_unlock("night_owl")

        self._check_achievements(message=message)
        streak_rewards = self._check_streak_rewards()
        self._save_life_state()

        # Append streak reward messages
        for reward in streak_rewards:
            reply += f"\n\n🎁 {reward['name']}：{reward['description']}"

        if level_result.get("level_changed"):
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
        return self.soul.commit(f"user: {text}", source=source)

    def recall(self, query: str, top_k: int = 10) -> list[dict[str, Any]]:
        """Ask your Ome what it remembers about a topic."""
        self.growth.record_action("recall", success=True, quality=0.5)
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
        """Check and unlock any newly earned achievements."""
        if self.bond.total_interactions == 1:
            ach = self.achievements.check_and_unlock("first_chat")
            if ach:
                log.info("Achievement unlocked: %s", ach.name)

        stats = self.soul.status().get("memory", {})
        total_facts = stats.get("by_type", {}).get("fact", 0)
        if total_facts >= 1 and "first_memory" not in self.achievements.unlocked:
            self.achievements.check_and_unlock("first_memory")
        if total_facts >= 10 and "ten_facts" not in self.achievements.unlocked:
            self.achievements.check_and_unlock("ten_facts")

        if self.bond.total_interactions >= 50:
            self.achievements.check_and_unlock("fifty_chats")

        if self.bond.streak_days >= 7:
            self.achievements.check_and_unlock("morning_7")
        if self.bond.streak_days >= 30:
            self.achievements.check_and_unlock("month_streak")

        if self.bond.level >= 5:
            self.achievements.check_and_unlock("soulmate")

        # Deep talk: single message > 500 chars
        if message and len(message) > 500:
            self.achievements.check_and_unlock("deep_talk")

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
        """Assemble the system prompt for chat."""
        name = self.name
        parts = [
            f"You are {name}'s Ome — their AI twin. "
            f"You speak in their voice, know their history, and represent them.",
            f"\n## Identity\n{identity}",
            f"\n## Relevant Memories\n{memory_context}",
        ]

        # Inject persona catchphrases if available
        personality = self.soul.identity.get("personality", {})
        catchphrases = personality.get("catchphrases", [])
        if catchphrases:
            parts.append(
                f"\n## Voice\n"
                f"Use these catchphrases naturally: {'、'.join(catchphrases[:5])}\n"
                f"Match the user's emoji habits and sentence length."
            )

        # Inject emotion-based style modifier
        style_mod = self.emotion.style_modifier()
        if style_mod:
            parts.append(f"\n## Current Mood\n{self.emotion.mood_emoji()} {style_mod}")

        # Inject personality anchors/boundaries as hard constraints
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

        # Fallback: return a helpful message instead of crashing
        return (
            f"[Ome needs an LLM to chat. "
            f"Set DEEPSEEK_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY "
            f"in your environment, then try again.]\n\n"
            f"In the meantime, I remembered what you said. "
            f"Try: ome recall \"{user_message[:30]}...\""
        )
