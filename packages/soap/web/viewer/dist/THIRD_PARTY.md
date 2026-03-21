# 第三方组件与许可证（SOAP-View）

Omnity 主仓库为 **Apache-2.0**。本前端通过 **npm** 声明依赖，由 **Vite** 打包进 `dist/`，随 `omnity-soap` wheel 的 `viewer_static/` 分发。

## npm 依赖（以各包 `package.json` / 仓库 `LICENSE` 为准）

| 包 | 用途 | 许可证（常见） |
|----|------|------------------|
| [vite](https://github.com/vitejs/vite) | 构建工具（仅 devDependency） | **MIT** |
| [bootstrap](https://github.com/twbs/bootstrap) | UI 布局与组件样式 | **MIT** |
| [@popperjs/core](https://github.com/popperjs/popper-core) | Bootstrap 工具提示等定位依赖 | **MIT** |
| [vis-network](https://github.com/visjs/vis-network) | 关系图 | **MIT** 与 **Apache-2.0** 双许可 |
| [vis-data](https://github.com/visjs/vis-data) | vis-network 数据结构 | **MIT** 与 **Apache-2.0** 双许可 |
| [phaser](https://github.com/phaserjs/phaser) | 像素风 2D 地图（`pixelArt`、键盘漫游） | **MIT** |

构建命令：`npm ci && npm run build`（在 `packages/soap/web/viewer/`）。

## 设计灵感（非代码拷贝）

- 俯视像素地图 + 键盘漫游的**交互范式**，与 Stanford **Generative Agents** 及社区复现 **[GenerativeAgentsCN](https://github.com/x-glacier/GenerativeAgentsCN)**（Apache-2.0）相近；本 viewer **程序生成**棋盘格与色块，**不使用**对方 tilemap / 精灵素材。  
- 与 **Generative Agents / Smallville** 的**信息架构**类比另见仓库内 **`docs/soap/VISUALIZER_INSPIRATION.md`**。

## 引用其它开源项目时的注意点

1. **只借鉴论文/想法**：文档注明即可。  
2. **拷贝源码**：保留版权声明与许可证；核对与 Apache-2.0 的兼容性。  
3. **npm 依赖**：发版前更新本表并运行 `npm audit`（按需）。

---

*维护：Omnity / SOAP 参考实现。*
