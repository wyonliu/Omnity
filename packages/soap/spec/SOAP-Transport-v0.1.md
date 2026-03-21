# SOAP Transport Specification v0.1.0

**HTTP + WebSocket Transport for SOAP (Spatial Omnity Agentic Protocol)**
**Status**: Draft · **Depends on**: [SOAP-v0.1.md](./SOAP-v0.1.md)

> This document defines how SOAP scenes, actions, agents, and events are transported
> over the network. Any client — MR headset, phone, robot, AI glasses, browser —
> can interact with a SOAP-compatible server using standard HTTP + WebSocket.

---

## 1. Design Principles

1. **HTTP-native**: REST endpoints follow standard HTTP semantics. Any `curl` can talk SOAP.
2. **Real-time via WebSocket**: Polling is available but WebSocket is the primary channel for live multi-agent interaction.
3. **Transport-agnostic spec**: The core SOAP spec (scene graph, verbs, schemas) is independent of this transport layer. Alternative transports (gRPC, MQTT) can be specified separately.
4. **Backward compatible**: Legacy `/api/*` endpoints from soap-view continue to work.

---

## 2. Media Type

```
Content-Type: application/soap+json; version=0.1
```

Servers MUST also accept `application/json`. Clients that cannot set custom content types may use `application/json`.

---

## 3. Base URL

```
http(s)://{host}:{port}/api/v1
```

All v1 endpoints are prefixed with `/api/v1`. Legacy endpoints (`/api/scene`, `/api/act`, etc.) are preserved at their original paths for backward compatibility.

---

## 4. RESTful Endpoints

### 4.1 Scene

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/scene` | Full scene snapshot (coordinate_frame, objects, regions) |
| `GET` | `/api/v1/scene/summary` | Metadata: version, space_id, counts |

### 4.2 Objects

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/objects` | List all objects (id, type, reality, affordances, state) |
| `GET` | `/api/v1/objects/search` | Search by `type`, `reality`, `affordance`, `tag`, `region_id` |
| `GET` | `/api/v1/objects/spatial` | Spatial query by sphere (`cx,cy,cz,radius`) or AABB (`min_x..max_z`) |
| `GET` | `/api/v1/objects/{id}` | Full object detail |

### 4.3 Regions

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/regions` | List all regions |
| `GET` | `/api/v1/regions/{id}` | Full region detail |
| `GET` | `/api/v1/regions/{id}/inventory` | Region summary with objects, states, and present agents |

### 4.4 Actions

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/actions` | Execute a SOAP action |

**Request body** (AgentAction):
```json
{
  "agent_id": "explorer_01",
  "verb": "OBSERVE",
  "target_id": "fountain_center",
  "params": {}
}
```

**Response** (ActionResult):
```json
{
  "ok": true,
  "verb": "OBSERVE",
  "code": "OK",
  "detail": "",
  "data": { ... }
}
```

### 4.5 Events

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/events?after={seq}` | Event log (all events with seq > after) |

### 4.6 Agents

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/agents` | Register agent |
| `GET` | `/api/v1/agents` | List all agents |
| `GET` | `/api/v1/agents/{id}` | Get agent detail |
| `PUT` | `/api/v1/agents/{id}/heartbeat` | Presence heartbeat |
| `DELETE` | `/api/v1/agents/{id}` | Deregister agent |
| `GET` | `/api/v1/agents/nearby?agent_id={id}&radius={m}` | Nearby agents |

**Agent Registration Request**:
```json
{
  "agent_id": "robot_delivery_07",
  "agent_type": "robot",
  "capabilities": ["observe", "navigate", "manipulate"],
  "position": [12.5, 0.0, -3.2],
  "meta": {
    "sensors": ["lidar", "camera_rgb"],
    "control_api": "robot://fleet/d-07/cmd"
  }
}
```

**Agent Types**: `human` | `autonomous` | `npc` | `robot` | `unknown`

**Heartbeat**:
```json
PUT /api/v1/agents/{id}/heartbeat
{
  "position": [12.5, 0.0, -3.2],
  "status": "active"
}
```

Default heartbeat TTL: 30 seconds. Agent marked `stale` after 1x TTL, `disconnected` after 2x TTL.

