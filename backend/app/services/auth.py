import uuid
from datetime import datetime, timezone
import asyncio
import logging
from redis.asyncio import Redis
from fastapi import Request, Response, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select   

from app.core.config import settings
from app.schemas.auth import LoginRequest, RegisterRequest
from app.schemas.dto import EmailSchema
from app.db.models import User, LoginEvent
from app.services.email import send_email
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token

from app.detection.velocity import check_velocity, record_attempt
from app.detection.geo import check_geo
from app.detection.device import check_device
from app.detection.behavioral import check_behavioral
from app.detection.aggregate import compute_rule_based_risk, compute_final_risk


logger = logging.getLogger(__name__)

def _issue_tokens(user: User) -> dict:
    subject = str(user.uuid)
    return {
        "access_token": create_access_token(subject),
        "refresh_token": create_refresh_token(subject),
        "token_type": "bearer"
    }

def _set_auth_cookies(response: Response, access_token: str, refresh_token: str):
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=settings.REFRESH_TOKEN_EXPIRE_MINUTES * 60,
        path="/auth/refresh",
    )


# def get_lockout_response(failed_count: int) -> tuple[int, str] | None:
#     """Returns (delay_seconds, message) or None if no lockout."""
#     if failed_count < 3:
#         return None                          # no friction
#     if failed_count < 5:
#         return (5, "Too many attempts, wait 5 seconds")
#     if failed_count < 10:
#         return (30, "Too many attempts, wait 30 seconds")
#     return (300, "Account temporarily restricted")


def _progressive_delay(failed_count: int) -> int:
    """Returns seconds to sleep before responding. Slows brute force."""
    if failed_count < 3:
        return 0
    if failed_count < 5:
        return 3
    if failed_count < 10:
        return 10
    return 30

async def _send_security_alert(email: str, subject:str, template_name:str, ip: str, attempt_count: int) -> None:
    context = {"ip": ip, "attempt_count": attempt_count}
    email_schema = EmailSchema(to_email=email, subject=subject, template_name=template_name, template_params=context)
    result = await send_email(
        email_schema
    )

async def auth_flow(
    request: Request,
    response: Response,
    login_request: LoginRequest,
    db: AsyncSession,
    redis: Redis
):
    email = login_request.credentials.email
    password = login_request.credentials.password
    ip = request.client.host

    behavioral = check_behavioral(login_request.behavioral_signals) 
    if behavioral.is_likely_bot:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user = (
        db.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()
 
    if user is None:
        await record_attempt(user_id=None, ip=ip, redis=redis)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.is_active:
        await record_attempt(user.id, ip, redis)
        raise HTTPException(status_code=403, detail="Account disabled")

    vel_res = await check_velocity(user_id=user.id, ip=ip, redis=redis)
 
    if vel_res.flagged:
        db.add(LoginEvent(
            user_id=user.id,
            ip_address=ip,
            outcome="blocked_velocity",
            device_fingerprint=login_request.device_spec.device_fingerprint,
            risk_score=1.0,
        ))
        db.commit()
        raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")

    
    if not verify_password(password, user.hashed_password):
        await record_attempt(user_id=user.id, ip=ip, redis=redis)

        user.failed_login_count += 1
 
        # notify user on threshold — don't lock them out
        if user.failed_login_count == 5:
            # asyncio.create_task(
            #     _send_security_alert(user.email, ip, user.failed_login_count)
            # )
            logger.debug("Sending security alert to %s: failed_count:%s", user.email, user.failed_login_count)
            
 
        db.add(LoginEvent(
            user_id=user.id,
            ip_address=ip,
            outcome="failed_credentials",
            device_fingerprint=login_request.device_spec.device_fingerprint,
        ))
        db.commit()
 
        # progressive delay — return wait time without server-side sleep
        delay = _progressive_delay(user.failed_login_count)

        raise HTTPException(
            status_code=401,
            detail={
                "message": "Invalid credentials",
                "delay_seconds": delay,
                "failed_count": user.failed_login_count,
            },
        )

    # ── 5. Correct password — run full signal pipeline ────────────────────────
    user.failed_login_count = 0  # reset on success
    _, geo_res, device_res = await asyncio.gather(
        record_attempt(user_id=user.id, ip=ip, redis=redis),
        check_geo(user_id=user.id, ip=ip, redis=redis),
        check_device(
            user_id=user.id,
            device=login_request.device_spec,
            session=login_request.session_metadata,
            db=db,
        ),
    )

    rule_based_risk = compute_rule_based_risk(vel_res, geo_res, device_res, behavioral)
    final_risk = compute_final_risk(rule_based_risk)
    logger.debug("final risk: %s", final_risk)
    # ── Suspicious
    # 7.1
    # MFA/Block (send email)
    

    # ── Request found to be genuine
    # ── 7.2 Update user state + persist event ──
    user.last_login_at = datetime.now(timezone.utc)
    db.add(LoginEvent(
        user_id=user.id,
        ip_address=ip,
        outcome="success",
        device_fingerprint=login_request.device_spec.device_fingerprint,
        risk_score=final_risk,
    ))
    db.commit()

    tokens = _issue_tokens(user)
    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")
    # _set_auth_cookies(response, access_token, refresh_token)

    return {"message": "Login successful"}


async def register_flow(response: Response, register_request: RegisterRequest, db: AsyncSession, redis: Redis):
    email = register_request.credentials.email
    user = db.query(User).filter(User.email == email).first()
    if user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user = User(
        uuid=uuid.uuid4(),
        email=email,
        hashed_password=hash_password(register_request.credentials.password),
        full_name=register_request.credentials.full_name,
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    tokens = _issue_tokens(user)    
    _set_auth_cookies(response, tokens.get("access_token", ""), tokens.get("refresh_token"))
    
    return {"success": True, "uuid": user.uuid, "email": user.email, "full_name": user.full_name, "is_active": True}