"""Promote an existing user to admin role.

Usage:
    uv run python scripts/make_admin.py <email>

Also resets is_active=True and clears any lockout state so a demo-blocked
admin can sign back in.
"""
from __future__ import annotations

import sys

from sqlalchemy import select

from app.db.models import User, UserRole
from app.db.session import SessionLocal


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: make_admin.py <email>", file=sys.stderr)
        return 2

    email = sys.argv[1].strip().lower()
    with SessionLocal() as db:
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is None:
            print(f"no user found with email={email}", file=sys.stderr)
            return 1

        user.role = UserRole.admin
        user.is_active = True
        user.is_verified = True
        user.lock_level = 0
        user.locked_until = None
        user.failed_login_count = 0
        db.commit()

        print(
            f"OK: {user.email} (uuid={user.uuid}) is now admin, "
            f"is_active=True, locks cleared."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
