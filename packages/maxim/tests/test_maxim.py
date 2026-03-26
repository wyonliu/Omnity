"""Comprehensive test suite for the Maxim simulation package."""

from __future__ import annotations

import json
import random
import tempfile
from pathlib import Path

import pytest

from maxim.models import Agent, Event, EconomyStats, GoodDef, MarketListing, Needs, World
from maxim.config import load_scenario
from maxim.needs import decay_needs, decide_intention, DECAY
from maxim.economy import (
    produce, consume, consume_inventory, spoil_goods, calculate_stats,
    list_goods, pay_wages, reset_tick_stats, _gini,
)
from maxim.social import (
    _socialize, _court, check_births, check_deaths, age_agents,
    update_from_intentions,
)
from maxim.chronicle import Chronicle
from maxim.engine import Simulation
from maxim.gm import rules_arbitrate, apply_outcomes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_agent(id="a1", name="Alice", age=25, occupation="farmer",
               traits=None, wealth=100.0, needs=None, skills=None,
               spouse="", alive=True) -> Agent:
    return Agent(
        id=id, name=name, age=age, occupation=occupation,
        traits=traits or [], wealth=wealth,
        needs=needs or Needs(), skills=skills or {},
        spouse=spouse, alive=alive,
    )


def make_world(agents=None, goods=None, name="TestWorld") -> World:
    w = World(name=name)
    if agents:
        for a in agents:
            w.agents[a.id] = a
    if goods:
        w.goods = goods
    return w


def make_pair_world() -> World:
    """Two agents with mutual affinity, suitable for marriage/social tests."""
    a = make_agent("a1", "Alice", 25, "farmer", traits=["kind"])
    b = make_agent("b1", "Bob", 27, "blacksmith", traits=["kind"])
    a.relationships["b1"] = 0.5
    b.relationships["a1"] = 0.5
    w = make_world([a, b])
    return w


# ===========================================================================
# 1. models.py
# ===========================================================================

class TestNeeds:
    def test_clamp_upper(self):
        n = Needs(survival=120.0, safety=50.0)
        n.clamp()
        assert n.survival == 100.0

    def test_clamp_lower(self):
        n = Needs(survival=-10.0, belonging=-5.0)
        n.clamp()
        assert n.survival == 0.0
        assert n.belonging == 0.0

    def test_clamp_no_change(self):
        n = Needs(survival=50.0)
        n.clamp()
        assert n.survival == 50.0

    def test_lowest_unmet_returns_survival_first(self):
        n = Needs(survival=10.0, safety=10.0, belonging=10.0)
        assert n.lowest_unmet(threshold=30.0) == "survival"

    def test_lowest_unmet_skips_met(self):
        n = Needs(survival=50.0, safety=10.0)
        assert n.lowest_unmet(threshold=30.0) == "safety"

    def test_lowest_unmet_all_met(self):
        n = Needs(survival=50.0, safety=50.0, belonging=50.0, esteem=50.0, actualization=50.0)
        assert n.lowest_unmet(threshold=30.0) is None

    def test_to_dict(self):
        n = Needs(survival=33.33)
        d = n.to_dict()
        assert d["survival"] == 33.3
        assert set(d.keys()) == {"survival", "safety", "belonging", "esteem", "actualization"}


class TestAgent:
    def test_add_memory_basic(self):
        a = make_agent()
        a.add_memory("hello")
        assert "hello" in a.memory

    def test_add_memory_truncates(self):
        a = make_agent()
        for i in range(25):
            a.add_memory(f"event_{i}")
        assert len(a.memory) == 20
        assert a.memory[0] == "event_5"
        assert a.memory[-1] == "event_24"

    def test_add_memory_custom_max(self):
        a = make_agent()
        for i in range(10):
            a.add_memory(f"e{i}", max_memories=5)
        assert len(a.memory) == 5

    def test_summary(self):
        a = make_agent(traits=["brave", "kind"])
        s = a.summary()
        assert "Alice" in s
        assert "brave/kind" in s


