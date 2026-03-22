# Mindos 开发计划

**v0.2 · 2026-03-21**
**永久摇光：可插拔的数字灵魂协议**

---

## 零、根本性反思：v0.1 做错了什么

v0.1 把 Mindos 定位为"Claws 的大脑"——又一个 Agent 框架，和 OpenClaw 互补。这个定位太窄了。

OpenClaw 做手脚，我们做大脑？那我们永远是 OpenClaw 的配件。

真正的问题是：**今天所有的 AI 交互——Claude、ChatGPT、Cursor、OpenClaw、任何 Agent——都是一次性的。** 你和 Claude 聊了三个月，换到 GPT 就一切归零。你在 OpenClaw 里积累的记忆，搬不到别的平台。你的个性、偏好、知识、习惯、风格，被锁死在每一个平台的孤岛里。

**这就是 Mindos 要解决的问题。**

---

## 一、Mindos 是什么

### 不是 Agent 框架。不是大脑插件。是你的数字灵魂。

**Mindos 是一层可插拔的持久身份协议。** 它承载一个人（或 AI 角色）的：

| 维度 | 内容 | 类比 |
|------|------|------|
| **记忆** | 所有经历、对话、学到的知识 | 海马体 |
| **个性** | 说话风格、价值观、性格特征 | 性格基因 |
| **习性** | 作息偏好、工作方式、决策模式 | 肌肉记忆 |
| **能力** | 擅长什么、不擅长什么、技能树 | 专业积累 |
| **关系** | 认识谁、对谁的印象、社交图谱 | 社会脑 |

**关键洞察：这些东西和"用哪个大模型"无关。** 它们属于用户自己。

### 一个比喻

你的 Mindos 就像你的大脑记忆 + 人格。你的身体（平台）可以换——今天用 Claude 的身体，明天用 GPT 的身体，后天住进 OpenClaw 的身体，大后天通过 SOAP 走进 3D 世界的身体。但你的灵魂始终是你的，走到哪带到哪，而且每一次经历都让你更完整。

```
你 (主人)
 │
 │ 拥有
 ▼
┌───────────────────────────────────┐
│          你的 Mindos               │  ← 你的数字灵魂（本地/自托管）
│                                   │
│  记忆 · 个性 · 习性 · 能力 · 关系   │
│                                   │
│  hydrate() ──→ 注入到任何 AI 会话   │
│  commit()  ──→ 从任何 AI 会话写回   │
└──────┬────────────┬───────────────┘
       │            │
  ┌────▼────┐  ┌───▼────┐  ┌──────────┐  ┌──────────┐
  │ Claude  │  │  GPT   │  │ OpenClaw │  │ SOAP 空间 │ ...
  │  对话   │  │  对话   │  │  Agent   │  │ 3D 世界  │
  └─────────┘  └────────┘  └──────────┘  └──────────┘
       ↑            ↑           ↑              ↑
       所有平台都读/写同一份 Mindos，经历统一积累
```

### 为什么人离不开

1. **用了 3 个月**：Mindos 记住了你所有对话中提到的人名、偏好、项目、决定。换任何新平台，插上 Mindos，新平台立刻"认识"你。
2. **用了 1 年**：Mindos 的知识图谱覆盖了你的工作流程、人际关系、决策历史。它比你自己更清楚你去年做了什么决定以及为什么。
3. **用了 3 年**：Mindos 沉淀出了一个你的"数字镜像"——你的思考方式、表达风格、价值判断。这已经不是工具，是你的一部分。

**切换成本指数级增长。这就是护城河。**

---

## 二、核心协议设计

### 2.1 两个原语：hydrate 与 commit

整个 Mindos 的外部接口只有两个核心操作：

```python
# hydrate（水合）：给定当前上下文，从 Mindos 中提取最相关的身份信息
context = mindos.hydrate(
    situation="用户在 Claude 中讨论下周旅行计划",
    recent_messages=[...],       # 最近几轮对话
    max_tokens=2000,             # 预算：注入到 system prompt 的空间
)
# 返回：精心组装的身份片段——相关记忆、个性描述、相关能力、相关关系

# commit（提交）：对话结束后，将新经历写回 Mindos
mindos.commit(
    messages=[...],              # 本次对话全文
    source="claude-web",         # 来源平台标识
    auto_extract=True,           # 自动提取事实、偏好、关系变化
)
# Mindos 自动完成：摘要、分类、关联、存储、更新知识图谱
```

```python
# forget（遗忘）：物理级擦除指定记忆——GDPR Right to be Forgotten
mindos.forget(
    pattern="关于项目X的一切",       # 自然语言或正则
    scope="all",                     # all / facts / episodes / relations
    hard_delete=True,                # 物理擦除，非降权
)
# 从 SQLite、向量索引、知识图谱中彻底移除匹配内容
```

**三个原语，覆盖灵魂的完整生命周期**：hydrate 读取，commit 写入，forget 擦除。任何平台只需实现"对话开始时调 hydrate，对话结束时调 commit"就完成集成。forget 由用户按需调用，确保数据主权。

### 2.2 hydrate 的智能——不是简单的 RAG

hydrate 不是暴力把所有记忆塞进 prompt。它是**情境感知的身份组装器**：

