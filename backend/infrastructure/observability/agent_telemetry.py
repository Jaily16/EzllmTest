"""Manual, low-cardinality OpenTelemetry for the Iteration 4 Agent.

Framework, Redis and SQLAlchemy auto-instrumentation are intentionally absent.
Only registered Agent boundaries and allowlisted attributes are recorded.
"""

from __future__ import annotations

import re
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Iterator, Mapping

from opentelemetry import context as otel_context
from opentelemetry import trace
from opentelemetry.metrics import Meter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    MetricExportResult,
    MetricExporter,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SpanExportResult,
    SpanExporter,
)
from opentelemetry.trace import Link, Status, StatusCode
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from infrastructure.observability.local_export import (
    LocalMetricExporter,
    LocalSpanExporter,
    LocalTelemetryTransport,
)
from service.observability.contracts import (
    ATTRIBUTE_KEYS,
    GENAI_SAFE_POLICY_VERSION,
    METRIC_KINDS,
    METRIC_LABEL_KEYS,
    SERVICE_NAME,
    SPAN_NAME,
    TELEMETRY_SCHEMA_VERSION,
)


_TRACEPARENT = re.compile(r"^00-([0-9a-f]{32})-([0-9a-f]{16})-(00|01)$")


class TelemetrySettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    enabled: bool = False
    local_url: str = Field(default="", repr=False)
    local_token: str = Field(default="", repr=False)
    service_name: str = "ezllm-agent"
    export_timeout_ms: int = Field(default=2_000, ge=100, le=30_000)
    metric_interval_ms: int = Field(default=30_000, ge=1_000, le=300_000)

    @field_validator("service_name")
    @classmethod
    def _safe_service_name(cls, value: str) -> str:
        """将服务名称收敛为允许公开的安全形式。

        参数:
            `value`：待处理的值。

        返回:
            `str`，内容保持现有调用方契约。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
        if not SERVICE_NAME.fullmatch(value):
            raise ValueError("telemetry service name is invalid")
        return value

    @field_validator("local_url")
    @classmethod
    def _controlled_endpoint(cls, value: str) -> str:
        """处理controlled端点，并保持 `TelemetrySettings` 的现有状态约束。

        参数:
            `value`：待处理的值。

        返回:
            `str`，内容保持现有调用方契约。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
        if value and not value.startswith(
            ("http://127.0.0.1:", "http://localhost:")
        ):
            raise ValueError("local telemetry endpoint must use loopback")
        return value.rstrip("/")

    @model_validator(mode="after")
    def _enabled_configuration(self) -> "TelemetrySettings":
        """处理启用配置，并保持 `TelemetrySettings` 的现有状态约束。

        返回:
            `'TelemetrySettings'`，内容保持现有调用方契约。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
        if self.enabled and (
            not self.local_url
            or not self.local_token
            or any(character.isspace() for character in self.local_token)
        ):
            raise ValueError("local telemetry transport is not configured")
        return self

    @classmethod
    def from_environment(
        cls, *, service_name: str = "ezllm-agent"
    ) -> "TelemetrySettings":
        """从环境变量解析内部逻辑，并校验现有数据约束。

        参数:
            `service_name`：沿用签名中 `str` 类型约束的输入。

        返回:
            `'TelemetrySettings'`，内容保持现有调用方契约。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
        import os

        enabled = os.environ.get("AGENT_TELEMETRY_ENABLED", "false").lower()
        if enabled not in {"true", "false", "1", "0"}:
            raise ValueError("AGENT_TELEMETRY_ENABLED must be true or false")

        def integer(name: str, default: int) -> int:
            """读取并校验整数字段。

            参数:
                `name`：目标名称。
                `default`：沿用签名中 `int` 类型约束的输入。

            返回:
                `int`，内容保持现有调用方契约。

            异常:
                `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
            raw = os.environ.get(name)
            if raw is None:
                return default
            try:
                return int(raw)
            except ValueError as exc:
                raise ValueError(f"{name} must be an integer") from exc

        return cls(
            enabled=enabled in {"true", "1"},
            local_url=os.environ.get(
                "EZLLMTEST_OBSERVABILITY_INGEST_URL", ""
            ),
            local_token=os.environ.get(
                "EZLLMTEST_OBSERVABILITY_INGEST_TOKEN", ""
            ),
            service_name=os.environ.get(
                "AGENT_TELEMETRY_SERVICE_NAME", service_name
            ),
            export_timeout_ms=integer("AGENT_OTEL_EXPORT_TIMEOUT_MS", 2_000),
            metric_interval_ms=integer(
                "AGENT_OTEL_METRIC_INTERVAL_MS", 30_000
            ),
        )


class TraceCarrier(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    traceparent: str

    @field_validator("traceparent")
    @classmethod
    def _canonical_traceparent(cls, value: str) -> str:
        """处理规范traceparent，并保持 `TraceCarrier` 的现有状态约束。

        参数:
            `value`：待处理的值。

        返回:
            `str`，内容保持现有调用方契约。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
        match = _TRACEPARENT.fullmatch(value)
        if (
            match is None
            or int(match.group(1), 16) == 0
            or int(match.group(2), 16) == 0
        ):
            raise ValueError("traceparent is invalid")
        return value

    @property
    def trace_id(self) -> str:
        """返回当前Trace ID。"""
        return self.traceparent.split("-", 3)[1]

    @property
    def span_id(self) -> str:
        """返回当前Span ID。"""
        return self.traceparent.split("-", 3)[2]


