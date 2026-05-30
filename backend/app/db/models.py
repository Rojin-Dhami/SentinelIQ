import uuid as uuid_lib
from datetime import datetime
import enum

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import (
    Boolean, Integer, String, Float, DateTime, ForeignKey,
    func, UniqueConstraint, UUID, Enum, text
)
from sqlalchemy.dialects.postgresql import JSONB


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ── Enums ────────────────────────────────────────────

class UserRole(str, enum.Enum):
    user = "user"
    admin = "admin"


class LoginOutcome(str, enum.Enum):
    success = "success"
    failed_credentials = "failed_credentials"
    blocked_risk = "blocked_risk"
    blocked_velocity = "blocked_velocity"
    mfa_required = "mfa_required"
    mfa_verified = "mfa_verified"


# ── Tables ───────────────────────────────────────────

class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    uuid: Mapped[uuid_lib.UUID] = mapped_column(
        UUID(as_uuid=True), default=uuid_lib.uuid4, unique=True, nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="false")
    is_verified: Mapped[bool] = mapped_column(Boolean, server_default="false")
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), server_default="user")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_login_count: Mapped[int] = mapped_column(Integer, server_default="0")

    # Temporal account lock (escalating: 15 min → 1 h → 6 h → hard_block)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lock_level: Mapped[int] = mapped_column(Integer, server_default="0")

    behavior_profile: Mapped["UserBehaviorProfile"] = relationship(
        back_populates="user", uselist=False
    )


class UserDevice(Base):
    __tablename__ = "user_devices"
    __table_args__ = (
        UniqueConstraint("user_id", "device_fingerprint", name="uq_user_device"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    device_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)

    # Component-level fingerprint pieces (for similarity matching)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    platform: Mapped[str | None] = mapped_column(String(64), nullable=True)
    screen: Mapped[str | None] = mapped_column(String(32), nullable=True)
    canvas_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    webgl_renderer: Mapped[str | None] = mapped_column(String(256), nullable=True)
    hardware_concurrency: Mapped[int | None] = mapped_column(Integer, nullable=True)

    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Trust: device skips step-up MFA until trusted_until
    trusted_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserBehaviorProfile(Base):
    __tablename__ = "user_behavior_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, unique=True, index=True
    )

    # Running means (EWMA)
    avg_dwell_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_flight_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Running standard deviations (for z-score)
    std_dwell_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    std_flight_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    total_logins: Mapped[int] = mapped_column(Integer, server_default=text("0"))

    user: Mapped["User"] = relationship(back_populates="behavior_profile")


class LoginEvent(Base):
    __tablename__ = "login_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    country: Mapped[str | None] = mapped_column(String(128), nullable=True)
    device_fingerprint: Mapped[str | None] = mapped_column(String(128), nullable=True)
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    outcome: Mapped[LoginOutcome] = mapped_column(Enum(LoginOutcome), server_default="failed_credentials")
    decision: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    breakdown: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    device_id: Mapped[int | None] = mapped_column(ForeignKey("user_devices.id"), nullable=True)

    refresh_token_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
