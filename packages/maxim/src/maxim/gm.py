"""Game Master — LLM-powered arbitration of agent intentions."""

from __future__ import annotations

import json
import logging
import random

from maxim.models import Agent, Event, World
from maxim import llm

log = logging.getLogger("maxim.gm")

SYSTEM_PROMPT = """\
You are the Game Master of a village simulation. Your job is to arbitrate what happens each season.

You receive:
1. World state (year, season, population, economy).
2. All agent intentions (what each person wants to do).
3. Recent events.

You must return a JSON object with:
{
  "outcomes": [
    {
      "agent_id": "string",
      "success": true/false,
      "detail": "1-2 sentence description of what happened",
      "needs_delta": {"survival": 0, "safety": 0, "belonging": 0, "esteem": 0, "actualization": 0},
      "wealth_delta": 0
    }
  ],
  "random_event": null or {
    "type": "drought|festival|plague|bandit_raid|innovation|trade_caravan|conflict",
    "description": "What happened",
    "affected_agents": ["agent_id1", "agent_id2"],
    "needs_delta": {"survival": 0, "safety": 0, "belonging": 0, "esteem": 0, "actualization": 0}
  },
  "social_changes": [
    {"from": "agent_id", "to": "agent_id", "delta": 0.1, "reason": "string"}
  ],
  "narration": "A 1-2 sentence literary description of the season"
}

Rules:
- Be realistic. Not everyone succeeds every season. Weather, luck, skill all matter.
- Consider agent traits when determining outcomes. A "cautious" farmer prepares better for drought.
- Random events should happen ~20% of seasons. They make the story interesting.
- Create drama: rivalries, unexpected kindness, betrayals, romances.
- Economic constraints are real: agents can't spend more than they have.
- Death and hardship are part of life. Don't make everything happy.
- Keep outcomes SHORT (1-2 sentences each).
"""


def arbitrate(world: World, intentions: dict[str, dict]) -> dict:
    """Call LLM to arbitrate all intentions. Returns parsed result."""
    # Build context
    agents_summary = "\n".join(
        f"- {a.summary()}: wants to {json.dumps(intentions.get(a.id, {}), ensure_ascii=False)}"
        for a in world.living_agents
    )

    recent = world.events[-6:] if world.events else []
    recent_str = "\n".join(f"- [{e.type}] {e.description}" for e in recent) or "(none)"

    user_msg = f"""\
World: {world.name}, {world.time_str()}, population {world.population}
Economy: GDP {world.economy.gdp:.0f}, avg wealth {world.economy.avg_wealth:.0f}, Gini {world.economy.gini:.2f}, unemployment {world.economy.unemployment_rate:.0%}
Treasury: {world.treasury:.0f}

Agents and intentions:
{agents_summary}

Recent events:
{recent_str}

Arbitrate this season. Return JSON."""

    result = llm.call_json(SYSTEM_PROMPT, user_msg, max_tokens=2048)
    return result


