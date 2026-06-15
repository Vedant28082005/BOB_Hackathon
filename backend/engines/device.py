"""
Device & Network Intelligence Engine.
Real GeoIP lookup (MaxMind GeoLite2), VPN/datacenter detection, emulator heuristics.
"""
from __future__ import annotations
import re
from pathlib import Path
from typing import Optional

import structlog

from config import settings

log = structlog.get_logger(__name__)

# ── GeoIP ─────────────────────────────────────────────────────────────────────
_geoip_reader = None

def _get_geoip():
    global _geoip_reader
    if _geoip_reader is not None:
        return _geoip_reader
    db = Path(settings.geoip_db_path)
    if db.exists():
        try:
            import geoip2.database
            _geoip_reader = geoip2.database.Reader(str(db))
            log.info("geoip_loaded", path=str(db))
        except ImportError:
            log.warning("geoip2 not installed; pip install geoip2")
        except Exception as e:
            log.warning("geoip_load_failed", error=str(e))
    else:
        log.warning("geoip_db_missing", path=str(db),
                    note="Download from https://dev.maxmind.com/geoip/geolite2-free-geolocation-data")
    return _geoip_reader


def _lookup_ip(ip: str) -> dict:
    reader = _get_geoip()
    if not reader:
        return {}
    try:
        resp = reader.city(ip)
        return {
            "country": resp.country.iso_code or "",
            "region": resp.subdivisions.most_specific.name or "",
            "city": resp.city.name or "",
            "latitude": resp.location.latitude,
            "longitude": resp.location.longitude,
            "timezone": resp.location.time_zone or "",
            "is_datacenter": resp.traits.is_hosting_provider or False,
            "is_anonymous_proxy": resp.traits.is_anonymous_proxy or False,
        }
    except Exception:
        return {}


# ── Emulator/bot UA patterns ───────────────────────────────────────────────────
_EMULATOR_PATTERNS = [
    r"genymotion", r"bluestacks", r"nox", r"memu", r"ldplayer",
    r"android.*x86", r"headlesschrome", r"phantomjs", r"selenium",
    r"puppeteer", r"playwright", r"webdriver", r"bot/", r"spider/",
    r"crawler", r"slurp", r"baiduspider",
]
_EMULATOR_RE = re.compile("|".join(_EMULATOR_PATTERNS), re.I)

# Known fraud IP prefixes (from threat-intel; in production use a live feed)
_FRAUD_IP_PREFIXES = ("196.245.100.", "185.220.", "45.142.", "91.108.")

_PRIVATE_PREFIXES = ("127.", "10.", "172.16.", "172.17.", "172.18.", "172.19.",
                     "172.2", "172.3", "192.168.", "::1", "0.0.0.0")


def _is_private(ip: str) -> bool:
    return any(ip.startswith(p) for p in _PRIVATE_PREFIXES)


def analyse_device(signals: dict, ip_address: str) -> dict:
    flags: list[str] = []
    score = 100.0

    ua = signals.get("user_agent", "")
    platform = signals.get("platform", "")
    hw = signals.get("hardware_concurrency", 4)
    tz_offset = signals.get("timezone_offset", 0)
    lang = signals.get("language", "")
    fingerprint = signals.get("fingerprint", "")

    # 1. Emulator/bot UA
    if _EMULATOR_RE.search(ua):
        flags.append("EMULATOR_DETECTED")
        score -= 30.0

    # 2. Suspicious hardware concurrency (emulators often report 1 or exactly 2)
    if hw in (0, 1):
        flags.append("SUSPICIOUS_HW_CONCURRENCY")
        score -= 10.0

    # 3. GeoIP lookup
    geo = {}
    if ip_address and not _is_private(ip_address):
        geo = _lookup_ip(ip_address)

        # VPN / datacenter
        if geo.get("is_datacenter"):
            flags.append("VPN_DATACENTER_IP")
            score -= 12.0
        if geo.get("is_anonymous_proxy"):
            flags.append("ANONYMOUS_PROXY")
            score -= 15.0

        # Timezone vs GeoIP timezone consistency
        geo_tz = geo.get("timezone", "")
        if geo_tz and tz_offset is not None:
            # Convert browser TZ offset (minutes, inverted) to rough country check
            # This is a heuristic — production would compare geo_tz to tz_offset properly
            india_offsets = {-330}  # IST = UTC+5:30 = browser reports -330
            is_india_tz = int(tz_offset) in india_offsets if tz_offset else False
            is_india_geo = "Asia/Kolkata" in geo_tz or "Asia/Calcutta" in geo_tz
            if is_india_tz != is_india_geo:
                flags.append("TZ_IP_MISMATCH")
                score -= 8.0

        # Known fraud IPs (threat-intel prefix match)
        if any(ip_address.startswith(p) for p in _FRAUD_IP_PREFIXES):
            flags.append("FRAUD_IP")
            score -= 20.0

    score = max(0.0, min(100.0, score))

    return {
        "score": score,
        "signals": {
            "fingerprint": fingerprint[:16] + "…" if len(fingerprint) > 16 else fingerprint,
            "user_agent": ua[:80],
            "platform": platform,
            "hardware_concurrency": hw,
            "timezone_offset": tz_offset,
            "language": lang,
            "geo_country": geo.get("country", ""),
            "geo_region": geo.get("region", ""),
            "geo_timezone": geo.get("timezone", ""),
            "is_datacenter": geo.get("is_datacenter", False),
        },
        "flags": flags,
    }
