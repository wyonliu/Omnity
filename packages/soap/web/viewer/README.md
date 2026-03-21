# SOAP-View 前端（Vite）

**壳层**与 [GenerativeAgentsCN](https://github.com/x-glacier/GenerativeAgentsCN) 回放页一致：**Bootstrap 3.4** + **jQuery**（CDN）、`#game-container`、随仓 **`public/vendor/generative-agents-cn/style.css`**（Apache-2.0）。**Phaser**、**vis-network** 经 npm 打包。许可证见 **`public/THIRD_PARTY.md`**。

## 可选：GenerativeAgentsCN 小镇 + 示例回放

```bash
npm run vendor:gacn
```

详见仓库内 [`SOAP_VIEW_RESTART.md`](../../SOAP_VIEW_RESTART.md)。

## 构建

```bash
cd packages/soap/web/viewer
npm ci
npm run vendor:gacn   # 可选
npm run build
```

产物在 **`dist/`**（含 `vendor/`）。`soap-view` 从 `web/viewer/dist/` 或 wheel 内 `viewer_static/` 提供静态文件。

## 开发联调

终端 1：`SOAP_SCENE_PATH=... soap-view`  
终端 2：`npm run dev`（`/api` 代理到 `8765`，见 `vite.config.js`）。
