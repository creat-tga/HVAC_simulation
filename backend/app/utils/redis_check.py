"""Redis availability checker with caching."""

from __future__ import annotations

import logging
import time

import redis

from app.config import settings

log = logging.getLogger(__name__)

_last_check_time: float = 0.0
_last_check_result: bool = False
_CHECK_INTERVAL = 30.0  # Re-check every 30 seconds


def is_redis_available() -> bool:
    """Check whether Redis is reachable. Result is cached for 30 seconds."""
    global _last_check_time, _last_check_result

    now = time.monotonic()
    if now - _last_check_time < _CHECK_INTERVAL:
        return _last_check_result

    try:
        r = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=2)
        r.ping()
        r.close()
        if not _last_check_result:
            log.info("Redis is available at %s", settings.redis_url)
        _last_check_result = True
    except Exception:
        if _last_check_result or _last_check_time == 0.0:
            log.warning("Redis is not available at %s, using in-process fallback", settings.redis_url)
        _last_check_result = False

    _last_check_time = now
    return _last_check_result
