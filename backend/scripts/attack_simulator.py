"""SentinelIQ attack simulator.

Drives POST /api/auth/login with crafted payloads to exercise each rule-based
detector (velocity, geo, device, behavioral) and reports the per-signal
breakdown returned by the backend in DEBUG mode.

Prereqs:
  - Backend running with DEBUG=True (so /login returns a `debug` field).
  - One registered + verified test user (pass via --email / --password).
  - Backend trusts X-Forwarded-For (it does today). The simulator uses it to
    spoof source IPs for geo / velocity scenarios.

Usage examples (PowerShell):
  python scripts/attack_simulator.py --email test@x.com --password Hunter2! brute_force
  python scripts/attack_simulator.py --email test@x.com --password Hunter2! impossible_travel
  python scripts/attack_simulator.py --email test@x.com --password Hunter2! all
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
import uuid
from dataclasses import dataclass
from typing import Any

import requests

DEFAULT_BASE_URL = "http://localhost:8000/api"

# Real public IPs ipinfo will resolve to known countries / ASNs.
IP_US = "8.8.8.8"            # Google DNS, US
IP_AU = "1.1.1.1"            # Cloudflare, AU
IP_NP = "27.34.20.1"         # Nepal residential range
IP_DE = "144.76.10.1"        # Hetzner DE (also a datacenter ASN)
IP_AWS = "52.95.110.1"       # AWS, datacenter ASN
IP_CF = "104.16.50.1"        # Cloudflare edge, datacenter ASN


# ─── payload builders ────────────────────────────────────────────────────────

def human_device(seed: str = "stable") -> dict[str, Any]:
    """Stable device spec that should look like a known/trusted machine after
    the first login."""
    return {
        "device_fingerprint": f"fp-known-{seed}",
        "hardware_concurrency": 8,
        "device_memory": 8.0,
        "screen_width": 1920,
        "screen_height": 1080,
        "pixel_ratio": 1.0,
        "is_touch": False,
        "platform": "Win32",
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        ),
        "color_depth": "24",
        "plugins_hash": "ph-stable",
        "canvas_hash": "cv-stable",
        "webgl_renderer": "ANGLE (NVIDIA GeForce RTX 3060)",
    }


def new_device(seed: str | None = None) -> dict[str, Any]:
    """Randomized device spec — looks like a brand-new machine."""
    rnd = seed or uuid.uuid4().hex[:8]
    platforms = ["Linux x86_64", "MacIntel", "Win32", "Linux armv8l"]
    return {
        "device_fingerprint": f"fp-new-{rnd}",
        "hardware_concurrency": random.choice([2, 4, 6, 16]),
        "device_memory": random.choice([2.0, 4.0, 16.0]),
        "screen_width": random.choice([1280, 1366, 2560, 3840]),
        "screen_height": random.choice([720, 768, 1440, 2160]),
        "pixel_ratio": random.choice([1.0, 1.5, 2.0]),
        "is_touch": random.choice([True, False]),
        "platform": random.choice(platforms),
        "user_agent": f"Mozilla/5.0 SimBot/{rnd}",
        "color_depth": "24",
        "plugins_hash": f"ph-{rnd}",
        "canvas_hash": f"cv-{rnd}",
        "webgl_renderer": f"SwiftShader-{rnd}",
    }


def human_network() -> dict[str, Any]:
    return {
        "timezone": "Asia/Kathmandu",
        "language": "en-US",
        "languages": ["en-US", "en"],
        "connection_type": "wifi",
        "webrtc_local_ip": "192.168.1.42",
        "do_not_track": None,
    }


def human_behavior() -> dict[str, Any]:
    """Realistic-ish typing with jitter."""
    return {
        "form_time_ms": random.randint(4000, 9000),
        "password_pasted": False,
        "username_pasted": False,
        "avg_dwell_time_ms": random.uniform(80, 140),
        "avg_flight_time_ms": random.uniform(120, 220),
        "keystroke_variance": random.uniform(20, 60),
        "typo_count": random.randint(0, 2),
        "mouse_event_count": random.randint(20, 80),
        "mouse_linearity": random.uniform(0.3, 0.6),
        "mouse_avg_speed": random.uniform(0.4, 0.9),
        "used_tab_to_navigate": random.choice([True, False]),
    }


def bot_behavior() -> dict[str, Any]:
    """Bot signature: instant form, zero typing variance, no mouse, paste."""
    return {
        "form_time_ms": random.randint(40, 250),
        "password_pasted": True,
        "username_pasted": True,
        "avg_dwell_time_ms": 5.0,
        "avg_flight_time_ms": 5.0,
        "keystroke_variance": 0.0,
        "typo_count": 0,
        "mouse_event_count": 0,
        "mouse_linearity": 1.0,
        "mouse_avg_speed": 0.0,
        "used_tab_to_navigate": False,
    }


def session_meta(*, webdriver: bool = False, headless: bool = False) -> dict[str, Any]:
    return {
        "session_id": str(uuid.uuid4()),
        "referrer": "http://localhost:3000/login",
        "cookies_enabled": True,
        "webdriver": webdriver,
        "chrome_headless": headless,
        "no_plugins": False,
    }


def build_payload(
    email: str,
    password: str,
    *,
    device: dict[str, Any] | None = None,
    network: dict[str, Any] | None = None,
    behavior: dict[str, Any] | None = None,
    session: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "credentials": {"email": email, "password": password},
        "device_spec": device or human_device(),
        "network_context": network or human_network(),
        "behavioral_signals": behavior or human_behavior(),
        "session_metadata": session or session_meta(),
    }


# ─── HTTP helpers ────────────────────────────────────────────────────────────

@dataclass
class LoginOutcome:
    status_code: int
    body: Any
    spoofed_ip: str

    @property
    def decision(self) -> str:
        if isinstance(self.body, dict):
            dbg = self.body.get("debug")
            if isinstance(dbg, dict) and "decision" in dbg:
                return dbg["decision"]
            detail = self.body.get("detail")
            if isinstance(detail, dict):
                inner = detail.get("debug")
                if isinstance(inner, dict) and "decision" in inner:
                    return inner["decision"]
        return f"http_{self.status_code}"

    @property
    def signals(self) -> dict[str, float] | None:
        candidates = []
        if isinstance(self.body, dict):
            candidates.append(self.body.get("debug"))
            detail = self.body.get("detail")
            if isinstance(detail, dict):
                candidates.append(detail.get("debug"))
        for c in candidates:
            if isinstance(c, dict) and isinstance(c.get("signals"), dict):
                return c["signals"]
        return None


def post_login(base_url: str, payload: dict[str, Any], spoofed_ip: str) -> LoginOutcome:
    url = f"{base_url}/auth/login"
    headers = {"X-Forwarded-For": spoofed_ip, "Content-Type": "application/json"}
    r = requests.post(url, json=payload, headers=headers, timeout=60)
    try:
        body = r.json()
    except ValueError:
        body = r.text
    return LoginOutcome(r.status_code, body, spoofed_ip)


def print_outcome(label: str, out: LoginOutcome) -> None:
    sig = out.signals or {}
    sig_str = (
        f"v={sig.get('velocity', 0):.2f} g={sig.get('geo', 0):.2f} "
        f"d={sig.get('device', 0):.2f} b={sig.get('behavioral', 0):.2f}"
        if sig
        else "(no debug breakdown — is DEBUG=True?)"
    )
    final = None
    ml_val = None
    if isinstance(out.body, dict):
        final = out.body.get("risk")
        dbg_body = out.body.get("debug")
        if isinstance(dbg_body, dict):
            ml_val = dbg_body.get("ml")
            if final is None:
                final = dbg_body.get("final")
        if final is None and isinstance(out.body.get("detail"), dict):
            inner_dbg = out.body["detail"].get("debug", {})
            final = inner_dbg.get("final")
            if ml_val is None:
                ml_val = inner_dbg.get("ml")
    final_str = f"{final:.3f}" if isinstance(final, (int, float)) else "—"
    ml_str = f" ml={ml_val:.2f}" if isinstance(ml_val, (int, float)) else ""

    # Pull optional extras (only present in 401 debug payloads).
    extra = ""
    dbg = None
    if isinstance(out.body, dict):
        dbg = out.body.get("debug")
        if dbg is None and isinstance(out.body.get("detail"), dict):
            dbg = out.body["detail"].get("debug")
    if isinstance(dbg, dict):
        vc = dbg.get("velocity_counts")
        flc = dbg.get("failed_login_count")
        bits = []
        if isinstance(vc, dict):
            bits.append(f"counts(u={vc.get('user')},ip={vc.get('ip')},u_ip={vc.get('user_ip')})")
        if isinstance(flc, int):
            bits.append(f"fails={flc}")
        if bits:
            extra = "  " + " ".join(bits)

    print(
        f"  [{out.status_code}] {label:<28} ip={out.spoofed_ip:<15} "
        f"decision={out.decision:<20} final={final_str}  {sig_str}{ml_str}{extra}"
    )


# ─── scenarios ───────────────────────────────────────────────────────────────

def scenario_brute_force(base_url: str, email: str, password: str) -> None:
    print("\n=== brute_force: 15 wrong-password attempts from one IP, then 1 real-creds probe ===")
    print("Expected: per-(user,ip) velocity climbs; final probe shows v= lit on a successful run.")
    ip = IP_NP
    tripped = False
    for i in range(15):
        payload = build_payload(email, "wrong-" + uuid.uuid4().hex[:6])
        out = post_login(base_url, payload, ip)
        print_outcome(f"wrong #{i+1}", out)
        if out.status_code == 429:
            print("  → backend tripped the IP rate limit. Good.")
            tripped = True
            break
        time.sleep(0.05)

    if not tripped:
        print("\n  -- probe with CORRECT password to see the full breakdown --")
        probe = post_login(base_url, build_payload(email, password), ip)
        print_outcome("correct-creds probe", probe)


def scenario_distributed_brute(base_url: str, email: str, password: str) -> None:
    print("\n=== distributed_brute: same user, rotated IPs ===")
    print("Expected: per-IP velocity stays low, but per-USER velocity climbs and triggers velocity risk.")
    for i in range(20):
        ip = f"203.0.113.{random.randint(1, 250)}"   # TEST-NET-3
        payload = build_payload(email, "wrong-" + uuid.uuid4().hex[:6])
        out = post_login(base_url, payload, ip)
        print_outcome(f"attempt #{i+1}", out)
        time.sleep(0.05)


def scenario_impossible_travel(base_url: str, email: str, password: str) -> None:
    print("\n=== impossible_travel: login from US, then 5s later from AU ===")
    print("Expected: 2nd login flags geo risk (speed > GEO_MAX_SPEED_KMH).")
    dev = human_device("travel")
    out1 = post_login(base_url, build_payload(email, password, device=dev), IP_US)
    print_outcome("login from US", out1)
    if out1.status_code >= 400:
        print("  ! first login was rejected. Verify creds / verified user.")
        return
    time.sleep(5)
    out2 = post_login(base_url, build_payload(email, password, device=dev), IP_AU)
    print_outcome("login from AU", out2)


def scenario_new_device(base_url: str, email: str, password: str) -> None:
    print("\n=== new_device: correct password but brand-new fingerprint ===")
    print("Expected: device signal ~0.5 → likely STEP_UP MFA.")
    payload = build_payload(email, password, device=new_device())
    out = post_login(base_url, payload, IP_NP)
    print_outcome("new device login", out)


def scenario_bot_behavior(base_url: str, email: str, password: str) -> None:
    print("\n=== bot_behavior: correct password with bot-like typing ===")
    print("Note: behavioral baseline only kicks in after BEHAVIOR_MIN_LOGINS_FOR_BASELINE (5) successful logins.")
    payload = build_payload(
        email, password,
        device=human_device("bot"),
        behavior=bot_behavior(),
        session=session_meta(webdriver=True, headless=True),
    )
    out = post_login(base_url, payload, IP_NP)
    print_outcome("bot login", out)


def scenario_datacenter_ip(base_url: str, email: str, password: str) -> None:
    print("\n=== datacenter_ip: correct password from an AWS IP ===")
    print("Expected: geo risk bumps because ASN matches DATACENTER_ASNS.")
    for ip, label in [(IP_AWS, "AWS"), (IP_CF, "Cloudflare"), (IP_DE, "Hetzner")]:
        out = post_login(base_url, build_payload(email, password), ip)
        print_outcome(f"login via {label}", out)
        time.sleep(0.5)


def scenario_combined(base_url: str, email: str, password: str) -> None:
    print("\n=== combined: new device + foreign IP + bot typing + headless ===")
    print("Expected: BLOCK or STEP_UP with multiple signals lit.")
    payload = build_payload(
        email, password,
        device=new_device(),
        behavior=bot_behavior(),
        session=session_meta(webdriver=True, headless=True),
    )
    out = post_login(base_url, payload, IP_AWS)
    print_outcome("combined attack", out)


SCENARIOS = {
    "brute_force": scenario_brute_force,
    "distributed_brute": scenario_distributed_brute,
    "impossible_travel": scenario_impossible_travel,
    "new_device": scenario_new_device,
    "bot_behavior": scenario_bot_behavior,
    "datacenter_ip": scenario_datacenter_ip,
    "combined": scenario_combined,
}


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="SentinelIQ rule-based engine simulator")
    parser.add_argument("scenario", choices=[*SCENARIOS, "all"],
                        help="which scenario to run")
    parser.add_argument("--email", required=True, help="verified test user email")
    parser.add_argument("--password", required=True, help="correct password for that user")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL,
                        help=f"backend API base (default {DEFAULT_BASE_URL})")
    parser.add_argument("--seed", type=int, default=None,
                        help="random seed for reproducible runs")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    print(f"Target: {args.base_url}")
    print(f"User:   {args.email}")

    scenarios = list(SCENARIOS.values()) if args.scenario == "all" else [SCENARIOS[args.scenario]]
    for fn in scenarios:
        try:
            fn(args.base_url, args.email, args.password)
        except requests.RequestException as e:
            print(f"  ! request failed: {e}")
        except Exception as e:  # noqa: BLE001
            print(f"  ! scenario error: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