@dataclass
class TelemetryExportStatus:
    exported_batches: int = 0
    failed_batches: int = 0
    dropped_batches: int = 0
    last_error: str | None = None


# telemetry 导出失败只能降级记录状态，不能泄露 prompt、凭证或阻断业务恢复路径。
class _SafeSpanExporter(SpanExporter):
    def __init__(self, delegate: SpanExporter, status: TelemetryExportStatus) -> None:
        """初始化实例并保存后续操作所需的依赖与状态。"""
        self._delegate = delegate
        self._status = status

    def export(self, spans) -> SpanExportResult:
        """导出当前批次的脱敏观测数据。

        参数:
            `spans`：调用方传入的现有参数。

        返回:
            `SpanExportResult`，内容保持现有调用方契约。

        副作用:
            可能向本地观测队列或 loopback 服务发送脱敏遥测副本。

        不变量:
            观测失败不得阻断业务，且禁止发送 prompt、项目正文、凭据或 traceback。"""
        try:
            result = self._delegate.export(spans)
        except BaseException:
            self._status.failed_batches += 1
            self._status.last_error = "export_failed"
            return SpanExportResult.FAILURE
        if result is SpanExportResult.SUCCESS:
            self._status.exported_batches += 1
        else:
            self._status.failed_batches += 1
            self._status.last_error = "export_failed"
        return result

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        """在既有超时边界内刷新待发送的观测数据。"""
        try:
            result = self._delegate.force_flush(timeout_millis)
            return True if result is None else bool(result)
        except BaseException:
            self._status.failed_batches += 1
            self._status.last_error = "export_failed"
            return False

    def shutdown(self) -> None:
        """关闭当前组件并释放其后台资源。"""
        try:
            self._delegate.shutdown()
        except BaseException:
            self._status.failed_batches += 1
            self._status.last_error = "export_failed"


class _SafeMetricExporter(MetricExporter):
    def __init__(
        self, delegate: MetricExporter, status: TelemetryExportStatus
    ) -> None:
        """初始化实例并保存后续操作所需的依赖与状态。"""
        super().__init__()
        self._delegate = delegate
        self._status = status

    def export(self, metrics_data, timeout_millis: float = 10_000, **kwargs):
        """导出当前批次的脱敏观测数据。

        参数:
            `metrics_data`：调用方传入的现有参数。
            `timeout_millis`：沿用签名中 `float` 类型约束的输入。
            `kwargs`：调用方传入的现有参数。

        副作用:
            可能向本地观测队列或 loopback 服务发送脱敏遥测副本。

        不变量:
            观测失败不得阻断业务，且禁止发送 prompt、项目正文、凭据或 traceback。"""
        try:
            result = self._delegate.export(
                metrics_data, timeout_millis=timeout_millis, **kwargs
            )
        except BaseException:
            self._status.failed_batches += 1
            self._status.last_error = "metric_export_failed"
            return MetricExportResult.FAILURE
        if result is MetricExportResult.SUCCESS:
            self._status.exported_batches += 1
        else:
            self._status.failed_batches += 1
            self._status.last_error = "metric_export_failed"
        return result

    def force_flush(self, timeout_millis: float = 10_000) -> bool:
        """在既有超时边界内刷新待发送的观测数据。"""
        try:
            result = self._delegate.force_flush(timeout_millis=timeout_millis)
            return True if result is None else bool(result)
        except BaseException:
            self._status.failed_batches += 1
            self._status.last_error = "metric_export_failed"
            return False

    def shutdown(self, timeout_millis: float = 30_000, **kwargs) -> None:
        """关闭当前组件并释放其后台资源。"""
        try:
            self._delegate.shutdown(timeout_millis=timeout_millis, **kwargs)
        except BaseException:
            self._status.failed_batches += 1
            self._status.last_error = "metric_export_failed"


