# omnity-mindos

**Portable Digital Soul Protocol -- your AI knows you, everywhere.**

Install once, and every AI -- Claude, ChatGPT, Cursor, Gemini, local models -- remembers who you are, what you know, and how you think. Across devices. Forever.

## Install

```bash
pip install omnity-mindos                       # core (just pyyaml)
pip install "omnity-mindos[llm]"                # + LLM-powered commit (openai)
pip install "omnity-mindos[anthropic]"          # + native Anthropic support
pip install "omnity-mindos[all]"                # + semantic vector search + all LLMs
```

Requires Python 3.9+.

## Quick Start

```bash
# Create your soul (interactive, 5 questions)
mindos quickstart

# Teach it something
mindos commit "user: I'm a Python developer working on distributed systems"

# See what it knows
mindos status
mindos recall "Python"

# Start the server
mindos serve
```

### Python API

```python
from mindos import Mindos

soul = Mindos.load()                              # loads from ~/.mindos/
context = soul.hydrate(context="travel planning")  # assemble identity + relevant memories
result = soul.commit("user: I love hiking\nassistant: Great!", source="myapp")
memories = soul.recall("hiking", top_k=5)

# Generate a portable persona for any platform
ome = soul.export_ome(context="hiking")
```

### MCP (Claude Desktop / Cursor)

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

### HTTP API

```bash
mindos serve

curl localhost:3456/api/hydrate -d '{"context": "coding"}'
curl localhost:3456/api/commit  -d '{"conversation": "user: I learned Rust today", "source": "api"}'
curl localhost:3456/api/recall  -d '{"query": "Rust"}'
curl localhost:3456/api/status
```

## API Overview

| Class / Module | What it does |
|----------------|-------------|
| **`Mindos`** | The main facade. Provides `hydrate()`, `commit()`, `recall()`, `forget()`, `reflect()`, `export_ome()`, and `sync()`. Load it once with `Mindos.load()` and use it from any code. |
| **`LayerRouter`** | Dispatches requests to the cheapest brain layer (L0-L4) that can handle them. L0 (memory retrieval) is near-zero cost; L3 (deep reasoning) is on-demand. |
| **`MemoryStore`** | SQLite-backed storage with FTS5 full-text search, content-hash dedup, forgetting curve, and a sync journal for cross-device replication. |
| **`ModelRouter`** | Selects the best available LLM provider (DeepSeek, OpenAI, Anthropic, Ollama) per task. Falls back to rule-based extraction when no LLM is configured. |

### Five-Layer Brain

| Layer | Analogy | What it does | Cost |
|-------|---------|-------------|------|
| **L0** | Hippocampus | Memory retrieval -- FTS5 search, vector index, forgetting curve | ~0 |
| **L1** | Brainstem | Instinct -- hydrate assembly, emotion state, request routing | ~0 |
| **L2** | Cortex | Understanding -- LLM commit digestion, fact extraction | Low |
| **L3** | Prefrontal | Decision -- deep reasoning, planning, conflict resolution | On demand |
| **L4** | Self (DMN) | Identity -- reflection loop, drift detection, value alignment | Async |

## Cross-Device Sync

```bash
# Start a Sync Hub on your VPS
mindos serve --sync --port 3457

# On each device
export MINDOS_SYNC_URL=http://your-vps:3457
mindos sync
```

Every mutation is recorded in a local journal. The Hub relays events between devices but never stores your data.

## Privacy

- All data lives locally in `~/.mindos/` (SQLite)
- No cloud, no accounts, no telemetry
- `mindos forget "pattern"` does GDPR hard delete
- Optional Bearer token auth via `MINDOS_AUTH_TOKEN`

## Part of Omnity

```
SOAP            spatial protocol for 3D environments
  Mindos        <-- you are here
    Ome           individual AI agent (persona, skills, growth)
      Maxim         multi-agent society + economy
        OmeTown       the integrated world
```

`pip install omnity-soap omnity-mindos omnity-ome omnity-maxim`

## License

[Apache-2.0](../../LICENSE)
