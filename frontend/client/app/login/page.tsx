"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import styles from "./page.module.css";
import { collectDeviceSpec, collectNetworkContext, collectSessionMetadata } from "./collectors";
import { useBehavior } from "./useBehavior";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState("");

  const { snapshot, onUsernamePaste, onPasswordPaste } = useBehavior();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatus("loading");
    setErrorMsg("");

    try {
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
        throw new Error(data?.detail ?? `HTTP ${res.status}`);
      }

      const data = await res.json();

      // Store auth token and user info
      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("user_id", data.user_id);
      localStorage.setItem("user_email", data.email);
      localStorage.setItem("user_name", data.full_name);

      setStatus("success");

      // Redirect after a brief success flash
      setTimeout(() => router.push("/dashboard"), 1000);
    } catch (err: unknown) {
      setStatus("error");
      setErrorMsg(err instanceof Error ? err.message : "Login failed. Please try again.");
    }
  };

  return (
    <div className={styles.page}>
      {/* ── Navbar ──────────────────────────────────────────────────── */}
      <header className={styles.navbar}>
        <a href="/" className={styles.logo}>Innovators Wallet</a>
        <nav className={styles.navLinks}>
          <a href="#">Features</a>
          <a href="#">Security</a>
          <a href="#">Pricing</a>
        </nav>
      </header>

      {/* ── Login card ─────────────────────────────────────────────── */}
      <main className={styles.main}>
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <div className={styles.iconWrap}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" width="28" height="28">
                <rect x="3" y="11" width="18" height="11" rx="2" />
                <path d="M7 11V7a5 5 0 0 1 10 0v4" />
              </svg>
            </div>
            <h1 className={styles.title}>Welcome back</h1>
            <p className={styles.subtitle}>Sign in to your Innovators Wallet</p>
          </div>

          <form className={styles.form} onSubmit={handleSubmit} noValidate>
            <div className={styles.field}>
              <label htmlFor="email" className={styles.label}>Email address</label>
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
                <a href="#" className={styles.forgotLink}>Forgot?</a>
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

            {errorMsg && (
              <div className={styles.errorBanner} role="alert">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16">
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="8" x2="12" y2="12" />
                  <line x1="12" y1="16" x2="12.01" y2="16" />
                </svg>
                {errorMsg}
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
              disabled={status === "loading" || status === "success"}
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
      </main>
    </div>
  );
}