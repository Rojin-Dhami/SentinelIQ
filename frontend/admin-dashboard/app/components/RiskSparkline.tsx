"use client";

import { C } from "../lib/theme";

interface Props {
  data: number[]; // risk scores 0..1
  height?: number;
  label?: string;
}

function riskColor(v: number): string {
  if (v >= 0.7) return C.red;
  if (v >= 0.45) return C.orange;
  if (v >= 0.25) return "#facc15";
  return C.teal;
}

export default function RiskSparkline({ data, height = 56, label }: Props) {
  if (data.length < 2) {
    return (
      <div
        style={{
          height,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 10,
          fontFamily: "monospace",
          color: C.textDim,
        }}
      >
        No data yet…
      </div>
    );
  }

  const W = 600;
  const H = height;
  const pad = 3;
  const usableW = W - pad * 2;
  const usableH = H - pad * 2;

  const pts = data.map((v, i) => {
    const x = pad + (i / (data.length - 1)) * usableW;
    const y = pad + (1 - v) * usableH;
    return { x, y, v };
  });

  const polylineStr = pts.map((p) => `${p.x},${p.y}`).join(" ");
  const areaStr = [
    `${pts[0].x},${H}`,
    ...pts.map((p) => `${p.x},${p.y}`),
    `${pts[pts.length - 1].x},${H}`,
  ].join(" ");

  const last = data[data.length - 1];
  const avg = data.reduce((s, v) => s + v, 0) / data.length;
  const lineCol = riskColor(last);
  const gradId = "sparkGrad" + Math.round(avg * 100);

  // Threshold y positions
  const thresholds = [
    { v: 0.25, label: "MFA" },
    { v: 0.5, label: "BLOCK" },
    { v: 0.7, label: "HIGH" },
  ];

  return (
    <div style={{ position: "relative" }}>
      {label && (
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "baseline",
            marginBottom: 4,
          }}
        >
          <span
            style={{
              fontSize: 10,
              fontFamily: "monospace",
              color: C.textLabel,
              textTransform: "uppercase",
              letterSpacing: "0.15em",
            }}
          >
            {label}
          </span>
          <span
            style={{
              fontSize: 11,
              fontFamily: "monospace",
              color: lineCol,
              fontWeight: "bold",
            }}
          >
            latest {last.toFixed(3)}
            <span style={{ color: C.textMuted, fontWeight: "normal" }}>
              {" "}
              avg {avg.toFixed(3)}
            </span>
          </span>
        </div>
      )}
      <svg
        viewBox={`0 0 ${W} ${H}`}
        style={{ width: "100%", height: H, display: "block" }}
        preserveAspectRatio="none"
      >
        <defs>
          <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={lineCol} stopOpacity={0.35} />
            <stop offset="100%" stopColor={lineCol} stopOpacity={0.02} />
          </linearGradient>
        </defs>

        {/* Threshold lines */}
        {thresholds.map(({ v }) => {
          const ty = pad + (1 - v) * usableH;
          return (
            <line
              key={v}
              x1={pad}
              y1={ty}
              x2={W - pad}
              y2={ty}
              stroke="#1e3a52"
              strokeWidth={0.6}
              strokeDasharray="4,4"
            />
          );
        })}

        {/* Area fill */}
        <polygon points={areaStr} fill={`url(#${gradId})`} />

        {/* Line */}
        <polyline
          points={polylineStr}
          fill="none"
          stroke={lineCol}
          strokeWidth={1.8}
          strokeLinejoin="round"
          strokeLinecap="round"
        />

        {/* Last-point dot */}
        <circle
          cx={pts[pts.length - 1].x}
          cy={pts[pts.length - 1].y}
          r={3}
          fill={lineCol}
        />
      </svg>
    </div>
  );
}
