"""Maslow needs-driven decision engine — no LLM, pure rules."""

from __future__ import annotations

import random

from maxim.models import Agent, World

# Needs decay per tick (season)
DECAY = {
    "survival": -15.0,
    "safety": -5.0,
    "belonging": -8.0,
    "esteem": -3.0,
    "actualization": -2.0,
}


def decay_needs(world: World) -> None:
    """Apply natural needs decay each tick."""
    for agent in world.living_agents:
        for need, delta in DECAY.items():
            current = getattr(agent.needs, need)
            setattr(agent.needs, need, current + delta)
        # Wealth feeds back into survival/safety
        if agent.wealth > 200:
            agent.needs.safety += 3.0
        elif agent.wealth < 20:
            agent.needs.safety -= 5.0
            agent.needs.survival -= 3.0
        # Spouse feeds belonging
        if agent.spouse:
            agent.needs.belonging += 4.0
        agent.needs.clamp()


def decide_intention(agent: Agent, world: World) -> dict:
    """Given needs + world state, return an intention dict."""
    unmet = agent.needs.lowest_unmet(threshold=30.0)

    if unmet == "survival":
        # Need food/shelter → work or buy food
        if agent.inventory.get("food", 0) > 0:
            return {"action": "eat", "reason": "hungry"}
        if agent.wealth > 10:
            return {"action": "buy", "target": "food", "reason": "need to eat"}
        return {"action": "work", "reason": "need money for food"}

    if unmet == "safety":
        # Seek security → save money, form alliance
        friends = [aid for aid, aff in agent.relationships.items() if aff > 0.2]
        if not friends:
            return {"action": "socialize", "reason": "seeking allies for safety"}
        return {"action": "work", "reason": "saving for security"}

    if unmet == "belonging":
        # Lonely → socialize or court
        if not agent.spouse and agent.age >= 18:
            candidates = _marriage_candidates(agent, world)
            if candidates:
                return {"action": "court", "target": candidates[0], "reason": "seeking partner"}
        return {"action": "socialize", "reason": "feeling lonely"}

    if unmet == "esteem":
        # Want respect → trade, teach, take challenge
        best_skill = max(agent.skills, key=agent.skills.get) if agent.skills else None
        if best_skill and agent.skills.get(best_skill, 0) > 0.5:
            return {"action": "teach", "skill": best_skill, "reason": "sharing expertise"}
        return {"action": "work", "reason": "building reputation"}

    if unmet == "actualization":
        return {"action": "create", "reason": "expressing creativity"}

    # All needs met — choose based on personality
    if "ambitious" in agent.traits or "hardworking" in agent.traits:
        return {"action": "work", "reason": "driven to produce"}
    if "social" in agent.traits or "kind" in agent.traits:
        return {"action": "socialize", "reason": "enjoying community"}
    if "curious" in agent.traits:
        return {"action": "explore", "reason": "curious about the world"}

    # Default: weighted random
    actions = ["work", "socialize", "rest", "explore"]
    return {"action": random.choice(actions), "reason": "free time"}


def _marriage_candidates(agent: Agent, world: World) -> list[str]:
    """Find eligible partners with mutual affinity."""
    candidates = []
    for other in world.living_agents:
        if (
            other.id != agent.id
            and not other.spouse
            and 18 <= other.age <= 60
            and agent.relationships.get(other.id, 0) > 0.2
            and other.relationships.get(agent.id, 0) > 0.2
        ):
            candidates.append(other.id)
    return candidates
