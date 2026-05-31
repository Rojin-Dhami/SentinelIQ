"use client";

import { C, decisionBorder, decisionColor, outcomeColor } from "../lib/theme";
import type { AdminEvent } from "../lib/types";

function fmtTime(iso: string | null): string {
  if (!iso) return "--:--:--";
  try {
    return new Date(iso).toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
  } catch {
    return "--:--:--";
  }
}

function fmtLoc(ev: AdminEvent): string {
  const parts = [ev.city, ev.country].filter(Boolean);
  return parts.length > 0 ? parts.join(", ") : "—";
}

function fmtDevice(ev: AdminEvent): string {
  if (!ev.device_fingerprint) return "—";
  return ev.device_fingerprint.length > 14
    ? ev.device_fingerprint.slice(0, 14) + "…"
    : ev.device_fingerprint;
}

const TH: React.CSSProperties = {
  padding: "10px 12px",
  fontSize: 10,
  fontFamily: "monospace",
  color: C.teal,
  textTransform: "uppercase",
  letterSpacing: "0.12em",
  textAlign: "left",
  fontWeight: "normal",
  borderBottom: `1px solid ${C.borderSub}`,
  background: C.bgCard,
};

interface Props {
  events: AdminEvent[];
  selectedId: number | null;
  onSelect: (ev: AdminEvent) => void;
  loading: boolean;
  recentIds?: Set<number>;
}

export default function LiveFeed({
  events,
  selectedId,
  onSelect,
  loading,
  recentIds,
}: Props) {
  return (
    <div
      style={{
        background: C.bgCard,
        border: `1px solid ${C.borderCard}`,
        borderRadius: 12,
        overflow: "hidden",
      }}
    >
      <div style={{ overflowX: "auto", maxHeight: 480, overflowY: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead style={{ position: "sticky", top: 0, zIndex: 10 }}>
            <tr>
              {[
                "Time",
                "User",
                "IP",
                "Location",
                "Device",
                "Risk",
                "Decision",
                "Outcome",
                "",
              ].map((h, i) => (
                <th key={i} style={TH}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {events.length === 0 && (
              <tr>
                <td
                  colSpan={9}
                  style={{
                    textAlign: "center",
                    padding: "60px 0",
                    fontSize: 11,
                    fontFamily: "monospace",
                    color: C.textDim,
                  }}
                >
                  {loading ? "Loading events…" : "Waiting for events…"}
                </td>
              </tr>
            )}
            {events.map((ev) => {
              const isSelected = selectedId === ev.id;
              const isRecent = recentIds?.has(ev.id) ?? false;
              const borderColor = decisionBorder(ev.decision);
              const actionColor = decisionColor(ev.decision);

              // Pick flash animation by decision severity
              let flashAnim = "none";
              if (isRecent) {
                if (
                  ev.decision === "block" ||
                  ev.decision === "hard_block" ||
                  ev.decision === "locked" ||
                  ev.decision === "lock" ||
                  ev.decision === "rate_limited"
                ) {
                  flashAnim = "rowFlashRed 1.8s ease forwards";
                } else if (
                  ev.decision === "step_up" ||
                  ev.decision === "mfa" ||
                  ev.decision === "mfa_required"
                ) {
                  flashAnim = "rowFlashOrange 1.8s ease forwards";
                } else {
                  flashAnim = "rowFlash 1.8s ease forwards";
                }
              }

              return (
                <tr
                  key={ev.id}
                  onClick={() => onSelect(ev)}
                  style={{
                    borderLeft: `2.5px solid ${borderColor}`,
                    background: isSelected
                      ? "rgba(45,212,191,0.06)"
                      : "transparent",
                    cursor: "pointer",
                    transition: isRecent ? "none" : "background 0.12s",
                    animation: isSelected ? "none" : flashAnim,
                  }}
                >
                  <Td>
                    {fmtTime(ev.created_at)}
                    {isRecent && (
                      <span
                        style={{
                          marginLeft: 5,
                          fontSize: 8,
                          fontFamily: "monospace",
                          color: "#081624",
                          background: C.teal,
                          borderRadius: 2,
                          padding: "1px 4px",
                          letterSpacing: "0.08em",
                          verticalAlign: "middle",
                        }}
                      >
                        NEW
                      </span>
                    )}
                  </Td>
                  <Td white>{ev.user_email ?? `user#${ev.user_id ?? "?"}`}</Td>
                  <Td>{ev.ip ?? "—"}</Td>
                  <Td>{fmtLoc(ev)}</Td>
                  <Td>{fmtDevice(ev)}</Td>
                  <Td color={actionColor} bold>
                    {ev.risk_score != null ? ev.risk_score.toFixed(2) : "—"}
                  </Td>
                  <Td color={actionColor} bold>
                    {(ev.decision ?? "—").toUpperCase()}
                  </Td>
                  <Td color={outcomeColor(ev.outcome)}>{ev.outcome ?? "—"}</Td>
                  <Td>
                    <span style={{ color: C.textMuted, fontSize: 16 }}>›</span>
                  </Td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Td({
  children,
  color,
  white,
  bold,
}: {
  children: React.ReactNode;
  color?: string;
  white?: boolean;
  bold?: boolean;
}) {
  return (
    <td
      style={{
        padding: "7px 12px",
        fontSize: 11,
        fontFamily: "monospace",
        color: color ?? (white ? C.textWhite : C.textMuted),
        fontWeight: bold ? "bold" : "normal",
        whiteSpace: "nowrap",
        maxWidth: 200,
        overflow: "hidden",
        textOverflow: "ellipsis",
      }}
    >
      {children}
    </td>
  );
}
