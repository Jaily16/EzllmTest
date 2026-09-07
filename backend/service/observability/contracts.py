"""Strict schemas shared by the local telemetry exporter and query service."""

from __future__ import annotations

import math
import re
import time
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


OBSERVABILITY_SCHEMA_VERSION = "iteration6-observability-v1"
TELEMETRY_SCHEMA_VERSION = "iteration4-aspect7-v1"
GENAI_SAFE_POLICY_VERSION = "otel-genai-safe-v1"

TRACE_ID = re.compile(r"^[0-9a-f]{32}$")
SPAN_ID = re.compile(r"^[0-9a-f]{16}$")
SERVICE_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]{0,62}$")
SPAN_NAME = re.compile(
    r"^(?:http\.agent_api|mcp\.request|agent\.(?:command(?:\.enqueue|\.worker)?|"
    r"run|graph\.[a-z_]+|plan|tool|retrieval|checkpoint|validation|recovery|sse)|"
    r"gen_ai\.(?:chat|embeddings))$"
)

ATTRIBUTE_KEYS = frozenset(
    {
        "agent.cache",
        "agent.checkpoint.kind",
        "agent.command.kind",
        "agent.error.type",
        "agent.operation",
        "agent.retention",
        "agent.status",
        "agent.tool.name",
        "gen_ai.operation.name",
        "gen_ai.output.type",
        "gen_ai.provider.name",
        "gen_ai.request.model",
        "gen_ai.usage.input_tokens",
        "gen_ai.usage.output_tokens",
        "http.request.method",
        "retrieval.corpus",
        "retrieval.index.action",
        "retrieval.strategy",
        "server.address",
    }
)
METRIC_LABEL_KEYS = frozenset(
    {
        "cache",
        "checkpoint_kind",
        "command_kind",
        "corpus",
        "model",
        "operation",
        "retention",
        "status",
        "strategy",
    }
)
METRIC_KINDS = {
    "ezllm.agent.checkpoint.duration": "histogram",
    "ezllm.agent.checkpoint.operations": "counter",
    "ezllm.agent.commands.duration": "histogram",
    "ezllm.agent.commands.enqueue.duration": "histogram",
    "ezllm.agent.commands.enqueued": "counter",
    "ezllm.agent.commands.processed": "counter",
    "ezllm.agent.commands.received": "counter",
    "ezllm.agent.embedding.calls": "counter",
    "ezllm.agent.embedding.duration": "histogram",
    "ezllm.agent.graph.node.duration": "histogram",
    "ezllm.agent.graph.nodes": "counter",
    "ezllm.agent.model.calls": "counter",
    "ezllm.agent.model.duration": "histogram",
    "ezllm.agent.model.input_tokens": "counter",
    "ezllm.agent.model.output_tokens": "counter",
    "ezllm.agent.recovery": "counter",
    "ezllm.agent.retrieval.duration": "histogram",
    "ezllm.agent.retrieval.queries": "counter",
    "ezllm.agent.runs.active": "gauge",
    "ezllm.agent.runs.created": "counter",
    "ezllm.agent.sse.connections": "gauge",
    "ezllm.agent.sse.ttfe": "histogram",
    "ezllm.agent.tool.calls": "counter",
    "ezllm.agent.tool.duration": "histogram",
}
LOG_EVENTS = frozenset({"agent.command.acknowledged"})
LOG_FIELDS = frozenset(
    {
        "trace_id",
        "span_id",
        "run_id",
        "thread_id",
        "operation",
        "status",
        "cache",
        "error_code",
        "input_tokens",
        "output_tokens",
        "model_calls",
        "embedding_calls",
        "tool_calls",
        "elapsed_ms",
        "sequence",
    }
)
WINDOW_MILLISECONDS = {
    "15m": 15 * 60 * 1_000,
    "1h": 60 * 60 * 1_000,
    "6h": 6 * 60 * 60 * 1_000,
    "24h": 24 * 60 * 60 * 1_000,
    "7d": 7 * 24 * 60 * 60 * 1_000,
}


class StrictRecord(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        strict=True,
    )


