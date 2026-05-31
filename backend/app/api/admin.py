"""Admin dashboard API.

All routes require an authenticated user with role=admin (see require_admin).
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid as uuid_lib
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.deps import get_db, get_redis, require_admin
from app.db.models import LoginEvent, Session as SessionModel, User
from app.services import dashboard, sessions as session_svc
from scripts.attack_simulator import SCENARIOS as ATTACK_SCENARIOS, SCENARIO_META

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stream")
async def stream(
    request: Request,
    _admin: User = Depends(require_admin),
    redis: Redis = Depends(get_redis),
) -> StreamingResponse:
    """Server-Sent Events feed of login pipeline outcomes."""

    async def event_generator():
        # Initial hello so the client knows the channel is live.
        yield "event: hello\ndata: {}\n\n"

        sub_iter = dashboard.subscribe(redis).__aiter__()
        keepalive_interval = 15.0

        try:
            while True:
                if await request.is_disconnected():
                    break

                # Wait for either a new event or the keepalive timeout.
                next_task = asyncio.create_task(sub_iter.__anext__())
                try:
                    payload = await asyncio.wait_for(next_task, timeout=keepalive_interval)
                    yield f"event: login_event\ndata: {json.dumps(payload, default=str)}\n\n"
                except asyncio.TimeoutError:
                    next_task.cancel()
                    # SSE comment line keeps proxies from closing the socket.
                    yield ": keepalive\n\n"
                except StopAsyncIteration:
                    break
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("admin stream error")
        finally:
            try:
                await sub_iter.aclose()  # type: ignore[attr-defined]
            except Exception:
                pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",  # nginx: disable response buffering
            "Connection": "keep-alive",
        },
    )


_WINDOWS = {
    "1h": timedelta(hours=1),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}


def _row_to_payload(event: LoginEvent, user_email: str | None, user_uuid: str | None = None) -> dict:
    return dashboard.event_payload(event, user_email=user_email, user_uuid=user_uuid)


@router.get("/stats")
def stats(
    window: str = Query("24h", pattern="^(1h|24h|7d|30d)$"),
    _admin: User = Depends(require_admin),
    db: DbSession = Depends(get_db),
) -> dict:
    """Aggregate counts grouped by outcome and decision within the window."""
    since = datetime.now(timezone.utc) - _WINDOWS[window]

    total = db.scalar(
        select(func.count(LoginEvent.id)).where(LoginEvent.created_at >= since)
    ) or 0

    by_outcome_rows = db.execute(
        select(LoginEvent.outcome, func.count(LoginEvent.id))
        .where(LoginEvent.created_at >= since)
        .group_by(LoginEvent.outcome)
    ).all()
    by_outcome = {(o.value if o else "unknown"): n for o, n in by_outcome_rows}

    by_decision_rows = db.execute(
        select(LoginEvent.decision, func.count(LoginEvent.id))
        .where(LoginEvent.created_at >= since)
        .group_by(LoginEvent.decision)
    ).all()
    by_decision = {(d or "unknown"): n for d, n in by_decision_rows}

    unique_users = db.scalar(
        select(func.count(func.distinct(LoginEvent.user_id)))
        .where(LoginEvent.created_at >= since, LoginEvent.user_id.is_not(None))
    ) or 0
    unique_ips = db.scalar(
        select(func.count(func.distinct(LoginEvent.ip_address)))
        .where(LoginEvent.created_at >= since)
    ) or 0

    return {
        "window": window,
        "since": since.isoformat(),
        "total": total,
        "unique_users": unique_users,
        "unique_ips": unique_ips,
        "by_outcome": by_outcome,
        "by_decision": by_decision,
    }


@router.get("/events")
def list_events(
    limit: int = Query(50, ge=1, le=200),
    before_id: int | None = Query(None, ge=1),
    since_id: int | None = Query(None, ge=1),
    decision: str | None = Query(None),
    outcome: str | None = Query(None),
    user_id: int | None = Query(None, ge=1),
    _admin: User = Depends(require_admin),
    db: DbSession = Depends(get_db),
) -> dict:
    """Paginated event history.

    - `before_id` is used for reverse-chronological paging (older events).
    - `since_id` is used by SSE clients to backfill events missed during a
      reconnect; returns events strictly newer than `since_id` in ascending
      order.
    """
    stmt = select(LoginEvent, User.email, User.uuid).join(
        User, User.id == LoginEvent.user_id, isouter=True
    )
    if before_id is not None:
        stmt = stmt.where(LoginEvent.id < before_id)
    if since_id is not None:
        stmt = stmt.where(LoginEvent.id > since_id)
    if decision:
        stmt = stmt.where(LoginEvent.decision == decision)
    if outcome:
        stmt = stmt.where(LoginEvent.outcome == outcome)
    if user_id is not None:
        stmt = stmt.where(LoginEvent.user_id == user_id)

    order = LoginEvent.id.asc() if since_id is not None else LoginEvent.id.desc()
    stmt = stmt.order_by(order).limit(limit)

    rows = db.execute(stmt).all()
    items = [_row_to_payload(ev, email, str(uuid) if uuid else None) for ev, email, uuid in rows]
    next_before_id = items[-1]["id"] if (since_id is None and items) else None

    return {
        "items": items,
        "count": len(items),
        "next_before_id": next_before_id,
    }


@router.get("/events/{event_id}")
def get_event(
    event_id: int,
    _admin: User = Depends(require_admin),
    db: DbSession = Depends(get_db),
) -> dict:
    row = db.execute(
        select(LoginEvent, User.email, User.uuid)
        .join(User, User.id == LoginEvent.user_id, isouter=True)
        .where(LoginEvent.id == event_id)
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="event not found")
    ev, email, uuid = row
    return _row_to_payload(ev, email, str(uuid) if uuid else None)


@router.post("/users/{user_uuid}/unlock")
def unlock_user(
    user_uuid: uuid_lib.UUID,
    _admin: User = Depends(require_admin),
    db: DbSession = Depends(get_db),
) -> dict:
    """Fully clear the user's lockout state (temporal + hard block)."""
    user = db.execute(select(User).where(User.uuid == user_uuid)).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")

    user.failed_login_count = 0
    user.locked_until = None
    user.lock_level = 0
    user.is_active = True
    db.commit()
    db.refresh(user)
    return {
        "uuid": str(user.uuid),
        "email": user.email,
        "is_active": user.is_active,
        "lock_level": user.lock_level,
        "locked_until": None,
        "failed_login_count": user.failed_login_count,
    }


