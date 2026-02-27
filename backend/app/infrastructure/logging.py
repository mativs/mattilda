import logging
from typing import Any

import structlog

from app.config import settings


def configure_logging() -> None:
    log_level_name = settings.log_level.upper()
    log_level = getattr(logging, log_level_name, logging.INFO)
    logging.basicConfig(format="%(message)s", level=log_level)

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    renderer = structlog.processors.JSONRenderer() if settings.log_json else structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[structlog.stdlib.filter_by_level, *shared_processors, renderer],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str):
    return structlog.get_logger(name)
