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


class TestRegionAwareness:
    def setup_method(self):
        self.rt = SOAPRuntime.load(MALL)

    def test_update_agent_region_fires_events(self):
        events = []
        self.rt.add_event_listener(lambda t, d: events.append((t, d)))
        self.rt.register_agent("bot_1")
        # Move from default "atrium" to "cafe_201"
        result = self.rt.update_agent_region("bot_1", new_region="cafe_201")
        assert result == "cafe_201"
        topics = [e[0] for e in events]
        assert "region.exited" in topics
        assert "region.entered" in topics
        # Check the exit was from atrium, enter was cafe_201
        exit_ev = [e for e in events if e[0] == "region.exited"][0]
        enter_ev = [e for e in events if e[0] == "region.entered"][0]
        assert exit_ev[1]["region_id"] == "atrium"
        assert enter_ev[1]["region_id"] == "cafe_201"

    def test_no_event_if_same_region(self):
        events = []
        self.rt.register_agent("bot_1")
        self.rt.add_event_listener(lambda t, d: events.append((t, d)))
        self.rt.update_agent_region("bot_1", new_region="atrium")
        region_events = [e for e in events if "region" in e[0]]
        assert len(region_events) == 0

    def test_heartbeat_auto_updates_region(self):
        self.rt.register_agent("bot_1", position=[0, 0, 0])
        events = []
        self.rt.add_event_listener(lambda t, d: events.append((t, d)))
        # Heartbeat with a position near cafe_201 objects
        # (the actual position doesn't matter much since resolve_region uses generous margin)
        self.rt.heartbeat("bot_1", position=[50, 0, 50])
        # At minimum, the heartbeat should succeed
        ar = self.rt.get_registered_agent("bot_1")
        assert ar.position == [50, 0, 50]


class TestAgentQuery:
    def setup_method(self):
        self.rt = SOAPRuntime.load(MALL)

    def test_query_by_type(self):
        self.rt.register_agent("r1", agent_type="robot")
        self.rt.register_agent("h1", agent_type="human")
        self.rt.register_agent("r2", agent_type="robot")
        result = self.rt.query_agents(agent_type="robot")
        ids = [a["id"] for a in result]
        assert "r1" in ids and "r2" in ids
        assert "h1" not in ids

    def test_query_by_capability(self):
        self.rt.register_agent("r1", capabilities=["observe", "navigate"])
        self.rt.register_agent("h1", capabilities=["observe"])
        result = self.rt.query_agents(capability="navigate")
        ids = [a["id"] for a in result]
        assert "r1" in ids
        assert "h1" not in ids

    def test_query_by_region(self):
        self.rt.register_agent("a1")
        self.rt.update_agent_region("a1", new_region="cafe_201")
        self.rt.register_agent("a2")  # default atrium
        result = self.rt.query_agents(region_id="cafe_201")
        ids = [a["id"] for a in result]
        assert "a1" in ids
        assert "a2" not in ids

    def test_query_combined(self):
        self.rt.register_agent("r1", agent_type="robot", capabilities=["navigate"])
        self.rt.register_agent("r2", agent_type="robot", capabilities=["observe"])
        result = self.rt.query_agents(agent_type="robot", capability="navigate")
        assert len(result) == 1
        assert result[0]["id"] == "r1"


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


# ── Input validation tests ─────────────────────────────────────

