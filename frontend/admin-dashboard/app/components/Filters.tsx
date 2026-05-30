"use client";

import { C } from "../lib/theme";
import type { Decision, Outcome } from "../lib/types";

const DECISIONS:
  | { value: ""; label: string }[]
  | { value: string; label: string }[] = [
  { value: "", label: "All decisions" },
  { value: "allow", label: "Allow" },
  { value: "step_up", label: "Step-up" },
  { value: "mfa", label: "MFA" },
  { value: "block", label: "Block" },
  { value: "lock", label: "Lock" },
];

const OUTCOMES = [
  { value: "", label: "All outcomes" },
  { value: "success", label: "Success" },
  { value: "failed_credentials", label: "Failed credentials" },
  { value: "blocked_risk", label: "Blocked: risk" },
  { value: "blocked_velocity", label: "Blocked: velocity" },
  { value: "mfa_required", label: "MFA required" },
  { value: "mfa_verified", label: "MFA verified" },
];

interface Props {
  decision: Decision | "";
  outcome: Outcome | "";
  onDecision: (d: Decision | "") => void;
  onOutcome: (o: Outcome | "") => void;
}

export default function Filters({
  decision,
  outcome,
  onDecision,
  onOutcome,
}: Props) {
  return (
    <div style={{ display: "flex", gap: 8 }}>
      <Select
        value={decision}
        onChange={(v) => onDecision(v as Decision | "")}
        options={DECISIONS}
      />
      <Select
        value={outcome}
        onChange={(v) => onOutcome(v as Outcome | "")}
        options={OUTCOMES}
      />
    </div>
  );
}

function Select({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      style={{
        background: C.bgCard,
        color: value ? C.teal : C.textMuted,
        border: `1px solid ${value ? C.teal : C.borderCard}`,
        borderRadius: 6,
        padding: "5px 10px",
        fontSize: 10,
        fontFamily: "monospace",
        letterSpacing: "0.1em",
        textTransform: "uppercase",
        cursor: "pointer",
        outline: "none",
      }}
    >
      {options.map((o) => (
        <option key={o.value} value={o.value} style={{ background: C.bgCard }}>
          {o.label}
        </option>
      ))}
    </select>
  );
}
