# Mindos

**Portable Digital Soul Protocol** — 把记忆、人格与习惯做成可插拔的一层：换模型、换平台，**你**还是你。

全称 *Multi-layer Intention & Neural Dynamic Operating System*；当前代码聚焦 **L0 海马体（记忆）** 与三大原语 **`hydrate` / `commit` / `forget`**，与 [`MINDOS_PLAN.md`](./MINDOS_PLAN.md) 中的五层架构、MCP、Proxy 等规划对齐，逐步迭代。

---

## 当前版本完成度（v0.1.x）

| 能力 | 状态 | 说明 |
|------|------|------|
| `identity.yaml` + `memory.db` | ✅ | 本地优先，用户拥有数据目录 |
| `hydrate()` | ✅ | 拼装身份 + 相关记忆注入 system prompt；无向量时回退关键词/最近记忆 |
| `commit()` | ✅ | 规则抽取事实/偏好/技能 + 对话摘要；**去重**；**敏感信息跳过** |
| `forget()` | ✅ | 物理删除记忆；**同步清理知识图谱**（即使无匹配记忆行） |
| 知识图谱（三元组） | ✅ | SQLite 存储，Dashboard 可读 |
| CLI | ✅ | `init` / `status` / `forget` / `serve --dashboard` / `--version` |
| Dashboard | ✅ | 本地 Web：状态、记忆浏览、hydrate/commit/forget 试用；**端口占用自动递增**；`/api/config` 显示实际端口与数据路径 |
| 语义向量检索 | 可选 | 需安装 `semantic` 扩展（见下） |
| MCP / HTTP Proxy / LLM 消化 | 🔜 | 见 `MINDOS_PLAN.md` 路线图 |

**质量要点**：SQLite WAL；`commit` 返回 `skipped_duplicate` / `skipped_sensitive`；`reload_identity()` 热读配置文件。

---

## 安装

```bash
cd packages/mindos
pip install -e .

# 语义检索（sentence-transformers + numpy，体积较大，可选）
pip install -e ".[semantic]"
# 或一次性：pip install -e ".[all]"
```

仅标准能力时只需 **PyYAML**（`identity.yaml`）。无 PyYAML 时会尝试 JSON 兼容路径（不推荐长期使用）。

---

## 快速开始

```bash
# 初始化灵魂目录（默认 ~/.mindos）
mindos init --name "YourName" --traits "好奇,直接" --style "简洁技术风"

# 查看状态
mindos status

# 启动可视化面板（3456 被占用则自动 3457…）
mindos serve --dashboard

# 遗忘某类信息（GDPR 式硬删）
mindos forget "某关键词" --scope all
```

**演示脚本**（灌入示例数据后开面板）：

```bash
PYTHONPATH=src python3 scripts/demo_dashboard.py
# 仅灌数据：python3 scripts/demo_dashboard.py --no-serve
# 指定端口：python3 scripts/demo_dashboard.py --port 8765
```

**开发者入口**：

```bash
PYTHONPATH=src python3 -m mindos --version
PYTHONPATH=src python3 -m mindos status --path /path/to/.mindos
```

---

## Python API

```python
from pathlib import Path
from mindos import Mindos

m = Mindos.load("~/.mindos")

ctx = m.hydrate(situation="讨论下周出差", max_tokens=2000)
# → 拼进 LLM 的 system prompt

m.commit(
    [
        {"role": "user", "content": "我下周去东京"},
        {"role": "assistant", "content": "好的，需要行程建议吗？"},
    ],
    source="claude",
)
# → 返回 memories_added, skipped_duplicate, skipped_sensitive

n = m.forget("东京")  # 删除含该关键词的记忆与图谱边

m.reload_identity()   # 手动改完 identity.yaml 后调用
```

---

## 测试

```bash
cd packages/mindos
PYTHONPATH=src python3 tests/test_soul.py
```

---

## 故障排除

| 现象 | 处理 |
|------|------|
| `ModuleNotFoundError: yaml` | `pip install pyyaml` |
| `ModuleNotFoundError: numpy` | 仅影响向量与 embedding；可 `pip install numpy` 或装 `.[semantic]` |
| `Address already in use` | 已自动换端口；或 `mindos serve --dashboard --port 8765`；或 `lsof -i :3456` 后 `kill` |

---

## 文档与许可

- 产品与技术规划：[MINDOS_PLAN.md](./MINDOS_PLAN.md)  
- 仓库总览：[../../README.md](../../README.md)  
- 许可：与根目录 [LICENSE](../../LICENSE) 一致，**Apache-2.0**。

---

## English summary

Mindos v0.1.x ships a **local-first** soul store: SQLite + optional vector recall, **`hydrate` / `commit` / `forget`** primitives, CLI, and a **dark-themed Dashboard** with auto free-port binding. Install optional **`[semantic]`** for embeddings. See **MINDOS_PLAN.md** for the full five-layer brain, MCP, and proxy roadmap.
