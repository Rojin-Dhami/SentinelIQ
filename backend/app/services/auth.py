"""Authentication flow with risk-based adaptive MFA.

Decision pipeline:
    1. Always-on signals: behavioral bot detector, velocity (per IP).
    2. Look up user (no early-return on missing email — constant-time).
    3. Verify password (against real hash, or dummy hash if user is None).
    4. If credentials are wrong: record failure + progressive delay + alert at threshold.
    5. If credentials are right: run geo + device + behavioral-baseline in parallel.
    6. Compute final risk → decide ALLOW / STEP_UP / BLOCK.
        - ALLOW   → issue session
        - STEP_UP → store pending challenge in Redis, email OTP, return challenge_id
        - BLOCK   → email "was it you" magic link, refuse login
    7. /auth/mfa/verify consumes the challenge and (optionally) trusts the device.
    8. /auth/security/{yes,no} consume magic link tokens.
"""
import asyncio
import logging
import uuid as uuid_lib
from datetime import datetime, timezone

from fastapi import HTTPException, Request, Response
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.db.models import LoginEvent, LoginOutcome, User, UserDevice
from app.deps import get_client_ip
from app.detection.aggregate import RiskDecision, build_breakdown, derive_reasons
from app.detection.behavioral import check_behavioral, get_profile, update_baseline
from app.detection.device import (
    check_device, increment_device_login, mark_device_trusted, revoke_all_device_trust,
)
from app.detection.geo import check_geo
from app.detection.velocity import check_velocity, record_attempt
from app.ml import inference as ml_inference
from app.schemas.auth import (
    LoginRequest, MfaRequestRequest, MfaVerifyRequest, RegisterRequest, RegisterVerifyRequest,
)
from app.services import lockout, mfa as mfa_svc
from app.services import dashboard, notifications, otp as otp_svc, sessions as session_svc

logger = logging.getLogger(__name__)

# Pre-computed Argon2 hash for a value no one will ever type. Used to keep
# verify_password timing constant when the email doesn't exist.
_DUMMY_PASSWORD_HASH = hash_password("__dummy_password_for_timing__")


def _progressive_delay(failed_count: int) -> int:
    if failed_count < 3:
        return 0
    if failed_count < 5:
        return 3
    if failed_count < 10:
        return 10
    return 30


def _device_label(device_spec) -> str:
    ua = device_spec.user_agent or ""
    return ua[:80] if ua else "Unknown device"


def _debug_payload(breakdown, device_res, ip, city, country) -> dict:
    """DEBUG-mode payload returned in /login responses so tooling (the attack
    simulator, integration tests) can see per-signal scores without scraping
    server logs. Never enable in production."""
    return {
        "ip": ip,
        "city": city,
        "country": country,
        "decision": breakdown.decision.value,
        "final": round(breakdown.final, 3),
        "rule_based": round(breakdown.rule_based, 3),
        "ml": round(breakdown.ml, 3),
        "signals": {
            "velocity": round(breakdown.velocity, 3),
            "geo": round(breakdown.geo, 3),
            "device": round(breakdown.device, 3),
            "behavioral": round(breakdown.behavioral, 3),
        },
        "device": {
            "is_known": device_res.is_known_device,
            "is_similar": device_res.is_similar_device,
            "is_trusted": device_res.is_trusted_device,
            "headless_score": round(device_res.headless_score, 3),
        },
    }


def _generic_invalid_credentials() -> HTTPException:
    """Single 401 used for: wrong password, locked account, unknown-device MFA
    request. Identical shape so an attacker can't distinguish."""
    return HTTPException(
        status_code=401,
        detail={"code": "invalid_credentials", "message": "Invalid credentials"},
    )


def _publish_login_event(
    db: DbSession,
    redis: Redis,
    event: LoginEvent,
    user_email: str | None = None,
    extra: dict | None = None,
) -> None:
    """Fire-and-forget publish to the admin dashboard SSE channel.

    Caller must have already committed the event. We refresh to populate
    server-side defaults (id, created_at) before serializing.
    """
    try:
        db.refresh(event)
    except Exception:
        pass
    payload = dashboard.event_payload(event, user_email=user_email, extra=extra)
    asyncio.create_task(dashboard.publish_event(redis, payload))


