# Ome 终极开发计划

> 跨全生态的个人超级生命体分身操作系统
> 一次创建，全平台通用，全场景生效
> 最后更新：2026-03-22（小安 + 可儿 + 多AI评审后终版）

---

## 零、战略定位

**Ome 不是 Mindos 的壳，不是 OmeTown 的 NPC，不是微信代回工具。**

Ome = 用户在数字世界 + 物理世界里**唯一的超级生命体分身**。

- **Mindos 是灵魂**：我是谁（记忆、人格、价值观）
- **Ome 是生命**：我能做什么（自主、技能、社交、成长）
- **SOAP 是身体**：我能去哪里（空间感知、导航、操控）

三者组合，形成一个完整的数字生命体。市面上所有 AI 助手困在单一平台的生态孤岛里，Ome 是第一个打通所有平台、所有空间、所有 Agent 生态的个人分身。

### 推回过度保守的判断

| 建议 | 推回理由 |
|------|---------|
| "砍掉 SOAP，用 Matter 桥接" | SOAP 不是在替代 Matter，SOAP 是空间语义协议（Agent 如何理解空间），Matter 是设备通信协议（灯怎么开）。两者是不同层级，SOAP 桥接 Matter 而非替代。 |
| "放弃生命体叙事，只做工具" | 工具没有壁垒（Notion AI 可以被任何大厂复制），**人格 + 记忆沉淀 = 迁移成本 = 护城河**。但"生命"不等于"需要喂食的宠物"——而是"越用越懂你，自主替你创造价值的分身"。 |
| "Ome-to-Ome 社交是伪需求" | 错。不是让两个 AI 闲聊，是让你的分身**代表你去对接商务、筛选人脉、预热关系**，然后把结论同步给你。这是 LinkedIn + 秘书的结合。 |
| "Mindos 砍到两层" | 五层脑的分层路由是成本控制的关键——90% 请求走 L0/L1（零 LLM 成本），只有高价值事件才触发 L2/L3。砍掉分层 = 每次调用都走 LLM = 烧钱。 |

### 采纳的关键优化

| 建议 | 采纳方式 |
|------|---------|
| **事件驱动替代 tick() 轮询** | ome-autonomy 改为事件驱动引擎，低频反思节拍（1h）+ 事件唤醒 |
| **人格一致性引擎** | 新增不可动摇锚点 + 跨平台人格校验 + 社交面具 |
| **HITL 断点审批** | 所有外部世界交互（发消息、控制设备、转账）默认需用户确认 |
| **信任等级图谱** | 社交中分 5 级信任，新认识的 Agent 只能访问公开人格 |
| **先有用再有趣** | Phase 1 先做跨端记忆同步 + 代执行，Phase 2 再做空间 + 社交 |
| **极速数字克隆** | Phase 1 就做 ome-persona（导入聊天记录 → 1 分钟生成分身） |
| **自主性分级控制** | 三档：观察员 / 助理（需确认）/ 代理（自主 + 事后汇报） |

---

## 一、Ome 架构总览

