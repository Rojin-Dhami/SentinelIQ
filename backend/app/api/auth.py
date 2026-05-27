"""
app/api/auth.py — /api/auth/signup and /api/auth/login endpoints.

Key pipeline (login):
  1. Extract client IP
  2. Compute heuristic bot-signal risk (webdriver / headless)
  3. Authenticate user (password check)
  4. Call geo detection  → distance, country, lat/lon
  5. Call ML engine      → Isolation Forest score + tier
  6. Gate on tier: HARD_BLOCK / ACCOUNT_LOCK → reject; MFA_STEP_UP → warn; ALLOW → pass
  7. Persist LoginAttempt with all scores
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token
from app.deps import get_db, get_redis
from app.db.models import LoginAttempt, User
from app.detection.geo import check_geo
from app.detection.velocity import check_velocity
from app.ml.engine import score_login

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_client_ip(request: Request) -> str:
    """Extract real client IP, respecting X-Forwarded-For for reverse proxies."""
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "127.0.0.1"


def _heuristic_bot_score(session: "SessionMetadata", behavior: "BehavioralSignals") -> int:
    """
    Fast bot-signal check from browser telemetry only.
    Returns 0-100. Used as a pre-filter before the ML model.
    """
    score = 0
    if session.webdriver:         score += 40
    if session.chrome_headless:   score += 30
    if session.no_plugins:        score += 10
    if session.headless_signals not in ("none", ""):
        score += 10
    if 0 < behavior.form_time_ms < 1000:      score += 15
    if behavior.mouse_event_count == 0:        score += 10
    if 0 < behavior.avg_dwell_time_ms < 30:    score += 10
    if behavior.password_pasted and behavior.username_pasted:
        score += 5
    return min(score, 100)


# ─── Pydantic schemas ─────────────────────────────────────────────────────────

class DeviceSpec(BaseModel):
    device_fingerprint: str = ""
    hardware_concurrency: int = 0
    device_memory: float = 0
    screen_width: int = 0
    screen_height: int = 0
    pixel_ratio: int = 1
    is_touch: bool = False
    platform: int = 5
    user_agent: str = ""
    color_depth: str = ""
    plugins_hash: str = ""
    canvas_hash: str = ""
    webgl_renderer: str = ""


class NetworkContext(BaseModel):
    timezone: str = ""
    language: str = ""
    languages: list[str] = []
    connection_type: str = ""
    webrtc_local_ip: str | None = None
    do_not_track: str | None = None


class BehavioralSignals(BaseModel):
    form_time_ms: int = 0
    password_pasted: bool = False
    username_pasted: bool = False
    avg_dwell_time_ms: float = 0
    avg_flight_time_ms: float = 0
    keystroke_variance: float = 0
    typo_count: int = 0
    mouse_event_count: int = 0
    mouse_linearity: float = 1
    mouse_avg_speed: float = 0
    used_tab_to_navigate: bool = False


class SessionMetadata(BaseModel):
    session_id: str = ""
    referrer: str | None = None
    cookies_enabled: bool = True
    headless_signals: str = "none"
    webdriver: bool = False
    chrome_headless: bool = False
    no_plugins: bool = False


class SignupCredentials(BaseModel):
    full_name: str
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        return v

    @field_validator("full_name")
    @classmethod
    def name_required(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Full name is required.")
        return v.strip()


class LoginCredentials(BaseModel):
    email: EmailStr
    password: str


class SignupRequest(BaseModel):
    credentials: SignupCredentials
    device_spec: DeviceSpec = DeviceSpec()
    network_context: NetworkContext = NetworkContext()
    behavioral_signals: BehavioralSignals = BehavioralSignals()
    session_metadata: SessionMetadata = SessionMetadata()


class LoginRequest(BaseModel):
    credentials: LoginCredentials
    device_spec: DeviceSpec = DeviceSpec()
    network_context: NetworkContext = NetworkContext()
    behavioral_signals: BehavioralSignals = BehavioralSignals()
    session_metadata: SessionMetadata = SessionMetadata()


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    full_name: str
    risk_score: float = 0.0
    risk_tier: str = "ALLOW"


# ─── Signup ───────────────────────────────────────────────────────────────────

@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    body: SignupRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    creds = body.credentials

    # 1. Quick bot heuristic
    bot_score = _heuristic_bot_score(body.session_metadata, body.behavioral_signals)
    if bot_score >= 70:
        logger.warning("Signup blocked — bot score %d for %s", bot_score, creds.email)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Request flagged as automated. Please try again from a normal browser.",
        )

    # 2. Duplicate email check
    result = await db.execute(select(User).where(User.email == creds.email.lower()))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    d = body.device_spec
    n = body.network_context
    s = body.session_metadata

    user = User(
        email=creds.email.lower(),
        full_name=creds.full_name,
        hashed_password=pwd_context.hash(creds.password),
        signup_device_fingerprint=d.device_fingerprint or None,
        signup_canvas_hash=d.canvas_hash or None,
        signup_webgl_renderer=d.webgl_renderer or None,
        signup_platform=d.platform,
        signup_screen=f"{d.screen_width}x{d.screen_height}",
        signup_timezone=n.timezone or None,
        signup_language=n.language or None,
        signup_webrtc_ip=n.webrtc_local_ip,
        signup_headless_signals=s.headless_signals,
        signup_webdriver=s.webdriver,
        signup_risk_score=bot_score,
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    logger.info("New user created: %s (bot_score=%d)", user.email, bot_score)

    return AuthResponse(
        access_token=create_access_token(str(user.id), user.email),
        user_id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        risk_score=bot_score / 100.0,
        risk_tier="ALLOW",
    )


# ─── Login ────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=AuthResponse)
async def login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    creds = body.credentials
    ip = _get_client_ip(request)
    d = body.device_spec
    n = body.network_context
    b = body.behavioral_signals
    s = body.session_metadata

    # 1. Quick bot heuristic check
    bot_score = _heuristic_bot_score(s, b)
    if bot_score >= 70:
        logger.warning("Login blocked — bot score %d for %s", bot_score, creds.email)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Request flagged as automated. Please try again from a normal browser.",
        )

    # 2. Velocity check (using email as identifier pre-auth)
    velocity_result = await check_velocity(creds.email.lower(), ip, redis)
    if velocity_result.flagged:
        logger.warning(
            "Login rate-limited — user_count=%d ip_count=%d for %s",
            velocity_result.user_count, velocity_result.ip_count, creds.email,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please wait before trying again.",
        )

    # 3. Authenticate user
    result = await db.execute(select(User).where(User.email == creds.email.lower()))
    user = result.scalar_one_or_none()

    # Build attempt record (committed on both success and failure)
    attempt = LoginAttempt(
        email=creds.email.lower(),
        success=False,
        ip_address=ip,
        user_agent=d.user_agent or None,
        # device
        device_fingerprint=d.device_fingerprint or None,
        canvas_hash=d.canvas_hash or None,
        webgl_renderer=d.webgl_renderer or None,
        platform=d.platform,
        screen=f"{d.screen_width}x{d.screen_height}",
        pixel_ratio=d.pixel_ratio,
        hardware_concurrency=d.hardware_concurrency,
        is_touch=d.is_touch,
        # network
        timezone=n.timezone or None,
        language=n.language or None,
        connection_type=n.connection_type or None,
        webrtc_local_ip=n.webrtc_local_ip,
        do_not_track=n.do_not_track,
        # behavioral
        form_time_ms=b.form_time_ms,
        password_pasted=b.password_pasted,
        username_pasted=b.username_pasted,
        avg_dwell_time_ms=b.avg_dwell_time_ms,
        avg_flight_time_ms=b.avg_flight_time_ms,
        keystroke_variance=b.keystroke_variance,
        typo_count=b.typo_count,
        mouse_event_count=b.mouse_event_count,
        mouse_linearity=b.mouse_linearity,
        mouse_avg_speed=b.mouse_avg_speed,
        used_tab_to_navigate=b.used_tab_to_navigate,
        # session
        session_id=s.session_id or None,
        headless_signals=s.headless_signals,
        webdriver=s.webdriver,
        chrome_headless=s.chrome_headless,
        no_plugins=s.no_plugins,
        risk_score=bot_score,
    )

    if not user or not pwd_context.verify(creds.password, user.hashed_password):
        logger.warning("Failed login attempt for %s from %s", creds.email, ip)
        db.add(attempt)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Please contact support.",
        )

    # 4. Determine if this is a new device
    is_new_device = bool(
        user.signup_device_fingerprint
        and d.device_fingerprint
        and d.device_fingerprint != user.signup_device_fingerprint
    )

    # 5. Geo check — get location, distance, country
    geo_result, is_proxy, is_datacenter = await check_geo(str(user.id), ip, redis)

    # Extract geo values for ML
    current_loc = geo_result.current_location
    country_code = current_loc.country_code if current_loc else "NP"
    latitude     = current_loc.lat          if current_loc else 27.7103
    longitude    = current_loc.lon          if current_loc else 85.3222
    distance_km  = geo_result.distance_km   if geo_result.distance_km is not None else 0.0
    hours_since  = (
        (geo_result.time_elapsed_seconds / 3600)
        if geo_result.time_elapsed_seconds is not None
        else 0.0
    )

    # 6. ML Isolation Forest scoring
    ml_result = await score_login(
        user_id=str(user.id),
        ip_address=ip,
        is_new_device=is_new_device,
        is_tor=s.webdriver and s.no_plugins,   # strong proxy for headless/automation
        is_known_vpn=is_proxy,
        is_datacenter_ip=is_datacenter,
        country_code=country_code,
        latitude=latitude,
        longitude=longitude,
        distance_from_last_login_km=distance_km,
        hours_since_last_login=hours_since,
        redis=redis,
    )

    # 7. Gate on ML tier
    if ml_result.tier == "HARD_BLOCK":
        logger.warning(
            "ML HARD_BLOCK user=%s score=%.3f reason=%s",
            user.email, ml_result.score, ml_result.rule_reason,
        )
        attempt.flagged = True
        attempt.flag_reason = ml_result.rule_reason or "ML HARD_BLOCK"
        attempt.risk_score = ml_result.score
        attempt.geo_signals = {
            "country": country_code,
            "distance_km": distance_km,
            "is_proxy": is_proxy,
        }
        db.add(attempt)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ml_result.rule_reason or "Login blocked due to suspicious activity.",
        )

    if ml_result.tier == "ACCOUNT_LOCK":
        logger.warning(
            "ML ACCOUNT_LOCK user=%s score=%.3f reason=%s",
            user.email, ml_result.score, ml_result.rule_reason,
        )
        attempt.flagged = True
        attempt.flag_reason = ml_result.rule_reason or "ML ACCOUNT_LOCK"
        attempt.risk_score = ml_result.score
        db.add(attempt)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been temporarily locked due to unusual activity. "
                   "Please contact support.",
        )

    # MFA_STEP_UP — log warning but allow for now (extend with OTP in future)
    if ml_result.tier == "MFA_STEP_UP":
        logger.info(
            "ML MFA_STEP_UP user=%s score=%.3f — logging, proceeding",
            user.email, ml_result.score,
        )

    # 8. Successful login — persist attempt
    attempt.success = True
    attempt.user_id = user.id
    attempt.risk_score = ml_result.score
    attempt.flagged = ml_result.tier in ("MFA_STEP_UP",)
    attempt.flag_reason = ml_result.rule_reason
    attempt.geo_signals = {
        "country": country_code,
        "lat": latitude,
        "lon": longitude,
        "distance_km": distance_km,
        "is_proxy": is_proxy,
        "is_datacenter": is_datacenter,
        "is_impossible_travel": geo_result.is_impossible_travel,
    }
    attempt.behavioral_signals = {
        "form_time_ms": b.form_time_ms,
        "mouse_event_count": b.mouse_event_count,
        "ml_tier": ml_result.tier,
        "ml_score": ml_result.score,
        "top_factors": [f["feature"] for f in ml_result.top_factors[:3]],
    }
    db.add(attempt)
    await db.commit()

    logger.info(
        "Successful login: %s ip=%s ml_score=%.3f tier=%s",
        user.email, ip, ml_result.score, ml_result.tier,
    )

    return AuthResponse(
        access_token=create_access_token(str(user.id), user.email),
        user_id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        risk_score=round(ml_result.score, 4),
        risk_tier=ml_result.tier,
    )