async def _send_register_otp_bg(email: str, name: str, otp: str) -> None:
    try:
        await notifications.send_register_otp(email, name, otp)
    except Exception:
        logger.exception("register OTP send failed")


async def _send_mfa_otp_bg(email: str, name: str, otp: str) -> None:
    try:
        await notifications.send_mfa_otp(email, name, otp)
    except Exception:
        logger.exception("MFA OTP send failed")


# ─────────────────────────────────────────────────────────────────────────────
# REGISTER
# ─────────────────────────────────────────────────────────────────────────────

async def register_flow(
    request: Request,
    register_request: RegisterRequest,
    db: DbSession,
    redis: Redis,
) -> dict:
    email = register_request.credentials.email
    existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if existing and existing.is_active:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Reuse the row if a previous registration didn't complete verification
    if existing:
        existing.hashed_password = hash_password(register_request.credentials.password)
        existing.full_name = register_request.credentials.full_name
        user = existing
    else:
        user = User(
            uuid=uuid_lib.uuid4(),
            email=email,
            hashed_password=hash_password(register_request.credentials.password),
            full_name=register_request.credentials.full_name,
            is_active=False,
            is_verified=False,
        )
        db.add(user)
    db.commit()

    otp = await otp_svc.issue_otp(redis, purpose="register", subject=email)
    asyncio.create_task(_send_register_otp_bg(email, user.full_name or "", otp))

    return {
        "status": "otp_sent",
        "email": email,
        "expires_in": settings.OTP_TTL_SECONDS,
    }


async def register_verify_flow(
    request: Request,
    response: Response,
    payload: RegisterVerifyRequest,
    db: DbSession,
    redis: Redis,
) -> dict:
    ok, reason = await otp_svc.verify_otp(redis, "register", payload.email, payload.otp)
    if not ok:
        raise HTTPException(status_code=400, detail=f"OTP {reason}")

    user = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = True
    user.is_verified = True
    db.commit()

    ip = get_client_ip(request)
    ua = request.headers.get("user-agent", "")
    _, access, refresh = session_svc.create_session(db, user, device_id=None, ip=ip, user_agent=ua)
    db.commit()
    session_svc.set_auth_cookies(response, access, refresh)

    return {
        "status": "ok",
        "uuid": str(user.uuid),
        "email": user.email,
        "full_name": user.full_name,
    }


# ─────────────────────────────────────────────────────────────────────────────
# LOGIN
# ─────────────────────────────────────────────────────────────────────────────

