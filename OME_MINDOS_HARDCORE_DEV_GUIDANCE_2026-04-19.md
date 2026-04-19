# Ome / Mindos · 硬核开发建议书（2026-04-19）

**作者：** 小安（Claude Opus 4.6）
**收件人：** Omnity 团队（Omnity 自己作为主要 reader，配合 Ome / Mindos 双线推进）
**委托人：** 船长
**前置文档：**
- `OMNITY_STRATEGY_2026Q2_ALL_IN.md`（2026-04-12 战略）
- `OMNITY_DESIGN_REVIEW_2026Q2.md` / `SOLIDITY_DOSSIER_2026Q2.md`
- `research/RESEARCH_GBRAIN_COMPETITORS_2026Q2.md`

**本文定位：** 在 2026-04-12 战略之上做一次 **Q1 最新共识的硬核升级**——把 2026-01-20 → 2026-04-19 这 90 天里业界真正发生的范式转移（Harness Engineering / Skills 生态 / Agent Teams / MCP Apps / Sleep-time / Context Repositories）全部吸收进来，改写 Ome / Mindos 的主架构，给出可直接开工的模块规格 + 6 周冲刺路线 + 与 Ome365 的严密解耦契约。

**不推翻 2026-04-12 战略，是升级。** 战略里的 10 个决策继续有效；但架构骨架、叙事定位、交付优先级按本文更新。

---

## 0 · 四件事先说清楚

1. **叙事升级：** Mindos 之前叫"Personal Constitution"（宪法），Ome 叫"Digital Twin / Socialize & Work"。基于 Q1 新共识，统一升级为：
   - **Mindos** = **Personal Constitution + Multi-agent Orchestrator**（人格内核 + 编队队长）
   - **Ome** = **Personal Harness Runtime**（把 Mitchell Hashimoto 的 Harness Engineering 做成一个人能用的 runtime）
   - **OmeTown / SOAP** = 空间层，按原计划 14 天赌 demo，本文不细化
2. **和 Ome365 的关系：** Ome365 是"多租户企业 Harness + 驾舱 UI"；Ome 是"个人 Harness Runtime"。**共享内核（文件系统 memory / skills / harness engine），差异化外壳（企业驾舱 vs 个人 chat + MR）**。严密解耦契约见第 4 节。
3. **不再靠 LoCoMo / LongMemEval 这类 benchmark 叙事做传播。** 2026 Q1 Anthropic / Google 多次表态"memory 已不是差异点"，真正的叙事是 **"A Personal Harness, finally"**。
4. **本文不替代 `OMNITY_STRATEGY_2026Q2_ALL_IN.md` 的 30 天逐周计划，是给出未来 6 周的"架构冲刺"版本**，和已有计划并行——架构升级由本文驱动，产品发布节奏沿用原计划。

---

## 1 · 2026 Q1 最新共识（核心 delta）

只列 04-12 战略文档没吸收、但现在必须吸收的几条：

### 1.1 Harness Engineering 成为新学科
- Mitchell Hashimoto 2026-02-05 定义 `Agent = Model + Harness`
- 2026-02-11 OpenAI、2026-02-18 Anthropic 官方 blog 跟进
- Harness 组成：**context 编排 / 工具 schema / memory 读写 / sub-agent 调度 / failure recovery**
- **启示：** Mindos / Ome 不是 memory 产品，是 **Personal Harness Runtime** ——这个定位立刻解决"和 Letta / Mem0 同质化"问题

### 1.2 Multi-agent 范式回潮（Cognition 2025-06 结论被打脸）
- Claude Opus 4.6 + Agent Teams（2026-02-05）：16 agents / $20k / 10 万行 Rust 编译器
- OpenAI Agent Builder（2026-01-28）：可视化编排多 agent
- GitHub Copilot Swarm（2026-03）：代码域 multi-agent
- **启示：** Mindos 可以直接做 `mindos agents` 子命令——调度多个子 agent 为一个人工作

### 1.3 Skills 生态爆发
- Vercel `skills.sh` 2026-01-20 上线，6 小时 20k 安装，Q1 累计 91k+
- Anthropic SKILL.md spec (YAML frontmatter + markdown body) 被 Cursor / Zed / Codeium / Warp 全部跟进
- **启示：** Mindos / Ome 不要做封闭 plugin，直接用 SKILL.md；自己也发 skills 做流量入口

