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
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

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
class AgentRecord:
    """Registered agent with presence tracking."""
    id: str
    agent_type: str  # "human" | "autonomous" | "npc" | "robot" | "unknown"
    capabilities: List[str] = field(default_factory=list)
    position: Optional[List[float]] = None
    near_target: str = "atrium"
    meta: Dict[str, Any] = field(default_factory=dict)
    registered_at: float = 0.0
    last_heartbeat: float = 0.0
    status: str = "active"  # "active" | "stale" | "disconnected"
    hp: int = 100
    action_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "id": self.id, "agent_type": self.agent_type,
            "capabilities": self.capabilities,
            "near_target": self.near_target,
            "status": self.status, "hp": self.hp,
            "action_count": self.action_count,
            "registered_at": self.registered_at,
            "last_heartbeat": self.last_heartbeat,
        }
        if self.position:
            d["position"] = self.position
        if self.meta:
            d["meta"] = self.meta
        return d


@dataclass
class LockRecord:
    """Advisory lock on an object."""
    object_id: str
    agent_id: str
    lock_id: str
    acquired_at: float
    ttl: float
    expires_at: float

    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "object_id": self.object_id, "agent_id": self.agent_id,
            "lock_id": self.lock_id, "acquired_at": self.acquired_at,
            "ttl": self.ttl, "expires_at": self.expires_at,
            "expired": self.is_expired(),
        }


