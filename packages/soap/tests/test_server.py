"""Tests for SOAP Server (FastAPI transport layer).

Covers: REST v1 endpoints, legacy compat, agent registration,
locking, WebSocket, and runtime extensions.
"""
import json
import pytest

# Runtime extension tests (no FastAPI needed)
from omnity_soap.runtime import SOAPRuntime, AgentRecord, LockRecord
from pathlib import Path

MALL = Path(__file__).resolve().parent.parent / "examples" / "mall-mixed-reality.json"


# ── Runtime extension tests ───────────────────────────────────

class TestAgentRegistry:
    def setup_method(self):
        self.rt = SOAPRuntime.load(MALL)

    def test_register_and_list(self):
        self.rt.register_agent("bot_1", agent_type="robot", capabilities=["observe"])
        agents = self.rt.list_agents()
        ids = [a["id"] for a in agents]
        assert "bot_1" in ids

    def test_register_duplicate_raises(self):
        self.rt.register_agent("bot_1")
        with pytest.raises(ValueError, match="already registered"):
            self.rt.register_agent("bot_1")

    def test_heartbeat(self):
        self.rt.register_agent("bot_1")
        assert self.rt.heartbeat("bot_1") is True
        assert self.rt.heartbeat("nonexistent") is False

    def test_heartbeat_updates_position(self):
        self.rt.register_agent("bot_1", position=[0, 0, 0])
        self.rt.heartbeat("bot_1", position=[10, 0, 5])
        ar = self.rt.get_registered_agent("bot_1")
        assert ar.position == [10, 0, 5]

    def test_deregister(self):
        self.rt.register_agent("bot_1")
        assert self.rt.deregister_agent("bot_1") is True
        assert self.rt.deregister_agent("bot_1") is False
        assert self.rt.get_agent("bot_1") is None

    def test_nearby_by_position(self):
        self.rt.register_agent("a", position=[0, 0, 0])
        self.rt.register_agent("b", position=[3, 0, 0])
        self.rt.register_agent("c", position=[100, 0, 0])
        nearby = self.rt.nearby_agents("a", radius=5.0)
        ids = [a["id"] for a in nearby]
        assert "b" in ids
        assert "c" not in ids

    def test_nearby_by_region(self):
        self.rt.register_agent("a", agent_type="npc")
        self.rt.register_agent("b", agent_type="npc")
        # both default to near_target="atrium"
        nearby = self.rt.nearby_agents("a")
        assert any(a["id"] == "b" for a in nearby)

    def test_reap_stale(self):
        import time
        self.rt.register_agent("bot_1")
        ar = self.rt.get_registered_agent("bot_1")
        ar.last_heartbeat = time.time() - 60  # simulate old heartbeat
        changed = self.rt.reap_stale_agents(heartbeat_ttl=5.0)
        assert "bot_1" in changed
        assert self.rt.get_registered_agent("bot_1").status == "stale"


class TestObjectLocking:
    def setup_method(self):
        self.rt = SOAPRuntime.load(MALL)

    def test_acquire_and_check(self):
        lr = self.rt.acquire_lock("fountain_center", "agent_a", ttl=30)
        assert lr is not None
        assert lr.agent_id == "agent_a"
        checked = self.rt.check_lock("fountain_center")
        assert checked is not None
        assert checked.lock_id == lr.lock_id

    def test_lock_conflict(self):
        self.rt.acquire_lock("fountain_center", "agent_a", ttl=30)
        result = self.rt.acquire_lock("fountain_center", "agent_b", ttl=30)
        assert result is None  # can't acquire, held by agent_a

    def test_same_agent_can_reacquire(self):
        self.rt.acquire_lock("fountain_center", "agent_a", ttl=30)
        lr2 = self.rt.acquire_lock("fountain_center", "agent_a", ttl=30)
        assert lr2 is not None

    def test_release(self):
        self.rt.acquire_lock("fountain_center", "agent_a", ttl=30)
        assert self.rt.release_lock("fountain_center", "agent_a") is True
        assert self.rt.check_lock("fountain_center") is None

    def test_release_by_wrong_agent(self):
        self.rt.acquire_lock("fountain_center", "agent_a", ttl=30)
        assert self.rt.release_lock("fountain_center", "agent_b") is False

    def test_expired_lock_auto_clears(self):
        lr = self.rt.acquire_lock("fountain_center", "agent_a", ttl=0.001)
        import time
        time.sleep(0.01)
        assert self.rt.check_lock("fountain_center") is None

    def test_manipulate_blocked_by_lock(self):
        self.rt.acquire_lock("fountain_center", "agent_a", ttl=30)
        result = self.rt.manipulate("agent_b", "fountain_center", "place_object")
        assert result.ok is False
        assert result.code == "LOCK_HELD"


