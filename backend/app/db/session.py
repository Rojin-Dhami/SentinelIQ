"""
app/db/session.py — async session dependency for FastAPI routes.
"""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import AsyncSessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency — yields a fresh DB session per request,
    commits on success, rolls back on error, always closes.
    Multiple developers / requests hit the pool concurrently — safe.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()