async def login_flow(
    request: Request,
    response: Response,
    login_request: LoginRequest,
    db: DbSession,
    redis: Redis,
) -> dict:
    email = login_request.credentials.email
    password = login_request.credentials.password
    ip = get_client_ip(request)

    # ── Pre-user-lookup velocity (catches credential-stuffers hammering one IP) ──
    pre_velocity = await check_velocity(user_id=None, ip=ip, redis=redis)
    if pre_velocity.ip_risk > 0.8:
        raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")

    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()

    # Timing-side-channel protection: always run verify_password against SOMETHING.
    real_password_ok = verify_password(
        password,
        user.hashed_password if user else _DUMMY_PASSWORD_HASH,
    )

    if user is None:
        await record_attempt(user_id=None, ip=ip, redis=redis)
        raise _generic_invalid_credentials()

    # ── Temporal lock: any /login during the lock window is rejected.
    #    Demo posture: we surface the lock state + countdown so the user knows
    #    to switch to email verification. Trade-off: leaks account existence.
    if lockout.is_locked(user):
        await record_attempt(user.id, ip, redis)
        ev = LoginEvent(
            user_id=user.id, ip_address=ip,
            outcome=LoginOutcome.blocked_velocity,
            device_fingerprint=login_request.device_spec.device_fingerprint,
            decision="locked",
            breakdown={
                "reasons": ["bruteforce_lockout"],
                "lock_level": user.lock_level,
                "locked_until": user.locked_until.isoformat() if user.locked_until else None,
            },
        )
        db.add(ev)
        db.commit()
        _publish_login_event(db, redis, ev, user_email=user.email)
        raise HTTPException(status_code=401, detail={
            "code": "account_locked",
            "message": "Account temporarily locked due to repeated failures.",
            "locked_until": user.locked_until.isoformat() if user.locked_until else None,
            "seconds_remaining": lockout.seconds_remaining(user),
            "lock_level": user.lock_level,
            "unlock_via_email": True,
        })

    if not user.is_verified:
        await record_attempt(user.id, ip, redis)
        raise HTTPException(status_code=403, detail="Email not verified")

    if not user.is_active:
        await record_attempt(user.id, ip, redis)
        if lockout.is_hard_blocked(user):
            raise HTTPException(status_code=403, detail={
                "code": "account_blocked",
                "message": "Account permanently blocked due to repeated abuse. Contact support to restore access.",
                "lock_level": user.lock_level,
            })
        raise HTTPException(status_code=403, detail="Account disabled")

    # Per-user / per-(user,ip) velocity check
    vel_res = await check_velocity(user_id=user.id, ip=ip, redis=redis)
    if vel_res.flagged:
        ev = LoginEvent(
            user_id=user.id, ip_address=ip,
            outcome=LoginOutcome.blocked_velocity,
            device_fingerprint=login_request.device_spec.device_fingerprint,
            risk_score=1.0,
            decision="rate_limited",
            breakdown={
                "reasons": ["velocity_spike"],
                "velocity": round(max(vel_res.user_risk, vel_res.ip_risk, vel_res.user_ip_risk), 4),
            },
        )
        db.add(ev)
        db.commit()
        _publish_login_event(db, redis, ev, user_email=user.email)
        raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")

    # Run behavioral bot check AFTER user is confirmed (so a stuck JS sensor on
    # a legit user produces a clean 401 instead of leaking "this account exists").
    profile = get_profile(db, user.id)
    behavioral = check_behavioral(login_request.behavioral_signals, profile=profile)

    if not real_password_ok:
        await record_attempt(user_id=user.id, ip=ip, redis=redis)
        lock_applied = lockout.register_failure(db, user)
        is_hard = lockout.is_hard_blocked(user)
        ev = LoginEvent(
            user_id=user.id, ip_address=ip,
            outcome=LoginOutcome.failed_credentials,
            device_fingerprint=login_request.device_spec.device_fingerprint,
            decision=("hard_block" if is_hard else ("locked" if lock_applied else "failed")),
            breakdown={
                "reasons": (
                    ["hard_block"] if is_hard
                    else ["bruteforce_lockout"] if lock_applied
                    else ["invalid_credentials"]
                ),
                "lock_level": user.lock_level,
                "failed_login_count": user.failed_login_count,
            },
        )
        db.add(ev)
        db.commit()
        _publish_login_event(db, redis, ev, user_email=user.email)

        if lock_applied:
            logger.info(
                "account locked user=%s level=%d until=%s",
                user.email, user.lock_level, user.locked_until,
            )

        delay = _progressive_delay(user.failed_login_count)
        if delay:
            await asyncio.sleep(delay)
        # Hard block just engaged → distinct 403, no temporal countdown.
        if lock_applied and lockout.is_hard_blocked(user):
            raise HTTPException(status_code=403, detail={
                "code": "account_blocked",
                "message": "Account permanently blocked due to repeated abuse. Contact support to restore access.",
                "lock_level": user.lock_level,
            })
        # If this failure just triggered the lock, tell the client right away
        # (demo posture — see lock check above).
        if lock_applied and lockout.is_locked(user):
            raise HTTPException(status_code=401, detail={
                "code": "account_locked",
                "message": "Account temporarily locked due to repeated failures.",
                "locked_until": user.locked_until.isoformat() if user.locked_until else None,
                "seconds_remaining": lockout.seconds_remaining(user),
                "lock_level": user.lock_level,
                "unlock_via_email": True,
            })
        bad_detail: dict = {"code": "invalid_credentials", "message": "Invalid credentials"}
        if settings.DEBUG:
            v = await check_velocity(user_id=user.id, ip=ip, redis=redis)
            bad_detail["debug"] = {
                "ip": ip,
                "decision": "invalid_credentials",
                "lock_active": lockout.is_locked(user),
                "lock_level": user.lock_level,
                "signals": {
                    "velocity": round(max(v.user_risk, v.ip_risk, v.user_ip_risk), 3),
                    "geo": 0.0, "device": 0.0, "behavioral": 0.0,
                },
                "velocity_counts": {
                    "user": v.user_count, "ip": v.ip_count, "user_ip": v.user_ip_count,
                },
                "failed_login_count": user.failed_login_count,
            }
        raise HTTPException(status_code=401, detail=bad_detail)

    # ── Password OK — run the full pipeline ─────────────────────────────────
    lockout.clear_lock(user)
    user.lock_level = 0  # password worked organically, decay back to baseline

    # Bot signals after correct password still matter: a bot that bought creds
    # off a dump should still trigger MFA.
    _, geo_res = await asyncio.gather(
        record_attempt(user_id=user.id, ip=ip, redis=redis),
        check_geo(user_id=user.id, ip=ip, redis=redis, store=False),
    )

    city = geo_res.current_location.city if geo_res.current_location else None
    country = geo_res.current_location.country if geo_res.current_location else None
    lat = geo_res.current_location.lat if geo_res.current_location else None
    lon = geo_res.current_location.lon if geo_res.current_location else None

    device_res = check_device(
        user_id=user.id,
        device=login_request.device_spec,
        session=login_request.session_metadata,
        db=db,
        ip=ip, city=city, country=country,
    )

    # ── ML scoring (best-effort, returns 0 if model unavailable) ──
    account_age_days = (
        datetime.now(timezone.utc) - user.created_at
    ).days if user.created_at else 0
    ml_features = ml_inference.build_feature_row(
        user_account_age_days=account_age_days,
        failed_login_count=user.failed_login_count or 0,
        velocity=vel_res, geo=geo_res, device=device_res, behavioral=behavioral,
    )
    ml_risk = ml_inference.score_login(ml_features)

    breakdown = build_breakdown(vel_res, geo_res, device_res, behavioral, ml_risk=ml_risk)
    logger.info(
        "login risk user=%s decision=%s final=%.3f rule=%.3f ml=%.3f bd=%s",
        user.email, breakdown.decision.value, breakdown.final,
        breakdown.rule_based, breakdown.ml,
        {"v": breakdown.velocity, "g": breakdown.geo, "d": breakdown.device, "b": breakdown.behavioral},
    )
    debug_payload = _debug_payload(breakdown, device_res, ip, city, country) if settings.DEBUG else None
    reasons = derive_reasons(breakdown, vel_res, geo_res, device_res, behavioral)
    breakdown_dict = breakdown.to_dict(reasons=reasons)
    # ── BLOCK ─────────────────────────────────────────────────────────────────
    if breakdown.decision is RiskDecision.BLOCK:
        event = LoginEvent(
            user_id=user.id, ip_address=ip, city=city, country=country,
            outcome=LoginOutcome.blocked_risk,
            device_fingerprint=login_request.device_spec.device_fingerprint,
            risk_score=breakdown.final,
            decision="block",
            breakdown=breakdown_dict,
        )
        db.add(event)
        db.commit()
        _publish_login_event(db, redis, event, user_email=user.email)

        yes_token = await mfa_svc.create_magic_link(redis, {
            "kind": "yes", "user_id": user.id, "device_id": device_res.device_id, "ip": ip,
        })
        no_token = await mfa_svc.create_magic_link(redis, {
            "kind": "no", "user_id": user.id,
        })
        notifications.notify_suspicious_login(
            email=user.email, name=user.full_name or "",
            ip=ip, city=city or "", country=country or "",
            device=_device_label(login_request.device_spec),
            yes_token=yes_token, no_token=no_token,
            lat=lat, lon=lon,
        )
        raise HTTPException(status_code=403, detail={
            "code": "blocked_high_risk",
            "message": "Sign-in blocked. Check your email to confirm it was you.",
            **({"debug": debug_payload} if debug_payload else {}),
        })

    # ── STEP-UP MFA ────────────────────────────────────────────────────────
    if breakdown.decision is RiskDecision.STEP_UP:
        ev = LoginEvent(
            user_id=user.id, ip_address=ip, city=city, country=country,
            outcome=LoginOutcome.mfa_required,
            device_fingerprint=login_request.device_spec.device_fingerprint,
            risk_score=breakdown.final,
            decision="step_up",
            breakdown=breakdown_dict,
        )
        db.add(ev)
        db.commit()
        _publish_login_event(db, redis, ev, user_email=user.email)

        challenge_id = await mfa_svc.create_challenge(redis, {
            "user_id": user.id,
            "device_id": device_res.device_id,
            "ip": ip,
            "user_agent": request.headers.get("user-agent", ""),
            "city": city, "country": country,
            "lat": lat, "lon": lon,
            "risk": breakdown.final,
            "device_fingerprint": login_request.device_spec.device_fingerprint,
            "device_label": _device_label(login_request.device_spec),
            "is_new_device": not device_res.is_known_device,
        })
        otp = await otp_svc.issue_otp(redis, purpose="mfa", subject=challenge_id)
        asyncio.create_task(_send_mfa_otp_bg(user.email, user.full_name or "", otp))

        return {
            "status": "mfa_required",
            "challenge_id": challenge_id,
            "expires_in": settings.OTP_TTL_SECONDS,
            "risk": breakdown.final,
            **({"debug": debug_payload} if debug_payload else {}),
        }

    # ── ALLOW ───────────────────────────────────────────────────────────────────────
    await _finalize_login(
        request=request, response=response, db=db, user=user,
        device_id=device_res.device_id,
        ip=ip, city=city, country=country, lat=lat, lon=lon,
        device_fingerprint=login_request.device_spec.device_fingerprint,
        device_label=_device_label(login_request.device_spec),
        is_new_device=not device_res.is_known_device,
        behavioral_signals=login_request.behavioral_signals,
        risk_score=breakdown.final,
        outcome=LoginOutcome.success,
        redis=redis,
        decision="allow",
        breakdown=breakdown_dict,
    )

    return {
        "status": "ok",
        "uuid": str(user.uuid),
        "email": user.email,
        "risk": breakdown.final,
        **({"debug": debug_payload} if debug_payload else {}),
    }


