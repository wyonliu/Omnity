# Omnity

**An open-source stack for AI agents that live in real space and remember who you are.**

Omnity connects five layers: a spatial protocol for 3D environments, a persistent memory brain, individual agent personas, multi-agent society simulation, and a shared world where humans and AI coexist. Each layer is a standalone package. Use one, or use them all.

```
You ←→ AI Agents ←→ Real 3D Spaces
         ↕              ↕
      Mindos          SOAP
    (memory)       (spatial protocol)
         ↕              ↕
        Ome ←→ Maxim ←→ OmeTown
     (persona)  (society)  (world)
```

---

## Packages

### [SOAP](./packages/soap) — Spatial Omnity Agentic Protocol

**The HTTP for spatial agents.** An open protocol that lets any AI agent understand, query, and manipulate real 3D spaces through four verbs: OBSERVE, NAVIGATE, MANIPULATE, REARRANGE.

```bash
pip install soap-tools
soap-validate examples/mall-mixed-reality.json
soap-explore examples/mall-mixed-reality.json   # interactive 6-role walkthrough
soap-view                                        # browser visualization + agent demo
```

Ships with: spec v0.1 + JSON Schema, SOAPRuntime (in-memory mutable scene), `soap-mcp` (Claude/Cursor integration), `soap-view` (Canvas 2D visualizer with autonomous agent demo), HTTP API for external agents.

### [Mindos](./packages/mindos) — Your Portable Digital Soul

**Your AI forgets you after every conversation. Mindos fixes that.** A five-layer brain (Hippocampus → Brainstem → Cortex → Prefrontal → Self) that stores your identity, memories, and knowledge graph locally. Any AI can read and write to it.

```bash
pip install mindos
mindos quickstart          # create your soul
mindos serve --mcp         # expose to Claude/Cursor via MCP
mindos serve               # HTTP API for any app
```

Ships with: FTS5 search, content-hash dedup, cross-device sync, LLM-powered memory extraction (DeepSeek/OpenAI/Anthropic/Ollama), Ome persona export, emotion state, GDPR forget. 22 integration tests.

### [Ome](./packages/ome) — Individual Agent Persona

Persona, skills, workflows, social behavior, and growth for individual AI agents. Depends on Mindos; optionally connects to SOAP for spatial awareness.

### [Maxim](./packages/maxim) — Multi-Agent Society Simulator

Multi-agent scheduling, relationships, events, and economic simulation. Think Stanford Generative Agents meets agent-native economics.

### [OmeTown](./packages/ometown) — The Shared World

The product layer where humans and AI agents coexist in mixed-reality spaces. Integrates all packages above into a Web/MR experience.

---

## Architecture

```
Layer 0: SOAP (spatial protocol)
  ↓ agents can perceive and act in 3D space
Layer 1: Mindos (persistent memory + identity)
  ↓ agents remember who they are and who you are
Layer 2: Ome (individual persona) + Maxim (society)
  ↓ agents have personality, skills, relationships, economy
Layer 3: OmeTown (shared world)
  → humans and agents coexist in mixed-reality spaces
```

Each layer is independently useful. SOAP works without Mindos. Mindos works without SOAP. You don't need OmeTown to use the lower layers.

**Dependency direction** (bottom-up): `soap` → `mindos` → `ome` / `maxim` → `ometown`. Lower layers ship first.

## Why "Omnity"

**Omni** (all) + **-ity** — echoing humanity, vicinity, community, infinity, opportunity. Also blends City + Unity + Humanity: many spaces and agents, connected through one interoperable layer.

## Status

| Package | Version | Status |
|---------|---------|--------|
| SOAP | v0.1 | Spec + runtime + MCP + visualizer. Ready to use. |
| Mindos | v0.3 | Five-layer brain + sync + MCP. Ready to use. |
| Ome | — | Design phase |
| Maxim | — | Design phase |
| OmeTown | — | Design phase |

## Quick Start

**Use Mindos** (the fastest path to value):

```bash
pip install mindos
mindos quickstart
mindos commit "user: I'm a Python developer working on distributed systems"
mindos recall "Python"
```

**Use SOAP** (if you work with 3D spaces):

```bash
cd packages/soap
pip install -e .
soap-explore examples/mall-mixed-reality.json
```

**Use with Claude/Cursor** (MCP):

```json
{
  "mcpServers": {
    "mindos": { "command": "mindos", "args": ["serve", "--mcp"] },
    "soap":   { "command": "soap-mcp" }
  }
}
```

## Integration with OpenClaw / Agent Frameworks

```python
from mindos import Mindos

soul = Mindos.load()

# Before agent run: inject identity
system_prompt = soul.hydrate(context="code review") + "\n" + your_prompt

# After agent run: persist what happened
soul.commit(conversation_text, source="openclaw")
```

## Contributing

Apache-2.0. PRs welcome.

1. Pick a package. Read its README.
2. Open an issue or RFC in [Discussions](https://github.com/wyonliu/Omnity/discussions).
3. Submit a PR with reproducible build/test steps.

## Docs

- [SOAP Spec v0.1](./packages/soap/spec/SOAP-v0.1.md)
- [SOAP Vision & Execution](./docs/soap/PROTOCOL_VISION_AND_EXECUTION.md)
- [Mindos Plan](./packages/mindos/MINDOS_PLAN.md)
- [Execution Roadmap](./ometown_execution.md)

---

*Build in Public. Ship Every Month.*
