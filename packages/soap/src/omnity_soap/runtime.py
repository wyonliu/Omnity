"""SOAPRuntime — 可变场景图 + 动作执行 + 事件日志。

v0.1 从只读改为可写：外部 Agent（通过 soap-mcp 或 HTTP /api/act）可以
OBSERVE / NAVIGATE / MANIPULATE / REARRANGE，每次执行写入 event_log，
soap-view 通过轮询 /api/events 实时观察。
"""
from __future__ import annotations

import copy
import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from omnity_soap.validate import validate_scene_file


@dataclass
class ActionResult:
    ok: bool
    verb: str
    code: str
    detail: str = ""
    data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"ok": self.ok, "verb": self.verb, "code": self.code}
        if self.detail:
            d["detail"] = self.detail
        if self.data is not None:
            d["data"] = self.data
        return d


@dataclass
class Event:
    seq: int
    ts: float
    agent_id: str
    verb: str
    target_id: str
    params: Dict[str, Any]
    result: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "seq": self.seq,
            "ts": self.ts,
            "agent_id": self.agent_id,
            "verb": self.verb,
            "target_id": self.target_id,
            "params": self.params,
            "result": self.result,
        }


@dataclass
class SOAPRuntime:
    """Mutable in-memory scene graph with action execution and event log."""

    raw: Dict[str, Any]
    space_id: str
    event_log: List[Event] = field(default_factory=list)
    _seq: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @classmethod
    def load(cls, path: Path) -> SOAPRuntime:
        validate_scene_file(path)
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls(raw=copy.deepcopy(raw), space_id=raw["space_id"])

    # ── read API (unchanged) ────────────────────────────────────

    def summary(self) -> Dict[str, Any]:
        return {
            "soap_version": self.raw.get("soap_version"),
            "space_id": self.space_id,
            "title": self.raw.get("title"),
            "object_count": len(self.raw.get("objects", [])),
            "region_count": len(self.raw.get("regions", [])),
            "event_count": len(self.event_log),
        }

    def list_objects(self) -> List[Dict[str, Any]]:
        return list(self.raw.get("objects", []))

    def get_object(self, obj_id: str) -> Optional[Dict[str, Any]]:
        for o in self.list_objects():
            if o.get("id") == obj_id:
                return o
        return None

    def list_regions(self) -> List[Dict[str, Any]]:
        return list(self.raw.get("regions", []))

    def get_region(self, region_id: str) -> Optional[Dict[str, Any]]:
        for r in self.list_regions():
            if r.get("id") == region_id:
                return r
        return None

    def get_events_since(self, after_seq: int = 0) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self.event_log if e.seq > after_seq]

    # ── write: record event ─────────────────────────────────────

    def _record(self, agent_id: str, verb: str, target_id: str,
                params: Dict[str, Any], result: ActionResult) -> Event:
        with self._lock:
            self._seq += 1
            ev = Event(
                seq=self._seq, ts=time.time(), agent_id=agent_id,
                verb=verb, target_id=target_id, params=params,
                result=result.to_dict(),
            )
            self.event_log.append(ev)
            return ev

    # ── action verbs ────────────────────────────────────────────

    def observe(self, agent_id: str, target_id: str) -> ActionResult:
        """OBSERVE — 返回目标物体/区域的感知摘要。"""
        obj = self.get_object(target_id)
        if obj is not None:
            snapshot = {
                "id": obj["id"],
                "type": obj.get("type"),
                "reality": obj.get("reality"),
                "affordances": obj.get("affordances", []),
                "state": obj.get("state"),
                "bounds": obj.get("bounds"),
            }
            res = ActionResult(ok=True, verb="OBSERVE", code="OK", data=snapshot)
            self._record(agent_id, "OBSERVE", target_id, {}, res)
            return res

        region = self.get_region(target_id)
        if region is not None:
            objs_in = []
            obj_map = {o["id"]: o for o in self.list_objects()}
            for oid in region.get("contained_object_ids", []):
                o = obj_map.get(oid)
                if o:
                    objs_in.append({
                        "id": o["id"], "type": o.get("type"),
                        "reality": o.get("reality"),
                    })
            snapshot = {
                "id": region["id"],
                "name": region.get("name"),
                "purpose_tags": region.get("purpose_tags", []),
                "objects": objs_in,
            }
            res = ActionResult(ok=True, verb="OBSERVE", code="OK", data=snapshot)
            self._record(agent_id, "OBSERVE", target_id, {}, res)
            return res

        res = ActionResult(ok=False, verb="OBSERVE", code="NOT_FOUND",
                           detail=f"No object or region with id '{target_id}'")
        self._record(agent_id, "OBSERVE", target_id, {}, res)
        return res

    def navigate(self, agent_id: str, object_id: str, target_uri: str) -> ActionResult:
        """NAVIGATE — 移动物体到目标 URI 所指位置（更新 bounds 中心）。

        如果 object_id 是区域而非物体，视为 agent 自身移动到该区域（记录事件但不修改场景几何）。
        """
        obj = self.get_object(object_id)
        if obj is None:
            region = self.get_region(object_id)
            if region is not None:
                res = ActionResult(
                    ok=True, verb="NAVIGATE", code="OK",
                    detail=f"Agent {agent_id} navigated to region '{object_id}' ({region.get('name', '')})",
                    data={"agent_id": agent_id, "region_id": object_id,
                          "target_uri": target_uri or region.get("uri", ""),
                          "region_name": region.get("name", ""),
                          "contained_objects": region.get("contained_object_ids", [])})
                self._record(agent_id, "NAVIGATE", object_id, {"target_uri": target_uri}, res)
                return res
            res = ActionResult(ok=False, verb="NAVIGATE", code="UNKNOWN_OBJECT",
                               detail=f"'{object_id}' is neither an object nor a region")
            self._record(agent_id, "NAVIGATE", object_id, {"target_uri": target_uri}, res)
            return res
        if not target_uri.startswith("soap://"):
            res = ActionResult(ok=False, verb="NAVIGATE", code="INVALID_URI",
                               detail="target_uri must start with soap://")
            self._record(agent_id, "NAVIGATE", object_id, {"target_uri": target_uri}, res)
            return res

        target_obj_id = target_uri.rsplit("/", 1)[-1]
        anchor = self.get_object(target_obj_id)
        anchor_region = self.get_region(target_obj_id)

        dest_desc = target_uri
        if anchor and anchor.get("bounds", {}).get("min"):
            b = anchor["bounds"]
            cx = (b["min"][0] + b["max"][0]) / 2
            cy = (b["min"][1] + b["max"][1]) / 2
            cz = (b["min"][2] + b["max"][2]) / 2
            offset = 1.5
            new_bounds = {
                "type": "aabb",
                "min": [round(cx + offset, 2), round(cy, 2), round(cz, 2)],
                "max": [round(cx + offset + 1.0, 2), round(cy + 1.8, 2), round(cz + 1.0, 2)],
            }
            obj["bounds"] = new_bounds
            dest_desc = f"near {target_obj_id} at [{cx+offset:.1f}, {cy:.1f}, {cz:.1f}]"

        obj.setdefault("state", {})["last_navigate_target"] = target_uri

        res = ActionResult(ok=True, verb="NAVIGATE", code="OK",
                           detail=f"{object_id} moved to {dest_desc}",
                           data={"object_id": object_id, "target_uri": target_uri,
                                 "new_bounds": obj.get("bounds")})
        self._record(agent_id, "NAVIGATE", object_id, {"target_uri": target_uri}, res)
        return res

    def manipulate(self, agent_id: str, object_id: str, action: str,
                   params: Optional[Dict[str, Any]] = None) -> ActionResult:
        """MANIPULATE — 对物体执行一个 affordance 动作。"""
        params = params or {}
        obj = self.get_object(object_id)
        if obj is None:
            res = ActionResult(ok=False, verb="MANIPULATE", code="UNKNOWN_OBJECT",
                               detail=f"Object '{object_id}' not found")
            self._record(agent_id, "MANIPULATE", object_id,
                         {"action": action, **params}, res)
            return res

        affordances = obj.get("affordances", [])
        if action not in affordances:
            res = ActionResult(ok=False, verb="MANIPULATE", code="NOT_AFFORDED",
                               detail=f"'{action}' not in affordances {affordances}")
            self._record(agent_id, "MANIPULATE", object_id,
                         {"action": action, **params}, res)
            return res

        state = obj.setdefault("state", {})
        response_data: Dict[str, Any] = {"object_id": object_id, "action": action}

        if action == "speak":
            message = params.get("message", "")
            npc_type = obj.get("type", "")
            mood = state.get("mood", "neutral")
            if "npc" in npc_type:
                reply = self._npc_reply(obj, message)
                response_data["reply"] = reply
                response_data["mood"] = mood
            else:
                response_data["reply"] = f"[{object_id} 无法说话]"

        elif action == "attack_target":
            hp = state.get("hp", 0)
            damage = params.get("damage", 25)
            hp = max(0, hp - damage)
            state["hp"] = hp
            response_data["hp_remaining"] = hp
            response_data["damage_dealt"] = damage
            if hp == 0:
                state["status"] = "defeated"
                response_data["defeated"] = True
                if "drop_loot" in affordances:
                    response_data["loot_dropped"] = True

        elif action == "scan_qr":
            twin_url = obj.get("bindings", {}).get("digital_twin_url", "")
            response_data["digital_twin_url"] = twin_url

        elif action == "recommend":
            promo = state.get("current_promo", "")
            response_data["recommendation"] = f"当前促销: {promo}" if promo else "暂无促销"

        elif action in ("navigate", "navigate_through"):
            state["status"] = "in_use"
            response_data["status"] = "navigating"

        elif action == "make_coffee":
            state["current_task"] = "making_coffee"
            response_data["status"] = "brewing"

        elif action in ("clean_floor", "carry", "dock"):
            state["status"] = action
            response_data["status"] = action

        else:
            state[f"last_{action}"] = time.time()
            response_data["executed"] = True

        res = ActionResult(ok=True, verb="MANIPULATE", code="OK",
                           detail=f"{action} on {object_id}", data=response_data)
        self._record(agent_id, "MANIPULATE", object_id,
                     {"action": action, **params}, res)
        return res

    def _npc_reply(self, obj: Dict[str, Any], message: str) -> str:
        """NPC 简单响应逻辑，展示 SOAP 的 state/bindings 如何驱动对话上下文。"""
        name = obj["id"]
        mood = obj.get("state", {}).get("mood", "neutral")
        task = obj.get("state", {}).get("current_task", "idle")
        obj_type = obj.get("type", "")

        if "barista" in name or "coffee" in obj_type:
            if "coffee" in message.lower() or "拿铁" in message or "咖啡" in message:
                return f"[{name}] (mood={mood}) 好的，一杯拿铁马上来！我正在 {task}。"
            return f"[{name}] (mood={mood}) 欢迎光临！要来杯咖啡吗？我现在 {task}。"

        if "merchant" in name or "clerk" in name:
            promo = obj.get("state", {}).get("current_promo", "")
            if promo:
                return f"[{name}] (mood={mood}) 您好！今天有活动：{promo}。需要帮您推荐什么吗？"
            return f"[{name}] (mood={mood}) 您好，有什么可以帮您的？"

        return f"[{name}] (mood={mood}, task={task}) 你好！"

    def execute_action(self, agent_id: str, verb: str, target_id: str,
                       params: Optional[Dict[str, Any]] = None) -> ActionResult:
        """统一入口：根据 verb 分发到具体方法。"""
        params = params or {}
        v = verb.upper()
        if v == "OBSERVE":
            return self.observe(agent_id, target_id)
        elif v == "NAVIGATE":
            return self.navigate(agent_id, target_id, params.get("target_uri", ""))
        elif v == "MANIPULATE":
            return self.manipulate(agent_id, target_id, params.get("action", ""), params)
        elif v == "REARRANGE":
            res = ActionResult(ok=False, verb="REARRANGE", code="NOT_IMPLEMENTED",
                               detail="REARRANGE requires a planner (v0.2+)")
            self._record(agent_id, "REARRANGE", target_id, params, res)
            return res
        else:
            res = ActionResult(ok=False, verb=verb, code="UNKNOWN_VERB",
                               detail=f"Unknown verb '{verb}'. Use OBSERVE/NAVIGATE/MANIPULATE/REARRANGE.")
            self._record(agent_id, verb, target_id, params, res)
            return res
