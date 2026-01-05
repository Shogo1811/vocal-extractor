"""Logging configuration for the application."""
import logging
import sys
from datetime import datetime
from pathlib import Path

from app.config import settings


def setup_logging() -> logging.Logger:
    """Configure and return the application logger."""
    # Create logs directory
    log_dir = settings.base_dir / "logs"
    log_dir.mkdir(exist_ok=True)

    # Create logger
    logger = logging.getLogger("vocal_extractor")
    logger.setLevel(logging.DEBUG if settings.debug else logging.INFO)

    # Clear existing handlers
    logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # File handler
    log_file = log_dir / f"app_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)

    return logger


# Global logger instance
logger = setup_logging()
