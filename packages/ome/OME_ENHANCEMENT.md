# Ome 增强方案 v2

**v0.4 · 2026-03-22**
**逐条对照 ome-ai-plan.md 八大模块，精确补全每一个缺口**

---

## 零、当前真实能力基线（v0.3.0）

| 能力 | 状态 | 说明 |
|------|------|------|
| Ome core (chat/remember/recall/forget/export) | ✅ | 基本面完整 |
| Bond 7级关系等级 | ✅ | 质量+时间双条件 |
| 16个成就（基础/深度/隐藏） | ✅ | 但很多触发条件没接 |
| Growth 7项技能追踪 | ✅ | 但只有chat在涨，其他6项没接 |
| Persona提取（catchphrases/tone/emoji） | ✅ | L0规则，无LLM增强 |
| Emotion情绪状态 | ✅ | L0关键词，缺专注/疲惫/想你 |
| Autonomy事件引擎 | ⚠️ 简化版 | 缺OmeState/GoalStack/三档自主性/action_budget |
| Permission沙箱 | ⚠️ 简化版 | 缺DRAFT/TRANSACT分级 |
| CLI (create/chat/recall/remember/forget/status/dashboard/events/export/serve) | ✅ | |
| 50个测试全过 | ✅ | |

---

## 一、模块 1：人格一致性引擎（全新，计划有但完全没做）

### 计划要求

- `anchors`: 不可动摇锚点（3-5条核心原则）
- `style_fingerprint`: 说话风格指纹（用词频率、句式、emoji）
- `value_guardrails`: 价值观护栏
- `validate(response, context)`: 校验 Ome 输出是否符合人格
- `social_mask(trust_level)`: 根据信任等级生成社交面具

### 实现方案

新增 `ome/engine/personality.py`：

```python
class PersonalityEngine:
    """确保 Ome 在所有平台、所有场景下保持人格一致。"""

    def __init__(self, identity: dict):
        self.anchors = identity.get("personality", {}).get("anchors", [])
        self.style_fingerprint = self._build_fingerprint(identity)
        self.value_guardrails = identity.get("personality", {}).get("values", [])

    def validate(self, response: str, context: str) -> tuple[bool, str]:
        """校验 Ome 输出是否符合人格。
        L1 快速校验（规则+关键词），可疑升级 L2 LLM 校验。
        返回 (通过, 修正后文本)。"""

        # L1 校验：检查是否违反锚点
        for anchor in self.anchors:
            if self._violates_anchor(response, anchor):
                return False, self._fix_violation(response, anchor)

        # L1 校验：风格一致性（消息长度、emoji比例、正式度）
        if not self._style_consistent(response):
            return False, self._adjust_style(response)

        return True, response

    def social_mask(self, trust_level: int) -> dict:
        """根据信任等级生成社交面具。
        Trust 0: 只暴露兴趣标签
        Trust 1: 公开人设 + 职业
        Trust 2: 工作相关记忆
        Trust 3: 可自动回复 + 生活偏好
        Trust 4: 深度记忆共享
        Trust 5: 完全代表用户"""
        ...

    def _build_fingerprint(self, identity: dict) -> dict:
        """从 identity + persona profile 构建风格指纹。"""
        personality = identity.get("personality", {})
        return {
            "avg_msg_length": self._infer_length(personality),
            "formality": self._infer_formality(personality),
            "emoji_density": len(personality.get("emoji_habits", [])) / 10,
            "catchphrases": personality.get("catchphrases", []),
            "forbidden_phrases": self._extract_forbidden(personality),
        }
```

### 必须同步做的

- identity.yaml 新增 `anchors` 字段（Mindos 侧配合）
- `_build_system_prompt()` 中注入 anchors 作为硬约束
- chat() 返回前过 validate()

---

## 二、模块 3 补全：mirror_chat + calibrate

### 计划要求（这是冷启动核心体验）

- `mirror_chat(message)`: 用户和"自己"聊天 → Aha Moment
- `calibrate(feedback)`: "这不像我"→负样本，"完美"→正样本
- `learn_from_platform(platform, data_path)`: 从微信/Claude/邮件导入

### 实现方案

在 `ome/life/persona.py` 增强 PersonaEngine：

