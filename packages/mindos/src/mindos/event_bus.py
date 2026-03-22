"""EventBus — Mindos internal event system connecting layers + external systems.

Decouples producers (L2 commit, L4 reflect) from consumers (Ome, Scheduler, InsightEngine).
Synchronous dispatch by default; async-compatible via callback pattern.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable

log = logging.getLogger("mindos.event_bus")


# ---------------------------------------------------------------------------
# Built-in event types
# ---------------------------------------------------------------------------

MEMORY_COMMITTED = "memory.committed"
REFLECT_COMPLETED = "reflect.completed"
PERSONALITY_CHANGED = "personality.changed"
CONTRADICTION_DETECTED = "contradiction.detected"
INSIGHT_GENERATED = "insight.generated"
COMMIT_BATCH = "commit.batch"
MEMORY_COMPRESSED = "memory.compressed"
MAINTENANCE_RUN = "maintenance.run"


@dataclass
class Event:
    """An event payload flowing through the bus."""
    type: str
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()


class EventBus:
    """Publish-subscribe event bus for Mindos internals.

    Usage:
        bus = EventBus()
        bus.on("memory.committed", lambda e: print(e.data))
        bus.emit("memory.committed", {"facts_added": 3})
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable[[Event], None]]] = defaultdict(list)
        self._history: list[Event] = []
        self._max_history = 100

    def on(self, event_type: str, handler: Callable[[Event], None]) -> None:
        """Register an event handler."""
        self._handlers[event_type].append(handler)

    def off(self, event_type: str, handler: Callable[[Event], None]) -> None:
        """Unregister an event handler."""
        handlers = self._handlers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)

    def emit(self, event_type: str, data: dict[str, Any] | None = None) -> Event:
        """Emit an event. All registered handlers are called synchronously."""
        event = Event(type=event_type, data=data or {})
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        for handler in self._handlers.get(event_type, []):
            try:
                handler(event)
            except Exception as e:
                log.warning("Event handler for %s failed: %s", event_type, e)

        return event

    def recent_events(self, event_type: str | None = None, limit: int = 20) -> list[Event]:
        """Get recent events, optionally filtered by type."""
        events = self._history
        if event_type:
            events = [e for e in events if e.type == event_type]
        return events[-limit:]

    def clear_handlers(self) -> None:
        """Remove all handlers (useful for testing)."""
        self._handlers.clear()

    def handler_count(self, event_type: str | None = None) -> int:
        """Count registered handlers."""
        if event_type:
            return len(self._handlers.get(event_type, []))
        return sum(len(h) for h in self._handlers.values())
