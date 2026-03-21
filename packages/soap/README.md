# `packages/soap` — SOAP

**SOAP** = **S**patial **O**mnity **A**gentic **P**rotocol — **空间智能体时代的 HTTP**：开放规范 + 参考实现 + `soap-mcp`，让任意 AI Agent 用统一方式理解、查询与操作真实 3D 空间。

## 已实现

| 组件 | 说明 |
|------|------|
| **规范 v0.1** | [`spec/SOAP-v0.1.md`](./spec/SOAP-v0.1.md) + [JSON Schema](./spec/schemas/) — 四动词（OBSERVE / NAVIGATE / MANIPULATE / REARRANGE）、Spatial URI、虚实标签 |
| **样例场景** | [`examples/`](./examples/) — `minimal-scene.json`、`mall-mixed-reality.json`（六角色活商场）、`sample-action-observe.json` |
| **SOAPRuntime** | 内存可变运行时：加载场景 → 接收 Agent 动作 → 修改状态 → 事件日志 |
| **soap-validate** | CLI 校验场景 JSON 是否符合 Schema |
| **soap-explore** | 交互式 CLI，六角色视角检验场景可见性 |
| **soap-mcp** | MCP Server（[README](./soap-mcp/README.md)）— 让 Cursor / Claude 等宿主通过标准 MCP 查询和操作空间 |
| **soap-view** | 浏览器可视化（[`web/viewer/`](./web/viewer/)）— 商场平面图 + Agent 头像 + 动作动画 + 自主巡游演示 |

### soap-view 亮点

- **Canvas 2D 像素级清晰渲染**：商场楼层布局 + 实体图标 + 虚实颜色编码
- **Agent 实时可视化**：绿色头像 + 思维气泡（💭 斯坦福小镇风格）
- **平滑移动动画**：所有动作（OBSERVE / NAVIGATE / MANIPULATE）在 1s 内沿路径平滑移动，不跳变
- **动作特效**：OBSERVE 扫描波纹、NAVIGATE 虚线路径 + 箭头、MANIPULATE 冲击波
- **自主巡游**：一键启动 `explorer` Agent，自动规划 12 步探索商场（观察→逛店→聊天→喝咖啡→战斗）
- **HTTP API**：`/api/scene`、`/api/roles`、`/api/events`、`/api/act`（POST）— 外部 Agent 通过 HTTP 即可交互

## 快速开始

```bash
cd packages/soap

# 1. Python 环境
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"      # 校验与测试
pip install -e ".[mcp]"      # MCP Server（需 Python ≥3.10）

# 2. 构建前端
(cd web/viewer && npm ci && npm run build)

# 3. 启动可视化
export SOAP_SCENE_PATH=examples/mall-mixed-reality.json
soap-view
# 浏览器打开 http://127.0.0.1:8765/

# 4. 校验 & 测试
soap-validate examples/mall-mixed-reality.json
pytest tests/ -q
```

### 通过 HTTP 控制 Agent

```bash
# 观察中庭
curl -X POST http://127.0.0.1:8765/api/act \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"my_bot","verb":"OBSERVE","target_id":"atrium","params":{}}'

# 导航到店铺
curl -X POST http://127.0.0.1:8765/api/act \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"my_bot","verb":"NAVIGATE","target_id":"store_102","params":{"target_uri":"soap://mall_01/store_102"}}'

# 与 NPC 对话
curl -X POST http://127.0.0.1:8765/api/act \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"my_bot","verb":"MANIPULATE","target_id":"store_102_ai_clerk","params":{"action":"speak","message":"推荐一下？"}}'
```

## 文档

- [SOAP 规范 v0.1](./spec/SOAP-v0.1.md)
- [五层协议栈愿景](../../docs/soap/PROTOCOL_VISION_AND_EXECUTION.md)
- [活商场思想实验](../../docs/soap/THOUGHT_EXPERIMENT_THE_LIVING_MALL.md)
- [工作计划](../../docs/soap/WORK_PLAN.md)
- [soap-mcp README](./soap-mcp/README.md)
- [可视化灵感与合规](../../docs/soap/VISUALIZER_INSPIRATION.md)

## 后续规划

- `soap-scan` — 照片 → 3DGS + SOAP 场景
- `soap-sem` — 3D 语义分割
- `soap-edit` — 自然语言空间编辑
- `soap-render` — 跨端 3DGS 渲染

## 许可

[Apache-2.0](../../LICENSE)
