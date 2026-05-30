"use client";

import { useEffect, useState } from "react";
import { C, decisionColor } from "../lib/theme";
import {
  ApiError,
  getEvent,
  revokeAllUserSessions,
  unlockUser,
} from "../lib/api";
import type { AdminEvent } from "../lib/types";

interface Props {
  eventId: number;
  onClose: () => void;
}

interface FeatureBar {
  name: string;
  value: number;
  raw: unknown;
}

// Extract numeric values from the breakdown for the bar chart.
function extractFeatures(
  breakdown: Record<string, unknown> | null,
): FeatureBar[] {
  if (!breakdown) return [];
  const flat: FeatureBar[] = [];
  for (const [k, v] of Object.entries(breakdown)) {
    if (typeof v === "number") {
      flat.push({ name: k, value: v, raw: v });
    } else if (v && typeof v === "object") {
      for (const [k2, v2] of Object.entries(v as Record<string, unknown>)) {
        if (typeof v2 === "number") {
          flat.push({ name: `${k}.${k2}`, value: v2, raw: v2 });
        }
      }
    }
  }
  flat.sort((a, b) => Math.abs(b.value) - Math.abs(a.value));
  return flat.slice(0, 12);
}

function featColor(v: number): string {
  if (v >= 0.7) return C.red;
  if (v >= 0.4) return C.orange;
  if (v >= 0.15) return C.yellow;
  return C.teal;
}

