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

## Life System — Your Ome Grows

Ome is not just a chatbot. It has a **life system** that evolves through real interaction:

### Bond Levels (7 stages)
```
Lv.0 初见 → Lv.1 相识 → Lv.2 熟悉 → Lv.3 知己 → Lv.4 挚友 → Lv.5 灵魂伴侣 → Lv.6 命运共同体
```
Dual-threshold progression: interaction count + days together. No rushing, no grinding.

### Conversation Strategy Engine
Every chat uses a **structured thinking** block (zero extra API cost):
- **Deep emotion**: LLM-level nuance (not keyword matching). "升职了但感觉很空" → lonely, not happy.
- **4-phase growth arc**: newborn → forming → distinct → soulmate. Each phase changes how Ome talks.
- **Memory classification**: factual / emotional echo / callback / preference — each with usage hints.
- **Continuous persona evolution**: Ome learns your personality markers every conversation.

### Gamification & Retention
- **20 achievements** across 3 tiers (basic / deep / hidden)
- **Daily challenges** — rotating goals that keep users coming back
- **Streak tracking** with milestone rewards (3d / 7d / 14d / 30d / 90d / 365d)
- **7 skills** with competence tracking, unlocked by bond level
- **Autonomy engine** — proactive events (morning greeting, streak reminder, idle check-in, milestone celebration)
- **Level-up celebrations** with visual orb evolution

### iOS App
Native SwiftUI app with:
- SSE streaming chat + mirror mode
- Evolving OmeOrb visualization (colors, particles, aurora at high levels)
- Bond progress dashboard + 7-day streak calendar
- Achievement toast notifications on unlock
- Daily challenge banner in chat
- Push notification re-engagement (1d/3d/7d)
- Zero-registration first chat → seamless migration to registered account

## Status

v0.4.0

| Feature | Status |
|---------|--------|
| Create / load Ome | ✅ Done |
| Chat (with auto-memory) | ✅ Done |
| Conversation strategy engine | ✅ Done |
| Deep emotion (LLM-parsed) | ✅ Done |
| Persona evolution | ✅ Done |
| Growth arc (4 phases) | ✅ Done |
| Remember / recall / forget | ✅ Done |
| Export persona (JSON + prompt) | ✅ Done |
| MCP server (Claude/Cursor) | ✅ Done |
| HTTP server + SSE streaming | ✅ Done |
| Bond system (7 levels) | ✅ Done |
| Achievement system (20) | ✅ Done |
| Daily challenges | ✅ Done |
| Streak rewards | ✅ Done |
| Skill system (7 skills) | ✅ Done |
| Autonomy engine (L0 events) | ✅ Done |
| iOS native app | ✅ Done |
| Ome-to-Ome interaction (OmeTown) | ✅ Done |
| Autonomy L1 (LLM-powered events) | Planned |
| App Store release | In progress |

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
