from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

    DEBUG: bool = True
    DATABASE_URL: str
    SECRET_KEY: str = "unsafe-KOACG1Y8u-Y_akeSco4nrSshIPAf3Xxhs9ZKU"

    APP_NAME: str = "SentinelIQ"
    APP_BASE_URL: str = "http://localhost:8000"
    FRONTEND_BASE_URL: str = "http://localhost:3000"

    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 14   # 14 days

    ALLOW_ORIGINS: list[str] = ["http://localhost:3000"]

    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_PASSWORD: str

    # ── Email (Brevo) ──
    BREVO_API_KEY: str
    BREVO_URL: str = "https://api.brevo.com/v3/smtp/email"
    BREVO_FROM_NAME: str = "SentinelIQ"
    BREVO_FROM_EMAIL: str = ""

    # ── Velocity ──
    VELOCITY_WINDOW_SECONDS: int = 60
    USER_MAX_ATTEMPTS: int = 5
    IP_MAX_ATTEMPTS: int = 20
    USER_IP_MAX_ATTEMPTS: int = 10

    # ── Detection weights (rule-based) ──
    VELOCITY_WEIGHT: float = 0.30
    GEO_WEIGHT: float = 0.35
    DEVICE_WEIGHT: float = 0.20
    BEHAVIORAL_WEIGHT: float = 0.15

    # Final blend (rule vs ML; ML stays muted until artifacts are loaded)
    RULE_BASE_WEIGHT: float = 0.75
    ML_WEIGHT: float = 0.25
    ML_ENABLED: bool = True
    ML_ARTIFACTS_DIR: str = "../ml_core/notebook/artifacts"

    # ── Risk bands ──
    RISK_ALLOW_MAX: float = 0.35
    RISK_BLOCK_MIN: float = 0.70
    TRUSTED_DEVICE_HARD_BLOCK: float = 0.85   # even trusted device gets MFA above this

    # ── Geo ──
    GEO_MAX_SPEED_KMH: int = 900
    GEO_HOME_RADIUS_KM: int = 500
    GEO_HISTORY_SIZE: int = 10
    IP_INFO_KEY: str
    IP_INFO_URL: str = "https://ipinfo.io"

    # Datacenter / hosting ASNs (common cloud + VPS providers)
    DATACENTER_ASNS: set[str] = {
        "AS14618", "AS16509",         # AWS
        "AS15169",                    # Google
        "AS8075",                     # Microsoft
        "AS14061",                    # DigitalOcean
        "AS16276",                    # OVH
        "AS24940",                    # Hetzner
        "AS20473",                    # Choopa / Vultr
        "AS63949",                    # Linode
        "AS13335",                    # Cloudflare
        "AS396982",                   # Google Cloud
        "AS9009",                     # M247
        "AS51167",                    # Contabo
    }

    # ── Device trust ──
    TRUSTED_DEVICE_DAYS: int = 30
    DEVICE_SIMILARITY_THRESHOLD: float = 0.66   # ≥ 4/6 components match

    # ── MFA / OTP ──
    OTP_LENGTH: int = 6
    OTP_TTL_SECONDS: int = 5 * 60
    OTP_MAX_ATTEMPTS: int = 5
    MFA_CHALLENGE_TTL_SECONDS: int = 10 * 60
    MAGIC_LINK_TTL_SECONDS: int = 24 * 60 * 60

    # ── Behavioral baseline ──
    BEHAVIOR_EWMA_ALPHA: float = 0.2
    BEHAVIOR_MIN_LOGINS_FOR_BASELINE: int = 5
    BEHAVIOR_ZSCORE_FLAG: float = 3.0

    # ── Account lockout (temporal) ──
    LOCK_FAIL_THRESHOLD: int = 5
    LOCK_DURATIONS_MINUTES: list[int] = [15, 60, 360]  # level 1 → 2 → 3


settings = Settings()