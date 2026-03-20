# SOAP：国民级空间协议 — 综合愿景与可执行版本

> 本文综合外部建议与 Omnity 既定方向，**统一对外叙事为 SOAP**（Spatial Omnity Agentic Protocol）。历史上讨论的「SCP / SDTP / SATP」等，在工程上收敛为 **SOAP 协议栈分层**（见下文），**不另立子品牌**，避免认知分裂。  
> 执行 backlog 仍以 [`WORK_PLAN.md`](./WORK_PLAN.md) 为周粒度清单；本文为「为什么做、做成什么、按什么顺序赢」。

---

## 一、根本定位：不是又一个 Agent 框架

| 维度 | OpenClaw 类框架 | **SOAP** |
|------|-----------------|----------|
| 解决的问题 | Agent 在 **2D 数字世界**里接工具、跑任务 | Agent 在 **3D 真实/虚拟空间**里被寻址、可感知、可行动、可协同、可进化 |
| 类比 | 应用层「瑞士军刀」 | **空间侧的 HTTP + URI**：资源如何命名、如何读状态、如何提交动作 |
| 与 OpenClaw 关系 | **互补**：OpenClaw 可挂载 `soap-mcp`，获得空间能力 | SOAP **不绑定**某一框架，服务所有 MCP / A2A 宿主 |

**一句话**：OpenClaw 让 Agent「会干活」；SOAP 让 Agent「有地方可站、有坐标可说、有动作可对空间生效」——包括数字孪生与纯虚拟世界，**同一套契约**。

**「超过 OpenClaw 热度」的理性含义**：Star 数是虚荣指标；**国民级**更应看：**MCP/宿主里的默认空间工具、外部独立实现数量、跨引擎场景文件互操作**。Star 可作为结果之一，不作唯一北极星。

---

## 二、SOAP 协议栈（五层，对内分层、对外统称 SOAP）

与 TCP/IP 类似：**下层不暴露给应用作者时，仍可说「我们支持 SOAP」**；文档里用 L1–L5 分解职责，便于实现与演进。

```
L5  应用画像（Profiles）     行业/场景模板、合规注意事项、示例场景库
L4  协同（Coordination）     多 Agent 锁、广播、会话、权限模型
L3  行为（Actions）          标准化动作原语 + 错误码 + 虚实映射槽位（Driver）
L2  上下文（Context）       拓扑图、语义本体、区域、可供性（Affordance）、空间记忆引用格式
L1  互操作承载（Payload）    场景文件封装、坐标系/锚点、虚实标签、增量更新、多格式适配（glTF/USD/3DGS…）
```

### 与「虚实互通、自进化、全场景交互」的对应关系

| 命题 | 主要落层 | 必须标准化的最小内容 |
|------|----------|----------------------|
| **虚实互通** | L1 + L3 + L4 | 物体的 `reality`/`binding` 元数据；**真实世界优先（Real-World Override）** 冲突规则；动作由 **Driver** 映射到 IoT/引擎 |
| **智能体自进化** | L2 + L5（可选 L4） | 交互轨迹、失败码、校正式反馈的 **可序列化记录格式**（供 Mindos 等消费）；**不强制**上传数据，仅定义「若贡献则长什么样」 |
| **真实↔虚拟交互** | L1–L3 | 统一 **Spatial URI**（见下）与同一套 Action 动词，底层是 GS 还是游戏引擎由 L1 Profile 说明 |

### 核心基石（极简、不可绕过）

1. **Spatial URI**（空间的 URL）  
   例：`soap://{space_id}/{zone_id}/{object_id}`（语法在 spec 中严格定义，支持查询参数如坐标 hint）。  
   **拓扑图**：节点 = 区域/物体，边 = 相邻、包含、面向——模型先吃图，再吃精确几何。

2. **动作原语（Verbs）**  
   v0.1 **少而硬**：如 `OBSERVE` / `NAVIGATE` / `MANIPULATE` / `REARRANGE` + 扩展位。复杂组合由上层编排，**协议层不爆炸**。

3. **虚实同步与冲突**  
   明确：**传感器/物理状态覆盖纯虚拟推断**；定义「最后写入者」「权威源」字段，避免孪生分叉无规则。

4. **空间反馈 → 可学习**  
   标准 **错误码**（如碰撞、不可达、权限拒绝）+ **可选** `feedback` 记录块，便于 RLHF / 记忆系统接入——**协议不替代训练，只保证数据形状一致**。

---

## 三、仓库里「都要有什么」（内容矩阵）

### A. 规范（The Bible）

| 交付物 | 说明 |
|--------|------|
| `SOAP-v0.1.md` … `v1.0` | 人话 + 规范性要求；每层一章；附录给 JSON Schema |
| `CHANGELOG.md` | SemVer |
| 中英双轨 | 核心术语表对齐；对外传播以英文标题为主（*SOAP: The HTTP for Spatial AI*） |

### B. 机器契约

| 交付物 | 说明 |
|--------|------|
| JSON Schema | `scene` / `object` / `region` / `action` / `agent-session` |
| 校验 CLI | `validate` 进 CI |

### C. 参考实现（本 monorepo）

| 模块 | 说明 |
|------|------|
| `soap-runtime` | 加载场景、只读查询、锁与广播的最小实现 |
| **`soap-mcp`** | **第一触点**：MCP 工具 = 协议的广告牌 |
| `soap-scan` / `soap-sem` / `soap-render` / `soap-edit` | 生产链路，按 WORK_PLAN 阶段解锁 |

### D. 开发者体验（超越「只有文档」）