def _finite(value: float) -> float:
    """将输入规范化为有限数值。

    参数:
        `value`：待处理的值。

    返回:
        `float`，内容保持现有调用方契约。

    异常:
        `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
    if not math.isfinite(value):
        raise ValueError("numeric telemetry values must be finite")
    return value


def _safe_scalar_map(
    value: dict[str, Any], allowed: frozenset[str], *, string_limit: int
) -> dict[str, bool | int | float | str]:
    """将标量映射收敛为允许公开的安全形式。

    参数:
        `value`：待处理的值。
        `allowed`：沿用签名中 `frozenset[str]` 类型约束的输入。
        `string_limit`：沿用签名中 `int` 类型约束的输入。

    返回:
        `dict[str, bool | int | float | str]`，内容保持现有调用方契约。

    异常:
        `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
    output: dict[str, bool | int | float | str] = {}
    for key, item in value.items():
        if key not in allowed:
            raise ValueError("telemetry field is not allowlisted")
        if isinstance(item, bool):
            output[key] = item
        elif isinstance(item, int):
            output[key] = item
        elif isinstance(item, float):
            output[key] = _finite(item)
        elif isinstance(item, str) and len(item) <= string_limit:
            output[key] = item
        else:
            raise ValueError("telemetry value is invalid")
    return output


class SpanRecord(StrictRecord):
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    service: str
    name: str
    started_at_ms: int = Field(ge=0)
    ended_at_ms: int = Field(ge=0)
    duration_ms: float = Field(ge=0)
    status: Literal["unset", "ok", "error"] = "unset"
    attributes: dict[str, bool | int | float | str] = Field(default_factory=dict)

    @field_validator("trace_id")
    @classmethod
    def _trace_id(cls, value: str) -> str:
        """返回当前Trace ID。

        参数:
            `value`：待处理的值。

        返回:
            `str`，内容保持现有调用方契约。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
        if not TRACE_ID.fullmatch(value) or int(value, 16) == 0:
            raise ValueError("trace id is invalid")
        return value

    @field_validator("span_id")
    @classmethod
    def _span_id(cls, value: str) -> str:
        """返回当前Span ID。

        参数:
            `value`：待处理的值。

        返回:
            `str`，内容保持现有调用方契约。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
        if not SPAN_ID.fullmatch(value) or int(value, 16) == 0:
            raise ValueError("span id is invalid")
        return value

    @field_validator("parent_span_id")
    @classmethod
    def _parent_span_id(cls, value: str | None) -> str | None:
        """返回当前父级Span ID。

        参数:
            `value`：待处理的值。

        返回:
            `str | None`，内容保持现有调用方契约。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
        if value is not None and (
            not SPAN_ID.fullmatch(value) or int(value, 16) == 0
        ):
            raise ValueError("parent span id is invalid")
        return value

    @field_validator("service")
    @classmethod
    def _service(cls, value: str) -> str:
        """返回当前已绑定的服务实例。

        参数:
            `value`：待处理的值。

        返回:
            `str`，内容保持现有调用方契约。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
        if not SERVICE_NAME.fullmatch(value):
            raise ValueError("service name is invalid")
        return value

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        """返回当前名称。

        参数:
            `value`：待处理的值。

        返回:
            `str`，内容保持现有调用方契约。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
        if not SPAN_NAME.fullmatch(value):
            raise ValueError("span name is not registered")
        return value

    @field_validator("duration_ms")
    @classmethod
    def _duration(cls, value: float) -> float:
        """处理耗时，并保持 `SpanRecord` 的现有状态约束。"""
        return _finite(value)

    @field_validator("attributes")
    @classmethod
    def _attributes(
        cls, value: dict[str, Any]
    ) -> dict[str, bool | int | float | str]:
        """构造符合允许清单的安全属性。"""
        return _safe_scalar_map(value, ATTRIBUTE_KEYS, string_limit=128)

    @model_validator(mode="after")
    def _ordered_times(self) -> "SpanRecord":
        """处理有序times，并保持 `SpanRecord` 的现有状态约束。

        返回:
            `'SpanRecord'`，内容保持现有调用方契约。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
        if self.ended_at_ms < self.started_at_ms:
            raise ValueError("span timestamps are out of order")
        expected = self.ended_at_ms - self.started_at_ms
        if abs(expected - self.duration_ms) > 2.0:
            raise ValueError("span duration does not match timestamps")
        return self


class MetricRecord(StrictRecord):
    observed_at_ms: int = Field(ge=0)
    start_time_ms: int = Field(ge=0)
    service: str
    name: str
    kind: Literal["counter", "gauge", "histogram"]
    value: float | None = None
    count: int | None = Field(default=None, ge=0)
    total: float | None = None
    minimum: float | None = None
    maximum: float | None = None
    bounds: list[float] = Field(default_factory=list)
    bucket_counts: list[int] = Field(default_factory=list)
    labels: dict[str, str] = Field(default_factory=dict)

    @field_validator("service")
    @classmethod
    def _service(cls, value: str) -> str:
        """返回当前已绑定的服务实例。

        参数:
            `value`：待处理的值。

        返回:
            `str`，内容保持现有调用方契约。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
        if not SERVICE_NAME.fullmatch(value):
            raise ValueError("service name is invalid")
        return value

    @field_validator("labels")
    @classmethod
    def _labels(cls, value: dict[str, str]) -> dict[str, str]:
        """构造符合低基数约束的指标标签。

        参数:
            `value`：待处理的值。

        返回:
            `dict[str, str]`，内容保持现有调用方契约。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
        if set(value).difference(METRIC_LABEL_KEYS):
            raise ValueError("metric label is not allowlisted")
        if any(not isinstance(item, str) or len(item) > 64 for item in value.values()):
            raise ValueError("metric label value is invalid")
        return value

    @model_validator(mode="after")
    def _shape(self) -> "MetricRecord":
        """处理结构，并保持 `MetricRecord` 的现有状态约束。

        返回:
            `'MetricRecord'`，内容保持现有调用方契约。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
        expected_kind = METRIC_KINDS.get(self.name)
        if expected_kind is None or expected_kind != self.kind:
            raise ValueError("metric name or kind is not registered")
        if self.observed_at_ms < self.start_time_ms:
            raise ValueError("metric timestamps are out of order")
        for number in (self.value, self.total, self.minimum, self.maximum):
            if number is not None:
                _finite(number)
        if self.kind in {"counter", "gauge"}:
            if self.value is None or any(
                item is not None
                for item in (self.count, self.total, self.minimum, self.maximum)
            ) or self.bounds or self.bucket_counts:
                raise ValueError("scalar metric shape is invalid")
        else:
            if self.value is not None or self.count is None or self.total is None:
                raise ValueError("histogram metric shape is invalid")
            if len(self.bounds) > 64 or len(self.bucket_counts) != len(self.bounds) + 1:
                raise ValueError("histogram buckets are invalid")
            if sum(self.bucket_counts) != self.count:
                raise ValueError("histogram count does not match buckets")
            if sorted(self.bounds) != self.bounds:
                raise ValueError("histogram bounds are not ordered")
        return self


class LogRecord(StrictRecord):
    observed_at_ms: int = Field(ge=0)
    level: Literal["info", "warning", "error"]
    service: str
    event: str
    fields: dict[str, bool | int | float | str] = Field(default_factory=dict)

    @field_validator("service")
    @classmethod
    def _service(cls, value: str) -> str:
        """返回当前已绑定的服务实例。

        参数:
            `value`：待处理的值。

        返回:
            `str`，内容保持现有调用方契约。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
        if not SERVICE_NAME.fullmatch(value):
            raise ValueError("service name is invalid")
        return value

    @field_validator("event")
    @classmethod
    def _event(cls, value: str) -> str:
        """处理事件，并保持 `LogRecord` 的现有状态约束。

        参数:
            `value`：待处理的值。

        返回:
            `str`，内容保持现有调用方契约。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
        if value not in LOG_EVENTS:
            raise ValueError("log event is not registered")
        return value

    @field_validator("fields")
    @classmethod
    def _fields(
        cls, value: dict[str, Any]
    ) -> dict[str, bool | int | float | str]:
        """处理字段，并保持 `LogRecord` 的现有状态约束。"""
        return _safe_scalar_map(value, LOG_FIELDS, string_limit=128)


class SpanBatch(StrictRecord):
    records: list[SpanRecord] = Field(min_length=1, max_length=256)


class MetricBatch(StrictRecord):
    records: list[MetricRecord] = Field(min_length=1, max_length=256)


class LogBatch(StrictRecord):
    records: list[LogRecord] = Field(min_length=1, max_length=256)


def window_start_ms(window: str, *, now_ms: int | None = None) -> int:
    """根据查询窗口计算毫秒级起始时间。

    参数:
        `window`：查询时间窗口。
        `now_ms`：沿用签名中 `int | None` 类型约束的输入。

    返回:
        `int`，内容保持现有调用方契约。

    异常:
        `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
    duration = WINDOW_MILLISECONDS.get(window)
    if duration is None:
        raise ValueError("unsupported observability window")
    current = int(time.time() * 1_000) if now_ms is None else now_ms
    return max(0, current - duration)
