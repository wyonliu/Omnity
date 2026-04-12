# omnity-ome

**Your AI twin -- remembers everything, works for you 24/7.**

Not a pet. Not a tool. A digital life that inherits your personality, memory, knowledge, and relationships. It grows every time you (or any AI) talk to it.

## Why Ome vs Mem0 / Khoj / MemGPT?

| | Ome | Mem0 | Khoj | MemGPT (Letta) |
|---|---|---|---|---|
| Memory storage | ✅ SQLite + FTS5 + vector | ✅ ChromaDB | ✅ Postgres | ✅ Postgres |
| Semantic recall | ✅ 40% weight in scoring | ✅ vector only | ✅ | ✅ |
| Cognitive layers | ✅ **5 layers (L0-L4)** | ❌ flat store | ❌ | ❌ |
| Personality + growth | ✅ **BigFive + bond + achievements** | ❌ | ❌ | ❌ |
| Emotional intelligence | ✅ **valence/arousal + mood-aware recall** | ❌ | ❌ | ❌ |
| Self-reflection | ✅ **L4 auto-reflect + drift detection** | ❌ | ❌ | ✅ self-edit |
| LLM failover chain | ✅ **auto retry A→B→C** | ❌ single | ❌ single | ❌ single |
| Zero-config setup | ✅ **from_env() auto-detect** | ❌ needs ChromaDB | ❌ needs Postgres | ❌ needs Postgres |
| Extra dependencies | **0** (just pyyaml) | chromadb + more | postgres + more | postgres + more |
| Privacy | ✅ **local-only, no cloud** | ✅ | ✅ | ✅ |

**Mem0 is a memory warehouse. Ome is a cognitive brain with memory, personality, emotion, and growth.**

## Install

```bash
pip install omnity-ome                    # core (pulls in omnity-mindos)
pip install "omnity-ome[llm]"             # + chat via OpenAI/DeepSeek
pip install "omnity-ome[all]"             # everything
```

Requires Python 3.9+.

## Quick Start (3 minutes)

```bash
# 1. Set any LLM API key
export DEEPSEEK_API_KEY="sk-..."   # or OPENAI_API_KEY, OPENROUTER_API_KEY

# 2. Create your twin
ome create

# 3. Talk to it
ome chat
```

### Python API (3 lines)

```python
from ome import Ome

twin = Ome.create("~/.ome", name="Alice", traits=["curious", "direct"])
reply = twin.chat("What do you know about my Python projects?")
```

### Rich Response (for apps)

```python
# chat_rich() returns memories recalled, emotion, bond — everything your UI needs
result = twin.chat_rich("Tell me about my work")
print(result["reply"])                    # The response text
print(result["memories_recalled"])        # Which memories were used
print(result["emotion"])                  # Current mood/energy/warmth
print(result["evolution_pending"])        # Ready for personality evolution?
```

### On-Demand Evolution

```python
if twin.evolution_pending:
    reflection = twin.evolve()            # Trigger L4 self-reflection
    print(reflection["summary"])          # What changed
```

### Smart Extraction

```python
# Extract structured data from natural language
data = twin.smart_extract("帮我记住张三的电话 13800138000，明天下午开会")
print(data["contacts"])                   # [{"name": "张三", "info": "13800138000"}]
print(data["tasks"])                      # [{"title": "开会", "due": "明天下午"}]
```

### Growth Stage & Maturity (v0.7)

```python
from ome import Ome, GrowthGate, Capability, MaturityScorer

twin = Ome.load("~/.ome")

# Check what capabilities are unlocked at current growth phase
gate = GrowthGate()
unlocked = gate.unlocked_capabilities(twin.growth_phase)  # e.g. phase="forming"
# [CHAT, RECALL, REMEMBER, WRITE, RESEARCH, PROACTIVE_GREET, FOLLOW_UPS]

can_evolve = gate.is_unlocked(Capability.EVOLVE, twin.growth_phase)  # False until "distinct"

# Maturity diagnostic (read-only, never gates features)
scorer = MaturityScorer()
snapshot = scorer.score(twin)
print(snapshot.score)                   # 0.42
print(snapshot.reflection_depth)        # 0.55
print(snapshot.memory_complexity)       # 0.38
print(snapshot.behavioral_consistency)  # 0.33
print(snapshot.label)                   # "developing"

# life_dashboard() now includes capabilities + maturity
dashboard = twin.life_dashboard()
print(dashboard["capabilities"])        # list of unlocked capability names
print(dashboard["maturity"])            # MaturitySnapshot dict
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
ome dashboard                               # bond, emotion, achievements
ome mirror                                  # talk to "yourself"
ome export --prompt                         # system prompt for any AI
ome forget "sensitive_topic"                # GDPR hard delete
```

