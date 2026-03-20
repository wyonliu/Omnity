"""soap-explore: 交互式 SOAP 场景探索器（角色视角 + 自由查询）。

纯 stdlib + jsonschema/referencing，Python 3.9 可跑。
"""
from __future__ import annotations

import json
import os
import sys
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from omnity_soap.paths import package_root
from omnity_soap.validate import validate_scene_file


# ── scene loading ──────────────────────────────────────────────

def _resolve_scene() -> Path:
    env = os.environ.get("SOAP_SCENE_PATH")
    if env:
        return Path(env).expanduser().resolve()
    return package_root() / "examples" / "mall-mixed-reality.json"


def load_scene(path: Path) -> Dict[str, Any]:
    validate_scene_file(path)
    return json.loads(path.read_text(encoding="utf-8"))


# ── helpers ────────────────────────────────────────────────────

def _obj_map(scene: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {o["id"]: o for o in scene.get("objects", [])}


def _region_map(scene: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {r["id"]: r for r in scene.get("regions", [])}


def _relations_for(scene: Dict[str, Any], obj_id: str) -> List[Dict[str, Any]]:
    return [
        r for r in scene.get("relations", [])
        if r.get("from_id") == obj_id or r.get("to_id") == obj_id
    ]


def _objects_in_region(scene: Dict[str, Any], region_id: str) -> List[Dict[str, Any]]:
    objs = _obj_map(scene)
    region = _region_map(scene).get(region_id)
    if not region:
        return []
    return [objs[oid] for oid in region.get("contained_object_ids", []) if oid in objs]


def _objects_by_reality(scene: Dict[str, Any], reality: str) -> List[Dict[str, Any]]:
    return [o for o in scene.get("objects", []) if o.get("reality") == reality]


def _objects_with_affordance(scene: Dict[str, Any], aff: str) -> List[Dict[str, Any]]:
    return [o for o in scene.get("objects", []) if aff in o.get("affordances", [])]


def _format_obj_brief(o: Dict[str, Any]) -> str:
    tags = ", ".join(o.get("affordances", [])[:4])
    r = o.get("reality", "?")
    return f'  {o["id"]:30s}  [{r:8s}]  {o.get("type", "")}  ({tags})'


def _format_obj_detail(o: Dict[str, Any], scene: Dict[str, Any]) -> str:
    lines = [f'── {o["id"]} ──']
    lines.append(f'  URI       : {o.get("uri")}')
    lines.append(f'  type      : {o.get("type")}')
    lines.append(f'  reality   : {o.get("reality")}')
    lines.append(f'  affordances: {o.get("affordances")}')
    if o.get("bounds"):
        lines.append(f'  bounds    : {o["bounds"]}')
    if o.get("bindings"):
        lines.append(f'  bindings  : {json.dumps(o["bindings"], ensure_ascii=False)}')
    if o.get("state"):
        lines.append(f'  state     : {json.dumps(o["state"], ensure_ascii=False)}')
    rels = _relations_for(scene, o["id"])
    if rels:
        lines.append("  relations :")
        for r in rels:
            lines.append(f'    {r["from_id"]} --[{r["relation"]}]--> {r["to_id"]}')
    return "\n".join(lines)


# ── role definitions ───────────────────────────────────────────

ROLES: List[Dict[str, Any]] = [
    {
        "key": "mr",
        "name": "MR 眼镜玩家（平行世界游戏）",
        "desc": "戴 MR 眼镜在中庭玩平行世界游戏。能看到虚拟游戏物体叠加在物理空间上，需要避开真实障碍物。",
        "filter": lambda scene: [
            o for o in scene.get("objects", [])
            if o.get("type", "").startswith("mr_game.")
            or "anchor_ar" in o.get("affordances", [])
            or "circulation_obstacle" in o.get("affordances", [])
        ],
        "actions": [
            "OBSERVE game_portal_alpha  → 看到传送门入口, quest=collect_crystal_shard",
            "OBSERVE game_monster_01    → 发现怪物, hp=120, lv5, 在 pillar_03 附近",
            "NAVIGATE → pillar_03       → 接近柱子（物理障碍物, 也是游戏锚点）",
            "MANIPULATE game_monster_01 → 攻击怪物（虚拟交互 → drop_loot）",
        ],
        "insight": (
            "SOAP 让 MR 游戏引擎知道物理柱子的 bounds，虚拟怪物被 anchor 在柱子旁。\n"
            "游戏逻辑通过 bindings.game_id 运行，SOAP 只管空间语义和碰撞边界。"
        ),
    },
    {
        "key": "phone",
        "name": "手机扫描用户（进入门店数字孪生）",
        "desc": "拿着手机在 102 号店铺门口扫码，进入数字孪生页面查看促销和商品信息。",
        "filter": lambda scene: [
            o for o in scene.get("objects", [])
            if o.get("id") in ("store_102_front", "store_102_shelf_a", "store_102_ai_clerk")
            or "scan_qr" in o.get("affordances", [])
            or "view_promotions" in o.get("affordances", [])
        ],
        "actions": [
            "OBSERVE store_102_front    → 看到店铺状态: open, 当前促销: 满300减50",
            "MANIPULATE store_102_front (scan_qr) → 扫码跳转 digital_twin_url",
            "OBSERVE store_102_shelf_a  → 浏览货架商品",
            "OBSERVE store_102_ai_clerk → 虚拟导购弹出, mood=helpful, 支持中英文",
        ],
        "insight": (
            "SOAP 的 bindings.digital_twin_url 让手机扫码后直达商品页。\n"
            "store_102_ai_clerk 是 reality=virtual 的 NPC，手机 AR 模式也能看到。"
        ),
    },
    {
        "key": "glasses",
        "name": "AI 眼镜用户（导航 + 语音交互）",
        "desc": "戴着 AI 眼镜在商场导航，语音问路，看到指示牌和设施的实时信息。",
        "filter": lambda scene: [
            o for o in scene.get("objects", [])
            if "visual_landmark" in o.get("affordances", [])
            or "navigate_through" in o.get("affordances", [])
            or "floor_transition" in o.get("affordances", [])
            or "read_text" in o.get("affordances", [])
            or o.get("type", "").startswith("facility.")
            or o.get("type", "").startswith("decor.")
        ],
        "actions": [
            "OBSERVE nav_sign_f1_01     → 读取: ← 洗手间 | 扶梯↑ | 出口→",
            "OBSERVE fountain_center    → 识别地标, 确认当前位置在中庭中心",
            "NAVIGATE → escalator_f1_up → 导航到扶梯（connects_to cafe_201）",
            "OBSERVE escalator_f1_up    → 确认扶梯运行中, 方向: up",
        ],
        "insight": (
            "AI 眼镜通过 SOAP URI 解析当前区域 → 查询区域内 affordances 含 visual_landmark 的物体 → 构建导航路径。\n"
            "relations 中 escalator_f1_up --connects_to--> cafe_201 让导航知道扶梯通向何处。"
        ),
    },
    {
        "key": "robot",
        "name": "具身智能机器人（配送 + 清洁）",
        "desc": "配送机器人在后场通道配送包裹，清洁机器人在中庭执行清洁任务。",
        "filter": lambda scene: [
            o for o in scene.get("objects", [])
            if o.get("type", "").startswith("robot.")
            or "robot_lane" in (
                _region_map(scene).get(
                    next(
                        (r["to_id"] for r in scene.get("relations", [])
                         if r.get("from_id") == o.get("id") and r.get("relation") == "assigned_to"),
                        ""
                    ), {}
                ).get("purpose_tags", [])
            )
            or "circulation_obstacle" in o.get("affordances", [])
        ],
        "actions": [
            "OBSERVE robot_unit_d       → battery=78%, payload=package_1042, status=delivering",
            "NAVIGATE robot_unit_d → soap://mall_01/store_102/entrance  → 从服务通道导航到 102 门口",
            "OBSERVE robot_cleaner_e    → battery=52%, zone=atrium, status=cleaning",
            "MANIPULATE robot_cleaner_e (avoid_obstacle) → 检测 pillar_03 bounds, 绕行",
        ],
        "insight": (
            "机器人通过 SOAP 查询 region.purpose_tags 知道 service_lane 是 robot_lane，可自由行驶。\n"
            "所有 circulation_obstacle 的 bounds 用于避障路径规划。\n"
            "bindings.control_api 指向 robot://fleet/d-07/cmd — SOAP 不控制机器人，只提供空间上下文。"
        ),
    },
    {
        "key": "npc",
        "name": "线上虚拟 NPC（1:1 数字孪生世界）",
        "desc": "NPC 商人 Lin 和咖啡师 Chen 在线上数字孪生世界中生活，有自己的任务和情绪。",
        "filter": lambda scene: [
            o for o in scene.get("objects", [])
            if o.get("type", "").startswith("npc.")
        ],
        "actions": [
            "OBSERVE npc_merchant_lin   → mood=welcoming, task=greeting_visitors",
            "OBSERVE npc_barista_chen   → mood=busy, task=serving_latte",
            "NAVIGATE npc_merchant_lin → soap://mall_01/cafe_201/counter → Lin 走去咖啡店找 Chen",
            "MANIPULATE npc_merchant_lin (speak) → Lin 向来访者打招呼",
        ],
        "insight": (
            "NPC 通过 bindings.world_model_entity 连接 Mindos 意识模型。\n"
            "bindings.twin_anchor_uri 决定他们在物理空间的「投影位置」—— MR 眼镜据此渲染。\n"
            "virtual_twin region 是 NPC 的家，它和 atrium / store_102 通过 contained_object_ids 共享 NPC。"
        ),
    },
    {
        "key": "mr_npc",
        "name": "MR 眼镜看虚拟 NPC + 物理世界融合",
        "desc": "戴 MR 眼镜时同时看到物理商场和虚拟 NPC。Lin 站在 102 门口招呼你，你走过去和他交谈。",
        "filter": lambda scene: [
            o for o in scene.get("objects", [])
            if o.get("reality") in ("virtual", "mixed")
            or o.get("id") in ("store_102_front", "pillar_03")
        ],
        "actions": [
            "OBSERVE 全局              → MR 眼镜渲染: 物理空间 + 所有 reality=virtual/mixed 物体",
            "OBSERVE npc_merchant_lin   → 看到 Lin 站在 store_102 入口 (bindings.twin_anchor_uri)",
            "NAVIGATE → soap://mall_01/store_102/entrance → 走向 Lin",
            "MANIPULATE npc_merchant_lin (speak) → 语音交互, Lin 回答促销信息",
            "OBSERVE store_102_ai_clerk → 进店后虚拟导购也出现了 (stationed_at store_102_front)",
        ],
        "insight": (
            "MR 渲染器的逻辑：过滤 reality ∈ {virtual, mixed}，按 bindings.twin_anchor_uri 放置。\n"
            "这就是虚实融合的核心 —— SOAP 不做渲染，只告诉渲染器「什么虚拟物体、锚定在哪个物理坐标」。"
        ),
    },
]


def viewer_roles_payload(scene: Dict[str, Any]) -> List[Dict[str, Any]]:
    """供 `soap-view` Web UI 使用的角色视角（可 JSON 序列化）。"""
    out: List[Dict[str, Any]] = []
    for r in ROLES:
        visible = r["filter"](scene)
        out.append(
            {
                "key": r["key"],
                "name": r["name"],
                "desc": r["desc"],
                "actions": r["actions"],
                "insight": r["insight"],
                "visible_object_ids": [o["id"] for o in visible],
            }
        )
    return out


# ── REPL ───────────────────────────────────────────────────────

C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_CYAN = "\033[36m"
C_GREEN = "\033[32m"
C_YELLOW = "\033[33m"
C_DIM = "\033[2m"


def _banner(scene: Dict[str, Any], path: Path) -> str:
    n_obj = len(scene.get("objects", []))
    n_reg = len(scene.get("regions", []))
    n_rel = len(scene.get("relations", []))
    return textwrap.dedent(f"""\
    {C_BOLD}{C_CYAN}
    ╔══════════════════════════════════════════════════════════════╗
    ║        SOAP  Explorer  v0.1  —  六角色思想实验               ║
    ╚══════════════════════════════════════════════════════════════╝{C_RESET}

    {C_GREEN}场景{C_RESET}: {scene.get('title')}
    {C_GREEN}文件{C_RESET}: {path}
    {C_GREEN}统计{C_RESET}: {n_obj} objects, {n_reg} regions, {n_rel} relations

    {C_BOLD}命令{C_RESET}:
      {C_YELLOW}role{C_RESET}                  选择角色视角（交互式）
      {C_YELLOW}role <key>{C_RESET}            直接进入角色 (mr / phone / glasses / robot / npc / mr_npc)
      {C_YELLOW}objects{C_RESET}               列出全部物体
      {C_YELLOW}regions{C_RESET}               列出全部区域
      {C_YELLOW}obj <id>{C_RESET}              查看物体详情
      {C_YELLOW}region <id>{C_RESET}           查看区域及其包含物体
      {C_YELLOW}relations{C_RESET}             列出全部关系
      {C_YELLOW}filter <reality>{C_RESET}      按 reality 过滤 (physical / virtual / mixed)
      {C_YELLOW}aff <affordance>{C_RESET}      按 affordance 过滤 (navigate / speak / scan_qr ...)
      {C_YELLOW}json <id>{C_RESET}             输出物体原始 JSON
      {C_YELLOW}validate{C_RESET}              重新校验当前场景
      {C_YELLOW}help{C_RESET}                  显示此帮助
      {C_YELLOW}quit{C_RESET}                  退出
    """)


def _show_role(role: Dict[str, Any], scene: Dict[str, Any]) -> None:
    print(f"\n{C_BOLD}{C_CYAN}═══ {role['name']} ═══{C_RESET}")
    print(f"{C_DIM}{role['desc']}{C_RESET}\n")
    print(f"{C_BOLD}可见物体:{C_RESET}")
    for o in role["filter"](scene):
        print(_format_obj_brief(o))
    print(f"\n{C_BOLD}可执行动作 (Action Verbs):{C_RESET}")
    for a in role["actions"]:
        print(f"  → {a}")
    print(f"\n{C_BOLD}SOAP 如何支撑:{C_RESET}")
    print(f"  {role['insight']}")
    print()


def _role_menu(scene: Dict[str, Any]) -> None:
    print(f"\n{C_BOLD}选择角色:{C_RESET}")
    for i, r in enumerate(ROLES, 1):
        print(f"  {C_YELLOW}{i}{C_RESET}. [{r['key']:8s}] {r['name']}")
    print(f"  {C_YELLOW}0{C_RESET}. 返回")
    try:
        choice = input(f"\n{C_GREEN}角色编号> {C_RESET}").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return
    if choice == "0":
        return
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(ROLES):
            _show_role(ROLES[idx], scene)
        else:
            print("无效编号")
    except ValueError:
        for r in ROLES:
            if r["key"] == choice:
                _show_role(r, scene)
                return
        print(f"未找到角色 key={choice}")


def repl(scene: Dict[str, Any], path: Path) -> None:
    print(_banner(scene, path))
    while True:
        try:
            raw = input(f"{C_GREEN}soap> {C_RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见，爸爸 ✦")
            break
        if not raw:
            continue
        parts = raw.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if cmd in ("quit", "exit", "q"):
            print("再见，爸爸 ✦")
            break
        elif cmd in ("help", "h", "?"):
            print(_banner(scene, path))
        elif cmd == "role":
            if arg:
                found = False
                for r in ROLES:
                    if r["key"] == arg:
                        _show_role(r, scene)
                        found = True
                        break
                if not found:
                    print(f"未找到角色 key={arg}。可选: {', '.join(r['key'] for r in ROLES)}")
            else:
                _role_menu(scene)
        elif cmd == "objects":
            for o in scene.get("objects", []):
                print(_format_obj_brief(o))
        elif cmd == "regions":
            for r in scene.get("regions", []):
                ids = ", ".join(r.get("contained_object_ids", []))
                print(f'  {r["id"]:20s}  {r.get("name", "")}  ({ids})')
        elif cmd == "obj":
            if not arg:
                print("用法: obj <id>")
                continue
            o = _obj_map(scene).get(arg)
            if o:
                print(_format_obj_detail(o, scene))
            else:
                print(f"未找到: {arg}")
        elif cmd == "region":
            if not arg:
                print("用法: region <id>")
                continue
            r = _region_map(scene).get(arg)
            if not r:
                print(f"未找到: {arg}")
                continue
            print(f'\n── {r["id"]}: {r.get("name")} ──')
            print(f'  URI         : {r.get("uri")}')
            print(f'  purpose_tags: {r.get("purpose_tags")}')
            if r.get("parent_region_id"):
                print(f'  parent      : {r["parent_region_id"]}')
            print(f"  物体:")
            for o in _objects_in_region(scene, arg):
                print(_format_obj_brief(o))
        elif cmd == "relations":
            for rel in scene.get("relations", []):
                print(f'  {rel["from_id"]:30s} --[{rel["relation"]}]--> {rel["to_id"]}')
        elif cmd == "filter":
            if not arg:
                print("用法: filter <physical|virtual|mixed>")
                continue
            results = _objects_by_reality(scene, arg)
            if results:
                for o in results:
                    print(_format_obj_brief(o))
            else:
                print(f"没有 reality={arg} 的物体")
        elif cmd == "aff":
            if not arg:
                print("用法: aff <affordance>")
                continue
            results = _objects_with_affordance(scene, arg)
            if results:
                for o in results:
                    print(_format_obj_brief(o))
            else:
                print(f"没有 affordance={arg} 的物体")
        elif cmd == "json":
            if not arg:
                print("用法: json <object_id>")
                continue
            o = _obj_map(scene).get(arg)
            if o:
                print(json.dumps(o, indent=2, ensure_ascii=False))
            else:
                print(f"未找到: {arg}")
        elif cmd == "validate":
            try:
                validate_scene_file(path)
                print(f"{C_GREEN}✓ 场景校验通过{C_RESET}")
            except Exception as e:
                print(f"\033[31m✗ 校验失败: {e}{C_RESET}")
        else:
            print(f"未知命令: {cmd}（输入 help 查看帮助）")


# ── entry point ────────────────────────────────────────────────

def main() -> None:
    path = _resolve_scene()
    if not path.is_file():
        print(f"场景文件不存在: {path}", file=sys.stderr)
        print("设置环境变量 SOAP_SCENE_PATH 指向 .json 场景文件。", file=sys.stderr)
        sys.exit(1)
    try:
        scene = load_scene(path)
    except Exception as e:
        print(f"场景加载失败: {e}", file=sys.stderr)
        sys.exit(1)
    repl(scene, path)


if __name__ == "__main__":
    main()
