"use client";

import { C } from "../lib/theme";
import type { StatsResponse } from "../lib/types";

function fmt(n: number): string {
  return n.toLocaleString();
}

function sum(obj: Record<string, number> | undefined, keys: string[]): number {
  if (!obj) return 0;
  return keys.reduce((acc, k) => acc + (obj[k] ?? 0), 0);
}

function StatCard({
  label,
  value,
  sub,
  valueColor,
  borderColor,
}: {
  label: string;
  value: string;
  sub: string;
  valueColor: string;
  borderColor: string;
}) {
  return (
    <div
      style={{
        flex: 1,
        minWidth: 180,
        background: C.bgCard,
        border: `1.5px solid ${borderColor}`,
        borderRadius: 12,
        padding: "16px 20px",
      }}
    >
      <div
        style={{
          fontSize: 10,
          fontFamily: "monospace",
          color: C.textLabel,
          textTransform: "uppercase",
          letterSpacing: "0.15em",
          marginBottom: 6,
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontSize: 32,
          fontWeight: "bold",
          fontFamily: "monospace",
          color: valueColor,
          lineHeight: 1,
        }}
      >
        {value}
      </div>
      <div style={{ fontSize: 11, color: C.textMuted, marginTop: 6 }}>
        {sub}
      </div>
    </div>
  );
}

export default function StatCards({ stats }: { stats: StatsResponse | null }) {
  const total = stats?.total ?? 0;
  const flagged = sum(stats?.by_decision, ["step_up", "mfa", "mfa_required"]);
  const blocked = sum(stats?.by_decision, ["block", "blocked", "lock"]);
  const successes = sum(stats?.by_outcome, ["success", "mfa_verified"]);
  const successPct = total > 0 ? ((successes / total) * 100).toFixed(1) : "0.0";

  return (
    <div
      style={{ display: "flex", gap: 12, marginBottom: 24, flexWrap: "wrap" }}
    >
      <StatCard
        label="Logins"
        value={fmt(total)}
        sub={`${stats?.unique_users ?? 0} users · ${stats?.unique_ips ?? 0} IPs`}
        valueColor={C.teal}
        borderColor={C.teal}
      />
      <StatCard
        label="Flagged (MFA/Step-up)"
        value={fmt(flagged)}
        sub="Tier 2 events"
        valueColor={C.orange}
        borderColor={C.orange}
      />
      <StatCard
        label="Blocked"
        value={fmt(blocked)}
        sub="Tier 3 + Tier 4"
        valueColor={C.red}
        borderColor={C.red}
      />
      <StatCard
        label="Success Rate"
        value={`${successPct}%`}
        sub={`${fmt(successes)} successful`}
        valueColor={C.green}
        borderColor={C.green}
      />
    </div>
  );
}
