# `packages/mindos` — Mindos

**Mindos** = **M**ulti-layer **I**ntention & **N**eural **D**ynamic **O**perating **S**ystem — 多层脑 Agent 操作系统（记忆 L0、本能 L1、思考 L2、意图 L3、路由与反思等）。

实现与 API 随 Phase 0–1 落地；详见 [`../../ometown_execution.md`](../../ometown_execution.md)。

## Dashboard 端口被占用

若出现 `OSError: [Errno 48] Address already in use`：通常是上次 Dashboard 仍在运行。任选其一：

- **自动换端口**：更新后的 `run_dashboard` 会在 3456 被占用时依次尝试 3457、3458…
- **手动指定**：`mindos serve --dashboard --port 8765`
- **结束旧进程**（macOS）：`lsof -i :3456` 查看 PID，再 `kill <PID>`

## 许可

与仓库根目录 [LICENSE](../../LICENSE) 一致：**Apache-2.0**。
