"""Comprehensive tests for Ome Phase 0 enhancements.

Tests cover:
  - PersonalityEngine (anchors, validate, social_mask)
  - Skill system (registry, builtins, execution)
  - Identity Protocol (from_ome, expose_for, verify)
  - Autonomy enhancement (OmeState, AutonomyLevel, GoalStack, budget)
  - Emotion补全 (focused, tired, missing_you)
  - Streak rewards
  - Permission补全 (DRAFT, TRANSACT, three-state check)
  - Dashboard highlights
  - mirror_chat, calibrate, learn_from_platform
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest


@pytest.fixture
def ome_dir(tmp_path):
    return tmp_path / "test_ome"


@pytest.fixture
def ome(ome_dir):
    from ome.core import Ome
    return Ome.create(ome_dir, name="TestUser", traits=["curious", "direct"],
                      style="concise and technical", values=["honesty"])


# =============================================================================
# PersonalityEngine
# =============================================================================

class TestPersonalityEngine:
    def test_init_from_identity(self):
        from ome.engine.personality import PersonalityEngine
        identity = {
            "name": "Alice",
            "personality": {
                "traits": ["curious", "direct"],
                "anchors": ["说话简洁直接", "不替用户做不可逆决策"],
                "values": ["honesty"],
                "catchphrases": ["说白了"],
                "emoji_habits": ["😊"],
                "boundaries": ["不讨论「前任」相关话题"],
            }
        }
        pe = PersonalityEngine(identity)
        assert pe.name == "Alice"
        assert len(pe.anchors) == 2
        assert len(pe.traits) == 2
        assert pe.style_fingerprint.catchphrases == ["说白了"]
        assert "前任" in pe.style_fingerprint.forbidden_phrases

    def test_validate_passes(self):
        from ome.engine.personality import PersonalityEngine
        pe = PersonalityEngine({"name": "Bob", "personality": {"anchors": ["说话简洁"]}})
        ok, text = pe.validate("短回复", context="问好")
        assert ok is True
        assert text == "短回复"

    def test_validate_too_long(self):
        from ome.engine.personality import PersonalityEngine
        pe = PersonalityEngine({"name": "Bob", "personality": {"anchors": ["说话简洁"]}})
        long_text = "啰嗦" * 300
        ok, text = pe.validate(long_text)
        assert ok is False
        assert len(text) < len(long_text)

    def test_validate_irreversible_action(self):
        from ome.engine.personality import PersonalityEngine
        pe = PersonalityEngine({"name": "Bob", "personality": {
            "anchors": ["不替用户做不可逆决策，必须确认"]
        }})
        ok, text = pe.validate("我已经发送了那封邮件")
        assert ok is False
        assert "确认" in text

    def test_validate_pii_leak(self):
        from ome.engine.personality import PersonalityEngine
        pe = PersonalityEngine({"name": "Bob", "personality": {
            "anchors": ["保护隐私"]
        }})
        ok, text = pe.validate("他的手机号是13812345678")
        assert ok is False
        assert "已隐藏" in text

    def test_social_mask_trust_0(self):
        from ome.engine.personality import PersonalityEngine
        pe = PersonalityEngine({
            "name": "Alice",
            "personality": {"traits": ["curious", "direct"], "anchors": ["be honest"]}
        })
        mask = pe.social_mask(0)
        assert "display_name" in mask
        assert "anchors" not in mask

    def test_social_mask_trust_5(self):
        from ome.engine.personality import PersonalityEngine
        pe = PersonalityEngine({
            "name": "Alice",
            "personality": {
                "traits": ["curious"], "anchors": ["be honest"],
                "boundaries": ["no politics"]
            }
        })
        mask = pe.social_mask(5)
        assert mask["full_representation"] is True
        assert "anchors" in mask

    def test_system_prompt_injection(self):
        from ome.engine.personality import PersonalityEngine
        pe = PersonalityEngine({
            "name": "Alice",
            "personality": {
                "anchors": ["诚实", "简洁"],
                "boundaries": ["不讨论「前任」"],
            }
        })
        text = pe.system_prompt_injection()
        assert "诚实" in text
        assert "NEVER violate" in text
        assert "NEVER discuss" in text


# =============================================================================
# Skill System
# =============================================================================

class TestSkillSystem:
    def test_registry_register_and_get(self):
        from ome.skills.base import SkillRegistry, Skill
        reg = SkillRegistry()
        s = Skill()
        s.name = "test_skill"
        s.description = "test"
        reg.register(s)
        assert reg.get("test_skill") is not None
        assert reg.get("nonexistent") is None

    def test_registry_match(self):
        from ome.skills.base import SkillRegistry
        from ome.skills.builtins import register_builtins
        reg = SkillRegistry()
        register_builtins(reg)

        matches = reg.match("写封邮件")
        names = [s.name for s in matches]
        assert "write" in names

    def test_registry_list_all(self):
        from ome.skills.base import SkillRegistry
        from ome.skills.builtins import register_builtins
        reg = SkillRegistry()
        register_builtins(reg)
        skills = reg.list_all()
        assert len(skills) == 5
        names = [s["name"] for s in skills]
        assert "chat" in names
        assert "recall" in names
        assert "write" in names
        assert "research" in names
        assert "schedule" in names

    def test_skill_can_execute(self, ome):
        skills = ome.list_skills()
        chat_skill = next(s for s in skills if s["name"] == "chat")
        assert chat_skill["available"] is True

    def test_use_chat_skill(self, ome):
        result = ome.use_skill("chat", message="Hello!")
        # Without LLM, chat skill falls back
        assert result.success is True or "LLM" in result.output

    def test_use_recall_skill_empty(self, ome):
        result = ome.use_skill("recall", query="nonexistent")
        assert result.success is True
        assert "没有找到" in result.output

    def test_use_schedule_skill(self, ome):
        # Bond level might be too low for schedule
        from ome.engine.permissions import TrustLevel
        ome.permissions.raise_trust(TrustLevel.ASSISTANT)
        ome.bond.level = 2  # Force bond level for test

        result = ome.use_skill("schedule", action="list")
        assert result.success is True
        assert "暂无日程" in result.output

    def test_skill_not_found(self, ome):
        result = ome.use_skill("nonexistent_skill")
        assert result.success is False

    def test_skill_bond_check(self):
        from ome.skills.builtins import WriteSkill
        skill = WriteSkill()
        assert skill.min_bond_level == 2
        assert skill.requires_approval is True


# =============================================================================
# Identity Protocol
# =============================================================================

class TestIdentityProtocol:
    def test_from_ome(self, ome):
        from ome.identity_protocol import OmeIdentity
        identity = OmeIdentity.from_ome(ome)
        assert identity.ome_id.startswith("ome:testuser:")
        assert identity.version == "0.4.0"
        assert "display_name" in identity.public_persona
        assert identity.public_persona["display_name"] == "TestUser"
        assert len(identity.mindos_anchor) == 64  # sha256

    def test_expose_mcp(self, ome):
        card = ome.identity_card(protocol="mcp")
        assert card["uri"] == "ome://identity"
        assert card["mimeType"] == "application/json"
        parsed = json.loads(card["text"])
        assert "ome_id" in parsed

    def test_expose_http(self, ome):
        card = ome.identity_card(protocol="http")
        assert "ome_id" in card
        assert "trust_policy" in card
        assert "mindos_anchor" in card

    def test_expose_soap(self, ome):
        card = ome.identity_card(protocol="soap")
        assert card["event"] == "agent.presence"
        assert "agent_id" in card
        assert "payload" in card

    def test_expose_generic(self, ome):
        card = ome.identity_card(protocol="generic")
        assert "ome_id" in card
        assert "created_at" in card
        assert "mindos_anchor" in card

    def test_verify(self):
        from ome.identity_protocol import OmeIdentity
        identity = OmeIdentity(mindos_anchor="abc123")
        assert identity.verify("abc123") is True
        assert identity.verify("wrong") is False

    def test_to_dict_and_from_dict(self, ome):
        from ome.identity_protocol import OmeIdentity
        identity = OmeIdentity.from_ome(ome)
        d = identity.to_dict()
        restored = OmeIdentity.from_dict(d)
        assert restored.ome_id == identity.ome_id
        assert restored.mindos_anchor == identity.mindos_anchor


# =============================================================================
# Autonomy Enhancement
# =============================================================================

class TestAutonomyEnhancement:
    def test_ome_state_enum(self):
        from ome.engine.autonomy import OmeState
        assert OmeState.IDLE.value == "idle"
        assert OmeState.THINKING.value == "thinking"
        assert OmeState.ACTING.value == "acting"
        assert OmeState.RESTING.value == "resting"

    def test_autonomy_level_enum(self):
        from ome.engine.autonomy import AutonomyLevel
        assert AutonomyLevel.OBSERVER == 0
        assert AutonomyLevel.ASSISTANT == 1
        assert AutonomyLevel.DEPUTY == 2
        assert AutonomyLevel.OBSERVER < AutonomyLevel.ASSISTANT

    def test_goal_management(self):
        from ome.engine.autonomy import AutonomyEngine
        engine = AutonomyEngine()

        g1 = engine.add_goal("Write report", priority=1)
        g2 = engine.add_goal("Send email", priority=5)
        g3 = engine.add_goal("Research topic", priority=3)

        assert len(engine.goals) == 3
        assert engine.top_goal().title == "Send email"  # highest priority
        assert len(engine.active_goals()) == 3

        engine.complete_goal("Send email", result="Sent!")
        assert len(engine.active_goals()) == 2
        assert engine.top_goal().title == "Research topic"

    def test_daily_budget(self):
        from ome.engine.autonomy import AutonomyEngine, OmeState
        engine = AutonomyEngine()
        engine.daily_action_budget = 3

        # Register a simple handler
        engine.register("test_event", handler=lambda ctx: "fired",
                        cooldown_hours=0)

        for i in range(5):
            engine.tick({"now": datetime(2026, 3, 22, 12, i)})

        assert engine.actions_today <= 3
        assert engine.state == OmeState.RESTING

    def test_budget_resets_daily(self):
        from ome.engine.autonomy import AutonomyEngine, OmeState
        engine = AutonomyEngine()
        engine.daily_action_budget = 2
        engine.register("test_event", handler=lambda ctx: "fired",
                        cooldown_hours=0)

        engine.tick({"now": datetime(2026, 3, 22, 12, 0)})
        engine.tick({"now": datetime(2026, 3, 22, 12, 1)})
        engine.tick({"now": datetime(2026, 3, 22, 12, 2)})
        assert engine.state == OmeState.RESTING

        # Next day → budget resets, verify actions_today is 0
        # Use a high budget so we don't re-exhaust immediately
        engine.daily_action_budget = 100
        engine.tick({"now": datetime(2026, 3, 23, 8, 0)})
        assert engine.state != OmeState.RESTING
        assert engine.actions_today < 100  # budget was reset

    def test_observer_needs_approval(self):
        from ome.engine.autonomy import AutonomyEngine, AutonomyLevel
        engine = AutonomyEngine()
        engine.autonomy_level = AutonomyLevel.OBSERVER

        results = engine.tick({
            "now": datetime(2026, 3, 22, 8, 0),
            "user_name": "X",
            "streak_days": 1,
        })
        for r in results:
            assert r.needs_approval is True

    def test_deputy_no_approval(self):
        from ome.engine.autonomy import AutonomyEngine, AutonomyLevel
        engine = AutonomyEngine()
        engine.autonomy_level = AutonomyLevel.DEPUTY

        results = engine.tick({
            "now": datetime(2026, 3, 22, 8, 0),
            "user_name": "X",
            "streak_days": 1,
        })
        for r in results:
            assert r.needs_approval is False

    def test_state_persistence(self):
        from ome.engine.autonomy import AutonomyEngine, AutonomyLevel, OmeState
        engine = AutonomyEngine()
        engine.autonomy_level = AutonomyLevel.DEPUTY
        engine.add_goal("Test goal", priority=3)
        engine.tick({
            "now": datetime(2026, 3, 22, 8, 0),
            "user_name": "X",
            "streak_days": 1,
        })

        state = engine.to_dict()
        assert state["autonomy_level"] == 2
        assert len(state["goals"]) == 1

        engine2 = AutonomyEngine()
        engine2.load_state(state)
        assert engine2.autonomy_level == AutonomyLevel.DEPUTY
        assert len(engine2.goals) == 1
        assert engine2.goals[0].title == "Test goal"

    def test_backwards_compat_load_state(self):
        """Old state format (flat events dict) still works."""
        from ome.engine.autonomy import AutonomyEngine
        engine = AutonomyEngine()
        old_state = {
            "morning_greeting": {
                "tier": "L0",
                "enabled": True,
                "last_fired": "2026-03-22T08:00:00",
                "cooldown_hours": 20.0,
            }
        }
        engine.load_state(old_state)
        assert engine.events["morning_greeting"].last_fired is not None


# =============================================================================
# Emotion Enhancement
# =============================================================================

class TestEmotionEnhancement:
    def test_focused_detection(self):
        from ome.life.emotion import EmotionState
        state = EmotionState()
        for msg in ["我在专注coding", "别打扰我，正在赶工", "集中精力"]:
            state.update_from_message(msg)
        assert state.mood == "focused"

    def test_tired_from_budget(self):
        from ome.life.emotion import EmotionState
        state = EmotionState()
        state.update_from_interaction(
            streak_days=3, bond_level=2,
            actions_today=45, action_budget=50,
        )
        assert state.mood == "tired"
        assert state.energy < 0.5

    def test_missing_you(self):
        from ome.life.emotion import EmotionState
        state = EmotionState()
        state.update_from_interaction(
            streak_days=0, bond_level=2,
            idle_days=5,
        )
        assert state.mood == "missing_you"

    def test_missing_you_requires_bond(self):
        """missing_you only triggers with bond >= 1."""
        from ome.life.emotion import EmotionState
        state = EmotionState()
        state.update_from_interaction(
            streak_days=0, bond_level=0,
            idle_days=5,
        )
        assert state.mood != "missing_you"

    def test_focused_emoji(self):
        from ome.life.emotion import EmotionState
        state = EmotionState(mood="focused")
        assert state.mood_emoji() == "🎯"

    def test_tired_emoji(self):
        from ome.life.emotion import EmotionState
        state = EmotionState(mood="tired")
        assert state.mood_emoji() == "😴"

    def test_missing_emoji(self):
        from ome.life.emotion import EmotionState
        state = EmotionState(mood="missing_you")
        assert state.mood_emoji() == "🥺"

    def test_focused_style_modifier(self):
        from ome.life.emotion import EmotionState
        state = EmotionState(mood="focused")
        mod = state.style_modifier()
        assert "简洁" in mod or "高效" in mod


# =============================================================================
# Streak Rewards
# =============================================================================

class TestStreakRewards:
    def test_streak_3_reward(self, ome):
        ome.bond.streak_days = 3
        rewards = ome._check_streak_rewards()
        names = [r["name"] for r in rewards]
        assert "每日洞察" in names

    def test_streak_7_achievement(self, ome):
        ome.bond.streak_days = 7
        ome._check_streak_rewards()
        assert "morning_7" in ome.achievements.unlocked

    def test_streak_30_achievement(self, ome):
        ome.bond.streak_days = 30
        ome._check_streak_rewards()
        assert "month_streak" in ome.achievements.unlocked

    def test_streak_reward_not_repeated(self, ome):
        ome.bond.streak_days = 3
        rewards1 = ome._check_streak_rewards()
        rewards2 = ome._check_streak_rewards()
        # Second call should return empty (already given)
        assert len(rewards2) == 0
        assert len(rewards1) > 0


# =============================================================================
# Permission Enhancement
# =============================================================================

class TestPermissionEnhancement:
    def test_draft_category(self):
        from ome.engine.permissions import PermissionSandbox, ActionCategory, TrustLevel
        sandbox = PermissionSandbox()  # Default OBSERVER
        assert sandbox.can_do(ActionCategory.DRAFT) is False

        sandbox.raise_trust(TrustLevel.ASSISTANT)
        assert sandbox.can_do(ActionCategory.DRAFT) is True

    def test_transact_category(self):
        from ome.engine.permissions import PermissionSandbox, ActionCategory, TrustLevel
        sandbox = PermissionSandbox()
        sandbox.raise_trust(TrustLevel.ASSISTANT)
        assert sandbox.can_do(ActionCategory.TRANSACT) is False

        sandbox.raise_trust(TrustLevel.DEPUTY)
        assert sandbox.can_do(ActionCategory.TRANSACT) is True

    def test_check_three_state_allowed(self):
        from ome.engine.permissions import PermissionSandbox, ActionCategory, PermissionResult, TrustLevel
        sandbox = PermissionSandbox(trust_level=TrustLevel.ASSISTANT)
        result = sandbox.check(ActionCategory.DRAFT)
        assert result == PermissionResult.ALLOWED

    def test_check_three_state_needs_approval(self):
        from ome.engine.permissions import PermissionSandbox, ActionCategory, PermissionResult, TrustLevel
        sandbox = PermissionSandbox(trust_level=TrustLevel.ASSISTANT)
        # TRANSACT requires DEPUTY (3), we're at ASSISTANT (2) — one level below
        result = sandbox.check(ActionCategory.TRANSACT)
        assert result == PermissionResult.NEEDS_APPROVAL

    def test_check_three_state_denied(self):
        from ome.engine.permissions import PermissionSandbox, ActionCategory, PermissionResult, TrustLevel
        sandbox = PermissionSandbox(trust_level=TrustLevel.OBSERVER)
        # TRANSACT requires DEPUTY (3), we're at OBSERVER (1) — too far below
        result = sandbox.check(ActionCategory.TRANSACT)
        assert result == PermissionResult.DENIED

    def test_check_approved_scope_overrides(self):
        from ome.engine.permissions import PermissionSandbox, ActionCategory, PermissionResult
        sandbox = PermissionSandbox()  # OBSERVER
        sandbox.approved_scopes.add(ActionCategory.TRANSACT)
        result = sandbox.check(ActionCategory.TRANSACT)
        assert result == PermissionResult.ALLOWED


# =============================================================================
# Dashboard Highlights
# =============================================================================

class TestDashboard:
    def test_dashboard_has_highlights(self, ome):
        ome.chat("Hello!")
        dashboard = ome.life_dashboard()
        assert "highlights" in dashboard
        assert isinstance(dashboard["highlights"], list)

    def test_dashboard_has_autonomy(self, ome):
        dashboard = ome.life_dashboard()
        assert "autonomy" in dashboard
        assert dashboard["autonomy"]["state"] == "idle"
        assert "level_name" in dashboard["autonomy"]

    def test_highlights_show_interactions(self, ome):
        ome.chat("Hi")
        highlights = ome._weekly_highlights()
        has_interaction = any("对话" in h for h in highlights)
        assert has_interaction

    def test_version_bump(self, ome):
        s = ome.status()
        assert s["ome_version"] == "0.4.0"


# =============================================================================
# Mirror Chat & Calibrate
# =============================================================================

class TestMirrorCalibrate:
    def test_mirror_chat_returns_string(self, ome):
        reply = ome.mirror_chat("你最近在忙什么？")
        assert isinstance(reply, str)
        assert len(reply) > 0

    def test_mirror_chat_commits_memory(self, ome):
        ome.mirror_chat("Python开发很有趣")
        results = ome.recall("Python")
        contents = " ".join(r.get("content", "") for r in results)
        assert "Python" in contents

    def test_calibrate_positive(self, ome):
        result = ome.calibrate("你好", "你好啊！", "完美")
        assert result["action"] == "reinforced"

    def test_calibrate_negative(self, ome):
        result = ome.calibrate("你好", "你好呀~", "这不像我，我不会用波浪号")
        assert result["action"] == "corrected"
        assert "波浪号" in result["feedback"]

    def test_learn_from_platform_empty(self, ome):
        from ome.life.persona import PersonaProfile
        profile = ome.learn_from_platform("wechat", "/nonexistent/path.txt")
        assert isinstance(profile, PersonaProfile)


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    def test_full_chat_lifecycle(self, ome):
        """Full chat → memory → achievement → streak cycle."""
        reply = ome.chat("Hello, I'm a Python developer!")
        assert isinstance(reply, str)

        results = ome.recall("Python")
        assert len(results) > 0

        assert ome.bond.total_interactions >= 1

    def test_skill_after_chat(self, ome):
        """Skills work after chat."""
        ome.chat("Hi!")
        result = ome.use_skill("recall", query="Hi")
        assert result.success is True

    def test_identity_card_after_interactions(self, ome):
        """Identity card reflects current state."""
        ome.chat("I love building things")
        card = ome.identity_card()
        assert "ome_id" in card

    def test_emotion_updates_through_chat(self, ome):
        """Emotion updates via chat messages."""
        for msg in ["太棒了!", "好开心!", "太好了!", "谢谢!"]:
            ome.chat(msg)
        assert ome.emotion.mood in ("happy", "excited")

    def test_dashboard_comprehensive(self, ome):
        """Dashboard after some activity."""
        ome.chat("Hello!")
        ome.remember("I like Python")

        dashboard = ome.life_dashboard()
        assert "bond" in dashboard
        assert "achievements" in dashboard
        assert "skills" in dashboard
        assert "streak" in dashboard
        assert "emotion" in dashboard
        assert "permissions" in dashboard
        assert "autonomy" in dashboard
        assert "highlights" in dashboard

    def test_export_includes_skills(self, ome):
        """list_skills returns all 5 builtins."""
        skills = ome.list_skills()
        assert len(skills) == 5

    def test_autonomy_in_ome(self, ome):
        """Ome's autonomy engine has new fields."""
        from ome.engine.autonomy import OmeState, AutonomyLevel
        assert ome.autonomy.state == OmeState.IDLE
        assert ome.autonomy.autonomy_level == AutonomyLevel.ASSISTANT
        assert ome.autonomy.daily_action_budget == 50

    def test_personality_integrated(self, ome):
        """PersonalityEngine is initialized in Ome."""
        assert ome.personality is not None
        assert ome.personality.name == "TestUser"

    def test_save_load_preserves_new_state(self, ome_dir):
        """New autonomy/emotion state persists across save/load."""
        from ome.core import Ome
        from ome.engine.autonomy import AutonomyLevel

        ome = Ome.create(ome_dir, name="PersistTest")
        ome.autonomy.autonomy_level = AutonomyLevel.DEPUTY
        ome.autonomy.add_goal("Test goal", priority=5)
        ome.chat("Hello")  # triggers save

        ome2 = Ome.load(ome_dir)
        assert ome2.autonomy.autonomy_level == AutonomyLevel.DEPUTY
        assert len(ome2.autonomy.goals) == 1