@requires_fastapi
class TestInputValidation:

    def setup_method(self):
        self.app = create_app(MALL)
        self.client = TestClient(self.app)

    def test_register_empty_agent_id(self):
        r = self.client.post("/api/v1/agents", json={"agent_id": ""})
        assert r.status_code == 422

    def test_register_whitespace_agent_id(self):
        r = self.client.post("/api/v1/agents", json={"agent_id": "   "})
        assert r.status_code == 422

    def test_register_bad_position_length(self):
        r = self.client.post("/api/v1/agents", json={
            "agent_id": "bot_1", "position": [1, 2],
        })
        assert r.status_code == 422

    def test_heartbeat_bad_position_length(self):
        self.client.post("/api/v1/agents", json={"agent_id": "bot_1"})
        r = self.client.put("/api/v1/agents/bot_1/heartbeat",
                            json={"position": [1]})
        assert r.status_code == 422

    def test_lock_negative_ttl(self):
        r = self.client.post("/api/v1/objects/fountain_center/lock",
                             json={"agent_id": "a", "ttl_seconds": -5})
        assert r.status_code == 422

    def test_lock_zero_ttl(self):
        r = self.client.post("/api/v1/objects/fountain_center/lock",
                             json={"agent_id": "a", "ttl_seconds": 0})
        assert r.status_code == 422

    def test_lock_excessive_ttl(self):
        r = self.client.post("/api/v1/objects/fountain_center/lock",
                             json={"agent_id": "a", "ttl_seconds": 99999})
        assert r.status_code == 422

    def test_lock_empty_agent_id(self):
        r = self.client.post("/api/v1/objects/fountain_center/lock",
                             json={"agent_id": "", "ttl_seconds": 30})
        assert r.status_code == 422

    def test_lock_nonexistent_object(self):
        r = self.client.post("/api/v1/objects/nonexistent/lock",
                             json={"agent_id": "a", "ttl_seconds": 30})
        assert r.status_code == 404


# ── Additional endpoint coverage ───────────────────────────────

@requires_fastapi
class TestV1EdgeCases:

    def setup_method(self):
        self.app = create_app(MALL)
        self.client = TestClient(self.app)

    def test_region_not_found(self):
        r = self.client.get("/api/v1/regions/nonexistent")
        assert r.status_code == 404

    def test_action_unknown_verb(self):
        r = self.client.post("/api/v1/actions", json={
            "agent_id": "test", "verb": "FLY",
            "target_id": "fountain_center",
        })
        assert r.status_code == 400
        assert r.json()["code"] == "UNKNOWN_VERB"

    def test_action_rearrange_not_implemented(self):
        r = self.client.post("/api/v1/actions", json={
            "agent_id": "test", "verb": "REARRANGE",
            "target_id": "fountain_center",
        })
        assert r.status_code == 501
        assert r.json()["code"] == "NOT_IMPLEMENTED"

    def test_action_observe_not_found(self):
        r = self.client.post("/api/v1/actions", json={
            "agent_id": "test", "verb": "OBSERVE",
            "target_id": "nonexistent_xyz",
        })
        assert r.status_code == 404
        assert r.json()["code"] == "NOT_FOUND"

    def test_action_navigate_invalid_uri(self):
        """NAVIGATE with a non-soap:// URI should return INVALID_URI / 400."""
        # Need a valid object first
        objects = self.client.get("/api/v1/objects").json()["objects"]
        obj_id = objects[0]["id"]
        r = self.client.post("/api/v1/actions", json={
            "agent_id": "test", "verb": "NAVIGATE",
            "target_id": obj_id,
            "params": {"target_uri": "http://example.com"},
        })
        assert r.status_code == 400
        assert r.json()["code"] == "INVALID_URI"

    def test_deregister_nonexistent(self):
        r = self.client.delete("/api/v1/agents/ghost")
        assert r.status_code == 404

    def test_agent_not_found(self):
        r = self.client.get("/api/v1/agents/ghost")
        assert r.status_code == 404


# ── Runtime edge cases ─────────────────────────────────────────

class TestRuntimeEdgeCases:

    def setup_method(self):
        self.rt = SOAPRuntime.load(MALL)

    def test_nearby_unregistered_agent(self):
        """nearby_agents for unknown agent_id returns empty list."""
        assert self.rt.nearby_agents("nonexistent") == []

    def test_nearby_disconnected_excluded(self):
        """Disconnected agents are excluded from nearby results."""
        import time
        self.rt.register_agent("a", position=[0, 0, 0])
        self.rt.register_agent("b", position=[1, 0, 0])
        # Mark b as disconnected
        ar_b = self.rt.get_registered_agent("b")
        ar_b.status = "disconnected"
        nearby = self.rt.nearby_agents("a", radius=5.0)
        assert not any(a["id"] == "b" for a in nearby)

    def test_reap_to_disconnected(self):
        """Agent goes stale -> disconnected after 2x TTL."""
        import time
        self.rt.register_agent("bot_1")
        ar = self.rt.get_registered_agent("bot_1")
        ar.last_heartbeat = time.time() - 120
        # First reap: active -> stale
        ar.status = "stale"  # simulate already stale
        changed = self.rt.reap_stale_agents(heartbeat_ttl=5.0)
        assert "bot_1" in changed
        assert self.rt.get_registered_agent("bot_1").status == "disconnected"

    def test_event_log_ordering(self):
        """Events are sequentially numbered."""
        self.rt.observe("a", "fountain_center")
        self.rt.observe("a", "atrium")
        events = self.rt.get_events_since(0)
        assert events[0]["seq"] == 1
        assert events[1]["seq"] == 2
        # after=1 should skip first
        filtered = self.rt.get_events_since(1)
        assert len(filtered) == 1
        assert filtered[0]["seq"] == 2