```
输入：当前会话的语境
            │
    ┌───────▼───────┐
    │  意图识别       │  这次对话可能涉及什么领域？
    └───────┬───────┘
            │
    ┌───────▼───────┐
    │  记忆检索       │  从 L0 拉取相关记忆（向量 + 关键词 + 图）
    └───────┬───────┘
            │
    ┌───────▼───────┐
    │  个性裁剪       │  根据场景选择合适的性格面（工作/休闲/创作）
    └───────┬───────┘
            │
    ┌───────▼───────┐
    │  能力匹配       │  当前任务需要哪些技能？
    └───────┬───────┘
            │
    ┌───────▼───────┐
    │  关系上下文     │  对话中提到的人，Mindos 对他们有什么记忆？
    └───────┬───────┘
            │
    ┌───────▼───────┐
    │  Token 预算分配 │  在有限的 prompt 空间内优先放最重要的内容
    └───────┬───────┘
            │
            ▼
    输出：≤ max_tokens 的身份上下文（直接拼入 system prompt）
```

### 2.3 commit 的智能——不是简单的日志追加

commit 不是存聊天记录。它是**认知消化器**：

```
输入：一段完整对话
            │
    ┌───────▼───────┐
    │  事实提取       │  用户提到了新信息？（"我下周去东京"）
    └───────┬───────┘
            │
    ┌───────▼───────┐
    │  偏好更新       │  用户展示了新偏好？（"我更喜欢简洁的表达"）
    └───────┬───────┘
            │
    ┌───────▼───────┐
    │  关系变化       │  提到了新的人？对某人印象变了？
    └───────┬───────┘
            │
    ┌───────▼───────┐
    │  能力信号       │  用户在这个领域的表现如何？是否可以更新技能评估？
    └───────┬───────┘
            │
    ┌───────▼───────┐
    │  情绪标注       │  这段对话的情绪基调是什么？
    └───────┬───────┘
            │
    ┌───────▼───────┐
    │  去重 & 合并    │  新信息是否修正了旧记忆？（搬家了→更新地址）
    └───────┬───────┘
            │
    ┌───────▼───────┐
    │  置信度评分     │  高→直接写入  中→标记待确认  低→丢弃
    └───────┬───────┘  玩笑/假设/反讽 → 自动降权
            │
    ┌───────▼───────┐
    │  矛盾检测       │  与已有记忆冲突？→ 触发冲突解决而非静默覆盖
    └───────┬───────┘
            │
    ┌───────▼───────┐
    │  敏感信息过滤   │  密码/身份证号/API Key → 自动拒绝存储
    └───────┬───────┘
            │
            ▼
    写入 L0 记忆层 + 更新知识图谱 + 更新人格描述
```

### 2.4 多平台同步

用户可能同时在 Claude 里聊工作、在 GPT 里聊旅行。两个平台各自 commit，Mindos 需要合并：

```
Claude 对话 ──→ commit(source="claude") ──→ ┐
                                             ├──→ Mindos 合并引擎
GPT 对话   ──→ commit(source="gpt")   ──→ ┘      │
                                                    ▼
                                              统一的记忆 + 知识图谱
```

**冲突解决策略**：时间戳优先 + 来源加权 + 手动确认（重大事实变更）。日常使用中冲突极少——两个平台很少同时更新同一条事实。

---

## 三、数据归属与存储

### 3.1 用户拥有自己的数据

Mindos 是 **local-first** 的：

```
~/.mindos/
├── identity.yaml        # 人格描述（可编辑）
├── memory.db            # SQLite：所有记忆
├── knowledge.json       # 知识图谱
├── vectors/             # 向量索引
├── journal/             # 原始对话日志（可选保留）
│   ├── 2026-03-21-claude.jsonl
│   ├── 2026-03-21-gpt.jsonl
│   └── ...
└── config.yaml          # 配置（LLM、检索参数、同步设置）
```

整个 Mindos 就是一个目录。你可以 `cp -r` 备份，`rsync` 同步到另一台电脑，用 git 做版本控制。**没有云端锁定。**

### 3.2 可选的云端同步

对于跨设备使用的用户，提供可选的加密同步：
- 自托管：用户自己的 S3 / WebDAV / Syncthing
- 托管服务（后期）：Mindos Cloud（E2E 加密，零知识）

---

## 四、集成方式——插拔到任何平台

### 4.1 最轻量：MCP Server

Mindos 作为 MCP Server 运行，任何支持 MCP 的 AI 平台（Claude、Cursor、各种 Claw）直接调用：

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

MCP 工具：
- `mindos_hydrate(situation, recent_messages, max_tokens)` → 身份上下文
- `mindos_commit(messages, source)` → 写回经历
- `mindos_recall(query)` → 查询特定记忆
- `mindos_who(name)` → 查询某人的关系记忆

### 4.2 HTTP API

对于不支持 MCP 的平台，提供本地 HTTP 接口：

```
POST /hydrate   ← 获取身份上下文
POST /commit    ← 写回对话
GET  /recall    ← 查询记忆
GET  /status    ← 当前状态
```

### 4.3 Python SDK

```python
from mindos import Mindos

me = Mindos.load("~/.mindos")

# 在任何 LLM 调用前 hydrate
system_prompt = me.hydrate(situation="写代码", max_tokens=1500)
response = llm.chat(system=system_prompt, messages=[...])

# 对话后 commit
me.commit(messages=[...], source="my-app")
```

### 4.4 Proxy 模式——零代码接入（推荐）

Mindos 作为 API 反向代理运行，用户只需将 API base URL 改为 `localhost:8080`，其余代码零改动：

```bash
mindos serve --proxy --port 8080 --upstream https://api.openai.com
```

工作流程：

```
用户应用（base_url=localhost:8080）
     │ 发送请求
     ▼
┌─── Mindos Proxy ────────────────────────┐
│  1. 拦截请求                              │
│  2. 自动 hydrate → 注入身份到 system prompt │
│  3. 转发给上游 LLM API                    │
│  4. 收到回复                              │
│  5. 自动 commit → 提取记忆写回             │
│  6. 返回原始回复给用户                     │
└─────────────────────────────────────────┘
```

