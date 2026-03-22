"""Redis cache layer with graceful fallback.

When Redis is unavailable the app continues to work — cache operations
silently become no-ops.  Configure via environment variable:

    REDIS_URL=redis://localhost:6379/0

TTL for analysis cache is controlled by CACHE_TTL_SECONDS (default 600 = 10 min).
Rate limit window and max hits are RATE_LIMIT_WINDOW / RATE_LIMIT_MAX.
"""

import hashlib
import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

REDIS_URL: str = os.environ.get(
    "REDIS_URL",
    "redis://default:IcqvJcTEKRMPTyknJFY4zKbtIr0G40KF@redis-17671.crce288.eu-central-1-1.ec2.cloud.redislabs.com:17671",
)
CACHE_TTL: int = int(os.environ.get("CACHE_TTL_SECONDS", "600"))
RATE_LIMIT_WINDOW: int = int(os.environ.get("RATE_LIMIT_WINDOW", "60"))
RATE_LIMIT_MAX: int = int(os.environ.get("RATE_LIMIT_MAX", "10"))

_PREFIX_CACHE = "tracer:cache:"
_PREFIX_RATE = "tracer:rate:"

_redis = None
_available = False


def _connect():
    """Lazy-connect to Redis on first use."""
    global _redis, _available
    if _redis is not None:
        return
    try:
        import redis as _redis_lib
        _redis = _redis_lib.Redis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        _redis.ping()
        _available = True
        logger.info("Redis connected: %s", REDIS_URL)
    except Exception as e:
        _redis = None
        _available = False
        logger.warning("Redis unavailable (%s) — running without cache", e)


def is_available() -> bool:
    _connect()
    return _available


def _cache_key(url: str) -> str:
    normalized = url.strip().lower().rstrip("/")
    h = hashlib.sha256(normalized.encode()).hexdigest()[:16]
    return f"{_PREFIX_CACHE}{h}"


# --------------- Analysis result cache ---------------

def get_cached_analysis(url: str) -> Optional[dict]:
    _connect()
    if not _available:
        return None
    try:
        raw = _redis.get(_cache_key(url))
        if raw:
            logger.debug("Cache HIT for %s", url)
            return json.loads(raw)
    except Exception as e:
        logger.debug("Cache GET error: %s", e)
    return None


def set_cached_analysis(url: str, data: dict, ttl: int | None = None) -> None:
    _connect()
    if not _available:
        return
    try:
        _redis.setex(
            _cache_key(url),
            ttl or CACHE_TTL,
            json.dumps(data, ensure_ascii=False, default=str),
        )
        logger.debug("Cache SET for %s (ttl=%s)", url, ttl or CACHE_TTL)
    except Exception as e:
        logger.debug("Cache SET error: %s", e)


# --------------- Rate limiting ---------------

def check_rate_limit(client_ip: str) -> tuple[bool, int]:
    """Returns (allowed: bool, remaining: int).

    Uses a sliding-window counter per IP address.
    """
    _connect()
    if not _available:
        return True, RATE_LIMIT_MAX

    key = f"{_PREFIX_RATE}{client_ip}"
    try:
        current = _redis.get(key)
        count = int(current) if current else 0

        if count >= RATE_LIMIT_MAX:
            ttl = _redis.ttl(key)
            return False, 0

        pipe = _redis.pipeline()
        pipe.incr(key)
        if count == 0:
            pipe.expire(key, RATE_LIMIT_WINDOW)
        pipe.execute()

        return True, RATE_LIMIT_MAX - count - 1
    except Exception as e:
        logger.debug("Rate limit check error: %s", e)
        return True, RATE_LIMIT_MAX


def get_info() -> dict:
    """Return Redis connection info for /api/health."""
    _connect()
    if not _available:
        return {"status": "unavailable", "url": REDIS_URL}
    try:
        info = _redis.info("server")
        return {
            "status": "connected",
            "version": info.get("redis_version", "?"),
            "url": REDIS_URL,
        }
    except Exception as e:
        return {"status": f"error: {e}", "url": REDIS_URL}
