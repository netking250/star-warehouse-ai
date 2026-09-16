"""LangSmith tracing setup for Celery workers."""

import logging
import os

from app.core.config import settings
from app.core.tracing import is_langsmith_tracing_enabled

logger = logging.getLogger(__name__)


def setup_celery_langsmith_tracing() -> None:
    """Configure LangSmith environment variables for Celery workers.

    This module intentionally lives outside ``app.tasks`` so the Celery
    application can configure tracing before importing task modules.
    """
    if not is_langsmith_tracing_enabled() or not settings.LANGSMITH_CELERY_TRACING:
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
        return

    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_API_KEY", settings.LANGSMITH_API_KEY.get_secret_value())
    os.environ.setdefault("LANGCHAIN_PROJECT", settings.LANGSMITH_PROJECT)

    logger.info(
        "LangSmith Celery tracing enabled",
        extra={"event": "langsmith_celery_tracing_enabled", "project": settings.LANGSMITH_PROJECT},
    )
