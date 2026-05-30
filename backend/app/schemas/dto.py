from dataclasses import dataclass, field


@dataclass
class VelocityResult:
    user_count: int
    ip_count: int
    user_ip_count: int
    user_risk: float
    ip_risk: float
    user_ip_risk: float
    flagged: bool


@dataclass
class GeoLocation:
    ip: str
    lat: float
    lon: float
    city: str
    country: str
    asn: str
    is_proxy: bool = False
    is_hosting: bool = False
    is_vpn: bool = False
    is_tor: bool = False


@dataclass
class GeoResult:
    current_location: GeoLocation | None
    last_location: GeoLocation | None
    distance_km: float | None
    time_elapsed_seconds: float | None
    required_speed_kmh: float | None
    is_impossible_travel: bool
    is_new_country: bool = False
    is_outside_home_cluster: bool = False
    is_datacenter: bool = False
    is_proxy: bool = False
    risk: float = 0.0


@dataclass
class EmailSchema:
    to_email: str
    subject: str
    template_name: str          # e.g. "mfa.html", "register.html"
    template_params: dict = field(default_factory=dict)