"""Temporal account-lock state machine.

Triggered by repeated password / MFA failures. While locked, /login always
rejects with a generic "invalid credentials" 401 (no info leak). A legit user
on a known device can still unlock via /auth/mfa/request → /auth/mfa/verify.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import User


def is_locked(user: User) -> bool:
    if user.locked_until is None:
        return False
    return user.locked_until > datetime.now(timezone.utc)


def is_hard_blocked(user: User) -> bool:
    """Permanent block: account auto-disabled after exhausting all temporal
    lock tiers. Requires admin reset (manual re-enable of is_active)."""
    return (not user.is_active) and (user.lock_level or 0) > len(
        settings.LOCK_DURATIONS_MINUTES
    )


def seconds_remaining(user: User) -> int:
    if not is_locked(user):
        return 0
    return int((user.locked_until - datetime.now(timezone.utc)).total_seconds())


def register_failure(db: Session, user: User) -> bool:
    """Increment failed_login_count. If it crosses the threshold, escalate the
    lock level and stamp locked_until. Once the user has already exhausted the
    last temporal tier, the next escalation flips is_active=False (permanent
    hard block). Returns True if a lock was just applied."""
    user.failed_login_count = (user.failed_login_count or 0) + 1
    if user.failed_login_count < settings.LOCK_FAIL_THRESHOLD:
        return False

    durations = settings.LOCK_DURATIONS_MINUTES
    current = user.lock_level or 0

    if current >= len(durations):
        # Exhausted all temporal tiers → permanent block.
        user.is_active = False
        user.lock_level = current + 1
        user.locked_until = None
        user.failed_login_count = 0
        return True

    level = current + 1
    minutes = durations[level - 1]
    user.lock_level = level
    user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    user.failed_login_count = 0
    return True


def clear_lock(user: User) -> None:
    """Called after a successful authentication of any kind. Resets failure
    counter and the active lock window but keeps lock_level so the next abuse
    burst escalates faster (until a long quiet period — left for future)."""
    user.failed_login_count = 0
    user.locked_until = None
