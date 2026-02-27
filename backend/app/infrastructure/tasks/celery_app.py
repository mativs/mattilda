from celery import Celery

from app.config import settings

celery_app = Celery(
    "mattilda",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.infrastructure.tasks.invoice_tasks",
        "app.infrastructure.tasks.reconciliation_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)
