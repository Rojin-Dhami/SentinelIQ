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
import { getStats, listEvents, me } from "./lib/api";
import { C } from "./lib/theme";
import type {
  AdminEvent,
  Decision,
  Outcome,
  StatsResponse,
  Window,
} from "./lib/types";

const MAX_EVENTS = 200;
const STATS_REFRESH_MS = 10_000;

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
          />
        </div>

        <AttackSimulator />
      </div>
    </div>
  );
}
