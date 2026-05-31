"""Dashboard pub/sub for real-time admin SSE feed.

Publish events on `dashboard:login_events` after each login-pipeline outcome.
Subscribers (the SSE endpoint) read from the same channel and forward as
Server-Sent Events to admin browsers.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator

from redis.asyncio import Redis

from app.db.models import LoginEvent

logger = logging.getLogger(__name__)

CHANNEL = "dashboard:login_events"


def event_payload(
    event: LoginEvent,
    *,
    user_email: str | None = None,
    user_uuid: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Shape a LoginEvent row into the JSON payload the dashboard consumes."""
    payload: dict[str, Any] = {
        "id": event.id,
        "created_at": event.created_at.isoformat() if event.created_at else None,
        "user_id": event.user_id,
        "user_email": user_email,
        "user_uuid": user_uuid,
        "ip": event.ip_address,
        "city": event.city,
        "country": event.country,
        "device_fingerprint": event.device_fingerprint,
        "outcome": event.outcome.value if event.outcome else None,
        "decision": event.decision,
        "risk_score": event.risk_score,
        "breakdown": event.breakdown,
    }
    if extra:
        payload.update(extra)
    return payload


async def publish_event(redis: Redis, payload: dict[str, Any]) -> None:
    """Fire-and-forget publish. Swallows errors so the login path never breaks
    because the dashboard is unhappy."""
    try:
        await redis.publish(CHANNEL, json.dumps(payload, default=str))
    except Exception:
        logger.exception("dashboard publish failed")


def publish_in_background(redis: Redis, payload: dict[str, Any]) -> None:
    """Schedule publish_event without awaiting (use from sync code paths)."""
    asyncio.create_task(publish_event(redis, payload))


async def subscribe(redis: Redis) -> AsyncIterator[dict[str, Any]]:
    """Yield decoded JSON payloads from the dashboard channel until cancelled.

    Caller is responsible for cancellation (e.g. when the SSE client
    disconnects).
    """
    pubsub = redis.pubsub()
    await pubsub.subscribe(CHANNEL)
    try:
        async for message in pubsub.listen():
            if message is None or message.get("type") != "message":
                continue
            raw = message.get("data")
            if not raw:
                continue
            try:
                yield json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("dashboard: dropped malformed payload")
    finally:
        try:
            await pubsub.unsubscribe(CHANNEL)
        except Exception:
            pass
        try:
            await pubsub.aclose()
        except Exception:
            pass