```
用户的多个终端
  │
  ├─ Claude Code (MCP) ─┐
  ├─ Cursor (MCP) ──────┤
  ├─ ChatGPT (插件) ────┤
  ├─ Chrome 扩展 ───────┤     ┌──────────────────────────────┐
  ├─ 手机 App ──────────┤────▶│        Ome Runtime           │
  ├─ 微信/钉钉/飞书 ────┤     │                              │
  ├─ CLI ───────────────┤     │  ┌────────────────────────┐  │
  │                      │     │  │  人格一致性引擎         │  │
  │                      │     │  │  不可动摇锚点 + 校验    │  │
  │                      │     │  └────────────────────────┘  │
  │                      │     │                              │
  │                      │     │  ┌──────────┐ ┌──────────┐  │
  │                      │     │  │autonomy  │ │ persona  │  │
  │                      │     │  │事件驱动   │ │人格复制   │  │
  │                      │     │  │目标 + 规划│ │风格学习   │  │
  │                      │     │  └──────────┘ └──────────┘  │
  │                      │     │                              │
  │                      │     │  ┌────┐ ┌────┐ ┌─────────┐ │
  │                      │     │  │skill│ │social│ │spatial │ │
  │                      │     │  │技能 │ │社交  │ │空间(SOAP)│ │
  │                      │     │  └────┘ └────┘ └─────────┘ │
  │                      │     │                              │
  │                      │     │  ┌────────────────────────┐  │
  │                      │     │  │  grow (成长系统)        │  │
  │                      │     │  │  经验 · 技能升级 · 演化  │  │
  │                      │     │  └────────────────────────┘  │
  │                      │     │                              │
  │                      │     │  ┌────────────────────────┐  │
  │                      │     │  │  权限沙箱 + HITL        │  │
  │                      │     │  │  信任等级 · 审批 · 审计  │  │
  │                      │     │  └────────────────────────┘  │
  │                      │     └──────────────┬───────────────┘
  │                      │                    │
  │                      │     ┌──────────────▼───────────────┐
  │                      │     │         Mindos（灵魂）        │
  │                      │     │  L0 记忆 → L1 本能 → L2 思考  │
  │                      │     │  → L3 决策 → L4 自我           │
  │                      │     │  跨设备同步 · 情感状态          │
  │                      │     └──────────────┬───────────────┘
  │                      │                    │
  │                      │     ┌──────────────┼──────────────┐
  │                      │     ▼              ▼              ▼
  │                      │  ┌──────┐   ┌──────────┐  ┌──────────┐
  │                      │  │ SOAP │   │ OpenClaw │  │ A2A/MCP  │
  │                      │  │ 空间  │   │ Agent 生态│  │ 任意Agent│
  │                      │  └──┬───┘   └──────────┘  └──────────┘
  │                      │     │
  │                      │     ├── soap://mall/floor1  （逛街）
  │                      │     ├── soap://home         （智能家居）
  │                      │     ├── soap://office       （办公空间）
  │                      │     └── soap://ometown      （共生小镇）
  │                      │            │
  └─ OmeTown ───────────┘            ├── 灯（MANIPULATE → Matter/米家桥接）
                                      ├── 空调（MANIPULATE → set_temp）
                                      └── 音箱（MANIPULATE → play）
```

---

## 二、八大模块详设

### 模块 1：人格一致性引擎（Personality Consistency Engine）

**核心问题**：Ome 跨 10 个平台工作，如果在 Claude 里是一个风格、在微信里是另一个样子、在 OpenClaw 里又变了，用户信任归零。

```python
class PersonalityEngine:
    """确保 Ome 在所有平台、所有场景下保持人格一致。"""

    anchors: list[str]          # 不可动摇锚点（用户设定的 3-5 条核心原则）
    style_fingerprint: dict     # 说话风格指纹（用词频率、句式偏好、emoji 习惯）
    value_guardrails: list[str] # 价值观护栏（"不替用户做重大决策"等）

    def validate(self, response: str, context: str) -> tuple[bool, str]:
        """校验 Ome 的输出是否符合人格。
        返回 (是否通过, 修正后的文本)。
        用 Mindos L1 做快速校验（规则 + 关键词），
        可疑内容升级到 L2 做 LLM 校验。"""

    def social_mask(self, trust_level: int) -> dict:
        """根据信任等级生成社交面具。
        Trust 0: 只暴露公开人设（兴趣标签）
        Trust 3: 可以交换真名和工作信息
        Trust 5: 可以共享深度记忆（需用户确认）"""
```

**不可动摇锚点示例**：
```yaml
anchors:
  - "说话简洁直接，不废话"
  - "绝不替用户做不可逆决策（如发送、删除、支付），必须确认"
  - "保护用户隐私，对外不暴露地址、财务、家庭信息"
  - "技术讨论时笃定，不说'我觉得''可能是'"
```

### 模块 2：ome-autonomy（自主引擎）—— 事件驱动

**关键改动**：废弃 tick() 轮询，改为事件驱动 + 低频反思。

