# Mindos

**Your AI forgets you after every conversation. Mindos fixes that.**

Mindos is a portable digital soul protocol. Install once, and every AI — Claude, ChatGPT, Cursor, Gemini, local models, OpenClaw agents — remembers who you are, what you know, and how you think. Across devices. Forever.

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

Worse: your identity is locked inside each platform. Your Claude memories don't follow you to ChatGPT. Your Cursor context doesn't exist in Gemini. You are fragmented across AI silos.

## The Solution

```
You ←→ [Any AI] ←→ Mindos ←→ ~/.mindos/ ←→ Sync Hub ←→ Other Devices
```

Mindos stores your identity, memories, knowledge graph, and personality locally.
Any AI can read it (hydrate) and write back (commit). Changes sync across all your devices. The more you use AI, the more Mindos knows you. The more Mindos knows you, the better every AI works.

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

MCP tools: `mindos_hydrate`, `mindos_commit`, `mindos_recall`, `mindos_forget`, `mindos_reflect`, `mindos_ome`, `mindos_sync`.

### Python SDK

```python
from mindos import Mindos

soul = Mindos.load()
context = soul.hydrate(context="travel planning")
result = soul.commit("user: I love hiking\nassistant: Great!", source="myapp")
memories = soul.recall("hiking", top_k=5)

# Generate a portable persona for any platform
ome = soul.export_ome(context="hiking")
```

### HTTP API

```bash
# Start server
mindos serve

# Any app can call
curl localhost:3456/api/hydrate -d '{"context": "coding"}'
curl localhost:3456/api/commit -d '{"conversation": "user: I learned Rust today", "source": "api"}'
curl localhost:3456/api/recall -d '{"query": "Rust"}'
curl localhost:3456/api/ome       # Generate Ome persona package
curl localhost:3456/api/status    # Identity, memories, emotion, sync state
```

### OpenClaw / Any Agent Framework

```python
from mindos import Mindos

soul = Mindos.load()

# Before agent run: inject identity
system_prompt = soul.hydrate(context="code review") + "\n" + your_system_prompt

# After agent run: persist what happened
soul.commit(conversation_text, source="openclaw")
```

## Cross-Device Sync

Your soul lives on all your devices. Mac, phone, browser — all in sync.

```
Mac (Claude Code + Cursor)           Phone (Ome App)
┌──────────────┐                     ┌──────────────┐
│ SQLite (local)│  ← push/pull →    │ SQLite (local)│
│ sync_journal  │       ↕            │ sync_journal  │
└───────────────┘  ┌─────────┐      └───────────────┘
                   │Sync Hub │
                   │ (relay) │
                   └────┬────┘
                        │
                   Chrome Extension
                   (Gemini / Doubao)
```

### How it works

Every mutation (commit, forget, reflect) is recorded in a local `sync_journal`. The Sync Hub is a lightweight event relay — it doesn't store your soul, just forwards events between devices.

```bash
# Start a Sync Hub on your VPS
mindos serve --sync --port 3457

# On each device
export MINDOS_SYNC_URL=http://your-vps:3457
mindos sync                # push + pull in one step
mindos sync --push         # push only
mindos sync --pull         # pull only
```

Conflict resolution:
- **Memories**: append-only + content-hash dedup (no conflicts)
- **Knowledge graph**: idempotent upsert (no conflicts)
- **Forget**: propagates to all devices (GDPR)
- **Identity edits**: last-writer-wins (rare, low-frequency)

## Ome Generation

An **Ome** is a lightweight persona snapshot exported from your Mindos soul. It contains your identity, relevant memories, knowledge graph, and hydrated context — ready to inject into any AI platform.

```python
soul = Mindos.load()
ome = soul.export_ome(context="customer support")
# → { identity, anchor, hydrated_context, memories, knowledge_graph, emotion }

# Send to any platform that accepts persona JSON
```

Also available via CLI (`mindos ome`), HTTP (`GET /api/ome`), and MCP (`mindos_ome` tool).

## Architecture

Five-layer brain inspired by neuroscience:

| Layer | Brain Region | What it does | Latency | Cost |
|-------|-------------|--------------|---------|------|
| **L0** | Hippocampus | What you **remember** — FTS5 search, vector index, forgetting curve | < 50ms | ~0 |
| **L1** | Brainstem | Your **instinct** — hydrate assembly, emotion state, request routing | < 100ms | ~0 |
| **L2** | Cortex | How you **understand** — LLM commit digestion, fact extraction, sensitive filter | < 2s | Low |
| **L3** | Prefrontal | How you **decide** — deep reasoning, planning, conflict resolution | 1-10s | On demand |
| **L4** | Self (DMN) | Who you **are** — reflection loop, drift detection, value alignment | Async | ~0 |

