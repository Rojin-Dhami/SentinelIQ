"""
Async PostgreSQL engine with connection pooling.
All developers share the same DB — pool handles concurrent connections safely.
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

# Shared engine — pool_size controls max simultaneous connections per process
is_sqlite = settings.DATABASE_URL.startswith("sqlite")
engine_options = {
    "echo": False,                       # set True for SQL debug logs
    "pool_pre_ping": True,               # drop stale connections automatically
    "pool_recycle": 1800,                # recycle connections every 30 min
}
if not is_sqlite:
    engine_options["pool_size"] = 10     # connections kept open per worker
    engine_options["max_overflow"] = 20  # extra connections allowed under load

engine = create_async_engine(
    settings.DATABASE_URL,
    **engine_options
)

# Session factory — each request gets its own session from the pool
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


async def init_db() -> None:
    """Create all tables on startup (for dev). Use Alembic in production."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Dispose the connection pool on shutdown."""
    await engine.dispose()