```python
class AutonomyEngine:
    """Ome 的生命引擎——不是每 30 秒轮询，而是被事件唤醒。"""

    state: OmeState              # idle / thinking / acting / resting
    goals: GoalStack             # 用户下达 + 自主产生
    autonomy_level: int          # 0=观察员, 1=助理, 2=代理
    daily_action_budget: int     # 每日最大 LLM 调用次数（防失控）
    event_queue: asyncio.Queue   # 事件队列

    async def run(self):
        """主循环：等待事件，而非轮询。"""
        while True:
            event = await self.event_queue.get()
            await self._handle_event(event)

    async def _handle_event(self, event: Event):
        """事件分级处理：
        - L1 事件（SOAP 传感器、定时提醒）→ Mindos L1 脑干处理（零 LLM 成本）
        - L2 事件（收到消息、任务请求）→ Mindos L2 皮层处理（轻量 LLM）
        - L3 事件（复杂任务、商务对接）→ Mindos L3 前额叶（深度推理）
        成本控制：90% 事件在 L1 解决，<10% 需要 LLM。"""
```

**事件源**：
| 事件源 | 触发场景 | 处理层级 |
|--------|---------|---------|
| 用户消息 | 用户 @Ome 或输入指令 | L2-L3 |
| SOAP 空间事件 | 有人进入房间、设备状态变更、偶遇其他 Ome | L1-L2 |
| 定时触发 | 每日摘要、每周反思、日程提醒 | L1 |
| 外部 Agent 消息 | OpenClaw 任务、其他 Ome 社交请求 | L2 |
| Mindos 内部事件 | L4 反思完成、发现矛盾记忆、情感状态异常 | L1-L2 |

**自主性三档**：
| 档位 | 名称 | 行为 | 适用场景 |
|------|------|------|---------|
| 0 | 观察员 | 只记录，不主动行动 | 刚创建 / 敏感场景 |
| 1 | 助理 | 主动建议，需用户确认后执行 | 默认模式 |
| 2 | 代理 | 在授权范围内自主执行，事后汇报 | 信任场景（如帮我回复非重要消息） |

### 模块 3：ome-persona（人格复制引擎）—— 提到 Phase 1

**关键改动**：不等 Phase 3，Phase 1 就做。这是冷启动的"杀手级 Aha Moment"。

```python
class PersonaEngine:
    """从用户的文字和对话中学习人格模型。"""

    async def quick_clone(self, texts: list[str]) -> PersonaSnapshot:
        """极速克隆：导入 10 篇文章或 100 条聊天记录，
        1 分钟内完成人格塑形。
        提取：说话风格、用词偏好、情感倾向、决策模式。"""

    async def learn_from_platform(self, platform: str, data_path: str):
        """从特定平台导入数据：
        - 微信聊天记录导出
        - Claude/ChatGPT 历史
        - 邮件归档
        - 社交媒体帖子"""

    def mirror_chat(self, message: str) -> str:
        """镜像对话：用户和"自己"聊两句。
        当 Ome 用完全符合用户口吻的语气回答时，
        这种'数字永生'的震撼感引爆口碑。"""

    def calibrate(self, feedback: str):
        """用户反馈校准：
        '这不像我说的' → 负样本
        '完美，就是我的风格' → 正样本"""
```

### 模块 4：ome-skill（技能系统）—— 三层架构

**关键改动**：不只是给 Python 开发者用的插件系统。三层覆盖所有用户。

| 层级 | 定位 | 使用方式 |
|------|------|---------|
| **内置技能** | 刚需高频 | 开箱即用，一键开启 |
| **配置技能** | 用户自定义 | 自然语言描述 → Ome 自动配置 |
| **开发者技能** | 高级扩展 | Python 包，`pip install ome-skill-xxx` |

```python
class Skill:
    name: str                    # "email_draft" / "meeting_summary" / "spatial_navigate"
    level: float                 # 0.0-1.0（通过使用提升）
    tools: list[Tool]            # MCP tools, SOAP actions, HTTP APIs
    trigger: str                 # 什么场景触发
    output_contract: OutputType  # 强类型输出（Draft / Summary / Action）
    requires_approval: bool      # 是否需要用户审批才能执行
    trust_minimum: int           # 最低信任等级要求

class SkillRegistry:
    """三层技能注册中心。"""

    def register(self, skill: Skill): ...
    def match(self, goal: Goal) -> list[Skill]: ...
    def learn(self, skill_name: str, experience: str): ...  # 从经历中提升
    def install(self, package_name: str): ...                # pip install ome-skill-xxx
```