class TestEventListeners:
    def test_listener_called_on_action(self):
        rt = SOAPRuntime.load(MALL)
        events_received = []
        rt.add_event_listener(lambda topic, data: events_received.append((topic, data)))
        rt.observe("test_agent", "fountain_center")
        assert len(events_received) >= 1
        assert events_received[-1][0] == "events"

    def test_remove_listener(self):
        rt = SOAPRuntime.load(MALL)
        events_received = []
        cb = lambda topic, data: events_received.append(1)
        rt.add_event_listener(cb)
        rt.observe("test_agent", "fountain_center")
        assert len(events_received) == 1
        rt.remove_event_listener(cb)
        rt.observe("test_agent", "atrium")
        assert len(events_received) == 1  # no new events


# ── FastAPI server tests (skip if fastapi not installed) ──────

try:
    from fastapi.testclient import TestClient
    from omnity_soap.server import create_app
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

requires_fastapi = pytest.mark.skipif(not HAS_FASTAPI, reason="fastapi not installed")


@requires_fastapi
class TestLegacyCompat:
    """Legacy /api/* endpoints must continue to work."""

    def setup_method(self):
        self.app = create_app(MALL)
        self.client = TestClient(self.app)

    def test_legacy_scene(self):
        r = self.client.get("/api/scene")
        assert r.status_code == 200
        data = r.json()
        assert "scene" in data
        assert data["scene"]["space_id"] == "mall_01"

    def test_legacy_summary(self):
        r = self.client.get("/api/summary")
        assert r.status_code == 200
        assert r.json()["space_id"] == "mall_01"

    def test_legacy_events(self):
        r = self.client.get("/api/events?after=0")
        assert r.status_code == 200
        assert "events" in r.json()

    def test_legacy_agents(self):
        r = self.client.get("/api/agents")
        assert r.status_code == 200
        assert "agents" in r.json()

    def test_legacy_act(self):
        r = self.client.post("/api/act", json={
            "agent_id": "test", "verb": "OBSERVE",
            "target_id": "fountain_center", "params": {},
        })
        assert r.status_code == 200
        assert r.json()["ok"] is True


@requires_fastapi
class TestV1Endpoints:

    def setup_method(self):
        self.app = create_app(MALL)
        self.client = TestClient(self.app)

    def test_scene(self):
        r = self.client.get("/api/v1/scene")
        assert r.status_code == 200
        assert r.json()["space_id"] == "mall_01"

    def test_summary(self):
        r = self.client.get("/api/v1/scene/summary")
        assert r.status_code == 200
        s = r.json()
        assert s["object_count"] > 0

    def test_list_objects(self):
        r = self.client.get("/api/v1/objects")
        assert r.status_code == 200
        assert len(r.json()["objects"]) > 0

    def test_get_object(self):
        r = self.client.get("/api/v1/objects/fountain_center")
        assert r.status_code == 200
        assert r.json()["id"] == "fountain_center"

    def test_get_object_not_found(self):
        r = self.client.get("/api/v1/objects/nonexistent")
        assert r.status_code == 404

    def test_list_regions(self):
        r = self.client.get("/api/v1/regions")
        assert r.status_code == 200
        assert len(r.json()["regions"]) > 0

    def test_get_region(self):
        r = self.client.get("/api/v1/regions/atrium")
        assert r.status_code == 200
        assert r.json()["id"] == "atrium"

    def test_action_observe(self):
        r = self.client.post("/api/v1/actions", json={
            "agent_id": "test", "verb": "OBSERVE",
            "target_id": "fountain_center",
        })
        assert r.status_code == 200
        assert r.json()["ok"] is True
        assert r.json()["verb"] == "OBSERVE"

    def test_action_not_afforded(self):
        r = self.client.post("/api/v1/actions", json={
            "agent_id": "test", "verb": "MANIPULATE",
            "target_id": "fountain_center",
            "params": {"action": "fly"},
        })
        assert r.status_code == 403

    def test_events(self):
        # trigger an action first
        self.client.post("/api/v1/actions", json={
            "agent_id": "test", "verb": "OBSERVE",
            "target_id": "atrium",
        })
        r = self.client.get("/api/v1/events?after=0")
        assert r.status_code == 200
        assert len(r.json()["events"]) > 0


