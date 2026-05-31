"use client";

import { useEffect, useState } from "react";
import { ApiError, getScenarios, simulateAttack } from "../lib/api";
import { C } from "../lib/theme";
import type { ScenarioMeta } from "../lib/types";

type ScenarioStatus = "idle" | "running" | "done" | "error";

interface ScenarioState {
  status: ScenarioStatus;
  lastMsg: string;
  lastRun: Date | null;
}

const LS_EMAIL = "sentineliq_sim_email";
const LS_PASS = "sentineliq_sim_pass";

export default function AttackSimulator() {
  const [email, setEmail] = useState(() =>
    typeof window !== "undefined" ? (localStorage.getItem(LS_EMAIL) ?? "") : "",
  );
  const [password, setPassword] = useState(() =>
    typeof window !== "undefined" ? (localStorage.getItem(LS_PASS) ?? "") : "",
  );
  const [scenarios, setScenarios] = useState<ScenarioMeta[]>([]);
  const [states, setStates] = useState<Record<string, ScenarioState>>({});
  const [expanded, setExpanded] = useState<string | null>(null);
  const [globalErr, setGlobalErr] = useState<string | null>(null);

  // Fetch scenario metadata from backend
  useEffect(() => {
    getScenarios()
      .then((r) => setScenarios(r.scenarios))
      .catch(() => {
        // Fallback static list if backend is unavailable
        setScenarios([
          {
            key: "brute_force",
            label: "Brute Force",
            icon: "🔨",
            description: "15 wrong-password attempts from one IP.",
            expected: ["velocity ↑"],
            tier: "Tier 3",
          },
          {
            key: "distributed_brute",
            label: "Distributed Brute",
            icon: "🌐",
            description: "Rotating IPs, same target account.",
            expected: ["user_velocity ↑"],
            tier: "Tier 3",
          },
          {
            key: "impossible_travel",
            label: "Impossible Travel",
            icon: "✈️",
            description: "US → AU in 5 seconds.",
            expected: ["geo_time_risk ↑"],
            tier: "Tier 4",
          },
          {
            key: "new_device",
            label: "New Device",
            icon: "💻",
            description: "Correct creds, unknown fingerprint.",
            expected: ["device ↑"],
            tier: "Tier 2",
          },
          {
            key: "bot_behavior",
            label: "Bot Behavior",
            icon: "🤖",
            description: "Instant fill, zero variance, headless.",
            expected: ["behavioral ↑"],
            tier: "Tier 2–3",
          },
          {
            key: "datacenter_ip",
            label: "Datacenter IP",
            icon: "🏢",
            description: "AWS / Cloudflare / Hetzner ASNs.",
            expected: ["geo ASN ↑"],
            tier: "Tier 2",
          },
          {
            key: "combined",
            label: "Combined Attack",
            icon: "⚡",
            description: "All signals stacked at once.",
            expected: ["all signals ↑"],
            tier: "Tier 4",
          },
          {
            key: "password_spray",
            label: "Password Spray",
            icon: "💦",
            description: "One IP vs 8 accounts, common passwords.",
            expected: ["ip_velocity ↑"],
            tier: "Tier 3",
          },
          {
            key: "account_takeover",
            label: "Account Takeover",
            icon: "🎯",
            description: "Correct creds + new device + foreign IP + bot.",
            expected: ["device + geo + behavioral"],
            tier: "Tier 4",
          },
        ]);
      });
  }, []);

  function saveCredentials() {
    if (typeof window === "undefined") return;
    localStorage.setItem(LS_EMAIL, email);
    localStorage.setItem(LS_PASS, password);
    setGlobalErr(null);
  }

  async function fire(key: string) {
    if (!email || !password) {
      setGlobalErr("Enter test user credentials first.");
      return;
    }
    setGlobalErr(null);
    setStates((s) => ({
      ...s,
      [key]: { status: "running", lastMsg: "Running…", lastRun: new Date() },
    }));
    try {
      await simulateAttack(key, email, password);
      setStates((s) => ({
        ...s,
        [key]: {
          status: "done",
          lastMsg: "Started — watch the feed ↑",
          lastRun: new Date(),
        },
      }));
    } catch (e) {
      setStates((s) => ({
        ...s,
        [key]: {
          status: "error",
          lastMsg: e instanceof ApiError ? e.message : "Failed to start",
          lastRun: new Date(),
        },
      }));
    }
  }

  async function runAll() {
    if (!email || !password) {
      setGlobalErr("Enter test user credentials first.");
      return;
    }
    setGlobalErr(null);
    for (const s of scenarios) {
      await fire(s.key);
      await new Promise((r) => setTimeout(r, 400));
    }
  }

  const anyRunning = Object.values(states).some((s) => s.status === "running");

  return (
    <div
      style={{
        background: C.bgCard,
        border: `1px solid ${C.borderCard}`,
        borderRadius: 12,
        padding: "18px 20px",
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          marginBottom: 14,
          flexWrap: "wrap",
        }}
      >
        <span style={{ color: C.orange, fontSize: 14 }}>⚡</span>
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
        {anyRunning && (
          <span
            style={{
              fontSize: 10,
              fontFamily: "monospace",
              color: C.red,
              animation: "blinkDot 1s ease infinite",
              letterSpacing: "0.1em",
            }}
          >
            ● ATTACK IN PROGRESS
          </span>
        )}
      </div>

      {/* Credential row */}
      <div
        style={{
          display: "flex",
          gap: 8,
          marginBottom: 12,
          alignItems: "center",
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
        <button
          onClick={saveCredentials}
          title="Save credentials to browser storage"
          style={{
            padding: "7px 14px",
            background: "rgba(45,212,191,0.08)",
            border: `1px solid ${C.teal}`,
            borderRadius: 6,
            fontSize: 10,
            fontFamily: "monospace",
            color: C.teal,
            cursor: "pointer",
            letterSpacing: "0.08em",
            whiteSpace: "nowrap",
          }}
        >
          SAVE
        </button>
        <button
          onClick={runAll}
          disabled={anyRunning}
          title="Fire all scenarios sequentially"
          style={{
            padding: "7px 14px",
            background: anyRunning
              ? "rgba(249,115,22,0.06)"
              : "rgba(249,115,22,0.12)",
            border: `1px solid ${C.orange}`,
            borderRadius: 6,
            fontSize: 10,
            fontFamily: "monospace",
            color: C.orange,
            cursor: anyRunning ? "not-allowed" : "pointer",
            letterSpacing: "0.08em",
            opacity: anyRunning ? 0.6 : 1,
            whiteSpace: "nowrap",
          }}
        >
          RUN ALL
        </button>
      </div>

      {globalErr && (
        <div
          style={{
            marginBottom: 10,
            fontSize: 11,
            fontFamily: "monospace",
            color: C.red,
          }}
        >
          {globalErr}
        </div>
      )}

      {/* Scenario grid */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))",
          gap: 8,
        }}
      >
        {scenarios.map((s) => {
          const st = states[s.key];
          const isRunning = st?.status === "running";
          const isDone = st?.status === "done";
          const isErr = st?.status === "error";
          const isExpanded = expanded === s.key;

          let borderCol: string = C.borderCard;
          if (isRunning) borderCol = C.orange;
          else if (isDone) borderCol = C.teal;
          else if (isErr) borderCol = C.red;

          return (
            <div
              key={s.key}
              style={{
                background: isRunning
                  ? "rgba(249,115,22,0.06)"
                  : isExpanded
                    ? "rgba(45,212,191,0.04)"
                    : "#0a1a2e",
                border: `1px solid ${borderCol}`,
                borderRadius: 8,
                padding: "10px 12px",
                transition: "all 0.18s",
                animation: isRunning
                  ? "pulseGlowOrange 1.5s ease infinite"
                  : "none",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  marginBottom: isExpanded ? 8 : 0,
                }}
              >
                <span style={{ fontSize: 16 }}>{s.icon}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div
                    style={{
                      fontSize: 11,
                      fontFamily: "monospace",
                      color: C.textWhite,
                      fontWeight: "bold",
                    }}
                  >
                    {s.label}
                  </div>
                  <div
                    style={{
                      fontSize: 9,
                      fontFamily: "monospace",
                      color: C.textMuted,
                      marginTop: 1,
                    }}
                  >
                    {s.tier}
                  </div>
                </div>
                {/* Info toggle */}
                <button
                  onClick={() => setExpanded(isExpanded ? null : s.key)}
                  style={{
                    background: "none",
                    border: "none",
                    color: isExpanded ? C.teal : C.textDim,
                    cursor: "pointer",
                    fontSize: 13,
                    padding: "0 2px",
                    lineHeight: 1,
                  }}
                >
                  {isExpanded ? "▲" : "▼"}
                </button>
                {/* Fire button */}
                <button
                  onClick={() => fire(s.key)}
                  disabled={isRunning}
                  style={{
                    padding: "5px 12px",
                    background: isRunning
                      ? "rgba(249,115,22,0.15)"
                      : "rgba(239,68,68,0.10)",
                    border: `1px solid ${isRunning ? C.orange : C.red}`,
                    borderRadius: 5,
                    fontSize: 9,
                    fontFamily: "monospace",
                    fontWeight: "bold",
                    letterSpacing: "0.1em",
                    color: isRunning ? C.orange : C.red,
                    cursor: isRunning ? "not-allowed" : "pointer",
                    whiteSpace: "nowrap",
                  }}
                >
                  {isRunning ? "…" : "FIRE"}
                </button>
              </div>

              {/* Expanded description */}
              {isExpanded && (
                <div>
                  <div
                    style={{
                      fontSize: 10,
                      fontFamily: "monospace",
                      color: "#8bafc8",
                      lineHeight: 1.65,
                      marginBottom: 6,
                    }}
                  >
                    {s.description}
                  </div>
                  {s.expected.length > 0 && (
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                      {s.expected.map((e) => (
                        <span
                          key={e}
                          style={{
                            fontSize: 9,
                            fontFamily: "monospace",
                            color: C.teal,
                            border: `1px solid ${C.teal}`,
                            borderRadius: 3,
                            padding: "1px 5px",
                            opacity: 0.8,
                          }}
                        >
                          {e}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Status line */}
              {st && (
                <div
                  style={{
                    marginTop: 6,
                    fontSize: 9,
                    fontFamily: "monospace",
                    color: isRunning ? C.orange : isDone ? C.teal : C.red,
                  }}
                >
                  {st.lastMsg}
                </div>
              )}
            </div>
          );
        })}
      </div>

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
  minWidth: 160,
  background: "#0a1a2e",
  border: `1px solid #162d44`,
  borderRadius: 6,
  padding: "7px 11px",
  fontSize: 11,
  fontFamily: "monospace",
  color: "#e2eaf2",
  outline: "none",
};
