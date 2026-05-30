from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.core.config import settings
from app.schemas.dto import VelocityResult, GeoResult
from app.detection.device import DeviceCheckResult
from app.detection.behavioral import BehavioralCheckResult


class RiskDecision(str, Enum):
    ALLOW = "allow"
    STEP_UP = "step_up"
    BLOCK = "block"


@dataclass
class RiskBreakdown:
    velocity: float
    geo: float
    device: float
    behavioral: float
    rule_based: float
    ml: float
    final: float
    decision: RiskDecision

    def to_dict(self, reasons: list[str] | None = None) -> dict:
        return {
            "velocity": round(self.velocity, 4),
            "geo": round(self.geo, 4),
            "device": round(self.device, 4),
            "behavioral": round(self.behavioral, 4),
            "ml": round(self.ml, 4),
            "rule_based": round(self.rule_based, 4),
            "final": round(self.final, 4),
            "decision": self.decision.value,
            "reasons": reasons or [],
        }


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _velocity_risk(v: VelocityResult) -> float:
    return _clamp(max(v.user_risk, v.ip_risk, v.user_ip_risk))


def _device_risk(d: DeviceCheckResult) -> float:
    if d.is_trusted_device:
        risk = 0.0
    elif d.is_known_device:
        # similar (fuzzy) match — small bump, not a full "new device"
        risk = 0.15 if d.is_similar_device else 0.0
    else:
        risk = 0.5
    risk += d.headless_score * 0.5
    return _clamp(risk)


def _behavioral_risk(b: BehavioralCheckResult) -> float:
    # combine static bot score with per-user baseline anomaly
    return _clamp(max(b.bot_behavior_score, b.baseline_anomaly_score))


def _weighted(weights: dict[str, float], risks: dict[str, float]) -> float:
    total = sum(weights.values())
    if total <= 0:
        return 0.0
    return _clamp(sum(risks[k] * weights[k] for k in weights) / total)


def compute_rule_based_risk(
    velocity: VelocityResult,
    geo: GeoResult,
    device: DeviceCheckResult,
    behavioral: BehavioralCheckResult,
) -> tuple[float, dict[str, float]]:
    weights = {
        "velocity": settings.VELOCITY_WEIGHT,
        "geo": settings.GEO_WEIGHT,
        "device": settings.DEVICE_WEIGHT,
        "behavioral": settings.BEHAVIORAL_WEIGHT,
    }
    risks = {
        "velocity": _velocity_risk(velocity),
        "geo": _clamp(geo.risk),
        "device": _device_risk(device),
        "behavioral": _behavioral_risk(behavioral),
    }
    return _weighted(weights, risks), risks


def compute_final_risk(rule_based_risk: float, ml_risk: float | None = None) -> float:
    ml_score = _clamp(ml_risk or 0.0)
    weighted = (rule_based_risk * settings.RULE_BASE_WEIGHT) + (ml_score * settings.ML_WEIGHT)
    return _clamp(weighted)


def decide(final_risk: float, is_trusted_device: bool) -> RiskDecision:
    """Map final risk + trust into an action.

    Trusted devices skip MFA unless risk is extreme (TRUSTED_DEVICE_HARD_BLOCK).
    """
    if final_risk >= settings.RISK_BLOCK_MIN:
        return RiskDecision.BLOCK
    if is_trusted_device and final_risk < settings.TRUSTED_DEVICE_HARD_BLOCK:
        return RiskDecision.ALLOW
    if final_risk >= settings.RISK_ALLOW_MAX:
        return RiskDecision.STEP_UP
    return RiskDecision.ALLOW


def build_breakdown(
    velocity: VelocityResult,
    geo: GeoResult,
    device: DeviceCheckResult,
    behavioral: BehavioralCheckResult,
    ml_risk: float | None = None,
) -> RiskBreakdown:
    rule_based, risks = compute_rule_based_risk(velocity, geo, device, behavioral)
    final = compute_final_risk(rule_based, ml_risk)
    return RiskBreakdown(
        velocity=risks["velocity"],
        geo=risks["geo"],
        device=risks["device"],
        behavioral=risks["behavioral"],
        rule_based=round(rule_based, 4),
        ml=round(_clamp(ml_risk or 0.0), 4),
        final=round(final, 4),
        decision=decide(final, device.is_trusted_device),
    )


def derive_reasons(
    breakdown: RiskBreakdown,
    velocity: VelocityResult,
    geo: GeoResult,
    device: DeviceCheckResult,
    behavioral: BehavioralCheckResult,
) -> list[str]:
    """Translate raw signals into human-readable tags for the admin dashboard.

    Each tag is a stable enum-like string so the UI can render badges and the
    dashboard can filter on them.
    """
    reasons: list[str] = []

    if breakdown.velocity >= 0.5:
        reasons.append("velocity_spike")
    if breakdown.geo >= 0.5:
        # geo.risk already encodes impossible_travel / new_country / tor proxies.
        if getattr(geo, "is_impossible_travel", False):
            reasons.append("impossible_travel")
        elif getattr(geo, "is_new_country", False):
            reasons.append("new_country")
        else:
            reasons.append("geo_anomaly")
    if not device.is_known_device:
        reasons.append("new_device")
    elif device.is_similar_device:
        reasons.append("similar_device")
    if device.headless_score >= 0.5:
        reasons.append("headless_browser")
    if behavioral.bot_behavior_score >= 0.5:
        reasons.append("bot_typing")
    if behavioral.baseline_anomaly_score >= 0.5:
        reasons.append("behavior_drift")
    if breakdown.ml >= 0.6:
        reasons.append("ml_anomaly")

    return reasons
