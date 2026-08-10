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

    api_key = settings.LANGSMITH_API_KEY.get_secret_value()
    masked_key = f"{api_key[:8]}..." if len(api_key) > 8 else "***"
    logger.info(
        "LangSmith Celery tracing enabled (project=%s, api_key=%s)",
        settings.LANGSMITH_PROJECT,
        masked_key,
    )
