from fastapi import Depends, HTTPException, Cookie, Request

from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from redis.asyncio import Redis

from app.db.session import SessionLocal
from app.core.security import decode_token
from app.db.models import User, Session as SessionModel, UserRole
from app.core.config import settings

_redis_client: Redis | None = None


def get_redis_client() -> Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD or None,
            ssl=settings.REDIS_USE_SSL,
            decode_responses=True,
        )
    return _redis_client


async def close_redis() -> None:
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None


async def get_redis():
    yield get_redis_client()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_client_ip(request: Request) -> str:
    # NOTE: X-Forwarded-For is honored unconditionally. Safe only when the app
    # actually sits behind a trusted reverse proxy that overwrites this header.
    # Direct exposure to the internet would let clients spoof their IP.
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "0.0.0.0"


def is_authenticated(
    access_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
):
    if not access_token:
        raise HTTPException(status_code=401, detail="Missing access token")

    payload = decode_token(access_token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token")

    # Bind the JWT to a server-side session row so revocation actually works.
    # Without this, a revoked session's JWT keeps passing until it expires.
    sid = payload.get("sid")
    if sid is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    session_row = db.get(SessionModel, sid)
    if (
        session_row is None
        or session_row.revoked_at is not None
        or session_row.expires_at <= datetime.now(timezone.utc)
    ):
        raise HTTPException(status_code=401, detail="Session no longer valid")

    return payload


def get_current_user(
    payload: dict = Depends(is_authenticated),
    db: Session = Depends(get_db),
) -> User:
    stmt = select(User).where(User.uuid == payload.get("sub"))
    user = db.execute(stmt).scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user