@requires_fastapi
class TestV1Agents:

    def setup_method(self):
        self.app = create_app(MALL)
        self.client = TestClient(self.app)

    def test_register(self):
        r = self.client.post("/api/v1/agents", json={
            "agent_id": "robot_01", "agent_type": "robot",
            "capabilities": ["observe", "navigate"],
        })
        assert r.status_code == 201
        assert r.json()["ok"] is True
        assert r.json()["agent"]["agent_type"] == "robot"

    def test_register_duplicate(self):
        self.client.post("/api/v1/agents", json={"agent_id": "robot_01"})
        r = self.client.post("/api/v1/agents", json={"agent_id": "robot_01"})
        assert r.status_code == 409

    def test_list(self):
        self.client.post("/api/v1/agents", json={"agent_id": "robot_01"})
        r = self.client.get("/api/v1/agents")
        assert r.status_code == 200
        ids = [a["id"] for a in r.json()["agents"]]
        assert "robot_01" in ids

    def test_get(self):
        self.client.post("/api/v1/agents", json={"agent_id": "robot_01"})
        r = self.client.get("/api/v1/agents/robot_01")
        assert r.status_code == 200
        assert r.json()["id"] == "robot_01"

    def test_heartbeat(self):
        self.client.post("/api/v1/agents", json={"agent_id": "robot_01"})
        r = self.client.put("/api/v1/agents/robot_01/heartbeat",
                            json={"position": [1, 0, 2]})
        assert r.status_code == 200

    def test_heartbeat_unregistered(self):
        r = self.client.put("/api/v1/agents/ghost/heartbeat", json={})
        assert r.status_code == 404

    def test_deregister(self):
        self.client.post("/api/v1/agents", json={"agent_id": "robot_01"})
        r = self.client.delete("/api/v1/agents/robot_01")
        assert r.status_code == 200
        r2 = self.client.get("/api/v1/agents/robot_01")
        assert r2.status_code == 404

    def test_nearby(self):
        self.client.post("/api/v1/agents", json={
            "agent_id": "a", "position": [0, 0, 0],
        })
        self.client.post("/api/v1/agents", json={
            "agent_id": "b", "position": [2, 0, 0],
        })
        self.client.post("/api/v1/agents", json={
            "agent_id": "c", "position": [100, 0, 0],
        })
        r = self.client.get("/api/v1/agents/nearby?agent_id=a&radius=5")
        assert r.status_code == 200
        ids = [a["id"] for a in r.json()["agents"]]
        assert "b" in ids
        assert "c" not in ids


@requires_fastapi
class TestV1Locking:

    def setup_method(self):
        self.app = create_app(MALL)
        self.client = TestClient(self.app)

    def test_acquire_and_check(self):
        r = self.client.post("/api/v1/objects/fountain_center/lock",
                             json={"agent_id": "a", "ttl_seconds": 30})
        assert r.status_code == 200
        assert r.json()["ok"] is True

        r2 = self.client.get("/api/v1/objects/fountain_center/lock")
        assert r2.json()["locked"] is True
        assert r2.json()["agent_id"] == "a"

    def test_lock_conflict(self):
        self.client.post("/api/v1/objects/fountain_center/lock",
                         json={"agent_id": "a", "ttl_seconds": 30})
        r = self.client.post("/api/v1/objects/fountain_center/lock",
                             json={"agent_id": "b", "ttl_seconds": 30})
        assert r.status_code == 409

    def test_release(self):
        self.client.post("/api/v1/objects/fountain_center/lock",
                         json={"agent_id": "a", "ttl_seconds": 30})
        r = self.client.delete("/api/v1/objects/fountain_center/lock?agent_id=a")
        assert r.status_code == 200
        r2 = self.client.get("/api/v1/objects/fountain_center/lock")
        assert r2.json()["locked"] is False

    def test_manipulate_blocked(self):
        self.client.post("/api/v1/objects/fountain_center/lock",
                         json={"agent_id": "a", "ttl_seconds": 30})
        r = self.client.post("/api/v1/actions", json={
            "agent_id": "b", "verb": "MANIPULATE",
            "target_id": "fountain_center",
            "params": {"action": "place_object"},
        })
        assert r.status_code == 409
        assert r.json()["code"] == "LOCK_HELD"


@requires_fastapi
class TestWebSocket:

    def setup_method(self):
        self.app = create_app(MALL)
        self.client = TestClient(self.app)

    def test_connect_and_welcome(self):
        with self.client.websocket_connect("/ws") as ws:
            ws.send_text(json.dumps({
                "type": "hello",
                "agent_id": "ws_test",
                "subscribe": ["events"],
            }))
            data = json.loads(ws.receive_text())
            assert data["type"] == "welcome"
            assert data["space_id"] == "mall_01"

    def test_inline_action(self):
        with self.client.websocket_connect("/ws") as ws:
            ws.send_text(json.dumps({
                "type": "hello",
                "agent_id": "ws_test",
                "subscribe": [],
            }))
            ws.receive_text()  # welcome

            ws.send_text(json.dumps({
                "type": "action",
                "verb": "OBSERVE",
                "target_id": "fountain_center",
            }))
            data = json.loads(ws.receive_text())
            assert data["type"] == "action_result"
            assert data["data"]["ok"] is True