export default function EventDetailsPanel({ eventId, onClose }: Props) {
  const [mounted, setMounted] = useState(false);
  const [ev, setEv] = useState<AdminEvent | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionMsg, setActionMsg] = useState<string | null>(null);
  const [userUuid, setUserUuid] = useState("");

  useEffect(() => {
    setTimeout(() => setMounted(true), 20);
  }, []);

  useEffect(() => {
    let cancelled = false;
    setEv(null);
    setErr(null);
    setActionMsg(null);
    getEvent(eventId)
      .then((e) => {
        if (!cancelled) setEv(e);
      })
      .catch((e) => {
        if (cancelled) return;
        setErr(e instanceof ApiError ? e.message : "Failed to load event");
      });
    return () => {
      cancelled = true;
    };
  }, [eventId]);

  async function withBusy(label: string, fn: () => Promise<unknown>) {
    setBusy(true);
    setActionMsg(null);
    try {
      const res = await fn();
      setActionMsg(`${label}: OK · ${JSON.stringify(res)}`);
    } catch (e) {
      setActionMsg(
        e instanceof ApiError ? `${label}: ${e.message}` : `${label}: failed`,
      );
    } finally {
      setBusy(false);
    }
  }

  const features = ev ? extractFeatures(ev.breakdown) : [];
  const maxFeat = features.length
    ? Math.max(...features.map((f) => Math.abs(f.value)), 0.0001)
    : 1;
  const decisionCol = decisionColor(ev?.decision ?? null);

  return (
    <>
      <div
        onClick={onClose}
        style={{
          position: "fixed",
          inset: 0,
          background: "rgba(0,0,0,0.55)",
          zIndex: 40,
        }}
      />
      <div
        style={{
          position: "fixed",
          top: 0,
          right: 0,
          bottom: 0,
          width: 360,
          zIndex: 50,
          background: C.bgCard,
          borderLeft: `1px solid ${C.borderCard}`,
          display: "flex",
          flexDirection: "column",
          transform: mounted ? "translateX(0)" : "translateX(100%)",
          transition: "transform 0.28s ease",
          boxShadow: "-8px 0 40px rgba(0,0,0,0.6)",
        }}
      >
        {/* Header */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            padding: "12px 16px",
            borderBottom: `1px solid ${C.borderCard}`,
          }}
        >
          <span
            style={{
              fontSize: 10,
              fontFamily: "monospace",
              color: C.teal,
              letterSpacing: "0.15em",
              textTransform: "uppercase",
            }}
          >
            Event #{eventId} · Risk Breakdown
          </span>
          <button
            onClick={onClose}
            style={{
              background: "none",
              border: "none",
              color: C.textMuted,
              cursor: "pointer",
              fontSize: 22,
              lineHeight: 1,
              padding: "0 4px",
            }}
          >
            ×
          </button>
        </div>

        <div style={{ flex: 1, overflowY: "auto", padding: 16 }}>
          {err && (
            <div
              style={{ color: C.red, fontFamily: "monospace", fontSize: 11 }}
            >
              {err}
            </div>
          )}

          {ev && (
            <>
              {/* Info block */}
              <div
                style={{
                  background: "#0a1a2e",
                  borderRadius: 8,
                  padding: 12,
                  marginBottom: 14,
                  fontSize: 11,
                  fontFamily: "monospace",
                  lineHeight: 1.8,
                  border: `1px solid ${C.borderSub}`,
                }}
              >
                {[
                  ["USER", ev.user_email ?? `id ${ev.user_id ?? "?"}`],
                  ["IP", ev.ip ?? "—"],
                  [
                    "LOC",
                    [ev.city, ev.country].filter(Boolean).join(", ") || "—",
                  ],
                  ["DEVICE", ev.device_fingerprint ?? "—"],
                  ["TIME", ev.created_at ?? "—"],
                ].map(([k, v]) => (
                  <div key={k}>
                    <span style={{ color: C.textMuted }}>{k} </span>
                    <span style={{ color: C.textWhite }}>{v}</span>
                  </div>
                ))}
                <div>
                  <span style={{ color: C.textMuted }}>RISK </span>
                  <span style={{ color: decisionCol, fontWeight: "bold" }}>
                    {ev.risk_score != null ? ev.risk_score.toFixed(3) : "—"}
                  </span>
                  {"  "}
                  <span style={{ color: C.textMuted }}>DECISION </span>
                  <span style={{ color: decisionCol }}>
                    {(ev.decision ?? "—").toUpperCase()}
                  </span>
                </div>
                <div>
                  <span style={{ color: C.textMuted }}>OUTCOME </span>
                  <span style={{ color: C.textWhite }}>
                    {ev.outcome ?? "—"}
                  </span>
                </div>
              </div>

              {/* Feature bars */}
              <div
                style={{
                  fontSize: 10,
                  fontFamily: "monospace",
                  color: C.textMuted,
                  textTransform: "uppercase",
                  letterSpacing: "0.12em",
                  marginBottom: 8,
                }}
              >
                Risk Breakdown
              </div>
              {features.length === 0 && (
                <div
                  style={{
                    color: C.textDim,
                    fontSize: 11,
                    fontFamily: "monospace",
                  }}
                >
                  No breakdown data.
                </div>
              )}
              {features.map((f) => {
                const pct = ((Math.abs(f.value) / maxFeat) * 100).toFixed(1);
                const col = featColor(Math.abs(f.value));
                return (
                  <div key={f.name} style={{ marginBottom: 8 }}>
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        fontSize: 10,
                        fontFamily: "monospace",
                        marginBottom: 3,
                      }}
                    >
                      <span style={{ color: C.textWhite }}>{f.name}</span>
                      <span style={{ color: col }}>{f.value.toFixed(3)}</span>
                    </div>
                    <div
                      style={{
                        height: 5,
                        background: "#0a1a2e",
                        borderRadius: 99,
                        overflow: "hidden",
                      }}
                    >
                      <div
                        style={{
                          height: "100%",
                          width: `${pct}%`,
                          background: col,
                          borderRadius: 99,
                          transition: "width 0.5s ease",
                        }}
                      />
                    </div>
                  </div>
                );
              })}

              {/* Raw JSON (collapsed style) */}
              <details style={{ marginTop: 14 }}>
                <summary
                  style={{
                    color: C.textMuted,
                    fontFamily: "monospace",
                    fontSize: 10,
                    letterSpacing: "0.12em",
                    textTransform: "uppercase",
                    cursor: "pointer",
                  }}
                >
                  Raw breakdown
                </summary>
                <pre
                  style={{
                    background: "#0a1a2e",
                    border: `1px solid ${C.borderSub}`,
                    borderRadius: 6,
                    padding: 10,
                    fontSize: 10,
                    color: C.textWhite,
                    overflowX: "auto",
                    marginTop: 6,
                  }}
                >
                  {JSON.stringify(ev.breakdown, null, 2)}
                </pre>
              </details>
            </>
          )}
        </div>

        {/* Admin actions */}
        <div
          style={{
            padding: "12px 16px",
            borderTop: `1px solid ${C.borderCard}`,
            display: "flex",
            flexDirection: "column",
            gap: 8,
          }}
        >
          {actionMsg && (
            <div
              style={{
                fontSize: 10,
                fontFamily: "monospace",
                color: C.teal,
                wordBreak: "break-all",
              }}
            >
              {actionMsg}
            </div>
          )}
          <input
            type="text"
            placeholder="user UUID (required for unlock / revoke-all)"
            value={userUuid}
            onChange={(e) => setUserUuid(e.target.value.trim())}
            style={{
              background: "#0a1a2e",
              border: `1px solid ${C.borderSub}`,
              borderRadius: 6,
              padding: "7px 10px",
              fontSize: 11,
              fontFamily: "monospace",
              color: C.textWhite,
              outline: "none",
            }}
          />
          <ActionBtn
            label="Unlock User"
            color={C.green}
            disabled={busy || !userUuid}
            onClick={() => withBusy("unlock", () => unlockUser(userUuid))}
          />
          <ActionBtn
            label="Revoke ALL User Sessions"
            color={C.red}
            disabled={busy || !userUuid}
            onClick={() =>
              withBusy("revoke_all", () => revokeAllUserSessions(userUuid))
            }
          />
        </div>
      </div>
    </>
  );
}

function ActionBtn({
  label,
  color,
  disabled,
  onClick,
}: {
  label: string;
  color: string;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        padding: "8px 0",
        fontSize: 11,
        fontFamily: "monospace",
        fontWeight: "bold",
        letterSpacing: "0.12em",
        background: disabled ? "rgba(255,255,255,0.02)" : `${color}22`,
        border: `1px solid ${disabled ? C.borderSub : color}`,
        color: disabled ? C.textDim : color,
        borderRadius: 6,
        cursor: disabled ? "not-allowed" : "pointer",
        transition: "background 0.15s",
      }}
    >
      {label}
    </button>
  );
}
