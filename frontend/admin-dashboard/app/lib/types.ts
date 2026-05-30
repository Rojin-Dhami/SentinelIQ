// Shared API types mirroring the backend admin endpoints.

export type Window = "1h" | "24h" | "7d" | "30d";

export type Decision = "allow" | "step_up" | "mfa" | "block" | "lock" | string;

export type Outcome =
  | "success"
  | "failed_credentials"
  | "blocked_risk"
  | "blocked_velocity"
  | "mfa_required"
  | "mfa_verified"
  | string;

export interface AdminEvent {
  id: number;
  created_at: string | null;
  user_id: number | null;
  user_email: string | null;
  ip: string | null;
  city: string | null;
  country: string | null;
  device_fingerprint: string | null;
  outcome: Outcome | null;
  decision: Decision | null;
  risk_score: number | null;
  breakdown: Record<string, unknown> | null;
}

export interface StatsResponse {
  window: Window;
  since: string;
  total: number;
  unique_users: number;
  unique_ips: number;
  by_outcome: Record<string, number>;
  by_decision: Record<string, number>;
}

export interface EventsResponse {
  items: AdminEvent[];
  count: number;
  next_before_id: number | null;
}

export interface AdminUser {
  uuid: string;
  email: string;
  full_name: string | null;
  role: string;
  is_verified: boolean;
}
