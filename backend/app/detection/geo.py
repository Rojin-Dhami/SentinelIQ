import asyncio
import httpx
import json
import logging
import time
from math import sin, cos, sqrt, radians, atan2

from redis.asyncio import Redis

from app.core.config import settings
from app.schemas.dto import GeoLocation, GeoResult

logger = logging.getLogger(__name__)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371 # Earth`s radius in km
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))
 
   
async def _fetch_geo(ip: str = ""):
    """Look up an IP via ipinfo.io. Empty `ip` resolves the caller's own IP."""
    try:
        path = f"/{ip}/json" if ip else "/json"
        url = f"{settings.IP_INFO_URL}{path}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params={"token": settings.IP_INFO_KEY})
            data = resp.json()

            if not data or data.get("bogon") or "loc" not in data:
                return None

            lat_str, _, lon_str = data["loc"].partition(",")
            try:
                lat = float(lat_str)
                lon = float(lon_str)
            except ValueError:
                return None

            org = data.get("org") or ""
            asn = org.split(" ", 1)[0] if org.startswith("AS") else "Unknown"

            # ipinfo's free tier doesn't ship proxy/hosting flags; the
            # DATACENTER_ASNS check downstream still catches cloud ASNs.
            privacy = data.get("privacy") or {}

            return GeoLocation(
                ip=data.get("ip", ip),
                lat=lat,
                lon=lon,
                city=data.get("city", ""),
                country=data.get("country", ""),
                asn=asn,
                is_proxy=bool(privacy.get("proxy") or privacy.get("vpn") or privacy.get("tor")),
                is_hosting=bool(privacy.get("hosting")),
            )
    except Exception as e:
        logger.error(e)
        return None


def _get_redis_key(user_id: int) -> str:
    return f"geo:last_login:{user_id}"


def _get_history_key(user_id: int) -> str:
    return f"geo:history:{user_id}"


def _loc_from_dict(data: dict) -> GeoLocation:
    return GeoLocation(
        ip=data["ip"],
        lat=data["lat"],
        lon=data["lon"],
        city=data.get("city", ""),
        country=data.get("country", ""),
        asn=data.get("asn", "Unknown"),
        is_proxy=bool(data.get("is_proxy", False)),
        is_hosting=bool(data.get("is_hosting", False)),
    )


async def _get_last_location(user_id: int, redis: Redis):
    raw = await redis.get(_get_redis_key(user_id))
    if not raw:
        return None
    data = json.loads(raw)
    return _loc_from_dict(data), data["timestamp"]


async def _get_history(user_id: int, redis: Redis) -> list[GeoLocation]:
    raws = await redis.lrange(_get_history_key(user_id), 0, settings.GEO_HISTORY_SIZE - 1)
    out: list[GeoLocation] = []
    for raw in raws:
        try:
            out.append(_loc_from_dict(json.loads(raw)))
        except Exception:
            continue
    return out


async def _store_location(user_id: int, loc: GeoLocation, redis: Redis):
    payload = json.dumps({
        "ip": loc.ip,
        "lat": loc.lat,
        "lon": loc.lon,
        "city": loc.city,
        "country": loc.country,
        "asn": loc.asn,
        "is_proxy": loc.is_proxy,
        "is_hosting": loc.is_hosting,
        "timestamp": time.time(),
    })
    await redis.set(_get_redis_key(user_id), payload, ex=60 * 60 * 24 * 30)
    hkey = _get_history_key(user_id)
    await redis.lpush(hkey, payload)
    await redis.ltrim(hkey, 0, settings.GEO_HISTORY_SIZE - 1)
    await redis.expire(hkey, 60 * 60 * 24 * 90)


def _outside_home_cluster(current: GeoLocation, history: list[GeoLocation]) -> bool:
    """True when the user has a meaningful history but this login sits far from
    every previously-seen location."""
    if len(history) < 3:
        return False
    if current.lat is None or current.lon is None:
        return False
    radius = settings.GEO_HOME_RADIUS_KM
    for past in history:
        if past.lat is None or past.lon is None:
            continue
        if _haversine_km(current.lat, current.lon, past.lat, past.lon) <= radius:
            return False
    return True
    

async def check_geo(user_id: int, ip: str, redis: Redis, store: bool = False) -> GeoResult:
    """When `store=True`, persist this location to last+history (call only after
    a successful credential check, but before the risk decision)."""
    current_loc = await _fetch_geo(ip)

    if current_loc is None:
        return GeoResult(
            current_location=None, last_location=None, distance_km=None,
            time_elapsed_seconds=None, required_speed_kmh=None,
            is_impossible_travel=False, risk=0.0,
        )

    is_datacenter = current_loc.asn in settings.DATACENTER_ASNS or current_loc.is_hosting
    is_proxy = current_loc.is_proxy

    last = await _get_last_location(user_id, redis)
    history = await _get_history(user_id, redis)

    if last is None:
        if store:
            await _store_location(user_id, current_loc, redis)
        risk = 0.0
        if is_datacenter:
            risk += 0.3
        if is_proxy:
            risk += 0.3
        return GeoResult(
            current_location=current_loc, last_location=None,
            distance_km=None, time_elapsed_seconds=None, required_speed_kmh=None,
            is_impossible_travel=False, is_new_country=False,
            is_outside_home_cluster=False,
            is_datacenter=is_datacenter, is_proxy=is_proxy,
            risk=min(risk, 1.0),
        )

    last_loc, last_timestamp = last
    now = time.time()
    distance_km = _haversine_km(last_loc.lat, last_loc.lon, current_loc.lat, current_loc.lon)
    time_elapsed_seconds = now - last_timestamp
    time_elapsed_hours = time_elapsed_seconds / 3600

    if time_elapsed_hours < 0.001:
        required_speed_kmh = float("inf")
    else:
        required_speed_kmh = distance_km / time_elapsed_hours

    is_impossible_travel = required_speed_kmh > settings.GEO_MAX_SPEED_KMH and distance_km > 50
    is_new_country = last_loc.country != current_loc.country
    is_outside_home = _outside_home_cluster(current_loc, history)
    
    risk = 0.0
    if is_impossible_travel:
        risk = max(risk, 1.0)
    if is_new_country:
        risk = max(risk, 0.6)
    if is_outside_home:
        risk = max(risk, 0.35)
    elif last_loc.city != current_loc.city:
        risk = max(risk, 0.15)
    if is_datacenter:
        risk += 0.3
    if is_proxy:
        risk += 0.3
    risk = min(risk, 1.0)

    if store and not is_impossible_travel:
        await _store_location(user_id, current_loc, redis)

    return GeoResult(
        current_location=current_loc,
        last_location=last_loc,
        distance_km=round(distance_km, 2),
        time_elapsed_seconds=round(time_elapsed_seconds, 2),
        required_speed_kmh=round(required_speed_kmh, 2) if required_speed_kmh != float("inf") else None,
        is_impossible_travel=is_impossible_travel,
        is_new_country=is_new_country,
        is_outside_home_cluster=is_outside_home,
        is_datacenter=is_datacenter,
        is_proxy=is_proxy,
        risk=round(risk, 4),
    )
        

if __name__ == "__main__":
    res = asyncio.run(_fetch_geo())
    print(res)