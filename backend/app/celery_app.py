"""Celery application configuration for HVAC simulation background tasks."""

from celery import Celery

from app.config import settings

celery_app = Celery(
    "hvac_simulation",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
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

# Auto-discover tasks in app/tasks/
celery_app.autodiscover_tasks(["app.tasks"])

# Ensure tasks are registered
import app.tasks  # noqa: F401, E402
