/**
 * Ome API Client — talks to ome-server.
 *
 * Supports both anonymous sessions (zero-registration) and authenticated users.
 */

import AsyncStorage from "@react-native-async-storage/async-storage";

const API_BASE = __DEV__
  ? "http://192.168.3.242:8765/api"  // LAN IP for mobile testing
  : "https://api.ome.ai/api"; // TODO: production URL

let _token: string | null = null;
let _sessionId: string | null = null;

// ── Token Management ───────────────────────────────────────────

async function getToken(): Promise<string | null> {
  if (_token) return _token;
  _token = await AsyncStorage.getItem("ome_token");
  return _token;
}

async function setToken(token: string) {
  _token = token;
  await AsyncStorage.setItem("ome_token", token);
}

export async function clearToken() {
  _token = null;
  await AsyncStorage.removeItem("ome_token");
}

export async function isLoggedIn(): Promise<boolean> {
  const token = await getToken();
  return !!token;
}

// ── Session Management (Anonymous) ─────────────────────────────

async function getSessionId(): Promise<string | null> {
  if (_sessionId) return _sessionId;
  _sessionId = await AsyncStorage.getItem("ome_session_id");
  return _sessionId;
}

async function setSessionId(sid: string) {
  _sessionId = sid;
  await AsyncStorage.setItem("ome_session_id", sid);
}

export async function clearSession() {
  _sessionId = null;
  await AsyncStorage.removeItem("ome_session_id");
}

// ── HTTP Helpers ───────────────────────────────────────────────

async function request<T = any>(
  path: string,
  options: { method?: string; body?: any; headers?: Record<string, string> } = {}
): Promise<T> {
  const token = await getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...options.headers,
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    method: options.method || "GET",
    headers,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }

  return res.json();
}

// ── Anonymous Session (Zero Registration) ──────────────────────

export async function createAnonSession(): Promise<string> {
  const result = await request<{ session_id: string }>("/anon/session", {
    method: "POST",
  });
  await setSessionId(result.session_id);
  return result.session_id;
}

export async function ensureSession(): Promise<string> {
  const existing = await getSessionId();
  if (existing) return existing;
  return createAnonSession();
}

export interface AnonChatResult {
  reply: string;
  mood: string;
  mood_emoji: string;
  message_count: number;
  session_id: string;
}

export async function anonChat(message: string): Promise<AnonChatResult> {
  const sessionId = await ensureSession();
  return request("/anon/chat", {
    method: "POST",
    body: { message },
    headers: { "X-Session-ID": sessionId },
  });
}

// ── Auth ───────────────────────────────────────────────────────

export interface AuthResult {
  token: string;
  user_id: string;
  name: string;
}

export async function register(params: {
  user_id: string;
  password: string;
  name: string;
  traits?: string[];
  style?: string;
  session_id?: string | null;
}): Promise<AuthResult> {
  // Include session_id to migrate anonymous chat history
  const sessionId = params.session_id ?? (await getSessionId());
  const result = await request<AuthResult>("/auth/register", {
    method: "POST",
    body: { ...params, session_id: sessionId },
  });
  await setToken(result.token);
  await AsyncStorage.setItem("ome_user_id", result.user_id);
  await AsyncStorage.setItem("ome_name", result.name);
  await clearSession(); // Anonymous session migrated
  return result;
}

export async function login(
  user_id: string,
  password: string
): Promise<AuthResult> {
  const result = await request<AuthResult>("/auth/login", {
    method: "POST",
    body: { user_id, password },
  });
  await setToken(result.token);
  await AsyncStorage.setItem("ome_user_id", result.user_id);
  await AsyncStorage.setItem("ome_name", result.name);
  return result;
}

// ── Chat (Authenticated) ──────────────────────────────────────

export interface ChatResult {
  reply: string;
  mood: string;
  mood_emoji: string;
  bond_level: number;
  streak_days: number;
}

export async function chat(message: string): Promise<ChatResult> {
  return request("/chat", { method: "POST", body: { message } });
}

export async function mirror(message: string): Promise<ChatResult> {
  return request("/mirror", { method: "POST", body: { message } });
}

// ── SSE Streaming Chat ────────────────────────────────────────

export interface StreamCallbacks {
  onToken: (token: string) => void;
  onDone: (result: ChatResult & { full_reply: string }) => void;
  onError: (error: Error) => void;
}

export async function chatStream(
  message: string,
  callbacks: StreamCallbacks
): Promise<void> {
  const token = await getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  try {
    const res = await fetch(`${API_BASE}/chat/stream`, {
      method: "POST",
      headers,
      body: JSON.stringify({ message }),
    });

    if (!res.ok) {
      throw new Error(`Stream failed: HTTP ${res.status}`);
    }

    const reader = res.body?.getReader();
    if (!reader) throw new Error("No response body");

    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const jsonStr = line.slice(6).trim();
        if (!jsonStr) continue;

        try {
          const data = JSON.parse(jsonStr);
          if (data.done) {
            callbacks.onDone(data);
          } else if (data.token !== undefined) {
            callbacks.onToken(data.token);
          }
        } catch {
          // Skip malformed JSON
        }
      }
    }
  } catch (e: any) {
    callbacks.onError(e);
  }
}

export async function calibrate(
  message: string,
  response: string,
  feedback: string
) {
  return request("/calibrate", {
    method: "POST",
    body: { message, response, feedback },
  });
}

// ── Life ──────────────────────────────────────────────────────

export async function getDashboard() {
  return request("/dashboard");
}

export async function getProfile() {
  return request("/profile");
}

export async function getStatus() {
  return request("/status");
}

export async function getEvents() {
  return request("/events");
}

// ── Memory ────────────────────────────────────────────────────

export async function remember(text: string) {
  return request("/remember", { method: "POST", body: { text } });
}

export async function recall(query: string, top_k = 10) {
  return request("/recall", {
    method: "POST",
    body: { query, top_k },
  });
}

// ── Skills ────────────────────────────────────────────────────

export async function listSkills() {
  return request("/skills");
}

export async function useSkill(name: string, kwargs: Record<string, any> = {}) {
  return request(`/skills/${name}`, { method: "POST", body: { kwargs } });
}

// ── Agent Network (OmeTown) ───────────────────────────────────

export async function getAgentDirectory() {
  return request("/agents/directory");
}

export async function introduceToAgent(targetId: string, greeting = "") {
  return request(`/agents/${targetId}/introduce`, {
    method: "POST",
    body: { greeting },
  });
}

export async function messageAgent(
  targetId: string,
  message: string,
  context = ""
) {
  return request(`/agents/${targetId}/message`, {
    method: "POST",
    body: { message, context },
  });
}

export async function getAgentProfile(targetId: string) {
  return request(`/agents/${targetId}/profile`);
}