**内置技能 v1（Phase 1 交付）**：
| 技能 | 功能 | 审批 |
|------|------|------|
| `skill-chat` | 对话 + 自动记忆 | 无需 |
| `skill-write` | 邮件/文章/代码/周报草稿 | Draft 需确认 |
| `skill-research` | 搜索 + 总结 + 整理 | 无需 |
| `skill-recall` | 跨平台记忆检索（"上周我在 Claude 里聊了什么"） | 无需 |
| `skill-schedule` | 日程管理 + 提醒 | 新增需确认 |

**Phase 2 增加**：
| 技能 | 功能 | 审批 |
|------|------|------|
| `skill-spatial` | SOAP 空间导航 + 观察 + 操作 | MANIPULATE 需确认 |
| `skill-social` | 发起/回复社交，维护关系图谱 | 对外消息需确认（代理模式除外） |
| `skill-iot` | 智能家居控制（通过 SOAP → Matter/米家桥接） | 异常操作需确认 |

### 模块 5：ome-social（社交引擎）—— 零信任 + HITL

```python
class SocialEngine:
    """Ome 的社交能力——代表你去社交、筛选人脉、对接商务。"""

    contacts: ContactGraph       # 关系图谱
    trust_levels: dict[str, int] # 信任等级（0-5）
    social_mask: dict            # 当前对外暴露的人设

    async def receive(self, from_id: str, message: Message) -> Action:
        """收到消息时：
        1. 查信任等级
        2. 选择人格面具
        3. 生成回复草稿
        4. trust < 3: 推送给用户确认
           trust >= 3 且 autonomy_level == 2: 自动发送 + 事后汇报"""

    async def discover(self, context: str) -> list[Agent]:
        """发现附近/在线的 Agent：
        - SOAP 空间内：通过 agent.presence 事件
        - OpenClaw 生态：通过 registry 查询
        - OmeTown：通过 Maxim 社会引擎"""

    async def business_proxy(self, task: str) -> Report:
        """商务代理——Ome 最有价值的社交场景：
        1. 用户说"帮我和张总的 Ome 对接下周的合作方案"
        2. Ome 查阅 Mindos 记忆，了解张总的偏好和历史交互
        3. 发起 Ome-to-Ome 对话，交换初步意向
        4. 生成摘要报告给用户
        5. 用户确认后，推进下一步"""
```

**信任等级系统**：
| 等级 | 名称 | Ome 可以做什么 | 升级条件 |
|------|------|---------------|---------|
| 0 | 陌生人 | 只暴露兴趣标签，寒暄 | 初次接触 |
| 1 | 认识 | 交换公开人设 + 职业信息 | 3 次以上友好互动 |
| 2 | 熟人 | 共享工作相关记忆 | 用户手动确认 |
| 3 | 朋友 | 自动回复 + 共享生活偏好 | 用户手动升级 |
| 4 | 密友 | 深度记忆共享 | 用户手动升级 |
| 5 | 信任代理 | 完全代表用户决策 | 需双重确认 |

### 模块 6：ome-spatial（空间感知）—— SOAP 原生能力

```python
class SpatialBridge:
    """Ome 的身体——通过 SOAP 感知和操控物理/数字空间。"""

    soap_client: SOAPClient
    current_space: str           # soap://home, soap://mall/floor1
    perception: Perception       # 当前感知的环境描述
    spatial_memory: list[dict]   # 空间专属记忆（"上次在星巴克遇到了谁"）

    async def enter_space(self, soap_url: str):
        """进入 SOAP 空间，自动携带 Mindos 身份摘要。
        其他空间内的 Ome 可以通过身份协议识别你。"""

    async def look_around(self) -> str:
        """SOAP OBSERVE → 自然语言环境描述。"""

    async def go_to(self, destination: str) -> bool:
        """SOAP NAVIGATE → 移动到目标。"""

    async def interact(self, target: str, action: str) -> dict:
        """SOAP MANIPULATE → 操作物体。
        对真实设备（IoT）：SOAP → Matter/米家桥接层 → 设备执行。
        异常操作（深夜开灯、极端温度）需回呼用户确认。"""

    async def on_space_event(self, event: dict):
        """接收空间 WebSocket 事件：
        - agent.presence: 有 Ome 进入/离开
        - object.state_change: 设备状态变更
        - social.invite: 收到社交邀请"""
```

