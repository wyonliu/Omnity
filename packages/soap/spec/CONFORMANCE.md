# SOAP Transport Conformance Checklist v0.1

Any server claiming SOAP Transport v0.1 conformance MUST pass all **MUST** items.
**SHOULD** items are recommended but not required.

---

## 1. Scene (4 tests)

| # | Level | Test | Endpoint |
|---|-------|------|----------|
| 1.1 | MUST | `GET /api/v1/scene` returns 200 with `space_id` and `scene` | Scene |
| 1.2 | MUST | `GET /api/v1/scene/summary` returns `object_count`, `region_count` | Scene |
| 1.3 | MUST | Response content-type is `application/json` | Scene |
| 1.4 | SHOULD | Accept `application/soap+json` content type | Scene |

## 2. Objects (8 tests)

| # | Level | Test | Endpoint |
|---|-------|------|----------|
| 2.1 | MUST | `GET /api/v1/objects` returns array of objects | Objects |
| 2.2 | MUST | `GET /api/v1/objects/{id}` returns object with matching `id` | Objects |
| 2.3 | MUST | `GET /api/v1/objects/{id}` returns 404 for unknown ID | Objects |
| 2.4 | MUST | Objects contain `id`, `type`, `reality`, `affordances` | Objects |
| 2.5 | SHOULD | `GET /api/v1/objects/search?type=` filters by type | Search |
| 2.6 | SHOULD | `GET /api/v1/objects/search?affordance=` filters by affordance | Search |
| 2.7 | SHOULD | `GET /api/v1/objects/spatial?cx=&cy=&cz=&radius=` sphere query | Spatial |
| 2.8 | SHOULD | `GET /api/v1/objects/spatial?min_x=..max_z=` AABB query | Spatial |

## 3. Regions (4 tests)

| # | Level | Test | Endpoint |
|---|-------|------|----------|
| 3.1 | MUST | `GET /api/v1/regions` returns array of regions | Regions |
| 3.2 | MUST | `GET /api/v1/regions/{id}` returns 404 for unknown ID | Regions |
| 3.3 | SHOULD | `GET /api/v1/regions/{id}/inventory` returns objects + agents | Regions |
| 3.4 | SHOULD | Region inventory includes `object_count` and `agent_count` | Regions |

## 4. Actions (8 tests)

| # | Level | Test | Endpoint |
|---|-------|------|----------|
| 4.1 | MUST | `POST /api/v1/actions` with OBSERVE returns 200 + `ok: true` | Actions |
| 4.2 | MUST | Unknown verb returns 400 + `UNKNOWN_VERB` | Actions |
| 4.3 | MUST | OBSERVE on unknown target returns 404 + `NOT_FOUND` | Actions |
| 4.4 | MUST | MANIPULATE with non-afforded action returns 403 + `NOT_AFFORDED` | Actions |
| 4.5 | MUST | NAVIGATE with non-soap:// URI returns 400 + `INVALID_URI` | Actions |
| 4.6 | MUST | REARRANGE returns 501 + `NOT_IMPLEMENTED` | Actions |
| 4.7 | MUST | ActionResult contains `ok`, `verb`, `code` | Actions |
| 4.8 | SHOULD | MANIPULATE blocked by lock returns 409 + `LOCK_HELD` | Actions |

## 5. Agents (10 tests)

| # | Level | Test | Endpoint |
|---|-------|------|----------|
| 5.1 | MUST | `POST /api/v1/agents` registers agent (201) | Agents |
| 5.2 | MUST | Duplicate registration returns 409 + `AGENT_EXISTS` | Agents |
| 5.3 | MUST | `GET /api/v1/agents` lists registered agents | Agents |
| 5.4 | MUST | `GET /api/v1/agents/{id}` returns agent detail | Agents |
| 5.5 | MUST | `GET /api/v1/agents/{id}` returns 404 for unknown agent | Agents |
| 5.6 | MUST | `PUT /api/v1/agents/{id}/heartbeat` updates last_heartbeat | Agents |
| 5.7 | MUST | Heartbeat for unregistered agent returns 404 | Agents |
| 5.8 | MUST | `DELETE /api/v1/agents/{id}` removes agent | Agents |
| 5.9 | SHOULD | `GET /api/v1/agents/nearby` returns proximity-based results | Agents |
| 5.10 | SHOULD | `GET /api/v1/agents/query` filters by type/capability/region/status | Agents |

## 6. Locking (6 tests)

