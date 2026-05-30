"""Isolation Forest inference shim.

Loads `model.pkl` + `scaler_params.json` once at import time and exposes
`score_login(features) -> float (0-1)`. Returns 0.0 silently on any load or
inference failure so a broken model can never block real logins.

Feature row contract — must match the training order exactly:
    hour_of_day, hour_deviation, distance_from_last_login_km,
    hours_since_last_login, impossible_travel, fail_count_before_success,
    user_account_age_days, velocity_spike_score, geo_time_risk, bot_score,
    trust_deficit_score, network_risk_score
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path

import numpy as np

from app.core.config import settings
from app.detection.behavioral import BehavioralCheckResult
from app.detection.device import DeviceCheckResult
from app.schemas.dto import GeoResult, VelocityResult

logger = logging.getLogger(__name__)

FEATURE_ORDER = [
    "hour_of_day",
    "hour_deviation",
    "distance_from_last_login_km",
    "hours_since_last_login",
    "impossible_travel",
    "fail_count_before_success",
    "user_account_age_days",
    "velocity_spike_score",
    "geo_time_risk",
    "bot_score",
    "trust_deficit_score",
    "network_risk_score",
]

# Lazy-loaded singletons
_model = None
_score_min: float = 0.0
_score_max: float = 0.0
_loaded = False
_load_attempted = False


def _resolve_artifacts_dir() -> Path:
    raw = settings.ML_ARTIFACTS_DIR
    p = Path(raw)
    if p.is_absolute():
        return p
    # Resolve relative to the backend/ folder (where uvicorn runs)
    return (Path(os.getcwd()) / p).resolve()


def _load() -> None:
    global _model, _score_min, _score_max, _loaded, _load_attempted
    if _load_attempted:
        return
    _load_attempted = True
    if not settings.ML_ENABLED:
        logger.info("ML scoring disabled via config")
        return
    try:
        import joblib

        artifacts = _resolve_artifacts_dir()
        model_path = artifacts / "model.pkl"
        scaler_path = artifacts / "scaler_params.json"
        if not model_path.exists() or not scaler_path.exists():
            logger.warning("ML artifacts not found at %s — ML score=0", artifacts)
            return
        _model = joblib.load(model_path)
        params = json.loads(scaler_path.read_text())
        _score_min = float(params["score_min"])
        _score_max = float(params["score_max"])
        _loaded = True
        logger.info(
            "ML model loaded from %s (calibration range [%.4f, %.4f])",
            artifacts, _score_min, _score_max,
        )
    except Exception:
        logger.exception("ML model load failed — ML score will be 0")


def is_loaded() -> bool:
    _load()
    return _loaded


def _calibrate(raw: float) -> float:
    if _score_max == _score_min:
        return 0.0
    clipped = max(_score_min, min(_score_max, raw))
    normalized = (clipped - _score_max) / (_score_min - _score_max + 1e-10)
    return float(max(0.0, min(1.0, normalized)))


def build_feature_row(
    *,
    user_account_age_days: int,
    failed_login_count: int,
    velocity: VelocityResult,
    geo: GeoResult,
    device: DeviceCheckResult,
    behavioral: BehavioralCheckResult,
    now: datetime | None = None,
) -> dict[str, float]:
    """Translate live detection results into the ML feature vocabulary.

    Approximations (training used different/richer data — flagged so we can
    tighten later):
      - velocity_spike_score: 60s user-count as proxy for true 1h/24h spike ratio
      - network_risk_score: only proxy + datacenter (no Tor/IP-reputation yet)
      - hour_deviation: 0 placeholder (no per-user baseline-hour column yet)
    """
    now = now or datetime.now()
    hours_since = (geo.time_elapsed_seconds or 0) / 3600.0
    distance_km = geo.distance_km or 0.0

    # Composite approximations
    velocity_spike = min(velocity.user_count / 5.0, 10.0)  # 5 attempts/min ≈ "1.0 normal pace"
    geo_time = distance_km / max(hours_since, 0.01) if distance_km > 0 else 0.0
    geo_time = min(geo_time, 2000.0)

    is_known_int = 1 if device.is_known_device else 0
    trust_deficit = (
        0.5 * (0 if device.is_trusted_device else 1)
        + 0.3 * (1 - is_known_int)
        + 0.2 * (1 - min(user_account_age_days / 365.0, 1.0))
    )

    network_risk = (
        0.25 * (1 if geo.is_proxy else 0)
        + 0.25 * (1 if geo.is_datacenter else 0)
        # is_tor + ip_reputation placeholders (0) until upstream signal lands
    )

    return {
        "hour_of_day": float(now.hour),
        "hour_deviation": 0.0,
        "distance_from_last_login_km": float(distance_km),
        "hours_since_last_login": float(hours_since),
        "impossible_travel": 1.0 if geo.is_impossible_travel else 0.0,
        "fail_count_before_success": float(failed_login_count),
        "user_account_age_days": float(user_account_age_days),
        "velocity_spike_score": float(velocity_spike),
        "geo_time_risk": float(geo_time),
        "bot_score": float(behavioral.bot_behavior_score),
        "trust_deficit_score": float(min(trust_deficit, 1.0)),
        "network_risk_score": float(min(network_risk, 1.0)),
    }


def score_login(features: dict[str, float]) -> float:
    """Return calibrated risk 0-1. Returns 0.0 if model unavailable."""
    _load()
    if not _loaded or _model is None:
        return 0.0
    try:
        row = np.array([[features[name] for name in FEATURE_ORDER]], dtype=float)
        raw = float(_model.score_samples(row)[0])
        return _calibrate(raw)
    except Exception:
        logger.exception("ML scoring failed — returning 0")
        return 0.0