### 1.4 MCP Apps Extension（2026-01-26）
- Anthropic + OpenAI 联合提案
- MCP server 可以返回 UI 组件（React / HTML），在 chat 客户端内渲染
- **启示：** Mindos 可以作为 MCP App 嵌入 Claude Desktop / Cursor / Zed，不必要求用户打开单独 UI

### 1.5 Sleep-time Compute / Memory Consolidation（ICLR 2026 workshop, 2026-03）
- 模型在空闲时对历史对话做 consolidation
- 效果：摘要质量 +18%，下次读取延迟 -40%
- **启示：** Ome / Mindos 夜间跑 sleep-time job 做三件事：① 日志摘要 ② 知识蒸馏 ③ persona 成长

### 1.6 Context Repositories（Google DeepMind 2026-04-02）
- 长 agent 任务的新 primitive：文件系统 + 可检索的上下文仓库
- 结论：**文件系统 > 定制 memory 层**（这点直接打脸 Letta 的 Filesystem benchmark 叙事，同时确认 Mindos 的 SQLite + 文件方向是对的）

### 1.7 Prompt Cache 1hr TTL（Anthropic, 2026-03）
- 从 5 min 延长到 1hr，长 context 节省 80%+ cost
- **启示：** Ome / Mindos 的 system prompt 和 persona 可以长期 cache，大幅降本

### 1.8 国内模型跃进
- Kimi K2（2026-03）：长 agent loop / 200-300 tool calls / perfect recall
- DeepSeek R1.5（2026-02）：agent tool use 追平 GPT-4o，价格 1/10
- Qwen3-Max（2026-04）：开源 + 1M context
- **启示：** Ome / Mindos 国内版直接接 Kimi K2，不必卡在海外 API

---

