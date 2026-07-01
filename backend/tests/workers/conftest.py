"""
Worker test conftest.

Sets CELERY_TASK_ALWAYS_EAGER=True so Celery tasks execute synchronously
in the test process without needing a broker.
"""
import os

import pytest

from app.workers.celery_app import celery_app


@pytest.fixture(autouse=True, scope="session")
def celery_eager_mode():
    """Force all Celery tasks to run eagerly (synchronously) in tests."""
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    yield
    celery_app.conf.task_always_eager = False
