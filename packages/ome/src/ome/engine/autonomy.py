"""Autonomy Engine — event-driven proactive behavior.

Makes the Ome "alive": it doesn't just respond, it initiates.

Event tiers:
  L0 (zero LLM cost): time-based triggers, simple rules
    - morning greeting, streak reminder, birthday, memory anniversary
  L1 (lightweight LLM): needs context understanding
    - daily summary, todo reminder, mood check-in

Autonomy levels:
  Observer (0): only record, never act proactively
  Assistant (1): suggest actions, need confirmation (default)
  Deputy (2): act within authorized scope, report afterwards

OmeState machine: idle → thinking → acting → resting (budget exhausted)

All external actions go through the PermissionSandbox.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, time
from enum import Enum, IntEnum
from typing import Any, Callable, Optional

from ome.engine.permissions import PermissionSandbox, ActionCategory

log = logging.getLogger("ome.autonomy")


class OmeState(str, Enum):
    """Ome's operational state machine."""
    IDLE = "idle"          # Waiting for input or events
    THINKING = "thinking"  # Processing / reasoning
    ACTING = "acting"      # Executing an action
    RESTING = "resting"    # Daily action budget exhausted


class AutonomyLevel(IntEnum):
    """Three tiers of autonomy — how much the Ome can do on its own."""
    OBSERVER = 0    # Only record, never act proactively
    ASSISTANT = 1   # Suggest actions, need user confirmation (default)
    DEPUTY = 2      # Act within authorized scope, report afterwards


@dataclass
class Goal:
    """A goal on the GoalStack — user-assigned or self-generated."""
    title: str
    description: str = ""
    priority: int = 0       # higher = more important
    source: str = "user"    # "user" | "ome"
    created_at: str = ""
    completed: bool = False
    result: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "source": self.source,
            "created_at": self.created_at,
            "completed": self.completed,
            "result": self.result,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Goal":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class Event:
    """An event that can trigger Ome behavior."""
    name: str
    tier: str  # "L0" or "L1"
    description: str
    handler: Optional[Callable] = None
    last_fired: Optional[str] = None  # ISO timestamp
    enabled: bool = True
    cooldown_hours: float = 20.0  # Minimum hours between fires

    def can_fire(self, now: Optional[datetime] = None) -> bool:
        if not self.enabled:
            return False
        if not self.last_fired:
            return True
        now = now or datetime.now()
        try:
            last = datetime.fromisoformat(self.last_fired)
            hours_since = (now - last).total_seconds() / 3600
            return hours_since >= self.cooldown_hours
        except (ValueError, TypeError):
            return True

    def mark_fired(self, now: Optional[datetime] = None):
        self.last_fired = (now or datetime.now()).isoformat()


