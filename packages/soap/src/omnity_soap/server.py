"""SOAP Server — FastAPI + WebSocket transport for SOAP Runtime.

Implements SOAP Transport Spec v0.1:
- RESTful API at /api/v1/*
- WebSocket real-time events at /ws
- Agent registration, presence, nearby query
- Advisory object locking
- Backward-compatible legacy endpoints at /api/*
"""
import argparse
import asyncio
import json
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field, field_validator

from omnity_soap.paths import default_scene_path, viewer_static_dir, package_root
from omnity_soap.runtime import SOAPRuntime

# ── Pydantic models ────────────────────────────────────────────

class ActionRequest(BaseModel):
    agent_id: str = "anonymous"
    verb: str
    target_id: str
    params: Dict[str, Any] = Field(default_factory=dict)

class AgentRegisterRequest(BaseModel):
    agent_id: str
    agent_type: str = "unknown"
    capabilities: List[str] = Field(default_factory=list)
    position: Optional[List[float]] = None
    meta: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("agent_id")
    @classmethod
    def agent_id_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("agent_id must not be empty")
        return v

    @field_validator("position")
    @classmethod
    def position_length(cls, v: Optional[List[float]]) -> Optional[List[float]]:
        if v is not None and len(v) < 3:
            raise ValueError("position must have at least 3 elements [x, y, z]")
        return v

class HeartbeatRequest(BaseModel):
    position: Optional[List[float]] = None
    status: str = "active"

    @field_validator("position")
    @classmethod
    def position_length(cls, v: Optional[List[float]]) -> Optional[List[float]]:
        if v is not None and len(v) < 3:
            raise ValueError("position must have at least 3 elements [x, y, z]")
        return v

class LockRequest(BaseModel):
    agent_id: str
    ttl_seconds: float = 30.0

    @field_validator("agent_id")
    @classmethod
    def agent_id_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("agent_id must not be empty")
        return v

    @field_validator("ttl_seconds")
    @classmethod
    def ttl_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("ttl_seconds must be positive")
        if v > 3600:
            raise ValueError("ttl_seconds must not exceed 3600")
        return v

class LegacyActionRequest(BaseModel):
    agent_id: str = "anonymous"
    verb: str = ""
    target_id: str = ""
    params: Dict[str, Any] = Field(default_factory=dict)

# ── WebSocket Manager ──────────────────────────────────────────

class ConnectionManager:
    """Track WebSocket connections and their topic subscriptions."""

    def __init__(self) -> None:
        self._connections: Dict[str, Any] = {}  # ws_id -> {"ws": ws, "agent_id": str, "topics": set}
        self._lock = asyncio.Lock()
        self._counter = 0

    async def connect(self, ws: Any, agent_id: str, topics: Set[str]) -> str:
        async with self._lock:
            self._counter += 1
            ws_id = f"ws_{self._counter}"
            self._connections[ws_id] = {
                "ws": ws, "agent_id": agent_id, "topics": topics,
            }
            return ws_id

    async def disconnect(self, ws_id: str) -> Optional[str]:
        async with self._lock:
            conn = self._connections.pop(ws_id, None)
            return conn["agent_id"] if conn else None

    async def update_topics(self, ws_id: str, add: Optional[Set[str]] = None,
                            remove: Optional[Set[str]] = None) -> None:
        add = add or set()
        remove = remove or set()
        async with self._lock:
            conn = self._connections.get(ws_id)
            if conn:
                conn["topics"] |= add
                conn["topics"] -= remove

    async def broadcast(self, topic: str, data: Any) -> None:
        """Send to all connections subscribed to this topic."""
        msg = json.dumps({"type": "event", "topic": topic, "data": data},
                         ensure_ascii=False)
        async with self._lock:
            targets = [c["ws"] for c in self._connections.values()
                       if topic in c["topics"]]
        for ws in targets:
            try:
                await ws.send_text(msg)
            except Exception:
                pass

    async def send_to(self, ws_id: str, data: Any) -> None:
        async with self._lock:
            conn = self._connections.get(ws_id)
        if conn:
            try:
                await conn["ws"].send_text(
                    json.dumps(data, ensure_ascii=False))
            except Exception:
                pass


# ── App Factory ────────────────────────────────────────────────

