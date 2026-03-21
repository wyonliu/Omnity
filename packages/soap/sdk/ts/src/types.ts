/**
 * SOAP SDK Type Definitions
 * Mirrors the SOAP Transport Spec v0.1
 */

// ── Scene ────────────────────────────────────────────────────

export interface SOAPScene {
  soap_version: string;
  space_id: string;
  title?: string;
  coordinate_frame?: CoordinateFrame;
  objects: SOAPObject[];
  regions: SOAPRegion[];
}

export interface CoordinateFrame {
  type: string;
  up: number[];
  units: string;
}

export interface SOAPObject {
  id: string;
  type?: string;
  reality?: "physical" | "virtual" | "mixed";
  affordances?: string[];
  state?: Record<string, unknown>;
  bounds?: {
    type: string;
    min: number[];
    max: number[];
  };
  tags?: string[];
  bindings?: Record<string, unknown>;
}

export interface SOAPRegion {
  id: string;
  name?: string;
  purpose_tags?: string[];
  contained_object_ids?: string[];
}

// ── Actions ──────────────────────────────────────────────────

export interface AgentAction {
  agent_id: string;
  verb: "OBSERVE" | "NAVIGATE" | "MANIPULATE" | "REARRANGE";
  target_id: string;
  params?: Record<string, unknown>;
}

export interface ActionResult {
  ok: boolean;
  verb: string;
  code: SOAPStatusCode;
  detail?: string;
  data?: Record<string, unknown>;
}

export type SOAPStatusCode =
  | "OK"
  | "NOT_FOUND"
  | "UNKNOWN_OBJECT"
  | "UNKNOWN_VERB"
  | "NOT_AFFORDED"
  | "NOT_IMPLEMENTED"
  | "INVALID_URI"
  | "LOCK_HELD"
  | "AGENT_EXISTS"
  | "AGENT_NOT_FOUND"
  | "FORBIDDEN";

// ── Agents ───────────────────────────────────────────────────

export interface AgentRegistration {
  agent_id: string;
  agent_type?: "human" | "autonomous" | "npc" | "robot" | "unknown";
  capabilities?: string[];
  position?: [number, number, number];
  meta?: Record<string, unknown>;
}

export interface AgentRecord {
  id: string;
  agent_type: string;
  capabilities: string[];
  position?: number[];
  near_target: string;
  status: "active" | "stale" | "disconnected";
  hp: number;
  action_count: number;
  registered_at: number;
  last_heartbeat: number;
  meta?: Record<string, unknown>;
}

// ── Locking ──────────────────────────────────────────────────

export interface LockInfo {
  object_id: string;
  agent_id: string;
  lock_id: string;
  acquired_at: number;
  ttl: number;
  expires_at: number;
  expired: boolean;
}

// ── WebSocket ────────────────────────────────────────────────

export type WSSubscriptionTopic =
  | "events"
  | "agents"
  | "locks"
  | "state"
  | "regions";

export interface WSHelloMessage {
  type: "hello";
  agent_id: string;
  subscribe: WSSubscriptionTopic[];
  region_filter?: string | null;
  last_seq?: number;
}

export interface WSWelcomeMessage {
  type: "welcome";
  agent_id: string;
  space_id: string;
  server_version: string;
  ws_id: string;
  latest_seq: number;
}

export interface WSEventMessage {
  type: "event";
  topic: string;
  runtime_topic: string;
  seq: number;
  data: Record<string, unknown>;
}

export interface WSActionResultMessage {
  type: "action_result";
  data: ActionResult;
}

export interface WSErrorMessage {
  type: "error";
  code: string;
  detail: string;
}

export type WSServerMessage =
  | WSWelcomeMessage
  | WSEventMessage
  | WSActionResultMessage
  | WSErrorMessage;

// ── Semantic ─────────────────────────────────────────────────

export interface AffordanceDiscovery {
  affordance_count: number;
  object_count: number;
  affordances: Record<string, string[]>;
}

export interface RegionInventory {
  region_id: string;
  name?: string;
  purpose_tags?: string[];
  object_count: number;
  objects: SOAPObject[];
  agent_count: number;
  agents: AgentRecord[];
}

export interface SpatialRelationships {
  object_id: string;
  region_id?: string;
  region_name?: string;
  same_region?: string[];
  nearby?: string[];
}

// ── Permissions ──────────────────────────────────────────────

export interface PermissionRule {
  agent_id: string;
  verbs: string[];
  target_ids: string[];
  region_ids: string[];
}
