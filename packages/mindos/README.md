# Mindos — Portable Digital Soul Protocol

**Multi-layer Intention & Neural Dynamic Operating System**

Mindos is a persistent identity layer between you and every AI you use.
It remembers who you are — your personality, knowledge, preferences, skills,
and relationships — across every platform, every model, every session.

```
                  ┌─────────────────────────────────────┐
                  │         Mindos Server (:3456)        │
                  │                                     │
Terminal 1  ──────│  CLI auto-discovers via lockfile     │
Terminal 2  ──────│  MindosClient (Python SDK)           │
Claude MCP  ──────│  MCP Server (stdio)                  │
Cursor MCP  ──────│  MCP Server (stdio)                  │
Browser     ──────│  Dashboard (http://localhost:3456)    │
                  │                                     │
                  │           ~/.mindos/                 │
                  │  identity.yaml · config.yaml         │
                  │  memory.db (SQLite + WAL)             │
                  └─────────────────────────────────────┘
```

## Who Is This For?

### Developer using 3+ AI tools daily
You talk to Cursor, Claude, ChatGPT, and local models. Each one forgets
everything the moment a session ends. With Mindos, every AI knows your
tech stack, project context, and coding preferences from the first message.

```bash
# Terminal 1: start the server (runs in background)
mindos serve &

# Terminal 2: code in Cursor (MCP auto-connects)
# Terminal 3: chat with Claude (MCP auto-connects)
# Terminal 4: check what your AIs have learned
mindos recall "Python"
mindos memories --stats
```

### Researcher across multiple devices
Your literature review context is scattered across ChatGPT, Claude, and Gemini.
Mindos remembers your research topics, methodological preferences, and paper notes.

```bash
# Export your soul to move between machines
mindos memories --export -o backup.json

# Import on another machine
mindos memories --import-file backup.json
```

### Privacy-conscious user
All data stays in `~/.mindos/`. No cloud, no telemetry, no accounts.
You can encrypt, backup, and delete your data at any time.

```bash
# See exactly what's stored
mindos memories --stats
mindos memories -q "personal"

# GDPR-style hard delete
mindos forget "my_address" --scope fact
```

## Architecture

```
┌──────────────────────────────────────────────────────┐
│ L4  Self (Default Mode Network) — Personality        │
│     Reflection loop · Drift detection · Value anchor │
├──────────────────────────────────────────────────────┤
│ L3  Prefrontal — Decision                            │
│     Deep reasoning · Planning · Conflict resolution  │
├──────────────────────────────────────────────────────┤
│ L2  Cortex — Cognition                               │
│     LLM commit digestion · Fact extraction · Dedup   │
├──────────────────────────────────────────────────────┤
│ L1  Brainstem — Instinct                             │
│     Request routing · hydrate assembly · Emotion     │
├──────────────────────────────────────────────────────┤
│ L0  Hippocampus — Memory                             │
│     SQLite · Vector index · Relevance scoring        │
│     (recency × importance × frequency × decay)       │
└──────────────────────────────────────────────────────┘
     ↕            ↕            ↕            ↕
 LayerRouter  ModelRouter  HTTP Server  MCP Server
```

## Quick Start

```bash
# Install
pip install -e packages/mindos            # core
pip install -e "packages/mindos[llm]"     # + LLM support
pip install -e "packages/mindos[all]"     # + semantic search

# Create your soul
mindos init --name "YourName" --traits "curious,creative" --style "concise"

# Start the server
mindos serve
# → http://localhost:3456 (Dashboard)
# → Lockfile written; other terminals auto-discover
```

## Multi-Terminal Usage

This is the key design principle: **one server, many clients**.

```bash
# Terminal 1: start server
mindos serve

# Terminal 2: any mindos command auto-proxies to the server
mindos status                        # → talks to server via HTTP
mindos commit "user: I like Rust"    # → server digests it
mindos recall "Rust"                 # → server searches memories

# No server running? Commands fall back to direct DB access.
```