def create_app(scene_path: Optional[Path] = None):
    """Create a SOAP Server FastAPI application."""
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import JSONResponse

    rt: Optional[SOAPRuntime] = None
    mgr = ConnectionManager()
    _reaper_task: Optional[asyncio.Task] = None

    def _get_rt() -> SOAPRuntime:
        nonlocal rt
        if rt is None:
            p = scene_path or default_scene_path()
            rt = SOAPRuntime.load(p)
            # wire event listener to broadcast via WebSocket
            rt.add_event_listener(_on_runtime_event)
        return rt

    def _on_runtime_event(topic: str, data: Any) -> None:
        """Bridge sync runtime events to async WebSocket broadcast."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(mgr.broadcast(topic, data))
        except RuntimeError:
            pass  # no event loop (e.g. in tests without async)

    async def _heartbeat_reaper() -> None:
        """Background task: reap stale agents every 10s."""
        while True:
            await asyncio.sleep(10)
            try:
                r = _get_rt()
                changed = r.reap_stale_agents()
                if changed:
                    await mgr.broadcast("agents", {
                        "type": "agents.status_changed",
                        "agent_ids": changed,
                    })
            except Exception:
                pass

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        nonlocal _reaper_task
        _reaper_task = asyncio.create_task(_heartbeat_reaper())
        yield
        _reaper_task.cancel()
        try:
            await _reaper_task
        except asyncio.CancelledError:
            pass

    app = FastAPI(
        title="SOAP Server",
        version="0.1.0",
        description="Spatial Omnity Agentic Protocol — HTTP + WebSocket Transport",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── V1 endpoints ──────────────────────────────────────────

    # Scene
    @app.get("/api/v1/scene")
    def v1_scene():
        r = _get_rt()
        return JSONResponse({"space_id": r.space_id, "scene": r.raw})

    @app.get("/api/v1/scene/summary")
    def v1_summary():
        return JSONResponse(_get_rt().summary())

    # Objects
    @app.get("/api/v1/objects")
    def v1_objects():
        return JSONResponse({"objects": _get_rt().list_objects()})

    @app.get("/api/v1/objects/{obj_id}")
    def v1_object(obj_id: str):
        obj = _get_rt().get_object(obj_id)
        if not obj:
            raise HTTPException(404, f"Object '{obj_id}' not found")
        return JSONResponse(obj)

    # Regions
    @app.get("/api/v1/regions")
    def v1_regions():
        return JSONResponse({"regions": _get_rt().list_regions()})

    @app.get("/api/v1/regions/{region_id}")
    def v1_region(region_id: str):
        region = _get_rt().get_region(region_id)
        if not region:
            raise HTTPException(404, f"Region '{region_id}' not found")
        return JSONResponse(region)

    # Actions
    @app.post("/api/v1/actions")
    def v1_action(req: ActionRequest):
        r = _get_rt()
        result = r.execute_action(req.agent_id, req.verb, req.target_id, req.params)
        code = 200
        if result.code == "NOT_FOUND" or result.code == "UNKNOWN_OBJECT":
            code = 404
        elif result.code == "UNKNOWN_VERB":
            code = 400
        elif result.code == "NOT_AFFORDED":
            code = 403
        elif result.code == "INVALID_URI":
            code = 400
        elif result.code == "NOT_IMPLEMENTED":
            code = 501
        elif result.code == "LOCK_HELD":
            code = 409
        return JSONResponse(result.to_dict(), status_code=code)

    # Events
    @app.get("/api/v1/events")
    def v1_events(after: int = 0):
        r = _get_rt()
        return JSONResponse({
            "events": r.get_events_since(after),
            "latest_seq": r._seq,
        })

    # Agents
    @app.post("/api/v1/agents", status_code=201)
    def v1_register_agent(req: AgentRegisterRequest):
        r = _get_rt()
        try:
            ar = r.register_agent(
                req.agent_id, req.agent_type,
                req.capabilities, req.position, req.meta,
            )
            return JSONResponse({"ok": True, "agent": ar.to_dict()}, status_code=201)
        except ValueError as e:
            raise HTTPException(409, str(e))

    @app.get("/api/v1/agents")
    def v1_agents():
        return JSONResponse({"agents": _get_rt().list_agents()})

    @app.get("/api/v1/agents/nearby")
    def v1_nearby(agent_id: str = Query(...), radius: float = Query(10.0)):
        return JSONResponse({
            "agents": _get_rt().nearby_agents(agent_id, radius),
        })

    @app.get("/api/v1/agents/query")
    def v1_query_agents(
        agent_type: Optional[str] = Query(None),
        capability: Optional[str] = Query(None),
        region_id: Optional[str] = Query(None),
        status: Optional[str] = Query(None),
    ):
        return JSONResponse({
            "agents": _get_rt().query_agents(agent_type, capability, region_id, status),
        })

    @app.get("/api/v1/agents/{agent_id}")
    def v1_agent(agent_id: str):
        ag = _get_rt().get_agent(agent_id)
        if not ag:
            raise HTTPException(404, f"Agent '{agent_id}' not found")
        return JSONResponse(ag)

    @app.put("/api/v1/agents/{agent_id}/heartbeat")
    def v1_heartbeat(agent_id: str, req: HeartbeatRequest):
        r = _get_rt()
        ok = r.heartbeat(agent_id, req.position, req.status)
        if not ok:
            raise HTTPException(404, f"Agent '{agent_id}' not registered")
        # return updated agent info including resolved region
        ag = r.get_agent(agent_id)
        return JSONResponse({"ok": True, "agent": ag})

    @app.delete("/api/v1/agents/{agent_id}")
    def v1_deregister(agent_id: str):
        ok = _get_rt().deregister_agent(agent_id)
        if not ok:
            raise HTTPException(404, f"Agent '{agent_id}' not found")
        return JSONResponse({"ok": True})

    # Locking
    @app.post("/api/v1/objects/{obj_id}/lock")
    def v1_lock_acquire(obj_id: str, req: LockRequest):
        r = _get_rt()
        if not r.get_object(obj_id):
            raise HTTPException(404, f"Object '{obj_id}' not found")
        lr = r.acquire_lock(obj_id, req.agent_id, req.ttl_seconds)
        if lr is None:
            existing = r.check_lock(obj_id)
            raise HTTPException(409, f"Locked by '{existing.agent_id}'" if existing else "Lock conflict")
        return JSONResponse({"ok": True, **lr.to_dict()})

    @app.get("/api/v1/objects/{obj_id}/lock")
    def v1_lock_check(obj_id: str):
        lr = _get_rt().check_lock(obj_id)
        if not lr:
            return JSONResponse({"locked": False})
        return JSONResponse({"locked": True, **lr.to_dict()})

    @app.delete("/api/v1/objects/{obj_id}/lock")
    def v1_lock_release(obj_id: str, agent_id: str = Query(...)):
        ok = _get_rt().release_lock(obj_id, agent_id)
        if not ok:
            raise HTTPException(404, "Lock not found or not held by this agent")
        return JSONResponse({"ok": True})

    # ── WebSocket ─────────────────────────────────────────────

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        ws_id = None
        agent_id = "anonymous"
        try:
            # wait for hello
            hello_raw = await websocket.receive_text()
            hello = json.loads(hello_raw)
            agent_id = hello.get("agent_id", "anonymous")
            topics = set(hello.get("subscribe", []))
            ws_id = await mgr.connect(websocket, agent_id, topics)

            # send welcome
            r = _get_rt()
            await websocket.send_text(json.dumps({
                "type": "welcome",
                "agent_id": agent_id,
                "space_id": r.space_id,
                "server_version": "0.1.0",
                "ws_id": ws_id,
            }))

            # message loop
            while True:
                raw = await websocket.receive_text()
                msg = json.loads(raw)
                msg_type = msg.get("type", "")

                if msg_type == "subscribe":
                    await mgr.update_topics(ws_id, add=set(msg.get("topics", [])))
                elif msg_type == "unsubscribe":
                    await mgr.update_topics(ws_id, remove=set(msg.get("topics", [])))
                elif msg_type == "heartbeat":
                    r.heartbeat(agent_id)
                elif msg_type == "action":
                    result = r.execute_action(
                        msg.get("agent_id", agent_id),
                        msg.get("verb", ""),
                        msg.get("target_id", ""),
                        msg.get("params", {}),
                    )
                    await mgr.send_to(ws_id, {
                        "type": "action_result",
                        "data": result.to_dict(),
                    })

        except (WebSocketDisconnect, Exception):
            pass
        finally:
            if ws_id:
                await mgr.disconnect(ws_id)

    # ── Legacy endpoints (backward compat) ────────────────────

    @app.get("/api/scene")
    def legacy_scene():
        r = _get_rt()
        return JSONResponse({
            "meta": {"scene_path": str(scene_path or default_scene_path())},
            "scene": r.raw,
        })

    @app.get("/api/summary")
    def legacy_summary():
        return JSONResponse(_get_rt().summary())

    @app.get("/api/roles")
    def legacy_roles():
        try:
            from omnity_soap.explore import viewer_roles_payload
            r = _get_rt()
            return JSONResponse({
                "roles": viewer_roles_payload(r.raw),
                "scene_path": str(scene_path or default_scene_path()),
            })
        except Exception as e:
            return JSONResponse({"error": "roles_failed", "detail": str(e)}, 500)

    @app.get("/api/events")
    def legacy_events(after: int = 0):
        r = _get_rt()
        return JSONResponse({
            "events": r.get_events_since(after),
            "latest_seq": r._seq,
        })

    @app.get("/api/agents")
    def legacy_agents():
        return JSONResponse({"agents": _get_rt().list_agents()})

    @app.post("/api/act")
    def legacy_act(req: LegacyActionRequest):
        r = _get_rt()
        result = r.execute_action(req.agent_id, req.verb, req.target_id, req.params)
        return JSONResponse(result.to_dict())

    # ── Static files (viewer) ─────────────────────────────────
    static_dir = viewer_static_dir()
    if static_dir.is_dir() and (static_dir / "index.html").is_file():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="viewer")

    return app


# ── CLI entry point ────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="SOAP Server — HTTP + WebSocket transport")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8765, help="Port (default: 8765)")
    parser.add_argument("--scene", default=None, help="Path to scene JSON (default: $SOAP_SCENE_PATH)")
    args = parser.parse_args()

    scene_path = Path(args.scene) if args.scene else default_scene_path()
    if not scene_path.is_file():
        print(f"Scene file not found: {scene_path}", file=sys.stderr)
        print("Set SOAP_SCENE_PATH or use --scene.", file=sys.stderr)
        sys.exit(1)

    app = create_app(scene_path)

    import uvicorn
    print(f"SOAP Server → http://{args.host}:{args.port}/")
    print(f"  REST API: /api/v1/*")
    print(f"  WebSocket: ws://{args.host}:{args.port}/ws")
    print(f"  Scene: {scene_path}")
    print(f"  Legacy compat: /api/scene, /api/act, etc.")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
