"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import styles from "./page.module.css";
import {
  collectDeviceSpec,
  collectNetworkContext,
  collectSessionMetadata,
} from "../login/collectors";
import { BehavioralSignals, useBehavior } from "../login/useBehavior";

export default function SignupPage() {
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showBehavior, setShowBehavior] = useState(false);
  const [behaviorMetrics, setBehaviorMetrics] = useState<BehaviorMetrics | null>(null);
  const [status, setStatus] = useState<
    "idle" | "loading" | "success" | "error"
  >("idle");
  const [errorMsg, setErrorMsg] = useState("");

  const { snapshot, onUsernamePaste, onPasswordPaste } = useBehavior();

  useEffect(() => {
    if (!showBehavior) {
      return;
    }

    const timer = window.setInterval(() => {
      setBehaviorMetrics(snapshot());
    }, 500);

    return () => window.clearInterval(timer);
  }, [showBehavior, snapshot]);

  const formatMetric = (value: number | null, digits = 1) => {
    if (value === null || Number.isNaN(value)) {
      return "--";
    }
    return value.toFixed(digits);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg("");

    if (password !== confirmPassword) {
      setStatus("error");
      setErrorMsg("Passwords do not match.");
      return;
    }

    if (password.length < 8) {
      setStatus("error");
      setErrorMsg("Password must be at least 8 characters.");
      return;
    }

    setStatus("loading");

    try {
      const [device_spec, network_context] = await Promise.all([
        Promise.resolve(collectDeviceSpec()),
        collectNetworkContext(),
      ]);
      const session_metadata = collectSessionMetadata();
      const behavioral_signals = snapshot();

      const signupRequest = {
        credentials: { full_name: fullName, email, password },
        device_spec,
        network_context,
        behavioral_signals,
        session_metadata,
      };

      const res = await fetch("http://localhost:8000/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(signupRequest),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data?.detail ?? `HTTP ${res.status}`);
      }

      setStatus("success");
    } catch (err: unknown) {
      setStatus("error");
      setErrorMsg(
        err instanceof Error ? err.message : "Signup failed. Please try again.",
      );
    }
  };

  return (
    <div className={styles.page}>
      {/* ── Navbar ──────────────────────────────────────────────────── */}
      <header className={styles.navbar}>
        <a href="/" className={styles.logoBlock}>
          <span className={styles.logoMark}>
            <Image
              src="/image.png"
              alt="SentinelIQ Pay"
              width={48}
              height={48}
              priority
            />
          </span>
          <span className={styles.brandCopy}>
            <span className={styles.brandName}>SentinelIQ Pay</span>
            <span className={styles.brandTag}>Trusted digital wallet</span>
          </span>
        </a>
        <nav className={styles.navLinks}>
          <a href="#">Scan & Pay</a>
          <a href="#">Send Money</a>
          <a href="#">Offers</a>
          <a href="#">Support</a>
          <a href="/login" className={styles.ctaBtn}>
            Login
          </a>
        </nav>
      </header>

      {/* ── Signup card ─────────────────────────────────────────────── */}
      <main className={styles.main}>
        <div className={styles.content}>
          <div className={styles.card}>
            <div className={styles.cardHeader}>
              <div className={styles.iconWrap}>
                {/* User-plus icon */}
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  width="28"
                  height="28"
                >
                  <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
                  <circle cx="9" cy="7" r="4" />
                  <line x1="19" y1="8" x2="19" y2="14" />
                  <line x1="22" y1="11" x2="16" y2="11" />
                </svg>
              </div>
              <h1 className={styles.title}>Create account</h1>
              <p className={styles.subtitle}>
                Join SentinelIQ Pay — it&apos;s free
              </p>
            </div>

            <form className={styles.form} onSubmit={handleSubmit} noValidate>
              {/* Full name */}
              <div className={styles.field}>
                <label htmlFor="fullName" className={styles.label}>
                  Full name
                </label>
                <input
                  id="fullName"
                  type="text"
                  autoComplete="name"
                  required
                  placeholder="Jane Smith"
                  className={styles.input}
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                />
              </div>

              {/* Email */}
              <div className={styles.field}>
                <label htmlFor="email" className={styles.label}>
                  Email address
                </label>
                <input
                  id="email"
                  type="email"
                  autoComplete="email"
                  required
                  placeholder="you@example.com"
                  className={styles.input}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  onPaste={onUsernamePaste}
                />
              </div>

              {/* Password */}
              <div className={styles.field}>
                <label htmlFor="password" className={styles.label}>
                  Password
                </label>
                <input
                  id="password"
                  type="password"
                  autoComplete="new-password"
                  required
                  placeholder="Min. 8 characters"
                  className={styles.input}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onPaste={onPasswordPaste}
                />
              </div>

              {/* Confirm password */}
              <div className={styles.field}>
                <label htmlFor="confirmPassword" className={styles.label}>
                  Confirm password
                </label>
                <input
                  id="confirmPassword"
                  type="password"
                  autoComplete="new-password"
                  required
                  placeholder="Repeat your password"
                  className={styles.input}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                />
              </div>

              {/* Password strength bar */}
              {password.length > 0 && <PasswordStrength password={password} />}

              {/* Error banner */}
              {status === "error" && errorMsg && (
                <div className={styles.errorBanner} role="alert">
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    width="16"
                    height="16"
                  >
                    <circle cx="12" cy="12" r="10" />
                    <line x1="12" y1="8" x2="12" y2="12" />
                    <line x1="12" y1="16" x2="12.01" y2="16" />
                  </svg>
                  {errorMsg}
                </div>
              )}

              {/* Success banner */}
              {status === "success" && (
                <div className={styles.successBanner} role="status">
                  ✓ Account created — welcome aboard!
                </div>
              )}

              <button
                type="submit"
                className={styles.submitBtn}
                disabled={status === "loading" || status === "success"}
              >
                {status === "loading" ? (
                  <span
                    className={styles.spinner}
                    aria-label="Creating account…"
                  />
                ) : (
                  "Create account"
                )}
              </button>
            </form>

            <p className={styles.signupPrompt}>
              Already have an account?{" "}
              <a href="/login" className={styles.signupLink}>
                Sign in
              </a>
            </p>
          </div>

          <div className={styles.behaviorToggleWrap}>
            <button
              type="button"
              className={styles.behaviorToggle}
              onClick={() => setShowBehavior((prev) => !prev)}
            >
              {showBehavior ? "Hide" : "View"} behavior analysis
            </button>
          </div>

          {showBehavior && (
            <aside className={styles.behaviorPanel}>
            <div className={styles.panelHeader}>
              <p className={styles.panelEyebrow}>Behavior analytics</p>
              <h2 className={styles.panelTitle}>Live typing signals</h2>
              <p className={styles.panelSubcopy}>
                Updates in real time as you type.
              </p>
            </div>

            <div className={styles.metricGrid}>
              <div className={styles.metricCard}>
                <span className={styles.metricLabel}>Avg dwell time</span>
                <span className={styles.metricValue}>
                  {formatMetric(behaviorMetrics?.avg_dwell_time_ms ?? null)}
                  <span className={styles.metricUnit}>ms</span>
                </span>
              </div>
              <div className={styles.metricCard}>
                <span className={styles.metricLabel}>Avg flight time</span>
                <span className={styles.metricValue}>
                  {formatMetric(behaviorMetrics?.avg_flight_time_ms ?? null)}
                  <span className={styles.metricUnit}>ms</span>
                </span>
              </div>
              <div className={styles.metricCard}>
                <span className={styles.metricLabel}>Keystroke variance</span>
                <span className={styles.metricValue}>
                  {formatMetric(behaviorMetrics?.keystroke_variance ?? null, 2)}
                </span>
              </div>
              <div className={styles.metricCard}>
                <span className={styles.metricLabel}>Typos detected</span>
                <span className={styles.metricValue}>
                  {formatMetric(behaviorMetrics?.typo_count ?? null, 0)}
                </span>
              </div>
            </div>
            </aside>
          )}
        </div>
      </main>
    </div>
  );
}

