# `packages/soap` — SOAP

**SOAP** = **S**patial **O**mnity **A**gentic **P**rotocol — **空间智能体时代的 HTTP**：开放规范 + 本仓参考实现 + **`soap-mcp`**，让任意 Agent 宿主用统一方式理解、查询与操作真实 3D 空间。

**为什么做 / 五层协议栈 / 国民级路径**：[`docs/soap/PROTOCOL_VISION_AND_EXECUTION.md`](../../docs/soap/PROTOCOL_VISION_AND_EXECUTION.md)。  
**活商场思想实验**：[`docs/soap/THOUGHT_EXPERIMENT_THE_LIVING_MALL.md`](../../docs/soap/THOUGHT_EXPERIMENT_THE_LIVING_MALL.md)。  
**周粒度任务**：[`docs/soap/WORK_PLAN.md`](../../docs/soap/WORK_PLAN.md)。

## 已实现（v0.1）

- [`spec/SOAP-v0.1.md`](./spec/SOAP-v0.1.md) + [`spec/schemas/`](./spec/schemas/) + [`spec/CHANGELOG.md`](./spec/CHANGELOG.md)
- [`examples/`](./examples/) — `minimal-scene.json`、`mall-mixed-reality.json`、`sample-action-observe.json`
- Python 包 **`omnity-soap`**：`soap-validate`、`soap-explore`、**`soap-view`**（[`web/viewer/`](./web/viewer/)）、[`soap-mcp`](./soap-mcp/README.md)（需 Python **≥3.10**）、[`tests/`](./tests/)

### 本地开发

```bash
cd packages/soap
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"     # 校验与测试
pip install -e ".[mcp]"     # 另需 Python 3.10+ 以安装官方 mcp 包
pytest tests/ -q
soap-validate examples/mall-mixed-reality.json
SOAP_SCENE_PATH=examples/mall-mixed-reality.json soap-view
# 浏览器打开 http://127.0.0.1:8765/
```

**soap-view**：平面图（XZ）+ 关系图（vis-network CDN）+ 与 `soap-explore` 一致的六角色高亮。第三方与灵感来源见 [`web/viewer/THIRD_PARTY.md`](./web/viewer/THIRD_PARTY.md)；与斯坦福小镇类演示的**文档层面对比**见 [`docs/soap/VISUALIZER_INSPIRATION.md`](../../docs/soap/VISUALIZER_INSPIRATION.md)。

## 内容规划（后续）

- `soap-scan` / `soap-sem` / `soap-edit` / `soap-render` — 工具链（WORK_PLAN 阶段 4–6）

## 许可

与仓库根目录 [LICENSE](../../LICENSE) 一致：**Apache-2.0**。
