"use client";

import { useState } from "react";
import { ApiError, simulateAttack } from "../lib/api";
import { C } from "../lib/theme";

const SCENARIOS: { key: string; label: string; icon: string }[] = [
  { key: "brute_force", label: "Brute Force", icon: "🤖" },
  { key: "distributed_brute", label: "Distributed Brute", icon: "🌐" },
  { key: "impossible_travel", label: "Impossible Travel", icon: "🌍" },
  { key: "new_device", label: "New Device", icon: "💻" },
  { key: "bot_behavior", label: "Bot Behavior", icon: "🧬" },
  { key: "datacenter_ip", label: "Datacenter IP", icon: "🏢" },
  { key: "combined", label: "Combined Attack", icon: "⚡" },
];

export default function AttackSimulator() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(
    null,
  );

  async function fire(scenario: string) {
    if (!email || !password) {
      setMsg({ kind: "err", text: "Test user email + password required." });
      return;
    }
    setBusy(scenario);
    setMsg(null);
    try {
      await simulateAttack(scenario, email, password);
      setMsg({ kind: "ok", text: `Started: ${scenario} — watch the feed.` });
    } catch (e) {
      setMsg({
        kind: "err",
        text: e instanceof ApiError ? e.message : "Failed to start",
      });
    } finally {
      setBusy(null);
    }
  }

  return (
    <div
      style={{
        background: C.bgCard,
        border: `1px solid ${C.borderCard}`,
        borderRadius: 12,
        padding: "18px 20px",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          marginBottom: 14,
          flexWrap: "wrap",
        }}
      >
        <span style={{ color: C.orange, fontSize: 13 }}>⚡</span>
        <span
          style={{
            fontSize: 10,
            fontFamily: "monospace",
            color: C.orange,
            textTransform: "uppercase",
            letterSpacing: "0.15em",
            flex: 1,
          }}
        >
          Attack Simulation — Demo Tool
        </span>
      </div>

      <div
        style={{
          display: "flex",
          gap: 8,
          marginBottom: 12,
          flexWrap: "wrap",
        }}
      >
        <input
          type="email"
          placeholder="test user email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          style={inputStyle}
        />
        <input
          type="password"
          placeholder="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          style={inputStyle}
        />
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
        {SCENARIOS.map((s) => {
          const isBusy = busy === s.key;
          return (
            <button
              key={s.key}
              onClick={() => fire(s.key)}
              disabled={busy !== null}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                padding: "10px 16px",
                background: isBusy
                  ? "rgba(45,212,191,0.12)"
                  : "rgba(10,26,46,0.8)",
                border: `1px solid ${isBusy ? C.teal : C.borderCard}`,
                borderRadius: 8,
                fontSize: 12,
                fontFamily: "monospace",
                color: C.textWhite,
                cursor: busy ? "not-allowed" : "pointer",
                opacity: busy && !isBusy ? 0.5 : 1,
                transition: "all 0.15s",
              }}
            >
              <span style={{ fontSize: 16 }}>{s.icon}</span>
              {isBusy ? "running…" : s.label}
            </button>
          );
        })}
      </div>

      {msg && (
        <div
          style={{
            marginTop: 12,
            fontSize: 11,
            fontFamily: "monospace",
            color: msg.kind === "ok" ? C.green : C.red,
          }}
        >
          {msg.text}
        </div>
      )}

      {/* Legend */}
      <div
        style={{ display: "flex", gap: 18, marginTop: 14, flexWrap: "wrap" }}
      >
        {[
          { color: "#166534", label: "Allow" },
          { color: "#ca8a04", label: "Step-up / MFA" },
          { color: C.orange, label: "Lock" },
          { color: C.red, label: "Block" },
        ].map((l) => (
          <span
            key={l.label}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 5,
              fontSize: 10,
              fontFamily: "monospace",
              color: C.textMuted,
            }}
          >
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: 2,
                background: l.color,
                display: "inline-block",
              }}
            />
            {l.label}
          </span>
        ))}
      </div>
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  flex: 1,
  minWidth: 180,
  background: "#0a1a2e",
  border: `1px solid #162d44`,
  borderRadius: 6,
  padding: "7px 11px",
  fontSize: 11,
  fontFamily: "monospace",
  color: C.textWhite,
  outline: "none",
};
