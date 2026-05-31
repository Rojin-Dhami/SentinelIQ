// Shared palette for the SentinelIQ admin console.
export const C = {
  bgMain: "#081624",
  bgCard: "#0d1e30",
  bgNav: "#0a1a2e",
  borderCard: "#1e3a52",
  borderSub: "#162d44",
  teal: "#2dd4bf",
  orange: "#f97316",
  red: "#ef4444",
  green: "#4ade80",
  yellow: "#facc15",
  purple: "#c084fc",
  textMuted: "#4a6a85",
  textDim: "#2a4a65",
  textLabel: "#5a7a95",
  textWhite: "#e2eaf2",
} as const;

export const DECISION_COLOR: Record<string, string> = {
  allow: C.green,
  step_up: C.yellow,
  mfa: C.yellow,
  mfa_required: C.yellow,
  block: C.red,
  blocked: C.red,
  hard_block: C.red,
  lock: C.red,
  locked: C.red,
  rate_limited: C.red,
};

export const DECISION_BORDER: Record<string, string> = {
  allow: "#166534",
  step_up: "#ca8a04",
  mfa: "#ca8a04",
  mfa_required: "#ca8a04",
  block: C.red,
  blocked: C.red,
  hard_block: C.red,
  lock: C.red,
  locked: C.red,
  rate_limited: C.red,
};

export const OUTCOME_COLOR: Record<string, string> = {
  success: C.green,
  mfa_verified: C.green,
  failed: C.red,
  failure: C.red,
  blocked: C.red,
  locked: C.red,
  rate_limited: C.red,
  mfa_required: C.yellow,
  step_up: C.yellow,
};

export function outcomeColor(outcome: string | null | undefined): string {
  if (!outcome) return C.textMuted;
  return OUTCOME_COLOR[outcome] ?? C.textMuted;
}

export function decisionColor(decision: string | null | undefined): string {
  if (!decision) return C.textMuted;
  return DECISION_COLOR[decision] ?? C.textMuted;
}

export function decisionBorder(decision: string | null | undefined): string {
  if (!decision) return "#1e3a52";
  return DECISION_BORDER[decision] ?? "#1e3a52";
}
