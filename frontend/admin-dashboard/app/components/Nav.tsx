"use client";

import { useEffect, useState } from "react";
import { C } from "../lib/theme";
import { logout } from "../lib/api";
import { useRouter } from "next/navigation";

interface Props {
  adminEmail: string | null;
  connected: boolean;
}

export default function Nav({ adminEmail, connected }: Props) {
  const router = useRouter();
  const [clock, setClock] = useState<Date | null>(null);

  useEffect(() => {
    setClock(new Date());
    const t = setInterval(() => setClock(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  const npTime = clock
    ? clock.toLocaleTimeString("en-US", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
        timeZone: "Asia/Kathmandu",
      })
    : "--:--:--";

  async function onLogout() {
    try {
      await logout();
    } catch {
      /* ignore */
    }
    router.replace("/login");
  }

  return (
    <nav
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "10px 24px",
        background: C.bgNav,
        borderBottom: `1px solid ${C.borderSub}`,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
        <span
          style={{ fontWeight: "bold", fontSize: 18, letterSpacing: "-0.02em" }}
        >
          <span style={{ color: C.textWhite }}>Sentinel</span>
          <span style={{ color: C.teal }}>IQ</span>
        </span>
        <span
          style={{
            fontSize: 10,
            fontFamily: "monospace",
            color: C.teal,
            border: `1px solid ${C.teal}`,
            borderRadius: 20,
            padding: "3px 12px",
            letterSpacing: "0.04em",
          }}
        >
          Auth Anomaly Detection
        </span>
      </div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 20,
          fontSize: 11,
          fontFamily: "monospace",
        }}
      >
        <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span
            style={{
              width: 7,
              height: 7,
              borderRadius: "50%",
              background: connected ? C.green : C.red,
              display: "inline-block",
              boxShadow: `0 0 6px ${connected ? C.green : C.red}`,
            }}
          />
          <span style={{ color: connected ? C.green : C.red }}>
            {connected ? "LIVE" : "OFFLINE"}
          </span>
        </span>
        <span style={{ color: C.teal }}>{npTime} NPT</span>
        <span style={{ color: C.textMuted }}>
          {adminEmail ? (
            <>
              <span style={{ color: "#8bafc8" }}>{adminEmail}</span>
            </>
          ) : (
            "Security Ops"
          )}
        </span>
        <button
          onClick={onLogout}
          style={{
            background: "transparent",
            color: C.textMuted,
            border: `1px solid ${C.borderCard}`,
            borderRadius: 6,
            padding: "4px 10px",
            fontSize: 10,
            fontFamily: "monospace",
            letterSpacing: "0.12em",
            textTransform: "uppercase",
            cursor: "pointer",
          }}
        >
          Logout
        </button>
      </div>
    </nav>
  );
}