@router.post("/sessions/{session_id}/revoke")
def revoke_session(
    session_id: int,
    _admin: User = Depends(require_admin),
    db: DbSession = Depends(get_db),
) -> dict:
    s = db.get(SessionModel, session_id)
    if s is None:
        raise HTTPException(status_code=404, detail="session not found")
    if s.revoked_at is not None:
        return {"id": s.id, "revoked_at": s.revoked_at.isoformat(), "already_revoked": True}
    session_svc.revoke_session(db, s)
    db.commit()
    return {
        "id": s.id,
        "user_id": s.user_id,
        "revoked_at": s.revoked_at.isoformat() if s.revoked_at else None,
        "already_revoked": False,
    }


@router.post("/users/{user_uuid}/sessions/revoke")
def revoke_all_user_sessions(
    user_uuid: uuid_lib.UUID,
    _admin: User = Depends(require_admin),
    db: DbSession = Depends(get_db),
) -> dict:
    user = db.execute(select(User).where(User.uuid == user_uuid)).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    count = session_svc.revoke_all_user_sessions(db, user.id)
    db.commit()
    return {"uuid": str(user.uuid), "revoked_count": count}


@router.get("/scenarios")
def list_scenarios(_admin: User = Depends(require_admin)) -> dict:
    """Return available attack scenarios with metadata for the demo UI."""
    scenarios = []
    for key in ATTACK_SCENARIOS:
        meta = SCENARIO_META.get(key, {})
        scenarios.append({
            "key": key,
            "label": meta.get("label", key),
            "icon": meta.get("icon", "⚡"),
            "description": meta.get("description", ""),
            "expected": meta.get("expected", []),
            "tier": meta.get("tier", "—"),
        })
    return {"scenarios": scenarios}


@router.post("/simulate/{scenario}")
async def simulate_attack(
    scenario: str,
    request: Request,
    _admin: User = Depends(require_admin),
) -> dict:
    """Trigger an attack_simulator scenario against this backend.

    Body: {"email": "...", "password": "..."} — a verified test user.
    Runs the scenario in a background thread; events flow through the normal
    pipeline and appear in the SSE feed.
    """
    if scenario not in ATTACK_SCENARIOS:
        raise HTTPException(status_code=404, detail=f"unknown scenario: {scenario}")

    body = await request.json()
    email = body.get("email")
    password = body.get("password")
    if not email or not password:
        raise HTTPException(status_code=400, detail="email and password required")

    base_url = f"{request.url.scheme}://{request.url.netloc}/api"
    fn = ATTACK_SCENARIOS[scenario]

    asyncio.create_task(asyncio.to_thread(fn, base_url, email, password))
    return {"status": "started", "scenario": scenario}