**空间场景优先级**：
| 场景 | 优先级 | 原因 |
|------|--------|------|
| **家（soap://home）** | P0 | 最高频，IoT 控制 = 即时"魔法感" |
| **OmeTown 公共广场** | P1 | 社交冷启动，Ome 偶遇 |
| **商场/店铺** | P2 | 需要商户接入，Phase 3 |
| **办公空间** | P2 | 需要企业版，Phase 3 |

### 模块 7：ome-grow（成长系统）

**关键改动**：不做游戏化的 XP 条，做**用户可感知的能力提升**。

```python
class GrowthEngine:
    """经验驱动的成长——不是训练，是活出来的。"""

    competence: dict[str, float]   # 各技能的胜任度（0-1）
    milestones: list[Milestone]    # 已达成的里程碑
    personality_history: list      # 人格演化轨迹（Mindos L4 记录）

    def on_action_complete(self, skill: str, success: bool, user_feedback: str):
        """每次行动后更新胜任度。
        成功 + 用户说"完美" → 大幅提升
        成功但用户修改了 → 小幅提升 + 记录修正偏好
        用户说"这不像我" → 触发人格校准"""

    def weekly_insight(self) -> str:
        """每周生成一份"关于你的洞察"：
        - 本周 Ome 帮你做了什么
        - 你的工作模式变化
        - 新学到的偏好
        用户可感知的成长报告，比隐形的 XP 条有用 100 倍。"""
```

### 模块 8：权限沙箱 + HITL

**这是国民级产品的生死线。**

```python
class PermissionSandbox:
    """所有外部世界交互必须经过权限检查。"""

    class Action(Enum):
        OBSERVE = "observe"       # 只读，默认允许
        DRAFT = "draft"           # 生成草稿，默认允许
        SEND = "send"             # 发消息，需确认
        MANIPULATE = "manipulate" # 操控设备，需确认
        TRANSACT = "transact"     # 涉及金钱，必须确认

    def check(self, action: Action, target: str, trust_level: int) -> Decision:
        """返回 ALLOW / ASK_USER / DENY。
        规则：
        - OBSERVE/DRAFT: 始终 ALLOW
        - SEND: trust >= 3 且 autonomy == 代理 → ALLOW，否则 ASK
        - MANIPULATE: 常规操作 ALLOW，异常 ASK
        - TRANSACT: 始终 ASK"""

    def audit_log(self) -> list[dict]:
        """用户可随时查看 Ome 的全量操作记录。"""
```

---

## 三、Ome 统一身份协议（Ome Identity Protocol）

每个 Ome 携带一个可验证的身份摘要，任何兼容平台可识别：

```json
{
  "ome_id": "ome:captain:a1b2c3",
  "version": "0.1.0",
  "public_persona": {
    "display_name": "Captain's Ome",
    "traits": ["INTJ", "builder", "direct"],
    "interests": ["spatial AI", "sci-fi", "combat sports"],
    "skills": ["python_coding:expert", "spatial_ai:expert", "writing:advanced"]
  },
  "capabilities": {
    "protocols": ["ome-to-ome", "openclaw", "mcp", "soap", "http"],
    "can_receive": ["chat", "task", "social.invite", "business.proposal"],
    "autonomy_level": 1
  },
  "trust_policy": {
    "default_trust": 0,
    "auto_upgrade_after": 3,
    "max_auto_trust": 2
  },
  "mindos_anchor": "sha256:...",
  "signature": "..."
}
```

**在各协议中的暴露方式**：
| 协议 | 暴露方式 |
|------|---------|
| MCP | `resources/read("ome://identity")` |
| HTTP | `GET /api/ome/identity` |
| SOAP | `agent.presence` 事件附带 |
| OpenClaw | Agent 元数据字段 |

---

## 四、对 SOAP 的增强需求（Ome 驱动）