比浏览器插件稳定得多（不依赖 DOM），比 MCP 更通用（支持所有 OpenAI 兼容 API）。

### 4.5 浏览器插件（Phase 2）

自动拦截 Claude/ChatGPT 的 Web 会话，对话开始时 hydrate，结束时 commit。用户无感知，记忆自动同步。作为 Proxy 模式的补充，覆盖 Web UI 场景。

### 4.5 SOAP 集成——灵魂进入 3D 世界

```python
from mindos import Mindos
from mindos.spatial import SOAPBridge

me = Mindos.load("~/.mindos")
bridge = SOAPBridge(me, server="http://localhost:8765")

# Mindos 的记忆和个性驱动 SOAP Agent 在 3D 空间中行动
bridge.run()  # sense-think-act loop，思考由 Mindos 驱动
```

---

## 五、五层脑架构

### 5.1 设计哲学

Mindos 的五层对应一个完整灵魂需要的五种能力：**记得、感知、理解、决策、自知**。

前四层（L0-L3）是功能层——处理信息的流水线，从存储到推理。第五层（L4）是元层——它不处理信息，它审视"我是谁"。这正是让 Mindos 从"大脑"升华为"灵魂"的关键。

行为控制不需要独立成层。在真实大脑中，行为也不是由单一区域产生的——条件反射由脑干驱动，计划性行为由前额叶编排，而自我层确保一切行动符合"我是谁"。Mindos 同理。

### 5.2 总览

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

### 5.3 五层详解

| 层 | 名称 | 脑区 | 一句话 | 延迟 | 成本 |
|----|------|------|--------|------|------|
| **L0** | 海马体 | Hippocampus | 你**记得**什么 | < 50ms | ≈ 0 |
| **L1** | 脑干 | Brainstem | 你**本能**的反应 | < 100ms | ≈ 0 |
| **L2** | 皮层 | Cortex | 你如何**理解**世界 | < 2s | 极低 |
| **L3** | 前额叶 | Prefrontal | 你如何**决策**和行动 | 2-15s | 按需 |
| **L4** | 自我 | DMN | 你**是谁** | 异步 | 极低 |

#### L0 海马体——记忆

一切经验的沉淀。hydrate() 从这里提取，commit() 向这里写入。

- **事实记忆**：用户说过的具体信息（"我住在上海"、"我对花生过敏"）
- **情景记忆**：完整的交互片段，带时间戳和情绪标注
- **关系图谱**：人物之间的关系网络（"张三是用户的同事，关系一般"）
- **能力档案**：用户在各领域的表现评估
- **向量索引**：所有记忆的语义检索层
- **遗忘曲线**：长期不被访问的记忆逐渐衰减权重，但不删除

#### L1 脑干——本能

不需要思考的快速反应，处理 60% 以上的日常请求，成本几乎为零。

- **情绪状态机**：追踪用户当前情绪，调整回应基调
- **作息节律**：知道用户几点起床、何时工作效率最高
- **安全边界**：拒绝危险请求、保护隐私的硬编码规则
- **条件反射**：常见模式的即时回应（问候→回应、感谢→致谢）
- **hydrate 组装**：根据当前上下文从 L0 提取最相关的记忆片段
- **Token 预算分配**：根据场景决定给宿主 LLM 注入多少身份信息
- **路由决策**：判断请求是否需要上升到 L2/L3 处理

#### L2 皮层——认知

日常的理解和分析能力，由本地轻量模型或宿主 LLM 驱动。

- **commit 消化**：从对话中提取事实、偏好、关系变化、能力信号
- **知识图谱更新**：将提取的信息融合进已有知识网络
- **日常对话理解**：语义分析、意图识别、上下文补全
- **社交判断**：理解对话中的人际动态
- **去重与合并**：新信息是否修正了旧记忆？（搬家了→更新地址）

#### L3 前额叶——决策

复杂思考和行为规划，按需调用强力 LLM，是成本的主要来源。

- **深度推理**：需要多步逻辑链的复杂问题
- **创作**：写作、设计、头脑风暴
- **战略规划**：长期目标分解、优先级排序
- **行为编排**：把意图转化为具体行动序列（SOAP 导航、工具调用、多步执行）
- **冲突解决**：当多个目标冲突时做取舍

行为控制自然属于前额叶——在神经科学中，前额叶就是执行控制中枢。它不只是"想"，更负责"计划怎么做"。具体行动的执行则由宿主平台完成（SOAP、OpenClaw、浏览器等），Mindos 只输出行动方案。

#### L4 自我——人格

其他四层处理信息，这一层审视"我是谁"。它是 Mindos 区别于所有其他 AI 系统的根本。

- **人格模型**：维护一个持续演化的自我描述——价值观、风格、偏好、禁区
- **反思循环**：定期（每日或每 N 次 commit）审视近期经历，更新自我认知
- **一致性守护**：所有层的输出都经过 L4 校验——"这个回答/行为符合我的人格吗？"
- **认知失调检测**：当近期行为与人格模型显著偏离时，主动生成 Diff 提案——*"我注意到你最近三个月聊了大量艺术话题，这与之前的'硬核技术'人格有显著偏移。是否更新核心人格描述？"* 这种"AI 察觉到你在变，并请求同步"的时刻，是最强的情感锚点。
- **成长轨迹**：记录人格随时间的变化（"三个月前我更保守，现在更开放了"），支持 `mindos history` 查看演化时间线
- **跨平台身份锚**：无论在 Claude、GPT、SOAP 空间还是移动端，L4 确保"我"始终是"我"

L4 不需要高成本 LLM。它更像一个持续运行的低频后台进程，定期通过反思循环自我更新。

### 5.4 信息流与行为控制

