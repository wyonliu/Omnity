"""Chronicle — event log, milestone detection, snapshots."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path

from maxim.models import Event, World

log = logging.getLogger("maxim.chronicle")

# Auto-detected milestones
MILESTONE_TYPES = {
    "first_trade": False,
    "first_marriage": False,
    "first_death": False,
    "first_birth": False,
    "pop_20": False,
    "pop_50": False,
    "gini_high": False,  # Gini > 0.5
    "economic_crisis": False,  # GDP drops > 50% from peak
}


class Chronicle:
    """Records and analyzes civilization history."""

    def __init__(self):
        self.events: list[Event] = []
        self.milestones: list[Event] = []
        self.snapshots: list[dict] = []
        self._milestone_flags = dict(MILESTONE_TYPES)
        self._peak_gdp = 0.0
        self._gdp_history: list[float] = []

    def log_events(self, events: list[Event]) -> None:
        """Add events and check for milestones."""
        for event in events:
            self.events.append(event)
            self._check_milestone(event)

    def log_tick(self, world: World, narration: str = "") -> None:
        """Record per-tick economic data."""
        self._gdp_history.append(world.economy.gdp)
        if world.economy.gdp > self._peak_gdp:
            self._peak_gdp = world.economy.gdp

        # Check population milestones
        pop = world.population
        if pop >= 20 and not self._milestone_flags["pop_20"]:
            self._milestone_flags["pop_20"] = True
            m = Event(year=world.year, season=world.season, type="milestone",
                      description=f"Population reached {pop}")
            self.milestones.append(m)
            self.events.append(m)

        if pop >= 50 and not self._milestone_flags["pop_50"]:
            self._milestone_flags["pop_50"] = True
            m = Event(year=world.year, season=world.season, type="milestone",
                      description=f"Population reached {pop}")
            self.milestones.append(m)
            self.events.append(m)

        # Economic crisis detection
        if self._peak_gdp > 0 and world.economy.gdp < self._peak_gdp * 0.5:
            if not self._milestone_flags["economic_crisis"]:
                self._milestone_flags["economic_crisis"] = True
                m = Event(year=world.year, season=world.season, type="milestone",
                          description="Economic crisis: GDP dropped below 50% of peak")
                self.milestones.append(m)
                self.events.append(m)

        # High inequality
        if world.economy.gini > 0.5 and not self._milestone_flags["gini_high"]:
            self._milestone_flags["gini_high"] = True
            m = Event(year=world.year, season=world.season, type="milestone",
                      description=f"Inequality peaked: Gini coefficient {world.economy.gini:.2f}")
            self.milestones.append(m)
            self.events.append(m)

    def snapshot(self, world: World) -> None:
        """Save a world state snapshot."""
        snap = {
            "year": world.year,
            "season": world.season,
            "population": world.population,
            "gdp": world.economy.gdp,
            "avg_wealth": world.economy.avg_wealth,
            "gini": world.economy.gini,
            "unemployment": world.economy.unemployment_rate,
            "treasury": world.treasury,
            "agents": {
                a.id: {
                    "name": a.name,
                    "age": a.age,
                    "occupation": a.occupation,
                    "wealth": round(a.wealth, 1),
                    "alive": a.alive,
                }
                for a in world.agents.values()
            },
        }
        self.snapshots.append(snap)

    def export_json(self, path: str | Path) -> None:
        """Export full chronicle to JSON."""
        data = {
            "events": [
                {
                    "year": e.year,
                    "season": e.season,
                    "type": e.type,
                    "description": e.description,
                    "agents": e.agents_involved,
                }
                for e in self.events
            ],
            "milestones": [
                {"year": m.year, "description": m.description}
                for m in self.milestones
            ],
            "snapshots": self.snapshots,
            "gdp_history": self._gdp_history,
        }
        Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def summary(self) -> str:
        """Text summary of the civilization."""
        lines = [f"=== Chronicle: {len(self.events)} events, {len(self.milestones)} milestones ==="]
        for m in self.milestones:
            lines.append(f"  Year {m.year}: {m.description}")
        return "\n".join(lines)

    def _check_milestone(self, event: Event) -> None:
        flag_map = {
            "trade": "first_trade",
            "marriage": "first_marriage",
            "death": "first_death",
            "birth": "first_birth",
        }
        flag = flag_map.get(event.type)
        if flag and not self._milestone_flags.get(flag, True):
            self._milestone_flags[flag] = True
            m = Event(
                year=event.year,
                season=event.season,
                type="milestone",
                description=f"First {event.type}: {event.description}",
                agents_involved=event.agents_involved,
            )
            self.milestones.append(m)
