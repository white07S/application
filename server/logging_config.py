import os
import sys
from typing import Optional

from loguru import logger


LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

LOG_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
    "{message}"
)


def configure_logging() -> None:
    """Configure a shared Loguru logger for the application and libraries."""
    logger.remove()
    logger.add(
        sys.stderr,
        level=LOG_LEVEL,
        format=LOG_FORMAT,
        backtrace=False,
        diagnose=False,
    )


def get_logger(name: Optional[str] = None, **kwargs):
    """Return a logger bound with an optional module/component name."""
    if name:
        return logger.bind(module=name, **kwargs)
    return logger.bind(**kwargs)