```
        ┌─────────────────────────────────────────┐
        │              L4 自我（人格守护）           │
        │  "这符合我的价值观吗？风格对吗？"           │
        └────────────┬──────────────┬──────────────┘
                     │ 校验          │ 反思
    输入             ▼              ▼
     │    ┌──── L0 记忆检索 ────┐
     ├───→│                     │
     │    └────────┬────────────┘
     │             ▼
     │    ┌──── L1 本能判断 ────┐   60%+ 直接响应 ──→ 输出
     ├───→│  能直接处理？        │
     │    └────────┬────────────┘
     │         需要思考 ▼
     │    ┌──── L2 认知分析 ────┐   30% 日常认知 ──→ 输出
     │    │  理解、消化、分析    │
     │    └────────┬────────────┘
     │         需要深度 ▼
     │    ┌──── L3 前额叶决策 ──┐   10% 深度推理 ──→ 输出
     │    │  推理、规划、行为编排  │        ↓
     │    └─────────────────────┘   行动方案
     │                                    ↓
     │                          ┌──────────────────┐
     └──────────────────────────│ 宿主平台执行行动   │
           反馈回路               │ SOAP / OpenClaw / │
                                │ Browser / CLI     │
                                └──────────────────┘
```

**行为控制的分布式设计**：

| 行为类型 | 处理层 | 示例 |
|---------|--------|------|
| 条件反射 | L1 脑干 | 问候回应、危险拒绝、简单确认 |
| 习惯行为 | L1 + L0 | 根据记忆中的习惯模式自动行动 |
| 日常行为 | L2 皮层 | 社交回应、信息整理、简单建议 |
| 计划行为 | L3 前额叶 | 多步任务编排、SOAP 导航、工具调用链 |
| 价值对齐 | L4 自我 | 校验行为是否符合人格（"我不会这样说话"） |

### 5.3 ModelRouter——模型智能切换

Mindos 不绑定任何大模型。ModelRouter 根据任务类型、质量要求、延迟预算、成本预算，自动选择最优模型：

```python
class ModelRouter:
    """根据任务需求智能选择 LLM 后端"""

    providers: List[ModelProvider]  # 已配置的模型列表

    def select(self, task: Task) -> ModelProvider:
        # 按优先级匹配：
        # 1. 宿主平台自带的 LLM（零额外成本）
        # 2. 本地模型（Ollama 7B/14B，隐私优先）
        # 3. 云端高性价比（DeepSeek，日常推理）
        # 4. 云端旗舰（Claude/GPT，重度推理/创作）
        candidates = [p for p in self.providers if p.supports(task)]
        return self.rank(candidates, task.quality, task.latency, task.budget)
```

配置示例（`~/.mindos/config.yaml`）：

```yaml
models:
  - name: host          # 宿主平台的 LLM（如 Claude MCP 会话中的 Claude 本身）
    type: passthrough
    priority: 1         # 最优先：零额外成本
    for: [chat, simple_analysis]

  - name: local-7b
    type: ollama
    model: qwen2.5:7b
    priority: 2
    for: [commit_digest, reflection, classification]

  - name: deepseek
    type: openai_compatible
    base_url: https://api.deepseek.com
    api_key_env: DEEPSEEK_API_KEY
    model: deepseek-chat
    priority: 3
    for: [reasoning, planning, creation]

  - name: claude
    type: anthropic
    api_key_env: ANTHROPIC_API_KEY
    model: claude-sonnet-4-20250514
    priority: 4         # 旗舰：只在关键时刻调用
    for: [deep_reasoning, complex_creation]

  fallback: deepseek    # 兜底模型
```

**质量保障机制**：
- **结果校验**：commit 提取的事实交叉验证，矛盾时标记待确认
- **模型降级透明**：当高优先级模型不可用时自动降级，日志记录选择原因
- **用户可覆盖**：`mindos config set default-model claude` 强制指定

### 5.4 从 Mindos 生成 Ome

Ome（个体 Agent）是 Mindos 的"具身化"——给灵魂一个活的载体：

```python
from mindos import Mindos
from mindos.ome import OmeFactory

# 方式 1：从用户自己的 Mindos 生成 Ome（数字分身）
me = Mindos.load("~/.mindos")
my_ome = OmeFactory.spawn(
    mindos=me,
    name="Aria",
    role="我的 AI 助手",
    skills=["writing", "scheduling", "research"],
    autonomy=0.7,       # 自主程度：0=纯被动，1=完全自主
)
my_ome.run()  # 启动：按作息行动，接任务，社交

# 方式 2：从零创建一个全新 Ome（虚拟角色）
npc = OmeFactory.create(
    name="咖啡师小陈",
    personality="热情、话多、对咖啡有极深的热爱",
    backstory="在意大利学了三年咖啡，回国开了这家店",
    skills=["make_coffee", "speak", "recommend"],
)
npc.run()

# 方式 3：从已有 Mindos 克隆（继承记忆但独立演化）
clone = OmeFactory.fork(source=me, name="Aria-experimental")
```

**Ome 与 Mindos 的关系**：

```
Mindos（灵魂）        Ome（载体）
─────────────        ─────────────
记忆、个性、关系  ──→  驱动行为和对话
                 ←──  新经历写回 Mindos
不依赖任何平台        依赖执行环境（SOAP / OpenClaw / Web）
一个人只有一个        一个 Mindos 可生成多个 Ome
```

### 5.5 平台与设备接入矩阵