@dataclass
class SOAPRuntime:
    """Mutable in-memory scene graph with action execution and event log."""

    raw: Dict[str, Any]
    space_id: str
    event_log: List[Event] = field(default_factory=list)
    _seq: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _agents: Dict[str, Dict[str, Any]] = field(default_factory=dict, repr=False)
    _agent_registry: Dict[str, AgentRecord] = field(default_factory=dict, repr=False)
    _object_locks: Dict[str, LockRecord] = field(default_factory=dict, repr=False)
    _event_listeners: List[Callable] = field(default_factory=list, repr=False)

    @classmethod
    def load(cls, path: Path) -> SOAPRuntime:
        validate_scene_file(path)
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls(raw=copy.deepcopy(raw), space_id=raw["space_id"])

    # ── agent tracking ─────────────────────────────────────────

    def _touch_agent(self, agent_id: str, near_target: Optional[str] = None) -> Dict[str, Any]:
        """Ensure agent is tracked; update position if given."""
        ag = self._agents.setdefault(agent_id, {
            "id": agent_id, "hp": 100, "status": "active",
            "near_target": "atrium", "action_count": 0,
        })
        ag["action_count"] = ag.get("action_count", 0) + 1
        ag["last_active"] = time.time()
        if near_target:
            ag["near_target"] = near_target
        return ag

    def list_agents(self) -> List[Dict[str, Any]]:
        # Prefer registry records; fall back to legacy _agents
        if self._agent_registry:
            return [ar.to_dict() for ar in self._agent_registry.values()]
        return list(self._agents.values())

    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        ar = self._agent_registry.get(agent_id)
        if ar:
            return ar.to_dict()
        return self._agents.get(agent_id)

    # ── agent registry ────────────────────────────────────────

    def register_agent(self, agent_id: str, agent_type: str = "unknown",
                       capabilities: Optional[List[str]] = None,
                       position: Optional[List[float]] = None,
                       meta: Optional[Dict[str, Any]] = None) -> AgentRecord:
        """Register an agent. Raises ValueError if already registered."""
        if agent_id in self._agent_registry:
            raise ValueError(f"Agent '{agent_id}' already registered")
        now = time.time()
        ar = AgentRecord(
            id=agent_id, agent_type=agent_type,
            capabilities=capabilities or [],
            position=position, meta=meta or {},
            registered_at=now, last_heartbeat=now,
        )
        self._agent_registry[agent_id] = ar
        # also track in legacy dict for backward compat
        self._agents[agent_id] = ar.to_dict()
        self._notify_listeners("agent.registered", {"agent": ar.to_dict()})
        return ar

    def deregister_agent(self, agent_id: str) -> bool:
        """Remove agent. Returns True if found."""
        ar = self._agent_registry.pop(agent_id, None)
        self._agents.pop(agent_id, None)
        if ar:
            self._notify_listeners("agent.deregistered", {"agent_id": agent_id})
            return True
        return False

    def heartbeat(self, agent_id: str, position: Optional[List[float]] = None,
                  status: str = "active") -> bool:
        """Update agent heartbeat. Returns False if not registered.
        Auto-updates region if position changed."""
        ar = self._agent_registry.get(agent_id)
        if not ar:
            return False
        ar.last_heartbeat = time.time()
        ar.status = status
        if position:
            ar.position = position
            # auto-resolve region from new position
            self.update_agent_region(agent_id, position=position)
        # sync legacy
        self._agents[agent_id] = ar.to_dict()
        return True

    def get_registered_agent(self, agent_id: str) -> Optional[AgentRecord]:
        return self._agent_registry.get(agent_id)

    def nearby_agents(self, agent_id: str, radius: float = 10.0) -> List[Dict[str, Any]]:
        """Return agents near the given agent (same region or with close positions)."""
        me = self._agent_registry.get(agent_id)
        if not me:
            return []
        results = []
        for ar in self._agent_registry.values():
            if ar.id == agent_id or ar.status == "disconnected":
                continue
            # position-based distance
            if me.position and ar.position and len(me.position) >= 3 and len(ar.position) >= 3:
                dx = me.position[0] - ar.position[0]
                dy = me.position[1] - ar.position[1]
                dz = me.position[2] - ar.position[2]
                dist = (dx*dx + dy*dy + dz*dz) ** 0.5
                if dist <= radius:
                    results.append(ar.to_dict())
                continue
            # fallback: same near_target
            if me.near_target and me.near_target == ar.near_target:
                results.append(ar.to_dict())
        return results

    def resolve_region_for_position(self, position: List[float]) -> Optional[str]:
        """Find which region contains the given position (by checking object bounds in region)."""
        if not position or len(position) < 3:
            return None
        x, y, z = position[0], position[1], position[2]
        for region in self.list_regions():
            for oid in region.get("contained_object_ids", []):
                obj = self.get_object(oid)
                if obj and "bounds" in obj:
                    b = obj["bounds"]
                    mn, mx = b.get("min", []), b.get("max", [])
                    if len(mn) >= 3 and len(mx) >= 3:
                        # expand region check by generous margin (20m around any object in region)
                        margin = 20.0
                        if (mn[0] - margin <= x <= mx[0] + margin and
                            mn[2] - margin <= z <= mx[2] + margin):
                            return region["id"]
        return None

    def update_agent_region(self, agent_id: str, new_region: Optional[str] = None,
                            position: Optional[List[float]] = None) -> Optional[str]:
        """Update agent's region. Auto-resolves from position if new_region not given.
        Fires region.entered/region.exited events on change. Returns new region_id."""
        ar = self._agent_registry.get(agent_id)
        if not ar:
            return None
        if not new_region and position:
            new_region = self.resolve_region_for_position(position)
        if not new_region:
            return ar.near_target
        old_region = ar.near_target
        if old_region != new_region:
            ar.near_target = new_region
            self._agents[agent_id] = ar.to_dict()
            if old_region:
                self._notify_listeners("region.exited", {
                    "agent_id": agent_id, "region_id": old_region,
                })
            self._notify_listeners("region.entered", {
                "agent_id": agent_id, "region_id": new_region,
            })
        return new_region

    def query_agents(self, agent_type: Optional[str] = None,
                     capability: Optional[str] = None,
                     region_id: Optional[str] = None,
                     status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Query agents by type, capability, region, or status."""
        results = []
        for ar in self._agent_registry.values():
            if agent_type and ar.agent_type != agent_type:
                continue
            if capability and capability not in ar.capabilities:
                continue
            if region_id and ar.near_target != region_id:
                continue
            if status and ar.status != status:
                continue
            results.append(ar.to_dict())
        return results

    def reap_stale_agents(self, heartbeat_ttl: float = 30.0) -> List[str]:
        """Mark agents stale/disconnected based on heartbeat TTL. Returns changed IDs."""
        now = time.time()
        changed = []
        for ar in list(self._agent_registry.values()):
            elapsed = now - ar.last_heartbeat
            if ar.status == "active" and elapsed > heartbeat_ttl:
                ar.status = "stale"
                self._agents[ar.id] = ar.to_dict()
                changed.append(ar.id)
            elif ar.status == "stale" and elapsed > heartbeat_ttl * 2:
                ar.status = "disconnected"
                self._agents[ar.id] = ar.to_dict()
                changed.append(ar.id)
        if changed:
            self._notify_listeners("agents.status_changed",
                                   {"agent_ids": changed})
        return changed

    # ── object locking ────────────────────────────────────────

    def acquire_lock(self, object_id: str, agent_id: str,
                     ttl: float = 30.0) -> Optional[LockRecord]:
        """Acquire advisory lock. Returns None if already held by another agent."""
        with self._lock:
            existing = self._object_locks.get(object_id)
            if existing and not existing.is_expired() and existing.agent_id != agent_id:
                return None  # held by someone else
            now = time.time()
            lr = LockRecord(
                object_id=object_id, agent_id=agent_id,
                lock_id=str(uuid.uuid4()), acquired_at=now,
                ttl=ttl, expires_at=now + ttl,
            )
            self._object_locks[object_id] = lr
        # notify outside lock to avoid deadlocks
        self._notify_listeners("lock.acquired", lr.to_dict())
        return lr

    def release_lock(self, object_id: str, agent_id: str) -> bool:
        """Release lock. Only the holder can release."""
        with self._lock:
            lr = self._object_locks.get(object_id)
            if not lr:
                return False
            if lr.agent_id != agent_id and not lr.is_expired():
                return False
            self._object_locks.pop(object_id, None)
        # notify outside lock to avoid deadlocks
        self._notify_listeners("lock.released",
                               {"object_id": object_id, "agent_id": agent_id})
        return True

    def check_lock(self, object_id: str) -> Optional[LockRecord]:
        """Check lock status. Auto-clears expired locks."""
        expired_data = None
        with self._lock:
            lr = self._object_locks.get(object_id)
            if lr and lr.is_expired():
                self._object_locks.pop(object_id, None)
                expired_data = lr.to_dict()
                lr = None  # cleared
        # notify outside lock to avoid deadlocks
        if expired_data is not None:
            self._notify_listeners("lock.expired", expired_data)
        return lr

    def _check_lock_for_manipulate(self, object_id: str, agent_id: str) -> Optional[ActionResult]:
        """Returns LOCK_HELD ActionResult if object is locked by another agent, else None."""
        lr = self.check_lock(object_id)
        if lr and lr.agent_id != agent_id:
            return ActionResult(
                ok=False, verb="MANIPULATE", code="LOCK_HELD",
                detail=f"Object '{object_id}' is locked by agent '{lr.agent_id}' until {lr.expires_at}",
            )
        return None

    # ── event listeners ───────────────────────────────────────

    def add_event_listener(self, callback: Callable) -> None:
        self._event_listeners.append(callback)

    def remove_event_listener(self, callback: Callable) -> None:
        try:
            self._event_listeners.remove(callback)
        except ValueError:
            pass

    def _notify_listeners(self, topic: str, data: Any) -> None:
        for cb in self._event_listeners:
            try:
                cb(topic, data)
            except Exception:
                pass

    # ── read API ──────────────────────────────────────────────

    def summary(self) -> Dict[str, Any]:
        return {
            "soap_version": self.raw.get("soap_version"),
            "space_id": self.space_id,
            "title": self.raw.get("title"),
            "object_count": len(self.raw.get("objects", [])),
            "region_count": len(self.raw.get("regions", [])),
            "agent_count": len(self._agents),
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

    # ── S4: spatial query & discovery ──────────────────────────

    def query_objects(self, *,
                      obj_type: Optional[str] = None,
                      reality: Optional[str] = None,
                      affordance: Optional[str] = None,
                      tag: Optional[str] = None,
                      region_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search objects by type, reality, affordance, tag, or region."""
        # resolve region → contained object IDs
        region_oids: Optional[set] = None
        if region_id:
            region = self.get_region(region_id)
            if not region:
                return []
            region_oids = set(region.get("contained_object_ids", []))

        results = []
        for obj in self.list_objects():
            if region_oids is not None and obj["id"] not in region_oids:
                continue
            if obj_type and obj.get("type") != obj_type:
                continue
            if reality and obj.get("reality") != reality:
                continue
            if affordance and affordance not in obj.get("affordances", []):
                continue
            if tag and tag not in obj.get("tags", []):
                continue
            results.append(obj)
        return results

    def spatial_query(self, *,
                      center: Optional[List[float]] = None,
                      radius: Optional[float] = None,
                      bbox_min: Optional[List[float]] = None,
                      bbox_max: Optional[List[float]] = None) -> List[Dict[str, Any]]:
        """Query objects by spatial proximity (sphere or AABB).

        - Sphere: center + radius
        - AABB: bbox_min + bbox_max
        Objects without bounds are excluded.
        """
        results = []
        for obj in self.list_objects():
            bounds = obj.get("bounds", {})
            obj_min = bounds.get("min")
            obj_max = bounds.get("max")
            if not obj_min or not obj_max or len(obj_min) < 3 or len(obj_max) < 3:
                continue
            obj_cx = (obj_min[0] + obj_max[0]) / 2
            obj_cy = (obj_min[1] + obj_max[1]) / 2
            obj_cz = (obj_min[2] + obj_max[2]) / 2

            if center and radius is not None:
                if len(center) < 3:
                    continue
                dx = obj_cx - center[0]
                dy = obj_cy - center[1]
                dz = obj_cz - center[2]
                dist = (dx*dx + dy*dy + dz*dz) ** 0.5
                if dist > radius:
                    continue
            elif bbox_min and bbox_max:
                if len(bbox_min) < 3 or len(bbox_max) < 3:
                    continue
                # AABB overlap test (object center must be inside query box)
                if not (bbox_min[0] <= obj_cx <= bbox_max[0] and
                        bbox_min[1] <= obj_cy <= bbox_max[1] and
                        bbox_min[2] <= obj_cz <= bbox_max[2]):
                    continue
            else:
                continue  # need either sphere or bbox query

            results.append(obj)
        return results

    def region_inventory(self, region_id: str) -> Optional[Dict[str, Any]]:
        """Get region summary with all contained objects and their states."""
        region = self.get_region(region_id)
        if not region:
            return None
        obj_map = {o["id"]: o for o in self.list_objects()}
        items = []
        for oid in region.get("contained_object_ids", []):
            obj = obj_map.get(oid)
            if obj:
                items.append({
                    "id": obj["id"],
                    "type": obj.get("type"),
                    "reality": obj.get("reality"),
                    "affordances": obj.get("affordances", []),
                    "state": obj.get("state"),
                })
        agents_here = [ar.to_dict() for ar in self._agent_registry.values()
                       if ar.near_target == region_id and ar.status != "disconnected"]
        return {
            "region_id": region_id,
            "name": region.get("name"),
            "purpose_tags": region.get("purpose_tags", []),
            "object_count": len(items),
            "objects": items,
            "agent_count": len(agents_here),
            "agents": agents_here,
        }

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
        # notify outside lock to avoid deadlocks
        self._notify_listeners("events", ev.to_dict())
        return ev

    # ── action verbs ────────────────────────────────────────────

    def observe(self, agent_id: str, target_id: str) -> ActionResult:
        """OBSERVE — 返回目标物体/区域/agent 的感知摘要。"""
        self._touch_agent(agent_id, near_target=target_id)

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
            agents_here = [a for a in self._agents.values()
                           if a.get("near_target") in
                           ([region["id"]] + region.get("contained_object_ids", []))]
            snapshot = {
                "id": region["id"],
                "name": region.get("name"),
                "purpose_tags": region.get("purpose_tags", []),
                "objects": objs_in,
                "agents": [{"id": a["id"], "hp": a.get("hp"), "status": a.get("status")}
                           for a in agents_here if a["id"] != agent_id],
            }
            res = ActionResult(ok=True, verb="OBSERVE", code="OK", data=snapshot)
            self._record(agent_id, "OBSERVE", target_id, {}, res)
            return res

        target_agent = self.get_agent(target_id)
        if target_agent is not None:
            snapshot = {
                "id": target_agent["id"],
                "type": "agent",
                "hp": target_agent.get("hp", 100),
                "status": target_agent.get("status", "active"),
                "near_target": target_agent.get("near_target"),
                "action_count": target_agent.get("action_count", 0),
            }
            res = ActionResult(ok=True, verb="OBSERVE", code="OK", data=snapshot)
            self._record(agent_id, "OBSERVE", target_id, {}, res)
            return res

        res = ActionResult(ok=False, verb="OBSERVE", code="NOT_FOUND",
                           detail=f"No object, region, or agent with id '{target_id}'")
        self._record(agent_id, "OBSERVE", target_id, {}, res)
        return res

    def navigate(self, agent_id: str, object_id: str, target_uri: str) -> ActionResult:
        """NAVIGATE — 移动物体到目标 URI 所指位置（更新 bounds 中心）。

        如果 object_id 是区域而非物体，视为 agent 自身移动到该区域（记录事件但不修改场景几何）。
        """
        self._touch_agent(agent_id, near_target=object_id)
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
        """MANIPULATE — 对物体或 agent 执行动作。"""
        params = params or {}
        self._touch_agent(agent_id)

        # Advisory lock check
        lock_err = self._check_lock_for_manipulate(object_id, agent_id)
        if lock_err:
            self._record(agent_id, "MANIPULATE", object_id,
                         {"action": action, **params}, lock_err)
            return lock_err

        target_agent = self.get_agent(object_id)
        if target_agent is not None and object_id != agent_id:
            return self._manipulate_agent(agent_id, target_agent, action, params)

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

    def _manipulate_agent(self, agent_id: str, target: Dict[str, Any],
                          action: str, params: Dict[str, Any]) -> ActionResult:
        """Handle MANIPULATE actions targeting another agent."""
        tid = target["id"]
        response_data: Dict[str, Any] = {"object_id": tid, "action": action, "is_agent": True}

        if action == "attack_target":
            damage = params.get("damage", 25)
            hp = target.get("hp", 100)
            hp = max(0, hp - damage)
            target["hp"] = hp
            response_data["hp_remaining"] = hp
            response_data["damage_dealt"] = damage
            if hp == 0:
                target["status"] = "defeated"
                response_data["defeated"] = True
            else:
                target["status"] = "interrupted"
                response_data["interrupted"] = True

        elif action == "speak":
            msg = params.get("message", "")
            response_data["reply"] = f"[{tid}] 嗯？谁在跟我说话……「{msg}」"
            target["status"] = "interrupted"
            response_data["interrupted"] = True

        else:
            response_data["reply"] = f"[{tid}] 对 agent 执行了 {action}"

        res = ActionResult(ok=True, verb="MANIPULATE", code="OK",
                           detail=f"{action} on agent {tid}", data=response_data)
        self._record(agent_id, "MANIPULATE", tid, {"action": action, **params}, res)
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