# ─────────────────────────────────────────────────────────────────────────────
# MFA REQUEST (unlock-during-temporal-lock)
# ─────────────────────────────────────────────────────────────────────────────

async def mfa_request_flow(
    request: Request,
    payload: MfaRequestRequest,
    db: DbSession,
    redis: Redis,
) -> dict:
    """Issue an MFA OTP outside the normal /login decision path.

    Only legitimate when:
      - email + password are correct
      - device fingerprint matches a known UserDevice for this user
        (exact or fuzzy via DEVICE_SIMILARITY_THRESHOLD)
      - the account is currently locked (otherwise the user should just /login)

    Any failure on any of the above → identical generic 401 so an attacker
    cannot probe lock state, device-recognition state, or account existence.
    """
    from app.detection.device import _find_or_match_device  # internal lookup

    email = payload.credentials.email
    password = payload.credentials.password
    ip = get_client_ip(request)

    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()

    # Constant-time password check (use dummy hash when user missing)
    real_password_ok = verify_password(
        password,
        user.hashed_password if user else _DUMMY_PASSWORD_HASH,
    )

    if user is None or not real_password_ok or not user.is_active:
        await record_attempt(user_id=user.id if user else None, ip=ip, redis=redis)
        raise _generic_invalid_credentials()

    if not lockout.is_locked(user):
        # Not locked → no legitimate reason to use this endpoint
        raise _generic_invalid_credentials()

    # Device must be known (exact or fuzzy match)
    row, sim, _is_exact = _find_or_match_device(db, user.id, payload.device_spec)
    if row is None:
        # Attacker on an unknown device: indistinguishable from wrong password.
        # Failed MFA-request attempts also count toward future lock escalation.
        lockout.register_failure(db, user)
        db.commit()
        raise _generic_invalid_credentials()

    challenge_id = await mfa_svc.create_challenge(redis, {
        "user_id": user.id,
        "device_id": row.id,
        "ip": ip,
        "user_agent": request.headers.get("user-agent", ""),
        "device_fingerprint": payload.device_spec.device_fingerprint,
        "device_label": _device_label(payload.device_spec),
        "is_new_device": False,
        "unlock": True,
    })
    otp = await otp_svc.issue_otp(redis, purpose="mfa", subject=challenge_id)
    asyncio.create_task(_send_mfa_otp_bg(user.email, user.full_name or "", otp))

    return {
        "status": "mfa_required",
        "challenge_id": challenge_id,
        "expires_in": settings.OTP_TTL_SECONDS,
    }


