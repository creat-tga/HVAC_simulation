"""Redis and Celery worker availability checker with caching."""

from __future__ import annotations

import logging
import time

import redis

from app.config import settings

log = logging.getLogger(__name__)

_last_check_time: float = 0.0
_last_check_result: bool = False
_CHECK_INTERVAL = 30.0  # Re-check every 30 seconds

_last_worker_check_time: float = 0.0
_last_worker_check_result: bool = False
_WORKER_CHECK_INTERVAL = 15.0  # Re-check workers every 15 seconds


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


def is_celery_worker_available() -> bool:
    """Check whether at least one Celery worker is running. Result is cached for 15 seconds."""
    global _last_worker_check_time, _last_worker_check_result

    now = time.monotonic()
    if now - _last_worker_check_time < _WORKER_CHECK_INTERVAL:
        return _last_worker_check_result

    from app.celery_app import celery_app

    if celery_app is None:
        _last_worker_check_result = False
        _last_worker_check_time = now
        return False

    try:
        inspect = celery_app.control.inspect(timeout=2)
        ping_result = inspect.ping()
        available = bool(ping_result)
        if not available and _last_worker_check_result:
            log.warning("No Celery workers detected, will fall back to in-process tasks")
        elif available and not _last_worker_check_result:
            log.info("Celery worker(s) detected: %s", list(ping_result.keys()))
        _last_worker_check_result = available
    except Exception:
        if _last_worker_check_result or _last_worker_check_time == 0.0:
            log.warning("Failed to check Celery workers, assuming unavailable")
        _last_worker_check_result = False

    _last_worker_check_time = now
    return _last_worker_check_result
