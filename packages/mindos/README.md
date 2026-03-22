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
┌──────────────────────────────────────────────────────────────────┐
│                           Mindos                                  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ L0 海马体 (Hippocampus) —— 记忆                             │  │
│  │ 长期记忆 · 知识图谱 · 向量索引 · 遗忘曲线 · 情景记忆          │  │
│  │ ★ 灵魂的根基：用的越久越厚重，不可替代                      │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ L1 脑干 (Brainstem) —— 本能                                 │  │
│  │ 情绪状态机 · 作息节律 · 安全边界 · 条件反射式行为             │  │
│  │ hydrate 组装 · Token 预算 · 0 成本处理 60% 请求              │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ L2 皮层 (Cortex) —— 认知                                    │  │
│  │ commit 消化 · 事实/偏好/关系提取 · 日常对话 · 社交判断        │  │
│  │ 知识图谱更新 · 本地 7B 模型或宿主 LLM                        │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ L3 前额叶 (Prefrontal) —— 决策                              │  │
│  │ 深度推理 · 创作 · 战略规划 · 行为编排                         │  │
│  │ 冲突解决 · 优先级排序 · 通过 ModelRouter 调用最优 LLM         │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ L4 自我 (Self / Default Mode Network) —— 人格               │  │
│  │ 人格模型维护 · 反思循环 · 价值观守护 · 跨平台身份锚           │  │
│  │ ★ 从"大脑"到"灵魂"的涌现层                               │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ LayerRouter · ModelRouter · OmeFactory                      │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  对外接口：MCP Server · HTTP API · Python SDK · Ome Factory      │
└──────────────────────────────────────────────────────────────────┘
```

| 层 | 脑区 | 职责 | 延迟 | 成本 |
|----|------|------|------|------|
| **L0** 海马体 | Hippocampus | 你**记得**什么 | < 50ms | ≈ 0 |
| **L1** 脑干 | Brainstem | 你**本能**的反应 | < 100ms | ≈ 0 |
| **L2** 皮层 | Cortex | 你如何**理解**世界 | < 2s | 极低 |
| **L3** 前额叶 | Prefrontal | 你如何**决策** | 1-10s | 按需 |
| **L4** 自我 | DMN | 你**是谁** | 异步 | 极低 |

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

## File Structure

```
src/mindos/
├── core.py              Mindos facade (public API)
├── config.py            config.yaml + ModelRouter (DeepSeek/OpenAI/Anthropic/Ollama)
├── router.py            LayerRouter (orchestrates L0-L4)
├── server.py            HTTP server + lockfile auto-discovery
├── client.py            MindosClient (Python SDK + CLI proxy)
├── mcp_server.py        MCP Server (stdio JSON-RPC 2024-11-05)
├── store.py             SQLite memory store (WAL mode)
├── layers/
│   ├── l0_memory.py     Hippocampus: retrieval + relevance scoring
│   ├── l1_instinct.py   Brainstem: routing + hydrate + emotion state
│   ├── l2_cognition.py  Cortex: LLM commit digestion + rule fallback
│   ├── l3_decision.py   Prefrontal: reasoning + planning
│   └── l4_self.py       Self: reflection loop + drift detection
├── dashboard.py         Web UI
└── cli.py               CLI (auto-proxies to server)

~/.mindos/
├── identity.yaml        who you are
├── config.yaml          LLM providers
├── memory.db            SQLite (memories + KG + personality history)
├── server.lock          auto-created when server runs
└── journal/             future: raw conversation logs
```

## Contributing

Apache-2.0. PRs welcome. See `integrations/` for plugin examples.

---

*Part of [Omnity](https://github.com/wyonliu/Omnity) — SOAP (spatial AI protocol) + Mindos (digital soul protocol).*