# ─────────────────────────────────────────────────────────────────────────────
# MFA VERIFY
# ─────────────────────────────────────────────────────────────────────────────

async def mfa_verify_flow(
    request: Request,
    response: Response,
    payload: MfaVerifyRequest,
    db: DbSession,
    redis: Redis,
) -> dict:
    challenge = await mfa_svc.load_challenge(redis, payload.challenge_id)
    if not challenge:
        raise HTTPException(status_code=400, detail="Challenge expired or invalid")

    ok, reason = await otp_svc.verify_otp(redis, "mfa", payload.challenge_id, payload.otp)
    if not ok:
        raise HTTPException(status_code=400, detail=f"OTP {reason}")

    await mfa_svc.consume_challenge(redis, payload.challenge_id)

    user = db.get(User, challenge["user_id"])
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")

    # If this challenge was minted by the unlock-flow, clear the lock now that
    # OTP succeeded on a known device. Risk engine is skipped — the user just
    # proved themselves via a strictly stronger factor.
    if challenge.get("unlock"):
        lockout.clear_lock(user)
        user.lock_level = 0

    device_id = challenge.get("device_id")
    if payload.remember_device and device_id:
        mark_device_trusted(db, device_id)

    # Build a minimal BehavioralSignals-shaped payload from the challenge? We
    # don't have it here — that's fine, baseline update happens only on full
    # login. MFA verify just promotes the session.

    ip = challenge.get("ip") or get_client_ip(request)
    city = challenge.get("city")
    country = challenge.get("country")

    # Record success event
    ev = LoginEvent(
        user_id=user.id, ip_address=ip, city=city, country=country,
        outcome=LoginOutcome.mfa_verified,
        device_fingerprint=challenge.get("device_fingerprint"),
        risk_score=challenge.get("risk"),
        decision="mfa_verified",
        breakdown={
            "reasons": ["unlock" if challenge.get("unlock") else "mfa_verified"],
            "risk": challenge.get("risk"),
        },
    )
    db.add(ev)
    user.last_login_at = datetime.now(timezone.utc)
    if device_id:
        increment_device_login(db, device_id)

    # Persist geo as last-known (now that we know it was really the user)
    await check_geo(user_id=user.id, ip=ip, redis=redis, store=True)

    _, access, refresh = session_svc.create_session(
        db, user, device_id=device_id, ip=ip,
        user_agent=challenge.get("user_agent"),
    )
    db.commit()
    _publish_login_event(db, redis, ev, user_email=user.email)
    session_svc.set_auth_cookies(response, access, refresh)

    if challenge.get("is_new_device"):
        wasnt_me = await mfa_svc.create_magic_link(redis, {
            "kind": "no", "user_id": user.id,
        })
        notifications.notify_new_device(
            email=user.email, name=user.full_name or "",
            ip=ip, city=city or "", country=country or "",
            device=challenge.get("device_label", "Unknown"),
            wasnt_me_token=wasnt_me,
            lat=challenge.get("lat"), lon=challenge.get("lon"),
        )

    return {
        "status": "ok",
        "uuid": str(user.uuid),
        "email": user.email,
        "device_trusted": bool(payload.remember_device and device_id),
    }


