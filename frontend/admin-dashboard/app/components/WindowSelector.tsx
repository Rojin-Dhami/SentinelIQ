"use client";

import { C } from "../lib/theme";
import type { Window } from "../lib/types";

const OPTIONS: Window[] = ["1h", "24h", "7d", "30d"];
const LABEL: Record<Window, string> = {
  "1h": "Last hour",
  "24h": "Last 24h",
  "7d": "Last 7 days",
  "30d": "Last 30 days",
};

export default function WindowSelector({
  value,
  onChange,
}: {
  value: Window;
  onChange: (w: Window) => void;
}) {
  return (
    <div style={{ display: "flex", gap: 6 }}>
      {OPTIONS.map((w) => {
        const active = w === value;
        return (
          <button
            key={w}
            onClick={() => onChange(w)}
            style={{
              padding: "6px 12px",
              fontSize: 10,
              fontFamily: "monospace",
              letterSpacing: "0.12em",
              textTransform: "uppercase",
              background: active ? "rgba(45,212,191,0.12)" : "transparent",
              color: active ? C.teal : C.textMuted,
              border: `1px solid ${active ? C.teal : C.borderCard}`,
              borderRadius: 6,
              cursor: "pointer",
              transition: "all 0.15s",
            }}
          >
            {LABEL[w]}
          </button>
        );
      })}
    </div>
  );
}
