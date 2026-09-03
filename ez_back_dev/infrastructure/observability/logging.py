"""Allowlisted JSON logging with no exception or free-form payload support."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any


_FIELDS = frozenset(
    {
        "trace_id", "span_id", "run_id", "thread_id", "operation",
        "status", "cache", "error_code", "input_tokens", "output_tokens",
        "model_calls", "embedding_calls", "tool_calls", "elapsed_ms", "sequence",
    }
)
_ID_FIELDS = frozenset({"trace_id", "span_id", "run_id", "thread_id"})


class SafeJsonLogger:
    def __init__(self, logger: logging.Logger, *, service: str) -> None:
        self.logger = logger
        self.service = service[:64]

    def _emit(self, level: int, event: str, fields: dict[str, Any]) -> None:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": logging.getLevelName(level).lower(),
            "service": self.service,
            "event": event[:96],
        }
        for key, value in fields.items():
            if key not in _FIELDS:
                continue
            if isinstance(value, bool):
                payload[key] = value
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                payload[key] = value
            elif isinstance(value, str):
                payload[key] = value[: (128 if key in _ID_FIELDS else 64)]
        self.logger.log(
            level,
            json.dumps(payload, ensure_ascii=False, allow_nan=False, sort_keys=True),
            exc_info=None,
            stack_info=False,
        )

    def info(self, event: str, **fields: Any) -> None:
        self._emit(logging.INFO, event, fields)

    def warning(self, event: str, **fields: Any) -> None:
        self._emit(logging.WARNING, event, fields)

    def error(self, event: str, **fields: Any) -> None:
        self._emit(logging.ERROR, event, fields)


def build_safe_logger(service: str) -> SafeJsonLogger:
    logger = logging.getLogger(f"ezllm.{service}")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    logger.propagate = False
    logger.setLevel(logging.INFO)
    return SafeJsonLogger(logger, service=service)
