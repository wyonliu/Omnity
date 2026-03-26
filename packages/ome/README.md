# omnity-ome

**Your AI twin -- remembers everything, works for you 24/7.**

Not a pet. Not a tool. A digital life that inherits your personality, memory, knowledge, and relationships. It grows every time you (or any AI) talk to it.

## Install

```bash
pip install omnity-ome                    # core (pulls in omnity-mindos)
pip install "omnity-ome[llm]"             # + chat via OpenAI/DeepSeek
pip install "omnity-ome[anthropic]"       # + chat via Anthropic
pip install "omnity-ome[all]"             # everything
```

Requires Python 3.9+.

## Quick Start

```bash
ome create        # 5 questions, your twin is born
ome chat          # talk to it (it remembers everything)
ome serve --mcp   # connect to Claude/Cursor
```

### Python API

```python
from ome import Ome

# Create a new Ome
twin = Ome.create("~/.ome", name="Alice", traits=["curious", "direct"])

# Or load an existing one
twin = Ome.load("~/.ome")

# Chat (auto-remembers everything)
reply = twin.chat("What do you know about my Python projects?")

# Teach it something directly
twin.remember("I prefer pytest over unittest")

# Search its memory
results = twin.recall("Python testing")

# Check proactive events (morning greeting, streak reminders, etc.)
events = twin.check_events()

# Export persona for any platform
persona = twin.export()                              # JSON
prompt = twin.export_system_prompt(context="code review")  # system prompt string
```

### MCP (Claude Desktop / Cursor)

```json
{
  "mcpServers": {
    "ome": {
      "command": "ome",
      "args": ["serve", "--mcp"]
    }
  }
}
```

### CLI

```bash
ome create                                  # interactive setup
ome chat                                    # conversation mode
ome remember "I'm working on a Go compiler" # teach it a fact
ome recall "compiler"                       # search memory
ome export --prompt                         # system prompt for any AI
ome export                                  # full persona JSON
ome forget "sensitive_topic"                # GDPR hard delete
```

## API Overview

| Class / Module | What it does |
|----------------|-------------|
| **`Ome`** | The main class. `Ome.create()` / `Ome.load()` to get an instance. Provides `chat()`, `remember()`, `recall()`, `forget()`, `check_events()`, `export()`, and `export_system_prompt()`. Wraps Mindos with persona-aware conversation and a full life system. |
| **`ConversationStrategy`** | Zero-extra-cost structured thinking block injected into every chat. Handles deep emotion detection (LLM-level, not keywords), 4-phase growth arc, memory classification, and continuous persona evolution. |
| **`BondState`** | 7-level relationship system (Stranger to Soulmate). Dual-threshold progression based on interaction count + days together. Bond level gates skill unlocks and conversation depth. |
| **`AutonomyEngine`** | Proactive event system: morning greetings, streak reminders, idle check-ins, milestone celebrations. Your Ome reaches out to you, not just responds. |
| **`SkillRegistry`** | 7 skills with competence tracking, unlocked by bond level. Skills represent what your Ome can do for you. |

## Life System

Your Ome grows through real interaction:

- **Bond levels**: 7 stages from Stranger to Soulmate -- dual-threshold, no grinding
- **Growth arc**: 4 phases (newborn, forming, distinct, soulmate) that change how it talks
- **20 achievements** across 3 tiers (basic / deep / hidden)
- **Daily challenges** + streak tracking with milestone rewards
- **Deep emotion**: LLM-parsed nuance, not keyword matching
- **Persona evolution**: learns your personality markers every conversation

## Privacy

- All data lives locally in `~/.ome/` (SQLite via Mindos)
- No cloud, no accounts, no telemetry
- `ome forget "pattern"` permanently erases data

## Part of Omnity

```
SOAP            spatial protocol for 3D environments
  Mindos        persistent multi-layer brain
    Ome         <-- you are here
      Maxim       multi-agent society + economy
        OmeTown     the integrated world
```

`pip install omnity-soap omnity-mindos omnity-ome omnity-maxim`

## License

[Apache-2.0](../../LICENSE)
