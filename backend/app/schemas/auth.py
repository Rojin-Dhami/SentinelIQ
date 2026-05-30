from pydantic import BaseModel, EmailStr
from uuid import UUID


class LoginCredentials(BaseModel):
    email: EmailStr
    password: str


class RegisterCredentials(BaseModel):
    full_name: str
    email: EmailStr
    password: str


class DeviceSpec(BaseModel):
    device_fingerprint: str
    hardware_concurrency: int
    device_memory: float | None
    screen_width: int
    screen_height: int
    pixel_ratio: float
    is_touch: bool
    platform: str
    user_agent: str
    color_depth: str
    plugins_hash: str | None
    canvas_hash: str | None
    webgl_renderer: str | None


class NetworkContext(BaseModel):
    timezone: str
    language: str
    languages: list[str]
    connection_type: str | None
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
    session_id: UUID
    referrer: str | None
    cookies_enabled: bool
    webdriver: bool
    chrome_headless: bool
    no_plugins: bool


class LoginRequest(BaseModel):
    credentials: LoginCredentials
    device_spec: DeviceSpec
    network_context: NetworkContext
    behavioral_signals: BehavioralSignals
    session_metadata: SessionMetadata


class RegisterRequest(BaseModel):
    credentials: RegisterCredentials
    device_spec: DeviceSpec
    network_context: NetworkContext
    behavioral_signals: BehavioralSignals
    session_metadata: SessionMetadata


class RegisterVerifyRequest(BaseModel):
    email: EmailStr
    otp: str


class MfaVerifyRequest(BaseModel):
    challenge_id: str
    otp: str
    remember_device: bool = False


class MfaRequestRequest(BaseModel):
    """Used to start an MFA flow outside of the normal login decision path —
    today only consumed by the unlock-during-temporal-lock UX."""
    credentials: LoginCredentials
    device_spec: DeviceSpec
    network_context: NetworkContext
    behavioral_signals: BehavioralSignals
    session_metadata: SessionMetadata