## Architecture

```
┌─────────────────────────────────────────┐
│ Ome — Your AI Twin                       │
│   chat() / chat_rich() / evolve()       │
│   bond / emotion / achievements / skills │
│   GrowthGate (13 capabilities × 4 phases)│
│   MaturityScorer (3D diagnostic)         │
├─────────────────────────────────────────┤
│ Mindos — 5-Layer Cognitive Brain        │
│   L0 Memory    (recall + semantic rank) │
│   L1 Instinct  (routing + emotion)      │
│   L2 Cognition (fact extraction)        │
│   L3 Decision  (deep reasoning)         │
│   L4 Self      (reflection + drift)     │
│   Constitution (immutable trait rules)   │
│   Damping (oscillation-safe writeback)   │
│   ImportanceTrigger (reflection timing)  │
├─────────────────────────────────────────┤
│ ModelRouter — LLM Failover Chain        │
│   Provider A → B → C (30s timeout each) │
│   from_env() / from_dict() / config.yaml│
└─────────────────────────────────────────┘
```

## Skills (7 built-in, competence tracking)

| Skill | What it does | Bond required |
|-------|-------------|---------------|
| **chat** | Conversational AI + auto memory | 0 (Stranger) |
| **recall** | Cross-platform semantic memory search | 0 |
| **write** | Draft emails, articles, code in your voice | 0 |
| **research** | Search memories, synthesize, store findings | 0 |
| **schedule** | Add, list, remind, remove calendar tasks | 2 (Companion) |
| **social** | Multi-agent interaction (via Maxim) | 4 (Confidant) |
| **spatial** | 3D awareness & navigation (via SOAP) | 4 (Confidant) |

Each skill has a **competence score** (0.0–1.0) that grows with use. Higher bond unlocks more powerful skills.

## Life System

Your Ome grows through real interaction:

- **Bond levels**: 7 stages from Stranger to Soulmate -- dual-threshold, no grinding
- **Growth arc**: 4 phases (newborn, forming, distinct, soulmate) that change how it talks
- **Growth Stage Capability Unlocking** *(v0.7)*: 13 capabilities gated by growth phase — newborns get basic chat + recall, soulmates unlock everything including spatial AI and self-evolution
- **Maturity Score** *(v0.7)*: 3D diagnostic (reflection depth × memory complexity × behavioral consistency) — a read-only health check, never gates features
- **20 achievements** across 3 tiers (basic / deep / hidden)
- **Daily challenges** + streak tracking with milestone rewards
- **Deep emotion**: LLM-parsed nuance, not keyword matching
- **Persona evolution**: learns your personality markers every conversation
- **Constitution-protected identity** *(v0.7)*: core traits are locked by Mindos Constitution — reflection can evolve personality but never violate anchors

## Server Integration (FastAPI / Flask)

```python
from ome import Ome

ome = Ome.load("~/.ome/myapp")

@app.post("/api/ai")
async def chat(req: dict):
    result = ome.chat_rich(req["message"])
    return result  # reply + memories + emotion + bond — all in one call

@app.get("/api/growth")
async def growth():
    return ome.life_dashboard()

@app.post("/api/evolve")
async def evolve():
    return ome.evolve()

@app.post("/api/smart-input")
async def smart_input(req: dict):
    return ome.smart_extract(req["text"])

@app.get("/api/proactive")
async def proactive():
    events = ome.check_events()
    return [{"name": e.event_name, "message": e.message} for e in events]
```

## Enterprise: PostgreSQL Multi-Tenant (v0.7.1+)

For production deployments, inject a PostgreSQL store:

```python
# Default: SQLite (local, zero config)
ome = Ome.create(path="~/.ome", name="Alice")

# Enterprise: PostgreSQL + RLS (via ome-server)
ome = Ome.create(path="~/.ome", name="Alice", store=pg_memory_store)
ome = Ome.load("~/.ome", store=pg_memory_store)
```

The `ome-server` package provides `PgMemoryStore` with Row-Level Security for zero-trust tenant isolation. See `ome-server/db/` for the full enterprise stack.

## Privacy

- All data lives locally in `~/.ome/` (SQLite via Mindos) by default
- No cloud, no accounts, no telemetry
- `ome forget "pattern"` permanently erases data
- Enterprise PG mode: your own database, RLS isolation per tenant

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