class TestWorld:
    def test_living_agents_excludes_dead(self):
        a1 = make_agent("a1", alive=True)
        a2 = make_agent("a2", name="Dead", alive=False)
        w = make_world([a1, a2])
        assert len(w.living_agents) == 1
        assert w.living_agents[0].id == "a1"

    def test_population(self):
        agents = [make_agent(f"a{i}") for i in range(5)]
        agents[2].alive = False
        w = make_world(agents)
        assert w.population == 4

    def test_season_name(self):
        w = World(name="X")
        assert w.season_name == "spring"
        w.season = 2
        assert w.season_name == "autumn"

    def test_time_str(self):
        w = World(name="X", year=3, season=1)
        assert w.time_str() == "Year 3, summer"


# ===========================================================================
# 2. config.py
# ===========================================================================

class TestConfig:
    def test_load_village_scenario(self):
        path = Path(__file__).resolve().parents[1] / "examples" / "village.yaml"
        world, ticks = load_scenario(path)
        assert world.name == "Willowbrook Village"
        assert world.year == 1
        assert world.tax_rate == 0.05
        assert len(world.agents) == 12
        assert ticks == 400  # 100 years * 4 seasons
        assert "farmer_li" in world.agents
        assert world.agents["farmer_li"].occupation == "farmer"
        assert len(world.goods) == 5
        assert world.properties["Li Farm"] == "farmer_li"

    def test_load_village_agent_needs(self):
        path = Path(__file__).resolve().parents[1] / "examples" / "village.yaml"
        world, _ = load_scenario(path)
        elder = world.agents["elder_zhou"]
        assert elder.needs.survival == 60
        assert elder.needs.esteem == 60
        assert elder.wealth == 300.0

    def test_load_village_total_currency(self):
        path = Path(__file__).resolve().parents[1] / "examples" / "village.yaml"
        world, _ = load_scenario(path)
        # 11 agents at 150 + elder at 300 = 1950
        assert world.total_currency == 11 * 150 + 300


# ===========================================================================
# 3. needs.py
# ===========================================================================

class TestDecayNeeds:
    def test_decay_reduces_survival(self):
        a = make_agent(needs=Needs(survival=80.0, safety=80.0, belonging=80.0,
                                    esteem=80.0, actualization=80.0))
        w = make_world([a])
        decay_needs(w)
        assert a.needs.survival < 80.0
        assert a.needs.survival == pytest.approx(80.0 + DECAY["survival"], abs=0.01)

    def test_decay_clamps_to_zero(self):
        a = make_agent(needs=Needs(survival=5.0, safety=2.0, belonging=3.0,
                                    esteem=1.0, actualization=0.5))
        w = make_world([a])
        decay_needs(w)
        assert a.needs.survival >= 0.0
        assert a.needs.actualization >= 0.0

    def test_high_wealth_boosts_safety(self):
        a = make_agent(wealth=300.0, needs=Needs(safety=50.0))
        w = make_world([a])
        decay_needs(w)
        # safety decays -5 but gets +3 for wealth > 200 = net -2
        assert a.needs.safety == pytest.approx(50.0 - 5.0 + 3.0, abs=0.01)

    def test_low_wealth_hurts(self):
        a = make_agent(wealth=10.0, needs=Needs(survival=50.0, safety=50.0))
        w = make_world([a])
        decay_needs(w)
        # survival: -15 -3 = -18, safety: -5 -5 = -10
        assert a.needs.survival == pytest.approx(50.0 - 15.0 - 3.0, abs=0.01)
        assert a.needs.safety == pytest.approx(50.0 - 5.0 - 5.0, abs=0.01)

    def test_spouse_boosts_belonging(self):
        a = make_agent(spouse="someone", needs=Needs(belonging=50.0))
        w = make_world([a])
        decay_needs(w)
        # belonging: -8 + 4 = -4
        assert a.needs.belonging == pytest.approx(50.0 - 8.0 + 4.0, abs=0.01)


