"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";

import styles from "./page.module.css";
import {
  collectDeviceSpec,
  collectNetworkContext,
  collectSessionMetadata,
} from "./collectors";
import { BehavioralSignals, useBehavior } from "./useBehavior";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showBehavior, setShowBehavior] = useState(false);
  const [behaviorMetrics, setBehaviorMetrics] = useState<BehaviorMetrics | null>(null);
  const [status, setStatus] = useState<
    "idle" | "loading" | "success" | "error"
  >("idle");
  const [errorMsg, setErrorMsg] = useState("");
  const [delayRemaining, setDelayRemaining] = useState(0);

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

  useEffect(() => {
    if (delayRemaining <= 0) {
      return;
    }

    const timer = window.setInterval(() => {
      setDelayRemaining((prev) => Math.max(0, prev - 1));
    }, 1000);

    return () => window.clearInterval(timer);
  }, [delayRemaining]);

  const formatMetric = (value: number | null, digits = 1) => {
    if (value === null || Number.isNaN(value)) {
      return "--";
    }
    return value.toFixed(digits);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (delayRemaining > 0) {
      setStatus("error");
      setErrorMsg("Please wait before trying again.");
      return;
    }

    setStatus("loading");
    setErrorMsg("");

    try {
      // Collect all signals at submit time
      const [device_spec, network_context] = await Promise.all([
        Promise.resolve(collectDeviceSpec()),
        collectNetworkContext(),
      ]);
      const session_metadata = collectSessionMetadata();
      const behavioral_signals = snapshot();

      const loginRequest = {
        credentials: { email, password },
        device_spec,
        network_context,
        behavioral_signals,
        session_metadata,
      };

      const res = await fetch("http://localhost:8000/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(loginRequest),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        const detail = data?.detail;
        const wait = Number(
          (typeof detail === "object" ? detail?.delay_seconds : undefined) ??
            data?.delay_seconds ??
            0,
        );

        if (wait > 0) {
          setDelayRemaining(wait);
        }

        if (detail && typeof detail === "object") {
          const message = detail.message ?? "Invalid credentials";
          throw new Error(message);
        }

        throw new Error(detail ?? `HTTP ${res.status}`);
      }

      setStatus("success");
      setTimeout(() => {
        router.push("/dashboard");
      }, 600);
    } catch (err: unknown) {
      setStatus("error");
      setErrorMsg(
        err instanceof Error ? err.message : "Login failed. Please try again.",
      );
    }
  };

  const errorMessageWithDelay =
    delayRemaining > 0
      ? `${errorMsg || "Please wait"} ${delayRemaining} seconds.`
      : errorMsg;

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
          <a href="/signup" className={styles.ctaBtn}>
            Create account
          </a>
        </nav>
      </header>

      {/* ── Login card ─────────────────────────────────────────────── */}
      <main className={styles.main}>
        <div className={styles.content}>
          <div className={styles.card}>
            <div className={styles.cardHeader}>
              <div className={styles.iconWrap}>
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  width="28"
                  height="28"
                >
                  <rect x="3" y="11" width="18" height="11" rx="2" />
                  <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                </svg>
              </div>
              <h1 className={styles.title}>Welcome back</h1>
              <p className={styles.subtitle}>Sign in to your SentinelIQ Pay</p>
            </div>

            <form className={styles.form} onSubmit={handleSubmit} noValidate>
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

              <div className={styles.field}>
                <label htmlFor="password" className={styles.label}>
                  Password
                  <a href="#" className={styles.forgotLink}>
                    Forgot?
                  </a>
                </label>
                <input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  required
                  placeholder="••••••••"
                  className={styles.input}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onPaste={onPasswordPaste}
                />
              </div>

              {(errorMsg || delayRemaining > 0) && (
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
                  {errorMessageWithDelay}
                </div>
              )}

              {status === "success" && (
                <div className={styles.successBanner} role="status">
                  ✓ Login successful — redirecting…
                </div>
              )}

              <button
                type="submit"
                className={styles.submitBtn}
                disabled={status === "loading" || status === "success" || delayRemaining > 0}
              >
                {status === "loading" ? (
                  <span className={styles.spinner} aria-label="Signing in…" />
                ) : (
                  "Sign in"
                )}
              </button>
            </form>

            <p className={styles.signupPrompt}>
              Don&apos;t have an account?{" "}
              <a href="/signup" className={styles.signupLink}>
                Create one free
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