| 接入方式 | 适用场景 | 实现 | hydrate | commit |
|---------|---------|------|---------|--------|
| **MCP Server** | Claude Desktop、Cursor、Claw 系列 | `mindos serve --mcp` | ✅ 自动 | ✅ 自动 |
| **HTTP API** | 任何能发 HTTP 的应用 | `mindos serve --http` | ✅ | ✅ |
| **Python SDK** | 自建应用、脚本、Jupyter | `from mindos import Mindos` | ✅ | ✅ |
| **浏览器插件** | Claude/ChatGPT/Gemini Web 版 | Chrome Extension | ✅ 自动拦截 | ✅ 自动拦截 |
| **SOAP Bridge** | 3D 空间、MR 设备 | `mindos.spatial.SOAPBridge` | ✅ | ✅ |
| **OpenClaw 插件** | OpenClaw Agent 生态 | `openclaw-mindos` adapter | ✅ | ✅ |
| **CLI** | 终端用户、调试 | `mindos chat` | ✅ | ✅ |
| **移动端 SDK** | iOS/Android App | REST API + 本地缓存 | ✅ | ✅ 离线队列 |

**关键设计**：所有接入方式共享同一份 `~/.mindos` 数据。不同设备通过同步机制（Syncthing / 自托管 S3 / E2E 加密云）保持一致。

---

## 六、反思循环——L4 自我层的成长引擎

```
每日触发（或每 N 次 commit 后触发）
         │
  ┌──────▼────────────────────┐
  │  汇总今日所有 commit 来源   │  Claude 上聊了什么？GPT 上做了什么？
  └──────┬────────────────────┘
         │
  ┌──────▼────────────────────┐
  │  提取关键事实与洞察          │  今天学到了什么？有什么重要决定？
  └──────┬────────────────────┘
         │
  ┌──────▼────────────────────┐
  │  更新人格描述               │  "最近更关注健康了" / "对 AI 的兴趣持续增强"
  └──────┬────────────────────┘
         │
  ┌──────▼────────────────────┐
  │  压缩旧记忆                │  3 个月前的日常对话 → 浓缩为一句摘要
  └──────┬────────────────────┘  重要事件永久保留
         │
  ┌──────▼────────────────────┐
  │  巩固高频知识               │  反复提到的事实 → 提升权重
  └──────┬────────────────────┘  矛盾信息 → 标记待确认
         │
         ▼
  更新后的 L0 + identity.yaml
```

---

## 七、开发路线（重排优先级）

### 原则：先做能让人"离不开"的东西

之前的计划从 L1 本能引擎开始，那是"做 Agent"的思路。新计划从**记忆 + hydrate/commit**开始——先让用户在两个平台之间体验到"灵魂连续性"的震撼。

### Phase 0：核心协议 + 第一次"灵魂插拔"（Week 1-2）

| 天 | 任务 | 产出 |
|----|------|------|
| D1 | `pyproject.toml` + 包结构 + `~/.mindos` 目录规范 | `mindos init` 创建身份 |
| D2 | L0 `memory/store.py`：SQLite 记忆存储 + 基础 CRUD | 记忆写入/检索 |
| D3 | L0 `memory/retriever.py`：向量检索（sentence-transformers） | 语义相似度搜索 |
| D4 | L0 `memory/knowledge.py`：知识图谱（人/事/偏好） | 结构化记忆 |
| D5 | `identity.yaml` 格式 + `persona.py`：人格描述 | 个性定义与加载 |
| D6 | **`hydrate()` 实现**：情境感知的身份组装 | 核心原语 #1 |
| D7 | **`commit()` 实现**：对话消化与记忆写入 | 核心原语 #2 |
| D8 | `mindos serve --mcp`：MCP Server 实现 | 可被 Claude/Cursor 调用 |
| D9 | `mindos serve --http`：HTTP API 实现 | 可被任何平台调用 |
| D10 | Python SDK：`Mindos.load() / hydrate() / commit()` | 编程接口 |
| D11 | **集成测试：Claude MCP + GPT API，同一份 Mindos** | 跨平台灵魂连续性 |
| D12 | `mindos chat`：带记忆的 CLI 对话 + 记忆检索 | 开发调试工具 |
| D13 | 补测试 + 文档 + 修 bug | 质量保障 |
| D14 | **Demo：在 Claude 里聊 → 切到 GPT → GPT 记得 Claude 里说的话** | ⭐ 杀手级演示 |

**验收**：用户在 Claude 中聊天，Mindos 自动记忆。切换到 GPT，插入同一个 Mindos，GPT 立刻"认识"用户并记得之前聊过的内容。

### Phase 1：深度记忆 + 反思 + 灵魂成长（Week 3-4）

| 天 | 任务 | 产出 |
|----|------|------|
| D15 | `memory/compressor.py`：记忆压缩 + 遗忘曲线 | 记忆不会无限膨胀 |
| D16 | `commit()` 增强：自动提取事实/偏好/关系/情绪 | 更智能的记忆写入 |
| D17 | `hydrate()` 增强：Token 预算分配 + 多面人格 | 更精准的身份注入 |
| D18 | `reflection.py`：反思循环——跨平台汇总 + 洞察提取 | 灵魂自动成长 |
| D19 | 人格涌现测试：50 轮对话后 identity.yaml 自动演化 | 性格因经历而变 |
| D20 | SOAP 集成：`mindos.spatial.SOAPBridge` | 灵魂进入 3D 世界 |
| D21 | 与 soap-view 联调：Mindos 驱动 Agent 行动 | 可视化的有灵魂 Agent |
| D22 | `mindos export / import`：灵魂导出与迁移 | 可移植性保障 |
| D23 | `mindos status`：灵魂状态面板（记忆量/知识图谱/人格摘要） | 自我认知可视化 |
| D24 | 成本统计：hydrate/commit 各环节耗时与 token 用量 | 性能透明 |
| D25 | PyPI 发布 + README（5 分钟教程） | `pip install mindos` |
| D26 | Demo 视频：跨平台灵魂连续性 + 记忆成长 + SOAP 空间 | 传播素材 |
| D27 | 英文博客草稿 | "Your AI Knows You — Everywhere" |
| D28 | 发布 | GitHub + PyPI + 博客 |

