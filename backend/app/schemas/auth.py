"""
app/schemas/auth.py — request/response schemas for auth endpoints.
"""

import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr, field_validator


# ── Nested sub-schemas (your exact spec) ─────────────────────────────────────

class LoginCredentials(BaseModel):
    email: EmailStr
    password: str


class DeviceSpec(BaseModel):
    device_fingerprint: str
    hardware_concurrency: int
    device_memory: int
    screen_width: int
    screen_height: int
    pixel_ratio: int
    is_touch: bool
    platform: int
    user_agent: str
    color_depth: str
    plugins_hash: str
    canvas_hash: str
    webgl_renderer: str


class NetworkContext(BaseModel):
    timezone: str
    language: str
    languages: list[str]
    connection_type: str
    webrtc_local_ip: str | None
    do_not_track: str | None


class BehavioralSignals(BaseModel):
    form_time_ms: int
    password_pasted: bool
    username_pasted: bool
    avg_dwell_time_ms: float
    avg_flight_time_ms: float
    keystroke_variance: float
    typo_count: int
    mouse_event_count: int
    mouse_linearity: float
    mouse_avg_speed: float
    used_tab_to_navigate: bool


class SessionMetadata(BaseModel):
    session_id: str
    referrer: str | None
    cookies_enabled: bool
    headless_signals: str
    webdriver: bool
    chrome_headless: bool
    no_plugins: bool


# ── Top-level request ─────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    credentials: LoginCredentials
    device_spec: DeviceSpec
    network_context: NetworkContext
    behavioral_signals: BehavioralSignals
    session_metadata: SessionMetadata


# ── Signup (extends login shape with name + confirm_password) ─────────────────

class SignupCredentials(LoginCredentials):
    full_name: str
    confirm_password: str

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        if "password" in info.data and v != info.data["password"]:
            raise ValueError("Passwords do not match")
        return v

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class SignupRequest(BaseModel):
    credentials: SignupCredentials
    device_spec: DeviceSpec
    network_context: NetworkContext
    behavioral_signals: BehavioralSignals
    session_metadata: SessionMetadata


# ── Responses ─────────────────────────────────────────────────────────────────

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: uuid.UUID
    email: str
    full_name: str


class SignupResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: uuid.UUID
    email: str
    full_name: str


# ── User (for /me or admin endpoints) ────────────────────────────────────────

class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    is_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}