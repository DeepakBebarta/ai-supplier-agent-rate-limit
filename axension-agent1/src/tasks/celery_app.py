"""
src/tasks/celery_app.py — Celery instance for Axension AI.

Broker: Redis
Beat schedule: 8:00 AM IST daily (or AGENT1_INTERVAL_MINUTES for dev testing)
Timezone: Asia/Kolkata
"""

import os
from celery import Celery
from celery.schedules import crontab
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

# ─── Create Celery app ───
app = Celery("axension")

# ─── Broker & Backend ───
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

app.conf.update(
    broker_url=REDIS_URL,
    result_backend=REDIS_URL,
    timezone="Asia/Kolkata",
    enable_utc=False,
    imports=["src.tasks.agent1_tasks"],
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Reliability
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# ─── Beat Schedule ───
# Dev override: if AGENT1_INTERVAL_MINUTES is set, use that interval
# Production: run at 8:00 AM IST daily
INTERVAL_MINUTES = os.environ.get("AGENT1_INTERVAL_MINUTES", None)

if INTERVAL_MINUTES:
    schedule_config = {
        "task": "agent1.daily_supplier_followup",
        "schedule": timedelta(minutes=int(INTERVAL_MINUTES)),
        "options": {"queue": "default"},
    }
else:
    schedule_config = {
        "task": "agent1.daily_supplier_followup",
        "schedule": crontab(hour=8, minute=0),
        "options": {"queue": "default"},
    }

app.conf.beat_schedule = {
    "agent1-daily-supplier-followup": schedule_config,
}
