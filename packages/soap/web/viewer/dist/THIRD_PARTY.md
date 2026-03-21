# 第三方组件与许可证（SOAP-View）

Omnity 主仓库为 **Apache-2.0**。本前端由 **Vite** 打包进 `dist/`，随 `omnity-soap` wheel 的 `viewer_static/` 分发。

## npm 依赖

| 包 | 用途 | 许可证（以官方为准） |
|----|------|------------------------|
| [vite](https://github.com/vitejs/vite) | 构建（devDependency） | **MIT** |
| [vis-network](https://github.com/visjs/vis-network) | 关系图 | **MIT** & **Apache-2.0** |
| [vis-data](https://github.com/visjs/vis-data) | vis-network 数据 | **MIT** & **Apache-2.0** |
| [phaser](https://github.com/phaserjs/phaser) | 2D 地图（`pixelArt`） | **MIT** |

## 自 CDN 加载（与 [GenerativeAgentsCN](https://github.com/x-glacier/GenerativeAgentsCN) 回放页同源栈）

| 资源 | 用途 | 许可证 |
|------|------|--------|
| [Bootstrap 3.4.1](https://getbootstrap.com/docs/3.4/) CSS + JS | 栅格、面板、按钮 | **MIT** |
| [jQuery 3.7.1](https://jquery.com/) | Bootstrap 3 依赖 | **MIT** |

## 随仓分发的上游文件（Apache-2.0）

| 路径 | 来源 |
|------|------|
| `vendor/generative-agents-cn/style.css` | [GenerativeAgentsCN](https://github.com/x-glacier/GenerativeAgentsCN) `generative_agents/frontend/static/css/style.css` |

说明见同目录 **`ATTRIBUTION.md`**。页面 **HTML 结构**（`#game-container`、实体条带、`.media` 详情区）与上游回放页 **对齐**。

**默认**：地图为 **SOAP 场景**（`pixel-mall`），与 `soap-view` 的 `/api/scene` 一致。**上游小镇示例**：仅当地址栏带 **`?gacn=1`** 且已执行 `npm run vendor:gacn` 并 build 时，才加载对方 `movement.json`（The Ville 演示数据，非你的场景）。

构建：`npm ci && npm run build`（目录 `packages/soap/web/viewer/`）。对照 UI 时再执行 `vendor:gacn`。

---

*维护：Omnity / SOAP 参考实现。*