### LLM Providers

ModelRouter selects the best available provider per task:

| Provider | Type | Use case |
|----------|------|----------|
| DeepSeek | openai_compatible | commit, reflection, reasoning (default) |
| OpenAI | openai_compatible | commit, reasoning, creation |
| Anthropic | **native SDK** | deep reasoning, complex creation |
| Ollama | local | privacy-first, offline capable |

All providers are optional. Without any LLM, Mindos falls back to rule-based extraction.

## Memory Management

```bash
mindos memories                          # browse
mindos memories --stats                  # breakdown by type and source
mindos memories --export -o soul.json    # backup
mindos memories --import-file soul.json  # restore
mindos memories --consolidate            # merge similar memories
mindos forget "sensitive_topic"          # GDPR hard delete
```

## Privacy & Security

- **Local-first**: all data in `~/.mindos/` — SQLite, no cloud dependency
- **Auth**: `MINDOS_AUTH_TOKEN` env var enables Bearer token on HTTP API
- **No telemetry**: no accounts, no tracking, no network calls unless you configure LLM providers
- **Sensitive filter**: API keys, passwords, ID numbers auto-blocked on commit
- **GDPR forget**: `mindos forget` does physical erasure from DB and knowledge graph
- **Sync is optional**: Hub only relays events, never stores your soul data

## Install

```bash
pip install mindos                       # core (just pyyaml)
pip install "mindos[llm]"                # + LLM-powered commit (openai)
pip install "mindos[anthropic]"          # + native Anthropic support
pip install "mindos[all]"                # + semantic vector search + all LLMs
```

Requires Python 3.10+.

## Status

v0.3.0 — alpha. Core architecture is solid, actively iterating.

| Feature | Status |
|---------|--------|
| Five-layer brain (L0-L4) | Done |
| MCP Server (8 tools + 3 resources) | Done |
| HTTP Server + multi-terminal auto-discovery | Done |
| ModelRouter (DeepSeek/OpenAI/Anthropic/Ollama) | Done |
| Cross-device sync (Sync Hub + Journal) | Done |
| Ome generation (export_ome) | Done |
| FTS5 full-text search | Done |
| Content-hash fuzzy dedup | Done |
| Emotion state persistence | Done |
| Bearer token auth | Done |
| LLM response caching | Done |
| Memory management (export/import/consolidate) | Done |
| Interactive quickstart | Done |
| GDPR forget | Done |
| 22 integration tests | Done |
| Chrome extension | Planned |
| TypeScript SDK | Planned |
| Mobile SDK | Planned |
| PyPI package | Soon |

## File Structure

```
src/mindos/
├── core.py              Mindos facade (hydrate/commit/recall/forget/reflect/sync/export_ome)
├── config.py            config.yaml + ModelRouter (DeepSeek/OpenAI/Anthropic/Ollama)
├── router.py            LayerRouter (orchestrates L0-L4)
├── store.py             SQLite store (FTS5, content-hash dedup, sync journal)
├── sync.py              SyncHub (relay server) + SyncClient (push/pull)
├── server.py            HTTP server + lockfile auto-discovery + auth
├── client.py            MindosClient (HTTP SDK + auto-discovery)
├── mcp_server.py        MCP Server (stdio JSON-RPC, 8 tools)
├── dashboard.py         Web UI
├── cli.py               CLI (auto-proxies to server when running)
└── layers/
    ├── l0_memory.py     Hippocampus: retrieval + relevance scoring
    ├── l1_instinct.py   Brainstem: routing + hydrate + emotion state (persistent)
    ├── l2_cognition.py  Cortex: LLM commit digestion + rule fallback
    ├── l3_decision.py   Prefrontal: reasoning + planning
    └── l4_self.py       Self: reflection loop + drift detection + Ome anchor

~/.mindos/
├── identity.yaml        who you are
├── config.yaml          LLM providers + sync config
├── memory.db            SQLite (memories, KG, personality history, sync journal, soul state)
└── server.lock          auto-created when server runs
```

## Contributing

Apache-2.0. PRs welcome.

---

*Part of [Omnity](https://github.com/wyonliu/Omnity) — an open-source stack for spatial AI agents.*
