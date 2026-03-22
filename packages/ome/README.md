# Ome

**Your AI twin — remembers everything, speaks in your voice, works for you 24/7.**

Not a pet. Not a tool. A digital life that inherits your personality, memory, knowledge, and relationships. It grows every time you (or any AI) talks to it.

```bash
pip install ome
ome create        # 5 questions, your twin is born
ome chat          # talk to it (it remembers everything)
ome serve --mcp   # connect to Claude/Cursor
```

---

## What Ome Does

| You do this | Ome does this |
|-------------|---------------|
| `ome create` | Creates your digital identity: name, traits, style, values, skills |
| `ome chat` | Talks to you in your voice, auto-remembers every conversation |
| `ome remember "..."` | Learns a new fact about you |
| `ome recall "Python"` | Searches everything it knows about a topic |
| `ome serve --mcp` | Becomes a tool inside Claude/Cursor — they know who you are |
| `ome export --prompt` | Outputs a system prompt you can paste into any AI |
| `ome export` | Full persona JSON for any platform (OpenClaw, agents, apps) |

## How It Works

Ome is powered by [Mindos](../mindos) — a five-layer brain:

```
Your message → Ome
                ↓
  L0 Hippocampus: recall relevant memories
  L1 Brainstem:   assemble your identity context
  L2 Cortex:      generate response in your voice
                ↓
  Auto-commit conversation to long-term memory
                ↓
Ome's reply (+ it remembers this forever)
```

Every conversation makes your Ome smarter. It never forgets. It never resets.

## Connect to Claude / Cursor (MCP)

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

Now Claude and Cursor know your name, your skills, your preferences, your project context — automatically.

## Use with OpenClaw / Any Agent

```python
from ome import Ome

twin = Ome.load()

# Inject your identity into any agent
system_prompt = twin.export_system_prompt(context="code review")

# After the agent runs, teach your Ome what happened
twin.remember("Reviewed the auth module, found 3 SQL injection risks")
```

## Export Your Persona Anywhere

```bash
# As a system prompt (paste into ChatGPT, Gemini, anything)
ome export --prompt > my_persona.txt

# As structured JSON (for apps and agent frameworks)
ome export > my_persona.json

# Biased toward a topic
ome export --prompt --context "Python development"
```

## Privacy

- All data lives locally in `~/.ome/` (SQLite)
- No cloud, no accounts, no telemetry
- `ome forget "pattern"` permanently erases data (GDPR)
- You own your digital life

## Status

v0.1.0 — alpha.

| Feature | Status |
|---------|--------|
| Create / load Ome | Done |
| Chat (with auto-memory) | Done |
| Remember / recall / forget | Done |
| Export persona (JSON + prompt) | Done |
| MCP server (Claude/Cursor) | Done |
| HTTP server | Done |
| LLM-powered chat | Requires API key |
| Ome-to-Ome interaction | Planned |
| Skill system | Planned |
| Work engine (autonomous tasks) | Planned |

## Install

```bash
pip install ome                    # core
pip install "ome[llm]"             # + chat via OpenAI/DeepSeek
pip install "ome[anthropic]"       # + chat via Anthropic
pip install "ome[all]"             # everything
```

Requires Python 3.9+.

---

*Part of [Omnity](https://github.com/wyonliu/Omnity) — an open-source stack for AI agents in real space.*