| 交付物 | 优先级 | 说明 |
|--------|--------|------|
| **5 行/5 分钟教程** | P0 | 静态 JSON 场景 + MCP，**不依赖**重训练 |
| **SOAP Visualizer** | P1 | 本地 Web：拓扑图 + Agent 轨迹 + tool call 时间线；**短视频母版** |
| Playground（在线） | P2 | 有资源再上；先做本地 |
| 与 OpenClaw / LangChain 的示例 | P1 | **合作叙事**：「空间层接 SOAP」，不树敌 |

### E. 生态与传播

| 动作 | 说明 |
|------|------|
| MCP 目录占位 | 空间类稀缺，尽快 **可用 + 可录屏** |
| `#SOAPChallenge` / 样例仓库 | 极简关卡：fork → 改 JSON → 发视频 |
| 学术 | arxiv + Workshop 提案；**晚于**可运行 MVP |
| 基金会/W3C | **远期**；先有采用者与多实现再谈 |

---

## 四、分阶段路线图（可执行、与 WORK_PLAN 对齐）

### Phase A — 协议锚定 + MCP 占位（当前 ~8 周）

**目标**：任何人 **不装重 GPU 管线** 也能说「我接入了 SOAP」。  
**交付**：L2/L3 最小闭环（场景 JSON + 动作子集）+ `soap-mcp` + 2 个 example + Visualizer α。  
**验收**：外部 1 人按文档复现；Claude/Cursor 可对静态场景问答与 tool 调用。  
**对应** [`WORK_PLAN.md`](./WORK_PLAN.md) 阶段 0–3。

### Phase B — 生产链路（扫描与语义）

**目标**：**真房间 → 合规 SOAP 场景文件**。  
**交付**：`soap-scan` 对齐 L1；`soap-sem` 填 L2 物体列表；与 mcp 共用同一 Schema。  
**验收**：从照片到「可被 mcp 查询的家具列表」一条 CLI。  
**对应** WORK_PLAN 阶段 4–5。

### Phase C — 体验闭环与协同

**目标**：看得懂、改得动、多人不打架。  
**交付**：`soap-render`；`soap-edit` 最小；L4 锁 + 广播进 runtime。  
**验收**：浏览器内可视化 + 双 Agent 争用同一物体时行为可预测。  
**对应** WORK_PLAN 阶段 6 + 本文件 L4 扩写。

### Phase D — 画像与合规（L5）

**目标**：行业敢用。  
**交付**：`profiles/` 住宅/零售/展厅草案；隐私与数据贡献 **Opt-in** 说明；模板场景包。  
**验收**：每个 Profile 有一个端到端 demo + 数据流说明。

### Phase E — 标准与联盟（optional，12 个月外视进展）

多实现、联盟体、会议 Workshop、域名独立站——**采用者数量到位再做**，避免空壳「标准」。

---

## 五、KPI（建议口径）

| 指标 | Phase A 结束 | Phase B | Phase C |
|------|--------------|---------|---------|
| 外部独立仓库引用 / fork 教程跟做 | ≥3 | ≥15 | ≥50 |
| `soap-mcp` 在真实项目中的使用证据（issue/文章） | ≥5 | ≥20 | — |
| JSON Schema 兼容的场景文件（外部生成） | ≥1 | ≥5 | — |
| GitHub Star | 跟踪即可 | 不唯 star | — |

**对比 OpenClaw**：不强调「碾压 Star」，强调 **空间赛道默认接口** 是否被提及。

---

## 六、风险与对策（压缩版）

| 风险 | 对策 |
|------|------|
| 大厂封闭标准 | 开放实现快、MCP 占位、与中小引擎/工具链结盟 |
| 格式战争（USD/glTF/3DGS） | **L1 抽象**：多 Profile，核心 schema 不绑死一种格式 |
| 协议过厚无人用 | **v0.1 极薄**：Spatial URI + 4 动词 + 1 个 scene JSON；其余标 *experimental* |
| 闭源 / 开源信任 | **协议与参考实现保持 Apache-2.0**；商业化走托管与支持，不绑架 spec |

---

## 七、与参考草稿的差异（可儿做的取舍）

1. **统一品牌 SOAP**：参考文中 SCP/SDTP/SATP/SMCP 全部 **收编为 L1–L5 章节名**，对外发布时不强调四个缩写，降低记忆成本。  
2. **仓库与社区**：以 **`wyonliu/Omnity`** + **GitHub Discussions** 为准，不写死 `omnity-ai`、Discord。  
3. **闭源 soap-pro / Cloudflare for Spatial**：不作为当前承诺；避免与全仓 Apache 及「国民信任」冲突，**日后可选**。  
4. **数据护城河**：不写「独家龙湖数据」为开源项目必要条件；**可选行业试点**用脱敏与授权表述。  
5. **OpenClaw**：**协同大于对立**；官方插件若有机会再推，先做好 `soap-mcp` 通用性。

---

## 八、立即执行（与 WORK_PLAN 本周 backlog 合并执行）

1. 发布 **`packages/soap/spec/SOAP-v0.1.md` 首版**（含 L1–L3 最小集 + Spatial URI + 动词表 + 冲突规则占位）。  
2. **四个 JSON Schema** + `examples/*.json` + `validate`。  
3. **`soap-mcp` 四工具** 读静态场景。  
4. 录 **15–30 秒**「Claude + MCP + 空间 JSON」屏录，作为一切传播的母素材。  
5. 在 Discussions 开 **RFC-0001**，固定「分层命名与版本策略」。

详细任务勾选见 **[`WORK_PLAN.md`](./WORK_PLAN.md)**。

---

*可执行版本 v1.0 · 随 spec 迭代同步更新*
