from celery.schedules import crontab

from app.workers.celery_app import celery_app

# Celery Beat schedule
celery_app.conf.beat_schedule = {
    # Inactivity cleanup — every 5 minutes
    "cleanup-inactive-sessions": {
        "task": "app.workers.cleanup.cleanup_inactive_sessions_task",
        "schedule": crontab(minute="*/5"),
    },
    # Percentile rank recomputation — nightly at 2 AM UTC
    "recompute-percentile-ranks": {
        "task": "app.workers.cleanup.recompute_percentile_ranks_task",
        "schedule": crontab(hour=2, minute=0),
    },
    # Question pipeline — weekly on Sunday at midnight UTC
    # (Disabled by default; enable via admin UI or env override)
    # "question-pipeline": {
    #     "task": "app.workers.pipeline.generate_questions_task",
    #     "schedule": crontab(hour=0, minute=0, day_of_week=0),
    #     "args": ["scheduled", "software_engineering", "medium", 10],
    # },
}

celery_app.conf.timezone = "UTC"
