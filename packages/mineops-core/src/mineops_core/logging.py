"""JSON logging on top of stdlib ``logging``.

Choice (recorded in docs/milestones/M01): stdlib + a small formatter instead of structlog.
No extra dependency, and OpenTelemetry's logging instrumentation (M8) hooks stdlib directly.
"""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)

# Attributes every LogRecord has; anything else passed via ``extra=`` is context.
_RESERVED = frozenset(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {
    "message",
    "asctime",
    "taskName",
}


class JsonFormatter(logging.Formatter):
    def __init__(self, service: str) -> None:
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "service": self.service,
            "request_id": request_id_var.get(),
            "trace_id": trace_id_var.get(),
            "msg": record.getMessage(),
            "logger": record.name,
        }
        for key, value in vars(record).items():
            if key not in _RESERVED and key not in payload:
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


# HTTP client libraries log every request at INFO; that is debug detail for us.
NOISY_LOGGERS = ("httpx", "httpcore", "urllib3", "opensearch", "huggingface_hub")


def configure_logging(service: str, level: str = "INFO", json_format: bool = True) -> None:
    """Install a single stdout handler on the root logger (idempotent)."""
    handler = logging.StreamHandler(sys.stdout)
    if json_format:
        handler.setFormatter(JsonFormatter(service))
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    for name in NOISY_LOGGERS:
        logging.getLogger(name).setLevel(max(logging.WARNING, logging.getLevelName(level)))


@contextmanager
def log_context(request_id: str | None = None, trace_id: str | None = None) -> Iterator[None]:
    """Bind request/trace IDs for the duration of a block (async-safe via contextvars)."""
    tokens = []
    if request_id is not None:
        tokens.append((request_id_var, request_id_var.set(request_id)))
    if trace_id is not None:
        tokens.append((trace_id_var, trace_id_var.set(trace_id)))
    try:
        yield
    finally:
        for var, token in reversed(tokens):
            var.reset(token)
