"""
ORM models — maps to PostgreSQL/SQLite tables.
Stored in app/db/models.py to match your existing db/ folder.
"""

from datetime import datetime
import uuid
from sqlalchemy import (
    String, Boolean, DateTime, Float, Integer,
    ForeignKey, Text, func, Uuid, JSON
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Signup telemetry columns
    signup_device_fingerprint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    signup_canvas_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    signup_webgl_renderer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    signup_platform: Mapped[int | None] = mapped_column(Integer, nullable=True)
    signup_screen: Mapped[str | None] = mapped_column(String(64), nullable=True)
    signup_timezone: Mapped[str | None] = mapped_column(String(255), nullable=True)
    signup_language: Mapped[str | None] = mapped_column(String(255), nullable=True)
    signup_webrtc_ip: Mapped[str | None] = mapped_column(String(255), nullable=True)
    signup_headless_signals: Mapped[str | None] = mapped_column(String(255), nullable=True)
    signup_webdriver: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    signup_risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Relationship to login attempts
    login_attempts: Mapped[list["LoginAttempt"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User {self.email}>"


class LoginAttempt(Base):
    __tablename__ = "login_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Device spec fields
    device_fingerprint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    canvas_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    webgl_renderer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    platform: Mapped[int | None] = mapped_column(Integer, nullable=True)
    screen: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pixel_ratio: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hardware_concurrency: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_touch: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Network context fields
    timezone: Mapped[str | None] = mapped_column(String(255), nullable=True)
    language: Mapped[str | None] = mapped_column(String(255), nullable=True)
    connection_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    webrtc_local_ip: Mapped[str | None] = mapped_column(String(255), nullable=True)
    do_not_track: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Behavioral signals fields
    form_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    password_pasted: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    username_pasted: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    avg_dwell_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_flight_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    keystroke_variance: Mapped[float | None] = mapped_column(Float, nullable=True)
    typo_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mouse_event_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mouse_linearity: Mapped[float | None] = mapped_column(Float, nullable=True)
    mouse_avg_speed: Mapped[float | None] = mapped_column(Float, nullable=True)
    used_tab_to_navigate: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Session metadata fields
    session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    headless_signals: Mapped[str | None] = mapped_column(String(255), nullable=True)
    webdriver: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    chrome_headless: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    no_plugins: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Extra JSON columns for structured fallback storage
    behavioral_signals: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    geo_signals: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    flag_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User | None"] = relationship(back_populates="login_attempts")

    def __repr__(self) -> str:
        status = "✓" if self.success else "✗"
        return f"<LoginAttempt {status} {self.email} score={self.risk_score}>"