"""Structured logging with Loguru.

Provides a single ``setup_logging()`` callable that configures Loguru
with JSON-structured console output, a rotating file sink, and
request-id injection for distributed tracing.

Usage::

    from core.logger import setup_logging, get_logger
    setup_logging(log_level="INFO")
    logger = get_logger(__name__)
"""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

# Project root for relative log paths
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_LOG_DIR = _PROJECT_ROOT / "logs"


def _json_formatter(record: dict) -> str:
    """Produce a structured JSON log line.

    ``extra`` fields added via ``logger.bind(...)`` are merged
    into the top-level JSON object automatically by Loguru's
    ``serialize=True`` sink option.
    """
    # Avoid circular import
    record["extra"].setdefault("module", record["name"])
    record["extra"].setdefault("line", record["line"])
    return (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>\n"
    )


def setup_logging(log_level: str = "INFO") -> None:
    """Remove the default Loguru handler and install project handlers.

    Parameters
    ----------
    log_level:
        Minimum log level ("TRACE", "DEBUG", "INFO", etc.).
    """
    logger.remove()  # strip the default stderr handler

    # -- Console handler (human-readable, coloured) ------------------------
    logger.add(
        sys.stderr,
        format=_json_formatter,
        level=log_level.upper(),
        colorize=True,
        backtrace=True,
        diagnose=False,  # keep output clean in production
    )

    # -- Rotating file handler (plain text) ---------------------------------
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger.add(
        str(_LOG_DIR / "trend_analyzer_{time:YYYY-MM-DD}.log"),
        rotation="00:00",       # new file every midnight
        retention="30 days",     # keep last 30 log files
        compression="gz",
        level=log_level.upper(),
        format=(
                "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
                "{name}:{function}:{line} - {message}\n"
        ),
        enqueue=True,            # thread-safe async writing
    )

    # -- Error-only file handler for quick triage --------------------------
    logger.add(
        str(_LOG_DIR / "errors_{time:YYYY-MM-DD}.log"),
        rotation="00:00",
        retention="60 days",
        compression="gz",
        level="ERROR",
        format=(
                "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
                "{name}:{function}:{line} - {message}\n"
                "{exception}"
        ),
        enqueue=True,
    )

    logger.info("Logging initialised  level={log_level}", log_level=log_level)


def get_logger(name: str):
    """Return a child logger bound with the given module name."""
    return logger.bind(name=name)