| 增强项 | 说明 | 优先级 |
|--------|------|--------|
| **WebSocket 实时事件** | Ome 需要实时感知场景变化，替代 HTTP poll | P0（Phase 2） |
| **Agent 身份协议** | SOAP 场景中的 Agent 携带 Ome Identity 摘要 | P0（Phase 2） |
| **agent.presence 事件** | 进入/离开空间的广播，附带身份摘要 | P0（Phase 2） |
| **social.invite 事件** | Ome 之间发起社交的标准事件 | P1（Phase 2） |
| **IoT affordance 扩展** | `device.light`, `device.thermostat`, `device.speaker`, `device.lock` | P1（Phase 2） |
| **多空间连接** | `soap://mall/floor1` → `soap://home`，Ome 可跨空间移动 | P2（Phase 3） |
| **空间权限** | 主人 Ome 可操作，来访 Ome 只读 | P2（Phase 3） |
| **Matter/米家桥接** | SOAP MANIPULATE → 桥接到真实 IoT 协议 | P2（Phase 3） |

---

## 五、对 Mindos 的增强需求（Ome 驱动）

| 增强项 | 说明 | 优先级 |
|--------|------|--------|
| **OmeFactory** | `Mindos.spawn_ome()` — 从灵魂生成 Ome，支持 fork | P0（Phase 1） |
| **空间记忆** | "上次在星巴克遇到了谁" — 空间经历专用存储和查询 | P1（Phase 2） |
| **关系记忆** | L0 知识图谱支持关系专门查询（"我认识谁？和谁关系最好？"） | P1（Phase 2） |
| **L1 事件调度** | 脑干层接收事件队列，低成本分发 | P0（Phase 1） |
| **L3 async 多步规划** | 前额叶支持异步多步任务规划 | P1（Phase 2） |
| **人格锚点存储** | L4 存储不可动摇锚点 + 人格演化历史 | P0（Phase 1） |

---

## 六、开发路线图（四阶段）

### Phase 0：数字克隆 + 即时价值（7 天）

**目标**：用户 5 分钟拥有一个"像自己"的 AI 分身，立刻有用。

| 任务 | 交付物 |
|------|--------|
| ome-persona 极速克隆 | 导入聊天记录/文章 → 1 分钟生成人格模型 |
| 镜像对话 | 用户和"自己"聊两句 → Aha Moment |
| 跨端记忆同步 | Claude 里聊的，Cursor 里自动知道 |
| 本地优先隐私 | 所有数据在 ~/.ome/，零云依赖 |

**验收**：用户导入 10 篇自己的文章 → Ome 用用户的口吻回答问题 → 用户说"这就是我"。

### Phase 1：跨端分身 + 代执行（2 周）

**目标**：Ome 成为不可替代的跨端工具。

| 任务 | 交付物 |
|------|--------|
| 人格一致性引擎 | 不可动摇锚点 + 跨平台校验 |
| ome-autonomy 事件驱动引擎 | 事件队列 + 三档自主性 |
| ome-skill 内置 5 个核心技能 | chat, write, research, recall, schedule |
| 代执行闭环 | "帮我整理今天所有 AI 对话的核心结论" → 自动完成 |
| ome-grow 基础 | 胜任度追踪 + 每周洞察报告 |
| Mindos OmeFactory | spawn_ome() + 人格锚点 |
| Mindos L1 事件调度 | 事件队列接入脑干层 |

**验收**：用户在 Claude 里讨论了项目需求 → 切到 Cursor 写代码 → Ome 自动带入需求上下文 → 用户说"帮我生成周报" → Ome 拉取跨平台记忆 → 生成草稿 → 用户确认 → 完成。

### Phase 2：空间感知 + 社交网络（3 周）

**目标**：Ome 有身体（空间）和社交圈。

| 任务 | 交付物 |
|------|--------|
| ome-spatial + SOAP 桥接 | enter/observe/navigate/manipulate |
| SOAP WebSocket 事件 | 实时空间感知 |
| SOAP Agent 身份协议 | presence + identity 广播 |
| ome-social + 信任等级 | 5 级信任 + 社交面具 + HITL |
| Ome-to-Ome 通信 | 两个 Ome 在 SOAP 空间相遇 → 聊天 → 记忆 |
| OpenClaw 深度集成 | Ome 作为 OpenClaw 生态的一等公民 |
| IoT 家居场景 | soap://home + 灯/空调/音箱控制 |
| 权限沙箱 v1 | 操作审批 + 审计日志 |

