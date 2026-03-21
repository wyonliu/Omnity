# 第三方智能体接入、OpenClaw 与 MR 共见：路线图

本文回答两个问题：**别人养的 Agent（例如 OpenClaw 生态里的角色）怎么进 SOAP 场景？**以及 **另一个人通过 MR 眼镜怎么「看见」它们？** 结论先行：单靠 **SOAP v0.1（T1 语义）** 不够，需要 **分层契约 + 可选实时层 + 宿主集成**；下面按「现在能做的」与「下一版协议要长的」拆开。

---

## 1. 第三方开发者怎么参与（今天就能做的）

| 层级 | 做什么 | 产出 |
|------|--------|------|
| **读规范** | 阅读 `packages/soap/spec/SOAP-v0.1.md` 与 JSON Schema | 能手写或生成合法 `SOAPScene` |
| **校验** | `soap-validate` | CI 可门禁 |
| **可视化** | `soap-view` / `soap-explore` | 调试空间语义与角色视角 |
| **Agent 侧** | 在自有系统里实现 **MCP Client**，调用 **`soap-mcp`**（或自研 HTTP 版同一 API） | 用自然语言或代码查询场景 |
| **讨论与 RFC** | GitHub Discussions | 提案 **Guest Agent**、`bindings` 扩展字段 |

**最小集成故事**：第三方写一个「适配器」，把自己的 Agent 状态映射为一个 **`ObjectInstance`**（`uri`、`type`、`reality`、`bindings`、`state`），合并进场景的 `objects[]` 或通过 **场景片段 PATCH**（v0.2+ 可定义）注入。无需 fork Omnity，只需遵守 Schema。

---

## 2. 「OpenClaw 养的小龙虾」进商场：需要哪几层能力

### 2.1 身份与呈现（SOAP 能管的）

- 在 SOAP 里登记一个 **访客实体**，例如：  
  `id: guest_openclaw_lobster_01`，`type: agent.openclaw.avatar`（或通用 `agent.external`），`reality: virtual` 或 `mixed`。  
- **`bindings`** 建议预留：  
  - `external_agent_ref`: OpenClaw / 其它系统的稳定 ID  
  - `control_plane`: 回调 URL 或 MCP 端点（仅元数据，不强制实现）  
- **`twin_anchor_uri`**：锚到商场内某一 `soap://` 物理位置，MR 才知道贴在哪。

这样 **SOAP-View / soap-mcp** 立刻能列出「有一只外部小龙虾」；**不等于**它会动、会说。

### 2.2 行为与对话（SOAP 故意薄的）

- **移动路径**：超出 T1；需要 **T2/T3（几何/时序）** 或 **独立「轨迹流」**（例如 WebSocket 推送 pose 序列）。  
- **多 Agent 对话**：更适合 **MCP / A2A / 自建 message bus**；SOAP 提供 **「谁在谁旁边」** 的空间上下文，对话内容可走另一条协议。

**务实组合**：OpenClaw 侧负责「虾的脑」；Omnity 侧提供 **SOAP 场景 + soap-mcp**；中间一层 **bridge**（小服务）把 OpenClaw 状态 **投影** 为 SOAP JSON 并可选推送位姿。

### 2.3 让「另一个人用 MR 看见」

MR 客户端需要三件事（与是否 OpenClaw 无关）：

1. **同一份空间契约**：SOAP 场景（或子集）+ 坐标系说明。  
2. **虚实分层**：按 `reality` / `mixed` 过滤要渲染的实体；虚拟虾用 `virtual` + `twin_anchor_uri`。  
3. **（可选）实时同步**：若多人共见同一虾，需要 **会话房间 / 状态同步**（WebRTC DataChannel、MQTT、或游戏引擎 Netcode）——**不属于 SOAP v0.1 范围**，但应在文档里写清 **Profile**（例如 `SOAP+LivePresence v0.1` 未来 RFC）。

**一句话**：SOAP 回答 **「虾在语义上站在哪个店门口」**；MR 引擎回答 **「怎么画在镜片上」**；实时中台回答 **「多人看到的虾是否同一只」**。

---

## 3. 与 Conformance Tier 的对齐（避免过度承诺）

| Tier | 第三方 + MR 能做什么 |
|------|----------------------|
| **T1** | 共享 **同一套物体 ID / URI / 区域 / 关系**；MR 可静态摆放虚拟虾（手动或预计算）。 |
| **T2** | 几何一致（碰撞体、高度）对齐；虾与障碍物关系可验证。 |
| **T3** | 时间轴、回放、简单动画与 GenerativeAgentsCN 式 **movement.json** 可类比。 |
| **T4** | 低延迟控制回路；多设备实时一致（难，需产品与法务一起上）。 |

当前实现：**soap-view = T1 可视化 + 关系图**；**Phaser 像素层**是展示，不宣称 T4。

---

## 4. 建议的下一步（可写进 RFC 的题目）

1. **`bindings` 扩展注册表**：`external_agent_ref`、`openclaw.*`、`presence.session_id` 等（Discussions 征集前缀）。  
2. **`POST /api/scene/patch` 或 MCP tool**：仅限本地调试的 **访客注入**（安全模型另议）。  
3. **「SOAP Profile: GuestAgent」** 一页纸：必填字段 + 推荐交互（仍不绑定 OpenClaw 私有 API）。  
4. **示例 bridge 仓库**（可选）：Python 读 OpenClaw 导出 → 写 `mall-mixed-reality.json` 片段（社区维护，不必进核心 monorepo）。

---

## 5. 合规与品牌

- **OpenClaw**、**OpenAI**、各 MR 平台均为第三方商标；文档中仅作 **互操作举例**，不暗示隶属关系。  
- 参考 **[GenerativeAgentsCN](https://github.com/x-glacier/GenerativeAgentsCN)** 时：我们采用 **Phaser + pixelArt** 的**范式**，**不复制**其 tilemap 与精灵资源；对方仓库为 **Apache-2.0**，若未来直接引用代码须按许可证保留声明。

---

*与 [`PROTOCOL_VISION_AND_EXECUTION.md`](./PROTOCOL_VISION_AND_EXECUTION.md)、[`WORK_PLAN.md`](./WORK_PLAN.md) 一并迭代。*
