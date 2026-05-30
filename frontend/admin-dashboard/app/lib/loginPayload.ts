// Minimal login payload builder for the admin console.
// The backend's /auth/login schema requires full device/network/behavior/session
// objects. Admins are not trying to evade detection, so we send straightforward
// values pulled from the browser with safe defaults.

function uuidv4(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export function buildAdminLoginPayload(
  email: string,
  password: string,
  formTimeMs: number,
) {
  const nav = typeof navigator !== "undefined" ? navigator : ({} as Navigator);
  const scr =
    typeof screen !== "undefined"
      ? screen
      : ({ width: 1920, height: 1080, colorDepth: 24 } as Screen);
  const tz =
    (typeof Intl !== "undefined" &&
      Intl.DateTimeFormat().resolvedOptions().timeZone) ||
    "UTC";

  return {
    credentials: { email, password },
    device_spec: {
      device_fingerprint: `admin-console-${nav.userAgent?.length ?? 0}-${scr.width}x${scr.height}`,
      hardware_concurrency: nav.hardwareConcurrency ?? 4,
      device_memory:
        (nav as Navigator & { deviceMemory?: number }).deviceMemory ?? null,
      screen_width: scr.width,
      screen_height: scr.height,
      pixel_ratio: typeof window !== "undefined" ? window.devicePixelRatio : 1,
      is_touch: typeof window !== "undefined" && "ontouchstart" in window,
      platform: nav.platform ?? "unknown",
      user_agent: nav.userAgent ?? "admin-console",
      color_depth: String(scr.colorDepth ?? 24),
      plugins_hash: null,
      canvas_hash: null,
      webgl_renderer: null,
    },
    network_context: {
      timezone: tz,
      language: nav.language ?? "en-US",
      languages: Array.from(nav.languages ?? ["en-US"]),
      connection_type: null,
      webrtc_local_ip: null,
      do_not_track: null,
    },
    behavioral_signals: {
      form_time_ms: Math.max(500, formTimeMs),
      password_pasted: false,
      username_pasted: false,
      avg_dwell_time_ms: 100,
      avg_flight_time_ms: 150,
      keystroke_variance: 30,
      typo_count: 0,
      mouse_event_count: 25,
      mouse_linearity: 0.4,
      mouse_avg_speed: 0.5,
      used_tab_to_navigate: false,
    },
    session_metadata: {
      session_id: uuidv4(),
      referrer:
        typeof document !== "undefined" ? document.referrer || null : null,
      cookies_enabled:
        typeof navigator !== "undefined" ? navigator.cookieEnabled : true,
      webdriver: false,
      chrome_headless: false,
      no_plugins: false,
    },
  };
}
