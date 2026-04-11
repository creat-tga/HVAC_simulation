"""Celery application configuration for HVAC simulation background tasks.

Celery is only created when Redis is reachable.  When Redis is down the
module exposes ``celery_app = None`` so callers can easily branch.
"""

from __future__ import annotations

import logging
from typing import Optional

from celery import Celery

from app.config import settings
from app.utils.redis_check import is_redis_available

log = logging.getLogger(__name__)

celery_app: Optional[Celery] = None


def _create_celery() -> Optional[Celery]:
    if not is_redis_available():
        log.info("Redis not available — Celery disabled, using in-process tasks")
        return None

    app = Celery(
        "hvac_simulation",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
    )
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="Asia/Shanghai",
        enable_utc=True,
        task_track_started=True,
        worker_concurrency=settings.celery_worker_concurrency,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
    )
    app.autodiscover_tasks(["app.tasks"])
    log.info("Celery initialized with broker %s", settings.celery_broker_url)
    return app


celery_app = _create_celery()

if celery_app is not None:
    import app.tasks  # noqa: F401, E402
