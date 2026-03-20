# Omnity

**Omnity** = Omni + Unity — 万物智联。个人开源的 **空间智能体（Spatial AI Agent）** 栈：从开放协议与工具链，到多层脑 Agent OS、个体养成、多智能体社会与经济，再到 **OmeTown** 虚实共生体验。

> 与雇主及任何公司业务 **无隶属关系**；本仓库代码与文档默认不包含特定企业场景或机密材料。

- **仓库**：[`github.com/wyonliu/Omnity`](https://github.com/wyonliu/Omnity) · `git@github.com:wyonliu/Omnity.git`
- **作战手册**（路线图与阶段验收）：[`ometown_execution.md`](./ometown_execution.md)
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

Omnity is an open-source stack for **AI agents in real 3D space**: **SOAP** (spec + tools + `soap-mcp`), **Mindos** (layered brain OS), **Ome** (personal agent), **Maxim** (multi-agent society + economy), and **OmeTown** (integrated experience).  
**License:** Apache-2.0. **Community:** GitHub Discussions.

---

*Build in Public · Ship Every Month*
