"""Simulation engine — the core loop that drives everything."""

from __future__ import annotations

import logging
import time
from typing import Callable

from maxim.models import World
from maxim.needs import decay_needs, decide_intention
from maxim.economy import (
    produce, list_goods, consume, consume_inventory, spoil_goods,
    pay_wages, calculate_stats, reset_tick_stats,
)
from maxim.social import (
    update_from_intentions, check_births, check_deaths, age_agents,
)
from maxim.gm import arbitrate, rules_arbitrate, apply_outcomes
from maxim.chronicle import Chronicle

log = logging.getLogger("maxim")


class Simulation:
    """Runs the world tick by tick."""

    def __init__(self, world: World, use_llm: bool = True):
        self.world = world
        self.use_llm = use_llm
        self.chronicle = Chronicle()
        self.tick_count = 0
        self._on_tick: Callable | None = None

    def on_tick(self, callback: Callable[[World, int, str], None]) -> None:
        """Register a callback: fn(world, tick_number, narration)."""
        self._on_tick = callback

    def run(self, ticks: int) -> Chronicle:
        """Run the simulation for N ticks. Returns the chronicle."""
        log.info("Starting simulation: %s, %d ticks (%d years)",
                 self.world.name, ticks, ticks // 4)
        self.chronicle.snapshot(self.world)

        for t in range(ticks):
            narration = self.tick()
            self.tick_count += 1

            if self._on_tick:
                self._on_tick(self.world, self.tick_count, narration)

            # Snapshot every 4 ticks (1 year)
            if self.tick_count % 4 == 0:
                self.chronicle.snapshot(self.world)

            # Stop if everyone is dead
            if self.world.population == 0:
                log.info("All agents have perished at %s", self.world.time_str())
                break

        self.chronicle.snapshot(self.world)
        return self.chronicle

    def tick(self) -> str:
        """Advance the world by one season. Returns narration string."""
        world = self.world
        narration = ""

        # 0. Reset per-tick stats
        reset_tick_stats(world)

        # 1. Age agents (once per year, at spring)
        if world.season == 0:
            age_agents(world)

        # 2. Decay needs
        decay_needs(world)

        # 3. Each agent decides intention (rule-based, no LLM)
        intentions: dict[str, dict] = {}
        for agent in world.living_agents:
            intentions[agent.id] = decide_intention(agent, world)

        # 4. GM arbitrates (1 LLM call OR rules fallback)
        if self.use_llm:
            try:
                result = arbitrate(world, intentions)
                if not result.get("outcomes"):
                    # LLM returned empty/bad JSON → fallback
                    result = rules_arbitrate(world, intentions)
            except Exception as e:
                log.warning("GM LLM failed, using rules: %s", e)
                result = rules_arbitrate(world, intentions)
        else:
            result = rules_arbitrate(world, intentions)

        # 5. Apply GM outcomes
        gm_events = apply_outcomes(world, result)
        self.chronicle.log_events(gm_events)
        narration = result.get("narration", "")

        # 6. Process social intentions (socialize, court, teach)
        social_events = update_from_intentions(world, intentions)
        self.chronicle.log_events(social_events)

        # 7. Economy: produce, list, trade, consume
        produce(world)
        list_goods(world)
        purchases = consume(world)
        consume_inventory(world)
        spoil_goods(world)
        pay_wages(world)
        calculate_stats(world)

        # 8. Life events: births and deaths
        birth_events = check_births(world)
        death_events = check_deaths(world)
        self.chronicle.log_events(birth_events)
        self.chronicle.log_events(death_events)
        world.events.extend(gm_events + social_events + birth_events + death_events)

        # 9. Chronicle tick
        self.chronicle.log_tick(world, narration)

        # 10. Advance clock
        world.season = (world.season + 1) % 4
        if world.season == 0:
            world.year += 1

        return narration