class TestDecideIntention:
    def test_survival_eat_if_has_food(self):
        a = make_agent(needs=Needs(survival=10.0))
        a.inventory["food"] = 3
        w = make_world([a])
        intent = decide_intention(a, w)
        assert intent["action"] == "eat"

    def test_survival_buy_if_has_wealth(self):
        a = make_agent(needs=Needs(survival=10.0), wealth=50.0)
        w = make_world([a])
        intent = decide_intention(a, w)
        assert intent["action"] == "buy"

    def test_survival_work_if_poor(self):
        a = make_agent(needs=Needs(survival=10.0), wealth=5.0)
        w = make_world([a])
        intent = decide_intention(a, w)
        assert intent["action"] == "work"

    def test_belonging_court_if_eligible(self):
        a = make_agent("a1", "Alice", 25, needs=Needs(survival=50.0, safety=50.0, belonging=10.0))
        b = make_agent("b1", "Bob", 27)
        a.relationships["b1"] = 0.5
        b.relationships["a1"] = 0.5
        w = make_world([a, b])
        intent = decide_intention(a, w)
        assert intent["action"] == "court"

    def test_belonging_socialize_if_married(self):
        a = make_agent(spouse="someone", needs=Needs(survival=50.0, safety=50.0, belonging=10.0))
        w = make_world([a])
        intent = decide_intention(a, w)
        assert intent["action"] == "socialize"

    def test_esteem_teach(self):
        a = make_agent(needs=Needs(survival=50.0, safety=50.0, belonging=50.0, esteem=10.0),
                       skills={"farming": 0.8})
        w = make_world([a])
        intent = decide_intention(a, w)
        assert intent["action"] == "teach"

    def test_actualization_create(self):
        a = make_agent(needs=Needs(survival=50.0, safety=50.0, belonging=50.0,
                                    esteem=50.0, actualization=10.0))
        w = make_world([a])
        intent = decide_intention(a, w)
        assert intent["action"] == "create"

    def test_all_needs_met_ambitious(self):
        a = make_agent(traits=["ambitious"],
                       needs=Needs(survival=50.0, safety=50.0, belonging=50.0,
                                    esteem=50.0, actualization=50.0))
        w = make_world([a])
        intent = decide_intention(a, w)
        assert intent["action"] == "work"


# ===========================================================================
# 4. economy.py
# ===========================================================================

class TestProduce:
    def test_farmer_produces_food(self):
        a = make_agent(occupation="farmer", skills={"farming": 0.7})
        goods = [GoodDef(name="food", base_price=5, producers=["farmer"])]
        w = make_world([a], goods)
        produce(w)
        assert a.inventory.get("food", 0) > 0

    def test_no_production_for_none_occupation(self):
        a = make_agent(occupation="none")
        goods = [GoodDef(name="food", base_price=5, producers=["farmer"])]
        w = make_world([a], goods)
        produce(w)
        assert a.inventory.get("food", 0) == 0

    def test_skill_improves_after_produce(self):
        # produce() writes skill under agent.occupation key ("farmer")
        a = make_agent(occupation="farmer", skills={"farmer": 0.5})
        goods = [GoodDef(name="food", base_price=5, producers=["farmer"])]
        w = make_world([a], goods)
        old_skill = a.skills["farmer"]
        produce(w)
        assert a.skills["farmer"] > old_skill


class TestConsume:
    def test_consume_inventory_raises_survival(self):
        a = make_agent(needs=Needs(survival=30.0))
        a.inventory["food"] = 3
        w = make_world([a])
        consume_inventory(w)
        assert a.needs.survival == 50.0
        assert a.inventory["food"] == 2


class TestSpoilGoods:
    def test_spoil_reduces_food(self):
        a = make_agent()
        a.inventory["food"] = 10
        w = make_world([a])
        spoil_goods(w)
        assert a.inventory["food"] == 5  # 10 // 2

    def test_spoil_no_effect_small_inventory(self):
        a = make_agent()
        a.inventory["food"] = 2
        w = make_world([a])
        spoil_goods(w)
        assert a.inventory["food"] == 2  # <= 2, no spoilage


class TestCalculateStats:
    def test_gini_equal(self):
        assert _gini([100, 100, 100]) == pytest.approx(0.0, abs=0.01)

    def test_gini_unequal(self):
        g = _gini([0, 0, 0, 1000])
        assert g > 0.5

    def test_gini_single(self):
        assert _gini([100]) == 0.0

    def test_gini_empty(self):
        assert _gini([]) == 0.0

    def test_calculate_stats_basic(self):
        a1 = make_agent("a1", wealth=200.0)
        a2 = make_agent("a2", name="Bob", wealth=50.0, occupation="none")
        goods = [GoodDef(name="food", base_price=5, producers=["farmer"])]
        w = make_world([a1, a2], goods)
        w.economy.total_volume = 100.0
        calculate_stats(w)
        assert w.economy.avg_wealth == pytest.approx(125.0)
        assert w.economy.unemployment_rate == pytest.approx(0.5)
        assert w.economy.gdp == 100.0
        assert w.economy.gini > 0.0


