# SOAP-View 完整重启与测试（含 GenerativeAgentsCN 1:1 回放）

以下路径以仓库根目录 `omnity/` 为准。

## 1. 一次性：同步上游小镇素材 + 示例 `movement.json`

体积较大（tilemap、多张大图、约 5MB+ 的 JSON），**默认不入库**，由脚本拉取。

```bash
cd packages/soap/web/viewer
npm ci
npm run vendor:gacn
```

成功后可检查：

- `public/vendor/generative-agents-cn/assets/village/tilemap/tilemap.json`
- `public/vendor/generative-agents-cn/example/movement.json`

## 2. 构建前端

```bash
cd packages/soap/web/viewer
npm run build
```

`dist/` 会包含已同步的 `vendor/` 下文件（Vite 从 `public/` 拷贝）。

## 3. 安装并启动 soap-view

```bash
cd packages/soap
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

指定 SOAP 场景（与仓库内示例一致时可省略，使用包内默认）：

```bash
export SOAP_SCENE_PATH="/绝对路径/到你的/scene.json"
soap-view
```

默认监听 **http://127.0.0.1:8765**（以终端输出为准）。

## 4. 浏览器验证

1. **日常用法（默认）**：打开 **`http://127.0.0.1:8765`** —— 地图区是 **当前 `SOAP_SCENE_PATH` 场景** 的 SOAP 平面图（`pixel-mall`），条带、详情、关系图、角色视角均来自 **`/api/scene`、`/api/roles`**。这才是「跑我们的数据」。
2. **可选：上游 UI 对照**：仅当需要 1:1 对照 GenerativeAgentsCN 的 *The Ville 示例*（其自带的 `movement.json`，时间线/对白是对方项目里的演示数据）时，在已 `vendor:gacn` 且已 build 的前提下访问  
   **`http://127.0.0.1:8765/?gacn=1`**  
   才会加载 Tiled 小镇 + 示例回放。**不要**把该模式当成 Omnity 场景的真值来源。
3. 若加了 `?gacn=1` 但资源未同步，会留在 SOAP 平面图，并在页眉 meta 一行提示资源缺失。

点击 **「重新加载场景」** 会按当前地址栏参数重新决定是否挂载上游示例。

## 5. 开发模式（可选）

终端 1：

```bash
cd packages/soap
source .venv/bin/activate
SOAP_SCENE_PATH=... soap-view
```

终端 2：

```bash
cd packages/soap/web/viewer
npm run dev
```

浏览器打开 Vite 提示的地址（如 `http://127.0.0.1:5173`），`/api` 已代理到 `8765`。

## 6. 完全重来（清缓存式）

```bash
# 前端
cd packages/soap/web/viewer
rm -rf node_modules dist
rm -rf public/vendor/generative-agents-cn/assets public/vendor/generative-agents-cn/example
npm ci && npm run vendor:gacn && npm run build

# Python
cd packages/soap
rm -rf .venv
python3 -m venv .venv && source .venv/bin/activate && pip install -e .
soap-view
```

---

许可与归属见 `web/viewer/public/THIRD_PARTY.md`、`web/viewer/public/vendor/generative-agents-cn/ATTRIBUTION.md`。
