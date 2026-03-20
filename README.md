# Omnity

个人开源的 **空间智能体（Spatial AI Agent）** 栈：从开放协议与工具链，到多层脑 Agent OS、个体养成、多智能体社会与经济，再到 **OmeTown** 虚实共生体验。

> 与雇主及任何公司业务 **无隶属关系**；本仓库代码与文档默认不包含特定企业场景或机密材料。

## 为何是「Omnity」

**Omni**（全域 / 万千）+ **-ity**：与英语里一批表示「状态、场域、共同体」的词同构——既是造词，也是对终局的注脚。

- 人类：**human**ity  
- 附近：**vicin**ity  
- 无限：**infin**ity  
- 社区：**commun**ity  
- 机遇：**opportun**ity  

同时也叠合 **City**（城市）、**Unity**（连接）、**Humanity**（人文）：**万千空间与智能体，在同一套可互操作叙事里连接成一体**——不是单一 App，而是一层让「空间 × Agent × 人」共存的 **Omnity**。

文化脚注（个人向，与任何雇主无关）：**千空（Senku）** 隐喻「在物理世界的丛林里，用极客方式重建连接」；开源 Omnity 是把同一套理想，落在 **协议、代码与社区** 上。

**一句话**：Omnity = **万物智联** 的工程与开源表达；最底层那块「让 Agent 能进真实 3D 世界」的砖，就是 **SOAP**（空间智能体时代的 HTTP）。

- **仓库**：[`github.com/wyonliu/Omnity`](https://github.com/wyonliu/Omnity) · `git@github.com:wyonliu/Omnity.git`
- **作战手册**（路线图与阶段验收）：[`ometown_execution.md`](./ometown_execution.md)
- **SOAP 愿景与边界（最终版 v2.0）**：[`docs/soap/PROTOCOL_VISION_AND_EXECUTION.md`](./docs/soap/PROTOCOL_VISION_AND_EXECUTION.md) — 含「能否全行业一键协同」的深度论证与 **Conformance Tier**
- **活商场思想实验**：[`docs/soap/THOUGHT_EXPERIMENT_THE_LIVING_MALL.md`](./docs/soap/THOUGHT_EXPERIMENT_THE_LIVING_MALL.md)
- **SOAP 周粒度 backlog**：[`docs/soap/WORK_PLAN.md`](./docs/soap/WORK_PLAN.md)
- **SOAP v0.1 规范与代码**：[`packages/soap/`](./packages/soap/) · `soap-validate` · `soap-explore` · **`soap-view`**（浏览器可视化） · `soap-mcp`
- **可视化灵感与合规引用**：[`docs/soap/VISUALIZER_INSPIRATION.md`](./docs/soap/VISUALIZER_INSPIRATION.md)
- **社区**：[GitHub Discussions](https://github.com/wyonliu/Omnity/discussions)（RFC / Q&A / AMA）

## Monorepo 布局

| 路径 | 名称 | 一句话 |
|------|------|--------|
| [`packages/soap`](./packages/soap) | **SOAP** — Spatial Omnity Agentic Protocol | 空间智能体协议（`spec/`）+ `soap-scan` / `soap-sem` / `soap-edit` / `soap-render` / **`soap-mcp`** |
| [`packages/mindos`](./packages/mindos) | **Mindos** — Multi-layer Intention & Neural Dynamic Operating System | 多层脑、记忆与成本可控的持久 Agent OS |
| [`packages/ome`](./packages/ome) | **Ome** | 个体 Agent 养成（人格 / 技能 / 工作 / 社交 / 成长） |
| [`packages/maxim`](./packages/maxim) | **Maxim** — Multi-Agent Society: Interaction, eXchange & Multi-economy Modeler | 多 Agent 社会仿真 + 经济引擎 |
| [`packages/ometown`](./packages/ometown) | **OmeTown** | 集成上述能力的产品壳（Web / MR 体验） |

依赖方向（下层为地基）：**`soap` → `mindos` → `ome` / `maxim` → `ometown`**。下层未跑通前不强行上叠（见执行手册阻塞关系）。

## 许可策略

全仓库统一 [**Apache License 2.0**](./LICENSE)（见 [`NOTICE`](./NOTICE)）。

- **为何不用 MIT / 多许可混用**：SOAP 含「协议 + 参考实现 + MCP」形态，企业集成与二次分发场景多；**Apache-2.0** 的专利授权与贡献条款更清晰，**一个根许可证**减少 monorepo 分包时的合规解释成本。
- 若未来个别包需以其他许可证发布，再在子包目录增加明确 `LICENSE` 与根目录 `README` 说明（当前以统一 Apache-2.0 为准）。

## 快速参与

1. 阅读 [`ometown_execution.md`](./ometown_execution.md) 中 **Phase 0** 与「立即行动」。
2. 在 **Discussions** 开 RFC 或认领 issue（随工作流完善会补齐模板）。
3. 提交 PR 前请保证 **可构建 / 可复现** 的最小步骤写进对应 `packages/*/README.md`。

## English (short)

**Omnity** — *Omni* + *-ity*, echoing *humanity, vicinity, community, opportunity*: an open stack for **AI agents in real 3D space**. **SOAP** is the **HTTP for spatial agents** (spec + tools + `soap-mcp`); then **Mindos**, **Ome**, **Maxim**, **OmeTown**.  
**License:** Apache-2.0. **Community:** GitHub Discussions. **SOAP plan:** [`docs/soap/WORK_PLAN.md`](./docs/soap/WORK_PLAN.md).

---

*Build in Public · Ship Every Month*
