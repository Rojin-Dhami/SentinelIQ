"""
app/ml/engine.py — Singleton wrapper around the SentinelIQ Isolation Forest engine.

Loads the model once at startup and exposes score_login() for use in the auth routes.
"""

from __future__ import annotations

import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from redis.asyncio import Redis

logger = logging.getLogger(__name__)

# ── Resolve path to ml_core (SentinelIQ/ml_core/) ─────────────────────────────
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent  # …/SentinelIQ/backend
_ML_CORE_DIR = _BACKEND_DIR.parent / "ml_core"               # …/SentinelIQ/ml_core

if str(_ML_CORE_DIR) not in sys.path:
    sys.path.insert(0, str(_ML_CORE_DIR))

# Import the SentinelIQ engine AFTER path setup
from sentineliq_inference_if import SentinelIQ, LoginEvent, ScoringResult  # noqa: E402

# ── Singleton ──────────────────────────────────────────────────────────────────

_engine: SentinelIQ | None = None


def get_engine() -> SentinelIQ:
    """Return the global SentinelIQ singleton, loading it on first call."""
    global _engine
    if _engine is None:
        models_dir = _ML_CORE_DIR / "models"
        logger.info("Loading SentinelIQ Isolation Forest from %s", models_dir)
        _engine = SentinelIQ(model_dir=models_dir)
    return _engine


# ── Velocity helpers (1 hr + 24 hr windows) ───────────────────────────────────

async def _get_velocity_counts(
    identifier: str, ip: str, redis: Redis
) -> tuple[int, int]:
    """
    Returns (count_last_1hr, count_last_24hr) for the given identifier (user_id or email).
    Uses separate Redis sorted sets with TTLs.
    """
    try:
        now = time.time()
        key_1h  = f"vel:1h:{identifier}"
        key_24h = f"vel:24h:{identifier}"

        pipe = redis.pipeline()
        pipe.zremrangebyscore(key_1h,  "-inf", now - 3_600)
        pipe.zremrangebyscore(key_24h, "-inf", now - 86_400)
        pipe.zadd(key_1h,  {str(now): now})
        pipe.zadd(key_24h, {str(now): now})
        pipe.zcard(key_1h)
        pipe.zcard(key_24h)
        pipe.expire(key_1h,   7_200)
        pipe.expire(key_24h, 172_800)
        results = await pipe.execute()
        return int(results[4]), int(results[5])
    except Exception as e:
        logger.warning("Velocity Redis error: %s", e)
        return 0, 0


# ── Main scoring function ──────────────────────────────────────────────────────

async def score_login(
    *,
    user_id: str,
    ip_address: str,
    is_new_device: bool,
    is_tor: bool,
    is_known_vpn: bool,
    is_datacenter_ip: bool,
    country_code: str,
    latitude: float,
    longitude: float,
    distance_from_last_login_km: float,
    hours_since_last_login: float,
    redis: Redis,
) -> ScoringResult:
    """
    Build a LoginEvent from all available request signals, run the Isolation
    Forest model, and return a ScoringResult.

    Falls back to a safe ALLOW result if the model can't be loaded or Redis
    is unavailable (so a Redis outage never breaks logins).
    """
    try:
        engine = get_engine()

        now = datetime.now(timezone.utc)
        vel_1h, vel_24h = await _get_velocity_counts(user_id, ip_address, redis)

        # Hour deviation: how far from noon (neutral baseline)
        hour = now.hour
        hour_deviation = abs(hour - 12)

        event = LoginEvent(
            user_id=user_id,
            ip_address=ip_address,
            timestamp_unix=now.timestamp(),
            hour_of_day=hour,
            day_of_week=now.weekday(),
            ip_type="vpn" if is_known_vpn else (
                       "datacenter" if is_datacenter_ip else (
                       "tor" if is_tor else "residential")),
            country=country_code.upper() if country_code else "NP",
            latitude=latitude,
            longitude=longitude,
            is_new_device=is_new_device,
            is_known_vpn=is_known_vpn,
            is_datacenter_ip=is_datacenter_ip,
            is_tor=is_tor,
            velocity_last_1hr=vel_1h,
            velocity_last_24hr=vel_24h,
            distance_from_last_login_km=distance_from_last_login_km,
            hours_since_last_login=hours_since_last_login,
            hour_deviation=hour_deviation,
        )

        result = engine.score(event)
        logger.info(
            "ML score for %s: %.3f tier=%s latency=%.1fms",
            user_id, result.score, result.tier, result.latency_ms,
        )
        return result

    except Exception as exc:
        logger.error("ML scoring failed, defaulting to ALLOW: %s", exc)
        # Safe fallback — never block due to model errors
        from sentineliq_inference_if import ScoringResult, TIER_ACTIONS
        return ScoringResult(
            user_id=user_id,
            score=0.0,
            iso_score=0.0,
            tier="ALLOW",
            action=TIER_ACTIONS["ALLOW"],
            rule_triggered=False,
            rule_reason=None,
            top_factors=[],
            latency_ms=0.0,
            timestamp_unix=time.time(),
        )