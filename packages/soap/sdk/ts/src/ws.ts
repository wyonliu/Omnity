/**
 * SOAP WebSocket Client — real-time event streaming.
 *
 * Features:
 * - Auto-reconnection with exponential backoff
 * - Event sequencing and catch-up on reconnect
 * - Topic subscription management
 * - Region-scoped filtering
 * - Inline actions via WebSocket
 */

import type {
  WSSubscriptionTopic,
  WSServerMessage,
  WSWelcomeMessage,
  WSEventMessage,
  WSActionResultMessage,
  WSErrorMessage,
  ActionResult,
} from "./types.js";

export interface SOAPWSOptions {
  /** WebSocket URL (e.g. "ws://localhost:8765/ws") */
  url: string;
  /** Agent ID */
  agentId: string;
  /** Topics to subscribe to */
  subscribe?: WSSubscriptionTopic[];
  /** Region filter (only receive events from this region) */
  regionFilter?: string | null;
  /** Auto-reconnect on disconnect */
  autoReconnect?: boolean;
  /** Max reconnect attempts (0 = unlimited) */
  maxReconnectAttempts?: number;
  /** Custom WebSocket constructor (for Node.js) */
  WebSocket?: typeof globalThis.WebSocket;
}

type EventHandler<T> = (data: T) => void;

export class SOAPWebSocket {
  private url: string;
  private agentId: string;
  private topics: Set<WSSubscriptionTopic>;
  private regionFilter: string | null;
  private autoReconnect: boolean;
  private maxReconnectAttempts: number;
  private _WS: typeof globalThis.WebSocket;

  private ws: WebSocket | null = null;
  private lastSeq = 0;
  private reconnectAttempts = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private connected = false;
  private spaceId = "";

  // Event handlers
  private onWelcome: EventHandler<WSWelcomeMessage>[] = [];
  private onEvent: EventHandler<WSEventMessage>[] = [];
  private onActionResult: EventHandler<WSActionResultMessage>[] = [];
  private onError: EventHandler<WSErrorMessage>[] = [];
  private onConnect: EventHandler<void>[] = [];
  private onDisconnect: EventHandler<{ code: number; reason: string }>[] = [];

  // Pending action callbacks
  private pendingActions: Map<
    string,
    { resolve: (r: ActionResult) => void; reject: (e: Error) => void }
  > = new Map();
  private actionSeq = 0;

  constructor(options: SOAPWSOptions) {
    this.url = options.url;
    this.agentId = options.agentId;
    this.topics = new Set(options.subscribe ?? ["events"]);
    this.regionFilter = options.regionFilter ?? null;
    this.autoReconnect = options.autoReconnect ?? true;
    this.maxReconnectAttempts = options.maxReconnectAttempts ?? 0;
    this._WS = options.WebSocket ?? globalThis.WebSocket;
  }

  // ── Connection ─────────────────────────────────────────────

  connect(): void {
    if (this.ws) return;
    this.ws = new this._WS(this.url);

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      // send hello
      this.ws!.send(
        JSON.stringify({
          type: "hello",
          agent_id: this.agentId,
          subscribe: Array.from(this.topics),
          region_filter: this.regionFilter,
          last_seq: this.lastSeq,
        })
      );
    };

    this.ws.onmessage = (event) => {
      const msg: WSServerMessage = JSON.parse(event.data as string);
      this.handleMessage(msg);
    };

    this.ws.onclose = (event) => {
      this.connected = false;
      this.ws = null;
      this.onDisconnect.forEach((h) =>
        h({ code: event.code, reason: event.reason })
      );
      if (this.autoReconnect) {
        this.scheduleReconnect();
      }
    };

