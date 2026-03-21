"""测试 SOAPRuntime 的可写动作：OBSERVE / NAVIGATE / MANIPULATE + 事件日志。"""
from pathlib import Path

from omnity_soap.runtime import SOAPRuntime

MALL = Path(__file__).resolve().parent.parent / "examples" / "mall-mixed-reality.json"


def _rt() -> SOAPRuntime:
    return SOAPRuntime.load(MALL)


def test_observe_object():
    rt = _rt()
    res = rt.observe("test_agent", "fountain_center")
    assert res.ok
    assert res.code == "OK"
    assert res.data["id"] == "fountain_center"
    assert res.data["type"] == "decor.fountain"
    assert len(rt.event_log) == 1
    assert rt.event_log[0].verb == "OBSERVE"


def test_observe_region():
    rt = _rt()
    res = rt.observe("test_agent", "atrium")
    assert res.ok
    assert res.data["name"] == "中庭"
    assert len(res.data["objects"]) > 0


def test_observe_not_found():
    rt = _rt()
    res = rt.observe("test_agent", "nonexistent")
    assert not res.ok
    assert res.code == "NOT_FOUND"


def test_navigate_moves_object():
    rt = _rt()
    res = rt.navigate("test_agent", "npc_merchant_lin",
                       "soap://mall_01/cafe_201/counter")
    assert res.ok
    obj = rt.get_object("npc_merchant_lin")
    assert obj.get("bounds") is not None
    assert obj["state"]["last_navigate_target"] == "soap://mall_01/cafe_201/counter"


def test_navigate_unknown_object():
    rt = _rt()
    res = rt.navigate("test_agent", "ghost", "soap://mall_01/atrium")
    assert not res.ok
    assert res.code == "UNKNOWN_OBJECT"


def test_manipulate_speak():
    rt = _rt()
    res = rt.manipulate("test_agent", "npc_merchant_lin", "speak",
                         {"message": "你好"})
    assert res.ok
    assert "reply" in res.data
    assert "您好" in res.data["reply"] or "你好" in res.data["reply"]


def test_manipulate_attack():
    rt = _rt()
    res = rt.manipulate("test_agent", "game_monster_01", "attack_target",
                         {"damage": 50})
    assert res.ok
    assert res.data["hp_remaining"] == 70
    res2 = rt.manipulate("test_agent", "game_monster_01", "attack_target",
                          {"damage": 80})
    assert res2.ok
    assert res2.data["hp_remaining"] == 0
    assert res2.data["defeated"] is True


def test_manipulate_not_afforded():
    rt = _rt()
    res = rt.manipulate("test_agent", "fountain_center", "fly", {})
    assert not res.ok
    assert res.code == "NOT_AFFORDED"


def test_event_log_sequential():
    rt = _rt()
    rt.observe("a1", "fountain_center")
    rt.observe("a2", "atrium")
    rt.manipulate("a1", "npc_barista_chen", "speak", {"message": "hi"})
    assert len(rt.event_log) == 3
    assert rt.event_log[0].seq == 1
    assert rt.event_log[2].seq == 3
    since2 = rt.get_events_since(1)
    assert len(since2) == 2


def test_execute_action_dispatch():
    rt = _rt()
    res = rt.execute_action("agent", "OBSERVE", "fountain_center")
    assert res.ok
    res = rt.execute_action("agent", "NAVIGATE", "robot_unit_d",
                             {"target_uri": "soap://mall_01/atrium/pillar_03"})
    assert res.ok
    res = rt.execute_action("agent", "MANIPULATE", "store_102_front",
                             {"action": "scan_qr"})
    assert res.ok
    assert "digital_twin_url" in res.data
    res = rt.execute_action("agent", "REARRANGE", "atrium")
    assert not res.ok
    assert res.code == "NOT_IMPLEMENTED"
