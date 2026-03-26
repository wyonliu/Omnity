"""Load simulation scenarios from YAML."""

from __future__ import annotations

from pathlib import Path

import yaml

from maxim.models import Agent, GoodDef, Needs, World


def load_scenario(path: str | Path) -> tuple[World, int]:
    """Load a YAML scenario file. Returns (world, duration_in_ticks)."""
    with open(path) as f:
        cfg = yaml.safe_load(f)

    world = World(
        name=cfg.get("name", "Unnamed World"),
        year=cfg.get("start_year", 1),
        tax_rate=cfg.get("tax_rate", 0.05),
    )

    initial_wealth = cfg.get("initial_currency", 100.0)

    for ac in cfg.get("agents", []):
        needs_cfg = ac.get("needs", {})
        agent = Agent(
            id=ac["id"],
            name=ac["name"],
            age=ac.get("age", 25),
            traits=ac.get("traits", []),
            occupation=ac.get("occupation", "none"),
            wealth=ac.get("wealth", initial_wealth),
            needs=Needs(
                survival=needs_cfg.get("survival", 50.0),
                safety=needs_cfg.get("safety", 50.0),
                belonging=needs_cfg.get("belonging", 30.0),
                esteem=needs_cfg.get("esteem", 20.0),
                actualization=needs_cfg.get("actualization", 10.0),
            ),
            skills=ac.get("skills", {}),
        )
        world.agents[agent.id] = agent
        world.total_currency += agent.wealth

    for gc in cfg.get("goods", []):
        world.goods.append(
            GoodDef(
                name=gc["name"],
                base_price=gc.get("base_price", 10.0),
                producers=gc.get("producers", []),
            )
        )

    for pc in cfg.get("properties", []):
        world.properties[pc["name"]] = pc.get("owner", "")

    duration_years = cfg.get("duration_years", 100)
    ticks = duration_years * 4  # 4 seasons per year

    return world, ticks