    this.ws.onerror = () => {
      // onclose will fire after onerror
    };
  }

  disconnect(): void {
    this.autoReconnect = false;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.ws?.close();
    this.ws = null;
    this.connected = false;
  }

  get isConnected(): boolean {
    return this.connected;
  }

  // ── Message handling ───────────────────────────────────────

  private handleMessage(msg: WSServerMessage): void {
    switch (msg.type) {
      case "welcome":
        this.connected = true;
        this.spaceId = msg.space_id;
        this.onWelcome.forEach((h) => h(msg));
        this.onConnect.forEach((h) => h());
        break;

      case "event":
        this.lastSeq = Math.max(this.lastSeq, msg.seq);
        this.onEvent.forEach((h) => h(msg));
        break;

      case "action_result":
        this.onActionResult.forEach((h) => h(msg));
        // resolve pending action promise if any
        // (we use a simple FIFO since WS is ordered)
        if (this.pendingActions.size > 0) {
          const [key, pending] = this.pendingActions.entries().next().value!;
          this.pendingActions.delete(key);
          pending.resolve(msg.data);
        }
        break;

      case "error":
        this.onError.forEach((h) => h(msg));
        break;
    }
  }

  // ── Reconnection ───────────────────────────────────────────

  private scheduleReconnect(): void {
    if (
      this.maxReconnectAttempts > 0 &&
      this.reconnectAttempts >= this.maxReconnectAttempts
    ) {
      return;
    }
    const delay = Math.min(1000 * 2 ** this.reconnectAttempts, 30000);
    this.reconnectAttempts++;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
  }

  // ── Topic management ───────────────────────────────────────

  subscribe(...topics: WSSubscriptionTopic[]): void {
    for (const t of topics) this.topics.add(t);
    if (this.ws?.readyState === this._WS.OPEN) {
      this.ws.send(JSON.stringify({ type: "subscribe", topics }));
    }
  }

  unsubscribe(...topics: WSSubscriptionTopic[]): void {
    for (const t of topics) this.topics.delete(t);
    if (this.ws?.readyState === this._WS.OPEN) {
      this.ws.send(JSON.stringify({ type: "unsubscribe", topics }));
    }
  }

  setRegionFilter(regionId: string | null): void {
    this.regionFilter = regionId;
    if (this.ws?.readyState === this._WS.OPEN) {
      this.ws.send(
        JSON.stringify({ type: "set_region_filter", region_id: regionId })
      );
    }
  }

  // ── Inline actions ─────────────────────────────────────────

  sendAction(
    verb: string,
    targetId: string,
    params?: Record<string, unknown>
  ): Promise<ActionResult> {
    return new Promise((resolve, reject) => {
      if (!this.ws || this.ws.readyState !== this._WS.OPEN) {
        reject(new Error("WebSocket not connected"));
        return;
      }
      const key = `action_${++this.actionSeq}`;
      this.pendingActions.set(key, { resolve, reject });
      this.ws.send(
        JSON.stringify({
          type: "action",
          agent_id: this.agentId,
          verb,
          target_id: targetId,
          params: params ?? {},
        })
      );
    });
  }

  sendHeartbeat(): void {
    if (this.ws?.readyState === this._WS.OPEN) {
      this.ws.send(JSON.stringify({ type: "heartbeat" }));
    }
  }

  // ── Event registration ─────────────────────────────────────

  on(event: "welcome", handler: EventHandler<WSWelcomeMessage>): this;
  on(event: "event", handler: EventHandler<WSEventMessage>): this;
  on(event: "action_result", handler: EventHandler<WSActionResultMessage>): this;
  on(event: "error", handler: EventHandler<WSErrorMessage>): this;
  on(event: "connect", handler: EventHandler<void>): this;
  on(
    event: "disconnect",
    handler: EventHandler<{ code: number; reason: string }>
  ): this;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  on(event: string, handler: EventHandler<any>): this {
    switch (event) {
      case "welcome":
        this.onWelcome.push(handler as EventHandler<WSWelcomeMessage>);
        break;
      case "event":
        this.onEvent.push(handler as EventHandler<WSEventMessage>);
        break;
      case "action_result":
        this.onActionResult.push(
          handler as EventHandler<WSActionResultMessage>
        );
        break;
      case "error":
        this.onError.push(handler as EventHandler<WSErrorMessage>);
        break;
      case "connect":
        this.onConnect.push(handler as EventHandler<void>);
        break;
      case "disconnect":
        this.onDisconnect.push(
          handler as EventHandler<{ code: number; reason: string }>
        );
        break;
    }
    return this;
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  off(event: string, handler: EventHandler<any>): this {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const remove = <T>(arr: EventHandler<T>[], h: EventHandler<any>) => {
      const idx = arr.indexOf(h as EventHandler<T>);
      if (idx >= 0) arr.splice(idx, 1);
    };
    switch (event) {
      case "welcome":
        remove(this.onWelcome, handler);
        break;
      case "event":
        remove(this.onEvent, handler);
        break;
      case "action_result":
        remove(this.onActionResult, handler);
        break;
      case "error":
        remove(this.onError, handler);
        break;
      case "connect":
        remove(this.onConnect, handler);
        break;
      case "disconnect":
        remove(this.onDisconnect, handler);
        break;
    }
    return this;
  }
}
