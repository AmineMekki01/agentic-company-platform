"""Centralized logging configuration.

In production, logs are emitted as JSON objects for machine-parseable
filtering and alerting. In other environments, human-readable text is used.

Example production output:
    {"timestamp": "2026-06-28T01:05:00Z", "level": "warning", "event": "agent_response", "logger": "app.agents.graph", "agent": "it_agent", "len": 1234, "conv": "abc-123"}
"""

import json
import logging
import os
from datetime import UTC, datetime

_RESERVED = frozenset({
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "taskName", "message", "getMessage",
})


class JsonFormatter(logging.Formatter):
    """Format log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created, tz=UTC).strftime(
            "%Y-%m-%dT%H:%M:%S.") + f"{int(record.msecs):03d}Z"

        payload: dict = {
            "timestamp": timestamp,
            "level": record.levelname.lower(),
            "event": record.getMessage(),
            "logger": record.name,
        }

        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                try:
                    json.dumps(value)
                    payload[key] = value
                except (TypeError, ValueError):
                    payload[key] = repr(value)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging() -> None:
    """Configure root logging once at application startup."""
    _log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, _log_level, logging.INFO)

    from app.core.config import settings

    handler = logging.StreamHandler()
    if settings.environment == "production":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )

    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    """Return a logger with the given module name."""
    return logging.getLogger(name)