### 4.7 Object Locking

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/objects/{id}/lock` | Acquire lock |
| `GET` | `/api/v1/objects/{id}/lock` | Check lock status |
| `DELETE` | `/api/v1/objects/{id}/lock` | Release lock |

**Acquire Lock**:
```json
POST /api/v1/objects/{id}/lock
{
  "agent_id": "explorer_01",
  "ttl_seconds": 30
}
```

**Response**:
```json
{
  "ok": true,
  "object_id": "fountain_center",
  "agent_id": "explorer_01",
  "lock_id": "uuid",
  "acquired_at": 1711036800.0,
  "ttl": 30,
  "expires_at": 1711036830.0,
  "expired": false
}
```

Locking is **advisory** in v0.1: only MANIPULATE checks locks. OBSERVE and NAVIGATE are unrestricted.

**Constraints**:
- `agent_id` MUST be a non-empty, non-whitespace string.
- `ttl_seconds` MUST be positive and MUST NOT exceed 3600 (1 hour).
- `position` arrays, when provided, MUST have at least 3 elements `[x, y, z]`.

---

## 5. SOAP Status Codes

| SOAP Code | HTTP Status | Meaning |
|-----------|-------------|---------|
| `OK` | 200 | Success |
| `NOT_FOUND` | 404 | Object/region/agent not found |
| `UNKNOWN_OBJECT` | 404 | Object ID not in scene |
| `UNKNOWN_VERB` | 400 | Invalid action verb |
| `NOT_AFFORDED` | 403 | Action not in object's affordances |
| `NOT_IMPLEMENTED` | 501 | Verb not yet supported (e.g. REARRANGE) |
| `INVALID_URI` | 400 | Malformed soap:// URI |
| `LOCK_HELD` | 409 | Object locked by another agent |
| `AGENT_EXISTS` | 409 | Agent ID already registered |
| `AGENT_NOT_FOUND` | 404 | Agent ID not registered |

---

## 6. WebSocket Protocol

### 6.1 Connection

```
ws(s)://{host}:{port}/ws
```

On connect, client sends a **hello** message:
```json
{
  "type": "hello",
  "agent_id": "explorer_01",
  "subscribe": ["events", "agents", "locks"],
  "region_filter": "atrium",
  "last_seq": 0
}
```

- `region_filter` (optional): Only receive events from this region. Omit or `null` for all regions.
- `last_seq` (optional): Last received WebSocket sequence number. Server will replay missed events.

Server responds:
```json
{
  "type": "welcome",
  "agent_id": "explorer_01",
  "space_id": "mall_01",
  "server_version": "0.1.0",
  "latest_seq": 42
}
```

### 6.2 Topics

| Topic | Events pushed |
|-------|-------------|
| `events` | All action events (OBSERVE, NAVIGATE, MANIPULATE) |
| `agents` | Agent registered, deregistered, heartbeat timeout, status changes |
| `locks` | Lock acquired, released, expired |
| `state` | Object state changes (auto-derived from MANIPULATE results) |
| `regions` | Agent entered/exited region |

### 6.3 Server → Client Messages

All server→client event messages include a monotonic `seq` for reconnection tracking:
```json
{
  "type": "event",
  "topic": "events",
  "runtime_topic": "events",
  "seq": 42,
  "data": {
    "seq": 42,
    "ts": 1711036800.123,
    "agent_id": "player_a",
    "verb": "MANIPULATE",
    "target_id": "game_monster_01",
    "params": {"action": "attack_target", "damage": 25},
    "result": {"ok": true, "code": "OK", ...}
  }
}
```

**Error messages** (sent on malformed input):
```json
{"type": "error", "code": "INVALID_JSON", "detail": "Message is not valid JSON"}
{"type": "error", "code": "UNKNOWN_MESSAGE_TYPE", "detail": "Unknown message type 'foo'"}
```

### 6.4 Client → Server Messages

**Subscribe/Unsubscribe** (dynamic topic management):
```json
{"type": "subscribe", "topics": ["state", "regions"]}
{"type": "unsubscribe", "topics": ["locks"]}
```

**Set Region Filter** (scope events to a specific region):
```json
{"type": "set_region_filter", "region_id": "food_court"}
{"type": "set_region_filter", "region_id": null}
```

**Inline Action** (execute via WebSocket instead of REST):
```json
{
  "type": "action",
  "agent_id": "explorer_01",
  "verb": "OBSERVE",
  "target_id": "atrium",
  "params": {}
}
```

Response sent only to the requesting client:
```json
{
  "type": "action_result",
  "data": { "ok": true, "verb": "OBSERVE", "code": "OK", ... }
}
```

**Heartbeat**:
```json
{"type": "heartbeat"}
```

### 6.5 Disconnection

On WebSocket close, if the agent was registered, the server keeps the registration alive for 2x heartbeat TTL before marking as `disconnected`.

---

## 7. Backward Compatibility

The following legacy endpoints continue to work, mapping internally to v1 handlers:

| Legacy | Maps to |
|--------|---------|
| `GET /api/scene` | Scene snapshot (same as v1) |
| `GET /api/summary` | Scene summary |
| `GET /api/roles` | Viewer role perspectives |
| `GET /api/events?after=N` | Event log |
| `GET /api/agents` | Agent list |
| `POST /api/act` | Action execution |

---

## 8. CORS

Servers SHOULD set:
```
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS
Access-Control-Allow-Headers: Content-Type
```

---

## 9. Future Extensions (v0.2+)

- **Space Registry**: DNS-like discovery of SOAP servers by space_id
- **Federation**: Cross-server agent roaming (agent walks from space A to space B)
- **Spatial Queries**: `GET /api/v1/objects?bbox=x1,y1,z1,x2,y2,z2` — query by bounding box
- **LOD (Level of Detail)**: `?detail=low|medium|high` for bandwidth-constrained devices
- **Conformance Test Suite**: Standardized test set for third-party implementations

---

*SOAP Transport v0.1.0 · Omnity · Apache-2.0*