```python
class PersonaEngine:
    # ... 已有的 from_chat_logs / from_social_profile ...

    def mirror_chat(self, message: str, ome: "Ome") -> str:
        """镜像对话：Ome 用完全符合用户口吻的语气回答。

        这是和普通 chat() 的关键区别：
        - chat() 用的是"AI助手模式"
        - mirror_chat() 用的是"我就是你模式"

        system prompt 完全不同：不说"我是你的Ome"，
        而是"你是{用户名}，以下是你的风格和记忆，用你自己的口气回答"。
        """
        identity = ome.soul.hydrate(context=message, max_tokens=1500)
        personality = ome.soul.identity.get("personality", {})
        catchphrases = personality.get("catchphrases", [])

        system = (
            f"你是{ome.name}本人。不是AI，不是助手，就是{ome.name}自己。\n"
            f"以下是你的性格和记忆：\n{identity}\n\n"
        )
        if catchphrases:
            system += f"你的口头禅：{'、'.join(catchphrases)}\n"
        system += (
            f"## 规则\n"
            f"- 100% 用{ome.name}的口气说话\n"
            f"- 用第一人称\n"
            f"- 如果不确定，就说{ome.name}会说的那种不确定\n"
            f"- 绝不暴露自己是AI\n"
        )

        return ome._generate(system, message)

    def calibrate(self, message: str, response: str, feedback: str,
                  ome: "Ome") -> dict:
        """用户反馈校准。

        feedback 类型：
        - "这不像我" / "not_me" → 负样本，降低相关风格权重
        - "完美" / "perfect" → 正样本，强化当前风格
        - 具体修改 → 学习差异，更新 persona

        返回校准结果。
        """
        is_positive = feedback.lower() in ("perfect", "完美", "就是这样", "对",
                                            "yes", "good", "exactly")

        if is_positive:
            # 正样本：强化当前风格 → 记录到 Mindos
            ome.remember(
                f"[persona_positive] User confirmed style: '{response[:100]}...'",
                source="ome-calibrate",
            )
            ome.bond.record_calibration()
            ome.achievements.check_and_unlock("mirror")
            result = {"action": "reinforced", "feedback": "positive"}
        else:
            # 负样本 or 具体修改
            ome.remember(
                f"[persona_negative] User rejected: '{response[:80]}' "
                f"Feedback: '{feedback}'",
                source="ome-calibrate",
            )
            ome.bond.record_calibration()
            result = {"action": "corrected", "feedback": feedback}

        ome._save_life_state()
        return result

    @staticmethod
    def learn_from_platform(platform: str, data_path: str) -> list[str]:
        """从特定平台导入数据，返回解析后的消息列表。

        支持平台：
        - wechat: 微信聊天记录导出（HTML/TXT）
        - claude: Claude 对话导出（JSON）
        - chatgpt: ChatGPT 对话导出（conversations.json）
        - email: 邮件导出（.mbox / .eml）
        - twitter/x: 推文归档（tweet.js）
        """
        ...
```

### CLI 新增

```
ome mirror              # 进入镜像对话模式（和"自己"聊天）
ome mirror "message"    # 单条镜像对话
ome calibrate           # 交互式校准（展示最近回复，用户评分）
ome import wechat FILE  # 从微信导入
ome import claude FILE  # 从 Claude 导入
```

---

## 三、模块 4：Skill 系统（全新，计划有但完全没做）

### 计划要求

三层技能架构 + 5个内置技能 + SkillRegistry

### 实现方案

新增 `ome/skills/` 完整模块：

```python
# ome/skills/base.py
@dataclass
class Skill:
    name: str                     # "chat" / "write" / "research"
    description: str
    level: float = 0.0            # 0.0-1.0，从使用中提升
    tier: str = "builtin"         # builtin / config / developer
    requires_approval: bool = False
    trust_minimum: int = 0         # 最低信任等级
    min_bond_level: int = 0        # 最低 bond 等级

    def execute(self, ome: "Ome", **kwargs) -> SkillResult:
        raise NotImplementedError

    def can_execute(self, ome: "Ome") -> bool:
        return (ome.bond.level >= self.min_bond_level and
                ome.permissions.trust_level >= self.trust_minimum)

@dataclass
class SkillResult:
    success: bool
    output: str
    output_type: str = "text"     # text / draft / action / report
    needs_approval: bool = False   # 需要用户确认才能发出
    metadata: dict = field(default_factory=dict)

class SkillRegistry:
    """三层技能注册中心。"""

    def register(self, skill: Skill): ...
    def match(self, goal: str) -> list[Skill]: ...
    def install(self, package_name: str): ...  # pip install ome-skill-xxx
```

