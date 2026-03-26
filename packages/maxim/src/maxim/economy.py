"""Economic engine — production, market, trade, macro metrics."""

from __future__ import annotations

import math
from collections import defaultdict

from maxim.models import Agent, EconomyStats, MarketListing, World


def produce(world: World) -> None:
    """Agents produce goods based on occupation and skill."""
    for agent in world.living_agents:
        if agent.occupation == "none":
            continue
        for good in world.goods:
            if agent.occupation in good.producers:
                skill = agent.skills.get(agent.occupation.replace(" ", ""), 0.5)
                # Base output: 2 units, scaled by skill
                qty = max(1, int(2 * (0.5 + skill)))
                agent.inventory[good.name] = agent.inventory.get(good.name, 0) + qty
                # Skill slowly improves
                old = agent.skills.get(agent.occupation, 0.5)
                agent.skills[agent.occupation] = min(1.0, old + 0.005)


def list_goods(world: World) -> None:
    """Agents list surplus goods on the market."""
    world.market.clear()
    for agent in world.living_agents:
        for good_name, qty in list(agent.inventory.items()):
            if qty <= 0:
                continue
            # Keep 1 unit for self-consumption, sell the rest
            sell_qty = max(0, qty - 1)
            if sell_qty <= 0:
                continue
            base = _base_price(world, good_name)
            # Price: base * (1 + markup based on scarcity)
            supply = _total_supply(world, good_name)
            demand = world.population  # everyone needs basics
            scarcity = max(0.5, min(3.0, demand / max(1, supply)))
            price = base * scarcity
            world.market.append(
                MarketListing(
                    good=good_name,
                    price=round(price, 1),
                    seller_id=agent.id,
                    quantity=sell_qty,
                )
            )


def consume(world: World) -> dict[str, list[str]]:
    """Agents buy necessities. Returns {agent_id: [purchase descriptions]}."""
    purchases: dict[str, list[str]] = defaultdict(list)

    # Sort agents by urgency (lowest survival first)
    buyers = sorted(world.living_agents, key=lambda a: a.needs.survival)

    for agent in buyers:
        # Buy food if survival < 60
        if agent.needs.survival < 60 and agent.wealth > 0:
            _try_buy(world, agent, "food", purchases)

    return dict(purchases)


def _try_buy(
    world: World, agent: Agent, good_name: str, purchases: dict[str, list[str]]
) -> bool:
    """Try to buy one unit of a good from the cheapest listing."""
    available = sorted(
        [m for m in world.market if m.good == good_name and m.quantity > 0],
        key=lambda m: m.price,
    )
    if not available:
        return False

    listing = available[0]
    if agent.wealth < listing.price:
        return False

    # Transaction
    seller = world.agents.get(listing.seller_id)
    if not seller:
        return False

    agent.wealth -= listing.price
    seller.wealth += listing.price * (1 - world.tax_rate)
    world.treasury += listing.price * world.tax_rate
    listing.quantity -= 1
    agent.inventory[good_name] = agent.inventory.get(good_name, 0) + 1

    # Track
    world.economy.total_transactions += 1
    world.economy.total_volume += listing.price
    purchases[agent.id].append(f"bought {good_name} for {listing.price:.1f} from {seller.name}")

    # Social: trading builds mild trust
    agent.relationships[seller.id] = min(1.0, agent.relationships.get(seller.id, 0) + 0.02)
    seller.relationships[agent.id] = min(1.0, seller.relationships.get(agent.id, 0) + 0.02)

    return True


def consume_inventory(world: World) -> None:
    """Agents consume food from inventory to satisfy survival."""
    for agent in world.living_agents:
        food = agent.inventory.get("food", 0)
        if food > 0:
            agent.inventory["food"] = food - 1
            agent.needs.survival = min(100.0, agent.needs.survival + 20.0)


def spoil_goods(world: World) -> None:
    """Food spoils: -50% per tick. Other goods persist."""
    for agent in world.living_agents:
        food = agent.inventory.get("food", 0)
        if food > 2:
            agent.inventory["food"] = max(1, food // 2)


def pay_wages(world: World) -> None:
    """Employed agents earn base wages (from treasury or currency injection)."""
    for agent in world.living_agents:
        if agent.occupation != "none":
            skill = max(0.3, agent.skills.get(agent.occupation, 0.5))
            wage = 10.0 * skill
            agent.wealth += wage
            world.total_currency += wage  # mild inflation
            agent.needs.survival += 5.0
            agent.needs.safety += 2.0
            agent.needs.esteem += 1.0


def calculate_stats(world: World) -> None:
    """Update GDP, Gini, unemployment, prices."""
    living = world.living_agents
    if not living:
        return

    wealths = [a.wealth for a in living]
    world.economy.avg_wealth = sum(wealths) / len(wealths)
    world.economy.gini = _gini(wealths)
    unemployed = sum(1 for a in living if a.occupation == "none")
    world.economy.unemployment_rate = unemployed / len(living)

    # Prices snapshot
    for good in world.goods:
        listings = [m for m in world.market if m.good == good.name and m.quantity > 0]
        if listings:
            world.economy.prices[good.name] = sum(m.price for m in listings) / len(listings)
        else:
            world.economy.prices[good.name] = good.base_price

    # GDP = total transaction volume this tick
    world.economy.gdp = world.economy.total_volume


def reset_tick_stats(world: World) -> None:
    """Reset per-tick counters."""
    world.economy.total_transactions = 0
    world.economy.total_volume = 0.0
    world.economy.gdp = 0.0


def _base_price(world: World, good_name: str) -> float:
    for g in world.goods:
        if g.name == good_name:
            return g.base_price
    return 10.0


def _total_supply(world: World, good_name: str) -> int:
    return sum(a.inventory.get(good_name, 0) for a in world.living_agents)


def _gini(wealths: list[float]) -> float:
    """Calculate Gini coefficient (0=equal, 1=all wealth in one hand)."""
    if not wealths or len(wealths) < 2:
        return 0.0
    sorted_w = sorted(wealths)
    n = len(sorted_w)
    total = sum(sorted_w)
    if total == 0:
        return 0.0
    cum = sum((2 * (i + 1) - n - 1) * w for i, w in enumerate(sorted_w))
    return cum / (n * total)