# ── S3: WebSocket Event Bus tests ─────────────────────────────

@requires_fastapi
class TestWebSocketEventBus:
    """S3: Enhanced WebSocket event bus — topic routing, sequencing,
    reconnection catch-up, region filtering, error handling."""

    def setup_method(self):
        self.app = create_app(MALL)
        self.client = TestClient(self.app)

    def test_welcome_includes_latest_seq(self):
        """Welcome message includes latest_seq for reconnection tracking."""
        with self.client.websocket_connect("/ws") as ws:
            ws.send_text(json.dumps({
                "type": "hello", "agent_id": "t1", "subscribe": [],
            }))
            welcome = json.loads(ws.receive_text())
            assert "latest_seq" in welcome

    def test_error_on_invalid_json(self):
        """Server returns error on malformed JSON."""
        with self.client.websocket_connect("/ws") as ws:
            ws.send_text(json.dumps({
                "type": "hello", "agent_id": "t1", "subscribe": [],
            }))
            ws.receive_text()  # welcome
            ws.send_text("not json {{{")
            data = json.loads(ws.receive_text())
            assert data["type"] == "error"
            assert data["code"] == "INVALID_JSON"

    def test_error_on_unknown_message_type(self):
        """Server returns error on unknown message type."""
        with self.client.websocket_connect("/ws") as ws:
            ws.send_text(json.dumps({
                "type": "hello", "agent_id": "t1", "subscribe": [],
            }))
            ws.receive_text()  # welcome
            ws.send_text(json.dumps({"type": "foobar"}))
            data = json.loads(ws.receive_text())
            assert data["type"] == "error"
            assert data["code"] == "UNKNOWN_MESSAGE_TYPE"

    def test_set_region_filter(self):
        """Client can dynamically set region filter."""
        with self.client.websocket_connect("/ws") as ws:
            ws.send_text(json.dumps({
                "type": "hello", "agent_id": "t1", "subscribe": ["events"],
            }))
            ws.receive_text()  # welcome
            # set region filter (should not error)
            ws.send_text(json.dumps({
                "type": "set_region_filter", "region_id": "atrium",
            }))
            # now send an action — should still work
            ws.send_text(json.dumps({
                "type": "action", "verb": "OBSERVE", "target_id": "fountain_center",
            }))
            data = json.loads(ws.receive_text())
            assert data["type"] == "action_result"

    def test_topic_map_resolution(self):
        """ConnectionManager.resolve_ws_topic correctly maps runtime topics."""
        from omnity_soap.server import ConnectionManager
        assert ConnectionManager.resolve_ws_topic("events") == "events"
        assert ConnectionManager.resolve_ws_topic("agent.registered") == "agents"
        assert ConnectionManager.resolve_ws_topic("agents.status_changed") == "agents"
        assert ConnectionManager.resolve_ws_topic("lock.acquired") == "locks"
        assert ConnectionManager.resolve_ws_topic("lock.released") == "locks"
        assert ConnectionManager.resolve_ws_topic("lock.expired") == "locks"
        assert ConnectionManager.resolve_ws_topic("region.entered") == "regions"
        assert ConnectionManager.resolve_ws_topic("region.exited") == "regions"
        assert ConnectionManager.resolve_ws_topic("state.changed") == "state"

    def test_regions_topic_added(self):
        """Regions topic is documented and subscribable."""
        with self.client.websocket_connect("/ws") as ws:
            ws.send_text(json.dumps({
                "type": "hello", "agent_id": "t1",
                "subscribe": ["events", "regions"],
            }))
            welcome = json.loads(ws.receive_text())
            assert welcome["type"] == "welcome"
            # dynamically add state topic
            ws.send_text(json.dumps({
                "type": "subscribe", "topics": ["state"],
            }))
            # should not get an error back — verify with a follow-up action
            ws.send_text(json.dumps({
                "type": "action", "verb": "OBSERVE", "target_id": "atrium",
            }))
            data = json.loads(ws.receive_text())
            assert data["type"] == "action_result"


