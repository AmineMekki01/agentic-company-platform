"""Centralized logging configuration."""

import logging
import os


def configure_logging() -> None:
    """Configure root logging once at application startup."""
    _log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, _log_level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def get_logger(name: str) -> logging.Logger:
    """Return a logger with the given module name."""
    return logging.getLogger(name)
