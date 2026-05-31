"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import AuthGate from "./components/AuthGate";
import Nav from "./components/Nav";
import StatCards from "./components/StatCards";
import WindowSelector from "./components/WindowSelector";
import Filters from "./components/Filters";
import LiveFeed from "./components/LiveFeed";
import EventDetailsPanel from "./components/EventDetailsPanel";
import AttackSimulator from "./components/AttackSimulator";
import RiskSparkline from "./components/RiskSparkline";
import { getStats, listEvents, me } from "./lib/api";
import { C, decisionColor } from "./lib/theme";
import type {
  AdminEvent,
  Decision,
  Outcome,
  StatsResponse,
  Window,
} from "./lib/types";

const MAX_EVENTS = 200;
const MAX_SPARKLINE = 60;
const STATS_REFRESH_MS = 10_000;
const RECENT_FLASH_MS = 3_500;
const TOAST_TTL_MS = 7_000;

const HIGH_RISK_DECISIONS = new Set([
  "block",
  "hard_block",
  "lock",
  "locked",
  "rate_limited",
]);

export default function Page() {
  return (
    <AuthGate>
      <Dashboard />
    </AuthGate>
  );
}

function Dashboard() {
  const [adminEmail, setAdminEmail] = useState<string | null>(null);
  const [window, setWindow] = useState<Window>("24h");
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [events, setEvents] = useState<AdminEvent[]>([]);
  const [eventsLoading, setEventsLoading] = useState(true);
  const [decision, setDecision] = useState<Decision | "">("");
  const [outcome, setOutcome] = useState<Outcome | "">("");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [connected, setConnected] = useState(false);

  // --- New state for live demo features ---
  const [recentIds, setRecentIds] = useState<Set<number>>(new Set());
  const [riskHistory, setRiskHistory] = useState<number[]>([]);
  const [threatToasts, setThreatToasts] = useState<
    Array<{ id: string; event: AdminEvent }>
  >([]);

  const lastSeenIdRef = useRef<number>(0);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    me()
      .then((u) => setAdminEmail(u.email))
      .catch(() => {});
  }, []);

  useEffect(() => {
    let cancelled = false;
    const load = () =>
      getStats(window)
        .then((s) => {
          if (!cancelled) setStats(s);
        })
        .catch(() => {});
    load();
    const t = setInterval(load, STATS_REFRESH_MS);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, [window]);

  useEffect(() => {
    let cancelled = false;
    setEventsLoading(true);
    listEvents({
      limit: 80,
      decision: decision || undefined,
      outcome: outcome || undefined,
    })
      .then((r) => {
        if (cancelled) return;
        setEvents(r.items);
        if (r.items.length > 0) {
          lastSeenIdRef.current = Math.max(
            lastSeenIdRef.current,
            ...r.items.map((e) => e.id),
          );
        }
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setEventsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [decision, outcome]);

  useEffect(() => {
    const es = new EventSource("/api/admin/stream", { withCredentials: true });
    esRef.current = es;

    let consecutiveErrors = 0;

    const onOpen = () => {
      consecutiveErrors = 0;
      setConnected(true);
    };
    es.addEventListener("hello", onOpen);
    es.onopen = onOpen;
    es.onerror = () => {
      setConnected(false);
      consecutiveErrors += 1;
      // EventSource hides HTTP status; after several failed reconnects assume
      // the cookie is bad (likely overwritten by a login on the client app)
      // and verify session. me() will redirect to /login on 401/403.
      if (consecutiveErrors >= 3) {
        consecutiveErrors = 0;
        me().catch(() => {});
      }
    };

    es.addEventListener("login_event", (msg) => {
      try {
        const payload = JSON.parse((msg as MessageEvent).data) as AdminEvent;
        lastSeenIdRef.current = Math.max(lastSeenIdRef.current, payload.id);

        setEvents((prev) => {
          if (prev.some((e) => e.id === payload.id)) return prev;
          return [payload, ...prev].slice(0, MAX_EVENTS);
        });

        // Flash newly arrived row
        const eid = payload.id;
        setRecentIds((s) => new Set([...s, eid]));
        setTimeout(() => {
          setRecentIds((s) => {
            const next = new Set(s);
            next.delete(eid);
            return next;
          });
        }, RECENT_FLASH_MS);

        // Update risk sparkline
        if (payload.risk_score != null) {
          setRiskHistory((h) =>
            [...h, payload.risk_score!].slice(-MAX_SPARKLINE),
          );
        }

        // Threat toast for high-risk decisions
        if (payload.decision && HIGH_RISK_DECISIONS.has(payload.decision)) {
          const toastId = crypto.randomUUID();
          setThreatToasts((t) =>
            [{ id: toastId, event: payload }, ...t].slice(0, 5),
          );
          setTimeout(() => {
            setThreatToasts((t) => t.filter((x) => x.id !== toastId));
          }, TOAST_TTL_MS);
        }
      } catch {
        /* ignore */
      }
    });

    return () => {
      es.close();
      esRef.current = null;
    };
  }, []);

  const visibleEvents = useMemo(() => {
    return events.filter((e) => {
      if (decision && e.decision !== decision) return false;
      if (outcome && e.outcome !== outcome) return false;
      return true;
    });
  }, [events, decision, outcome]);

  const handleSelect = useCallback((ev: AdminEvent) => {
    setSelectedId(ev.id);
  }, []);

  return (
    <div
      style={{ minHeight: "100vh", background: C.bgMain, color: C.textWhite }}
    >
      <Nav adminEmail={adminEmail} connected={connected} />

      {selectedId != null && (
        <EventDetailsPanel
          eventId={selectedId}
          onClose={() => setSelectedId(null)}
        />
      )}

      {/* ── Threat toast overlay ──────────────────────────────────────── */}
      <div
        style={{
          position: "fixed",
          top: 60,
          right: 16,
          zIndex: 60,
          display: "flex",
          flexDirection: "column",
          gap: 8,
          pointerEvents: "none",
          maxWidth: 320,
        }}
      >
        {threatToasts.map(({ id, event: ev }) => {
          const isBlock =
            ev.decision === "block" ||
            ev.decision === "hard_block" ||
            ev.decision === "locked";
          const borderCol = isBlock ? C.red : C.orange;
          const col = decisionColor(ev.decision);
          return (
            <div
              key={id}
              style={{
                background: "#0d1e30",
                border: `1px solid ${borderCol}`,
                borderRadius: 8,
                padding: "10px 14px",
                fontSize: 11,
                fontFamily: "monospace",
                boxShadow: `0 4px 28px rgba(0,0,0,0.7), 0 0 18px ${borderCol}44`,
                pointerEvents: "auto",
                animation: isBlock
                  ? "slideInRight 0.3s ease, pulseGlow 2s ease 0.3s 3"
                  : "slideInRight 0.3s ease, pulseGlowOrange 2s ease 0.3s 3",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  marginBottom: 4,
                }}
              >
                <span
                  style={{
                    width: 7,
                    height: 7,
                    borderRadius: "50%",
                    background: borderCol,
                    display: "inline-block",
                    animation: "blinkDot 0.8s ease infinite",
                  }}
                />
                <span
                  style={{
                    color: col,
                    fontWeight: "bold",
                    letterSpacing: "0.12em",
                    textTransform: "uppercase",
                  }}
                >
                  🚨 {ev.decision?.replace("_", " ") ?? "ALERT"}
                </span>
              </div>
              <div style={{ color: C.textWhite, marginBottom: 2 }}>
                {ev.user_email ?? `user#${ev.user_id ?? "?"}`}
              </div>
              <div style={{ color: C.textMuted }}>
                {ev.ip}
                {ev.city || ev.country
                  ? ` · ${[ev.city, ev.country].filter(Boolean).join(", ")}`
                  : ""}
              </div>
              <div
                style={{
                  color: col,
                  marginTop: 4,
                  fontWeight: "bold",
                }}
              >
                Risk: {ev.risk_score != null ? ev.risk_score.toFixed(3) : "—"}
              </div>
            </div>
          );
        })}
      </div>

      <div style={{ padding: 24 }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: 14,
            flexWrap: "wrap",
            gap: 12,
          }}
        >
          <div
            style={{
              fontSize: 10,
              fontFamily: "monospace",
              color: C.textLabel,
              textTransform: "uppercase",
              letterSpacing: "0.18em",
            }}
          >
            Aggregates · {window}
          </div>
          <WindowSelector value={window} onChange={setWindow} />
        </div>

        <StatCards stats={stats} />

        {/* ── Risk Sparkline ──────────────────────────────────────────── */}
        {riskHistory.length >= 2 && (
          <div
            style={{
              background: C.bgCard,
              border: `1px solid ${C.borderCard}`,
              borderRadius: 12,
              padding: "14px 20px",
              marginBottom: 24,
            }}
          >
            <RiskSparkline
              data={riskHistory}
              height={60}
              label="Live Risk Score Trend"
            />
          </div>
        )}

        <div style={{ marginBottom: 24 }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              marginBottom: 10,
              flexWrap: "wrap",
            }}
          >
            <span
              style={{
                fontSize: 10,
                fontFamily: "monospace",
                color: C.textLabel,
                textTransform: "uppercase",
                letterSpacing: "0.18em",
              }}
            >
              Live Risk Feed
            </span>
            <div
              style={{
                flex: 1,
                height: 1,
                background: C.borderSub,
                minWidth: 20,
              }}
            />
            <Filters
              decision={decision}
              outcome={outcome}
              onDecision={setDecision}
              onOutcome={setOutcome}
            />
          </div>
          <LiveFeed
            events={visibleEvents}
            selectedId={selectedId}
            onSelect={handleSelect}
            loading={eventsLoading}
            recentIds={recentIds}
          />
        </div>

        <AttackSimulator />
      </div>
    </div>
  );
}