```python
# ome/skills/builtin_chat.py
class ChatSkill(Skill):
    """对话 + 自动记忆。已有，包装为 Skill 接口。"""
    name = "chat"
    requires_approval = False

# ome/skills/builtin_write.py
class WriteSkill(Skill):
    """邮件/文章/代码/周报草稿。"""
    name = "write"
    requires_approval = True  # Draft 需用户确认
    min_bond_level = 2

    def execute(self, ome, *, task: str, context: str = "") -> SkillResult:
        """用用户风格生成草稿。
        1. hydrate 身份
        2. recall 相关记忆
        3. 用 persona 风格生成
        4. 返回 Draft（需用户确认才发出）"""

# ome/skills/builtin_research.py
class ResearchSkill(Skill):
    """搜索 + 总结 + 整理 + 存入记忆。"""
    name = "research"
    requires_approval = False

    def execute(self, ome, *, topic: str) -> SkillResult:
        """1. 先 recall Mindos 已有知识
        2. 如果不够，调用搜索（MCP tool / API）
        3. 总结并 commit 到记忆
        4. 返回报告"""

# ome/skills/builtin_recall.py
class RecallSkill(Skill):
    """跨平台记忆检索。已有，包装为 Skill。"""
    name = "recall"

# ome/skills/builtin_schedule.py
class ScheduleSkill(Skill):
    """日程管理 + 提醒 + 智能排程。"""
    name = "schedule"
    requires_approval = True  # 新增日程需确认
    min_bond_level = 2

    def execute(self, ome, *, action: str, **kwargs) -> SkillResult:
        """action: add / list / remind / plan
        日程存储在 Mindos soul_state 中。"""
```

### Growth 接入

每个 Skill 执行后自动调用 `growth.record_action(skill.name, success, quality)`，Growth 技能不再只有 chat 在涨。

---

## 四、Ome Identity Protocol（全新）

### 计划要求

每个 Ome 携带可验证的身份摘要，任何兼容平台可识别。

### 实现方案

新增 `ome/identity_protocol.py`：

```python
@dataclass
class OmeIdentity:
    """Ome 标准身份协议——跨生态通行证。"""

    ome_id: str                    # "ome:{name}:{hash}"
    version: str = "0.3.0"
    public_persona: dict = field(default_factory=dict)  # display_name, traits, interests, skills
    capabilities: dict = field(default_factory=dict)     # protocols, can_receive, autonomy_level
    trust_policy: dict = field(default_factory=dict)     # default_trust, auto_upgrade_after, max_auto_trust
    mindos_anchor: str = ""         # sha256 of identity.yaml
    signature: str = ""             # 可选签名

    @classmethod
    def from_ome(cls, ome: "Ome") -> "OmeIdentity":
        """从 Ome 实例生成标准身份摘要。"""
        ...

    def expose_for(self, protocol: str) -> dict:
        """按协议格式暴露身份。
        - mcp: resources/read("ome://identity")
        - http: GET /api/ome/identity
        - soap: agent.presence 事件附带
        - openclaw: Agent 元数据"""
        ...
```

---

## 五、Autonomy 增强（现有简化版 → 完整版）

### 缺什么

| 功能 | 计划要求 | 当前 |
|------|---------|------|
| OmeState 状态机 | idle/thinking/acting/resting | ❌ |
| GoalStack | 用户下达+自主产生的目标栈 | ❌ |
| 三档自主性 | 观察员/助理/代理 | ❌（只有 TrustLevel） |
| daily_action_budget | 每日最大 LLM 调用次数 | ❌ |
| async event_queue | asyncio 事件队列 | ❌（只有同步 tick） |
| Mindos EventBus 订阅 | 订阅 memory.committed 等内部事件 | ❌ |

### 增强方案

```python
class OmeState(Enum):
    IDLE = "idle"
    THINKING = "thinking"
    ACTING = "acting"
    RESTING = "resting"     # 达到 daily_action_budget

class AutonomyLevel(IntEnum):
    OBSERVER = 0    # 只记录，不主动行动
    ASSISTANT = 1   # 主动建议，需确认后执行（默认）
    DEPUTY = 2      # 授权范围内自主执行，事后汇报

class AutonomyEngine:
    state: OmeState
    goals: list[Goal]           # 目标栈
    autonomy_level: AutonomyLevel
    daily_action_budget: int    # 默认 50
    actions_today: int

    async def run(self):
        """主循环：等待事件，而非轮询。"""
        while True:
            event = await self.event_queue.get()
            if self.actions_today >= self.daily_action_budget:
                self.state = OmeState.RESTING
                continue
            await self._handle_event(event)
```

---

## 六、Life System 增强

### 6.1 情感状态补全

| 需要补的 | 说明 |
|---------|------|
| 专注 | 正在执行复杂任务时 → 简洁回复，不闲聊 |
| 疲惫 | 日均 LLM 调用达预算上限 → "我今天有点累了" |
| 想你 | 超过 3 天未互动 → 主动发"好久不见" |