class AgentTelemetry:
    """Private SDK providers keep tests and benchmarks out of global state."""

    def __init__(
        self,
        settings: TelemetrySettings,
        *,
        span_exporter: SpanExporter | None = None,
        metric_exporter: MetricExporter | None = None,
    ) -> None:
        """初始化实例并保存后续操作所需的依赖与状态。

        参数:
            `settings`：沿用签名中 `TelemetrySettings` 类型约束的输入。
            `span_exporter`：沿用签名中 `SpanExporter | None` 类型约束的输入。
            `metric_exporter`：沿用签名中 `MetricExporter | None` 类型约束的输入。

        副作用:
            可能向本地观测队列或 loopback 服务发送脱敏遥测副本。

        不变量:
            观测失败不得阻断业务，且禁止发送 prompt、项目正文、凭据或 traceback。"""
        self.settings = settings
        self.export_status = TelemetryExportStatus()
        self._tracer_provider: TracerProvider | None = None
        self._meter_provider: MeterProvider | None = None
        self._meter: Meter | None = None
        self._counters: dict[str, Any] = {}
        self._histograms: dict[str, Any] = {}
        self._up_down_counters: dict[str, Any] = {}
        self._active_runs = None
        if not settings.enabled:
            self.tracer = trace.NoOpTracerProvider().get_tracer("ezllm.agent")
            return
        resource = Resource.create(
            {
                "service.name": settings.service_name,
                "telemetry.schema.version": TELEMETRY_SCHEMA_VERSION,
            }
        )
        provider = TracerProvider(resource=resource)
        transport = LocalTelemetryTransport(
            settings.local_url,
            settings.local_token,
            timeout_ms=settings.export_timeout_ms,
        )
        raw_span_exporter = span_exporter or LocalSpanExporter(transport)
        provider.add_span_processor(
            BatchSpanProcessor(
                _SafeSpanExporter(raw_span_exporter, self.export_status),
                max_queue_size=2_048,
                max_export_batch_size=256,
                schedule_delay_millis=min(1_000, settings.export_timeout_ms),
                export_timeout_millis=settings.export_timeout_ms,
            )
        )
        self._tracer_provider = provider
        self.tracer = provider.get_tracer(
            "ezllm.agent", TELEMETRY_SCHEMA_VERSION
        )
        # A supplied span exporter means an isolated trace-only test unless a
        # metric exporter is also supplied. It must never contact local I/O by surprise.
        if metric_exporter is None and span_exporter is not None:
            return
        raw_metric_exporter = metric_exporter or LocalMetricExporter(transport)
        reader = PeriodicExportingMetricReader(
            _SafeMetricExporter(raw_metric_exporter, self.export_status),
            export_interval_millis=settings.metric_interval_ms,
            export_timeout_millis=settings.export_timeout_ms,
        )
        self._meter_provider = MeterProvider(
            resource=resource, metric_readers=[reader]
        )
        self._meter = self._meter_provider.get_meter(
            "ezllm.agent", TELEMETRY_SCHEMA_VERSION
        )
        self._active_runs = self._meter.create_up_down_counter(
            "ezllm.agent.runs.active", unit="{run}"
        )

    @property
    def enabled(self) -> bool:
        """返回当前启用。"""
        return self.settings.enabled

    @staticmethod
    def _attributes(values: Mapping[str, Any] | None) -> dict[str, Any]:
        """构造符合允许清单的安全属性。"""
        output: dict[str, Any] = {}
        for key, value in (values or {}).items():
            if key not in ATTRIBUTE_KEYS:
                continue
            if isinstance(value, bool):
                output[key] = value
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                output[key] = value
            elif isinstance(value, str) and len(value) <= 128:
                output[key] = value
        return output

    @staticmethod
    def _labels(values: Mapping[str, Any] | None) -> dict[str, str]:
        """构造符合低基数约束的指标标签。"""
        return {
            key: str(value)[:64]
            for key, value in (values or {}).items()
            if key in METRIC_LABEL_KEYS and isinstance(value, (str, bool))
        }

    @contextmanager
    def span(
        self,
        name: str,
        attributes: Mapping[str, Any] | None = None,
        *,
        links: tuple[Link, ...] = (),
    ) -> Iterator[Any]:
        """处理Span，并保持 `AgentTelemetry` 的现有状态约束。

        参数:
            `name`：目标名称。
            `attributes`：沿用签名中 `Mapping[str, Any] | None` 类型约束的输入。
            `links`：沿用签名中 `tuple[Link, ...]` 类型约束的输入。

        返回:
            `Iterator[Any]`，内容保持现有调用方契约。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
        if not SPAN_NAME.fullmatch(name):
            raise ValueError("Agent span name is not registered")
        with self.tracer.start_as_current_span(
            name,
            attributes=self._attributes(attributes),
            links=links,
            record_exception=False,
            set_status_on_exception=False,
        ) as span:
            try:
                yield span
            except BaseException as exc:
                if span.is_recording():
                    span.set_attribute("agent.error.type", _stable_error_type(exc))
                    span.set_status(Status(StatusCode.ERROR))
                raise

    def current_trace_carrier(self) -> TraceCarrier | None:
        """返回当前遥测上下文的 Trace 传播载体。"""
        if not self.enabled:
            return None
        context = trace.get_current_span().get_span_context()
        if not context.is_valid:
            return None
        return TraceCarrier(
            traceparent=(
                f"00-{context.trace_id:032x}-{context.span_id:016x}-"
                f"{'01' if context.trace_flags.sampled else '00'}"
            )
        )

    @contextmanager
    def attach(self, carrier: TraceCarrier | None) -> Iterator[None]:
        """附加内部逻辑，并遵循现有调用契约。

        参数:
            `carrier`：沿用签名中 `TraceCarrier | None` 类型约束的输入。

        返回:
            `Iterator[None]`，内容保持现有调用方契约。"""
        if carrier is None:
            yield
            return
        parts = carrier.traceparent.split("-")
        span_context = trace.SpanContext(
            trace_id=int(parts[1], 16),
            span_id=int(parts[2], 16),
            is_remote=True,
            trace_flags=(
                trace.TraceFlags(1)
                if parts[3] == "01"
                else trace.TraceFlags(0)
            ),
            trace_state=trace.TraceState(),
        )
        token = otel_context.attach(
            trace.set_span_in_context(trace.NonRecordingSpan(span_context))
        )
        try:
            yield
        finally:
            otel_context.detach(token)

    def counter(
        self,
        name: str,
        amount: int = 1,
        labels: Mapping[str, Any] | None = None,
    ) -> None:
        """处理计数器，并保持 `AgentTelemetry` 的现有状态约束。

        参数:
            `name`：目标名称。
            `amount`：沿用签名中 `int` 类型约束的输入。
            `labels`：沿用签名中 `Mapping[str, Any] | None` 类型约束的输入。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
        if not self.enabled or self._meter is None:
            return
        kind = METRIC_KINDS.get(name)
        if kind not in {"counter", "gauge"}:
            raise ValueError("Agent metric name is invalid")
        instruments = self._counters if kind == "counter" else self._up_down_counters
        instrument = instruments.get(name)
        if instrument is None:
            instrument = (
                self._meter.create_counter(name)
                if kind == "counter"
                else self._meter.create_up_down_counter(name)
            )
            instruments[name] = instrument
        instrument.add(amount, self._labels(labels))

    def histogram(
        self, name: str, value: float, labels: Mapping[str, Any] | None = None
    ) -> None:
        """处理直方图，并保持 `AgentTelemetry` 的现有状态约束。

        参数:
            `name`：目标名称。
            `value`：待处理的值。
            `labels`：沿用签名中 `Mapping[str, Any] | None` 类型约束的输入。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
        if not self.enabled or self._meter is None:
            return
        if METRIC_KINDS.get(name) != "histogram" or value < 0:
            raise ValueError("Agent metric sample is invalid")
        instrument = self._histograms.get(name)
        if instrument is None:
            instrument = self._meter.create_histogram(name, unit="ms")
            self._histograms[name] = instrument
        instrument.record(value, self._labels(labels))

    def active_runs(
        self, delta: int, labels: Mapping[str, Any] | None = None
    ) -> None:
        """处理活跃运行，并保持 `AgentTelemetry` 的现有状态约束。"""
        if self._active_runs is not None:
            self._active_runs.add(delta, self._labels(labels))

    def force_flush(self, timeout_ms: int | None = None) -> bool:
        """在既有超时边界内刷新待发送的观测数据。"""
        timeout = timeout_ms or self.settings.export_timeout_ms
        okay = True
        for provider, error in (
            (self._tracer_provider, "export_failed"),
            (self._meter_provider, "metric_export_failed"),
        ):
            if provider is None:
                continue
            try:
                okay = bool(provider.force_flush(timeout)) and okay
            except BaseException:
                self.export_status.failed_batches += 1
                self.export_status.last_error = error
                okay = False
        return okay

    def shutdown(self, timeout_ms: int | None = None) -> None:
        """关闭当前组件并释放其后台资源。"""
        del timeout_ms
        for provider, error in (
            (self._meter_provider, "metric_export_failed"),
            (self._tracer_provider, "export_failed"),
        ):
            if provider is None:
                continue
            try:
                provider.shutdown()
            except BaseException:
                self.export_status.failed_batches += 1
                self.export_status.last_error = error


def _stable_error_type(exc: BaseException) -> str:
    """处理stable错误类型并返回现有契约规定的结果。"""
    name = type(exc).__name__.lower()
    if "cancel" in name:
        return "cancelled"
    if isinstance(exc, (ValueError, TypeError)):
        return "validation_error"
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return "transient_error"
    return "internal_error"


_telemetry_lock = threading.Lock()
_telemetry: AgentTelemetry | None = None
_agent_trace_active: ContextVar[bool] = ContextVar(
    "ezllm_agent_trace_active", default=False
)


def get_agent_telemetry() -> AgentTelemetry:
    """获取agent遥测，并遵循现有调用契约。"""
    global _telemetry
    if _telemetry is None:
        with _telemetry_lock:
            if _telemetry is None:
                _telemetry = AgentTelemetry(TelemetrySettings.from_environment())
    return _telemetry


def replace_agent_telemetry_for_tests(
    value: AgentTelemetry | None,
) -> AgentTelemetry | None:
    """为测试构造replace agent遥测。"""
    global _telemetry
    previous = _telemetry
    _telemetry = value
    return previous


@contextmanager
def use_agent_trace(
    carrier: TraceCarrier | None = None,
) -> Iterator[AgentTelemetry]:
    """临时绑定agent Trace，并遵循现有调用契约。"""
    telemetry = get_agent_telemetry()
    token = _agent_trace_active.set(True)
    try:
        with telemetry.attach(carrier):
            yield telemetry
    finally:
        _agent_trace_active.reset(token)


@contextmanager
def agent_span(
    name: str,
    attributes: Mapping[str, Any] | None = None,
    *,
    always: bool = False,
) -> Iterator[Any]:
    """处理agent Span并返回现有契约规定的结果。"""
    telemetry = get_agent_telemetry()
    if not always and not _agent_trace_active.get():
        yield trace.INVALID_SPAN
        return
    with telemetry.span(name, attributes) as span:
        yield span


def current_agent_trace_carrier() -> TraceCarrier | None:
    """返回当前 Agent Trace 的传播载体。"""
    if not _agent_trace_active.get():
        return None
    return get_agent_telemetry().current_trace_carrier()


def agent_trace_is_active() -> bool:
    """判断当前上下文是否存在有效 Agent Trace。"""
    return _agent_trace_active.get()


# 对外只返回脱敏的 telemetry 状态，不把 exporter 错误或 trace 内容暴露给客户端。
def telemetry_public_status() -> dict[str, Any]:
    """返回当前遥测公开状态。

    返回:
        `dict[str, Any]`，内容保持现有调用方契约。"""
    telemetry = get_agent_telemetry()
    return {
        "mode": "local" if telemetry.enabled else "disabled",
        "schema_version": TELEMETRY_SCHEMA_VERSION,
        "genai_policy": GENAI_SAFE_POLICY_VERSION,
        "trace_status": (
            "instrumented" if telemetry.enabled else "not_instrumented"
        ),
        "delivery": {
            "exported_batches": telemetry.export_status.exported_batches,
            "failed_batches": telemetry.export_status.failed_batches,
            "dropped_batches": telemetry.export_status.dropped_batches,
            "status": (
                "degraded" if telemetry.export_status.failed_batches else "ok"
            ),
        },
    }
