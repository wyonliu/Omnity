# Mindos — Portable Digital Soul Protocol

**Multi-layer Intention & Neural Dynamic Operating System**

Mindos is a persistent, portable identity layer that sits between you and any AI.
It remembers who you are, how you think, and what you care about — across every
platform, every model, every session.

```
User ←→ [Any AI Platform] ←→ Mindos Layer ←→ [Any LLM]
                                    ↕
                              ~/.mindos/ (your data)
```

## Architecture: Five-Layer Brain

```
┌─────────────────────────────────────────────────┐
│ L4  Self (Default Mode Network)                 │
│     Personality model · Reflection loop ·       │
│     Value alignment · Cross-platform anchor     │
├─────────────────────────────────────────────────┤
│ L3  Prefrontal — Decision                       │
│     Deep reasoning · Planning · Conflict        │
│     resolution · Behavior orchestration         │
├─────────────────────────────────────────────────┤
│ L2  Cortex — Cognition                          │
│     LLM-powered commit digestion · Fact         │
│     extraction · Contradiction detection        │
├─────────────────────────────────────────────────┤
│ L1  Brainstem — Instinct                        │
│     Fast routing · hydrate assembly · Emotion   │
│     state · Token budget · Handles 60%+ fast    │
├─────────────────────────────────────────────────┤
│ L0  Hippocampus — Memory                        │
│     SQLite + vector index · Relevance scoring   │
│     (recency × importance × frequency × decay)  │
│     Knowledge graph · Personality history       │
└─────────────────────────────────────────────────┘
     ↕           ↕            ↕           ↕
 LayerRouter  ModelRouter  MCP Server  Dashboard
```

## v0.2.0 Completion Matrix

| Component | Status | Details |
|-----------|--------|---------|
| L0 Hippocampus | ✅ | SQLite + WAL, vector search, KG, relevance scoring |
| L1 Brainstem | ✅ | Request classification, hydrate assembly, emotion state |
| L2 Cortex | ✅ | LLM-powered commit (DeepSeek/OpenAI), rule-based fallback |
| L3 Prefrontal | ✅ | Deep reasoning, planning, conflict resolution via ModelRouter |
| L4 Self | ✅ | Reflection loop, personality drift detection, heuristic fallback |
| LayerRouter | ✅ | Routes requests to appropriate layer |
| ModelRouter | ✅ | Multi-provider LLM switching (DeepSeek, OpenAI, Anthropic) |
| config.yaml | ✅ | Auto-generated, configurable providers and behavior |
| MCP Server | ✅ | `mindos serve --mcp` for Claude Desktop / Cursor |
| Dashboard | ✅ | Local web UI with hydrate/commit/recall/forget/reflect |
| CLI | ✅ | init, status, commit, recall, forget, serve |
| Relevance Scoring | ✅ | Composite: recency × importance × frequency × decay |
| Sensitive Filter | ✅ | Regex-based, blocks API keys / ID numbers / passwords |
| Deduplication | ✅ | Content-exact dedup in commit |
| Forget (GDPR) | ✅ | Physical erasure from memories + KG |
| Tests | ✅ | 8 integration tests covering all layers + MCP protocol |

## Quick Start

### Install

```bash
pip install -e packages/mindos              # core (pyyaml only)
pip install -e "packages/mindos[llm]"       # + LLM support (openai)
pip install -e "packages/mindos[all]"       # + semantic search
```

### Create a Soul

```bash
mindos init --name "YourName" --traits "curious,creative" --style "concise"
```

This creates `~/.mindos/` with:
- `identity.yaml` — your personality profile
- `config.yaml` — LLM provider configuration
- `memory.db` — memory storage (SQLite)

### Configure LLM Providers

Edit `~/.mindos/config.yaml`:

```yaml
models:
  - name: deepseek
    type: openai_compatible
    base_url: https://api.deepseek.com
    api_key_env: DEEPSEEK_API_KEY
    model: deepseek-chat
    priority: 1
    for: [commit_digest, reflection, reasoning]
```

Set environment variables for API keys — never store keys in config files.

### Use as MCP Server (Claude Desktop / Cursor)

```bash
mindos serve --mcp
```

Add to Claude Desktop config (`claude_desktop_config.json`):

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

MCP tools exposed:
- `mindos_hydrate` — load identity context into session
- `mindos_commit` — digest conversation into memories
- `mindos_recall` — search memories with relevance ranking
- `mindos_forget` — GDPR-compliant erasure
- `mindos_status` — current soul state
- `mindos_reflect` — trigger personality review

### Dashboard

```bash
mindos serve --dashboard
# → http://localhost:3456
```

### Python API

```python
from mindos import Mindos

soul = Mindos.load("~/.mindos")

# Inject identity into any AI session
context = soul.hydrate(context="discussing travel plans")

# Digest a conversation
result = soul.commit(
    "user: I live in Shanghai\nassistant: Got it!",
    source="claude"
)

# Search memories
memories = soul.recall("Shanghai", top_k=5)

# Deep reasoning (uses ModelRouter)
answer = soul.reason("Should I use Rust or Go for this project?")

# Force reflection cycle
reflection = soul.reflect()

# Physical erasure
soul.forget("Tokyo", scope="episode")
```

### CLI

```bash
mindos status                          # show soul state
mindos commit "user: I like Python"    # digest text
mindos recall "Python"                 # search memories
mindos forget "Tokyo" --scope episode  # erase memories
```

## Testing

```bash
cd packages/mindos
python3 tests/test_soul.py    # 8 integration tests

# Demo with dashboard
python3 scripts/demo_dashboard.py --no-serve
```

## File Structure

```
src/mindos/
├── __init__.py          # Package entry
├── core.py              # Mindos facade (public API)
├── config.py            # config.yaml + ModelRouter
├── router.py            # LayerRouter (orchestrates L0-L4)
├── store.py             # SQLite memory store
├── layers/
│   ├── l0_memory.py     # Hippocampus: retrieval + relevance scoring
│   ├── l1_instinct.py   # Brainstem: routing + hydrate + emotion
│   ├── l2_cognition.py  # Cortex: LLM commit digestion
│   ├── l3_decision.py   # Prefrontal: reasoning + planning
│   └── l4_self.py       # Self: reflection + personality drift
├── mcp_server.py        # MCP Server (stdio JSON-RPC)
├── dashboard.py         # Web UI
└── cli.py               # CLI
```

## Data Ownership

All data stays local in `~/.mindos/`. No cloud, no telemetry.
You own your soul.

---

*Part of the [Omnity](https://github.com/anthropics/omnity) ecosystem:
SOAP (Spatial Omnity Agentic Protocol) + Mindos (Digital Soul Protocol).*
