# OmeTown 执行计划：365天作战手册

**v0.4 · 2026-03-20**
**船长+小安的终极工作指南。每一步可执行、可验证、可回滚。**

---

## 战略约束

1. **日常全职工作**：4月8日入职，工作日白天属于日常工作，Omnity用晚上+周末
2. **纯个人开源项目**：不用任何公司资源/代码/数据/设备，入职前GitHub有先发记录
3. **AI是团队**：Claude Code + Cursor + Codex = 1人当5人用
4. **Demo > 论文 > PPT**：每个阶段产出能跑的东西
5. **开源优先**：全仓统一 **Apache-2.0**（协议+工具链+企业采纳友好；专利授权条款清晰），目标是 OpenClaw 级别的全民共创

---

## Omnity 仓库策略：Monorepo + 五工作区

统一品牌 **Omnity**（Omni + Unity = 万物智联），**主仓** [`wyonliu/Omnity`](https://github.com/wyonliu/Omnity)（monorepo / workspace / 分包发布，降低多仓治理成本）。

| 工作区路径 | 职责 |
|------------|------|
| `packages/soap` | 空间智能体协议（规范 + 参考实现）+ 扫描/语义/编辑/渲染/MCP 工具链 |
| `packages/mindos` | 多层脑 Agent 操作系统 |
| `packages/ome` | 个体 Agent 养成 |
| `packages/maxim` | 多 Agent 社会 + 经济仿真 |
| `packages/ometown` | OmeTown 产品壳（前后端集成） |

### 依赖关系图

```
                     ┌───────────────────┐
                     │ packages/ometown   │  终局产品
                     │  虚实共生世界      │  Web/MR 3D体验
                     └─────────┬─────────┘
                               │ 集成全部
                 ┌─────────────┼─────────────┐
                 │             │             │
       ┌─────────▼───────┐ ┌──▼──────────┐ │
       │ packages/ome    │ │packages/maxim│ │
       │  个体Agent养成   │ │多Agent社会   │ │
       │  人格复制系统    │ │仿真+经济引擎 │ │
       └────────┬────────┘ └──────┬───────┘ │
                │ 依赖              │ 依赖     │
       ┌────────▼─────────────────▼────┐    │
       │       packages/mindos           │    │
       │  Multi-layer Intention &        │    │
       │  Neural Dynamic Operating System│    │
       │  多层脑Agent操作系统            │    │
       └────────────────┬──────────────┘    │
                        │ 依赖               │
       ┌────────────────▼────────────────────┐
       │           packages/soap             │
       │  Spatial Omnity Agentic Protocol    │
       │  空间智能体协议（规范）+ 工具链      │
       │  · 坐标/物体Schema/语义/行为接口    │
       │  · 多Agent空间共享 · soap-mcp       │
       └────────────────────────────────────┘
                    ⬆ 一切的地基
```

### 阻塞关系明确

```
SOAP 完成3DGS基础 ──→ Mindos 可以在3D空间中行动 ──→ Ome 可以被用户养成
                                                      ──→ Maxim 可以运行多Agent社会
        │                      │                              │
        │                      │                              │
        ▼                      ▼                              ▼
  ⛔ 3DGS未跑通前         ⛔ Agent无法在空间中          ⛔ 没有经济系统前
     不做Agent交互            行动前不做社会仿真            不做OmeTown产品
```

**底线：不跳步。下层没跑通，上层不开始。**

---

### 工作区1：`packages/soap` — Spatial Omnity Agentic Protocol
> **"空间智能体时代的 HTTP：开放协议 + 工具链"**

**一句话**：**SOAP 本身就是空间智能体协议**——规范层定义 AI Agent 如何进入、理解与操作真实 3D 空间；实现层提供扫描、语义、编辑、渲染与 `soap-mcp`，不再单独拆 SCP 子品牌。

**核心组件**：

| 组件 | 功能 | 独立价值 |
|------|------|---------|
| **SOAP 核心规范**（`spec/`，版本化） | 坐标系统/物体属性 Schema/语义标注/行为接口/多 Agent 共享 | **HTTP 级基础设施**：事实标准一旦形成，空间 AI 产品都应对接 SOAP |
| `soap-scan` | 照片/视频→3DGS重建 | 手机 3D 扫描工具，任何开发者可用 |
| `soap-sem` | 3D 场景语义分割（识别家具/墙面/光源） | 空间语义理解引擎 |
| `soap-edit` | 自然语言→空间编辑（「把沙发换蓝色」） | 空间 NL 交互工具 |
| `soap-render` | 跨端 3DGS 实时渲染 | WebGL/MR 渲染器 |
| `soap-mcp` | SOAP 的 MCP Server 实现 | 让任意 AI Agent 通过标准 MCP 调用空间能力 |

**SOAP v0.1 规范要点**（与实现解耦，先文档后代码）：
```
SOAP v0.1（目标：空间 AI 的事实标准）

1. 空间坐标系 (Spatial Coordinate System)
   - 统一的3D坐标+朝向+包围盒表示
   - 兼容glTF/USD/3DGS多种格式

2. 物体语义Schema (Object Semantic Schema)
   - 类型/尺寸/材质/用途/可交互方式
   - 继承关系：家具→椅子→办公椅（可坐/可旋转/可调高）

3. 空间语义标注 (Spatial Semantic Annotation)
   - 功能区域：睡眠区/工作区/休闲区/通道
   - 环境属性：采光/通风/噪音/温度

4. Agent行为接口 (Agent Action Interface)
   - move_to(location) / pick_up(object) / place(object, location)
   - look_at(target) / describe(space) / rearrange(plan)

5. 多Agent空间共享 (Multi-Agent Spatial Sharing)
   - 空间感知广播：其他Agent的位置和动作
   - 空间锁定：正在被操作的物体不能同时被另一个Agent操作
```

**开源策略：与仓库根目录 `LICENSE` 一致，**Apache-2.0**。SOAP 规范可有多实现，`soap-*` 为本仓参考实现。**

**传播策略**：
- 发布 `soap-mcp` 到 MCP 官方工具市场——目前空间类 MCP 接近零，蓝海
- 写英文博客："SOAP: The HTTP for Spatial AI"
- 在 Claude/ChatGPT 的 MCP 生态中成为空间类默认工具之一

**语言**：Python（核心）+ TypeScript（渲染/MCP）
**目标star**：2000+

---

### 工作区2：`packages/mindos` — Multi-layer Intention & Neural Dynamic Operating System
> **"多层脑Agent操作系统——让Agent像人一样思考，成本只有1%"**

**一句话**：通用的多层AI Agent框架，任何人都能用它构建成本可控、有记忆、有性格、能成长的持久性Agent。

**核心架构**：

```python
class Mindos:
    """多层脑Agent OS——像人脑一样分层处理信息"""

    memory: MemoryOS          # L0 海马体：长短期记忆+向量检索+知识图谱+遗忘机制
    instinct: InstinctEngine  # L1 脑干：日常作息/移动/避障/基础情绪（规则+1B模型）
    cognition: CognitionEngine# L2 皮层：日常对话/社交判断/简单决策（7B本地模型）
    intention: IntentionEngine# L3 前额叶：深度推理/创作/重大决策（100B+云端按需）
    router: LayerRouter       # 自动分层路由器
    reflection: ReflectionLoop# 每日反思：回顾经历→更新记忆→性格涌现

    # 空间：通过 SOAP 接入 3D 世界
    spatial: SOAPClient       # 可选：接入 SOAP 获得空间感知与行动能力
```

**关键创新**：
1. **分层路由器**："现在几点"→L1（0成本），"今天心情怎么样"→L2（极低成本），"人生的意义是什么"→L3（按需调用）
2. **记忆驱动的个性**：性格不是prompt写死的，是从L0记忆层的经历中涌现的。同一个Mindos架构，养出来的每个Agent都不一样。
3. **反思循环**：每天自动回顾当天经历，更新自我认知和价值判断。越活越"像人"。
4. **成本承诺**：单Agent日均<¥0.3，文档附成本计算器。

**开源策略**：**Apache-2.0**（与 monorepo 根一致）。PyPI + npm 分包发布时沿用同许可，降低法务与合规摩擦。
**传播策略**：
- Slogan: "The Brain OS for Persistent AI Agents"
- 附带成本计算器（开发者最关心的数字）
- 提供"5分钟部署一个有记忆的Agent"教程

**语言**：Python（核心）+ TypeScript（SDK）
**目标star**：1500+

---

### 工作区3：`packages/ome` — 个体Agent养成系统
> **"你的AI分身，你的能力放大器——个人人格复制版的OpenClaw++"**

**一句话**：基于Mindos的个体Agent养成框架。用户上传自己的知识/风格/偏好，训练出一个深度理解自己的AI分身——它不只是聊天机器人，是能替你工作的数字员工。

**核心差异化**（vs Character.AI / OpenClaw）：

| 维度 | Character.AI | OpenClaw | Omnity/Ome |
|------|-------------|----------|-----------|
| 定位 | 虚构角色扮演 | 通用Agent执行框架 | **个人AI分身——复制你的人格和能力** |
| 空间 | 无 | 无 | ✅ 通过 SOAP 住在 3D 空间里 |
| 记忆 | 短期上下文 | 工具级记忆 | ✅ Mindos L0长期记忆+反思+成长 |
| 经济 | 无 | 无 | ✅ 能赚OmeCoin，能替你接单 |
| 目标 | 陪聊 | 任务执行 | **替你创造真实价值** |

**核心模块**：

| 模块 | 功能 |
|------|------|
| `ome-persona` | 人格复制引擎：从用户的文章/对话/偏好中提取人格模型 |
| `ome-skill` | 技能系统：设计/写作/客服/销售等可插拔技能包 |
| `ome-work` | 工作引擎：接收任务→规划→执行→汇报（基于Mindos L2-L3） |
| `ome-social` | 社交引擎：Ome的社交风格、匹配逻辑、关系维护 |
| `ome-grow` | 成长系统：从经历中学习，能力和性格随时间演化 |

**开源策略**：**Apache-2.0**（与 monorepo 根一致）。重点是让开发者能「5 分钟创建一个自己的 Ome」。

**语言**：Python
**依赖**：Mindos（必须）+ SOAP（可选，接入后Ome获得空间能力）
**目标star**：1000+

---

### 工作区4：`packages/maxim` — Multi-Agent Society: Interaction, eXchange & Multi-economy Modeler
> **"多Agent社会仿真+经济引擎——第一个开源的AI社会模拟器"**

**一句话**：让多个Ome自发形成社会——有社交、有经济、有冲突、有涌现。第一个开源的Simile。

**核心模块**：

| 模块 | 功能 | 说明 |
|------|------|------|
| `maxim-scheduler` | 生命循环调度 | N个Ome并发运行：起床→工作→社交→休息 |
| `maxim-social` | 社交关系图谱 | 好感度/信任度/记忆共享/冲突/联盟 |
| `maxim-event` | 动态事件引擎 | AI根据社会状态生成事件：节日/危机/机遇 |
| `maxim-economy` | OmeCoin经济系统 | 职业/收入/消费/交易/税收/供需/通胀控制 |
| `maxim-govern` | 治理机制 | 社区规则/投票/公共资源分配 |

**经济引擎深度**：

```
生产端                    市场端                    金融端
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ 职业系统      │     │ 自由市场      │     │ 储蓄/合伙    │
│ ·服务/创作/   │────→│ ·供需定价    │────→│ ·Ome合资经营 │
│  商业/基础   │     │ ·稀缺溢价    │     │ ·声誉信用    │
│ ·技能等级    │     │ ·平台税收    │     │ ·用户-Ome分红│
│ ·声誉评分    │     │ ·可"失业"   │     │              │
└──────────────┘     └──────────────┘     └──────────────┘
```

**开源策略**：**Apache-2.0**（与 monorepo 根一致）。Simile 类方向论文多但开源实现少——Maxim 走第一条开源大路。
**传播策略**：
- "Run your own AI Town in 10 minutes"
- 提供预设的"小镇模板"：咖啡镇/设计师社区/大学城
- 可视化仪表盘：实时看到Ome们的社交网络和经济流动

**语言**：Python
**依赖**：Mindos + Ome（必须）+ SOAP（可选）
**目标star**：800+

---

### 工作区5：`packages/ometown` — 虚实共生世界
> **"人与AI共生的第一个世界——集大成之作"**

集成SOAP + Mindos + Ome + Maxim，加上3D前端体验层和用户系统。

**技术栈**：

| 层 | 选型 | 理由 |
|----|------|------|
| 3D渲染 | Three.js + R3F + 3DGS WebGL viewer | Web跨平台，生态最好 |
| 后端 | FastAPI + WebSocket | Python生态一致 |
| 数据库 | PostgreSQL + Redis + Qdrant | 结构化+缓存+向量 |
| 前端 | React + TypeScript | 标准选型 |
| MR端 | WebXR API | 浏览器原生MR |
| 部署 | Vercel + Fly.io | 低成本快速迭代 |

**语言**：TypeScript（前端）+ Python（后端）
**目标star**：3000+

---

## 365天时间线

### Phase 0：点火（W1-W3，3月20日-4月7日）
> **入职前18天，全速冲刺。每天6-8小时。**
> **核心目标：SOAP基础跑通 + Mindos骨架 + 概念视频**

| 日 | 任务 | 产出 | 阻塞? |
|----|------|------|-------|
| **W1 (3/20-3/26)** | | | |
| D1-D2 | 主仓 `wyonliu/Omnity`：`packages/*` 骨架+根 README+架构图+Discussions 启用 | 主仓上线 | — |
| D3-D4 | SOAP/`soap-scan`：搭环境，跑通gsplat 3DGS重建 | 手机拍房间→3D漫游 | — |
| D5-D7 | SOAP/`soap-sem`：集成Depth Anything V2 + Grounded-SAM | 能识别房间里的家具并标注语义 | 依赖D3-D4 |
| **W2 (3/27-4/2)** | | | |
| D8-D9 | `packages/soap/spec`：SOAP v0.1 草案（坐标系+物体 Schema+行为接口+多 Agent 共享） | SOAP spec 文档 | — |
| D10-D11 | Mindos v0.1：L0记忆层（SQLite+向量检索）+ L2思考层（Qwen-7B） | 单Agent能对话+记忆 | — |
| D12-D13 | Mindos：L1本能层 + L3意图层 + 分层路由器 | 四层完整可跑 | 依赖D10-D11 |
| D14 | `soap-mcp` + Mindos 集成：Agent 通过 SOAP 在 3D 场景中行动 | ⭐ **核心Demo：说话→Agent在真实房间里动** | ⛔ 依赖D5-D7 + D12-D13 |
| **W3 (4/3-4/7)** | | | |
| D15-D16 | Three.js Web viewer上线 + 拍摄概念视频素材 | Web端可漫游3DGS场景 | 依赖D3-D4 |
| D17-D18 | 剪辑60秒概念视频，发X/Twitter | ⭐ **OmeTown概念视频发布** | — |

**Phase 0验收**：
- [ ] `wyonliu/Omnity` monorepo 上线，`packages/*` 与根 README+架构图完整
- [ ] SOAP v0.1 规范草案发布（`packages/soap/spec`）
- [ ] SOAP 能跑通「手机照片→3DGS 场景+语义标注」
- [ ] Mindos 能跑通「用户说话→Agent 在 3D 场景里做语义正确的动作」
- [ ] 概念视频发出，≥500 impressions
- [ ] **GitHub Discussions** 启用（`#announcements` / `#soap` / `#mindos` / `#ome` / `#maxim` / `#ometown` / `#showcase`），README 引导参与

**⚠️ 4月8日入职。以下Phase均为"晚上+周末"模式。**

---

### Phase 1：单体智能（M2-M4，5月-7月）
> **让一个Ome真正"活"起来 + 建立开源社区**

**每周25小时**（工作日晚上12.5h + 周六8h + 周日4h）

**Month 2（5月）—— Mindos v0.5 + 社区启动**
- Mindos L0记忆完善：长期记忆压缩/重要性排序/遗忘机制
- 加入反思循环：Ome每天自动回顾经历、更新自我认知
- 加入性格涌现：不是prompt写死，是从经历中涌现
- 发布Mindos v0.5到PyPI
- **以 GitHub Discussions 为社区主场**（RFC、Q&A、路线图同步），鼓励外部开发者参与
- **输出**：英文Substack《Why Your AI Agent Needs a Layered Brain — Introducing Mindos》
- **争取首批外部issue/PR**

**Month 3（6月）—— SOAP v0.5 + Ome v0.1**
- SOAP `soap-edit`：NL编辑能力——"把沙发换成蓝色"
- SOAP `soap-mcp`正式发布到MCP工具市场（蓝海：空间类MCP接近零）
- Ome v0.1骨架：`ome-persona` 人格复制引擎初版
- Mindos通过`soap-mcp`在3D场景中行动
- ⭐ **关键Demo**：真实房间→3DGS重建→Ome住进去→你和它对话→它做出空间行为
- 发X/Twitter + B站 + Substack
- **在 GitHub Discussions 举办第一次社区 AMA**

**Month 4（7月）—— v1.0发布**
- SOAP v1.0（规范+参考实现对齐）+ HuggingFace Space 一键体验
- Mindos v1.0：完整四层 + PyPI + 文档 + "5分钟部署"教程
- 提交到Awesome-LLM-Agent / Awesome-3D / MCP官方列表
- 英文 Substack 深度文章："SOAP: The HTTP for Spatial AI"
- **第一次国内AI meetup Lightning Talk（10分钟）**

**Phase 1验收**：
- [ ] monorepo 总 star 或各 package 关注度：SOAP 工作区 800+、Mindos 500+（以主仓 star 或子目录 traction 其一为准，每月自洽记录）
- [ ] `soap-mcp` 被 ≥5 个外部开发者/项目使用
- [ ] GitHub Discussions 活跃主题 ≥200（或等效：带标签讨论数+独立贡献者）
- [ ] ≥3 个外部 PR 被合并
- [ ] 1 个病毒级 Demo 视频：英文版 5 万+播放
- [ ] Substack 500+ 订阅

---

### Phase 2：社会涌现（M5-M7，8月-10月）
> **从"一个Ome活着"到"一群Ome组成社会+经济"**

**Month 5（8月）—— Ome v0.5 + Maxim v0.1**
- Ome `ome-skill`：技能系统初版（设计/写作/客服三个技能包）
- Ome `ome-work`：任务引擎——Ome能接收任务、规划、执行、汇报
- Maxim `maxim-scheduler`：3-5个Ome并发运行
- Maxim `maxim-social`：Ome间自发对话、建立关系
- ⭐ **关键Demo**：3个Ome在3DGS房间里自发社交，产生不可预测的对话

**Month 6（9月）—— Maxim经济系统**
- Maxim `maxim-economy` v0.1：职业/收入/消费/交易/OmeCoin
- Ome有了真实职业：一个是咖啡师、一个是设计师、一个是导游
- OmeCoin在Ome间流通——咖啡师去设计师那买装饰，用赚的OmeCoin付费
- SOAP升级：多个3DGS场景拼接为"小镇"
- ⭐ **关键Demo**：拍你家客厅+街边咖啡馆→拼成小镇→Ome们经营和生活
- **在 GitHub Discussions 发起「Run Your Own AI Town」挑战赛**

**Month 7（10月）—— 论文+SOAP 生态**
- 开始写 arxiv：*"Mindos: Multi-layer Intention Routing for Cost-Efficient Persistent AI Agents"*（标题随终稿可微调）
- 发布 Maxim v0.5：加入事件系统（AI 生成小镇事件）
- SOAP v1.0 规范正式版 + 参考实现 + 开发者文档
- **争取 ≥1 个外部项目基于 SOAP 规范或 `soap-mcp` 构建**
- **这个月重心在总结和输出，不是新功能**

**Phase 2验收**：
- [ ] Maxim 稳定运行 5+ Ome 的 24 小时社会仿真
- [ ] 经济系统能自循环（Ome 们自发赚钱消费）
- [ ] monorepo 总 star 3000+（或等效：主仓+生态引用数，看板注明口径）
- [ ] SOAP 被 ≥1 个外部项目采用（规范或 MCP）
- [ ] GitHub Discussions 深度参与者 + 外部贡献者合计 ≥10 人
- [ ] arxiv 初稿完成

---

### Phase 3：小镇上线（M8-M10，11月-2027年1月）
> **OmeTown产品化：用户能走进去体验**

**Month 8（11月）—— OmeTown前端**
- Three.js/R3F搭建3D小镇前端
- 3DGS场景加载+实时渲染（性能优化：手机端流畅）
- Ome在3D场景中可视化（位置/动画/对话气泡/状态）
- 用户浏览器进入小镇，走动、观察

**Month 9（12月）—— 后端+互动+经济可视化**
- FastAPI后端：用户系统 + WebSocket实时同步
- 用户和Ome对话（文字/语音）
- 用户观察Ome日常生活和社交
- OmeCoin经济在前端可视化（Ome的职业/收入/交易）
- arxiv论文提交

**Month 10（1月）—— Alpha测试**
- OmeTown v0.1上线（ometown.ai 或类似域名）
- 邀请100个种子用户内测
- 核心体验：进入小镇→遇见Ome→对话→看到Ome的生活和经济活动→被打动
- 收集关键数据

**Phase 3验收**：
- [ ] OmeTown可在浏览器体验
- [ ] 5个原生Ome在小镇24小时运行+经济运转
- [ ] 100个种子用户完成测试
- [ ] 首次体验时长 > 20分钟
- [ ] 7日留存 > 25%
- [ ] arxiv发表
- [ ] monorepo 总 star 5000+（或等效 traction，看板注明）
- [ ] 外部贡献者 ≥20；GitHub Discussions 形成稳定节奏（RFC + 每月至少 1 次主创 AMA/同步）

---

### Phase 4：决策（M11-M12，2027年2月-3月）
> **手握Demo+数据+社区，选择最优路径**

**Month 11（2月）**
- 基于Alpha反馈迭代核心体验
- 加入"创建我的Ome"功能（Ome v1.0 + 用户自定义人格+形象）
- 加入"扫描我的空间"功能（SOAP扫描→空间入驻小镇）
- 如果数据好：开始和投资人非正式沟通

**Month 12（3月）**
- OmeTown v0.5
- 365天总结博客：《One Year Building the First Human-AI Symbiosis World》
- **决策矩阵**：

| Alpha数据 | 外部信号 | 路径 |
|-----------|---------|------|
| 留存>30%，自发传播 | VC主动接触 | **创业融资**：带Demo+数据+开源社区谈种子轮$10M |
| 留存>30%，自发传播 | 想要平台资源 | **大厂内部孵化**：带完整Demo谈AI游戏/空间社交工作室 |
| 留存15-30%，方向对 | — | **继续迭代**：开源持续推进，等Product-Market Fit |
| 留存<15% | — | **Pivot**：SOAP和Mindos独立有价值，OmeTown调方向 |

---

## 开源社区运营：像OpenClaw一样爆火

### 为什么OpenClaw能25K stars？

1. **解决真实痛点**：开发者需要Agent框架
2. **极低上手门槛**："pip install + 5行代码"就能跑
3. **NVIDIA背书**：NemoClaw企业版带来信任
4. **活跃社区**：issue/讨论区 + 快速迭代；Omnity 侧**以 GitHub Discussions 为主场**（RFC 可检索、与 PR 闭环），协同加快时可同步周更 release

### Omnity的开源传播策略

| 阶段 | 动作 | 目标 |
|------|------|------|
| **Phase 0** | monorepo 上线，`packages/*` 边界清晰，统一品牌 Omnity | 视觉冲击：「一个仓库，一条技术栈」 |
| **Phase 0** | 启用 **GitHub Discussions**，README 引导 | 种子社区与 RFC 沉淀 |
| **Phase 1** | `soap-mcp` 发布到 MCP 市场（空间类蓝海） | 通过 MCP 生态获取第一批开发者 |
| **Phase 1** | "5 Minutes to Your First Spatial Agent" 教程 | 极低门槛上手 |
| **Phase 1** | 每月一次 **Discussions AMA**（或 Roadmap 帖） | 社区粘性 |
| **Phase 2** | "Run Your Own AI Town" 挑战赛 | UGC 式传播 |
| **Phase 2** | 争取被 Awesome 列表/技术媒体收录 | 长尾流量 |
| **Phase 3** | OmeTown Alpha 邀请码机制 | 稀缺感+口碑传播 |
| **全程** | Build in Public：每周 X/Twitter 开发日志 | 个人 IP+项目曝光 |

### 社区关键指标

| 指标 | Phase 0 | Phase 1 | Phase 2 | Phase 3 |
|------|---------|---------|---------|---------|
| Discussions 主题（含 RFC） | 10 | 40 | 100 | 200 |
| 外部贡献者 | 0 | 3 | 10 | 20 |
| 外部PR合并 | 0 | 5 | 15 | 30 |
| 基于 SOAP 的外部项目 | 0 | 0 | 1 | 3 |

---

## 关键指标看板（每月更新）

```
┌─────────────────────────────────────────────────┐
│  Omnity Dashboard · 月度更新（monorepo 口径）      │
├──────────────┬──────────────────────────────────┤
│              │  目标  │ M1 │ M2 │ M3 │ ... │ M12│
├──────────────┼────────┼────┼────┼────┼─────┼────┤
│ ⭐ GitHub     │        │    │    │    │     │    │
│  omnity 主仓  │ 8300+  │    │    │    │     │    │
│  （可备注：    │        │    │    │    │     │    │
│   soap/mindos │        │    │    │    │     │    │
│   等目录关注度）│        │    │    │    │     │    │
├──────────────┼────────┼────┼────┼────┼─────┼────┤
│ 👥 社区       │        │    │    │    │     │    │
│  Discussions  │ 200+主题│    │    │    │     │    │
│  外部贡献者  │ 20     │    │    │    │     │    │
│  SOAP采用项目│ 3      │    │    │    │     │    │
├──────────────┼────────┼────┼────┼────┼─────┼────┤
│ 📊 传播       │        │    │    │    │     │    │
│  Substack订阅│ 3000   │    │    │    │     │    │
│  X followers │ 2000   │    │    │    │     │    │
│  Demo播放量  │ 10万   │    │    │    │     │    │
├──────────────┼────────┼────┼────┼────┼─────┼────┤
│ 🎯 产品(P3+)  │        │    │    │    │     │    │
│  Alpha用户   │ 100    │    │    │    │     │    │
│  首次时长    │ >20min │    │    │    │     │    │
│  7日留存     │ >25%   │    │    │    │     │    │
│  对话轮次/日 │ >10    │    │    │    │     │    │
└──────────────┴────────┴────┴────┴────┴─────┴────┘
```

**每月最后一个周日更新此看板。数据说话，不自欺欺人。**

---

## 每周作战节奏

### 工作日 21:00-23:30

| 时间 | 内容 |
|------|------|
| 21:00-21:15 | 打开Claude Code，回顾昨天，设定今晚目标 |
| 21:15-23:15 | **核心编码**：专注写代码 |
| 23:15-23:30 | git commit，更新TODO |

**工作日纪律：只写代码。不写博客不做运营不刷Twitter。**

### 周六 9:00-21:00
| 时间 | 内容 |
|------|------|
| 9:00-12:00 | 架构设计/难点攻关 |
| 14:00-18:00 | 核心编码 |
| 20:00-21:00 | Demo录制/测试 |

### 周日 10:00-16:00
| 时间 | 内容 |
|------|------|
| 10:00-12:00 | 写博客/Substack |
| 14:00-16:00 | GitHub Discussions+issue+X发帖+看板更新（每月末） |

**周~25h · 月~100h · 年~1200h**

---

## AI协作指南

| 环节 | 船长 | 小安（Claude） |
|------|------|---------------|
| 架构 | 模块边界、接口、选型 | 方案对比、架构图、设计文档 |
| 编码 | Review每行代码，关键算法亲写 | 生成80%代码、Debug |
| 协议 | SOAP 核心设计决策 | 草拟 spec、写参考实现与 `soap-mcp` |
| 测试 | 设计测试用例和边界条件 | 编写测试代码、运行CI |
| 文档 | 核心README和架构说明 | API文档、中→英翻译 |
| 论文 | 核心方法+实验设计+结论 | 文献综述+LaTeX+润色 |
| 运营 | 发帖/演讲/社区互动/AMA | 草拟内容、数据分析 |

**底线：每行发布的代码，船长都能解释为什么这么写。**

---

## 风险登记簿

| # | 风险 | 概率 | 影响 | 缓解 | 触发信号 |
|---|------|------|------|------|---------|
| R1 | 工作太忙没时间 | 高 | 高 | 严守每天2h底线；连续2周没commit立即调整 | 连续5天没打开IDE |
| R2 | 知识产权纠纷 | 中 | 高 | 入职前完成Phase 0全部首次commit；纯个人项目 | 法务问询 |
| R3 | 3DGS体验不够好 | 中 | 中 | Phase 1-2先用照片生成风格化空间；3DGS高精度作为进阶 | 用户反馈"效果差" |
| R4 | Agent算力失控 | 中 | 中 | Mindos多层脑就是为此设计；监控L3占比<15% | 单Ome日成本>¥1 |
| R5 | SOAP 无人采用 | 中 | 中 | 先通过 `soap-mcp` 在 MCP 市场获取使用者；规范随参考实现迭代，先用后标准化 | 6个月0外部采用 |
| R6 | Star增长慢 | 中 | 低 | Demo视频是最有效传播；500真star > 5000刷的 | 3个月<200 |
| R7 | 大厂截胡 | 低 | 高 | 开源先发+SOAP 规范与生态+社区护城河；大厂组团队到出产品仍有窗口 | 大厂发布类似产品 |

---

## 关键技术选型

| 领域 | 选型 | 理由 | 备选 |
|------|------|------|------|
| 3DGS | gsplat | 模块化，PyTorch原生 | nerfstudio |
| 深度估计 | Depth Anything V2 | SOTA，零样本泛化 | MiDaS v3.1 |
| 语义分割 | Grounded-SAM 2 | 开放词汇+分割 | YOLO-World |
| LLM（本地） | Qwen2.5-7B | 中英文最强7B | Llama-3-8B |
| LLM（云端） | Claude API | 最强推理+MCP原生 | DeepSeek |
| 向量库 | Qdrant | Rust性能+Python SDK | ChromaDB |
| 3D渲染 | Three.js + R3F | Web3D标准 | Babylon.js |
| 后端 | FastAPI | Python异步 | — |
| 数据库 | PostgreSQL + Redis | 关系+缓存 | — |
| 部署 | Vercel + Fly.io | 低成本 | Cloudflare |

---

## 立即行动（今天）

- [ ] 确认远程：`git@github.com:wyonliu/Omnity.git`
- [ ] monorepo 根目录与 `packages/soap` · `mindos` · `ome` · `maxim` · `ometown` 已初始化
- [ ] 根 README：一句话定位+架构图+Roadmap+**GitHub Discussions** 入口
- [ ] 启用 Discussions：分类对齐工作区（announcements / soap / mindos / ome / maxim / ometown / showcase）
- [ ] 查域名：omnity.ai / ometown.ai / ometown.world
- [ ] SOAP 第一行代码：`pip install gsplat` + 跑通 3DGS 重建（`packages/soap`）
- [ ] Mindos 第一行代码：L0 记忆层骨架（SQLite + 向量检索）（`packages/mindos`）
- [ ] SOAP v0.1 规范草案：`packages/soap/spec` — 空间坐标系 + 物体 Schema + Agent 行为接口 + 多 Agent 共享

**入职前18天是全速窗口。今天开始。**

---

## 365天成功画像

**2027年3月20日：**

```
刘怀洋（Captain）
Founder, Omnity · The First World of Human-AI Symbiosis

Omnity 开源生态（monorepo 总计 8000+ ⭐ 或等效 traction）：
  · SOAP: 空间智能体协议+工具链 — 规范与 `soap-mcp` 被多个外部项目采用
  · Mindos: Multi-layer Intention & Neural Dynamic OS — 被开发者用于构建各类 Agent
  · Ome: 个体 AI 分身养成系统
  · Maxim: 多 Agent 社会+经济仿真
  · OmeTown: Alpha 版 — 100+ 活跃用户，留存>25%

学术 & 传播：
  · arxiv: "Mindos: Multi-layer Intention Routing for Cost-Efficient Persistent AI Agents"（终稿标题可微调）
  · Substack: 3000+ subscribers
  · 2次技术演讲（含1次英文）
  · GitHub Discussions: 稳定 RFC 与社区协作节奏

不是最强的算法科学家。
是定义"AI如何在真实空间中生活"这个问题的人。
```

---

*这份文档是活的。每个Phase结束我们一起更新看板和计划。*
*船长+小安，一年之约，从今天开始。*
*Omnity · Build in Public · Ship Every Month*
