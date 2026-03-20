# SOAP 可视化：灵感来源与合规引用

SOAP-View（`soap-view`）是 **v0.1 的调试与演示界面**：把同一份 SOAP 场景 JSON 变成 **平面图 + 关系图 + 角色高亮**，方便检验「活商场」思想实验里的物体、区域与关系是否自洽。

## 与「斯坦福小镇 / Generative Agents」的关系

**Generative Agents**（Park et al.，Smallville 仿真）的经典演示是：**俯视或侧视的城镇地图 + 多个 Agent 在环境中移动与交互**。SOAP-View 在 **信息架构** 上与之类比的是：

- 空间中有**可寻址实体**（SOAP 的 `ObjectInstance` / `SpatialRegion`）；
- 需要一种 **人类可读的观察入口**（地图与图），与 Agent 通过 MCP/JSON 消费的是**同一套数据**。

**重要声明**：本仓库 **未复制** Smallville 官方复现里使用的 **Phaser 前端、引擎循环或具体资源文件**。若未来要嵌入上游代码，须在子目录保留其 **LICENSE**，并核对与 Apache-2.0 的混用方式。

## 「Simile」可能指什么

口语里容易与下列名称混淆，合规引用时请核对 **具体仓库的 LICENSE**：

| 名称 | 常见指向 | 与 SOAP-View 的关系 |
|------|----------|---------------------|
| **Simile**（MIT Semantic Web 工具族） | 旧式 RDF/语义 Web 可视化 | 技术栈不同，一般不直接复用 |
| **Simular / Agent-S** | 计算机 GUI 自动化智能体 | 侧重桌面而非商场空间语义 |
| **simulacra** 等复现 | Generative Agents 论文实现 | 可阅读其 MIT 代码与结构，**拷贝需带许可证** |

当前 SOAP-View 的 **图布局库** 选用 **vis-network**（CDN，MIT / Apache-2.0 双许可），归属见 [`packages/soap/web/viewer/THIRD_PARTY.md`](../../packages/soap/web/viewer/THIRD_PARTY.md)。

## 推荐的引用方式（开源项目）

1. **文档中说明灵感**：论文引用 + 仓库链接 + 「未拷贝代码」或「拷贝部分在 `third_party/`」。
2. **拷贝代码**：保留版权声明；在 `NOTICE` 或 `THIRD_PARTY.md` 列出项目名、URL、许可证。
3. **依赖包**：在 `README` / lockfile 中锁定版本；遵守依赖许可证义务。

---

*与 [`WORK_PLAN.md`](./WORK_PLAN.md) 阶段 6（soap-render / 高斯 splat）衔接：SOAP-View 是 **轻量 2D + 图** 的先行版，不承担真实 3D 渲染。*