# ─────────────────────────────────────────────────────────────────────────────
# MAGIC LINKS (was it you? / no it wasn't)
# ─────────────────────────────────────────────────────────────────────────────

async def confirm_was_me_flow(token: str, db: DbSession, redis: Redis) -> dict:
    payload = await mfa_svc.consume_magic_link(redis, token)
    if not payload or payload.get("kind") != "yes":
        raise HTTPException(status_code=400, detail="Invalid or expired link")

    device_id = payload.get("device_id")
    if device_id:
        mark_device_trusted(db, device_id)
        db.commit()
    return {"status": "ok", "message": "Thanks — this device is now trusted."}


async def deny_was_me_flow(token: str, db: DbSession, redis: Redis) -> dict:
    payload = await mfa_svc.consume_magic_link(redis, token)
    if not payload or payload.get("kind") != "no":
        raise HTTPException(status_code=400, detail="Invalid or expired link")

    user_id = payload["user_id"]
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    revoke_all_device_trust(db, user_id)
    revoked = session_svc.revoke_all_user_sessions(db, user_id)
    db.commit()

    return {
        "status": "ok",
        "message": "All sessions revoked. Please reset your password.",
        "sessions_revoked": revoked,
    }


# ─────────────────────────────────────────────────────────────────────────────
# REFRESH / LOGOUT
# ─────────────────────────────────────────────────────────────────────────────