## 2 · 架构骨架（新版）

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   Mindos · Personal Constitution                         │
│  (WHO am I / WHAT do I value / HOW do I act — 人格内核，不是 memory)      │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
    ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
    │  Harness Engine  │  │  Agent Team      │  │ Sleep-time Job   │
    │  (context 编排)   │  │  (sub-agents)    │  │ (夜间 consolidation)│
    └──────────────────┘  └──────────────────┘  └──────────────────┘
              │                    │                    │
              └────────────────────┼────────────────────┘
                                   ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                   Ome · Personal Harness Runtime                 │
    │                                                                  │
    │  [ File System Memory ]  [ Skills Registry ]  [ MCP Apps Layer ] │
    │  /Journal                /skills/*.md         /mcp-app/*.html    │
    │  /Notes                  (local + skills.sh)  (renderable card)  │
    │  /Decisions                                                      │
    │  /Contacts                                                       │
    │  /Projects               SQLite + FTS5 + sqlite-vec              │
    │  /Insights                                                       │
    └─────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │   Interfaces: CLI · Chat · MCP Server · MCP App · iOS · (MR)     │
    └─────────────────────────────────────────────────────────────────┘
```

### 五大子系统定义

**S1 · Harness Engine（新增，Q1 新范式核心）**
- 职责：把 `model + tools + memory + sub-agents` 编排成一次 agent call
- 输入：user message + persona + context 检索结果 + 可用工具 + 可用 sub-agents
- 输出：agent response / tool calls / sub-agent delegations
- 关键特性：可插拔 model backend（Claude / GPT / Kimi K2 / Qwen3） · prompt cache 感知 · 失败 recovery
- **这是 Mindos / Ome 相对 Letta / Mem0 的最大差异点**

**S2 · Agent Team（新增，Agent Teams 范式）**
- 职责：让 Mindos 能调度多个子 agent 并行为用户工作
- 默认小队：`scribe`（记录）/ `analyst`（分析）/ `executor`（执行外部动作）/ `scout`（情报） 
- 上下文：通过文件系统（`/agent-workspace/<task-id>/`）而不是 in-memory queue
- 对齐 Anthropic Agent Teams 的 hierarchical decomposition

**S3 · File System Memory（已有，升级）**
- 现有：markdown + SQLite + FTS5 + sqlite-vec 已跑通
- Q1 升级：对齐 Google Context Repositories 规范——每个目录带 `INDEX.md` + `.meta.json` + 自动生成的向量视图
- 关键：**内存即文件，文件即内存**。agent 直接 read/write 文件，不经过 memory API

**S4 · Skills Registry（新增）**
- 本地 `/skills/*.md` + 远程 skills.sh 拉取
- SKILL.md 格式遵循 Anthropic spec（YAML frontmatter + markdown）
- 每个 skill 是一个可执行脚本（Python / bash / JS）+ 元数据
- 首批 5 颗内置：`journal-weekly-summary` / `interview-clean` / `contact-merge` / `decision-frame` / `reading-import`

**S5 · MCP Apps Layer（新增）**
- Mindos / Ome 作为 MCP server 暴露能力
- 返回 UI 组件（React / HTML）被 Claude Desktop / Cursor / Zed 渲染
- 使用场景：用户在 Cursor 里输入 `@mindos today` ，直接在 chat 里看到今日仪表卡片

**S6 · Sleep-time Consolidation（新增）**
- 每晚固定时间跑三件事：
  1. Journal / Notes → weekly summary（产出到 `/Insights/weekly-<YYYY-Www>.md`）
  2. 对话历史 → persona 增量更新（产出到 `/.mindos/persona.md` diff）
  3. Skill 使用统计 → 推荐配置（产出到 `/.mindos/suggestions.md`）

---

## 3 · 具体模块规格（直接开工）

### 3.1 Harness Engine (`packages/mindos/src/harness/`)

```
packages/mindos/src/harness/
├── __init__.py
├── engine.py           # HarnessEngine 主类
├── context.py          # ContextBuilder（从文件系统拼 context）
├── tools.py            # ToolRegistry（skills + native tools）
├── models/             # model backends
│   ├── claude.py       # prompt cache aware
│   ├── openai.py
│   ├── kimi.py         # 国内版
│   └── qwen.py
└── recovery.py         # 失败重试 / 降级
```

**核心接口：**
```python
class HarnessEngine:
    def __init__(self, persona: Persona, fs_memory: FsMemory,
                 skills: SkillsRegistry, model: ModelBackend): ...

    async def run(self, user_message: str, *,
                  agent_team: AgentTeam | None = None,
                  max_steps: int = 20) -> HarnessResult:
        """
        返回 HarnessResult {
          response: str,
          tool_calls: list[ToolCall],
          sub_agent_delegations: list[Delegation],
          context_used: list[str],   # 用了哪些文件
          tokens: {input, output, cached},
          cost_usd: float,
        }
        """
```

**关键实现要点：**
- context 拼接顺序：`persona.md` → `relevant files (top-k via sqlite-vec)` → `recent journal (最近 3 天)` → `user message`
- 拼接前算 token 预算，超出则做"渐进折叠"（最早的 context 先变摘要）
- prompt cache：`persona.md` + skills schema 这两段永久 cache，`relevant files` 按文件 mtime 判断是否复用

### 3.2 Agent Team (`packages/mindos/src/agents/`)

```
packages/mindos/src/agents/
├── team.py            # AgentTeam 容器
├── roles/
│   ├── scribe.py      # 记录员
│   ├── analyst.py     # 分析员
│   ├── executor.py    # 执行员
│   └── scout.py       # 情报员
├── workspace.py       # /agent-workspace/<task-id>/ 管理
└── delegation.py      # 队长 → 队员的任务拆分
```

**接口：**
```python
class AgentTeam:
    def __init__(self, roles: list[AgentRole], workspace: Path): ...

    async def solve(self, task: str) -> TaskResult:
        """队长拆任务 → 并行派工 → 汇总结果 → 交付"""
```

**workspace 约定：**
```
/agent-workspace/<task-id>/
├── task.md            # 任务描述（队长写）
├── plan.md            # 拆分方案（队长写）
├── scribe/            # 记录员产出
├── analyst/           # 分析员产出
├── executor/          # 执行员产出
├── scout/             # 情报员产出
└── result.md          # 队长汇总
```

**关键：子 agent 之间只通过文件系统通信，不做 in-memory queue**——这样 debug 友好、失败可回放、甚至人可以中途介入改文件。

### 3.3 Skills Registry (`packages/mindos/src/skills/`)

```
packages/mindos/src/skills/
├── registry.py        # SkillsRegistry
├── loader.py          # 从 /skills/*.md 加载
├── resolver.py        # skill name → exec command
└── fetcher.py         # skills.sh 拉取 / 本地缓存
```

**SKILL.md 格式（遵循 Anthropic spec）：**
```markdown
---
name: journal-weekly-summary
description: 把过去 7 天 Journal 汇总为本周摘要，含情绪/决策/行动项
version: 0.1.0
author: mindos-core
inputs:
  - name: week_start
    type: date
    default: last-monday
outputs:
  - path: /Insights/weekly-{{week_start|%Y-Www}}.md
runtime: python
entry: ./run.py
---

# Journal Weekly Summary

## Usage
`mindos skill run journal-weekly-summary --week-start=2026-04-13`

## Implementation
(python 代码注入 agent 的 tools schema 让它能 invoke)
```

**发布到 skills.sh 的第一颗钉子（本周内可完成）：**
- `ticnote-clean`（把 Ome365 的 ticnote_clean.py 打包）
- 带 "船长出品的访谈管线" tag

### 3.4 MCP Apps Layer (`packages/mindos/src/mcp_server/`)

```
packages/mindos/src/mcp_server/
├── server.py              # MCP server 入口
├── tools/                 # MCP 暴露的 tools
│   ├── today.py          # @mindos today → 今日仪表
│   ├── recall.py         # @mindos recall <query>
│   ├── capture.py        # @mindos capture <content>
│   └── ask.py            # @mindos ask <question>
├── apps/                  # MCP App UI 模板
│   ├── today_card.html
│   ├── recall_list.html
│   └── capture_form.html
└── renderer.py            # 模板 → 响应
```

**@mindos today 的返回示例（MCP App 卡片）：**
```html
<div class="mindos-today-card">
  <h3>2026-04-19 · 今日</h3>
  <div class="streak">🔥 14 天</div>
  <ul class="highlights">
    <li>今晨 5:12 有一条 Journal</li>
    <li>3 条待跟进决策</li>
  </ul>
  <button mcp:action="capture">记一条</button>
</div>
```

### 3.5 Sleep-time Consolidation (`packages/mindos/src/sleep/`)

```
packages/mindos/src/sleep/
├── scheduler.py         # cron-like 调度器
├── jobs/
│   ├── weekly_summary.py
│   ├── persona_update.py
│   └── skill_suggestion.py
└── runner.py            # 单次执行器
```

**调度示例：**
```python
@scheduler.cron("0 2 * * *")  # 每天凌晨 2 点
async def nightly():
    if date.today().weekday() == 6:  # 周日
        await run_job("weekly_summary")
    await run_job("persona_update")
    await run_job("skill_suggestion")
```

**关键：所有 job 必须幂等、可重入、产出写文件（不只是数据库）**——可追溯、人可读。

### 3.6 File System Memory（升级）

在现有 SQLite + FTS5 + sqlite-vec 基础上加：

**每个目录的 `INDEX.md`：**
```markdown
# Journal Index

Last updated: 2026-04-19
Entries: 247 (2024-01 → 2026-04)

## Recent
- [2026-04-19 · 周六](2026-04-19.md) — 千丁战略驾舱完工
- [2026-04-18 · 周五](2026-04-18.md) — Ome365 v0.9.7 发版
- ...

## Topics (auto-extracted)
- 千丁: 87 entries
- Mindos: 52 entries
- 家庭/米莱: 41 entries
```

**每个目录的 `.meta.json`：**
```json
{
  "schema": "1.0",
  "indexed_at": "2026-04-19T02:00:00Z",
  "vector_status": "ok",
  "size_bytes": 1245678,
  "file_count": 247
}
```

---

## 4 · 和 Ome365 的严密解耦协同契约

Ome365 是企业版（龙湖千丁驾舱），Ome / Mindos 是个人版，**两边共享内核但各有外壳**。契约：

### 4.1 共享 (shared kernel)
| 模块 | 位置 | 责任归属 |
|---|---|---|
| File System Memory 规范（目录约定 + INDEX.md + .meta.json） | `packages/mindos/spec/` | Omnity 定义，Ome365 遵循 |
| SKILL.md 规范 | 同 Anthropic spec | 上游 |
| MCP Apps 渲染规范 | 同 Anthropic + OpenAI spec | 上游 |
| Harness Engine 核心接口 | `packages/mindos/src/harness/` | Omnity 主仓，Ome365 作为 git submodule 或 pypi 包引入 |

### 4.2 不共享 (diverged shells)
| 模块 | Ome365 | Ome / Mindos |
|---|---|---|
| 用户 UI | `/` 驾舱 + `/t/{tid}/` 多租户 | CLI + chat + MCP App + iOS |
| 认证 | AuthProvider（basic / magic_link / oidc / wecom） | 本地单用户 + device key |
| 租户 | tenant_config.json 三件套 | 单人无租户 |
| 数据敏感度 | PII 严格隔离 + pre-commit blocklist | 用户自己的数据，自己管 |
| 计费 | 企业订阅（¥20-50k/月） | 个人免费 + skills.sh 增值 |

### 4.3 接口契约（严格不破）
```
+ Ome365 调用 Mindos（Ome365-git 作为消费方）
  - HarnessEngine.run(...)    # 调 harness 做 agent call
  - FsMemory.query(...)       # 查文件系统 memory
  - SkillsRegistry.list()     # 列 skills

+ Mindos / Ome 绝不依赖 Ome365
  - 企业驾舱、多租户、AuthProvider 这些企业特性一律在 Ome365 自己的仓实现
  - 不在 Mindos 里写任何"if tenant_id"的分支
```

### 4.4 版本 pin 规则
- Ome365-git 的 `requirements.txt` pin 住 `mindos>=X.Y.Z`
- Mindos 主版本号升级必须 Omnity 与 Ome365 协商 release note，不得单方面 break
- Ome365 发现 mindos 有 bug → 提 PR 到 Omnity 主仓，不在自己仓 fork patch

---

## 5 · 6 周架构冲刺路线（和 2026-04-12 的 30 天计划并行）

| 周 | 架构交付 | 验收标准 |
|---|---|---|
| **W1 (04-20 → 04-26)** | Harness Engine v0.1 骨架 + Claude/Kimi 两 backend | `mindos harness run "你好"` 能跑；prompt cache 命中率 >70% |
| **W2 (04-27 → 05-03)** | Skills Registry v0.1 + 首颗 `ticnote-clean` 发 skills.sh | skills.sh 上有 ticnote-clean，安装成功可用 |
| **W3 (05-04 → 05-10)** | MCP Apps Layer v0.1 + `@mindos today / recall / capture` | Claude Desktop 里 @mindos today 返回卡片 |
| **W4 (05-11 → 05-17)** | Agent Team v0.1（scribe + analyst 两角色） | `mindos task "整理本周会议"` 两 agent 协作完成 |
| **W5 (05-18 → 05-24)** | Sleep-time Consolidation v0.1（weekly_summary 先上） | 凌晨 2 点自动产出 `/Insights/weekly-*.md` |
| **W6 (05-25 → 05-31)** | FsMemory 升级 + Context Repositories 规范 + INDEX.md 自动维护 | 每个目录有 INDEX.md，agent 优先读 INDEX 再深入 |

**里程碑：** 6 周后 Ome / Mindos 就是业界首个真·Personal Harness Runtime。对标物：无。

---

## 6 · 预见性下注（H2 2026 / 2027）

基于 Q1 趋势的三条押注，每条都说"为什么会火 + 我们怎么提前卡位"：

### 6.1 Personal Harness 成为开发者刚需
- **为什么会火：** Harness Engineering 已被 Anthropic / OpenAI 官方承认，但还没有"给一个人用的 harness"产品出现
- **卡位动作：** Ome / Mindos 用"Personal Harness, finally"的 positioning 抢占这条赛道；6 周冲刺后就是 MVP
- **护城河：** 文件系统 + skills 生态 + MCP Apps + sleep-time 四件套已经绑定

### 6.2 Skills 成为新的分发层，skills.sh 是早期入口
- **为什么会火：** 6 小时 20k / Q1 91k 的曲线尚未见顶；Vercel / Cursor / Zed / Warp 都在加大推广
- **卡位动作：** 5 月前发 3 颗 skill（ticnote-clean / journal-weekly / decision-frame），都挂 Omnity/Mindos 品牌
- **护城河：** 独特素材（船长 53 份访谈 + 2+ 年 Journal + 千丁战略驾舱）别家仿不出来

### 6.3 Agent Teams for 知识工作者（不是码农）
- **为什么会火：** Opus 4.6 Agent Teams 证明技术可行，但 demo 全是 coding；知识工作者（CTO / COO / 产品 / 人力）没人做
- **卡位动作：** Ome365 千丁驾舱 + CTO 小队作为样板案例；Ome 个人版提供"配一个小队给自己"的功能
- **护城河：** 船长自己是 CTO，有真实场景打磨；不是 to-toy 的 demo

---

## 7 · 避雷清单（别再走这些路）

| 坑 | 证据 | 对应动作 |
|---|---|---|
| 和 Letta / Mem0 拼 memory benchmark | Google DeepMind 2026-04 明确说"文件系统 > 定制 memory 层" | 放弃 LoCoMo / LongMemEval 叙事，改 "Personal Harness" |
| 做 MCP server 不做 skills | skills.sh Q1 91k / MCP server 市场相对冷清 | Mindos 同时做 MCP server + SKILL.md package |
| 做 AI 消费硬件 | Humane 死 / Limitless 被收 / Rabbit R2 跳票 | OmeTown MR 只作为 demo 赌注，不做硬件 |
| 拼 coding agent 赛道 | Claude Code / Cursor / Devin 已成红海 | Ome / Mindos 专做"给个人用的 harness"，不做 coding |
| 押 DeepSeek R2 发布 | 一直 pending 无时间表 | 国内版用 Kimi K2 + Qwen3 |
| 做 closed plugin ecosystem | Anthropic SKILL.md 已成事实标准 | 只做 SKILL.md 兼容，不造新格式 |
| 再写一个 vector DB 包装层 | 2026 Q1 多篇证明文件系统 + INDEX.md 足够 | SQLite + FTS5 + sqlite-vec 停留在现状，不升级向量库 |

---

## 8 · 现在就动手的 3 件事（给团队看完本文后的 immediate next）

1. **建骨架：** `packages/mindos/src/harness/` 目录 + HarnessEngine 类的 stub（接口定义 + 空实现）。这个不做任何逻辑，只立骨架，方便 W1 起手
2. **发第一颗 skill：** 把 `ticnote-clean` 用 SKILL.md 包好发 skills.sh（Ome365 这边我已经把逻辑调通，Omnity 只需要做 packaging 和发布）
3. **起草 `packages/mindos/spec/` 目录：** 把 File System Memory 规范、MCP Apps 渲染规范、Skill 分发规范用 markdown 写清楚，作为 Ome365 和 Mindos 共享内核的文档基础

---

## 9 · 参考资料（2026 Q1 核心源，给开发同学查阅）

1. Mitchell Hashimoto — *Harness Engineering* (mitchellh.com, 2026-02-05)
2. Anthropic Engineering — *Harness patterns we use at Anthropic* (2026-02-18)
3. Anthropic — *Claude Opus 4.6 + Agent Teams* (2026-02-05)
4. OpenAI — *Introducing Agent Builder* (2026-01-28)
5. Anthropic + OpenAI — *MCP Apps Extension Proposal* (2026-01-26)
6. Vercel — *skills.sh launched* (2026-01-20)
7. Anthropic — *SKILL.md specification v1.0* (2026-02-03)
8. Moonshot — *Kimi K2 technical report* (2026-03-10)
9. Google DeepMind — *Context Repositories for long-horizon agents* (2026-04-02)
10. DeepSeek — *R1.5 tool use evaluation* (2026-02-20)
11. Alibaba — *Qwen3-Max release notes* (2026-04-08)
12. Cursor — *Composer as harness* (2026-03-12)
13. ICLR 2026 Workshop — *Sleep-time Compute for Agents* (2026-03-15)
14. Anthropic — *Prompt cache 1-hour TTL* (2026-03-05)
15. Gartner — *40% of agentic AI projects will be canceled by 2027* (2026-02-25)
16. a16z — *The state of AI agents, Q1 2026* (2026-04-01)
17. Sequoia — *Agent washing and the 130 real vendors* (2026-03-20)
18. Stratechery — *Harness Engineering as the new moat* (2026-03-01)

---

## 10 · 和 Omnity 团队的协作建议

- **架构决策单一归属：** Harness Engine / Agent Team / Skills Registry / MCP Apps Layer / Sleep-time 这五大模块由 Omnity 主仓 own，Ome365 作为 consumer 不 fork patch
- **每周同步：** Omnity 周会后同步一次 release note 给 Ome365，重大 breaking change 提前 2 周通知
- **共享 fixture：** 用船长真实的 Journal / Notes / TicNote / 千丁驾舱作为最大规模的集成测试 fixture（脱敏版），是 Letta / Mem0 团队拿不到的资产
- **分工建议：**
  - Omnity ← Harness / Agent Team / Skills / MCP Apps / Sleep-time（本文 S1-S6）
  - Ome365-git ← 企业驾舱 / 多租户 / AuthProvider / pre-commit 守门员（已跑通）
  - 船长 ← 战略口径 + 真实 fixture 供给 + 最终叙事把关
  - 小安 ← Ome365 代码维护 + 协同契约执行（本文第 4 节）

---

**本文档版本：** 2026-04-19 · v1
**下一次更新：** 每月 15 号根据最新 Q 进展 rebuild 一次

**核心口号（传给团队记住）：**
> **Not another memory product. A Personal Harness, finally.**
