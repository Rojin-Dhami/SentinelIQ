"""Wipe geo+velocity Redis keys for a given email so attack scenarios start clean."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.db.models import User
from app.db.session import SessionLocal
from app.deps import close_redis, get_redis_client


async def main(email: str) -> None:
    db = SessionLocal()
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None:
        print(f"no user for {email}")
        return
    redis = get_redis_client()
    keys: list[str] = []
    async for key in redis.scan_iter(f"geo:*:{user.id}"):
        keys.append(key)
    async for key in redis.scan_iter("velocity:*"):
        keys.append(key)
    if keys:
        await redis.delete(*keys)
    print(f"cleared {len(keys)} keys for user_id={user.id}")
    await close_redis()


if __name__ == "__main__":
    email = sys.argv[1] if len(sys.argv) > 1 else "4rwkvfk41h@bltiwd.com"
    asyncio.run(main(email))
