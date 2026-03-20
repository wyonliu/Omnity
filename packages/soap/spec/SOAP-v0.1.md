# SOAP Specification v0.1.0

**Spatial Omnity Agentic Protocol** — 空间智能体协议（草案）  
**状态**：Draft · **互操作目标**：Conformance **T1**（语义互操作），并为 T2 几何对齐预留字段  
**机器可读契约**：同目录下 [`schemas/`](./schemas/) JSON Schema · **CHANGELOG**：[`CHANGELOG.md`](./CHANGELOG.md)

> **本文不承诺**全链路实时控制（T4）或全行业零摩擦打通。详见 [`../../../docs/soap/PROTOCOL_VISION_AND_EXECUTION.md`](../../../docs/soap/PROTOCOL_VISION_AND_EXECUTION.md) 与思想实验 [`../../../docs/soap/THOUGHT_EXPERIMENT_THE_LIVING_MALL.md`](../../../docs/soap/THOUGHT_EXPERIMENT_THE_LIVING_MALL.md)。

---

## 1. 范围与愿景

SOAP 定义：

1. **空间与物体的稳定命名**（Spatial URI）与 **场景图**（对象、区域、关系）。  
2. **Agent 对空间发起的动作** 的 **动词子集** 与 **结果/错误形状**。  
3. **虚实属性** 与 **冲突处理原则**（真实世界优先）。

不定义：具体 SLAM 算法、物理引擎、世界模型内部表示。

---

## 2. 术语

| 术语 | 含义 |
|------|------|
| **Scene** | 一份可序列化的 `SOAPScene` 文档（通常 JSON）。 |
| **Spatial URI** | `soap://{space_id}/{path...}` 形式的全局可读标识。 |
| **ObjectInstance** | 场景中一个可被指称的实体（物理/虚拟/混合）。 |
| **SpatialRegion** | 功能或导航意义上的区域，可包含多个物体。 |
| **AgentAction** | Agent 对某 URI 发起的动作描述（可与 Scene 分离传输）。 |
| **reality** | `physical` \| `virtual` \| `mixed` — 虚实标签。 |

---

## 3. Spatial URI

**语法**（v0.1 正则意图，实现可放宽）：

```text
soap://{space_id}/{segment(/segment)*}(/object_id)?
```

- `space_id`：商场、房间、孪生世界的稳定 ID（由注册方分配）。  
- 路径：**从粗到细**（如 `atrium` → `store_102`）。  
- 查询参数（可选，v0.1）：`?hint=x,y,z` 仅作定位提示，**不**替代物体 ID。

**同一 URI** 在多端应解析到 **同一语义对象**（T1）；几何对齐属 T2。

---

## 4. SOAPScene 文档

根字段见 JSON Schema `scene.schema.json`。必填：

- `soap_version`：本规范版本，如 `0.1.0`。  
- `space_id`：与 URI 中 `space_id` 一致。  
- `coordinate_frame`：坐标系声明（右手/单位/向上轴/原点文字说明）。  
- `objects`：`ObjectInstance[]`。  
- `regions`：`SpatialRegion[]`。

可选：`title`、`relations`、`assets`、`meta`。

---

## 5. ObjectInstance

必填：`id`、`uri`、`type`、`reality`。

- `type`：建议点分本体路径，如 `furniture.chair.armchair`、`npc.avatar`、`robot.unit`。  
- `affordances`：字符串枚举列表，如 `sit`、`grasp`、`display_ar`、`navigate_through`。  
- `bounds`：v0.1 推荐 **轴对齐包围盒** `aabb` + `min`/`max`（与 `coordinate_frame` 一致）。  
- `state`：键值对（灯开关、门状态等），**不**强制统一全集。  
- `bindings`：虚实孪生绑定（设备 ID、引擎 entity id 等），**实现相关**。

---

## 6. SpatialRegion

必填：`id`、`uri`、`name`。

- `purpose_tags`：如 `circulation`、`retail`、`ar_overlay`、`robot_lane`。  
- `contained_object_ids`：属于该区域管辖或展示的物体 `id` 列表（逻辑包含，非严格几何）。

---

## 7. 动作动词（v0.1 最小集）

| 动词 | 意图 |
|------|------|
| **OBSERVE** | 获取某 URI 的感知摘要（可见性、状态子集由实现决定）。 |
| **NAVIGATE** | 移动某实体至目标 URI 或位姿（具身/化身/相机）。 |
| **MANIPULATE** | 对物体或设备执行原子操作（开/关、抓取信号等）。 |
| **REARRANGE** | 多物体布局变更（规划级或执行级由 Profile 定义）。 |

每个动作返回应包含：`ok`、`code`（标准错误码表未来扩充）、`detail`（可选）。

---

## 8. 多 Agent 与冲突（L4 占位）

v0.1 **不**强制实现锁服务器；建议在 `meta` 或扩展字段中携带 `lock_holder`、`authority` 提示。完整 L4 见路线图。

---

## 9. 真实世界优先

若同一物体的 **物理传感器状态** 与 **虚拟推断状态** 冲突：**以物理/经授权的孪生同步源为准**，虚拟侧应更新并产生可记录同步事件（供记忆与调试）。

---

## 10. 与「活商场」思想实验的对应

见 [`THOUGHT_EXPERIMENT_THE_LIVING_MALL.md`](../../../docs/soap/THOUGHT_EXPERIMENT_THE_LIVING_MALL.md)：本版提供 **共用的 URI 与场景图骨架**；几何、实时流、游戏引擎绑定通过 **后续 Profile** 与 **Tier** 扩展。

---

*SOAP v0.1.0 · Omnity*
