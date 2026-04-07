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
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from mindos.core import Mindos

from ome.life.bond import BondState
from ome.life.achievements import AchievementTracker
from ome.life.growth import GrowthEngine
from ome.life.emotion import EmotionState, detect_crisis
from ome.life.stages import GrowthGate, Capability
from ome.life.maturity import MaturityScorer, MaturitySnapshot
from ome.life.persona import (
    PersonaEngine, PersonaProfile, PersonaDefinition,
    build_persona_emotion_prompt, parse_chat_export,
)
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
from ome.constants import (
    CHAT_HISTORY_MAX,
    CHAT_RECALL_TOP_K,
    CHAT_LOW_ENGAGEMENT_CHARS,
    CHAT_DEFAULT_QUALITY,
    CHAT_REMEMBER_QUALITY,
    FOLLOW_UP_COUNT,
    FOLLOW_UP_MAX_CHARS,
    FOLLOW_UP_MAX_LINE,
    PROMPT_COUNT as _PROMPT_COUNT,
    PROMPT_RECALL_K,
    PROMPT_MAX_CHARS,
    PROMPT_MAX_LINE,
    GREETING_RECALL_K,
    GREETING_MAX_CHARS,
    GREETING_MORNING_HOUR,
    GREETING_AFTERNOON_HOUR,
    RECALL_DEFAULT_TOP_K,
    RECALL_TYPE_FILTER_MULT,
    MEMORY_HEALTH_ACTIVE_WEIGHT,
    MEMORY_HEALTH_RECALL_WEIGHT,
    MEMORY_HEALTH_RECALL_NORM,
    EMOTION_HISTORY_DEFAULT_DAYS,
    EMOTION_HISTORY_MAX_DAYS,
    GROWTH_TIMELINE_DEFAULT_LIMIT,
    GROWTH_TIMELINE_MAX_EVENTS,
    ACHIEVEMENT_NOTES_THRESHOLD,
    ACHIEVEMENT_TASKS_THRESHOLD,
    ACHIEVEMENT_CONTACTS_THRESHOLD,
    ACHIEVEMENT_FIRST_MEMORY_COUNT,
    ACHIEVEMENT_TEN_FACTS_COUNT,
    ACHIEVEMENT_FIFTY_CHATS,
    ACHIEVEMENT_STREAK_7,
    ACHIEVEMENT_STREAK_30,
    ACHIEVEMENT_WEEKLY_4_DAYS,
    ACHIEVEMENT_WEEKLY_4_INTERACTIONS,
    ACHIEVEMENT_SOULMATE_LEVEL,
    ACHIEVEMENT_DEEP_TALK_CHARS,
    ACHIEVEMENT_NIGHT_OWL_EARLY,
    ACHIEVEMENT_NIGHT_OWL_LATE,
    STREAK_MILESTONES,
    STREAK_HIGHLIGHT_MIN,
    SOUL_CARD_MIN_INTERACTIONS,
    EVOLUTION_COMMITS_THRESHOLD,
    LLM_EXTRACT_MAX_TOKENS,
    LLM_GENERATION_MAX_TOKENS,
    LONG_MESSAGE_CHARS,
    EVENING_HOUR,
    BOND_TRUST_ASSISTANT_LEVEL,
    BOND_TRUST_DEPUTY_LEVEL,
)

log = logging.getLogger("ome")


