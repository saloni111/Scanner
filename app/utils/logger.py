"""Loguru-based logger setup."""

import sys

from loguru import logger

from app.config import get_settings

_configured = False


def setup_logging() -> None:
    """Configure loguru once at startup."""
    global _configured
    if _configured:
        return

    settings = get_settings()
    logger.remove()
    logger.add(
        sys.stdout,
        level=settings.log_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
        backtrace=False,
        diagnose=False,
    )
    _configured = True


def get_logger(name: str | None = None):
    setup_logging()
    return logger.bind(name=name) if name else logger