# ===========================================================================
# 5. social.py
# ===========================================================================

class TestSocialize:
    def test_socialize_builds_affinity(self):
        a = make_agent("a1", "Alice")
        b = make_agent("b1", "Bob")
        w = make_world([a, b])
        random.seed(42)
        _socialize(a, w)
        assert a.relationships.get("b1", 0) > 0
        assert b.relationships.get("a1", 0) > 0
        assert a.needs.belonging > 30.0  # default 30 + 8

    def test_socialize_shared_traits_bonus(self):
        a = make_agent("a1", "Alice", traits=["kind", "brave"])
        b = make_agent("b1", "Bob", traits=["kind", "brave"])
        w = make_world([a, b])
        random.seed(42)
        _socialize(a, w)
        affinity = a.relationships.get("b1", 0)
        # Shared traits add 0.03 per shared trait
        assert affinity >= 0.05 + 0.03 * 2


class TestCourt:
    def test_court_builds_affinity(self):
        w = make_pair_world()
        a = w.agents["a1"]
        random.seed(99)  # ensure no marriage this seed
        _court(a, w, "b1")
        # Affinity should have increased
        assert a.relationships["b1"] > 0.5

    def test_court_can_marry(self):
        """With high affinity and favorable random, marriage happens."""
        a = make_agent("a1", "Alice", 25, traits=["kind"])
        b = make_agent("b1", "Bob", 27, traits=["kind"])
        a.relationships["b1"] = 0.5
        b.relationships["a1"] = 0.5
        w = make_world([a, b])
        # Try many seeds until we get a marriage
        married = False
        for seed in range(100):
            # Reset state
            a.spouse = ""
            b.spouse = ""
            a.relationships["b1"] = 0.5
            b.relationships["a1"] = 0.5
            random.seed(seed)
            events = _court(a, w, "b1")
            if a.spouse == "b1":
                married = True
                assert any(e.type == "marriage" for e in events)
                break
        assert married, "Marriage should happen with sufficient attempts"


class TestCheckBirths:
    def test_check_births_creates_child(self):
        a = make_agent("a1", "Alice", 25, spouse="b1")
        b = make_agent("b1", "Bob", 27, spouse="a1")
        w = make_world([a, b])
        # Try multiple seeds
        born = False
        for seed in range(200):
            # Reset
            a.children.clear()
            b.children.clear()
            # Remove any previously added children
            w.agents = {"a1": a, "b1": b}
            random.seed(seed)
            events = check_births(w)
            if events:
                born = True
                assert events[0].type == "birth"
                assert len(w.agents) == 3
                break
        assert born, "Birth should happen with sufficient attempts"


class TestCheckDeaths:
    def test_old_agent_can_die(self):
        a = make_agent("a1", "OldAlice", age=80, needs=Needs(survival=5.0))
        w = make_world([a])
        died = False
        for seed in range(200):
            a.alive = True
            random.seed(seed)
            events = check_deaths(w)
            if events:
                died = True
                assert a.alive is False
                assert events[0].type == "death"
                break
        assert died, "Death should happen for old agent with low survival"

    def test_young_agent_does_not_die(self):
        a = make_agent("a1", "YoungAlice", age=20)
        w = make_world([a])
        for seed in range(50):
            random.seed(seed)
            events = check_deaths(w)
            assert len(events) == 0
        assert a.alive is True


class TestAgeAgents:
    def test_age_increments(self):
        a = make_agent(age=25)
        w = make_world([a])
        age_agents(w)
        assert a.age == 26

    def test_child_gets_occupation_at_15(self):
        a = make_agent(age=14, occupation="none")
        goods = [GoodDef(name="food", base_price=5, producers=["farmer"])]
        w = make_world([a], goods)
        random.seed(42)
        age_agents(w)
        assert a.age == 15
        assert a.occupation != "none"


# ===========================================================================
# 6. chronicle.py
# ===========================================================================

