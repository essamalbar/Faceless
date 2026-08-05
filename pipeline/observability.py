"""GCP-native structured logging.

Cloud Run ingests container stdout into Cloud Logging; a log entry with
`severity=ERROR` and a stack trace in its payload is auto-grouped by Cloud
Error Reporting. So we need no external SDK — only correctly-shaped JSON on
stdout. stdlib only.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

_CONFIGURED = False
_LOGGER_NAME = "faceless"

_RESERVED = set(vars(logging.makeLogRecord({})).keys()) | {"message", "asctime", "taskName"}


class JsonFormatter(logging.Formatter):
    """One JSON object per line: severity + message (+ full traceback on
    exceptions so Error Reporting groups it) + any extra={...} as top-level
    keys."""

    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        if record.exc_info:
            message = f"{message}\n{self.formatException(record.exc_info)}".strip()
        elif record.exc_text:
            message = f"{message}\n{record.exc_text}".strip()
        payload: dict = {
            "severity": record.levelname,
            "message": message,
            "time": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "logger": record.name,
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(level: int = logging.INFO) -> None:
    """Idempotent: configure the root logger to emit JSON to stdout exactly
    once. Safe to call from both the API and the worker."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
    _CONFIGURED = True


def get_logger(name: str = _LOGGER_NAME) -> logging.Logger:
    return logging.getLogger(name)


def log_exception(exc: BaseException, *, where: str, **ctx) -> None:
    """Log an exception at ERROR with its traceback + structured context.
    `ctx` keys must not collide with stdlib LogRecord attributes."""
    get_logger().error("unhandled %s", type(exc).__name__,
                        exc_info=exc, extra={"where": where, **ctx})
