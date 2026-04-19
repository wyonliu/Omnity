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

## Personal Harness Runtime (v0.9 · W1)

*"Agent = Model + Harness."* Memory, skills, and identity become useful only when wired into a harness that talks to a real model, runs tools, and survives failures. `mindos.harness` is that wiring.

```python
from mindos.harness import HarnessEngine, ToolRegistry
from mindos.harness.models.claude import ClaudeBackend  # or KimiBackend, StubBackend

# 1. Snapshot a soul to disk (file-first context — Google Context Repos / Letta)
m.export_md("./snapshot")   # writes IDENTITY.md + MEMORY.md + FACTS.md + SOUL.md

# 2. Expose forged skills as tools the model can call
reg = ToolRegistry()
reg.load_from_skillforge(m.skills)

# 3. Run one turn with an explicit 1h prompt-cache TTL
engine = HarnessEngine(
    context_source="./snapshot",
    model=ClaudeBackend(model="claude-opus-4-6", cache_ttl="1h"),
    tools=reg,
    max_steps=20,
)
result = engine.run("帮我起草今天的 standup")
print(result.response, result.tokens, result.context_files)
```

**What you get for free**

- **File-first context** — the harness reads `IDENTITY.md → MEMORY.md → FACTS.md → Journal/` directly and applies a char budget with layered truncation (IDENTITY is non-negotiable).
- **Explicit prompt-cache TTL** — Anthropic silently flipped the default from `1h` back to `5m` on 2026-03-06 (20-32% cost inflation for long-lived agents). `ClaudeBackend` defaults to `ttl="1h"` and attaches `cache_control` to both the system block and the last tool block. Every `CompletionResult` surfaces `cache_ttl_used` so you can audit it.
- **Fail-soft tool dispatch** — tool errors become `tool_result` blocks the model can recover from, not exceptions that kill the turn.
- **Pluggable backends** — `ClaudeBackend` (Messages API), `KimiBackend` (K2 Thinking, OpenAI-compat, up to 200-300 tool calls per turn), `StubBackend` (deterministic, offline, for tests).
- **Cognition-safe by default** — single agent. Agent Teams are gated behind an explicit `agent_team=` flag (W4) so you don't accidentally ship the multi-agent failure mode Cognition documented in 2025-06.

**CLI**

```bash
# Offline demo (no API key required)
mindos harness run "你好" --backend stub --source ./snapshot

# Production
mindos harness run "draft the standup"           \
  --backend claude --model claude-opus-4-6       \
  --source ./snapshot --cache-ttl 1h --max-steps 20 --json
```

See `examples/harness_day2_demo.py` for a runnable end-to-end story (identity → export → forge skill → harness run → EvoLog breadcrumb), zero network required.

### W2 — Skills Registry + `skills.sh` packages

Built-in tools (`recall`, `commit`, `read_file`, `write_file`) land in the
registry in one call. File IO is jailed to an explicit sandbox root; no path
can escape via `..`.

```python
from mindos.harness import register_builtins, load_skill_dir, shipped_skills_dir

register_builtins(reg, mindos=m, sandbox_root="./workspace")
load_skill_dir(reg, shipped_skills_dir())  # advertises tdd-ship, personal-cache-audit
```

Skill packages follow the `agentskills.io` / Vercel `skills.sh` convention: a
directory (or `.zip`) containing `SKILL.md` with frontmatter (name, description,
version, tools). Loads are advertisement-only by default — the runtime handler
is opt-in via `handler=`.

### W3 — MCP Apps (SEP-1865) upgrade

`mindos.harness.mcp_apps` implements the 2026-03-15 spec:

- `initialize_response(...)` advertises `ui` / `elicitation` / `resource_templates`
  plus a `legacy` fallback path for 2024-11-05 clients.
- `UIComponent` yields `ui://{id}` resources, rejects both `html` + `iframe_url`,
  and enforces HTTPS iframe URLs.
- `elicitation_request` / `parse_elicitation_response` handle enum/required
  validation in one round-trip.
- `ResourceTemplate.expand(**params)` substitutes `{param}` tokens with URL
  quoting and rejects missing or stray keys.

Also in W3: `ContextLoader` (a `runtime_checkable` Protocol) lets PG+RLS
backends plug straight into `ContextBuilder` without dumping markdown to disk.
`_PathLoader` is the default filesystem implementation; soft-skips read errors
so the turn survives transient IO.

### W4 — Agent Teams (opt-in multi-agent)

Single agent is still the default. Opt in with `agent_team=[...]`:

```python
result = HarnessEngine(
    context_source=snap, model=ClaudeBackend(),
    tools=reg,
).run(
    "ship the overnight sync PR",
    agent_team=["code-reviewer", "release-notes-writer"],
)
for o in result.sub_agent_delegations:
    print(o.name, o.text)
```

Dispatch is **sequential with shared context** (per Cognition 2025-06): the
lead system prompt is stapled to each sub-agent, sub-agents have no tools, and
any sub-agent exception is absorbed as an error on its `SubAgentOutput`
without aborting the run. Results fold back into the lead's system prompt, not
the user turn, so the model sees them as prior context rather than a fresh
question.

### W5 — Overnight Soul Sync

```python
from mindos.harness.overnight import OvernightSoulSync, OvernightConfig

sync = OvernightSoulSync(m, config=OvernightConfig(
    consolidate_threshold=0.92,
    merge_facts_threshold=0.97,
    compress_older_than_days=30,
    archive_inactive_days=90,
    enable_reflection=False,   # opt-in
))
report = sync.run()            # or run(dry_run=True) for a preview
print(report.totals(), report.evo_log_id)
```

Orchestrates `consolidate → merge_facts → compress_episodes → archive_stale
→ reflect` with per-step fail-soft timing, a single `overnight_sync` EvoLog
row at the end, `only={...}` allow-list, and `on_event=` hooks for a
start/finish breadcrumb. Stores that implement only a subset of the steps
(e.g. PG+RLS mid-migration) soft-skip the missing methods instead of
crashing.

### W6 — OmeBench public benchmark driver

```python
from mindos.harness.omebench import OmeBench
from mindos.harness.models.base import StubBackend

bench = OmeBench(
    corpus_path="packages/mindos/omebench/sample_corpus",
    questions_path="packages/mindos/omebench/sample_questions.jsonl",
    model=StubBackend(reply_fn=my_oracle),
)
report = bench.run()
print(report.summary())
```

Or run from the shell:

```bash
python -m mindos.harness.omebench.cli \
    --corpus    packages/mindos/omebench/sample_corpus \
    --questions packages/mindos/omebench/sample_questions.jsonl \
    --backend   stub --verbose
```

Scoring is rule-based by default (`expected_contains` / `expected_any` /
`expected_regex` / `forbid_contains`) so public numbers are reproducible
without an LLM-judge. The v0 public board uses an authored corpus (53
interviews + a year of Journal + strategy notes) — until that lands every
number in this tree is from sample fixtures only and is **not** citable.

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

## Benchmark Results (LoCoMo)

Tested on the [LoCoMo](https://github.com/snap-research/locomo) long-conversation memory QA benchmark (conv-26: 419 messages, 199 questions across 4 categories):

| Question Type | Correct | Total | Accuracy |
|---------------|---------|-------|----------|
| Temporal | 35 | 37 | **94.6%** |
| Single-hop | 52 | 70 | **74.3%** |
| Multi-hop | 28 | 45 | **62.2%** |
| Open-domain | 12 | 47 | 25.5% |
| **Overall** | **127** | **199** | **63.8%** |

From 22% → 64% via two key innovations:
1. **Raw verbatim ingest** — store each message with session date, preserving every named entity
2. **LLM query expansion** — generate 6-10 topic keywords per question before FTS5 search

See `memorybench/scripts/run_mindos_raw.py` for the evaluation driver.

## Enterprise: PostgreSQL + RLS (v0.7.1+)

For multi-tenant deployments, Mindos supports an external store backend via dependency injection:

```python
from mindos import Mindos

# Default: SQLite (zero config)
soul = Mindos.load()

# Enterprise: inject a PostgreSQL store (e.g. PgMemoryStore from ome-server)
soul = Mindos.load("~/.mindos", store=my_pg_store)
soul = Mindos.init("~/.mindos", name="User", store=my_pg_store)
```

The `store=` parameter accepts any object implementing the `MemoryStore` interface. The `ome-server` package provides `PgMemoryStore` with:
- **Row-Level Security** — zero-trust tenant isolation at the database level
- **pgvector HNSW** — production-scale vector search (replaces in-process numpy)
- **tsvector + pg_trgm** — full-text + trigram search (replaces FTS5)
- **Zero-copy tenant migration** — anonymous → registered user is a metadata update

## Privacy

- All data lives locally in `~/.mindos/` (SQLite) by default
- No cloud, no accounts, no telemetry
- `mindos forget "pattern"` does GDPR hard delete
- Optional Bearer token auth via `MINDOS_AUTH_TOKEN`
- Enterprise PG mode: data in your own PostgreSQL, RLS enforces isolation

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