The discovery mechanism is a lockfile at `~/.mindos/server.lock`. When a server
starts, it writes its PID and port. When any CLI command runs, it checks the
lockfile first. Stale lockfiles (dead PIDs) are automatically cleaned up.

## MCP Integration (Claude Desktop / Cursor)

```bash
# Start MCP server (separate stdio process)
mindos serve --mcp
```

Claude Desktop `claude_desktop_config.json`:
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

MCP tools: `mindos_hydrate`, `mindos_commit`, `mindos_recall`, `mindos_forget`,
`mindos_status`, `mindos_reflect`.

## Memory Management

```bash
# Browse memories
mindos memories                       # recent 20
mindos memories -q "Python"           # search
mindos memories --stats               # breakdown by type/source

# Export / Import
mindos memories --export -o soul.json
mindos memories --import-file soul.json

# Physical erasure (GDPR)
mindos forget "sensitive_topic"
mindos forget "old_project" --scope episode
```

## Python SDK

```python
from mindos import Mindos

soul = Mindos.load()  # loads ~/.mindos/

# Inject identity into any AI session
context = soul.hydrate(context="discussing travel")

# Digest a conversation
result = soul.commit(
    "user: I live in Shanghai\nassistant: Got it!",
    source="my_app"
)

# Search with relevance ranking
memories = soul.recall("Shanghai", top_k=5)

# Deep reasoning via ModelRouter
answer = soul.reason("Rust or Go for this project?")

# Client mode (connect to running server)
from mindos.client import MindosClient
client = MindosClient.discover()  # auto-finds server
client.commit("user: learned Kubernetes today", source="notes")
```

## LLM Configuration

Edit `~/.mindos/config.yaml`:

```yaml
models:
  - name: deepseek
    type: openai_compatible
    base_url: https://api.deepseek.com
    api_key_env: DEEPSEEK_API_KEY    # reads from environment
    model: deepseek-chat
    priority: 1
    for: [commit_digest, reflection, reasoning]

  - name: openai
    type: openai_compatible
    base_url: https://api.openai.com/v1
    api_key_env: OPENAI_API_KEY
    model: gpt-4o-mini
    priority: 2
    for: [commit_digest, reasoning, creation]
```

ModelRouter selects the best available provider by priority and task type.
When no LLM is configured, commit falls back to rule-based extraction.

## Testing

```bash
cd packages/mindos
python3 tests/test_soul.py     # 11 tests (layers, MCP, server, export/import)

# Interactive demo
python3 scripts/demo_dashboard.py
```

## File Structure

```
src/mindos/
├── core.py              Mindos facade (public API)
├── config.py            config.yaml + ModelRouter
├── router.py            LayerRouter (orchestrates L0-L4)
├── server.py            HTTP server + lockfile discovery
├── client.py            HTTP client (MindosClient)
├── mcp_server.py        MCP Server (stdio JSON-RPC)
├── store.py             SQLite memory store
├── layers/
│   ├── l0_memory.py     Hippocampus: retrieval + relevance
│   ├── l1_instinct.py   Brainstem: routing + hydrate + emotion
│   ├── l2_cognition.py  Cortex: LLM commit digestion
│   ├── l3_decision.py   Prefrontal: reasoning + planning
│   └── l4_self.py       Self: reflection + drift detection
├── dashboard.py         Web UI HTML
└── cli.py               CLI (auto-proxies to server)
```

## Data Ownership

All data lives in `~/.mindos/`. No cloud dependencies.

```
~/.mindos/
├── identity.yaml     # who you are
├── config.yaml       # LLM providers
├── memory.db         # SQLite (memories + KG + personality history)
├── server.lock       # auto-created when server runs
└── journal/          # future: raw conversation logs
```

---

*Part of the [Omnity](https://github.com/wyonliu/Omnity) ecosystem.*