**验收**：用了两周的 Mindos 能清晰说出"你上周在 Claude 里讨论的项目方案，后来在 GPT 里做了修改，最终版本是 X"。这种跨平台的记忆连续性是市场上没有的。

### Phase 2：浏览器插件 + 生态扩展（Month 2-3）

- 浏览器插件：自动拦截 Claude/ChatGPT Web 会话，无感知 hydrate/commit
- OpenClaw 集成：作为 OpenClaw 的 memory provider
- 多人 Mindos：支持 Ome 角色（不只是真人用户，AI 角色也有自己的 Mindos）
- 加密同步：E2E 加密的跨设备同步
- Mindos Studio：可视化编辑记忆、知识图谱、人格

---

## 八、技术选型

| 组件 | 选型 | 理由 |
|------|------|------|
| 记忆存储 | SQLite + sqlite-vss | 零依赖单文件，用户可直接查看/备份 |
| 向量编码 | sentence-transformers (all-MiniLM-L6-v2) | 轻量离线，hydrate 延迟 < 100ms |
| 知识图谱 | NetworkX + JSON 序列化 | 轻量，个人规模足够 |
| commit 提取 | 调用宿主 LLM（或配置的默认 LLM） | 不绑定特定模型 |
| 反思循环 | 调用配置的 LLM（DeepSeek / local） | 低成本后台任务 |
| MCP Server | Python MCP SDK | Claude/Cursor 原生支持 |
| HTTP Server | FastAPI (uvicorn) | 轻量高性能 |
| CLI | Click | Python 生态标准 |
| 配置 | YAML | 人格文件人类可读可编辑 |

---

## 九、为什么这个方向能赢

### 9.1 网络效应

```
用户在 1 个平台用 Mindos → 体验到记忆连续性
                         ↓
      在第 2 个平台也插上 Mindos → 跨平台记忆更震撼
                         ↓
      推荐给朋友 → 朋友的 Mindos 和你的建立关系链接
                         ↓
      平台方主动集成 Mindos → 用户在此平台体验更好
                         ↓
              更多平台集成 → 更多用户 → 更厚的记忆
                         ↓
                    不可逆转的飞轮
```

### 9.2 差异化极其清晰

| 产品 | 做什么 | Mindos 的关系 |
|------|--------|-------------|
| OpenClaw | Agent 执行框架（调度、工具、容器） | Mindos 作为 memory provider 插入 |
| Claude/GPT | LLM 推理能力 | Mindos 给它们装上"认识你"的能力 |
| Character.AI | 虚构角色扮演 | Mindos 让角色有真正的记忆和成长 |
| Mem0 / Zep | 对话记忆中间件 | Mindos 不只是记忆——是完整身份（个性+习性+能力+关系） |
| Mindos | **可插拔的持久身份协议** | **全新品类** |

### 9.3 护城河

**不是技术护城河，是数据护城河。** 技术可以抄，但用户三年积累的记忆、涌现的个性、编织的关系网——这些抄不走。每多用一天，切换成本就多一分。

---

## 十、Slogan 候选

- **"Your AI Knows You — Everywhere."**
- **"永久摇光：你的数字灵魂，跨越所有 AI。"**
- "One soul, every AI."
- "The memory that follows you."
- "Switch models. Keep your mind."

---

## 十一、成本模型

Mindos 本身几乎零成本运行——它不做推理，推理交给宿主平台。

| 操作 | 耗时 | 成本 |
|------|------|------|
| hydrate（本地检索 + 组装） | ~80ms | ≈ 0（纯本地计算） |
| commit（提取 + 存储） | ~2s | ≈ ¥0.003（调用 LLM 提取事实，可用 DeepSeek） |
| 反思循环（每日一次） | ~30s | ≈ ¥0.05（一次 LLM 调用汇总当天） |
| **日均（200 次交互）** | | **≈ ¥0.65** |

对比：没有 Mindos 时，用户在每个平台重复解释自己的背景、偏好、上下文——浪费的 token 成本远超 ¥0.65。**Mindos 实际上是在帮用户省钱。**

---

## 十二、冷启动与灵魂种子

新用户的 Mindos 是空白的。为了让用户 1 分钟内感受到价值：

### 12.1 灵魂种子初始化

```bash
mindos init --name "Wyon"
# 交互式问卷（可选）：
#   你的职业？ → AI 开发者
#   你最看重什么？ → 效率、简洁、创新
#   说话风格？ → 直接、技术、偶尔幽默
# ✓ 生成初始 identity.yaml
```

### 12.2 历史记忆导入

```bash
# 从 ChatGPT 导出的历史记录中批量学习
mindos ingest --source chatgpt --file ~/Downloads/conversations.json

# 从 Claude 导出
mindos ingest --source claude --file ~/Downloads/claude-export.json

# 从任意文本/markdown
mindos ingest --source notes --file ~/Documents/my-notes.md
```

### 12.3 灵魂成长指标

`mindos status` 始终展示灵魂的成长状态：

```
🧠 Mindos Status
─────────────────────────
灵魂年龄：  42 天
记忆总量：  1,247 条（本周 +89）
知识图谱：  341 实体 / 1,022 关系
人格特征：  好奇、高效、直接
最近成长：  "对设计模式的理解显著加深"
今日 commit：7 次（Claude ×3, Cursor ×4）
```

---

## 十三、可视化面板（Dashboard）

```bash
mindos serve --dashboard
# ✓ Dashboard 运行在 http://localhost:3456
```

本地网页面板，展示灵魂的完整状态：