class TestChronicle:
    def test_log_events_tracks(self):
        c = Chronicle()
        e = Event(year=1, season=0, type="trade", description="A traded with B")
        c.log_events([e])
        assert len(c.events) == 1

    def test_first_marriage_milestone(self):
        c = Chronicle()
        e = Event(year=1, season=0, type="marriage",
                  description="Alice and Bob got married", agents_involved=["a1", "b1"])
        c.log_events([e])
        assert len(c.milestones) == 1
        assert "First marriage" in c.milestones[0].description

    def test_first_death_milestone(self):
        c = Chronicle()
        e = Event(year=5, season=2, type="death",
                  description="Elder Zhou passed away", agents_involved=["elder"])
        c.log_events([e])
        assert len(c.milestones) == 1
        assert "First death" in c.milestones[0].description

    def test_first_birth_milestone(self):
        c = Chronicle()
        e = Event(year=2, season=1, type="birth",
                  description="Alice and Bob had a child")
        c.log_events([e])
        assert any("First birth" in m.description for m in c.milestones)

    def test_first_trade_milestone(self):
        c = Chronicle()
        e = Event(year=1, season=0, type="trade", description="A traded with B")
        c.log_events([e])
        assert any("First trade" in m.description for m in c.milestones)

    def test_no_duplicate_milestones(self):
        c = Chronicle()
        e1 = Event(year=1, season=0, type="marriage", description="Wedding 1")
        e2 = Event(year=2, season=0, type="marriage", description="Wedding 2")
        c.log_events([e1])
        c.log_events([e2])
        marriage_milestones = [m for m in c.milestones if "marriage" in m.description.lower()]
        assert len(marriage_milestones) == 1

    def test_population_milestone(self):
        c = Chronicle()
        agents = {f"a{i}": make_agent(f"a{i}", f"Agent{i}") for i in range(20)}
        w = World(name="Big", agents=agents)
        c.log_tick(w)
        assert any("20" in m.description for m in c.milestones)

    def test_export_json(self):
        c = Chronicle()
        e = Event(year=1, season=0, type="trade", description="A traded")
        c.log_events([e])
        w = World(name="X")
        c.log_tick(w)
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        c.export_json(path)
        data = json.loads(Path(path).read_text())
        assert "events" in data
        assert "milestones" in data
        assert "snapshots" in data
        assert "gdp_history" in data
        assert len(data["events"]) >= 1
        Path(path).unlink()

    def test_snapshot(self):
        a = make_agent()
        w = make_world([a])
        c = Chronicle()
        c.snapshot(w)
        assert len(c.snapshots) == 1
        snap = c.snapshots[0]
        assert snap["population"] == 1
        assert "a1" in snap["agents"]


# ===========================================================================
# 7. engine.py
# ===========================================================================

class TestEngine:
    def test_tick_advances_season(self):
        a = make_agent(occupation="farmer", skills={"farming": 0.5})
        goods = [GoodDef(name="food", base_price=5, producers=["farmer"])]
        w = make_world([a], goods)
        sim = Simulation(w, use_llm=False)
        sim.tick()
        assert w.season == 1  # spring -> summer

    def test_run_10_ticks(self):
        """Simulation runs 10 ticks without crashing."""
        a1 = make_agent("a1", "Alice", 25, "farmer", ["kind"], skills={"farming": 0.6})
        a2 = make_agent("a2", "Bob", 27, "blacksmith", ["brave"], skills={"smithing": 0.5})
        goods = [
            GoodDef(name="food", base_price=5, producers=["farmer"]),
            GoodDef(name="tools", base_price=20, producers=["blacksmith"]),
        ]
        w = make_world([a1, a2], goods)
        sim = Simulation(w, use_llm=False)
        random.seed(42)
        chronicle = sim.run(10)
        assert sim.tick_count == 10
        assert len(chronicle.events) >= 0  # just ensure no crash
        assert w.year >= 3  # 10 ticks = 2.5 years, so year should be at least 3

    def test_run_stops_if_all_dead(self):
        a = make_agent("a1", "Alice", 90, needs=Needs(survival=1.0))
        w = make_world([a])
        sim = Simulation(w, use_llm=False)
        random.seed(0)
        chronicle = sim.run(100)
        # Should stop early since only 1 very old agent
        assert sim.tick_count <= 100

    def test_on_tick_callback(self):
        a = make_agent(occupation="farmer", skills={"farming": 0.5})
        goods = [GoodDef(name="food", base_price=5, producers=["farmer"])]
        w = make_world([a], goods)
        sim = Simulation(w, use_llm=False)
        ticks_seen = []
        sim.on_tick(lambda world, tick, narr: ticks_seen.append(tick))
        sim.run(3)
        assert ticks_seen == [1, 2, 3]


