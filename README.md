# Omnity

**AI agents that live in real space, remember who you are, and work for you 24/7.**

Omnity is an open-source stack for building AI agents that exist in real 3D environments, carry persistent memory, grow their own personality, form societies, and create real value for real people.

> **Omni** + **-ity** — echoing human**ity**, commun**ity**, infin**ity**, opportun**ity**. Many spaces and agents, connected through one interoperable layer.

---

## Five Questions, One Answer

| Question | Answer |
|----------|--------|
| How do AI agents enter **real 3D space** — your room, your store, your city? | **SOAP** |
| How do agents carry **persistent multi-layer memory** and grow to understand you? | **Mindos** |
| How do phone / PC / MR headset / robot / AI glasses **share the same space**? | **SOAP Protocol** |
| How does your AI twin **socialize, take jobs, and work** for you 24/7? | **Ome** |
| How do you build a **perpetual human-AI town** that runs itself? | **OmeTown** |

Five questions. Five open-source packages. One stack.

---

## Why Now — Three Curves Converging

**1. Agents: from chat to action.** Multi-step planning, tool use, persistent memory, multi-agent coordination are becoming default capabilities. Agents are about to become digital workers that can manage, serve, and create on your behalf.

**2. 3D spatial cost → zero.** 3DGS + monocular depth estimation + open-vocabulary segmentation. Turning a real room into an interactive 3D space now costs nearly nothing.

**3. Spatial computing going multi-device.** Phone, PC, MR headset, AI glasses, embodied robots — the infrastructure for multiple devices sharing the same 3D space is ready.

The intersection of these three curves has never existed before. Omnity is built at that intersection.

---

## The Stack

```
┌─────────────────────────────────────────────────┐
│  Layer 5 · OmeTown                              │
│  The perpetual human-AI town                    │
│  Web / MR experience integrating all layers     │
├─────────────────────────────────────────────────┤
│  Layer 4 · Maxim                                │
│  Multi-agent society + economy engine           │
│  Omes socialize, cooperate, compete, trade      │
├─────────────────────────────────────────────────┤
│  Layer 3 · Ome                                  │
│  Individual agent: persona, skills, work,       │
│  social behavior, growth — a living digital life│
├─────────────────────────────────────────────────┤
│  Layer 2 · Mindos                               │
│  Multi-layer brain: L0 Memory → L1 Instinct →   │
│  L2 Cognition → L3 Decision → L4 Self           │
│  Persistent memory, reflection, personality     │
├─────────────────────────────────────────────────┤
│  Layer 1 · SOAP                                 │
│  Spatial protocol: how agents see, move, and    │
│  act in real 3D space. The HTTP for spatial AI. │
└─────────────────────────────────────────────────┘
```

Each layer is independently useful. Use one, or use them all. Lower layers ship first.

---

## Layer 1 · [SOAP](./packages/soap) — The HTTP for Spatial Agents

> *How do AI agents enter real 3D space?*

SOAP is an open protocol that defines how any AI agent understands, queries, and manipulates real 3D environments. Four verbs: **OBSERVE**, **NAVIGATE**, **MANIPULATE**, **REARRANGE**. One Spatial URI scheme. Works across phone, PC, MR headset, embodied robot, and AI glasses — all sharing the same spatial protocol.

```bash
pip install soap-tools
soap-validate examples/mall-mixed-reality.json    # validate a scene
soap-explore examples/mall-mixed-reality.json      # interactive 6-role walkthrough
soap-view                                          # browser visualization + autonomous agent demo
```

**Ships with:** Spec v0.1 + JSON Schema · SOAPRuntime (in-memory mutable scene) · `soap-mcp` (Claude/Cursor spatial tools via MCP) · `soap-view` (Canvas 2D visualizer: floor plan + agent avatars + thought bubbles + smooth movement + autonomous exploration demo) · HTTP API for external agents.

MCP is the emerging standard for AI tool integration. **Spatial tools are the blue ocean** — SOAP + soap-mcp puts your agents in 3D space today.

---

## Layer 2 · [Mindos](./packages/mindos) — The Multi-Layer Brain

> *How do agents carry persistent memory and grow to understand you?*