def rules_arbitrate(world: World, intentions: dict[str, dict]) -> dict:
    """Fallback: pure-rules arbitration when LLM is unavailable."""
    outcomes = []
    for agent_id, intent in intentions.items():
        agent = world.agents.get(agent_id)
        if not agent or not agent.alive:
            continue

        action = intent.get("action", "rest")
        success = random.random() < 0.7  # 70% success rate

        needs_delta = {}
        wealth_delta = 0.0
        detail = ""

        if action == "work":
            if success:
                wealth_delta = 5.0
                needs_delta = {"survival": 5, "esteem": 2}
                detail = f"{agent.name} had a productive season at work."
            else:
                needs_delta = {"survival": -3}
                detail = f"{agent.name} struggled with work this season."

        elif action == "eat":
            needs_delta = {"survival": 15}
            detail = f"{agent.name} ate well."

        elif action == "socialize":
            needs_delta = {"belonging": 8}
            detail = f"{agent.name} spent time with neighbors."

        elif action == "rest":
            needs_delta = {"survival": 5, "safety": 3}
            detail = f"{agent.name} rested."

        elif action == "court":
            needs_delta = {"belonging": 5}
            detail = f"{agent.name} pursued a romantic interest."

        elif action == "teach":
            needs_delta = {"esteem": 8}
            detail = f"{agent.name} shared knowledge."

        elif action == "create":
            needs_delta = {"actualization": 10, "esteem": 3}
            detail = f"{agent.name} created something."

        elif action == "explore":
            needs_delta = {"actualization": 5}
            detail = f"{agent.name} explored the surroundings."

        elif action == "buy":
            needs_delta = {"survival": 10}
            wealth_delta = -10
            detail = f"{agent.name} bought supplies."

        else:
            detail = f"{agent.name} went about their day."

        outcomes.append({
            "agent_id": agent_id,
            "success": success,
            "detail": detail,
            "needs_delta": needs_delta,
            "wealth_delta": wealth_delta,
        })

    # Random event ~20%
    random_event = None
    if random.random() < 0.2:
        event_type = random.choice(["festival", "drought", "trade_caravan"])
        if event_type == "festival":
            random_event = {
                "type": "festival",
                "description": "The village holds a seasonal celebration.",
                "affected_agents": [a.id for a in world.living_agents],
                "needs_delta": {"belonging": 8, "survival": -2},
            }
        elif event_type == "drought":
            random_event = {
                "type": "drought",
                "description": "A dry spell threatens the harvest.",
                "affected_agents": [a.id for a in world.living_agents if a.occupation == "farmer"],
                "needs_delta": {"survival": -10, "safety": -5},
            }
        elif event_type == "trade_caravan":
            random_event = {
                "type": "trade_caravan",
                "description": "A trade caravan passes through, bringing goods and news.",
                "affected_agents": [a.id for a in world.living_agents if a.occupation == "merchant"],
                "needs_delta": {"esteem": 5, "actualization": 3},
            }

    return {
        "outcomes": outcomes,
        "random_event": random_event,
        "social_changes": [],
        "narration": f"Another {world.season_name} in {world.name}.",
    }


def apply_outcomes(world: World, result: dict) -> list[Event]:
    """Apply GM outcomes to the world state."""
    events: list[Event] = []

    for outcome in result.get("outcomes", []):
        agent = world.agents.get(outcome.get("agent_id", ""))
        if not agent or not agent.alive:
            continue

        # Apply needs delta
        for need, delta in outcome.get("needs_delta", {}).items():
            if hasattr(agent.needs, need):
                current = getattr(agent.needs, need)
                setattr(agent.needs, need, current + delta)

        # Apply wealth delta
        agent.wealth += outcome.get("wealth_delta", 0)
        agent.wealth = max(0.0, agent.wealth)
        agent.needs.clamp()

        # Memory
        detail = outcome.get("detail", "")
        if detail:
            agent.add_memory(detail)

    # Apply random event
    re = result.get("random_event")
    if re:
        for aid in re.get("affected_agents", []):
            agent = world.agents.get(aid)
            if not agent or not agent.alive:
                continue
            for need, delta in re.get("needs_delta", {}).items():
                if hasattr(agent.needs, need):
                    current = getattr(agent.needs, need)
                    setattr(agent.needs, need, current + delta)
            agent.needs.clamp()
            agent.add_memory(re.get("description", ""))

        events.append(
            Event(
                year=world.year,
                season=world.season,
                type=re.get("type", "random"),
                description=re.get("description", ""),
                agents_involved=re.get("affected_agents", []),
            )
        )

    # Apply social changes
    for sc in result.get("social_changes", []):
        a = world.agents.get(sc.get("from", ""))
        b = world.agents.get(sc.get("to", ""))
        if a and b:
            delta = sc.get("delta", 0)
            a.relationships[b.id] = max(-1.0, min(1.0, a.relationships.get(b.id, 0) + delta))

    return events