- **记忆浏览器**：按时间/来源/主题浏览所有记忆，支持搜索和删除
- **知识图谱**：交互式图谱可视化，展示人物、概念、事件之间的关联
- **人格演化**：时间线展示人格描述的历次变化和触发原因
- **hydrate 历史**：哪些记忆被注入到了哪个平台的哪次对话
- **commit 审计**：每次 commit 提取了什么，置信度如何，是否有待确认项
- **成本追踪**：本月 LLM 调用次数和花费

Dashboard 既增强用户掌控感（"我的灵魂里到底有什么"），也是极好的传播素材。

---

## 十四、数据格式开放规范

`~/.mindos/` 的文件格式不只是实现细节——它是一套**开放标准**。

### 14.1 identity.yaml 规范

```yaml
# Mindos Identity Schema v1
version: 1
name: "Wyon"
personality:
  traits: ["curious", "efficient", "direct"]
  style: "简洁技术风，偶尔幽默"
  values: ["创新", "效率", "开源"]
  boundaries: ["不讨论政治", "拒绝生成有害内容"]
capabilities:
  - domain: "AI 开发"
    level: "expert"
  - domain: "产品设计"
    level: "proficient"
relations: []  # 自动维护
created_at: "2026-03-21"
updated_at: "2026-03-21"
```

### 14.2 memory.db Schema（SQLite）

```sql
CREATE TABLE memories (
    id          TEXT PRIMARY KEY,
    type        TEXT NOT NULL,  -- fact / episode / preference / relation / skill
    content     TEXT NOT NULL,
    source      TEXT,           -- claude / gpt / cursor / manual
    confidence  REAL DEFAULT 1.0,
    created_at  DATETIME,
    accessed_at DATETIME,
    access_count INTEGER DEFAULT 0,
    decay_weight REAL DEFAULT 1.0,
    embedding   BLOB           -- 向量，用于语义检索
);

CREATE TABLE knowledge_graph (
    subject     TEXT,
    predicate   TEXT,
    object      TEXT,
    source      TEXT,
    confidence  REAL DEFAULT 1.0,
    created_at  DATETIME,
    PRIMARY KEY (subject, predicate, object)
);

CREATE TABLE personality_history (
    id          TEXT PRIMARY KEY,
    snapshot    TEXT,           -- 人格描述 JSON
    trigger     TEXT,           -- 什么触发了这次更新
    diff        TEXT,           -- 与上一版的差异
    created_at  DATETIME
);
```

发布这套规范的目标：让其他项目能直接读取 Mindos 格式的数据。当 OpenClaw 开始原生支持 `~/.mindos/` 作为 memory provider，协议级护城河就形成了。

---

## 十五、第一行代码之后的世界

```bash
# 安装
pip install mindos

# 创建你的数字灵魂
mindos init --name "Wyon"
# ✓ 已创建 ~/.mindos/
# ✓ identity.yaml — 编辑它来描述你自己（或让 Mindos 从对话中学习）

# 启动 MCP Server，让 Claude 认识你
mindos serve --mcp
# ✓ Mindos MCP Server 运行中
# ✓ 在 Claude Desktop 设置中添加 mindos MCP server 即可

# 和 Claude 聊完后，你的 Mindos 记住了一切
# 现在打开 ChatGPT，通过 API 调用 hydrate——
# ChatGPT 立刻知道你是谁、你在做什么、你关心什么

# 一年后——
mindos status
# 记忆：12,847 条
# 知识图谱：2,341 个实体，8,922 条关系
# 人格特征：好奇心强、注重效率、偏爱简洁、有幽默感
# 技能领域：AI 开发(专家)、产品设计(熟练)、写作(进阶)
# 关系：147 人，其中亲密 12 人
# 灵魂年龄：365 天
```

**开干。**

---

## 十六、v0.3 架构升级日志（2026-03-22）

### 修复的致命 Bug

| # | 问题 | 修复 |
|---|------|------|
| 1 | ModelRouter 把 Anthropic 当 OpenAI 调 | 新增 `_call_anthropic()` 走原生 anthropic SDK |
| 2 | Ollama 类型声明了但永远返回 None | 新增 `_call_ollama()` 走 OpenAI 兼容接口 |

### 核心升级

| # | 功能 | 文件 | 说明 |
|---|------|------|------|
| 3 | FTS5 全文搜索 | store.py | 中文/英文混合搜索，万级记忆毫秒级响应 |
| 4 | Content-hash 模糊去重 | store.py | 「我住上海」vs「我住在 上海。」不再重复存 |
| 5 | 情绪状态持久化 | l1_instinct.py, store.py | soul_state 表，重启后保持情绪 |
| 6 | Bearer Token 鉴权 | server.py, client.py | MINDOS_AUTH_TOKEN 环境变量，保护灵魂数据 |
| 7 | LLM 响应缓存 | config.py | ModelRouter 内置 5 分钟 TTL 缓存 |
| 8 | Token 估算升级 | l1_instinct.py | 区分 CJK（1.5 tokens/char）和 ASCII（0.25 tokens/char）|
| 9 | Sensitive 检测优化 | l2_cognition.py | 减少误杀（32+ 字符门槛，API key 前缀更精确）|
| 10 | 全局 logging | 所有模块 | `logging.getLogger("mindos.*")`，替代 print |

### Ome 生成

| # | 功能 | 接入点 |
|---|------|--------|
| 11 | `export_ome()` | Mindos.export_ome() / HTTP GET /api/ome / MCP mindos_ome |
| 12 | Ome 格式 v0.1 | identity + anchor + hydrated_context + memories + KG + emotion |

