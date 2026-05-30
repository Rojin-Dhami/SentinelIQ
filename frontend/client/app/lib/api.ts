// Thin client for the SentinelIQ backend (FastAPI under /api/auth/*).
// All session-establishing endpoints set httpOnly cookies, so every call must
// be made with credentials: "include" and the backend must allow the origin.

import type {
  DeviceSpec,
  NetworkContext,
  SessionMetadata,
} from "../login/collectors";
import type { BehavioralSignals } from "../login/useBehavior";

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api";

/* ── Request payloads ────────────────────────────────────────────────────── */

export interface LoginRequest {
  credentials: { email: string; password: string };
  device_spec: DeviceSpec;
  network_context: NetworkContext;
  behavioral_signals: BehavioralSignals;
  session_metadata: SessionMetadata;
}

export interface RegisterRequest {
  credentials: { full_name: string; email: string; password: string };
  device_spec: DeviceSpec;
  network_context: NetworkContext;
  behavioral_signals: BehavioralSignals;
  session_metadata: SessionMetadata;
}

export interface RegisterVerifyRequest {
  email: string;
  otp: string;
}

export interface MfaVerifyRequest {
  challenge_id: string;
  otp: string;
  remember_device?: boolean;
}

export interface MfaRequestRequest {
  credentials: { email: string; password: string };
  device_spec: DeviceSpec;
  network_context: NetworkContext;
  behavioral_signals: BehavioralSignals;
  session_metadata: SessionMetadata;
}

/* ── Response shapes ─────────────────────────────────────────────────────── */

export type LoginResponse =
  | {
      status: "ok";
      uuid: string;
      email: string;
      risk: number;
    }
  | {
      status: "mfa_required";
      challenge_id: string;
      expires_in: number;
      risk: number;
    };

export interface RegisterResponse {
  status: "otp_sent";
  email: string;
  expires_in: number;
}

export interface SessionUser {
  uuid: string;
  email: string;
  full_name: string | null;
  role: string;
  is_verified: boolean;
}

/* ── Error helper ────────────────────────────────────────────────────────── */

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown, message: string) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
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

/* ── Endpoints ───────────────────────────────────────────────────────────── */

export const api = {
  register: (body: RegisterRequest) =>
    request<RegisterResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  registerVerify: (body: RegisterVerifyRequest) =>
    request<SessionUser & { status: "ok" }>("/auth/register/verify", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  login: (body: LoginRequest) =>
    request<LoginResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  mfaVerify: (body: MfaVerifyRequest) =>
    request<{
      status: "ok";
      uuid: string;
      email: string;
      device_trusted: boolean;
    }>("/auth/mfa/verify", { method: "POST", body: JSON.stringify(body) }),

  mfaRequest: (body: MfaRequestRequest) =>
    request<{
      status: "mfa_required";
      challenge_id: string;
      expires_in: number;
    }>("/auth/mfa/request", { method: "POST", body: JSON.stringify(body) }),

  me: () => request<SessionUser>("/auth/me", { method: "GET" }),

  refresh: () => request<{ status: "ok" }>("/auth/refresh", { method: "POST" }),

  logout: () => request<{ status: "ok" }>("/auth/logout", { method: "POST" }),

  securityConfirm: (token: string) =>
    request<{ status: "ok"; message: string }>(
      `/auth/security/confirm?token=${encodeURIComponent(token)}`,
      { method: "GET" },
    ),

  securityDeny: (token: string) =>
    request<{ status: "ok"; message: string; sessions_revoked: number }>(
      `/auth/security/deny?token=${encodeURIComponent(token)}`,
      { method: "GET" },
    ),
};