type BehaviorMetrics = {
  avg_dwell_time_ms: BehavioralSignals["avg_dwell_time_ms"];
  avg_flight_time_ms: BehavioralSignals["avg_flight_time_ms"];
  keystroke_variance: BehavioralSignals["keystroke_variance"];
  typo_count: BehavioralSignals["typo_count"];
};

/* ── Password strength indicator ─────────────────────────────────────────── */

function getStrength(pw: string): {
  score: number;
  label: string;
  color: string;
} {
  let score = 0;
  if (pw.length >= 8) score++;
  if (pw.length >= 12) score++;
  if (/[A-Z]/.test(pw)) score++;
  if (/[0-9]/.test(pw)) score++;
  if (/[^A-Za-z0-9]/.test(pw)) score++;

  if (score <= 1) return { score, label: "Weak", color: "#ef4444" };
  if (score <= 2) return { score, label: "Fair", color: "#f59e0b" };
  if (score <= 3) return { score, label: "Good", color: "#3b82f6" };
  return { score, label: "Strong", color: "#2ae675" };
}

function PasswordStrength({ password }: { password: string }) {
  const { score, label, color } = getStrength(password);
  const max = 5;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
      <div style={{ display: "flex", gap: "4px" }}>
        {Array.from({ length: max }).map((_, i) => (
          <div
            key={i}
            style={{
              flex: 1,
              height: "3px",
              borderRadius: "99px",
              background: i < score ? color : "rgba(255,255,255,0.08)",
              transition: "background 0.3s",
            }}
          />
        ))}
      </div>
      <span style={{ fontSize: "0.75rem", color, fontWeight: 500 }}>
        {label}
      </span>
    </div>
  );
}
