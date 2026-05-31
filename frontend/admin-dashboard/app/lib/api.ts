// Thin client for the SentinelIQ admin API.
// Requests are same-origin (Next rewrite proxies /api/* to the backend), so
// the httpOnly access_token cookie is automatically attached.

import type {
  AdminEvent,
  AdminUser,
  Decision,
  EventsResponse,
  Outcome,
  StatsResponse,
  Window,
} from "./types";

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown, message: string) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

// If any admin call comes back 401/403, the cookie is gone or has been
// hijacked by another login on the same `localhost` cookie host. Bounce to
// /login instead of letting the dashboard spin on bad credentials.
function handleAuthFailure(status: number, path: string) {
  if (typeof window === "undefined") return;
  if (path.startsWith("/auth/")) return; // login/me handle their own errors
  if (window.location.pathname.startsWith("/login")) return;
  const reason = status === 403 ? "not_admin" : "expired";
  window.location.replace(`/login?err=${reason}`);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
  });

  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    /* empty body */
  }

  if (!res.ok) {
    if (res.status === 401 || res.status === 403) {
      handleAuthFailure(res.status, path);
    }
    const detail =
      body && typeof body === "object" && "detail" in body
        ? (body as { detail: unknown }).detail
        : body;
    const message =
      typeof detail === "string"
        ? detail
        : detail && typeof detail === "object" && "message" in detail
          ? String((detail as { message: unknown }).message)
          : `HTTP ${res.status}`;
    throw new ApiError(res.status, detail, message);
  }
  return body as T;
}

/* ── Auth ──────────────────────────────────────────────────────────────── */

export function me(): Promise<AdminUser> {
  return request<AdminUser>("/auth/me");
}

export function login(payload: unknown): Promise<unknown> {
  return request("/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function logout(): Promise<unknown> {
  return request("/auth/logout", { method: "POST" });
}

/* ── Admin: stats + events ─────────────────────────────────────────────── */

export function getStats(window: Window): Promise<StatsResponse> {
  return request<StatsResponse>(`/admin/stats?window=${window}`);
}

export function listEvents(
  params: {
    limit?: number;
    before_id?: number;
    since_id?: number;
    decision?: Decision;
    outcome?: Outcome;
  } = {},
): Promise<EventsResponse> {
  const qs = new URLSearchParams();
  if (params.limit) qs.set("limit", String(params.limit));
  if (params.before_id) qs.set("before_id", String(params.before_id));
  if (params.since_id) qs.set("since_id", String(params.since_id));
  if (params.decision) qs.set("decision", params.decision);
  if (params.outcome) qs.set("outcome", params.outcome);
  const q = qs.toString();
  return request<EventsResponse>(`/admin/events${q ? `?${q}` : ""}`);
}

export function getEvent(id: number): Promise<AdminEvent> {
  return request<AdminEvent>(`/admin/events/${id}`);
}

/* ── Admin: actions ────────────────────────────────────────────────────── */

export function unlockUser(uuid: string): Promise<unknown> {
  return request(`/admin/users/${uuid}/unlock`, { method: "POST" });
}

export function revokeSession(id: number): Promise<unknown> {
  return request(`/admin/sessions/${id}/revoke`, { method: "POST" });
}

export function revokeAllUserSessions(uuid: string): Promise<unknown> {
  return request(`/admin/users/${uuid}/sessions/revoke`, { method: "POST" });
}

export function simulateAttack(
  scenario: string,
  email: string,
  password: string,
): Promise<{ status: string; scenario: string }> {
  return request(`/admin/simulate/${scenario}`, {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function getScenarios(): Promise<import("./types").ScenariosResponse> {
  return request<import("./types").ScenariosResponse>("/admin/scenarios");
}