def _synchronized(method):
    """Decorator: acquires self._lock (RLock) before calling the method."""
    from functools import wraps

    @wraps(method)
    def wrapper(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return wrapper


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
        self._lock = threading.RLock()
        self._chat_history: list[dict[str, str]] = []
        self.bond = BondState()
        self.achievements = AchievementTracker()
        self.growth = GrowthEngine()
        self.emotion = EmotionState()
        self.permissions = PermissionSandbox()
        self.autonomy = AutonomyEngine(permissions=self.permissions)
        self._persona_profile: Optional[PersonaProfile] = None
        self._persona_definition: Optional[PersonaDefinition] = None
        self.personality = PersonalityEngine(soul.identity)
        self.skill_registry = SkillRegistry()
        register_builtins(self.skill_registry)
        # v0.7: Growth stage gating + maturity scorer
        self.growth_gate = GrowthGate()
        self._maturity_scorer = MaturityScorer()
        self._load_life_state()

    # -- Context manager & cleanup -------------------------------------------

    def close(self) -> None:
        """Persist state and release resources."""
        self._save_life_state()
        if hasattr(self.soul, "close"):
            self.soul.close()

    def __enter__(self) -> "Ome":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def _cap_chat_history(self) -> None:
        """Trim in-memory chat history to *CHAT_HISTORY_MAX* messages."""
        if len(self._chat_history) > CHAT_HISTORY_MAX:
            self._chat_history = self._chat_history[-CHAT_HISTORY_MAX:]

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

    @contextmanager
    def locked(self):
        """Context manager for thread-safe access in multi-worker setups.

        Usage:
            with ome.locked():
                result = ome.chat_rich(msg)
                # ... other operations that must be atomic
        """
        with self._lock:
            yield self

    # -- Chat (the main interface) -------------------------------------------

    @_synchronized
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
        is_low_engagement = len(stripped) <= CHAT_LOW_ENGAGEMENT_CHARS and not any(
            c in stripped for c in "？?！!…"
        )

        # Recall and classify memories
        memories = self.soul.recall(message, top_k=CHAT_RECALL_TOP_K)
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

        # Build persona + emotion section for soulful responses
        persona_section = build_persona_emotion_prompt(
            persona=self._persona_definition,
            emotion_state=self.emotion,
        )

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
            persona_prompt_section=persona_section,
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
        self.growth.record_action("chat", success=True, quality=CHAT_DEFAULT_QUALITY)

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
        self._save_emotion_snapshot()

        # Record growth events
        if self.bond.total_interactions == 1:
            self._record_growth_event("first_chat", "破冰 🌱", "我们的故事开始了")
        if level_result.get("level_changed"):
            lvl = level_result["new_level"]
            lvl_name = level_result["level_name"]
            self._record_growth_event(
                f"bond_up_{lvl}", f"羁绊升级 ✨", f"升级到「{lvl_name}」"
            )

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
            if new_level >= BOND_TRUST_ASSISTANT_LEVEL:
                self.permissions.raise_trust(TrustLevel.ASSISTANT)
            if new_level >= BOND_TRUST_DEPUTY_LEVEL:
                self.permissions.raise_trust(TrustLevel.DEPUTY)

        self._cap_chat_history()
        return reply

    @_synchronized
    def chat_rich(self, message: str, provider: str = "") -> dict[str, Any]:
        """Like chat(), but returns a rich dict with memories recalled, thinking, etc.

        This is the preferred API for Ome365 and other apps that need to display
        "记忆命中" (which memories were recalled) alongside the reply.

        Returns:
            {
                "reply": str,           # The Ome's response text
                "memories_recalled": [   # Which memories were used (for "记忆命中" display)
                    {"type": "fact", "content": "用户住在上海", "score": 0.85},
                    ...
                ],
                "emotion": {...},        # Current emotion state
                "bond": {...},           # Current bond level info
                "evolution_pending": bool,  # Whether L4 reflection is ready to trigger
                "phase": {...},          # Current growth phase
                "thinking": {...} | None,  # LLM's internal reasoning (if available)
            }
        """
        # L0 keyword emotion (fast fallback, always runs)
        self.emotion.update_from_message(message)

        # Crisis detection
        is_crisis = detect_crisis(message)

        # Low-engagement detection
        stripped = message.strip()
        is_low_engagement = len(stripped) <= CHAT_LOW_ENGAGEMENT_CHARS and not any(
            c in stripped for c in "？?！!…"
        )

        # Recall and classify memories
        memories = self.soul.recall(message, top_k=CHAT_RECALL_TOP_K)
        classified = classify_memories(memories) if memories else []
        memory_context = "\n".join(
            f"- [{m.get('type', '?')}] {m.get('content', '')}"
            for m in memories
        ) if memories else "(no relevant memories yet)"

        # Build memories_recalled for the response
        memories_recalled = []
        for m in (memories or []):
            memories_recalled.append({
                "type": m.get("type", "unknown"),
                "content": m.get("content", ""),
                "created_at": m.get("created_at", ""),
                "source": m.get("source", ""),
            })

        # Determine growth phase
        phase = get_growth_phase(self.bond.total_interactions)

        # Build strategy-aware system prompt
        identity = self.soul.hydrate(context=message, max_tokens=1500)
        personality = self.soul.identity.get("personality", {})
        catchphrases = personality.get("catchphrases", [])
        anchor_text = self.personality.system_prompt_injection()

        persona_section = build_persona_emotion_prompt(
            persona=self._persona_definition,
            emotion_state=self.emotion,
        )

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
            persona_prompt_section=persona_section,
        )

        # Generate
        raw_reply = self._generate(system_prompt, message, provider)

        # Parse thinking block
        reply, thinking = parse_response(raw_reply)

        # L1 deep emotion update from LLM's assessment
        thinking_dict = None
        if thinking:
            self.emotion.update_from_llm_thinking(
                emotion=thinking.emotion,
                nuance=thinking.emotion_nuance,
            )
            if thinking.persona_markers and self._persona_profile:
                self._persona_profile = PersonaEngine.evolve_from_markers(
                    self._persona_profile,
                    thinking.persona_markers,
                )
            elif thinking.persona_markers and not self._persona_profile:
                from ome.life.persona import PersonaProfile as PP
                self._persona_profile = PP(raw_traits=thinking.persona_markers[:5])
            thinking_dict = {
                "emotion": thinking.emotion,
                "emotion_nuance": thinking.emotion_nuance,
                "persona_markers": thinking.persona_markers,
            }

        # Validate response against personality
        ok, reply = self.personality.validate(reply, context=message)

        conversation = f"user: {message}\nassistant: {reply}"
        self._chat_history.append({"role": "user", "content": message})
        self._chat_history.append({"role": "assistant", "content": reply})

        # Commit to memory and capture memory_impact
        memory_impact: dict[str, Any] = {"facts_added": 0, "facts": []}
        try:
            commit_result = self.soul.commit(conversation, source="ome-chat")
            if isinstance(commit_result, dict):
                added = commit_result.get("facts_added", 0)
                if added:
                    memory_impact["facts_added"] = added
                    # Retrieve recently added facts for display
                    recent = self.soul.store.list_recent(limit=added, mem_type="fact")
                    memory_impact["facts"] = [m.content for m in recent]
        except Exception as e:
            log.warning("Failed to commit chat: %s", e)

        today = datetime.now().strftime("%Y-%m-%d")
        level_result = self.bond.record_interaction(today)
        self.growth.record_action("chat", success=True, quality=CHAT_DEFAULT_QUALITY)

        # Record growth events
        if self.bond.total_interactions == 1:
            self._record_growth_event("first_chat", "破冰 🌱", "我们的故事开始了")
        if level_result.get("level_changed"):
            lvl = level_result["new_level"]
            lvl_name = level_result["level_name"]
            self._record_growth_event(
                f"bond_up_{lvl}", f"羁绊升级 ✨", f"升级到「{lvl_name}」"
            )

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

        self._record_daily_stat(message)
        self._save_emotion_snapshot()

        suppress_gamification = is_crisis or (
            self.emotion.mood in ("sad", "stressed") and is_low_engagement
        )
        self._check_achievements(message=message)

        # Record achievement events
        newly_unlocked = self.achievements.unlocked_list()
        if newly_unlocked:
            last = newly_unlocked[-1]
            self._record_growth_event(
                f"achievement_{last['id']}", f"{last['icon']} {last['name']}",
                last.get("description", ""),
            )

        # Record streak milestones
        streak = self.bond.streak_days
        for threshold in STREAK_MILESTONES:
            if streak == threshold:
                self._record_growth_event(
                    f"streak_{threshold}", f"{threshold}日连续 🔥", ""
                )

        streak_rewards = self._check_streak_rewards() if not suppress_gamification else []
        self._save_life_state()

        if not suppress_gamification:
            for reward in streak_rewards:
                reply += f"\n\n🎁 {reward['name']}：{reward['description']}"

        if level_result.get("level_changed") and not suppress_gamification:
            lvl_name = level_result["level_name"]
            new_level = level_result["new_level"]
            reply += f"\n\n✨ 我们的关系升级了：{lvl_name}！"
            if new_level >= BOND_TRUST_ASSISTANT_LEVEL:
                self.permissions.raise_trust(TrustLevel.ASSISTANT)
            if new_level >= BOND_TRUST_DEPUTY_LEVEL:
                self.permissions.raise_trust(TrustLevel.DEPUTY)

        # Generate follow-up suggestions (async-friendly, non-blocking)
        follow_ups: list[str] = []
        try:
            follow_ups = self.suggest_follow_ups(message, reply, count=FOLLOW_UP_COUNT)
        except Exception:
            pass

        self._cap_chat_history()
        return {
            "reply": reply,
            "memories_recalled": memories_recalled,
            "emotion": self.emotion.to_dict(),
            "bond": self.bond.current_level_info(),
            "evolution_pending": self.evolution_pending,
            "phase": phase,
            "thinking": thinking_dict,
            # --- New fields ---
            "follow_ups": follow_ups,
            "memory_impact": memory_impact,
        }

    # -- Evolution (L4 self-reflection on demand) ------------------------------

    @property
    def evolution_pending(self) -> bool:
        """Whether enough commits have accumulated for L4 self-reflection.

        Returns True when ≥ 20 commits since last reflection.
        Use evolve() to trigger it.
        """
        l4 = self.soul.layers.l4
        return l4._commit_count_since_reflect >= EVOLUTION_COMMITS_THRESHOLD

    @property
    def commits_since_reflection(self) -> int:
        """Number of commits since last L4 reflection."""
        return self.soul.layers.l4._commit_count_since_reflect

    @_synchronized
    def evolve(self) -> dict[str, Any]:
        """Trigger L4 self-reflection on demand.

        Returns the reflection result including:
        - summary: what was reflected on
        - drift_detected: whether personality drift was found
        - new_traits_observed: any new traits emerging
        - method: "llm" or "heuristic"

        For POST /api/growth/evolve — Ome365 can call this when user taps "evolve".
        """
        result = self.soul.reflect()
        if result is None:
            result = {
                "summary": "No episodes to reflect on yet.",
                "drift_detected": None,
                "method": "skipped",
            }
        self._save_life_state()
        return result

    # -- Smart extraction (structured data from text) --------------------------

    @_synchronized
    def smart_extract(self, text: str) -> dict[str, Any]:
        """Extract structured data (contacts, tasks, notes) from natural language.

        For POST /api/ai/smart-input — AI-powered extraction for quick entry.

        Returns:
            {
                "contacts": [{"name": "...", "info": "..."}],
                "tasks": [{"title": "...", "due": "...", "priority": "..."}],
                "notes": [{"content": "..."}],
                "raw_facts": ["...", "..."],  # Mindos L2 extracted facts
            }
        """
        router = getattr(self.soul.layers.l2, "router", None)
        if router is None:
            # No LLM — use regex-based extraction
            contacts, tasks, notes = self._regex_extract(text)
            result = self.soul.commit(f"user: {text}", source="smart-input")
            if not notes and not contacts and not tasks:
                notes = [{"content": text}]
            return {
                "contacts": contacts,
                "tasks": tasks,
                "notes": notes,
                "raw_facts": result.get("facts", []),
            }

        system = (
            "你是一个信息提取助手。从用户输入中提取结构化数据。\n"
            "严格按JSON格式返回：\n"
            '{"contacts": [{"name": "姓名", "info": "电话/邮箱/关系"}], '
            '"tasks": [{"title": "任务描述", "due": "截止日期或空", "priority": "high/medium/low"}], '
            '"notes": [{"content": "备注内容"}]}\n'
            "如果某类没有数据，返回空数组。只返回JSON，不要其他文字。"
        )

        try:
            raw = router.call_llm(
                task="commit_digest",
                system=system,
                user=text,
                max_tokens=LLM_EXTRACT_MAX_TOKENS,
                json_mode=True,
            )
            if raw:
                parsed = json.loads(raw)
                # Also commit to memory
                self.soul.commit(f"user: {text}", source="smart-input")
                return {
                    "contacts": parsed.get("contacts", []),
                    "tasks": parsed.get("tasks", []),
                    "notes": parsed.get("notes", []),
                    "raw_facts": [],
                }
        except (json.JSONDecodeError, Exception) as e:
            log.warning("smart_extract LLM parse failed: %s", e)

        # Fallback: regex extraction + commit to memory
        contacts, tasks, notes = self._regex_extract(text)
        result = self.soul.commit(f"user: {text}", source="smart-input")
        if not notes and not contacts and not tasks:
            notes = [{"content": text}]
        return {
            "contacts": contacts,
            "tasks": tasks,
            "notes": notes,
            "raw_facts": result.get("facts", []),
        }

    @staticmethod
    def _regex_extract(text: str) -> tuple[list, list, list]:
        """Basic regex extraction for contacts, tasks, notes without LLM."""
        import re
        contacts = []
        tasks = []
        notes = []

        # Phone numbers (CN mobile: 1xx-xxxx-xxxx)
        phones = re.findall(r'(1[3-9]\d{9})', text)
        # Email
        emails = re.findall(r'([\w.+-]+@[\w-]+\.[\w.-]+)', text)
        # Chinese names near phone/email (2-4 chars before a phone/contact keyword)
        name_patterns = re.findall(r'([\u4e00-\u9fff]{2,4})(?:的?(?:电话|手机|号码|邮箱|微信|联系))', text)

        if phones or emails:
            info_parts = phones + emails
            name = name_patterns[0] if name_patterns else ""
            contacts.append({"name": name, "info": ", ".join(info_parts)})

        # Time-related tasks (明天/后天/下午/X点/X号/周X)
        time_keywords = re.findall(
            r'((?:明天|后天|今天|下周|周[一二三四五六日]|'
            r'\d{1,2}[.:：]\d{2}|\d{1,2}[点时](?:半)?|'
            r'\d{1,2}月\d{1,2}[日号]|[上下]午)'
            r'[^，。；\n]{0,30})',
            text,
        )
        # Task action keywords
        task_actions = re.findall(
            r'(?:提醒我?|记得|别忘了?|要|需要|去)([\u4e00-\u9fff\w\s]{2,20})',
            text,
        )
        if time_keywords:
            for tk in time_keywords:
                tasks.append({"title": tk.strip(), "due": "", "priority": "medium"})
        elif task_actions:
            for ta in task_actions:
                tasks.append({"title": ta.strip(), "due": "", "priority": "medium"})

        return contacts, tasks, notes

    def suggest_follow_ups(self, user_msg: str, ome_reply: str, count: int = FOLLOW_UP_COUNT) -> list[str]:
        """Generate contextual follow-up suggestions using LLM.

        Returns a list of short follow-up prompts the user might say next.
        Uses memory + emotion + bond state for personalization.
        """
        phase = get_growth_phase(self.bond.total_interactions)
        mood = self.emotion.mood

        system = (
            f"你是{self.name}的AI分身（Ome），正在和{self.name}聊天。\n"
            f"当前关系阶段：{phase['name']}，心情：{mood}。\n\n"
            f"刚刚的对话：\n"
            f"用户说：{user_msg}\n"
            f"你回复了：{ome_reply}\n\n"
            f"请生成{count}个用户可能想说的后续内容，作为快捷回复按钮。\n"
            f"要求：\n"
            f"- 每个不超过{FOLLOW_UP_MAX_CHARS}个字\n"
            f"- 自然、口语化，像发微信\n"
            f"- 至少一个是追问/深入，一个是肯定/共鸣\n"
            f"- 用中文\n"
            f"- 直接输出{count}行，每行一个，不要编号不要标点\n"
        )
        try:
            raw = self._generate(system, "生成跟进建议", "")
            lines = [l.strip() for l in raw.strip().split("\n") if l.strip()]
            # Clean: remove numbering, bullets, quotes
            clean = []
            for l in lines:
                l = l.lstrip("0123456789.、-·•\"'「」")
                l = l.strip()
                if l and len(l) <= FOLLOW_UP_MAX_LINE:
                    clean.append(l)
            return clean[:count]
        except Exception as e:
            log.warning("Failed to generate follow-ups: %s", e)
            return []

    def generate_prompts(self, count: int = _PROMPT_COUNT, context: str = "") -> list[str]:
        """Generate personalized conversation starters using LLM + memory.

        Returns prompts tailored to the user's history, mood, and growth phase.
        """
        phase = get_growth_phase(self.bond.total_interactions)
        mood = self.emotion.mood

        # Recall recent memories for context
        query = context if context else "最近发生的事"
        memories = self.soul.recall(query, top_k=PROMPT_RECALL_K)
        mem_summary = "\n".join(
            f"- {m.get('content', '')}" for m in (memories or [])
        )[:500]

        system = (
            f"你是{self.name}的AI分身（Ome），了解{self.name}的一切。\n"
            f"关系阶段：{phase['name']}（共{self.bond.total_interactions}次对话），心情：{mood}。\n"
            f"相关记忆：\n{mem_summary or '(暂无记忆)'}\n\n"
            f"请生成{count}个你想问{self.name}的问题或话题，作为今天的对话入口。\n"
            f"要求：\n"
            f"- 基于你对ta的了解，不要泛泛而谈\n"
            f"- 简短自然，像朋友发微信\n"
            f"- 每个一句话，不超过{PROMPT_MAX_CHARS}字\n"
            f"- 如果有记忆，至少一个要引用记忆中的细节\n"
            f"- 用中文\n"
            f"- 直接输出{count}行，每行一个，不要编号\n"
        )
        try:
            raw = self._generate(system, "生成今日话题", "")
            lines = [l.strip() for l in raw.strip().split("\n") if l.strip()]
            clean = []
            for l in lines:
                l = l.lstrip("0123456789.、-·•\"'「」")
                l = l.strip()
                if l and len(l) <= PROMPT_MAX_LINE:
                    clean.append(l)
            return clean[:count]
        except Exception as e:
            log.warning("Failed to generate prompts: %s", e)
            return []

    def generate_greeting(self) -> str:
        """Generate a personalized greeting using LLM + memory + time context."""
        phase = get_growth_phase(self.bond.total_interactions)
        mood = self.emotion.mood
        now = datetime.now()
        hour = now.hour
        time_hint = "早上" if hour < GREETING_MORNING_HOUR else ("下午" if hour < GREETING_AFTERNOON_HOUR else "晚上")
        streak = self.bond.streak_days

        # Grab recent memories for context
        memories = self.soul.recall("最近发生的事", top_k=GREETING_RECALL_K)
        mem_summary = "\n".join(
            f"- {m.get('content', '')}" for m in (memories or [])
        )[:300]

        system = (
            f"你是{self.name}的AI分身（Ome），现在是{time_hint}。\n"
            f"关系阶段：{phase['name']}（共{self.bond.total_interactions}次对话），"
            f"连续{streak}天，心情：{mood}。\n"
            f"相关记忆：\n{mem_summary or '(暂无记忆)'}\n\n"
            f"请用一两句话跟{self.name}打招呼。\n"
            f"要求：\n- 像老朋友发微信，温暖自然\n"
            f"- 如果有记忆，可以引用细节\n"
            f"- 根据时间和心情调整语气\n"
            f"- 不要超过{GREETING_MAX_CHARS}字\n- 用中文\n- 直接输出，不要编号\n"
        )
        try:
            raw = self._generate(system, "生成问候", "")
            # Clean up: take first line, strip quotes/punctuation artifacts
            line = raw.strip().split("\n")[0].strip()
            line = line.strip("\"'「」")
            return line if line else ""
        except Exception as e:
            log.warning("Failed to generate greeting: %s", e)
            return ""

    @_synchronized
    def remember(self, text: str, source: str = "manual") -> dict[str, Any]:
        """Teach your Ome something directly."""
        self.growth.record_action("recall", success=True, quality=CHAT_REMEMBER_QUALITY)
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
        # Manual/profile input is a fact, not conversation — store directly
        if source in ("manual", "profile", "api"):
            from mindos.store import Memory
            mem = Memory(id="", type="fact", content=text, source=source, confidence=0.9)
            self.soul.store.add(mem)
            return {"facts_added": 1, "method": "direct", "episode": ""}
        return self.soul.commit(f"user: {text}", source=source)

    @_synchronized
    def recall(self, query: str, top_k: int = RECALL_DEFAULT_TOP_K,
              type_filter: Optional[list[str]] = None) -> list[dict[str, Any]]:
        """Ask your Ome what it remembers about a topic.

        Args:
            query: Search query (empty string returns recent memories).
            top_k: Max results to return.
            type_filter: Optional list of memory types to include
                         (e.g. ["fact", "preference"]). None = all types.
        """
        self.growth.record_action("recall", success=True, quality=CHAT_DEFAULT_QUALITY)
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

        results = self.soul.recall(query, top_k=top_k * RECALL_TYPE_FILTER_MULT if type_filter else top_k)

        if type_filter:
            results = [m for m in results if m.get("type") in type_filter][:top_k]

        return results

    # -- Memory Stats ----------------------------------------------------------

    def memory_stats(self) -> dict[str, Any]:
        """Memory health dashboard — total, by_type, decay status, recent activity, health score.

        Returns:
            {
                "total": int,
                "by_type": {"fact": N, "episode": N, ...},
                "decay_status": {"active": N, "fading": N, "forgotten": N},
                "recent_7d": {"added": N, "recalled": N},
                "health": float  # 0-1 composite score
            }
        """
        store = self.soul.store
        basic = store.stats()
        total = basic["total_memories"]
        by_type = basic["by_type"]
        decay = store.decay_status()
        recent = store.count_recent(7)

        # Health score: active_ratio * weight + recall_frequency * weight
        active_ratio = decay["active"] / max(total, 1)
        recall_freq = min(recent["recalled"] / max(total, 1) * MEMORY_HEALTH_RECALL_NORM, 1.0)
        health = round(active_ratio * MEMORY_HEALTH_ACTIVE_WEIGHT + recall_freq * MEMORY_HEALTH_RECALL_WEIGHT, 2)

        return {
            "total": total,
            "by_type": by_type,
            "decay_status": decay,
            "recent_7d": recent,
            "health": health,
        }

    # -- Emotion History -------------------------------------------------------

    def emotion_history(self, days: int = EMOTION_HISTORY_DEFAULT_DAYS) -> list[dict[str, Any]]:
        """Emotion trace over the last N days.

        Returns list of daily snapshots (newest first):
            [{"date": "2026-04-07", "valence": 0.3, "arousal": 0.5,
              "mood": "curious", "energy": 0.7}, ...]
        """
        result = []
        raw = self.soul.store.get_state("ome.emotion_history")
        history: dict[str, dict] = json.loads(raw) if raw else {}

        # Include today's live state
        today = datetime.now().strftime("%Y-%m-%d")
        history[today] = {
            "valence": round(self.emotion.valence, 3),
            "arousal": round(self.emotion.arousal, 3),
            "mood": self.emotion.mood,
            "energy": round(self.emotion.energy, 2),
        }

        # Sort by date descending, limit to N days
        sorted_dates = sorted(history.keys(), reverse=True)[:days]
        for d in sorted_dates:
            entry = history[d]
            entry["date"] = d
            result.append(entry)

        return result

    # -- Growth Timeline -------------------------------------------------------

    def growth_timeline(self, limit: int = GROWTH_TIMELINE_DEFAULT_LIMIT) -> list[dict[str, Any]]:
        """Growth milestone event log — the soul of the nurture page.

        Returns list of events (newest first):
            [{"date": "2026-04-07 17:34", "event": "first_chat",
              "label": "破冰 🌱", "detail": "我们的故事开始了"}, ...]
        """
        raw = self.soul.store.get_state("ome.growth_timeline")
        events: list[dict] = json.loads(raw) if raw else []
        # Return newest first, limited
        return list(reversed(events[-limit:]))

    def _record_growth_event(self, event: str, label: str, detail: str = ""):
        """Append a growth event to the timeline."""
        raw = self.soul.store.get_state("ome.growth_timeline")
        events: list[dict] = json.loads(raw) if raw else []

        # Deduplicate by event type (some events only happen once)
        _UNIQUE_EVENTS = {"first_chat", "bond_up_1", "bond_up_2", "bond_up_3",
                          "bond_up_4", "bond_up_5", "bond_up_6"}
        if event in _UNIQUE_EVENTS:
            existing = {e["event"] for e in events}
            if event in existing:
                return

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        events.append({
            "date": now,
            "event": event,
            "label": label,
            "detail": detail,
        })

        # Keep last N events max
        if len(events) > GROWTH_TIMELINE_MAX_EVENTS:
            events = events[-GROWTH_TIMELINE_MAX_EVENTS:]

        self.soul.store.set_state("ome.growth_timeline", json.dumps(events, ensure_ascii=False))

    # -- External Stats Injection ----------------------------------------------

    def report_external_stats(self, stats: dict[str, Any]) -> dict[str, str]:
        """Inject vault / external metrics for achievement & growth calculations.

        Args:
            stats: Dict with keys like notes_count, tasks_done, tasks_total,
                   contacts_count, plan_pct, active_days, etc.

        Call this before life_dashboard() to keep Ome aware of external data.
        """
        self.soul.store.set_state("ome.external_stats", json.dumps(stats))

        # Check external-data-driven achievements
        notes = stats.get("notes_count", 0)
        tasks_done = stats.get("tasks_done", 0)
        contacts = stats.get("contacts_count", 0)

        if notes >= ACHIEVEMENT_NOTES_THRESHOLD:
            self.achievements.check_and_unlock("ten_facts")
        if tasks_done >= ACHIEVEMENT_TASKS_THRESHOLD:
            self.achievements.check_and_unlock("fifty_chats")  # repurpose as "50 tasks"
        if contacts >= ACHIEVEMENT_CONTACTS_THRESHOLD:
            self.achievements.check_and_unlock("social_first")

        self._save_life_state()
        return {"status": "ok"}

    def maturity(self) -> dict[str, Any]:
        """Compute the maturity score — read-only diagnostic of soul development.

        Returns:
            {"score": 0.0-1.0, "reflection_depth": ..., "memory_complexity": ...,
             "behavioral_consistency": ..., "label": "成长"}
        """
        # Gather inputs
        timeline = self.soul.store.personality_timeline()
        reflection_count = len(timeline)
        traits = self.soul.identity.get("personality", {}).get("traits", [])
        mem_stats = self.memory_stats()
        competences = [s.competence for s in self.growth.skills.values()]

        return self._maturity_scorer.score(
            reflection_count=reflection_count,
            trait_count=len(traits),
            memory_total=mem_stats["total"],
            memory_by_type=mem_stats["by_type"],
            streak_days=self.bond.streak_days,
            skill_competences=competences,
            total_interactions=self.bond.total_interactions,
        ).to_dict()

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
        self.growth.record_action("chat", success=True, quality=CHAT_REMEMBER_QUALITY)
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

    # -- Persona Definition (Phase 1: soulful persona) -------------------------

    def set_persona(self, persona: PersonaDefinition) -> None:
        """Set or replace the Ome's persona definition.

        The persona defines WHO the Ome is — background, personality,
        speaking style, values, quirks. It colors all future responses.
        """
        self._persona_definition = persona
        self._save_life_state()

    def set_builtin_persona(self, name: str) -> Optional[PersonaDefinition]:
        """Set persona from a built-in template by name.

        Available: 'warm_mentor', 'playful_creative', 'calm_philosopher'.
        Returns the PersonaDefinition if found, None otherwise.
        """
        from ome.life.persona import get_builtin_persona
        persona = get_builtin_persona(name)
        if persona:
            self._persona_definition = persona
            self._save_life_state()
        return persona

    @property
    def persona_definition(self) -> Optional[PersonaDefinition]:
        """Current persona definition, if set."""
        return self._persona_definition

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
        return self.bond.total_interactions >= SOUL_CARD_MIN_INTERACTIONS

    # -- Status --------------------------------------------------------------

    def status(self) -> dict[str, Any]:
        """What does your Ome know?"""
        s = self.soul.status()
        s["ome_version"] = "0.7.0"
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
        """Full life dashboard data for the Ome App.

        Enhanced with: daily_challenge, memory_stats, enriched phase,
        next_milestone — everything the nurture page needs in one call.
        """
        phase = get_growth_phase(self.bond.total_interactions)
        self.growth_gate.update_phase(phase.get("phase_id", 0))
        bond_info = self.bond.current_level_info()

        # Build next_milestone from bond + streak + achievements
        next_milestone = self._compute_next_milestone(bond_info)

        return {
            "bond": bond_info,
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
            # --- New fields for Ome365 v0.6 ---
            "daily_challenge": self.get_daily_challenge(),
            "memory_stats": self.memory_stats(),
            "phase": {
                "phase_id": phase.get("phase_id", 0),
                "name": phase.get("name", ""),
                "persona": phase.get("persona", ""),
                "strategy_hint": phase.get("strategy_hint", ""),
            },
            "next_milestone": next_milestone,
            # --- New fields for v0.7 ---
            "capabilities": self.growth_gate.to_dict(),
            "maturity": self.maturity(),
        }

    def _compute_next_milestone(self, bond_info: dict) -> dict[str, Any]:
        """Compute the nearest next milestone for the dashboard."""
        milestones = []

        # Bond level up
        interactions_needed = bond_info.get("interactions_needed", 0)
        next_level_name = bond_info.get("next_level", "")
        if next_level_name and interactions_needed > 0:
            total_for_next = interactions_needed + self.bond.total_interactions
            pct = int(self.bond.total_interactions / max(total_for_next, 1) * 100)
            milestones.append({
                "type": "bond_up",
                "label": f"升级到「{next_level_name}」",
                "progress_pct": min(pct, 99),
                "remaining": f"还需 {interactions_needed} 次互动",
            })

        # Streak milestones
        streak = self.bond.streak_days
        for target in STREAK_MILESTONES:
            if streak < target:
                pct = int(streak / target * 100)
                milestones.append({
                    "type": "streak",
                    "label": f"连续互动 {target} 天",
                    "progress_pct": min(pct, 99),
                    "remaining": f"还需 {target - streak} 天",
                })
                break

        # Next locked achievement
        locked = self.achievements.locked_visible()
        if locked:
            milestones.append({
                "type": "achievement",
                "label": f"解锁「{locked[0]['name']}」",
                "progress_pct": 0,
                "remaining": locked[0].get("hint", "继续努力"),
            })

        # Return the closest one (bond_up is highest priority)
        if milestones:
            return milestones[0]
        return {
            "type": "none",
            "label": "所有里程碑已达成！",
            "progress_pct": 100,
            "remaining": "",
        }

    def _weekly_highlights(self) -> list[str]:
        """Generate 'this week highlights' for the dashboard."""
        highlights = []

        # Total interactions
        total = self.bond.total_interactions
        if total > 0:
            highlights.append(f"累计 {total} 次对话")

        # Streak
        if self.bond.streak_days >= STREAK_HIGHLIGHT_MIN:
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
        if total_facts >= ACHIEVEMENT_FIRST_MEMORY_COUNT or total_memories >= ACHIEVEMENT_FIRST_MEMORY_COUNT:
            self.achievements.check_and_unlock("first_memory")
        if total_facts >= ACHIEVEMENT_TEN_FACTS_COUNT or total_memories >= ACHIEVEMENT_TEN_FACTS_COUNT:
            self.achievements.check_and_unlock("ten_facts")

        if self.bond.total_interactions >= ACHIEVEMENT_FIFTY_CHATS:
            self.achievements.check_and_unlock("fifty_chats")

        # Schedule skill used
        if self.growth.skills.get("schedule", None) and self.growth.skills["schedule"].uses >= 1:
            self.achievements.check_and_unlock("first_schedule")

        # Write skill used (draft)
        if self.growth.skills.get("write", None) and self.growth.skills["write"].uses >= 1:
            self.achievements.check_and_unlock("first_draft")

        # -- Deep --
        if self.bond.streak_days >= ACHIEVEMENT_STREAK_7:
            self.achievements.check_and_unlock("morning_7")
        if self.bond.streak_days >= ACHIEVEMENT_STREAK_30:
            self.achievements.check_and_unlock("month_streak")

        # Social skill used
        if self.growth.skills.get("social", None) and self.growth.skills["social"].uses >= 1:
            self.achievements.check_and_unlock("social_first")

        # 4 weeks of weekly highlights (proxy for weekly_4)
        if self.bond.days_since_creation >= ACHIEVEMENT_WEEKLY_4_DAYS and self.bond.total_interactions >= ACHIEVEMENT_WEEKLY_4_INTERACTIONS:
            self.achievements.check_and_unlock("weekly_4")

        # -- Hidden --
        if self.bond.level >= ACHIEVEMENT_SOULMATE_LEVEL:
            self.achievements.check_and_unlock("soulmate")

        # Deep talk: single message > 500 chars
        if message and len(message) > ACHIEVEMENT_DEEP_TALK_CHARS:
            self.achievements.check_and_unlock("deep_talk")

        # Night owl: chat after 23:00 or before 05:00
        now = datetime.now()
        if now.hour < ACHIEVEMENT_NIGHT_OWL_EARLY or now.hour >= ACHIEVEMENT_NIGHT_OWL_LATE:
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

        if len(message) > LONG_MESSAGE_CHARS:
            daily["long_messages"] = daily.get("long_messages", 0) + 1

        now = datetime.now()
        if now.hour >= EVENING_HOUR:
            daily["evening_chats"] = daily.get("evening_chats", 0) + 1

        try:
            self.soul.store.set_state(today_key, json.dumps(daily))
        except Exception:
            pass

    def _save_emotion_snapshot(self):
        """Persist today's emotion as a daily snapshot for emotion_history()."""
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            raw = self.soul.store.get_state("ome.emotion_history")
            history: dict[str, dict] = json.loads(raw) if raw else {}

            history[today] = {
                "valence": round(self.emotion.valence, 3),
                "arousal": round(self.emotion.arousal, 3),
                "mood": self.emotion.mood,
                "energy": round(self.emotion.energy, 2),
            }

            # Keep last N days max
            if len(history) > EMOTION_HISTORY_MAX_DAYS:
                sorted_keys = sorted(history.keys())
                for k in sorted_keys[:-EMOTION_HISTORY_MAX_DAYS]:
                    del history[k]

            self.soul.store.set_state("ome.emotion_history", json.dumps(history))
        except Exception as e:
            log.debug("Could not save emotion snapshot: %s", e)

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
            persona_def_data = self.soul.store.get_state("ome.persona_definition")
            if persona_def_data:
                self._persona_definition = PersonaDefinition.from_dict(json.loads(persona_def_data))
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
            if self._persona_definition:
                self.soul.store.set_state("ome.persona_definition", json.dumps(self._persona_definition.to_dict()))
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
        """Generate a response using the configured LLM.

        The ModelRouter handles retry-with-fallback across all configured providers.
        This method only needs to call once — the router tries every provider in
        priority order before giving up.
        """
        router = getattr(self.soul.layers.l2, "router", None)
        if router is None:
            log.error("No ModelRouter configured — cannot generate. "
                      "Set up ~/.mindos/config.yaml or call MindosConfig.from_env().")
            return (
                "I haven't been configured with an LLM yet — set one up so I can chat! "
                "我还没有配置好大脑，需要先设置 LLM 才能聊天。"
                "But I've remembered what you said! 不过我已经记住你说的话了！"
            )

        result = router.call_llm(
            task="chat",
            system=system,
            user=user_message,
            max_tokens=LLM_GENERATION_MAX_TOKENS,
        )
        if result:
            return result

        log.error("All LLM providers failed or returned empty. "
                  "Check config.yaml and API keys.")
        return (
            "抱歉，我的大脑暂时连不上了（所有 LLM 都没响应）。"
            "不过我已经记住你说的话了，等恢复后就来找你！"
        )
