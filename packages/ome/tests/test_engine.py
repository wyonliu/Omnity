"""Tests for Autonomy Engine and Permission Sandbox."""

from __future__ import annotations

from datetime import datetime

import pytest


# -- Permission Sandbox -------------------------------------------------------

def test_trust_level_default():
    """Default trust level is Observer."""
    from ome.engine.permissions import PermissionSandbox, TrustLevel
    sandbox = PermissionSandbox()
    assert sandbox.trust_level == TrustLevel.OBSERVER


def test_can_do_read():
    """Observer can read memory."""
    from ome.engine.permissions import PermissionSandbox, ActionCategory
    sandbox = PermissionSandbox()
    assert sandbox.can_do(ActionCategory.READ_MEMORY) is True
    assert sandbox.can_do(ActionCategory.WRITE_LOCAL) is False


def test_trust_level_raise():
    """Raising trust level enables more actions."""
    from ome.engine.permissions import PermissionSandbox, TrustLevel, ActionCategory
    sandbox = PermissionSandbox()
    assert sandbox.can_do(ActionCategory.WRITE_LOCAL) is False

    sandbox.raise_trust(TrustLevel.ASSISTANT)
    assert sandbox.can_do(ActionCategory.WRITE_LOCAL) is True
    assert sandbox.can_do(ActionCategory.SEND_MESSAGE) is False


def test_approved_scopes():
    """Pre-approved scopes bypass trust level."""
    from ome.engine.permissions import PermissionSandbox, ActionCategory
    sandbox = PermissionSandbox()
    assert sandbox.can_do(ActionCategory.SEND_MESSAGE) is False

    sandbox.approved_scopes.add(ActionCategory.SEND_MESSAGE)
    assert sandbox.can_do(ActionCategory.SEND_MESSAGE) is True


def test_permission_request():
    """Permission requests are logged correctly."""
    from ome.engine.permissions import PermissionSandbox, ActionCategory
    sandbox = PermissionSandbox()
    req = sandbox.request_permission(ActionCategory.WRITE_LOCAL, "Write a draft")
    assert req.approved is None
    assert len(sandbox.pending_requests) == 1

    sandbox.approve(req)
    assert req.approved is True


def test_permission_serialization():
    """Permission sandbox serializes and deserializes."""
    from ome.engine.permissions import PermissionSandbox, TrustLevel, ActionCategory
    sandbox = PermissionSandbox(trust_level=TrustLevel.ASSISTANT)
    sandbox.approved_scopes.add(ActionCategory.SEND_MESSAGE)

    data = sandbox.to_dict()
    restored = PermissionSandbox.from_dict(data)
    assert restored.trust_level == TrustLevel.ASSISTANT
    assert ActionCategory.SEND_MESSAGE in restored.approved_scopes


# -- Autonomy Engine ----------------------------------------------------------

def test_default_events_registered():
    """Default L0 events are registered on init."""
    from ome.engine.autonomy import AutonomyEngine
    engine = AutonomyEngine()
    assert "morning_greeting" in engine.events
    assert "streak_reminder" in engine.events
    assert "idle_checkin" in engine.events
    assert "milestone_celebration" in engine.events


def test_morning_greeting_fires():
    """Morning greeting fires between 6-10am."""
    from ome.engine.autonomy import AutonomyEngine

    engine = AutonomyEngine()
    morning = datetime(2026, 3, 22, 8, 0, 0)
    context = {"now": morning, "user_name": "Captain", "streak_days": 5}

    results = engine.tick(context)
    morning_results = [r for r in results if r.event_name == "morning_greeting"]
    assert len(morning_results) == 1
    assert "Captain" in morning_results[0].message


def test_morning_greeting_skips_afternoon():
    """Morning greeting does NOT fire in the afternoon."""
    from ome.engine.autonomy import AutonomyEngine

    engine = AutonomyEngine()
    afternoon = datetime(2026, 3, 22, 14, 0, 0)
    context = {"now": afternoon, "user_name": "Captain", "streak_days": 5}

    results = engine.tick(context)
    morning_results = [r for r in results if r.event_name == "morning_greeting"]
    assert len(morning_results) == 0


def test_milestone_fires_at_50():
    """Milestone celebration fires at 50 interactions."""
    from ome.engine.autonomy import AutonomyEngine

    engine = AutonomyEngine()
    context = {"now": datetime(2026, 3, 22, 12, 0), "total_interactions": 50}

    results = engine.tick(context)
    milestone = [r for r in results if r.event_name == "milestone_celebration"]
    assert len(milestone) == 1
    assert "50" in milestone[0].message


def test_event_cooldown():
    """Events respect cooldown period."""
    from ome.engine.autonomy import AutonomyEngine

    engine = AutonomyEngine()
    morning1 = datetime(2026, 3, 22, 8, 0, 0)
    morning2 = datetime(2026, 3, 22, 9, 0, 0)  # Same day, 1 hour later

    context = {"now": morning1, "user_name": "X", "streak_days": 1}
    results1 = engine.tick(context)

    context["now"] = morning2
    results2 = engine.tick(context)

    morning1_count = len([r for r in results1 if r.event_name == "morning_greeting"])
    morning2_count = len([r for r in results2 if r.event_name == "morning_greeting"])
    assert morning1_count == 1
    assert morning2_count == 0  # cooldown prevents re-fire


def test_custom_event():
    """Custom events can be registered and fired."""
    from ome.engine.autonomy import AutonomyEngine, EventResult

    engine = AutonomyEngine()
    engine.register("custom_test", tier="L0", handler=lambda ctx: "Hello custom!",
                    cooldown_hours=0)

    results = engine.tick({"now": datetime(2026, 3, 22, 12, 0)})
    custom = [r for r in results if r.event_name == "custom_test"]
    assert len(custom) == 1
    assert custom[0].message == "Hello custom!"


def test_idle_checkin():
    """Idle check-in fires after 2+ days of no chat."""
    from ome.engine.autonomy import AutonomyEngine

    engine = AutonomyEngine()
    context = {
        "now": datetime(2026, 3, 25, 12, 0),
        "last_chat_date": "2026-03-20",
        "streak_days": 0,
    }
    results = engine.tick(context)
    idle = [r for r in results if r.event_name == "idle_checkin"]
    assert len(idle) == 1
    assert "5" in idle[0].message  # 5 days idle


def test_engine_state_persistence():
    """Engine state (last_fired) can be saved and restored."""
    from ome.engine.autonomy import AutonomyEngine

    engine = AutonomyEngine()
    engine.tick({"now": datetime(2026, 3, 22, 8, 0), "user_name": "X", "streak_days": 1})

    state = engine.to_dict()
    assert state["events"]["morning_greeting"]["last_fired"] is not None

    engine2 = AutonomyEngine()
    engine2.load_state(state)
    assert engine2.events["morning_greeting"].last_fired is not None
