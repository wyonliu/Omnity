"""Growth Stage Capability Unlocking — gates features by maturity.

Each growth phase (newborn → forming → distinct → soulmate) unlocks new
capabilities. This module defines the capability taxonomy and stage gates,
keeping the logic decoupled from conversation_strategy.py's phase definitions.
"""

from __future__ import annotations

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Any


class Capability(Enum):
    """All capabilities an Ome can unlock over its growth arc."""
    CHAT = auto()           # Basic conversation
    RECALL = auto()         # Memory search
    REMEMBER = auto()       # Manual memory input
    WRITE = auto()          # Generate text (articles, summaries)
    RESEARCH = auto()       # Web/knowledge lookup
    PROACTIVE_GREET = auto()  # Send greetings autonomously
    FOLLOW_UPS = auto()     # Suggest follow-up questions
    SMART_EXTRACT = auto()  # Structured data extraction
    SCHEDULE = auto()       # Autonomous scheduling
    SOCIAL = auto()         # Cross-platform messaging
    EVOLVE = auto()         # Self-reflection / identity evolution
    SOUL_CARD = auto()      # Generate soul card
    SPATIAL = auto()        # Spatial AI features


# Stage → capabilities unlocked at that stage
# Cumulative: stage N includes all capabilities from stages 0..N-1
_STAGE_GATES: dict[int, list[Capability]] = {
    0: [Capability.CHAT, Capability.RECALL, Capability.REMEMBER],
    1: [Capability.WRITE, Capability.RESEARCH, Capability.PROACTIVE_GREET, Capability.FOLLOW_UPS],
    2: [Capability.SMART_EXTRACT, Capability.SCHEDULE, Capability.EVOLVE, Capability.SOUL_CARD],
    3: [Capability.SOCIAL, Capability.SPATIAL],
}


@dataclass
class GrowthGate:
    """Evaluates capability access based on growth phase."""

    phase_id: int = 0

    def update_phase(self, phase_id: int) -> None:
        self.phase_id = phase_id

    def unlocked_capabilities(self) -> list[Capability]:
        """All capabilities available at the current phase (cumulative)."""
        caps: list[Capability] = []
        for stage_id in sorted(_STAGE_GATES.keys()):
            if stage_id <= self.phase_id:
                caps.extend(_STAGE_GATES[stage_id])
        return caps

    def is_unlocked(self, cap: Capability) -> bool:
        """Check if a specific capability is unlocked."""
        return cap in self.unlocked_capabilities()

    def locked_capabilities(self) -> list[Capability]:
        """Capabilities not yet unlocked."""
        unlocked = set(self.unlocked_capabilities())
        return [c for c in Capability if c not in unlocked]

    def next_unlock(self) -> dict[str, Any] | None:
        """What unlocks at the next stage."""
        next_stage = self.phase_id + 1
        if next_stage not in _STAGE_GATES:
            return None
        return {
            "stage": next_stage,
            "capabilities": [c.name.lower() for c in _STAGE_GATES[next_stage]],
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase_id": self.phase_id,
            "unlocked": [c.name.lower() for c in self.unlocked_capabilities()],
            "locked": [c.name.lower() for c in self.locked_capabilities()],
            "next_unlock": self.next_unlock(),
        }
