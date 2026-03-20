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

构建命令：`npm ci && npm run build`（在 `packages/soap/web/viewer/`）。

## 设计灵感（非代码拷贝）

与 **Generative Agents / Smallville** 等「空间 + 多智能体」演示的**信息架构**类比见仓库内 **`docs/soap/VISUALIZER_INSPIRATION.md`**。**未嵌入** Phaser 等上游前端源码。

## 引用其它开源项目时的注意点

1. **只借鉴论文/想法**：文档注明即可。  
2. **拷贝源码**：保留版权声明与许可证；核对与 Apache-2.0 的兼容性。  
3. **npm 依赖**：发版前更新本表并运行 `npm audit`（按需）。

---

*维护：Omnity / SOAP 参考实现。*
