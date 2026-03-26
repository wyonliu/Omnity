"""Social relationship system — affinity tracking and life events."""

from __future__ import annotations

import random

from maxim.models import Agent, Event, World


def update_from_intentions(world: World, intentions: dict[str, dict]) -> list[Event]:
    """Process social intentions (socialize, court, teach) and generate events."""
    events: list[Event] = []

    for agent_id, intent in intentions.items():
        agent = world.agents.get(agent_id)
        if not agent or not agent.alive:
            continue

        action = intent.get("action")

        if action == "socialize":
            events.extend(_socialize(agent, world))

        elif action == "court":
            target_id = intent.get("target")
            if target_id:
                events.extend(_court(agent, world, target_id))

        elif action == "teach":
            events.extend(_teach(agent, world, intent.get("skill", "")))

    return events


def _socialize(agent: Agent, world: World) -> list[Event]:
    """Agent mingles with random villagers."""
    events = []
    others = [a for a in world.living_agents if a.id != agent.id]
    if not others:
        return events

    partner = random.choice(others)
    delta = 0.05 + random.uniform(0, 0.05)

    # Trait compatibility bonus
    shared = set(agent.traits) & set(partner.traits)
    if shared:
        delta += 0.03 * len(shared)

    agent.relationships[partner.id] = min(1.0, agent.relationships.get(partner.id, 0) + delta)
    partner.relationships[agent.id] = min(1.0, partner.relationships.get(agent.id, 0) + delta * 0.7)

    agent.needs.belonging = min(100.0, agent.needs.belonging + 8.0)
    partner.needs.belonging = min(100.0, partner.needs.belonging + 4.0)

    agent.add_memory(f"Spent time with {partner.name}")
    return events


def _court(agent: Agent, world: World, target_id: str) -> list[Event]:
    """Attempt courtship → marriage if mutual affinity high enough."""
    events = []
    target = world.agents.get(target_id)
    if not target or not target.alive or target.spouse:
        return events

    # Build affinity
    agent.relationships[target_id] = min(1.0, agent.relationships.get(target_id, 0) + 0.1)
    target.relationships[agent.id] = min(1.0, target.relationships.get(agent.id, 0) + 0.05)

    # Marriage check: both need affinity > 0.35
    if (
        agent.relationships.get(target_id, 0) > 0.35
        and target.relationships.get(agent.id, 0) > 0.25
        and random.random() < 0.4
    ):
        agent.spouse = target_id
        target.spouse = agent.id
        agent.needs.belonging = min(100.0, agent.needs.belonging + 25.0)
        target.needs.belonging = min(100.0, target.needs.belonging + 25.0)
        agent.add_memory(f"Married {target.name}")
        target.add_memory(f"Married {agent.name}")
        events.append(
            Event(
                year=world.year,
                season=world.season,
                type="marriage",
                description=f"{agent.name} and {target.name} got married",
                agents_involved=[agent.id, target_id],
            )
        )
    else:
        agent.add_memory(f"Courting {target.name}")

    return events


def _teach(agent: Agent, world: World, skill: str) -> list[Event]:
    """Agent teaches a skill to someone who needs it."""
    if not skill:
        return []

    students = [
        a
        for a in world.living_agents
        if a.id != agent.id and a.skills.get(skill, 0) < agent.skills.get(skill, 0) - 0.2
    ]
    if not students:
        return []

    student = random.choice(students)
    improvement = 0.05 + random.uniform(0, 0.05)
    student.skills[skill] = min(1.0, student.skills.get(skill, 0) + improvement)
    agent.needs.esteem = min(100.0, agent.needs.esteem + 10.0)
    student.needs.esteem = min(100.0, student.needs.esteem + 3.0)

    # Build strong relationship through teaching
    agent.relationships[student.id] = min(1.0, agent.relationships.get(student.id, 0) + 0.08)
    student.relationships[agent.id] = min(1.0, student.relationships.get(agent.id, 0) + 0.12)

    agent.add_memory(f"Taught {skill} to {student.name}")
    student.add_memory(f"Learned {skill} from {agent.name}")
    return []


def check_births(world: World) -> list[Event]:
    """Married couples may have children."""
    events = []
    checked = set()

    for agent in world.living_agents:
        if not agent.spouse or agent.id in checked:
            continue
        spouse = world.agents.get(agent.spouse)
        if not spouse or not spouse.alive:
            continue

        checked.add(agent.id)
        checked.add(spouse.id)

        # 30% chance per year (8% per season), if both under 50
        if agent.age < 50 and spouse.age < 50 and random.random() < 0.08:
            child_id = f"child_{world.year}_{len(world.agents)}"
            # Inherit traits from parents
            parent_traits = list(set(agent.traits + spouse.traits))
            child_traits = random.sample(parent_traits, min(2, len(parent_traits)))
            child = Agent(
                id=child_id,
                name=f"{agent.name.split()[0]}'s child",
                age=0,
                traits=child_traits,
                occupation="none",
                wealth=10.0,
                skills={},
            )
            world.agents[child_id] = child
            agent.children.append(child_id)
            spouse.children.append(child_id)
            agent.needs.belonging = min(100.0, agent.needs.belonging + 15.0)
            spouse.needs.belonging = min(100.0, spouse.needs.belonging + 15.0)
            agent.add_memory(f"Had a child")
            spouse.add_memory(f"Had a child")
            events.append(
                Event(
                    year=world.year,
                    season=world.season,
                    type="birth",
                    description=f"{agent.name} and {spouse.name} had a child",
                    agents_involved=[agent.id, spouse.id, child_id],
                )
            )

    return events


def check_deaths(world: World) -> list[Event]:
    """Age-based death probability."""
    events = []
    for agent in world.living_agents:
        if agent.age < 60:
            continue
        # 5% at 60, +3%/year above
        death_prob = 0.05 + 0.03 * (agent.age - 60)
        # Low survival increases death risk
        if agent.needs.survival < 10:
            death_prob += 0.2

        if random.random() < death_prob / 4:  # per season
            agent.alive = False
            # Distribute wealth to spouse or children
            heirs = []
            if agent.spouse and world.agents.get(agent.spouse, Agent(id="", name="", age=0, traits=[], occupation="")).alive:
                heirs.append(agent.spouse)
            heirs.extend(c for c in agent.children if world.agents.get(c, Agent(id="", name="", age=0, traits=[], occupation="")).alive)
            if heirs:
                share = agent.wealth / len(heirs)
                for h in heirs:
                    world.agents[h].wealth += share
            else:
                world.treasury += agent.wealth

            # Clear spouse
            if agent.spouse:
                s = world.agents.get(agent.spouse)
                if s:
                    s.spouse = ""
                    s.needs.belonging -= 20.0
                    s.add_memory(f"Lost spouse {agent.name}")

            events.append(
                Event(
                    year=world.year,
                    season=world.season,
                    type="death",
                    description=f"{agent.name} passed away at age {agent.age}",
                    agents_involved=[agent.id],
                )
            )

    return events


def age_agents(world: World) -> None:
    """Age all agents by 1 year (call once per year = every 4 ticks)."""
    for agent in world.living_agents:
        agent.age += 1
        # Children come of age at 15: assign occupation
        if agent.age == 15 and agent.occupation == "none":
            occupations = list({g.producers[0] for g in world.goods if g.producers})
            if occupations:
                agent.occupation = random.choice(occupations)
                agent.skills[agent.occupation] = 0.3 + random.uniform(0, 0.2)
                agent.add_memory(f"Started working as {agent.occupation}")
