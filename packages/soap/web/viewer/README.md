# SOAP-View（浏览器可视化）

由 `soap-view` 命令在本地启动 HTTP 服务后，在浏览器中查看 **SOAP 场景 JSON**：

- **平面图**：物体 AABB 在 **XZ 平面**上的投影；无几何的物体通过 `twin_anchor_uri` / `anchor_physical_uri` 锚定到已有 AABB 中心，其余排在右侧「扩展列」。
- **关系图**：区域 `contains` 物体 + `relations` 边（依赖 [vis-network](https://github.com/visjs/vis-network) CDN）。
- **角色视角**：与 `soap-explore` 相同的六种角色，用于高亮「该角色能看见的物体」。

## 启动

```bash
cd packages/soap
source .venv/bin/activate   # 或你的 venv
pip install -e .
export SOAP_SCENE_PATH=examples/mall-mixed-reality.json   # 可选；默认即此文件（在未设置 SOAP_SCENE_PATH 时 explore 已改为 mall）
soap-view
# 打开 http://127.0.0.1:8765/
```

默认绑定 `127.0.0.1:8765`。更换端口：`soap-view --port 9000`。

## API

- `GET /api/scene` → `{ "meta": { "scene_path": "..." }, "scene": { ... } }`
- `GET /api/roles` → `{ "roles": [ ... ], "scene_path": "..." }`

第三方说明见 [THIRD_PARTY.md](./THIRD_PARTY.md)。
