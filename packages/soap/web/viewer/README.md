# SOAP-View 前端（Vite）

共识技术栈：**Vite** + **Bootstrap 5** + **vis-network**（均通过 npm 安装，许可证见 `public/THIRD_PARTY.md`）。

## 构建

```bash
cd packages/soap/web/viewer
npm ci
npm run build
```

产物在 **`dist/`**。Python 侧 `soap-view` 默认从 `web/viewer/dist/`（或已安装的 `omnity_soap/viewer_static/`）提供静态文件。

## 开发联调（热更新）

终端 1：

```bash
cd packages/soap
SOAP_SCENE_PATH=examples/mall-mixed-reality.json soap-view
```

终端 2：

```bash
cd packages/soap/web/viewer
npm ci
npm run dev
```

浏览器打开 Vite 提示的地址（默认 `http://127.0.0.1:5173`）；`/api/*` 由 Vite 代理到 `http://127.0.0.1:8765`（见 `vite.config.js`）。

发版或跑 `pytest` 前请执行一次 **`npm run build`**，保证 `dist/` 与 lockfile 一致；CI 会强制执行。