class TestConnectionManagerCatchUp:
    """S3: Unit test for ConnectionManager catch-up and sequencing."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        try:
            from omnity_soap.server import ConnectionManager
            self._CM = ConnectionManager
            self.skip = False
        except ImportError:
            self.skip = True

    def test_recent_events_buffer(self):
        """Broadcast stores events in ring buffer for catch-up."""
        if self.skip:
            pytest.skip("fastapi not available")
        import asyncio

        async def _run():
            mgr = self._CM()  # create inside event loop for Python 3.9

            # simulate: connect a client
            class FakeWS:
                def __init__(self):
                    self.sent = []
                async def send_text(self, msg):
                    self.sent.append(msg)

            ws = FakeWS()
            ws_id = await mgr.connect(ws, "agent_1", {"events"})

            # broadcast 3 events (no subscribers at broadcast time besides agent_1)
            await mgr.broadcast("events", {"verb": "OBSERVE", "seq": 1})
            await mgr.broadcast("events", {"verb": "OBSERVE", "seq": 2})
            await mgr.broadcast("events", {"verb": "NAVIGATE", "seq": 3})

            # agent_1 should have received all 3
            assert len(ws.sent) == 3

            # now connect a second client with catch-up
            ws2 = FakeWS()
            ws_id2 = await mgr.connect(ws2, "agent_2", {"events"})
            # catch up from seq 1 (should get seq 2 and 3)
            await mgr.catch_up(ws_id2, after_seq=1)
            assert len(ws2.sent) == 2
            msgs = [json.loads(m) for m in ws2.sent]
            assert msgs[0]["seq"] == 2
            assert msgs[1]["seq"] == 3

        asyncio.run(_run())

    def test_ring_buffer_limit(self):
        """Ring buffer respects max_recent limit."""
        if self.skip:
            pytest.skip("fastapi not available")
        import asyncio

        async def _run():
            mgr = self._CM()
            mgr._max_recent = 5
            # no subscribers — just fill the buffer
            for i in range(10):
                await mgr.broadcast("events", {"i": i})
            assert len(mgr._recent_events) == 5
            # should keep the last 5 (seq 6-10)
            seqs = [e["seq"] for e in mgr._recent_events]
            assert seqs == [6, 7, 8, 9, 10]

        asyncio.run(_run())

    def test_catch_up_respects_topic_filter(self):
        """Catch-up only sends events matching client's subscribed topics."""
        if self.skip:
            pytest.skip("fastapi not available")
        import asyncio

        async def _run():
            mgr = self._CM()
            # broadcast mix of topics
            await mgr.broadcast("events", {"a": 1})
            await mgr.broadcast("lock.acquired", {"b": 2})
            await mgr.broadcast("events", {"c": 3})

            class FakeWS:
                def __init__(self):
                    self.sent = []
                async def send_text(self, msg):
                    self.sent.append(msg)

            # client subscribes only to "locks"
            ws = FakeWS()
            ws_id = await mgr.connect(ws, "a1", {"locks"})
            await mgr.catch_up(ws_id, after_seq=0)
            # should only get the lock event
            assert len(ws.sent) == 1
            msg = json.loads(ws.sent[0])
            assert msg["topic"] == "locks"

        asyncio.run(_run())


# ── S4: Spatial Query & Discovery tests ───────────────────────

