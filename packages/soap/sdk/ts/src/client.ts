/**
 * SOAP REST Client — HTTP interface for SOAP servers.
 *
 * Works in browser (fetch) and Node.js (18+ with global fetch).
 * Zero dependencies.
 */

import type {
  SOAPScene,
  SOAPObject,
  SOAPRegion,
  AgentAction,
  ActionResult,
  AgentRegistration,
  AgentRecord,
  LockInfo,
  AffordanceDiscovery,
  RegionInventory,
  SpatialRelationships,
  PermissionRule,
} from "./types.js";

export interface SOAPClientOptions {
  /** Base URL of the SOAP server (e.g. "http://localhost:8765") */
  baseUrl: string;
  /** Default agent ID for actions */
  agentId?: string;
  /** Custom fetch implementation (for Node.js < 18 or testing) */
  fetch?: typeof globalThis.fetch;
}

export class SOAPClient {
  private baseUrl: string;
  private agentId: string;
  private _fetch: typeof globalThis.fetch;

  constructor(options: SOAPClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/$/, "");
    this.agentId = options.agentId ?? "anonymous";
    this._fetch = options.fetch ?? globalThis.fetch.bind(globalThis);
  }

  // ── Internal helpers ─────────────────────────────────────

  private async get<T>(path: string): Promise<T> {
    const res = await this._fetch(`${this.baseUrl}${path}`, {
      headers: { Accept: "application/json" },
    });
    if (!res.ok) {
      const body = await res.text();
      throw new SOAPError(res.status, body, path);
    }
    return res.json() as Promise<T>;
  }

  private async post<T>(path: string, body: unknown): Promise<T> {
    const res = await this._fetch(`${this.baseUrl}${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new SOAPError(res.status, JSON.stringify(data), path);
    }
    return data as T;
  }

  private async put<T>(path: string, body?: unknown): Promise<T> {
    const res = await this._fetch(`${this.baseUrl}${path}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: body ? JSON.stringify(body) : undefined,
    });
    const data = await res.json();
    if (!res.ok) {
      throw new SOAPError(res.status, JSON.stringify(data), path);
    }
    return data as T;
  }

  private async del<T>(path: string): Promise<T> {
    const res = await this._fetch(`${this.baseUrl}${path}`, {
      method: "DELETE",
      headers: { Accept: "application/json" },
    });
    const data = await res.json();
    if (!res.ok) {
      throw new SOAPError(res.status, JSON.stringify(data), path);
    }
    return data as T;
  }

  // ── Scene ────────────────────────────────────────────────

  async getScene(): Promise<{ space_id: string; scene: SOAPScene }> {
    return this.get("/api/v1/scene");
  }

  async getSummary(): Promise<Record<string, unknown>> {
    return this.get("/api/v1/scene/summary");
  }

  // ── Objects ──────────────────────────────────────────────

  async listObjects(): Promise<SOAPObject[]> {
    const r = await this.get<{ objects: SOAPObject[] }>("/api/v1/objects");
    return r.objects;
  }

  async getObject(id: string): Promise<SOAPObject> {
    return this.get(`/api/v1/objects/${encodeURIComponent(id)}`);
  }

  async searchObjects(params: {
    type?: string;
    reality?: string;
    affordance?: string;
    tag?: string;
    region_id?: string;
  }): Promise<SOAPObject[]> {
    const qs = new URLSearchParams();
    if (params.type) qs.set("type", params.type);
    if (params.reality) qs.set("reality", params.reality);
    if (params.affordance) qs.set("affordance", params.affordance);
    if (params.tag) qs.set("tag", params.tag);
    if (params.region_id) qs.set("region_id", params.region_id);
    const r = await this.get<{ objects: SOAPObject[] }>(
      `/api/v1/objects/search?${qs}`
    );
    return r.objects;
  }

  async spatialQuery(params: {
    center?: [number, number, number];
    radius?: number;
    bboxMin?: [number, number, number];
    bboxMax?: [number, number, number];
  }): Promise<SOAPObject[]> {
    const qs = new URLSearchParams();
    if (params.center) {
      qs.set("cx", String(params.center[0]));
      qs.set("cy", String(params.center[1]));
      qs.set("cz", String(params.center[2]));
    }
    if (params.radius != null) qs.set("radius", String(params.radius));
    if (params.bboxMin) {
      qs.set("min_x", String(params.bboxMin[0]));
      qs.set("min_y", String(params.bboxMin[1]));
      qs.set("min_z", String(params.bboxMin[2]));
    }
    if (params.bboxMax) {
      qs.set("max_x", String(params.bboxMax[0]));
      qs.set("max_y", String(params.bboxMax[1]));
      qs.set("max_z", String(params.bboxMax[2]));
    }
    const r = await this.get<{ objects: SOAPObject[] }>(
      `/api/v1/objects/spatial?${qs}`
    );
    return r.objects;
  }

  // ── Regions ──────────────────────────────────────────────

  async listRegions(): Promise<SOAPRegion[]> {
    const r = await this.get<{ regions: SOAPRegion[] }>("/api/v1/regions");
    return r.regions;
  }

  async getRegion(id: string): Promise<SOAPRegion> {
    return this.get(`/api/v1/regions/${encodeURIComponent(id)}`);
  }

  async getRegionInventory(id: string): Promise<RegionInventory> {
    return this.get(`/api/v1/regions/${encodeURIComponent(id)}/inventory`);
  }

  // ── Actions ──────────────────────────────────────────────

  async act(
    verb: AgentAction["verb"],
    targetId: string,
    params?: Record<string, unknown>
  ): Promise<ActionResult> {
    return this.post("/api/v1/actions", {
      agent_id: this.agentId,
      verb,
      target_id: targetId,
      params: params ?? {},
    });
  }

  async observe(targetId: string): Promise<ActionResult> {
    return this.act("OBSERVE", targetId);
  }

  async navigate(
    objectId: string,
    targetUri: string
  ): Promise<ActionResult> {
    return this.act("NAVIGATE", objectId, { target_uri: targetUri });
  }

  async manipulate(
    objectId: string,
    action: string,
    params?: Record<string, unknown>
  ): Promise<ActionResult> {
    return this.act("MANIPULATE", objectId, { action, ...params });
  }

  // ── Events ───────────────────────────────────────────────

  async getEvents(afterSeq = 0): Promise<{
    events: Record<string, unknown>[];
    latest_seq: number;
  }> {
    return this.get(`/api/v1/events?after=${afterSeq}`);
  }

  // ── Agents ───────────────────────────────────────────────

  async registerAgent(
    reg: AgentRegistration
  ): Promise<{ ok: boolean; agent: AgentRecord }> {
    return this.post("/api/v1/agents", reg);
  }

  async listAgents(): Promise<AgentRecord[]> {
    const r = await this.get<{ agents: AgentRecord[] }>("/api/v1/agents");
    return r.agents;
  }

  async getAgent(id: string): Promise<AgentRecord> {
    return this.get(`/api/v1/agents/${encodeURIComponent(id)}`);
  }

  async heartbeat(
    agentId?: string,
    position?: [number, number, number],
    status = "active"
  ): Promise<{ ok: boolean; agent: AgentRecord }> {
    const id = agentId ?? this.agentId;
    return this.put(`/api/v1/agents/${encodeURIComponent(id)}/heartbeat`, {
      position,
      status,
    });
  }

  async deregisterAgent(
    agentId?: string
  ): Promise<{ ok: boolean }> {
    const id = agentId ?? this.agentId;
    return this.del(`/api/v1/agents/${encodeURIComponent(id)}`);
  }

  async nearbyAgents(
    agentId?: string,
    radius = 10
  ): Promise<AgentRecord[]> {
    const id = agentId ?? this.agentId;
    const r = await this.get<{ agents: AgentRecord[] }>(
      `/api/v1/agents/nearby?agent_id=${encodeURIComponent(id)}&radius=${radius}`
    );
    return r.agents;
  }

  // ── Locking ──────────────────────────────────────────────

  async acquireLock(
    objectId: string,
    ttlSeconds = 30
  ): Promise<LockInfo & { ok: boolean }> {
    return this.post(
      `/api/v1/objects/${encodeURIComponent(objectId)}/lock`,
      { agent_id: this.agentId, ttl_seconds: ttlSeconds }
    );
  }

  async checkLock(
    objectId: string
  ): Promise<{ locked: boolean } & Partial<LockInfo>> {
    return this.get(
      `/api/v1/objects/${encodeURIComponent(objectId)}/lock`
    );
  }

  async releaseLock(objectId: string): Promise<{ ok: boolean }> {
    return this.del(
      `/api/v1/objects/${encodeURIComponent(objectId)}/lock?agent_id=${encodeURIComponent(this.agentId)}`
    );
  }

  // ── Semantic ─────────────────────────────────────────────

  async discover(params?: {
    regionId?: string;
    center?: [number, number, number];
    radius?: number;
  }): Promise<AffordanceDiscovery> {
    const qs = new URLSearchParams();
    if (params?.regionId) qs.set("region_id", params.regionId);
    if (params?.center) {
      qs.set("cx", String(params.center[0]));
      qs.set("cy", String(params.center[1]));
      qs.set("cz", String(params.center[2]));
    }
    if (params?.radius != null) qs.set("radius", String(params.radius));
    return this.get(`/api/v1/discover?${qs}`);
  }

  async getContext(params?: {
    agentId?: string;
    regionId?: string;
  }): Promise<{ description: string }> {
    const qs = new URLSearchParams();
    if (params?.agentId) qs.set("agent_id", params.agentId);
    if (params?.regionId) qs.set("region_id", params.regionId);
    return this.get(`/api/v1/context?${qs}`);
  }

  async getRelationships(
    objectId: string,
    radius = 10
  ): Promise<SpatialRelationships> {
    return this.get(
      `/api/v1/objects/${encodeURIComponent(objectId)}/relationships?radius=${radius}`
    );
  }
}

// ── Error class ──────────────────────────────────────────────

export class SOAPError extends Error {
  constructor(
    public status: number,
    public body: string,
    public path: string
  ) {
    super(`SOAP ${status} on ${path}: ${body}`);
    this.name = "SOAPError";
  }
}
