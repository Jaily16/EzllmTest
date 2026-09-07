"""Allowlisted JSON logging with no exception or free-form payload support."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from infrastructure.observability.local_export import emit_safe_log


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
        """初始化实例并保存后续操作所需的依赖与状态。"""
        self.logger = logger
        self.service = service[:64]

    def _emit(self, level: int, event: str, fields: dict[str, Any]) -> None:
        """发送内部逻辑，并遵循现有调用契约。

        参数:
            `level`：沿用签名中 `int` 类型约束的输入。
            `event`：沿用签名中 `str` 类型约束的输入。
            `fields`：沿用签名中 `dict[str, Any]` 类型约束的输入。

        副作用:
            可能向本地观测队列或 loopback 服务发送脱敏遥测副本。

        不变量:
            观测失败不得阻断业务，且禁止发送 prompt、项目正文、凭据或 traceback。"""
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
        emit_safe_log(payload)

    def info(self, event: str, **fields: Any) -> None:
        """写入不包含敏感内容的 info 级安全日志。"""
        self._emit(logging.INFO, event, fields)

    def warning(self, event: str, **fields: Any) -> None:
        """写入不包含敏感内容的 warning 级安全日志。"""
        self._emit(logging.WARNING, event, fields)

    def error(self, event: str, **fields: Any) -> None:
        """写入不包含敏感内容的 error 级安全日志。"""
        self._emit(logging.ERROR, event, fields)


def build_safe_logger(service: str) -> SafeJsonLogger:
    """构建安全logger，并遵循现有调用契约。

    参数:
        `service`：沿用签名中 `str` 类型约束的输入。

    返回:
        `SafeJsonLogger`，内容保持现有调用方契约。

    副作用:
        可能向本地观测队列或 loopback 服务发送脱敏遥测副本。

    不变量:
        观测失败不得阻断业务，且禁止发送 prompt、项目正文、凭据或 traceback。"""
    logger = logging.getLogger(f"ezllm.{service}")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    logger.propagate = False
    logger.setLevel(logging.INFO)
    return SafeJsonLogger(logger, service=service)
