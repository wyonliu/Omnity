# Mindos 增强方案 v2

**v0.4 · 2026-03-22**
**基于源码审计的精准增强——只补真正缺的，不重复已有的**

---

## 零、当前真实能力基线（v0.3.0 审计结论）

Mindos v0.3 **不是** 半成品。4153 行代码，五层脑全部工作，8 个公共 API 方法全部端到端可用。以下已经能跑：

| 能力 | 实现文件 | 状态 |
|------|---------|------|
| 五层脑架构（L0-L4） | layers/*.py | ✅ 生产可用 |
| SQLite + FTS5 全文搜索 | store.py (646行) | ✅ 生产可用 |
| 内容去重（bigram Jaccard） | store.py | ✅ 生产可用 |
| 向量搜索（numpy cosine） | store.py | ✅ 可选依赖 |
| L1 请求分类路由 | l1_instinct.py classify_request() | ✅ 正则匹配 |
| L2 对话抽取（LLM+规则双路） | l2_cognition.py | ✅ 生产可用 |
| L3 推理+规划 | l3_decision.py reason()/plan() | ✅ 需LLM |
| L4 反思+性格漂移 | l4_self.py reflect() | ✅ LLM+启发式双路 |
| 情感状态（昼夜节律能量衰减） | l1_instinct.py EmotionState | ✅ 持久化 |
| HTTP Server（17个端点+认证） | server.py (426行) | ✅ 生产可用 |
| MCP Server（8 tools + 3 resources） | mcp_server.py (371行) | ✅ 生产可用 |
| 跨设备同步（Hub+Client） | sync.py (371行) | ✅ 生产可用 |
| LLM 多供应商路由+缓存 | config.py (311行) | ✅ 生产可用 |
| CLI（13个命令） | cli.py (479行) | ✅ 生产可用 |
| Ome 导出（便携人格包） | core.py export_ome() | ✅ 生产可用 |

**结论：骨架完整，缺的是「肌肉」——让 Mindos 从"能用"变成"不可替代"的增强能力。**

---

## 一、六大核心增强（P0，必须做）

### 1.1 统一请求入口 process()

**现状**：L1 的 `classify_request()` 存在且能分类，但 LayerRouter 没有 `process()` 统一入口——外部调用者（Ome、HTTP Server）仍需自己判断该调哪个方法。

**方案**：在 `router.py` 新增 `process(text, **kwargs)` 方法：

```python
class LayerRouter:
    def process(self, text: str, **kwargs) -> dict:
        """统一请求入口——L1 分类后自动分发。

        这是 Ome 和所有外部系统调用 Mindos 的首选入口。
        90% 请求在 L1/L2 解决，< 10% 升级到 L3/L4。
        """
        level = self.l1.classify_request(text)

        if level == "l1":
            return {
                "response": self.l1.quick_reply(text),
                "layer": "l1",
                "cost": 0,
            }
        elif level == "l2":
            identity = self.hydrate(text)
            memories = self.recall(text, top_k=5)
            memory_ctx = "\n".join(f"- {m['content']}" for m in memories)
            response = self.l2.router.call_llm(
                task="chat", system=identity,
                user=f"Context:\n{memory_ctx}\n\nUser: {text}",
            )
            return {"response": response, "layer": "l2"}
        elif level == "l3":
            return {
                "response": self.reason(text),
                "layer": "l3",
            }
        else:  # l4
            reflection = self.reflect()
            return {
                "response": reflection.get("summary", "Reflection complete.") if reflection else "No reflection needed.",
                "layer": "l4",
            }
```

同时在 L1 新增 `quick_reply(text)` —— 对简单查询零 LLM 成本返回：

```python
class Brainstem:
    def quick_reply(self, text: str) -> str:
        """L1 零成本快速回复：状态查询、简单问候、记忆检索。"""
        text_lower = text.lower()

        # 问候
        if re.match(r"^(hi|hello|hey|你好|嗨)", text_lower):
            name = self.identity.get("name", "")
            return f"你好{name}！有什么我能帮你的？"

        # 感谢
        if re.match(r"^(thanks|谢谢|ok|好的)", text_lower):
            return "不客气！随时找我。"

        # 状态查询
        if "status" in text_lower or "状态" in text_lower:
            stats = self.hippocampus.stats()
            return f"记忆 {stats.get('total', 0)} 条，知识图谱 {stats.get('kg_triples', 0)} 条关系。"

        # 记忆检索
        if "记得" in text or "remember" in text_lower:
            memories = self.hippocampus.recall(text, top_k=3)
            if memories:
                return "\n".join(f"- {m.content}" for m in memories)
            return "关于这个我还没有记忆。"

        return f"[L1] {text}"
```

**HTTP Server 新增端点**：`POST /api/process` —— 所有外部系统的首选入口。

### 1.2 L4 反思写回 identity

**现状**：`l4_self.py reflect()` 会检测性格漂移并记录到 `personality_history`，但 **不会写回 identity.yaml**。也就是说"性格从经历中涌现"这个核心承诺实际不工作。

**方案**：在 `reflect()` 末尾增加写回逻辑：

```python
class Self:
    def reflect(self) -> dict:
        result = self._reflect_llm() or self._reflect_heuristic()

        # 新增：将涌现的性格变化写回 identity
        if result and result.get("trait_updates"):
            self._apply_trait_updates(result["trait_updates"])
        if result and result.get("style_updates"):
            self._apply_style_updates(result["style_updates"])

        self.store.record_personality(result)
        return result

    def _apply_trait_updates(self, updates: list[str]):
        """安全更新 traits：只追加/微调，不删除用户手动设定的锚点。

        规则：
        1. 用户在 identity.yaml 手动写的 traits 是「锚点」，永远不删
        2. 涌现的新 trait 追加到尾部
        3. 如果与锚点矛盾，以锚点为准
        """
        anchors = self.identity.get("personality", {}).get("anchors", [])
        current = self.identity.get("personality", {}).get("traits", [])

        for trait in updates:
            if trait not in current and not self._contradicts_anchors(trait, anchors):
                current.append(trait)

        # 最多保留 15 个 traits
        self.identity.setdefault("personality", {})["traits"] = current[:15]
```

**关键**：新增 `anchors` 字段到 identity.yaml，用户设定的 3-5 条核心原则不可被反思覆写。

### 1.3 Memory 自动生成 embedding

**现状**：store.py 支持向量搜索（numpy cosine），但 `commit()` 时 **不会自动生成 embedding**——记忆存进去没有向量，语义搜索永远靠 FTS5 文本匹配。

**方案**：在 `core.py commit()` 流程中自动 embed：

```python
class Mindos:
    def commit(self, conversation: str, source: str = "unknown") -> dict:
        result = self.layers.commit(conversation, source=source)

        # 自动为新记忆生成 embedding
        if self._can_embed():
            for fact in result.get("facts", []):
                self._embed_and_store(fact)

        return result

    def _can_embed(self) -> bool:
        """检查是否有可用的 embedding 能力。"""
        # 优先 sentence-transformers（本地），其次 OpenAI embeddings API
        return self._embed_model is not None or self._embed_api is not None

    def _embed_and_store(self, content: str):
        """生成 embedding 并存储。"""
        try:
            if self._embed_model:
                vec = self._embed_model.encode(content)
            else:
                vec = self._embed_api(content)
            # 找到对应的 memory 并更新
            memories = self.store.search(content, limit=1)
            if memories:
                self.store.update_embedding(memories[0].id, vec.tolist())
        except Exception as e:
            log.debug("Embedding failed: %s", e)
```

**三种 embedding 来源（优先级递降）**：
1. `sentence-transformers`（本地，零成本，~50ms/条）
2. OpenAI `text-embedding-3-small`（API，¥0.001/条）
3. Ollama `nomic-embed-text`（本地，零成本）

config.yaml 新增 `embedding` 配置节：
```yaml
embedding:
  provider: local  # local / openai / ollama
  model: all-MiniLM-L6-v2  # sentence-transformers model name
```

### 1.4 EventBus 事件总线

**现状**：各层之间是直接函数调用，没有事件系统。L2 commit 后 L4 要反思得靠计数器轮询。外部系统（Ome）无法订阅 Mindos 内部事件。

**方案**：新增 `event_bus.py`：

```python
class EventBus:
    """Mindos 内部事件总线——连接各层 + 外部系统。"""

    def __init__(self):
        self._handlers: dict[str, list[Callable]] = defaultdict(list)

    def on(self, event_type: str, handler: Callable):
        """注册事件处理器。"""
        self._handlers[event_type].append(handler)

    def emit(self, event_type: str, data: dict):
        """发布事件，所有注册的 handler 同步处理。"""
        for handler in self._handlers.get(event_type, []):
            try:
                handler(data)
            except Exception as e:
                log.warning("Event handler failed: %s", e)

    # 内置事件类型
    MEMORY_COMMITTED = "memory.committed"      # 新记忆写入
    REFLECT_COMPLETED = "reflect.completed"    # 反思完成
    PERSONALITY_CHANGED = "personality.changed" # 人格更新
    CONTRADICTION_DETECTED = "contradiction.detected"  # 矛盾发现
    INSIGHT_GENERATED = "insight.generated"    # 洞察生成
    COMMIT_BATCH = "commit.batch"              # 攒够一批 commit
```

**接入点**：
- `commit()` 完成后 emit `MEMORY_COMMITTED`
- `reflect()` 完成后 emit `REFLECT_COMPLETED`
- L2 发现矛盾事实时 emit `CONTRADICTION_DETECTED`
- Ome 的 AutonomyEngine 订阅这些事件，替代 tick() 轮询

### 1.5 Scheduler 定时任务引擎

**现状**：零主动能力。不会自动反思、不会自动压缩、不会自动推送洞察。

**方案**：新增 `scheduler.py`：

```python
class MindosScheduler:
    """后台定时任务引擎。轻量级，不依赖 celery/cron。"""

    JOBS = [
        {"name": "daily_reflect",    "interval_hours": 24, "fn": "reflect"},
        {"name": "memory_compress",  "interval_hours": 72, "fn": "compress_old"},
        {"name": "daily_digest",     "interval_hours": 24, "fn": "daily_digest"},
        {"name": "weekly_insight",   "interval_hours": 168, "fn": "weekly_report"},
        {"name": "stale_cleanup",    "interval_hours": 168, "fn": "decay_stale"},
    ]

    def __init__(self, mindos: Mindos, event_bus: EventBus):
        self.mindos = mindos
        self.bus = event_bus
        self._last_run: dict[str, float] = {}

    def check_and_run(self):
        """检查所有任务，运行到期的。

        调用时机：Ome App 启动时 / HTTP Server 定期心跳 / CLI 手动触发。
        不需要后台进程——被动检查即可。
        """
        now = time.time()
        for job in self.JOBS:
            last = self._last_run.get(job["name"], 0)
            if now - last >= job["interval_hours"] * 3600:
                self._run_job(job)
                self._last_run[job["name"]] = now
```

**关键设计**：不启动后台线程/进程。每次 Ome 启动、HTTP 请求进来、或用户手动 `mindos maintenance` 时被动检查。

### 1.6 InsightEngine 洞察引擎

**现状**：零洞察能力。不会总结每天发生了什么，不会发现行为模式，不会检测矛盾记忆。

**方案**：新增 `insight.py`：

```python
class InsightEngine:
    """从记忆中提炼洞察——Ome 的"本周亮点"数据源。"""

    def daily_digest(self) -> str:
        """每日 21:00 可触发：汇总今天所有 commit → 3-5 条洞察。
        L1 级别（规则+统计），不需要 LLM。"""

    def weekly_reflection(self) -> str:
        """每周日：本周人格变化、知识增长、重要决策回顾。
        L2 级别（需要轻量 LLM 总结）。"""

    def contradiction_alert(self) -> list[str]:
        """发现矛盾记忆时提醒：
        '你上周说想减少咖啡，但本周记录了 4 次喝咖啡'。
        L1 级别（事实对比）。"""

    def pattern_discovery(self) -> list[str]:
        """发现行为模式：
        '你最近三周每周五下午 3 点都会讨论项目进度'。
        L1 级别（时间+主题聚类）。"""
```

### 1.7 MemoryCompressor 记忆压缩

**现状**：`consolidate()` 只做去重，不做压缩。老记忆无限堆积，recall 会越来越慢。

**方案**：新增到 store.py：

```python
class MemoryCompressor:
    def compress_old_episodes(self, older_than_days: int = 90):
        """3 个月前的日常对话 → 浓缩为一句摘要。
        高 confidence 或高 access_count 的记忆永久保留。"""

    def merge_redundant_facts(self):
        """重复事实合并："喜欢咖啡"出现 5 次 → 合并为一条，权重提升。"""

    def archive_stale(self):
        """长期未访问 + 低重要性 → 标记 archived（不删除，不参与默认检索）。"""
```

---

## 二、系统级集成（P0-P1，让 Mindos "无处不在"）

### 2.1 搜狗输入法模式——系统级常驻

**爸爸的原话**：Mindos 能不能做个类似搜狗输入法的插件，系统级获得用户授权？

这是一个绝妙的类比。搜狗输入法的核心价值：
- **永远在线**：只要你打字，它就在
- **跨应用**：在任何 App 里都能用
- **越用越懂你**：学你的词频、联想你的习惯
- **零感知成本**：用户不用"打开"它

**Mindos 的搜狗模式实现方案**：

#### 2.1.1 系统托盘守护进程（P0）

```
Mindos 系统托盘 🧠
  ├─ 状态：运行中 · 1,247 条记忆 · 精力 87%
  ├─ ⌘⇧M → 弹出快速 recall 面板（类 Spotlight）
  ├─ ⌘⇧C → 将剪贴板内容 commit 到 Mindos
  ├─ ⌘⇧H → 注入身份到当前 App 的输入框
  ├─ 今日洞察（InsightEngine daily_digest）
  ├─ 设置
  └─ 退出
```

技术方案：
- **macOS**: Swift MenuBarExtra + NSAppleEventManager（获取前台App信息）
- **Windows**: C# System.Windows.Forms.NotifyIcon
- **跨平台**: Tauri 2 系统托盘 API（与 Ome Desktop App 共享进程）
- **轻量方案**: Python pystray + rumps（先跑通再美化）

#### 2.1.2 浏览器扩展（P0）

```
用户打开 Claude / ChatGPT / Gemini 网页
  → 扩展检测到 AI 对话页面
  → 自动调用 Mindos HTTP: hydrate(context="claude chat")
  → 将身份上下文注入对话（system prompt 前缀 / 首条消息）
  → 用户正常聊天
  → 对话结束时，扩展自动调用 commit(conversation)
  → 记忆无感同步到 Mindos
```

技术方案：Chrome Extension Manifest V3
- content_script：检测 `.chat-message` 等 DOM 元素
- background service worker：与本地 Mindos HTTP Server 通信
- popup：显示当前对话的记忆命中数 + 一键 commit

**核心价值**：用户在 Claude 里聊完项目需求 → 切到 Cursor 写代码 → Mindos 自动把需求上下文带过来。**这就是"不被遗忘的 AI 时代工作"。**

#### 2.1.3 Spotlight / Raycast 插件（P1）

```
[⌘ Space] "上周和张总聊了什么"
  → Mindos recall("上周和张总聊了什么")
  → 展示匹配记忆列表
  → 点击可复制 / 展开详情
```

#### 2.1.4 IDE 扩展（P1）

VS Code / Cursor 扩展（不通过 MCP，作为侧边栏插件）：
- 自动识别当前项目上下文 → hydrate
- 代码评审时带入编码偏好和历史决策
- 侧边栏显示相关记忆
- `@mindos` 在编辑器内直接 recall

#### 2.1.5 移动端键盘扩展（P2）

类似搜狗输入法的系统键盘层：
- 输入时可快速调用 `@recall` 查询记忆
- 长按空格 → 弹出 Mindos 快捷面板

---

## 三、新增核心能力

### 3.1 多模态记忆

```python
class MultiModalMemory:
    def commit_image(self, image_path: str, description: str = ""):
        """图片 → LLM Vision 自动描述 → 事实抽取 → 存储。"""

    def commit_voice(self, audio_path: str):
        """语音 → Whisper 转文字 → 事实抽取 → 存储。"""

    def commit_location(self, lat: float, lng: float, context: str):
        """位置记忆："在星巴克和张总聊了合作方案"。"""
```

### 3.2 L3 多步规划循环

**现状**：L3 有 `reason()` 和 `plan()` 但都是单轮 LLM 调用，不能多步执行。

```python
class Prefrontal:
    async def execute_plan(self, goal: str, tools: list, max_steps: int = 5) -> dict:
        """ReAct 循环：思考 → 行动 → 观察 → 再思考。

        这是 Ome skill-research / skill-schedule 的底层引擎。
        """
        plan = self.plan(goal)
        results = []
        for step in plan["steps"][:max_steps]:
            action = self._select_action(step, tools)
            observation = await self._execute_action(action)
            results.append({"step": step, "action": action, "result": observation})
            if self._goal_achieved(goal, results):
                break
        return {"goal": goal, "steps": results, "success": self._goal_achieved(goal, results)}
```

### 3.3 人格锚点存储

```yaml
# identity.yaml 新增字段
personality:
  anchors:  # 不可动摇锚点，L4 反思永远不会覆写
    - "说话简洁直接，不废话"
    - "绝不替用户做不可逆决策，必须确认"
    - "保护用户隐私，对外不暴露地址、财务、家庭信息"
  traits: [...]      # 可由 L4 反思演化
  style: "..."       # 可由 persona 导入更新
  catchphrases: []   # 来自 Ome PersonaEngine
  emoji_habits: []   # 来自 Ome PersonaEngine
```

### 3.4 OmeFactory

```python
class Mindos:
    def spawn_ome(self, **overrides) -> dict:
        """从灵魂生成 Ome 实例配置。

        支持 fork：基于同一个 Mindos 创建多个 Ome 分身，
        各自有独立的 bond/achievements 但共享记忆。
        """
```

---

## 四、开发优先级

### Phase 0：核心增强（3-5天）

| 任务 | 文件 | 估时 |
|------|------|------|
| process() 统一入口 + L1 quick_reply | router.py, l1_instinct.py | 3h |
| L4 反思写回 identity + 锚点存储 | l4_self.py, identity.yaml | 3h |
| EventBus 基础 | event_bus.py（新） | 3h |
| Scheduler 被动检查 | scheduler.py（新） | 3h |
| Memory 自动 embedding | core.py, store.py, config.yaml | 4h |
| InsightEngine（daily_digest + contradiction_alert） | insight.py（新） | 4h |
| MemoryCompressor（compress + archive） | store.py 扩展 | 3h |
| HTTP 新端点 /api/process + /api/insights | server.py | 2h |
| 测试更新 | test_soul.py | 3h |

### Phase 1：系统级集成（1-2周）

| 任务 | 交付物 |
|------|--------|
| 系统托盘守护进程 | macOS MenuBar + 全局快捷键 |
| Chrome 浏览器扩展 | Claude/ChatGPT 自动 hydrate/commit |
| Spotlight/Raycast 插件 | 系统搜索栏 recall |

### Phase 2：深度能力（2-3周）

| 任务 | 交付物 |
|------|--------|
| L3 多步规划 execute_plan() | ReAct 循环 |
| 多模态记忆 | 图片/语音/位置 |
| OmeFactory | spawn_ome() + fork |
| IDE 扩展 | VS Code/Cursor 侧边栏 |

---

## 五、与 Ome 的接口约定

Ome 通过以下接口与 Mindos 交互，绝不直接操作 SQLite：

| Ome 操作 | Mindos API | 说明 |
|---------|-----------|------|
| 用户聊天 | `POST /api/process` | **新统一入口**，自动路由到 L1-L4 |
| 注入身份 | `POST /api/hydrate` | 组装身份上下文 |
| 记忆存储 | `POST /api/commit` | 抽取事实并存储 |
| 浏览记忆 | `GET /api/memories` + `POST /api/recall` | 列表/搜索 |
| 成长报告 | `POST /api/reflect` + `GET /api/insights` | 反思 + 洞察 |
| 代社交审批 | `POST /api/process` | L3 规划回复 |
| 生命面板数据 | `GET /api/status` | 含 emotion, commits 计数 |
| Ome 养成指标 | `POST /api/ome` | export_ome 扩展 |
| 事件订阅 | `WebSocket /api/events` | **新**，EventBus 实时推送 |
| 定时维护 | `POST /api/maintenance` | **新**，触发 Scheduler 检查 |

---

## 六、"搜狗模式"的核心叙事

**用户安装 Mindos 后的体验**：

1. `pip install mindos && mindos init` → 2 分钟创建灵魂
2. 系统托盘出现 🧠 图标，Mindos 开始常驻
3. 打开 Claude → 浏览器扩展自动注入身份 → Claude 已经"认识你"
4. 切到 Cursor → MCP 自动连接 → 你在 Claude 里讨论的需求，Cursor 里直接知道
5. ⌘⇧M → 弹出搜索框 → "上周关于 API 设计的讨论" → 瞬间检索
6. ⌘⇧C → 选中邮件正文 → commit → Mindos 自动抽取关键信息存储
7. 晚上 21:00 → 托盘弹出今日洞察："今天你讨论了 3 个项目，最多时间花在 X 上"

**这就是"开发者一键开启不被遗忘的 AI 时代工作"。**

---

*Mindos 不是一个 App，它是空气——你感觉不到它，但它无处不在。*
