# Mindos

**Your AI forgets you after every conversation. Mindos fixes that.**

Mindos is a portable identity layer that sits between you and every AI you use.
Install once, and every AI — Claude, ChatGPT, Cursor, local models, OpenClaw agents —
remembers who you are, what you know, and how you think.

```bash
pip install mindos
mindos quickstart
```

That's it. Your soul is created. Now every AI knows you.

---

## The Problem

You use 3-5 AI tools daily. Each one starts with zero context every time.
You re-explain your tech stack, your preferences, your project context,
your communication style — over and over. That's hundreds of hours wasted per year.

## The Solution

```
You ←→ [Any AI] ←→ Mindos ←→ ~/.mindos/
```

Mindos stores your identity, memories, knowledge graph, and personality locally.
Any AI can read it (hydrate) and write back (commit). The more you use AI,
the more Mindos knows you. The more Mindos knows you, the better every AI works.

## 30-Second Demo

```bash
# 1. Create your soul (interactive, 5 questions)
mindos quickstart

# 2. Teach it something
mindos commit "user: I'm a Python developer working on distributed systems"

# 3. See what it knows
mindos status
mindos recall "Python"

# 4. Start the server — now every terminal shares your soul
mindos serve
```

## Connect to Your AI Tools

### Claude Desktop / Cursor (MCP)

```json
{
  "mcpServers": {
    "mindos": {
      "command": "mindos",
      "args": ["serve", "--mcp"]
    }
  }
}
```

Now Claude and Cursor automatically know your name, skills, preferences,
and past conversation context.

### OpenClaw / Any Agent Framework

```python
from mindos_plugin import MindosPlugin

plugin = MindosPlugin()
context = plugin.before_run("code review")
# → inject into system prompt
plugin.after_run(conversation_text)
```

### Python SDK

```python
from mindos import Mindos

soul = Mindos.load()
context = soul.hydrate(context="travel planning")
result = soul.commit("user: I love hiking\nassistant: Great!", source="myapp")
memories = soul.recall("hiking", top_k=5)
```

### Any Terminal (multi-terminal)

```bash
# Terminal 1: start server
mindos serve

# Terminal 2, 3, 4: all auto-discover the server
mindos recall "Python"          # → "via server"
mindos commit "user: learned Kubernetes today"
mindos memories --stats
```

## Architecture

Five-layer brain inspired by neuroscience:

```
L4  Self          Personality drift detection, reflection, value alignment
L3  Prefrontal    Deep reasoning, planning, conflict resolution
L2  Cortex        LLM-powered fact extraction, contradiction detection
L1  Brainstem     Fast routing, context assembly, emotion state
L0  Hippocampus   Memory storage, relevance scoring, knowledge graph
```

+ ModelRouter (multi-LLM switching) + LayerRouter + HTTP Server + MCP Server

## Memory Management

```bash
mindos memories                     # browse
mindos memories --stats             # breakdown by type and source
mindos memories --export -o soul.json   # backup
mindos memories --import-file soul.json # restore
mindos memories --consolidate       # merge similar memories
mindos forget "sensitive_topic"     # GDPR hard delete
```

## Privacy

- All data in `~/.mindos/` — local SQLite, no cloud
- No telemetry, no accounts, no network calls (unless you configure LLM providers)
- Sensitive data (API keys, passwords, ID numbers) auto-filtered on commit
- Physical erasure via `mindos forget` — gone from DB and knowledge graph

## Install

```bash
pip install mindos                    # core (just pyyaml)
pip install "mindos[llm]"             # + LLM-powered commit (openai)
pip install "mindos[all]"             # + semantic vector search
```

## Status

v0.2.0 — alpha. Core architecture is solid, actively iterating.

| Feature | Status |
|---------|--------|
| Five-layer brain (L0-L4) | ✅ |
| MCP Server | ✅ |
| HTTP Server + multi-terminal | ✅ |
| ModelRouter (DeepSeek/OpenAI/Anthropic) | ✅ |
| Memory management (export/import/consolidate) | ✅ |
| Interactive quickstart | ✅ |
| Cursor Skill | ✅ |
| OpenClaw plugin | ✅ |
| LLM-powered commit + rule fallback | ✅ |
| Reflection loop + drift detection | ✅ |
| GDPR forget | ✅ |
| PyPI package | 🔜 |
| Browser extension | planned |
| Mobile SDK | planned |

## Contributing

Apache-2.0. PRs welcome. See `integrations/` for plugin examples.

---

*Part of [Omnity](https://github.com/wyonliu/Omnity) — SOAP (spatial AI protocol) + Mindos (digital soul protocol).*