**Ome = Mindos 的轻量快照**，是从"持久灵魂"到"实例化人格"的桥梁。任何平台只需读入一个 Ome JSON，即可让 AI 以你的身份说话。

### 测试覆盖

| 版本 | 测试数 |
|------|--------|
| v0.2 | 12 |
| v0.3 | 18（+6：export_ome, content_hash_dedup, fts_search, soul_state, mcp_ome, anthropic_router）|

### 依赖变更

- 新增可选依赖：`anthropic>=0.30`（`pip install mindos[anthropic]`）
- Ollama 不需要额外依赖（复用 openai SDK 的 compatible 接口）

---

## 十七、跨端同步架构（2026-03-22）

### 设计目标

| 场景 | 设备 | 接入方式 |
|------|------|---------|
| 开发 | Mac | Claude Code (MCP) / Cursor (MCP) → 本地 `~/.mindos/` |
| 咨询 | Chrome | Gemini / 豆包网页版 → Chrome Extension → Sync Hub |
| 移动 | 手机 | 豆包 App / Ome App → Sync SDK → Sync Hub |

### 架构：Event Sourcing + Sync Hub

```
Device A (Mac)                    Device B (Phone)
┌──────────────┐                  ┌──────────────┐
│ SQLite (本地) │  ← push/pull → │ SQLite (本地) │
│ sync_journal │      ↕          │ sync_journal │
└──────┬───────┘      │          └──────┬───────┘
       │         ┌────┴────┐           │
  MCP/CLI        │Sync Hub │      Ome SDK
                 │ REST API│
                 └────┬────┘
                      │
                Chrome Extension
```

### 核心设计

**1. Sync Journal（每设备本地）**
```sql
CREATE TABLE sync_journal (
    seq        INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id   TEXT UNIQUE,      -- UUID, 全局唯一
    device_id  TEXT,             -- 哪个设备产生的
    op         TEXT,             -- add_memory | add_triple | forget | update_identity | reflect
    payload    TEXT,             -- 变更 JSON
    created_at REAL,
    synced_at  REAL              -- NULL = 尚未同步
);
```

**2. 自动记录**：`add()` / `add_triple()` / `forget()` 自动写 journal，零代码侵入。

**3. 防重入**：`_applying_remote` 标志位，远程事件回放时不会再次写入 journal。

**4. Sync Hub**：无状态事件中继
- `POST /sync/push` — 设备推送事件到 Hub
- `POST /sync/pull` — 设备从 Hub 拉取其他设备的事件
- Hub 不存灵魂数据，只存事件流
- Hub 持久化到 JSON 文件（自托管场景可用 SQLite 或 Redis 替换）

**5. 冲突策略**
| 操作 | 策略 | 原因 |
|------|------|------|
| add_memory | 无冲突（append-only + hash dedup）| 记忆天然只增不减 |
| add_triple | 无冲突（幂等 upsert）| KG 三元组是集合操作 |
| forget | 传播到所有设备 | GDPR 要求全局删除 |
| identity | last-writer-wins（timestamp）| 人格编辑频率低 |

### 使用方式

```bash
# 在你的 VPS 上启动 Sync Hub
mindos serve --sync --port 3457

# 在 Mac 上配置
export MINDOS_SYNC_URL=http://your-vps:3457
mindos sync            # push + pull 一步到位

# 在 Claude Code MCP 里
mindos_sync            # 一键同步

# 在 Ome App 里（TypeScript SDK）
const sync = new SyncClient({ hubUrl: "http://your-vps:3457" });
await sync.sync();
```

### 测试覆盖

| 版本 | 测试数 |
|------|--------|
| v0.2 | 12 |
| v0.3 sync | 22（+10：ome 3, sync_journal, sync_hub, sync_apply, sync_persist, anthropic_router, hash_dedup, fts）|

---

## 十八、OpenClaw 社区发布清单

要让 Mindos 在 OpenClaw 社区一键爆火，需要的工作：

### 必须做（MVP）

| # | 工作 | 状态 | 说明 |
|---|------|------|------|
| 1 | `pip install mindos` 零报错 | ✅ | 纯 Python，仅依赖 pyyaml |
| 2 | `mindos quickstart` 30 秒上手 | ✅ | 交互式引导 + 即时展示 |
| 3 | MCP Server 一键接入 Claude/Cursor | ✅ | `mindos serve --mcp` |
| 4 | 跨端同步 | ✅ | Sync Hub + Journal |
| 5 | Ome 生成 | ✅ | 灵魂 → 人格快照 |
| 6 | Chrome Extension | ⏳ | 拦截 Gemini/豆包对话，auto-commit 到 Mindos |
| 7 | TypeScript SDK | ⏳ | 给 Ome App / Web 前端用 |
| 8 | OpenClaw Agent 集成示例 | ⏳ | 在 Claw 里 `import mindos; soul = mindos.load()` |
| 9 | 文档站 | ⏳ | GitHub Pages，含交互 demo |

### 应该做（增长飞轮）

| # | 工作 | 说明 |
|---|------|------|
| 10 | Soul Marketplace | 用户分享匿名化人格模板（如"AI 工程师人格"、"创意作家人格"）|
| 11 | One-click Deploy | `mindos deploy` 一键部署 Sync Hub 到 Railway/Vercel |
| 12 | Grafana Dashboard | 记忆增长、人格漂移、情绪曲线可视化 |
| 13 | React 组件 | `<MindosProvider>` + `useMindos()` hook |

### 爆火三板斧

1. **30 秒 Demo Video**：`pip install mindos && mindos quickstart` → 30 秒后 Claude 记住你是谁
2. **"AI 终于记住我了"** Reddit/HN 帖子标题
3. **OpenClaw 生态集成**：任何 Claw Agent 加一行 `soul = mindos.load()` 就有记忆