| # | Level | Test | Endpoint |
|---|-------|------|----------|
| 6.1 | MUST | `POST /api/v1/objects/{id}/lock` acquires lock | Locking |
| 6.2 | MUST | Lock conflict returns 409 | Locking |
| 6.3 | MUST | `DELETE /api/v1/objects/{id}/lock` releases lock | Locking |
| 6.4 | MUST | Expired locks auto-clear | Locking |
| 6.5 | SHOULD | Same agent can reacquire their own lock | Locking |
| 6.6 | SHOULD | Lock on nonexistent object returns 404 | Locking |

## 7. Input Validation (6 tests)

| # | Level | Test | Endpoint |
|---|-------|------|----------|
| 7.1 | MUST | Empty `agent_id` returns 422 | Agents |
| 7.2 | MUST | `position` with < 3 elements returns 422 | Agents |
| 7.3 | MUST | Negative `ttl_seconds` returns 422 | Locking |
| 7.4 | MUST | `ttl_seconds` > 3600 returns 422 | Locking |
| 7.5 | SHOULD | Whitespace-only `agent_id` returns 422 | Agents |
| 7.6 | SHOULD | `ttl_seconds` = 0 returns 422 | Locking |

## 8. Events (2 tests)

| # | Level | Test | Endpoint |
|---|-------|------|----------|
| 8.1 | MUST | `GET /api/v1/events?after=0` returns events with seq numbers | Events |
| 8.2 | MUST | Events have `seq`, `ts`, `agent_id`, `verb`, `target_id` | Events |

## 9. WebSocket (8 tests)

| # | Level | Test | Endpoint |
|---|-------|------|----------|
| 9.1 | MUST | Connect to `/ws`, send hello, receive welcome | WebSocket |
| 9.2 | MUST | Welcome contains `space_id`, `server_version` | WebSocket |
| 9.3 | MUST | Inline action returns `action_result` | WebSocket |
| 9.4 | MUST | Invalid JSON returns `INVALID_JSON` error | WebSocket |
| 9.5 | SHOULD | Welcome includes `latest_seq` | WebSocket |
| 9.6 | SHOULD | Subscribe/unsubscribe dynamically updates topics | WebSocket |
| 9.7 | SHOULD | `set_region_filter` scopes events | WebSocket |
| 9.8 | SHOULD | Reconnection with `last_seq` replays missed events | WebSocket |

## 10. Semantic Layer (4 tests)

| # | Level | Test | Endpoint |
|---|-------|------|----------|
| 10.1 | SHOULD | `GET /api/v1/discover` returns affordance map | Discover |
| 10.2 | SHOULD | `GET /api/v1/context` returns text description | Context |
| 10.3 | SHOULD | `GET /api/v1/objects/{id}/relationships` returns spatial info | Relationships |
| 10.4 | SHOULD | Relationships include `nearby`, `region_id`, `same_region` | Relationships |

## 11. Permissions (4 tests)

| # | Level | Test | Endpoint |
|---|-------|------|----------|
| 11.1 | SHOULD | Permissions disabled by default (all actions allowed) | Permissions |
| 11.2 | SHOULD | Enabled + no rules = default-deny (403 FORBIDDEN) | Permissions |
| 11.3 | SHOULD | Wildcard permission allows all | Permissions |
| 11.4 | SHOULD | Agent-specific permission restricts by verb/target/region | Permissions |

## 12. Legacy Compatibility (4 tests)

| # | Level | Test | Endpoint |
|---|-------|------|----------|
| 12.1 | SHOULD | `GET /api/scene` returns scene | Legacy |
| 12.2 | SHOULD | `GET /api/summary` returns summary | Legacy |
| 12.3 | SHOULD | `GET /api/events?after=N` returns events | Legacy |
| 12.4 | SHOULD | `POST /api/act` executes action | Legacy |

---

## Summary

| Category | MUST | SHOULD | Total |
|----------|------|--------|-------|
| Scene | 3 | 1 | 4 |
| Objects | 4 | 4 | 8 |
| Regions | 2 | 2 | 4 |
| Actions | 7 | 1 | 8 |
| Agents | 8 | 2 | 10 |
| Locking | 4 | 2 | 6 |
| Input Validation | 4 | 2 | 6 |
| Events | 2 | 0 | 2 |
| WebSocket | 4 | 4 | 8 |
| Semantic | 0 | 4 | 4 |
| Permissions | 0 | 4 | 4 |
| Legacy | 0 | 4 | 4 |
| **Total** | **38** | **30** | **68** |

**Minimum conformance**: All 38 MUST tests pass.
**Full conformance**: All 68 tests pass.

---

*SOAP Conformance Checklist v0.1.0 · Omnity · Apache-2.0*
