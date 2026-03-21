/**
 * SOAP SDK — TypeScript client for Spatial Omnity Agentic Protocol
 *
 * @example
 * ```ts
 * import { SOAPClient, SOAPWebSocket } from "soap-sdk";
 *
 * // REST client
 * const client = new SOAPClient({ baseUrl: "http://localhost:8765", agentId: "my_bot" });
 * const scene = await client.getScene();
 * const result = await client.observe("fountain_center");
 *
 * // WebSocket for real-time events
 * const ws = new SOAPWebSocket({ url: "ws://localhost:8765/ws", agentId: "my_bot" });
 * ws.on("event", (e) => console.log(e.topic, e.data));
 * ws.connect();
 * ```
 */

export { SOAPClient, SOAPError } from "./client.js";
export type { SOAPClientOptions } from "./client.js";

export { SOAPWebSocket } from "./ws.js";
export type { SOAPWSOptions } from "./ws.js";

export type {
  // Scene
  SOAPScene,
  SOAPObject,
  SOAPRegion,
  CoordinateFrame,
  // Actions
  AgentAction,
  ActionResult,
  SOAPStatusCode,
  // Agents
  AgentRegistration,
  AgentRecord,
  // Locking
  LockInfo,
  // WebSocket
  WSSubscriptionTopic,
  WSHelloMessage,
  WSWelcomeMessage,
  WSEventMessage,
  WSActionResultMessage,
  WSErrorMessage,
  WSServerMessage,
  // Semantic
  AffordanceDiscovery,
  RegionInventory,
  SpatialRelationships,
  // Permissions
  PermissionRule,
} from "./types.js";