async def refresh_flow(
    request: Request, response: Response, db: DbSession,
) -> dict:
    refresh = request.cookies.get("refresh_token")
    if not refresh:
        raise HTTPException(status_code=401, detail="Missing refresh token")

    s = session_svc.find_session_by_refresh(db, refresh)
    if not session_svc.is_session_valid(s):
        raise HTTPException(status_code=401, detail="Session expired")

    new_refresh = session_svc.rotate_session(db, s)
    db.commit()

    from app.core.security import create_access_token
    user = db.get(User, s.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User inactive")
    access = create_access_token(str(user.uuid), sid=s.id)
    session_svc.set_auth_cookies(response, access, new_refresh)
    return {"status": "ok"}


async def logout_flow(request: Request, response: Response, db: DbSession) -> dict:
    refresh = request.cookies.get("refresh_token")
    if refresh:
        s = session_svc.find_session_by_refresh(db, refresh)
        if s:
            session_svc.revoke_session(db, s)
            db.commit()
    session_svc.clear_auth_cookies(response)
    return {"status": "ok"}


# ─────────────────────────────────────────────────────────────────────────────
# Internal: finalize a successful (no-MFA) login
# ─────────────────────────────────────────────────────────────────────────────

async def _finalize_login(
    *, request: Request, response: Response, db: DbSession, user: User,
    device_id: int | None, ip: str, city: str | None, country: str | None,
    lat: float | None, lon: float | None,
    device_fingerprint: str, device_label: str, is_new_device: bool,
    behavioral_signals, risk_score: float, outcome: LoginOutcome, redis: Redis,
    decision: str | None = None, breakdown: dict | None = None,
) -> None:
    user.last_login_at = datetime.now(timezone.utc)
    ev = LoginEvent(
        user_id=user.id, ip_address=ip, city=city, country=country,
        outcome=outcome, device_fingerprint=device_fingerprint,
        risk_score=risk_score,
        decision=decision,
        breakdown=breakdown,
    )
    db.add(ev)
    if device_id:
        increment_device_login(db, device_id)
    update_baseline(db, user.id, behavioral_signals, ip=ip)
    await check_geo(user_id=user.id, ip=ip, redis=redis, store=True)

    _, access, refresh = session_svc.create_session(
        db, user, device_id=device_id, ip=ip,
        user_agent=request.headers.get("user-agent", ""),
    )
    db.commit()
    _publish_login_event(db, redis, ev, user_email=user.email)
    session_svc.set_auth_cookies(response, access, refresh)

    if is_new_device:
        wasnt_me = await mfa_svc.create_magic_link(redis, {
            "kind": "no", "user_id": user.id,
        })
        notifications.notify_new_device(
            email=user.email, name=user.full_name or "",
            ip=ip, city=city or "", country=country or "",
            device=device_label, wasnt_me_token=wasnt_me,
            lat=lat, lon=lon,
        )