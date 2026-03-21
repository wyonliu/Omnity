# SOAP 开发工作日志

**项目**: Omnity / packages/soap — Spatial Omnity Agentic Protocol  
**时间线**: 2026-03-18 至 2026-03-21  
**协作方式**: 人类指挥 + Claude AI（Cursor Agent 模式）执行  
**许可**: Apache-2.0

---

## 一、项目背景与目标

**SOAP**（Spatial Omnity Agentic Protocol）是 Omnity monorepo 的基座层——"空间智能体时代的 HTTP"。目标是定义一套开放规范，让任意 AI Agent 用统一方式理解、查询与操作真实 3D 空间。

Omnity 整体分五个工作区（`packages/soap` → `mindos` → `ome` → `maxim` → `ometown`），SOAP 是地基，上层全部依赖它。底线是"下层没跑通，上层不开始"。

参考文件：
- `ometown_execution.md` — 365天作战手册
- `ometown_pitch.md` — 项目愿景
- `docs/soap/WORK_PLAN.md` — SOAP 分阶段任务
- `docs/soap/PROTOCOL_VISION_AND_EXECUTION.md` — 五层协议栈愿景

---

## 二、阶段 0：规范 v0.1 成文

### 产出

| 文件 | 说明 |
|------|------|
| `spec/SOAP-v0.1.md` | 首版规范草案：Spatial URI、SOAPScene 文档结构、ObjectInstance、SpatialRegion、AgentAction 动词（OBSERVE / NAVIGATE / MANIPULATE / REARRANGE）、虚实属性（physical / virtual / mixed）、错误形状 |
| `spec/schemas/scene.schema.json` | SOAPScene 根文档的 JSON Schema |
| `spec/schemas/object-instance.schema.json` | 物体实例 Schema |
| `spec/schemas/spatial-region.schema.json` | 空间区域 Schema |
| `spec/schemas/agent-action.schema.json` | Agent 动作 Schema |
| `spec/CHANGELOG.md` | 规范变更日志 |

### 设计决策
- **坐标系**: 右手系，Y轴向上，单位米——兼容 glTF / USD / 3DGS
- **Spatial URI**: `soap://{space_id}/{path...}` 格式的全局稳定标识
- **四个 Schema 交叉引用**: 通过 `$id` 和 `$ref` 实现模块化
- **动词子集而非自由文本**: OBSERVE / NAVIGATE / MANIPULATE / REARRANGE，保持互操作性
- **虚实标签**: `reality` 字段区分 physical / virtual / mixed，支撑混合现实场景

---

## 三、阶段 1：样例与校验

### 产出

| 文件 | 说明 |
|------|------|
| `examples/minimal-scene.json` | 最小合法场景（1个物体，1个区域）|
| `examples/mall-mixed-reality.json` | **"活商场"完整思想实验场景**: 17个物体、5个区域、6种角色视角。包含物理柱子、AR喷泉、MR游戏传送门/怪物、NPC店员/咖啡师、配送/清洁机器人、智能屏等 |
| `examples/sample-action-observe.json` | OBSERVE 动作样例 |
| `src/omnity_soap/validate.py` | JSON Schema 校验器，支持交叉引用解析 |
| `src/omnity_soap/cli.py` | `soap-validate` CLI 入口 |

### mall-mixed-reality.json 场景架构
- **space_id**: `mall_01`
- **5个区域**: 中庭(atrium)、102号店铺(store_102)、二楼咖啡店(cafe_201)、后场服务通道(service_lane)、线上虚拟商场(virtual_twin)
- **6种角色视角**: MR眼镜玩家、手机扫描用户、AI眼镜用户、具身智能机器人、线上虚拟NPC、MR+NPC融合
- **17个物体**: 横跨物理/虚拟/混合三种 reality，每个物体都有 affordances（可交互动作列表）和 bounds（AABB包围盒）

---

## 四、阶段 2：内存 Runtime

### 产出

| 文件 | 说明 |
|------|------|
| `src/omnity_soap/runtime.py` | `SOAPRuntime` 类：可变场景图 + 动作执行 + 事件日志 |
| `src/omnity_soap/paths.py` | 路径解析：`default_scene_path()`、`viewer_static_dir()`、`schema_dir()` |
| `tests/test_validate.py` | 校验单元测试 |
| `tests/test_runtime_actions.py` | Runtime 动作单元测试（11个测试用例）|

### SOAPRuntime 设计
初始版本是只读的（加载 + 查询），后来根据需求改为**可写/可变**：

1. **读取 API**: `summary()`, `list_objects()`, `get_object()`, `list_regions()`, `get_region()`, `get_events_since()`
2. **动作 API**:
   - `observe(agent_id, target_id)` → 返回目标物体/区域的感知摘要
   - `navigate(agent_id, object_id, target_uri)` → 移动物体到目标位置（更新 bounds）
   - `manipulate(agent_id, object_id, action, params)` → 执行 affordance 动作
   - `execute_action(agent_id, verb, target_id, params)` → 统一分发入口
