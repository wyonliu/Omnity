# omnity-maxim

**Multi-Agent Society Simulator with economics -- the first open-source AI civilization engine.**

Agents don't just chat -- they work, earn, spend, trade, marry, have children, age, and die. Run 100 years of civilization history in 30 minutes for ~$0.40.

## Install

```bash
pip install omnity-maxim
```

Requires `DEEPSEEK_API_KEY` in environment for LLM mode. Without it, use `--no-llm` for rules-only simulation (instant, free).

## Quick Start

```bash
# Rules-only mode (instant, free)
maxim run examples/village.yaml --no-llm

# With LLM Game Master (richer narrative, ~$0.40 for 100 years)
export DEEPSEEK_API_KEY=sk-...
maxim run examples/village.yaml

# Export chronicle + open dashboard
maxim run examples/village.yaml --export chronicle.json
maxim dashboard chronicle.json
```

### Python API

```python
from maxim.config import load_scenario
from maxim.engine import Simulation

# Load a YAML scenario
world, ticks = load_scenario("village.yaml")

# Run the simulation
sim = Simulation(world, use_llm=False)
chronicle = sim.run(ticks)

# Inspect results
print(f"GDP: {world.gdp:.0f}, Gini: {world.gini:.2f}")
for milestone in chronicle.milestones:
    print(f"  Year {milestone.year}: {milestone.text}")

# Export for visualization
chronicle.export("output.json")
```

### CLI

```bash
maxim run <scenario.yaml>                    # full simulation with LLM
maxim run <scenario.yaml> --no-llm           # rules only (fast, free)
maxim run <scenario.yaml> --export out.json  # export chronicle
maxim dashboard out.json                     # interactive web dashboard
```

## API Overview

| Class / Module | What it does |
|----------------|-------------|
| **`Simulation`** | The core engine. Takes a `World` and runs tick-by-tick: needs decay, intention selection, GM arbitration, economy clearing, social events, chronicle recording. Call `sim.run(ticks)` to execute. |
| **`World` / `Agent`** | Data models. Each Agent has Maslow needs, traits, skills, occupation, wealth, relationships, and age. The World tracks GDP, Gini coefficient, treasury, and market state. |
| **`load_scenario()`** | Parses a YAML file into a `(World, ticks)` tuple ready for simulation. |
| **`Chronicle`** | Records every event, auto-detects milestones (first trade, first marriage, economic crisis, population peaks), and exports JSON for the web dashboard. |

## Architecture

```
Agent Needs (Maslow)     -> Rule-based intention selection (zero LLM cost)
     |
Game Master (LLM)        -> Arbitrates all intentions per tick (1 DeepSeek call)
     |
Economy Engine           -> Production, market clearing, wages, tax (pure math)
     |
Social System            -> Relationships, marriage, births, deaths, teaching
     |
Chronicle                -> Auto-detect milestones, export JSON for visualization
```

## Scenario Format

```yaml
name: "Willowbrook Village"
duration_years: 100
initial_currency: 150.0
tax_rate: 0.05

agents:
  - id: farmer_li
    name: "Li Wei"
    age: 25
    traits: [hardworking, cautious, kind]
    occupation: farmer
    skills: {farming: 0.7, cooking: 0.3}

goods:
  - name: food
    base_price: 5
    producers: [farmer, hunter]
```

See [`examples/village.yaml`](examples/village.yaml) for a complete 12-agent village.

## Dashboard

```bash
maxim dashboard chronicle.json
```

Interactive web UI with social network graph, economy charts (GDP + Gini), citizen cards with Maslow radar, event timeline, and playback controls.

## Cost

| Mode | Cost | Speed |
|------|------|-------|
| `--no-llm` | Free | <1 second |
| Default (DeepSeek) | ~$0.40 / 100 years | ~10-15 minutes |

## Part of Omnity

```
SOAP            spatial protocol for 3D environments
  Mindos        persistent multi-layer brain
    Ome           individual AI agent (persona, skills, growth)
      Maxim     <-- you are here
        OmeTown   the integrated world
```

`pip install omnity-soap omnity-mindos omnity-ome omnity-maxim`

## License

[Apache-2.0](../../LICENSE)
