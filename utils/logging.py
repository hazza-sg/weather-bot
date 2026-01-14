"""Logging configuration and utilities."""
import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional

from app.config import get_log_dir, get_settings


def setup_logging(
    level: Optional[str] = None,
    log_file: Optional[Path] = None,
) -> None:
    """
    Set up application logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional log file path
    """
    settings = get_settings()
    log_level = getattr(logging, (level or settings.log_level).upper(), logging.INFO)

    # Create formatters
    console_formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )

    file_formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)-7s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(console_formatter)

    # File handler
    if log_file is None:
        log_file = get_log_dir() / "weather_trader.log"

    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Set levels for noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    logging.info(f"Logging initialized at {log_level} level")
    logging.info(f"Log file: {log_file}")


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name."""
    return logging.getLogger(name)


class ActivityLogger:
    """Logger that also stores entries in the database for UI display."""

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self._db_callback = None

    def set_db_callback(self, callback) -> None:
        """Set callback for storing log entries in database."""
        self._db_callback = callback

    async def _store_entry(
        self,
        level: str,
        message: str,
        category: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> None:
        """Store log entry in database."""
        if self._db_callback:
            try:
                await self._db_callback(level, message, category, details)
            except Exception:
                pass  # Don't let DB errors affect logging

    def info(
        self,
        message: str,
        category: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> None:
        """Log info message."""
        self.logger.info(message)
        # Note: In async context, would await self._store_entry(...)

    def warning(
        self,
        message: str,
        category: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> None:
        """Log warning message."""
        self.logger.warning(message)

    def error(
        self,
        message: str,
        category: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> None:
        """Log error message."""
        self.logger.error(message)

    def debug(
        self,
        message: str,
        category: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> None:
        """Log debug message."""
        self.logger.debug(message)
