"""Core data models for Maxim simulation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Needs:
    """Maslow hierarchy — drives all agent behavior."""

    survival: float = 50.0  # food, shelter (0=dying, 100=thriving)
    safety: float = 50.0  # security, stability
    belonging: float = 30.0  # friendship, family
    esteem: float = 20.0  # reputation, achievement
    actualization: float = 10.0  # creativity, legacy

    def clamp(self) -> None:
        for attr in ("survival", "safety", "belonging", "esteem", "actualization"):
            setattr(self, attr, max(0.0, min(100.0, getattr(self, attr))))

    def lowest_unmet(self, threshold: float = 30.0) -> Optional[str]:
        """Return the lowest Maslow level below threshold, or None."""
        for level in ("survival", "safety", "belonging", "esteem", "actualization"):
            if getattr(self, level) < threshold:
                return level
        return None

    def to_dict(self) -> dict[str, float]:
        return {
            "survival": round(self.survival, 1),
            "safety": round(self.safety, 1),
            "belonging": round(self.belonging, 1),
            "esteem": round(self.esteem, 1),
            "actualization": round(self.actualization, 1),
        }


@dataclass
class Agent:
    """A citizen of the simulated world."""

    id: str
    name: str
    age: int
    traits: list[str]
    occupation: str  # "farmer", "blacksmith", etc. or "none"
    wealth: float = 100.0
    needs: Needs = field(default_factory=Needs)
    inventory: dict[str, int] = field(default_factory=dict)
    relationships: dict[str, float] = field(default_factory=dict)  # id -> affinity (-1..1)
    memory: list[str] = field(default_factory=list)  # recent events
    skills: dict[str, float] = field(default_factory=dict)  # skill -> 0..1
    alive: bool = True
    spouse: str = ""
    children: list[str] = field(default_factory=list)

    def add_memory(self, event: str, max_memories: int = 20) -> None:
        self.memory.append(event)
        if len(self.memory) > max_memories:
            self.memory = self.memory[-max_memories:]

    def summary(self) -> str:
        traits_str = "/".join(self.traits)
        return (
            f"{self.name}(age {self.age}, {self.occupation}, "
            f"traits: {traits_str}, wealth: {self.wealth:.0f}, "
            f"needs: S{self.needs.survival:.0f}/Sa{self.needs.safety:.0f}/"
            f"B{self.needs.belonging:.0f}/E{self.needs.esteem:.0f}/"
            f"A{self.needs.actualization:.0f})"
        )


@dataclass
class GoodDef:
    """Definition of a tradeable good."""

    name: str
    base_price: float
    producers: list[str]  # occupation names that produce this


@dataclass
class MarketListing:
    """A good listed for sale."""

    good: str
    price: float
    seller_id: str
    quantity: int


@dataclass
class Event:
    """A recorded event in the chronicle."""

    year: int
    season: int
    type: str  # "trade", "marriage", "death", "birth", "conflict", "milestone", "random"
    description: str
    agents_involved: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class EconomyStats:
    """Snapshot of economic indicators."""

    gdp: float = 0.0
    total_transactions: int = 0
    total_volume: float = 0.0
    unemployment_rate: float = 0.0
    avg_wealth: float = 0.0
    gini: float = 0.0
    prices: dict[str, float] = field(default_factory=dict)


@dataclass
class World:
    """The entire simulation state."""

    name: str
    year: int = 1
    season: int = 0  # 0=spring, 1=summer, 2=autumn, 3=winter
    agents: dict[str, Agent] = field(default_factory=dict)
    goods: list[GoodDef] = field(default_factory=list)
    market: list[MarketListing] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    economy: EconomyStats = field(default_factory=EconomyStats)
    total_currency: float = 0.0
    tax_rate: float = 0.05
    treasury: float = 0.0
    properties: dict[str, str] = field(default_factory=dict)  # location -> owner_id

    @property
    def season_name(self) -> str:
        return ["spring", "summer", "autumn", "winter"][self.season]

    @property
    def living_agents(self) -> list[Agent]:
        return [a for a in self.agents.values() if a.alive]

    @property
    def population(self) -> int:
        return len(self.living_agents)

    def time_str(self) -> str:
        return f"Year {self.year}, {self.season_name}"