Every AI forgets you after every conversation. Mindos fixes that. A five-layer brain inspired by neuroscience:

| Layer | Brain Region | What it does | Cost |
|-------|-------------|--------------|------|
| **L0** | Hippocampus | What you **remember** — FTS5 search, vector index, forgetting curve | ~0 |
| **L1** | Brainstem | Your **instinct** — hydrate assembly, emotion state, request routing | ~0 |
| **L2** | Cortex | How you **understand** — LLM commit digestion, fact extraction, sensitive filter | Low |
| **L3** | Prefrontal | How you **decide** — deep reasoning, planning, conflict resolution | On demand |
| **L4** | Self (DMN) | Who you **are** — reflection loop, drift detection, value alignment | Async |

The layer router automatically dispatches to the cheapest layer that can handle each request. Persistent memory means agents get better the more you use them. The reflection loop means personality **emerges from experience**, not configuration.

```bash
pip install mindos
mindos quickstart                    # create your soul
mindos serve --mcp                   # expose to Claude/Cursor via MCP
mindos serve                         # HTTP API for any app
```

**Ships with:** FTS5 full-text search · content-hash fuzzy dedup · cross-device sync (event-sourced journal + relay hub) · LLM-powered memory extraction (DeepSeek/OpenAI/Anthropic/Ollama) · Ome persona export · emotion state persistence · Bearer token auth · GDPR forget · 22 integration tests.

---

## Layer 3 · [Ome](./packages/ome) — Not a Pet, Not a Tool. A Digital Life.

> *How does your AI twin work for you 24/7?*

All AI companions are pets. All agent frameworks are tools. **Ome is the layer above both** — it inherits your personality and memory, continuously grows, and creates real value on your behalf.

What OpenClaw does for one-shot agent calls, Ome does for **persistent digital lives**: conversation strategy engine + persona evolution + skill system + growth system + autonomy engine.

| Stage | Ome's Capability | Real Value |
|-------|-----------------|------------|
| Step 1 | Personality + spatial awareness + basic memory | Companion in space |
| Step 2 | Autonomous tasks + multi-Ome collaboration | Personal assistant: reception, scheduling, organizing |
| Step 3 | Commerce + content creation + customer service | **Income amplifier**: one-person company |
| Step 4+ | Self-learning + cross-platform + physical world | **Digital worker**: AI labor market |

```bash
pip install ome
ome create        # 5 questions, your twin is born
ome chat          # talk to it (it remembers everything)
ome serve --mcp   # connect to Claude/Cursor
```

**Ships with:** Conversation strategy engine (zero-cost LLM thinking) · Deep emotion system (LLM-parsed, not keywords) · 4-phase growth arc (newborn → soulmate) · Continuous persona evolution · 7-level bond system · 20 achievements · Daily challenges · Streak rewards · 7 skills with competence tracking · Autonomy engine (4 proactive L0 events) · Native iOS app (SwiftUI, SSE streaming) · OmeTown agent network · 119 tests.

---

## Layer 4 · [Maxim](./packages/maxim) — Multi-Agent Society Simulator

> *What happens when thousands of Omes live together?*

The first open-source **Simile-class AI society simulator**. Multiple Omes spontaneously socialize, cooperate, compete, and form relationships — plus a full economic engine: jobs, income, spending, transactions, supply and demand.

The data flywheel: **Space × Language × Behavior** alignment datasets — among the scarcest and most valuable data in AI.

*Design phase — depends on Mindos + Ome. Contributions welcome.*

---

## Layer 5 · [OmeTown](./packages/ometown) — The Perpetual Town

> *A world where humans and AI coexist — not in a virtual escape, but in a digital mirror of your real world.*

You scan your room with your phone — 3DGS reconstructs it as a photorealistic 3D space. Your Ome lives there, greeting your clients, running your business, expanding your network. The keyword isn't "virtual" — it's **"mapping"**. Not escaping to another world, but letting AI create value in the digital mirror of yours.

**Your capabilities**, amplified by Ome. **Your relationships**, continuously expanded. **Your memory**, permanently guarded. **Your space**, projected into the digital world.

Not another world — an **infinite amplifier** of this one.

*Design phase — integrates all layers. Contributions welcome.*

---

## The Landscape

