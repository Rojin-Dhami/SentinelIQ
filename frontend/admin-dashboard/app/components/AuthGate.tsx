"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { me } from "../lib/api";
import { C } from "../lib/theme";

export default function AuthGate({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [state, setState] = useState<"checking" | "ok">("checking");

  useEffect(() => {
    let cancelled = false;
    me()
      .then((u) => {
        if (cancelled) return;
        if (u.role !== "admin") {
          router.replace("/login?err=not_admin");
          return;
        }
        setState("ok");
      })
      .catch(() => {
        if (!cancelled) router.replace("/login");
      });
    return () => {
      cancelled = true;
    };
  }, [router]);

  if (state === "checking") {
    return (
      <div
        style={{
          minHeight: "100vh",
          background: C.bgMain,
          color: C.textMuted,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: "monospace",
          fontSize: 12,
          letterSpacing: "0.15em",
          textTransform: "uppercase",
        }}
      >
        Checking session…
      </div>
    );
  }

  return <>{children}</>;
}