@dataclass
class EventResult:
    """Result of processing an event."""
    event_name: str
    message: str  # What the Ome says/does
    action_category: str = ActionCategory.READ_MEMORY  # Permission needed
    needs_approval: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class AutonomyEngine:
    """Event-driven autonomy for the Ome.

    Usage:
        engine = AutonomyEngine(permissions=sandbox)
        engine.register("morning", tier="L0", handler=my_handler)
        results = engine.tick(context)  # Check all events

    State machine:
        idle → thinking → acting → idle  (normal flow)
        any  → resting                    (budget exhausted)
        resting → idle                    (next day)
    """

    def __init__(self, permissions: Optional[PermissionSandbox] = None):
        self.permissions = permissions or PermissionSandbox()
        self.events: dict[str, Event] = {}
        self.state: OmeState = OmeState.IDLE
        self.autonomy_level: AutonomyLevel = AutonomyLevel.ASSISTANT
        self.goals: list[Goal] = []
        self.daily_action_budget: int = 50
        self.actions_today: int = 0
        self._budget_date: str = ""  # YYYY-MM-DD, for daily reset
        self._register_defaults()

    def register(
        self,
        name: str,
        *,
        tier: str = "L0",
        description: str = "",
        handler: Optional[Callable] = None,
        cooldown_hours: float = 20.0,
    ):
        """Register a custom event."""
        self.events[name] = Event(
            name=name,
            tier=tier,
            description=description or name,
            handler=handler,
            cooldown_hours=cooldown_hours,
        )

    def on(self, event_name: str, handler: Callable):
        """Shorthand: attach a handler to an event."""
        if event_name in self.events:
            self.events[event_name].handler = handler
        else:
            self.register(event_name, handler=handler)

    def tick(self, context: Optional[dict[str, Any]] = None) -> list[EventResult]:
        """Check all events and fire those that are ready.

        This is intentionally NOT a polling loop — the caller decides when to tick.
        CLI mode: tick on launch. App mode: tick on schedule.

        State machine: idle → thinking → acting → idle (or resting if budget hit).

        Args:
            context: Current state dict with keys like:
                - now: datetime
                - bond_level: int
                - streak_days: int
                - last_chat_date: str
                - user_name: str
        """
        context = context or {}
        now = context.get("now", datetime.now())

        # Daily budget reset
        today = now.strftime("%Y-%m-%d") if isinstance(now, datetime) else ""
        if today and today != self._budget_date:
            self.actions_today = 0
            self._budget_date = today
            if self.state == OmeState.RESTING:
                self.state = OmeState.IDLE

        # If resting, no events fire
        if self.state == OmeState.RESTING:
            return []

        results = []
        self.state = OmeState.THINKING

        for event in self.events.values():
            if not event.can_fire(now):
                continue
            if event.handler is None:
                continue

            # Budget check
            if self.actions_today >= self.daily_action_budget:
                self.state = OmeState.RESTING
                break

            try:
                self.state = OmeState.ACTING
                result = event.handler(context)
                if result:
                    if isinstance(result, str):
                        result = EventResult(event_name=event.name, message=result)
                    elif isinstance(result, dict):
                        result = EventResult(event_name=event.name, **result)

                    # Autonomy level filtering
                    if self.autonomy_level == AutonomyLevel.OBSERVER:
                        result.needs_approval = True
                    elif self.autonomy_level == AutonomyLevel.ASSISTANT:
                        if not self.permissions.can_do(result.action_category):
                            result.needs_approval = True
                    # DEPUTY: can act within authorized scope
                    elif self.autonomy_level == AutonomyLevel.DEPUTY:
                        result.needs_approval = False

                    results.append(result)
                    event.mark_fired(now)
                    self.actions_today += 1
            except Exception as e:
                log.debug("Event %s handler failed: %s", event.name, e)

        self.state = OmeState.IDLE if self.actions_today < self.daily_action_budget else OmeState.RESTING
        return results

    def record_action(self):
        """Record an action against the daily budget (called by external code)."""
        self.actions_today += 1
        if self.actions_today >= self.daily_action_budget:
            self.state = OmeState.RESTING

    @property
    def is_resting(self) -> bool:
        return self.state == OmeState.RESTING

    # -- Goal management -------------------------------------------------------

    def add_goal(self, title: str, description: str = "", source: str = "user",
                 priority: int = 0) -> Goal:
        """Push a goal onto the stack."""
        goal = Goal(
            title=title,
            description=description,
            priority=priority,
            source=source,
            created_at=datetime.now().isoformat(),
        )
        self.goals.append(goal)
        self.goals.sort(key=lambda g: -g.priority)
        return goal

    def complete_goal(self, title: str, result: str = "") -> bool:
        """Mark a goal as completed."""
        for g in self.goals:
            if g.title == title and not g.completed:
                g.completed = True
                g.result = result
                return True
        return False

    def active_goals(self) -> list[Goal]:
        """Return non-completed goals, highest priority first."""
        return [g for g in self.goals if not g.completed]

    def top_goal(self) -> Optional[Goal]:
        """Return the highest-priority active goal, or None."""
        active = self.active_goals()
        return active[0] if active else None

    def enable(self, event_name: str):
        if event_name in self.events:
            self.events[event_name].enabled = True

    def disable(self, event_name: str):
        if event_name in self.events:
            self.events[event_name].enabled = False

    def set_autonomy_level(self, level: AutonomyLevel):
        """Set the autonomy level."""
        self.autonomy_level = level

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "autonomy_level": int(self.autonomy_level),
            "daily_action_budget": self.daily_action_budget,
            "actions_today": self.actions_today,
            "budget_date": self._budget_date,
            "goals": [g.to_dict() for g in self.goals],
            "events": {
                name: {
                    "tier": e.tier,
                    "enabled": e.enabled,
                    "last_fired": e.last_fired,
                    "cooldown_hours": e.cooldown_hours,
                }
                for name, e in self.events.items()
            },
        }

    def load_state(self, state: dict[str, Any]):
        """Restore state from saved dict."""
        # Restore event fire times (backwards compat: state may be flat events dict)
        events_data = state.get("events", state)
        for name, data in events_data.items():
            if name in self.events and isinstance(data, dict):
                self.events[name].last_fired = data.get("last_fired")
                if "enabled" in data:
                    self.events[name].enabled = data["enabled"]

        # Restore new fields
        if "state" in state:
            try:
                self.state = OmeState(state["state"])
            except ValueError:
                self.state = OmeState.IDLE
        if "autonomy_level" in state:
            try:
                self.autonomy_level = AutonomyLevel(state["autonomy_level"])
            except ValueError:
                pass
        self.daily_action_budget = state.get("daily_action_budget", 50)
        self.actions_today = state.get("actions_today", 0)
        self._budget_date = state.get("budget_date", "")
        if "goals" in state:
            self.goals = [Goal.from_dict(g) for g in state["goals"]]

    # -- Default L0 events ----------------------------------------------------

    def _register_defaults(self):
        """Register built-in L0 events."""
        self.register(
            "morning_greeting",
            tier="L0",
            description="早安问候",
            handler=_handle_morning,
            cooldown_hours=20.0,
        )
        self.register(
            "streak_reminder",
            tier="L0",
            description="连续互动提醒",
            handler=_handle_streak_reminder,
            cooldown_hours=20.0,
        )
        self.register(
            "idle_checkin",
            tier="L0",
            description="超过24小时没聊天，关心一下",
            handler=_handle_idle_checkin,
            cooldown_hours=24.0,
        )
        self.register(
            "milestone_celebration",
            tier="L0",
            description="互动里程碑庆祝",
            handler=_handle_milestone,
            cooldown_hours=1.0,
        )