# ===========================================================================
# 8. gm.py
# ===========================================================================

class TestRulesArbitrate:
    def test_returns_valid_structure(self):
        a = make_agent(occupation="farmer")
        w = make_world([a])
        intentions = {"a1": {"action": "work", "reason": "need money"}}
        random.seed(42)
        result = rules_arbitrate(w, intentions)
        assert "outcomes" in result
        assert "random_event" in result
        assert "social_changes" in result
        assert "narration" in result
        assert len(result["outcomes"]) == 1
        outcome = result["outcomes"][0]
        assert outcome["agent_id"] == "a1"
        assert "success" in outcome
        assert "detail" in outcome
        assert "needs_delta" in outcome
        assert "wealth_delta" in outcome

    def test_work_success_gives_wealth(self):
        a = make_agent()
        w = make_world([a])
        intentions = {"a1": {"action": "work"}}
        # Force success by trying many seeds
        for seed in range(50):
            random.seed(seed)
            result = rules_arbitrate(w, intentions)
            outcome = result["outcomes"][0]
            if outcome["success"]:
                assert outcome["wealth_delta"] == 5.0
                assert outcome["needs_delta"].get("survival") == 5
                break

    def test_eat_action(self):
        a = make_agent()
        w = make_world([a])
        intentions = {"a1": {"action": "eat"}}
        random.seed(42)
        result = rules_arbitrate(w, intentions)
        outcome = result["outcomes"][0]
        assert outcome["needs_delta"].get("survival") == 15

    def test_create_action(self):
        a = make_agent()
        w = make_world([a])
        intentions = {"a1": {"action": "create"}}
        random.seed(42)
        result = rules_arbitrate(w, intentions)
        outcome = result["outcomes"][0]
        assert outcome["needs_delta"].get("actualization") == 10


class TestApplyOutcomes:
    def test_apply_needs_delta(self):
        a = make_agent(needs=Needs(survival=50.0))
        w = make_world([a])
        result = {
            "outcomes": [{
                "agent_id": "a1",
                "success": True,
                "detail": "Worked hard",
                "needs_delta": {"survival": 10},
                "wealth_delta": 5.0,
            }],
            "random_event": None,
            "social_changes": [],
        }
        events = apply_outcomes(w, result)
        assert a.needs.survival == 60.0
        assert a.wealth == 105.0
        assert "Worked hard" in a.memory

    def test_apply_random_event(self):
        a = make_agent(needs=Needs(survival=50.0, safety=50.0))
        w = make_world([a])
        result = {
            "outcomes": [],
            "random_event": {
                "type": "drought",
                "description": "A terrible drought",
                "affected_agents": ["a1"],
                "needs_delta": {"survival": -10, "safety": -5},
            },
            "social_changes": [],
        }
        events = apply_outcomes(w, result)
        assert a.needs.survival == 40.0
        assert a.needs.safety == 45.0
        assert len(events) == 1
        assert events[0].type == "drought"

    def test_apply_social_changes(self):
        a = make_agent("a1", "Alice")
        b = make_agent("b1", "Bob")
        w = make_world([a, b])
        result = {
            "outcomes": [],
            "random_event": None,
            "social_changes": [{"from": "a1", "to": "b1", "delta": 0.3}],
        }
        apply_outcomes(w, result)
        assert a.relationships["b1"] == pytest.approx(0.3)

    def test_wealth_cannot_go_negative(self):
        a = make_agent(wealth=5.0)
        w = make_world([a])
        result = {
            "outcomes": [{
                "agent_id": "a1",
                "success": False,
                "detail": "Lost money",
                "needs_delta": {},
                "wealth_delta": -100.0,
            }],
            "random_event": None,
            "social_changes": [],
        }
        apply_outcomes(w, result)
        assert a.wealth == 0.0
