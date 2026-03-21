# 来自 GenerativeAgentsCN 的静态资源

以下文件自 **[x-glacier/GenerativeAgentsCN](https://github.com/x-glacier/GenerativeAgentsCN)** 复制，遵循该仓库 **Apache License 2.0**。

| 文件 | 上游路径 |
|------|-----------|
| `style.css` | `generative_agents/frontend/static/css/style.css` |

**可选（不入库，见 `web/viewer/.gitignore`）**：运行 `npm run vendor:gacn` 后会出现：

- `assets/village/` — 上游 `generative_agents/frontend/static/assets/village/`（tilemap、图块、agents 图集等）
- `example/movement.json` — 上游 `generative_agents/results/compressed/example/movement.json`（示例回放）

此时 Phaser 回放逻辑与上游 `main_script.html` **对齐**（路径改为 `/vendor/generative-agents-cn/assets/village/…`）。未运行同步时仍为 SOAP 自研 `pixel-mall` 场景。

SOAP-View 其余胶水代码（Vite、vis-network、`main.js` 分支）以 Omnity 仓库 **Apache-2.0** 授权。GenerativeAgentsCN 为独立项目，**不暗示商标或隶属关系**。