# -- Built-in L0 event handlers ----------------------------------------------

def _handle_morning(ctx: dict) -> Optional[EventResult]:
    """Morning greeting — fires once per day in morning hours."""
    now = ctx.get("now", datetime.now())
    if not (6 <= now.hour <= 10):
        return None

    user_name = ctx.get("user_name", "")
    streak = ctx.get("streak_days", 0)

    if streak > 7:
        msg = f"早安！连续第 {streak} 天了，今天也是美好的一天 ☀️"
    elif streak > 0:
        msg = f"早安{user_name}！我们已经连续聊了 {streak} 天了 🌅"
    else:
        msg = f"早安{user_name}！新的一天开始了 🌅"

    return EventResult(
        event_name="morning_greeting",
        message=msg,
        action_category=ActionCategory.READ_MEMORY,
    )


def _handle_streak_reminder(ctx: dict) -> Optional[EventResult]:
    """Remind about streak when it's about to break."""
    now = ctx.get("now", datetime.now())
    last_chat = ctx.get("last_chat_date", "")
    streak = ctx.get("streak_days", 0)

    if not last_chat or streak < 3:
        return None

    # Only remind in evening if they haven't chatted today
    today = now.strftime("%Y-%m-%d")
    if last_chat == today:
        return None
    if not (18 <= now.hour <= 22):
        return None

    return EventResult(
        event_name="streak_reminder",
        message=f"今天还没聊呢！连续 {streak} 天的记录可别断了 💪",
        action_category=ActionCategory.READ_MEMORY,
    )


def _handle_idle_checkin(ctx: dict) -> Optional[EventResult]:
    """Check in if user hasn't chatted in over 24 hours."""
    last_chat = ctx.get("last_chat_date", "")
    if not last_chat:
        return None

    now = ctx.get("now", datetime.now())
    try:
        last_dt = datetime.strptime(last_chat, "%Y-%m-%d")
        days_idle = (now - last_dt).days
    except (ValueError, TypeError):
        return None

    if days_idle < 2:
        return None

    if days_idle < 7:
        msg = f"已经 {days_idle} 天没聊了，还好吗？"
    else:
        msg = f"好久不见！{days_idle} 天了，有什么新鲜事想聊的吗？"

    return EventResult(
        event_name="idle_checkin",
        message=msg,
        action_category=ActionCategory.READ_MEMORY,
    )


def _handle_milestone(ctx: dict) -> Optional[EventResult]:
    """Celebrate interaction milestones."""
    total = ctx.get("total_interactions", 0)
    milestones = [10, 50, 100, 200, 500, 1000, 2000]

    for m in milestones:
        if total == m:
            return EventResult(
                event_name="milestone_celebration",
                message=f"🎉 我们已经聊了 {m} 次了！这是一个值得纪念的时刻。",
                action_category=ActionCategory.READ_MEMORY,
            )

    return None