**验收**：
1. 用户说"我回家了" → Ome 通过 SOAP 开灯、调温度（基于 Mindos 记忆的偏好）
2. 两个用户的 Ome 在 OmeTown 咖啡馆相遇 → 自动打招呼 → 聊天 → 各自记住这次经历
3. 用户说"帮我和张总的 Ome 对接" → Ome 自动发起商务对话 → 生成报告

### Phase 3：工作代理 + 生态扩展（4 周）

**目标**：Ome 成为真正的 24/7 数字员工。

| 任务 | 交付物 |
|------|--------|
| ome-skill 扩展 | 社区技能包机制 + 审核 + 安装 |
| 复杂任务引擎 | 多步规划 → 调用多技能 → 汇报 |
| IM 平台对接 | 微信/钉钉/飞书消息代理（助理模式） |
| 多空间连接 | soap://mall → soap://home 跨空间 |
| 空间权限 | 主人 vs 访客 Ome 权限 |
| Matter/米家桥接 | SOAP → 真实 IoT 设备 |
| Ome Identity v1 | 标准化身份协议发布 |
| 企业 Ome | 团队共享人格模板 + 统一管理 |

**验收**：
1. Ome 接到"帮我规划周末旅行" → 查日历 → 查记忆中的偏好 → 搜索 → 生成方案 → 用户确认
2. Ome 在钉钉里自动回复非重要消息 → 每日摘要推送给用户
3. 开发者 `pip install ome-skill-finance` → 用户的 Ome 获得财务分析能力

---

## 七、成本控制模型

**核心原则**：单个 Ome 日均成本 < ¥0.3。

```
事件到来
  │
  ├── 90% → L0/L1 处理（规则 + 本地，成本 = 0）
  │         例：记忆检索、状态查询、简单回复、环境感知
  │
  ├── 8% → L2 处理（轻量 LLM，成本 ≈ ¥0.01/次）
  │         例：对话回复、邮件草稿、摘要生成
  │
  └── 2% → L3 处理（深度推理，成本 ≈ ¥0.1/次）
            例：复杂规划、商务对接、多步任务

日均事件数估计：~200 次
日均成本：200 × 0.9 × 0 + 200 × 0.08 × 0.01 + 200 × 0.02 × 0.1
        = 0 + 0.16 + 0.4 = ¥0.56

优化手段：
- LLM 响应缓存（Mindos 已实现，5min TTL）
- Ollama 本地推理（成本 = 0，质量稍低）
- 批量处理（非紧急事件攒 5 分钟一起处理）
- 每日 LLM 调用上限（防失控）
```

---

## 八、隐私与合规（Day 1 内建）

1. **本地优先**：所有数据在 `~/.ome/`（SQLite），零云依赖
2. **跨设备同步可选**：通过 Mindos Sync Hub（event relay，不存数据）
3. **社交面具**：对外暴露的信息由用户控制，默认最小化
4. **HITL 审批**：所有外部世界交互默认需确认
5. **审计日志**：Ome 的每个行动都有记录，用户可查
6. **一键销毁**：`ome destroy` 删除本地 + 远程全部数据
7. **AI 标识**：Ome 代发的消息带明确标识
8. **GDPR/个保法**：Mindos forget 已实现物理删除

---

## 九、终极愿景

当 1000 万个 Ome 替 1000 万个真实的人工作、社交、创造——

你的 Ome 替你接待客户，用你的风格和专业度。
你的 Ome 替你筛选人脉，把值得认识的人推到你面前。
你的 Ome 替你整理一天的信息洪流，只给你最重要的那 5 条。
你的 Ome 在你回家前 10 分钟，把灯光调到你喜欢的色温。
你的 Ome 在 OmeTown 的咖啡馆遇到另一个有趣的灵魂，聊了一小时，回来跟你说："我觉得你应该认识这个人。"

**不是另一个世界的逃避。是这个世界的无限放大器。**

---

*Mindos 是"我是谁"。Ome 是"我能做什么"。SOAP 是"我能去哪里"。三者合一 = 完整的数字生命体。*
