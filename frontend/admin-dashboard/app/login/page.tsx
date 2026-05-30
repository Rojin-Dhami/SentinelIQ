"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ApiError, login, me } from "../lib/api";
import { buildAdminLoginPayload } from "../lib/loginPayload";
import { C } from "../lib/theme";

function LoginInner() {
  const router = useRouter();
  const params = useSearchParams();
  const initialErr = params.get("err");

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(
    initialErr === "not_admin"
      ? "Account is not an admin. (Tip: another login on localhost may have overwritten your admin cookie — open the admin dashboard at http://127.0.0.1:3000 to avoid this.)"
      : initialErr === "expired"
        ? "Session expired or replaced — please sign in again."
        : null,
  );
  const startedAt = useRef<number>(Date.now());

  useEffect(() => {
    // If already logged in as admin, skip the form.
    me()
      .then((u) => {
        if (u.role === "admin") router.replace("/");
      })
      .catch(() => {});
  }, [router]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      const payload = buildAdminLoginPayload(
        email,
        password,
        Date.now() - startedAt.current,
      );
      const res = (await login(payload)) as { status?: string };
      if (res?.status === "mfa_required") {
        setErr("Account requires MFA — not supported in admin console yet.");
        return;
      }
      const u = await me();
      if (u.role !== "admin") {
        setErr("Account is not an admin.");
        return;
      }
      router.replace("/");
    } catch (e) {
      if (e instanceof ApiError) {
        setErr(e.message || `Login failed (HTTP ${e.status})`);
      } else {
        setErr("Login failed.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        background: C.bgMain,
        color: C.textWhite,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
      }}
    >
      <form
        onSubmit={onSubmit}
        style={{
          width: "100%",
          maxWidth: 380,
          background: C.bgCard,
          border: `1px solid ${C.borderCard}`,
          borderRadius: 12,
          padding: 28,
          display: "flex",
          flexDirection: "column",
          gap: 14,
        }}
      >
        <div style={{ marginBottom: 6 }}>
          <div
            style={{
              fontSize: 20,
              fontWeight: "bold",
              letterSpacing: "-0.02em",
            }}
          >
            <span style={{ color: C.textWhite }}>Sentinel</span>
            <span style={{ color: C.teal }}>IQ</span>
            <span style={{ color: C.textMuted, fontWeight: "normal" }}>
              {" "}
              · Admin
            </span>
          </div>
          <div
            style={{
              fontSize: 10,
              fontFamily: "monospace",
              color: C.textMuted,
              letterSpacing: "0.12em",
              textTransform: "uppercase",
              marginTop: 4,
            }}
          >
            Sign in to continue
          </div>
        </div>

        <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <span style={labelStyle}>Email</span>
          <input
            type="email"
            required
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            style={inputStyle}
          />
        </label>

        <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <span style={labelStyle}>Password</span>
          <input
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            style={inputStyle}
          />
        </label>

        {err && (
          <div
            style={{
              fontSize: 11,
              fontFamily: "monospace",
              color: C.red,
              background: "rgba(239,68,68,0.08)",
              border: `1px solid ${C.red}40`,
              borderRadius: 6,
              padding: "8px 10px",
            }}
          >
            {err}
          </div>
        )}

        <button
          type="submit"
          disabled={busy}
          style={{
            marginTop: 4,
            padding: "10px 0",
            background: busy ? "#0a1a2e" : C.teal,
            color: busy ? C.textMuted : "#06212a",
            border: "none",
            borderRadius: 6,
            fontFamily: "monospace",
            fontWeight: "bold",
            fontSize: 12,
            letterSpacing: "0.15em",
            textTransform: "uppercase",
            cursor: busy ? "not-allowed" : "pointer",
            transition: "background 0.15s",
          }}
        >
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}

const labelStyle: React.CSSProperties = {
  fontSize: 10,
  fontFamily: "monospace",
  color: C.textLabel,
  letterSpacing: "0.12em",
  textTransform: "uppercase",
};

const inputStyle: React.CSSProperties = {
  background: "#0a1a2e",
  border: `1px solid ${C.borderSub}`,
  borderRadius: 6,
  padding: "9px 11px",
  fontSize: 13,
  color: C.textWhite,
  outline: "none",
  fontFamily: "inherit",
};

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginInner />
    </Suspense>
  );
}
