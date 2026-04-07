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
| **`ModelRouter`** | Selects the best available LLM provider (DeepSeek, OpenAI, Anthropic, Ollama) per task. **Automatic fallback chain**: if provider A fails (timeout/error), tries provider B, then C. Falls back to rule-based extraction when no LLM is configured. |
| **`Constitution`** | *(v0.7)* Immutable constraints on identity evolution. Rules: `trait_immutable`, `range_lock`, `max_delta`, `value_required`. L4 reflection proposes changes; Constitution validates and clamps before writeback. Deterministic, no LLM calls. |
| **`WritebackDamper`** | *(v0.7)* Max-delta clamping + oscillation detection. Prevents identity whiplash from consecutive reflections. Replaces the old meta-reflection approach. |
| **`ImportanceTrigger`** | *(v0.7)* Stanford Generative Agents-inspired importance accumulator. Dual triggers: cumulative importance threshold + adaptive commit-count (first to fire wins). |

### Zero-Config Setup (v0.5.0+)

```python
from mindos.config import MindosConfig

# Auto-detect from environment variables (DEEPSEEK_API_KEY, OPENAI_API_KEY, etc.)
cfg = MindosConfig.from_env()

# Or configure programmatically — no YAML file needed
cfg = MindosConfig.from_dict({
    "models": [
        {"name": "deepseek", "type": "openai_compatible",
         "base_url": "https://api.deepseek.com",
         "api_key_env": "DEEPSEEK_API_KEY",
         "model": "deepseek-chat", "priority": 1, "for": ["chat", "reasoning"]},
        {"name": "ollama", "type": "ollama",
         "model": "qwen3.5:14b", "priority": 2, "for": []},  # catch-all fallback
    ],
})
```

**Robustness**: All LLM calls have a 30s timeout (configurable) and automatic provider failover. If DeepSeek is down, your app keeps working via the next provider in the chain.

### Five-Layer Brain

| Layer | Analogy | What it does | Cost |
|-------|---------|-------------|------|
| **L0** | Hippocampus | Memory retrieval -- FTS5 search, vector index, forgetting curve | ~0 |
| **L1** | Brainstem | Instinct -- hydrate assembly, emotion state, request routing | ~0 |
| **L2** | Cortex | Understanding -- LLM commit digestion, fact extraction | Low |
| **L3** | Prefrontal | Decision -- deep reasoning, planning, conflict resolution | On demand |
| **L4** | Self (DMN) | Identity -- reflection loop, drift detection, value alignment | Async |

## Self-Evolution Architecture (v0.7)

v0.7 introduces three modules that make identity evolution **safe and principled**:

### Constitution — Immutable Identity Rules

```python
from mindos import Constitution, ConstitutionRule

rules = [
    ConstitutionRule(id="core-style", type="trait_immutable", trait="communication_style"),
    ConstitutionRule(id="openness-range", type="range_lock", trait="openness", min=0.6, max=1.0),
    ConstitutionRule(id="slow-change", type="max_delta", trait="extraversion", delta=0.05),
    ConstitutionRule(id="must-value", type="value_required", value="honesty"),
]
constitution = Constitution(rules)

# L4 reflection proposes changes → Constitution validates & clamps
proposed = {"openness": 0.3}  # violates range_lock
result = constitution.apply(proposed)  # clamped to 0.6
```

### Writeback Damping — Oscillation Protection

Prevents identity whiplash when consecutive reflections pull traits in opposite directions. Max-delta clamping per cycle + oscillation detection (3+ direction reversals → freeze trait for cooldown).

### Importance-Triggered Reflection

Inspired by Stanford Generative Agents: each memory commit is scored for importance (0–10). When the cumulative score crosses a threshold, reflection fires. Dual triggers — importance accumulator + adaptive commit-count — first to fire wins.

```python
from mindos import ImportanceTrigger, estimate_importance

trigger = ImportanceTrigger(threshold=50.0)
score = estimate_importance("Got promoted to CTO today")  # ~8.5
trigger.accumulate(score)
if trigger.should_reflect():
    soul.reflect()
```

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
