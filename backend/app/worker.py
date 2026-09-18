"""Celery worker configuration."""

import logging

from celery import Celery
from celery.schedules import crontab

from app.config import settings

logger = logging.getLogger(__name__)

# Initialize Celery app
celery_app = Celery(
    "stocker_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks"]
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max task time
)


celery_app.conf.beat_schedule = {
    "fetch-sec-filings-every-15-min": {
        "task": "app.tasks.fetch_latest_sec_filings",
        "schedule": 900.0,  # 15 minutes
    },
    "fetch-macro-data-daily": {
        "task": "app.tasks.fetch_macro_indicators",
        "schedule": 86400.0,  # 24 hours
    },
    "daily-price-update-after-market-close": {
        "task": "app.tasks.daily_price_update",
        "schedule": crontab(hour=16, minute=30, day_of_week="1-5"),  # 4:30 PM EST M-F
    },
    "scheduled-news-ingestion-hourly": {
        "task": "app.tasks.scheduled_news_ingestion",
        "schedule": 3600.0,  # Every hour
    },
}