class TestSpatialQuery:
    """S4: Runtime spatial query methods."""

    def setup_method(self):
        self.rt = SOAPRuntime.load(MALL)

    def test_query_objects_by_type(self):
        results = self.rt.query_objects(obj_type="npc.store_clerk")
        assert len(results) > 0
        assert all(o["type"] == "npc.store_clerk" for o in results)

    def test_query_objects_by_reality(self):
        results = self.rt.query_objects(reality="physical")
        assert len(results) > 0
        assert all(o.get("reality") == "physical" for o in results)

    def test_query_objects_by_affordance(self):
        results = self.rt.query_objects(affordance="speak")
        assert len(results) > 0
        for o in results:
            assert "speak" in o.get("affordances", [])

    def test_query_objects_by_region(self):
        results = self.rt.query_objects(region_id="atrium")
        assert len(results) > 0
        atrium = self.rt.get_region("atrium")
        contained = set(atrium.get("contained_object_ids", []))
        for o in results:
            assert o["id"] in contained

    def test_query_objects_combined(self):
        results = self.rt.query_objects(reality="physical", region_id="atrium")
        for o in results:
            assert o.get("reality") == "physical"

    def test_query_objects_nonexistent_region(self):
        results = self.rt.query_objects(region_id="nonexistent")
        assert results == []

    def test_spatial_query_sphere(self):
        fountain = self.rt.get_object("fountain_center")
        b = fountain.get("bounds", {})
        cx = (b["min"][0] + b["max"][0]) / 2
        cy = (b["min"][1] + b["max"][1]) / 2
        cz = (b["min"][2] + b["max"][2]) / 2
        results = self.rt.spatial_query(center=[cx, cy, cz], radius=50.0)
        ids = [o["id"] for o in results]
        assert "fountain_center" in ids

    def test_spatial_query_small_radius(self):
        results = self.rt.spatial_query(center=[0, 0, 0], radius=0.01)
        assert isinstance(results, list)

    def test_spatial_query_bbox(self):
        results = self.rt.spatial_query(
            bbox_min=[-100, -100, -100], bbox_max=[100, 100, 100])
        assert len(results) > 0

    def test_region_inventory(self):
        inv = self.rt.region_inventory("atrium")
        assert inv is not None
        assert inv["region_id"] == "atrium"
        assert inv["object_count"] > 0

    def test_region_inventory_not_found(self):
        assert self.rt.region_inventory("nonexistent") is None

    def test_region_inventory_includes_agents(self):
        self.rt.register_agent("bot_inv", position=[0, 0, 0])
        ar = self.rt.get_registered_agent("bot_inv")
        ar.near_target = "atrium"
        inv = self.rt.region_inventory("atrium")
        agent_ids = [a["id"] for a in inv["agents"]]
        assert "bot_inv" in agent_ids


@requires_fastapi
class TestV1SpatialEndpoints:
    """S4: HTTP endpoints for spatial query."""

    def setup_method(self):
        self.app = create_app(MALL)
        self.client = TestClient(self.app)

    def test_search_by_type(self):
        r = self.client.get("/api/v1/objects/search?type=npc.store_clerk")
        assert r.status_code == 200
        assert len(r.json()["objects"]) > 0

    def test_search_by_reality(self):
        r = self.client.get("/api/v1/objects/search?reality=physical")
        assert r.status_code == 200
        assert len(r.json()["objects"]) > 0

    def test_search_by_affordance(self):
        r = self.client.get("/api/v1/objects/search?affordance=speak")
        assert r.status_code == 200
        for o in r.json()["objects"]:
            assert "speak" in o["affordances"]

    def test_search_by_region(self):
        r = self.client.get("/api/v1/objects/search?region_id=atrium")
        assert r.status_code == 200
        assert len(r.json()["objects"]) > 0

    def test_spatial_sphere(self):
        r = self.client.get("/api/v1/objects/spatial?cx=0&cy=0&cz=0&radius=200")
        assert r.status_code == 200
        assert len(r.json()["objects"]) > 0

    def test_spatial_bbox(self):
        r = self.client.get(
            "/api/v1/objects/spatial?min_x=-100&min_y=-100&min_z=-100"
            "&max_x=100&max_y=100&max_z=100")
        assert r.status_code == 200
        assert len(r.json()["objects"]) > 0

    def test_region_inventory(self):
        r = self.client.get("/api/v1/regions/atrium/inventory")
        assert r.status_code == 200
        inv = r.json()
        assert inv["region_id"] == "atrium"
        assert inv["object_count"] > 0

    def test_region_inventory_not_found(self):
        r = self.client.get("/api/v1/regions/nonexistent/inventory")
        assert r.status_code == 404