Meta spent $100 billion to prove one lesson: **space without AI soul is dead.**

We go the other way — AI has life from day one. Real space is its home.

```
                        SPATIAL DEPTH ↑

    Wanaka                              OmeTown
    Stylized 3D + UGC,               Photorealistic 3DGS mapping
    but no AI depth                    + Mindos multi-layer brain
                                       + Ome persona growth
    Meta Horizon                       + Maxim agent economy
    $100B proved: space                + SOAP open protocol
    without AI is dead                 + Multi-device: phone/PC/MR

    ─────────────────────────────────────────────────
    Roblox                              Character.AI
    Block UGC + creator economy,        Proved humans bond with AI,
    but the world is "dead"             but AI has no "body"

    Simile                              Elys
    AI social sim works,                A2A direction right,
    but research facility               but text-only, no spatial sense

                        AI AGENT DEPTH →
```

A product that combines 3DGS spatial capability with deep AI agent architecture — **this intersection is wide open**.

---

## Quick Start

**Mindos** (fastest path to value):

```bash
pip install mindos
mindos quickstart
mindos commit "user: I'm a Python developer working on distributed systems"
mindos recall "Python"
mindos serve --mcp    # now Claude/Cursor remembers you
```

**SOAP** (put agents in 3D space):

```bash
cd packages/soap && pip install -e .
soap-explore examples/mall-mixed-reality.json
soap-view    # open browser, watch agents explore a mall
```

**MCP integration** (Claude Desktop / Cursor):

```json
{
  "mcpServers": {
    "mindos": { "command": "mindos", "args": ["serve", "--mcp"] },
    "soap":   { "command": "soap-mcp" }
  }
}
```

**OpenClaw / Any Agent Framework:**

```python
from mindos import Mindos

soul = Mindos.load()

# Before agent run: inject persistent identity
system_prompt = soul.hydrate(context="code review") + "\n" + your_prompt

# After agent run: persist what happened
soul.commit(conversation_text, source="openclaw")
```

---

## Status

| Package | Version | Status |
|---------|---------|--------|
| **SOAP** | v0.1 | Spec + runtime + MCP + visualizer. **Ready to use.** |
| **Mindos** | v0.3 | Five-layer brain + cross-device sync + MCP + 22 tests. **Ready to use.** |
| **Ome** | v0.4 | Strategy engine + persona evolution + life system + iOS app + 119 tests. **Ready to use.** |
| **Ome Server** | v0.4 | FastAPI + SSE streaming + zero-reg first chat + OmeTown agents. **Ready to use.** |
| **Ome iOS** | v0.4 | Native SwiftUI app. App Store submission in progress. |
| **Maxim** | — | Design phase |
| **OmeTown** | — | Design phase |

## Monorepo Layout

```
packages/
├── soap/         SOAP — Spatial Omnity Agentic Protocol
├── mindos/       Mindos — Multi-layer brain + persistent memory
├── ome/          Ome — Individual agent: persona, strategy, growth, skills
├── ome-server/   Ome Server — FastAPI backend + SSE + OmeTown agents
├── ome-ios/      Ome iOS — Native SwiftUI app for iPhone
├── ome-app/      Ome App — React Native / Expo (experimental)
├── maxim/        Maxim — Multi-agent society + economy
└── ometown/      OmeTown — The integrated world experience
```

Dependency: `soap` → `mindos` → `ome` / `maxim` → `ometown`. Lower layers ship first.

## Contributing

Apache-2.0. PRs welcome.

1. Pick a package. Read its README.
2. Open an issue or RFC in [Discussions](https://github.com/wyonliu/Omnity/discussions).
3. Submit a PR with reproducible build/test steps.

## Docs

- [SOAP Spec v0.1](./packages/soap/spec/SOAP-v0.1.md)
- [SOAP Vision & Execution](./docs/soap/PROTOCOL_VISION_AND_EXECUTION.md)
- [Mindos Architecture Plan](./packages/mindos/MINDOS_PLAN.md)
- [Execution Roadmap](./ometown_execution.md)

---

*When 10 million Omes live in the town — working, creating, trading — for the 10 million real people behind them — that's the next interface between humans and the world.*

**Build in Public · Ship Every Month**