3. **事件系统**: 线程安全的 `Event` + `ActionResult`，每次动作自动记录序列号和时间戳
4. **NPC 简单响应逻辑**: 根据物体类型和 state 生成上下文相关回复
5. **怪物 HP 系统**: attack_target 扣血、defeated 状态、drop_loot

### 测试覆盖
- OBSERVE 物体/区域/不存在目标
- NAVIGATE 移动物体、未知物体
- MANIPULATE speak（NPC对话）、attack_target（怪物战斗）、not_afforded（无效动作）
- 事件日志顺序性
- execute_action 统一分发（含 REARRANGE NOT_IMPLEMENTED）

---

## 五、阶段 3：soap-mcp MVP

### 产出

| 文件 | 说明 |
|------|------|
| `src/omnity_soap/mcp_server.py` | MCP Server：通过 FastMCP 向外部 Agent 暴露 SOAP 工具 |
| `soap-mcp/README.md` | MCP 配置文档 |

### MCP 工具列表

| 工具 | 类型 | 说明 |
|------|------|------|
| `soap_get_scene_summary` | READ | 场景元数据概览 |
| `soap_list_objects` | READ | 所有物体列表（含状态）|
| `soap_get_object` | READ | 单个物体详情 |
| `soap_list_regions` | READ | 所有区域列表 |
| `soap_observe` | ACTION | OBSERVE 目标 |
| `soap_navigate` | ACTION | NAVIGATE 移动物体 |
| `soap_manipulate` | ACTION | MANIPULATE 执行 affordance |
| `soap_get_events` | ACTION | 读取事件日志 |

---

## 六、阶段 3b：soap-view（可视化调试入口）

这是工作量最大的部分，经历了多次迭代。

### 6.1 初始架构

| 文件 | 说明 |
|------|------|
| `src/omnity_soap/viewer_server.py` | Python HTTP 服务器，提供 API 端点 + 静态文件 |
| `web/viewer/index.html` | 前端 HTML 入口 |
| `web/viewer/src/main.js` | 前端主逻辑 |
| `web/viewer/src/soap-layout.js` | SOAP 场景几何计算 |
| `web/viewer/src/pixel-mall.js` | Phaser 3 商场平面图渲染 |
| `web/viewer/src/style.css` | 补充样式 |
| `web/viewer/vite.config.js` | Vite 构建 + 开发代理 |
| `web/viewer/package.json` | 依赖：phaser, vis-data, vis-network, vite |

### 6.2 GenerativeAgentsCN 对标与分离

**背景**: 用户最初要求 1:1 复刻 GenerativeAgentsCN（x-glacier/GenerativeAgentsCN）的小镇回放 UI。

**尝试**:
- 编写 `scripts/sync-gacn-assets.sh`：浅克隆 GACN 仓库，同步 tilemap 资产
- 编写 `src/gacn-replay.js`：Phaser Scene 实现 GACN 回放逻辑（persona 动画、camera 控制、HUD）
- UI 壳层对齐：Bootstrap 3.4 + jQuery + `vendor/generative-agents-cn/style.css`

**问题与转折**:
1. 浏览器中文路径 404 → `viewer_server.py` 的 `do_GET` 未对 URL percent-encode 做 `unquote`。修复：`from urllib.parse import unquote`
2. **用户强烈反对自动加载 GACN 数据**："界面里全是2024年2月的项目数据，什么 the Ville 摩尔家族的房子，你直接 copy 过来而不是运行我们的数据？那有何用？！"
3. **架构决策转变**: 移除 GACN 自动挂载，SOAP 场景始终为默认。GACN 降级为 `?gacn=1` URL 参数可选模式

**最终状态**: `gacn-replay.js` 保留但不再自动加载。主视图始终是 `pixel-mall.js` 渲染的 SOAP 场景。

### 6.3 pixel-mall.js 商场平面图

用户对初始"暗色棋盘格"不满，要求做成商场平面图风格。完全重写后的设计：

- **区域色板** (`REGION_PALETTE`): 每个区域独特配色（中庭暖黄、店铺蓝、咖啡店粉、服务通道靛、虚拟世界紫）
- **物体图标** (`TYPE_ICONS`): 用 emoji 表示不同类型（⛲喷泉、🌀传送门、👾怪物、🧑‍💼店员、🤖机器人等）
- **虚实边框**: physical 金色、virtual 紫色、mixed 蓝色
- **暖色地砖**: 双色交替的地板纹理
- **键盘漫游**: ↑↓←→ / WASD 控制摄像机
- **点击选中**: 物体点击后高亮，右侧显示 JSON 详情

### 6.4 HTTP API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/scene` | GET | 当前场景快照（含被 Agent 修改后的最新状态）|
| `/api/roles` | GET | 角色视角列表 |
| `/api/events?after=N` | GET | 事件日志（轮询式实时更新）|
| `/api/act` | POST | 执行动作（JSON body: agent_id, verb, target_id, params）|
| `/api/summary` | GET | 场景摘要 |

### 6.5 实时事件轮询

