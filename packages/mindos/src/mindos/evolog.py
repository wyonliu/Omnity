"""EvoLog — the progressive life-history audit trail for a Mindos.

Subscribes to :mod:`mindos.event_bus` and materialises a durable evolution
timeline in :mod:`mindos.store.evo_log`. Every nontrivial brain event —
reflections, identity changes, contradictions, insights, skill forging —
becomes a queryable row so a user (or ``ome evolve``) can ask:
"show me how my soul has grown this month".

Design notes:
    * Pure persistence layer: the store already has ``record_evo`` /
      ``evo_timeline`` / ``evo_stats``. This module is the *glue* that
      turns EventBus events into those rows.
    * Fail-soft: any exception inside a subscriber is swallowed by the
      EventBus, so the hot path (commit / reflect) is never blocked.
    * Cheap by default: we only persist a short summary + a compact
      JSON details blob. Full payloads live in the original store tables.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional

from mindos.event_bus import (
    CONTRADICTION_DETECTED,
    INSIGHT_GENERATED,
    MAINTENANCE_RUN,
    MEMORY_COMPRESSED,
    PERSONALITY_CHANGED,
    REFLECT_COMPLETED,
    Event,
)

if TYPE_CHECKING:
    from mindos.core import Mindos

log = logging.getLogger("mindos.evolog")


# Canonical event-type strings stored in evo_log.event_type ------------------
EVO_REFLECT = "reflect_cycle"
EVO_IDENTITY_CHANGE = "identity_change"
EVO_CONTRADICTION = "contradiction"
EVO_INSIGHT = "insight"
EVO_MAINTENANCE = "maintenance"
EVO_COMPRESSION = "memory_compressed"
EVO_SKILL_FORGED = "skill_forged"
EVO_CUSTOM = "custom"


def _truncate(text: str, n: int = 200) -> str:
    text = str(text or "").strip().replace("\n", " ")
    return text if len(text) <= n else text[: n - 1] + "…"


class EvoLogger:
    """Wires an event bus to the store's evo_log table.

    One instance per Mindos. Handlers are attached on construction and can
    be detached via :meth:`detach` (chiefly for tests / hot-reload).
    """

    def __init__(self, mindos: "Mindos") -> None:
        self.mindos = mindos
        self.store = mindos.store
        self.bus = mindos.event_bus
        self._handlers: list[tuple[str, Any]] = []
        self._attach()

    # -- subscription lifecycle -----------------------------------------------

    def _attach(self) -> None:
        pairs = [
            (REFLECT_COMPLETED, self._on_reflect),
            (PERSONALITY_CHANGED, self._on_personality),
            (CONTRADICTION_DETECTED, self._on_contradiction),
            (INSIGHT_GENERATED, self._on_insight),
            (MAINTENANCE_RUN, self._on_maintenance),
            (MEMORY_COMPRESSED, self._on_compressed),
        ]
        for event_type, handler in pairs:
            self.bus.on(event_type, handler)
            self._handlers.append((event_type, handler))

    def detach(self) -> None:
        for event_type, handler in self._handlers:
            self.bus.off(event_type, handler)
        self._handlers.clear()

    # -- explicit API ---------------------------------------------------------

    def record(self, event_type: str, summary: str = "",
               layer: str = "", details: Optional[dict] = None) -> str:
        """Manually log an arbitrary evolution event. Returns its id."""
        return self.store.record_evo(event_type=event_type,
                                     summary=summary, layer=layer,
                                     details=details or {})

    def timeline(self, limit: int = 100,
                 event_types: Optional[list[str]] = None,
                 since: Optional[float] = None) -> list[dict]:
        """Read the evolution timeline (newest first)."""
        return self.store.evo_timeline(limit=limit,
                                       event_types=event_types, since=since)

    def stats(self) -> dict[str, Any]:
        """Counts per event type + first/last timestamps."""
        return self.store.evo_stats()

    # -- EventBus handlers ----------------------------------------------------

    def _on_reflect(self, event: Event) -> None:
        data = event.data or {}
        insights = data.get("insights") or []
        summary = _truncate(
            f"reflect_cycle: {len(insights)} insight(s), "
            f"identity_updated={bool(data.get('identity_updated'))}"
        )
        self.store.record_evo(
            event_type=EVO_REFLECT, layer="L4",
            summary=summary,
            details={
                "insight_count": len(insights),
                "identity_updated": bool(data.get("identity_updated")),
                "sample": insights[:3] if isinstance(insights, list) else None,
            },
        )

    def _on_personality(self, event: Event) -> None:
        data = event.data or {}
        traits = data.get("traits") or []
        self.store.record_evo(
            event_type=EVO_IDENTITY_CHANGE, layer="L4",
            summary=_truncate("identity changed: " + ", ".join(map(str, traits[:5]))),
            details={"traits": list(traits)},
        )

    def _on_contradiction(self, event: Event) -> None:
        data = event.data or {}
        self.store.record_evo(
            event_type=EVO_CONTRADICTION, layer="L2",
            summary=_truncate(data.get("description")
                              or data.get("summary")
                              or "contradiction detected"),
            details=data,
        )

    def _on_insight(self, event: Event) -> None:
        data = event.data or {}
        self.store.record_evo(
            event_type=EVO_INSIGHT, layer="L4",
            summary=_truncate(data.get("content")
                              or data.get("summary")
                              or "insight generated"),
            details=data,
        )

    def _on_maintenance(self, event: Event) -> None:
        data = event.data or {}
        self.store.record_evo(
            event_type=EVO_MAINTENANCE, layer="L0",
            summary=_truncate("maintenance: "
                              + ", ".join(f"{k}={v}" for k, v in list(data.items())[:4])),
            details=data,
        )

    def _on_compressed(self, event: Event) -> None:
        data = event.data or {}
        self.store.record_evo(
            event_type=EVO_COMPRESSION, layer="L0",
            summary=_truncate(
                f"memory compressed: freed={data.get('freed', 0)} "
                f"merged={data.get('merged', 0)}"
            ),
            details=data,
        )
