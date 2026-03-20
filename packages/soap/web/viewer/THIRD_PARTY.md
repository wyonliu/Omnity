# 第三方组件与灵感来源（SOAP-View）

本目录为 **SOAP-View** 的静态前端；Omnity 主仓库许可为 **Apache-2.0**。下列组件为 **独立作品**，使用时请遵守其各自许可证；本文件满足常见的归属（attribution）要求。

## 运行时自 CDN 加载

| 组件 | 用途 | 获取方式 | 许可证（以官方为准） |
|------|------|----------|----------------------|
| **vis-network**（vis.js 系列） | 关系图布局与交互 | [unpkg.com/vis-network](https://unpkg.com/vis-network/) | **MIT** 与 **Apache-2.0** 双许可（见上游仓库 `LICENSE`） |

> 说明：浏览器需能访问 CDN；内网离线环境可将对应 UMD 包下载到本目录并在 `index.html` 中改为本地 `script src`。

## 设计灵感（非代码拷贝）

SOAP-View 的 **「俯视空间 + 实体关系 + 角色视角」** 产品形态，在体验上参考了学术与开源社区中 **小镇 / 多智能体仿真** 类演示的**信息架构**（地图上的智能体、可读的社交与环境图），例如：

- **Generative Agents: Interactive Simulacra of Human Behavior**（斯坦福等，Smallville 仿真）：论文与公开复现代码仓库常被社区以 **MIT** 等协议发布（具体以各 fork 的 `LICENSE` 为准）。**本仓库未复制其 Phaser/前端代码**，仅在文档层面对比「空间 + Agent」的可视化叙事。
- 若你指的是 **Simular / Agent-S** 等「GUI / 计算机操作」向的智能体框架，其与 SOAP 的「空间语义协议」侧重点不同；可视需要另做 **桌面自动化** 方向的 viewer，不在本包范围内。

## 若要在 Omnity 中「引用」其他开源项目

1. **只借鉴想法 / 论文**：在文档中注明来源即可（本文件即为一例）。  
2. **拷贝或修改上游代码**：保留其许可证与版权声明；若与 Apache-2.0 混合分发，需核对 **兼容性**（MIT / Apache-2.0 通常与企业场景友好）。  
3. **作为子模块或依赖**：在 `README` / `NOTICE` 中列出名称、仓库 URL、许可证。

---

*维护：Omnity / SOAP 参考实现。*