前端每 2 秒 `GET /api/events?after={lastSeq}`，有新事件时：
1. 更新事件日志面板（按动词着色：OBSERVE 蓝、NAVIGATE 橙、MANIPULATE 粉）
2. 重新 `GET /api/scene` 刷新地图和实体详情
3. 更新事件计数徽标

### 6.6 Agent 控制台（最新）

界面内嵌的 Agent 控制面板：
- **agent_id** 输入框
- **verb** 下拉：OBSERVE / NAVIGATE / MANIPULATE
- **target** 下拉：自动填充场景中所有区域和物体
- **参数输入**: 根据动词动态切换（OBSERVE 无参数、NAVIGATE 要 target_uri、MANIPULATE 要 action + message/damage）
- **发送动作** 按钮 → POST `/api/act` → 即时显示结果 → 触发事件轮询

---

## 七、Demo 脚本

| 文件 | 说明 |
|------|------|
| `scripts/demo-agent-session.sh` | 13步 Agent 交互序列脚本：OBSERVE 中庭 → 对话 NPC → 移动到咖啡店 → 做咖啡 → 攻击怪物 → 移动机器人 → 扫码进入数字孪生 |

---

## 八、pyproject.toml 与构建

```toml
[project]
name = "omnity-soap"
version = "0.1.0"
requires-python = ">=3.9"
dependencies = ["jsonschema>=4.20.0", "referencing>=0.35.0"]

[project.optional-dependencies]
mcp = ["mcp>=1.2.0; python_version>='3.10'"]
dev = ["pytest>=8.0"]

[project.scripts]
soap-validate = "omnity_soap.cli:main"
soap-explore  = "omnity_soap.explore:main"
soap-view     = "omnity_soap.viewer_server:main"
soap-mcp      = "omnity_soap.mcp_server:main"
```

前端构建：`cd web/viewer && npm ci && npm run build` → `dist/` → 被 `viewer_server.py` 作为静态资源提供。

---

## 九、文件清单

### Python 后端 (`src/omnity_soap/`)
- `__init__.py` — 包入口
- `cli.py` — soap-validate CLI
- `validate.py` — JSON Schema 校验
- `explore.py` — soap-explore 交互式场景探索器（角色视角 + 自由查询）
- `runtime.py` — SOAPRuntime（可变场景图 + 动作执行 + 事件日志）
- `viewer_server.py` — soap-view HTTP 服务器
- `mcp_server.py` — soap-mcp MCP Server
- `paths.py` — 路径解析

### 前端 (`web/viewer/src/`)
- `main.js` — 主入口：一屏式布局编排、Agent 控制台、事件轮询
- `pixel-mall.js` — Phaser 3 商场平面图（区域色块 + 物体图标 + 键盘漫游）
- `soap-layout.js` — SOAP 场景几何计算（AABB → 平面坐标、区域包络、未定位物体布局）
- `gacn-replay.js` — GenerativeAgentsCN 回放（可选，非默认）
- `style.css` — 补充样式

### 规范 (`spec/`)
- `SOAP-v0.1.md` — 规范文档
- `CHANGELOG.md` — 变更日志
- `schemas/` — 4个 JSON Schema

### 测试 (`tests/`)
- `test_validate.py` — 校验测试
- `test_viewer.py` — viewer 测试
- `test_runtime_actions.py` — Runtime 动作测试（11个用例）

### 样例 (`examples/`)
- `minimal-scene.json` — 最小场景
- `mall-mixed-reality.json` — 活商场完整场景（17物体/5区域）
- `sample-action-observe.json` — 动作样例

---

## 十、已知问题与后续方向

### 已修复的问题
1. **中文路径 404**: `viewer_server.py` 未 percent-decode URL → 加了 `unquote()`
2. **GACN 数据覆盖 SOAP 场景**: 自动加载 GACN → 改为默认 SOAP、`?gacn=1` 可选
3. **端口占用**: 8765 端口被旧进程占用 → `lsof -ti:8765 | xargs kill -9`

### 后续方向（参考 WORK_PLAN.md）
- **UI 优化**: 一屏布局美化、操作便捷性提升
- **阶段 4 soap-scan**: 搭环境，跑通 gsplat 3DGS 重建（手机拍房间 → 3D 漫游）
- **阶段 5 soap-sem**: Depth Anything V2 + Grounded-SAM 2 → 自动语义标注
- **阶段 6 soap-render / soap-edit**: Three.js 3D viewer + NL 空间编辑

---

## 十一、运行方式

```bash
# 1. 安装 Python 包
cd packages/soap
pip install -e ".[dev]"

# 2. 构建前端
cd web/viewer && npm ci && npm run build && cd ../..

# 3. 启动 soap-view
python3 -m omnity_soap.viewer_server --port 8765
# 浏览器打开 http://127.0.0.1:8765/

# 4. 运行 demo 脚本（另一终端）
bash scripts/demo-agent-session.sh

# 5. 跑测试
pytest tests/ -q
```

---

*此日志由 AI 助手根据完整开发对话记录整理，供后续 AI 或人类成员快速了解项目历史与当前状态。*