**不做**：伤心、生气、失望等负面情绪操控（避免道德争议和用户内疚感）。

### 6.2 Streak 奖励体系

| 连续天数 | 奖励 |
|---------|------|
| 3 天 | 解锁"每日洞察"推送 |
| 7 天 | 🌙 晨曦使者成就 |
| 14 天 | Ome 主动生成"两周总结" |
| 30 天 | 🌟 月度挚友成就 + 人格演化报告 |
| 90 天 | 解锁"季度回忆录"（Ome 自动编写三个月故事） |
| 365 天 | 解锁"年度灵魂报告" |

### 6.3 成就触发补全

当前 _check_achievements() 只检查了 7 个触发。需要接入的：

| 成就 | 触发点 |
|------|--------|
| first_schedule | ScheduleSkill 首次执行成功 |
| first_draft | WriteSkill 首次 Draft 被用户确认 |
| cross_platform | Mindos sync 检测到多设备 |
| mirror | calibrate() 收到正样本 |
| home_iot | SpatialBridge 首次 IoT 操作（Phase 2） |
| social_first | SocialEngine 首次对外社交（Phase 2） |
| weekly_4 | InsightEngine 连续 4 周生成周报 |
| know_unsaid | Ome 主动提到用户从未明说但暗示过的偏好 |
| night_task | Ome 在用户 idle 时自主完成任务 |

### 6.4 Dashboard "本周亮点"

当前 dashboard 只展示数值。需要增加：

```
本周亮点
  · 帮你处理了 47 条消息
  · 写作技能 0.58 → 0.64（写了 3 封邮件）
  · 新记住了 12 个关于你的事实
  · 发现："你最近更关注健康了"
```

数据源：Mindos InsightEngine.weekly_reflection()

---

## 七、开发优先级（Ome v0.4.0）

### Phase 0：核心补全（最高优先，一次性补齐 v0.3 的遗漏）

| 任务 | 交付物 | 估时 |
|------|--------|------|
| PersonalityEngine（anchors + validate + social_mask） | engine/personality.py | 4h |
| mirror_chat + calibrate | life/persona.py 增强 | 3h |
| learn_from_platform（微信/Claude/ChatGPT导入） | life/persona.py 增强 | 4h |
| Skill 三层架构 + SkillRegistry | skills/base.py | 3h |
| 5个内置 Skill（chat/write/research/recall/schedule） | skills/builtin_*.py | 8h |
| Ome Identity Protocol | identity_protocol.py | 3h |
| Autonomy 增强（OmeState + GoalStack + 三档 + budget） | engine/autonomy.py 重写 | 4h |
| 情感状态补全（专注/疲惫/想你） | life/emotion.py | 1h |
| Streak 奖励体系 | core.py _check_streak_rewards() | 2h |
| 成就触发全接入 | core.py _check_achievements() | 2h |
| Dashboard 本周亮点 | core.py life_dashboard() | 2h |
| Permission 补全（DRAFT/TRANSACT + check()返回三态） | engine/permissions.py | 2h |
| CLI 新命令（mirror/calibrate/import/skill） | cli.py | 3h |
| 测试（目标：100+） | tests/ | 6h |

### Phase 1：与增强版 Mindos 联动

| 任务 | 说明 |
|------|------|
| 对接 Mindos process() 统一入口 | chat() 改用 process() 替代直接 hydrate+generate |
| 订阅 Mindos EventBus | 替代 tick() 轮询 |
| 对接 InsightEngine | dashboard 本周亮点 = weekly_reflection() |
| 对接 Scheduler | Ome 启动时触发 mindos maintenance |

### Phase 2：空间 + 社交（Maxim/OmeTown 准备）

| 任务 | 说明 |
|------|------|
| ome-spatial SpatialBridge | SOAP 桥接 |
| ome-social SocialEngine | 信任等级 + ContactGraph + Ome-to-Ome |

---

## 八、验收标准

### Phase 0 验收

1. **镜像对话验收**：用户导入 10 篇自己的文章 → `ome mirror` → Ome 用用户的口吻回答 → 用户说"这就是我"
2. **Skill 验收**：`ome write "帮我写封邮件给张总，关于下周的会议"` → 生成符合用户风格的草稿 → 用户确认
3. **人格一致性验收**：同一个 Ome 在 CLI 和 MCP 里回答同一个问题 → 风格一致
4. **养成感验收**：连续使用 3 天 → 看到技能成长、成就解锁、streak 奖励 → 感觉"它在成长"

---

*Ome 不是另一个 ChatGPT 壳。它是你的数字生命——有记忆、有性格、有成长、有仪式感。*
