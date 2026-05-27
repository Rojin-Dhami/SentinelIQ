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
    R = 6371  # Earth's radius in km
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


async def _fetch_geo(ip: str = "") -> "tuple[GeoLocation, bool, bool] | None":
    """
    Returns (GeoLocation, is_proxy, is_hosting) or None on failure.
    is_proxy=True for VPN/anonymous proxies, is_hosting=True for datacenters.
    """
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(
                f"http://ip-api.com/json/{ip}",
                params={
                    "fields": "status,lat,lon,city,country,countryCode,as,proxy,hosting"
                },
            )
            data = resp.json()

            if data.get("status") != "success":
                return None

            loc = GeoLocation(
                ip=ip,
                lat=data.get("lat", 0.0),
                lon=data.get("lon", 0.0),
                city=data.get("city", ""),
                country=data.get("country", ""),
                country_code=data.get("countryCode", ""),
            )
            is_proxy = bool(data.get("proxy", False))
            is_hosting = bool(data.get("hosting", False))
            return loc, is_proxy, is_hosting
    except Exception as e:
        logger.error("Geo fetch failed: %s", e)
        return None


def _get_redis_key(user_id: str) -> str:
    return f"geo:last_login:{user_id}"


async def _get_last_location(user_id: str, redis: Redis):
    raw = await redis.get(_get_redis_key(user_id))
    if not raw:
        return None
    data = json.loads(raw)
    loc = GeoLocation(
        ip=data["ip"],
        lat=data["lat"],
        lon=data["lon"],
        city=data.get("city", ""),
        country=data.get("country", ""),
        country_code=data.get("country_code", ""),  # BUG FIX: was missing
    )
    return loc, data["timestamp"]


async def _store_location(user_id: str, loc: GeoLocation, redis: Redis):
    # BUG FIX: include country_code so _get_last_location doesn't KeyError
    payload = json.dumps({
        "ip": loc.ip,
        "lat": loc.lat,
        "lon": loc.lon,
        "city": loc.city,
        "country": loc.country,
        "country_code": loc.country_code,  # FIX: was missing
        "timestamp": time.time(),
    })
    await redis.set(_get_redis_key(user_id), payload, ex=60 * 60 * 24 * 30)


async def check_geo(
    user_id: str,
    ip: str,
    redis: Redis,
) -> "tuple[GeoResult, bool, bool]":
    """
    Returns (GeoResult, is_proxy, is_hosting).
    is_proxy/is_hosting are used by the ML engine.
    """
    fetched = await _fetch_geo(ip)

    empty_result = GeoResult(
        current_location=None,
        last_location=None,
        distance_km=None,
        time_elapsed_seconds=None,
        required_speed_kmh=None,
        is_impossible_travel=False,
        risk=0.0,
    )

    if fetched is None:
        return empty_result, False, False

    current_loc, is_proxy, is_hosting = fetched

    last = await _get_last_location(user_id, redis)

    if last is None:
        await _store_location(user_id, current_loc, redis)
        return GeoResult(
            current_location=current_loc,
            last_location=None,
            distance_km=0.0,
            time_elapsed_seconds=None,
            required_speed_kmh=None,
            is_impossible_travel=False,
            risk=0.0,
        ), is_proxy, is_hosting

    last_loc, last_timestamp = last
    now = time.time()

    distance_km = _haversine_km(
        last_loc.lat, last_loc.lon,
        current_loc.lat, current_loc.lon,
    )

    time_elapsed_seconds = now - last_timestamp
    time_elapsed_hours = time_elapsed_seconds / 3600

    if time_elapsed_hours < 0.001:
        required_speed_kmh = float("inf")
    else:
        required_speed_kmh = distance_km / time_elapsed_hours

    is_impossible_travel = required_speed_kmh > settings.GEO_MAX_SPEED_KMH

    if is_impossible_travel:
        risk = 1.0
    elif last_loc.country != current_loc.country:
        risk = 0.6
    elif last_loc.city != current_loc.city:
        risk = 0.2
    else:
        risk = 0.0

    if not is_impossible_travel:
        await _store_location(user_id, current_loc, redis)

    return GeoResult(
        current_location=current_loc,
        last_location=last_loc,
        distance_km=round(distance_km, 2),
        time_elapsed_seconds=round(time_elapsed_seconds, 2),
        required_speed_kmh=round(required_speed_kmh, 2),
        is_impossible_travel=is_impossible_travel,
        risk=round(risk, 4),
    ), is_proxy, is_hosting


if __name__ == "__main__":
    asyncio.run(_fetch_geo())