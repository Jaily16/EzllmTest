# 手动记录低基数 Agent 遥测，避免自动采集框架、SQL 或模型正文。
"""Manual, low-cardinality OpenTelemetry for the Iteration 4 Agent.

Framework, Redis and SQLAlchemy auto-instrumentation are intentionally absent.
Only registered Agent boundaries and allowlisted attributes are recorded.
"""

from __future__ import annotations
from ezllmtest.platform.security.session_token import provider as token_provider

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

from ezllmtest.platform.telemetry.local_export import LocalMetricExporter, LocalSpanExporter, LocalTelemetryTransport
from ezllmtest.platform.telemetry.contracts import ATTRIBUTE_KEYS, GENAI_SAFE_POLICY_VERSION, METRIC_KINDS, METRIC_LABEL_KEYS, SERVICE_NAME, SPAN_NAME, TELEMETRY_SCHEMA_VERSION


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
        """限制服务名称形式，防止自由文本进入观测资源维度。"""
        if not SERVICE_NAME.fullmatch(value):
            raise ValueError("telemetry service name is invalid")
        return value

    @field_validator("local_url")
    @classmethod
    def _controlled_endpoint(cls, value: str) -> str:
        """校验本地受控端点并统一末尾斜线，不能通过配置转发到任意远程接收者。"""
        if value and not value.startswith(
            ("http://127.0.0.1:", "http://localhost:")
        ):
            raise ValueError("local telemetry endpoint must use loopback")
        return value.rstrip("/")

    @model_validator(mode="after")
    def _enabled_configuration(self) -> "TelemetrySettings":
        """启用遥测时要求有效端点和凭据来源；不可用不等于允许关闭接收端鉴权。"""
        if self.enabled and (
            not self.local_url
            or (not self.local_token and token_provider() is None)
            or any(character.isspace() for character in self.local_token)
        ):
            raise ValueError("local telemetry transport is not configured")
        return self

    @classmethod
    def from_environment(
        cls, *, service_name: str = "ezllm-agent"
    ) -> "TelemetrySettings":
        """从已装配进程快照读取遥测设置，不自动发现 .env 或读取其他角色秘密。"""
        import os
        from ezllmtest.platform import configuration as runtime_values

        enabled = runtime_values.get("AGENT_TELEMETRY_ENABLED", "false").lower()
        if enabled not in {"true", "false", "1", "0"}:
            raise ValueError("AGENT_TELEMETRY_ENABLED must be true or false")

        def integer(name: str, default: int) -> int:
            """从进程快照解析有界整数设置，缺失时使用明确默认值。"""
            raw = runtime_values.get(name)
            if raw is None:
                return default
            try:
                return int(raw)
            except ValueError as exc:
                raise ValueError(f"{name} must be an integer") from exc

        return cls(
            enabled=enabled in {"true", "1"},
            local_url=runtime_values.get(
                "EZLLMTEST_OBSERVABILITY_INGEST_URL", ""
            ),
            local_token=runtime_values.get(
                "EZLLMTEST_OBSERVABILITY_INGEST_TOKEN", ""
            ),
            service_name=runtime_values.get(
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
        """检查 traceparent 格式和非零身份，跨边界只传播标准关联信息。"""
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
        """包装实际 span exporter 并共享导出状态，导出失败由安全包装层隔离于业务执行。"""
        self._delegate = delegate
        self._status = status

    def export(self, spans) -> SpanExportResult:
        """捕获底层 span 导出失败并返回失败结果，避免观测异常打断 Agent 业务。"""
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
        """在指定超时内刷新 span 导出，异常只更新导出失败状态并返回 False。"""
        try:
            result = self._delegate.force_flush(timeout_millis)
            return True if result is None else bool(result)
        except BaseException:
            self._status.failed_batches += 1
            self._status.last_error = "export_failed"
            return False

    def shutdown(self) -> None:
        """关闭 span exporter 时隔离异常，不让观测关闭故障打断业务收尾。"""
        try:
            self._delegate.shutdown()
        except BaseException:
            self._status.failed_batches += 1
            self._status.last_error = "export_failed"


class _SafeMetricExporter(MetricExporter):
    def __init__(
        self, delegate: MetricExporter, status: TelemetryExportStatus
    ) -> None:
        """包装指标 exporter 并共享健康状态，后续导出异常记录为观测故障而非业务失败。"""
        super().__init__()
        self._delegate = delegate
        self._status = status

    def export(self, metrics_data, timeout_millis: float = 10_000, **kwargs):
        """把指标导出异常收敛为失败状态，业务调用不承担观测服务可用性。"""
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
        """刷新指标 exporter 并归一化返回值，异常记为指标投递失败。"""
        try:
            result = self._delegate.force_flush(timeout_millis=timeout_millis)
            return True if result is None else bool(result)
        except BaseException:
            self._status.failed_batches += 1
            self._status.last_error = "metric_export_failed"
            return False

    def shutdown(self, timeout_millis: float = 30_000, **kwargs) -> None:
        """关闭指标 exporter 并记录安全错误类别，不传播底层异常正文。"""
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
        """按显式开关装配本地 exporter、批处理和低基数指标；禁用时使用空 tracer。"""
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
        """仅选择白名单标量属性并限制文本长度，未知字段在生产侧投影时跳过。"""
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
        """指标标签仅保留白名单中的字符串或布尔值，并限制长度以控制基数。"""
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
        """只记录允许的名称、属性和稳定错误类别；异常正文与输入输出不作为 span 属性。"""
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
        """在上下文中临时附加可信 trace carrier，离开时恢复原上下文，避免并发运行串线。"""
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
        """只创建目录允许的计数器，并按低基数标签清单过滤属性。"""
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
        """只记录目录允许的直方图样本，标签不能来自自由业务文本。"""
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
        """以增减计数表达活跃运行数量，调用方须在结束路径配对收尾。"""
        if self._active_runs is not None:
            self._active_runs.add(delta, self._labels(labels))

    def force_flush(self, timeout_ms: int | None = None) -> bool:
        """逐个刷新 trace 和 metric provider，聚合成功结果，失败仅更新安全导出状态。"""
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
        """依次关闭观测 provider 并隔离异常；当前 timeout_ms 参数不会强制中断底层 shutdown。"""
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
    """把异常归类为固定低基数类型，不输出异常消息或具体业务内容。"""
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
    """在锁内惰性创建进程级遥测对象，配置来自已安装快照。"""
    global _telemetry
    if _telemetry is None:
        with _telemetry_lock:
            if _telemetry is None:
                _telemetry = AgentTelemetry(TelemetrySettings.from_environment())
    return _telemetry


def replace_agent_telemetry_for_tests(
    value: AgentTelemetry | None,
) -> AgentTelemetry | None:
    """测试显式替换遥测单例并返回旧对象，便于隔离用例结束后恢复。"""
    global _telemetry
    previous = _telemetry
    _telemetry = value
    return previous


@contextmanager
def use_agent_trace(
    carrier: TraceCarrier | None = None,
) -> Iterator[AgentTelemetry]:
    """在当前调用上下文绑定 Trace 传播载体，退出时还原激活状态。"""
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
    """仅在 Agent trace 上下文激活时建立受控 span，其余调用不隐式创建业务观测链。"""
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
    """仅公开遥测模式、策略版本和投递计数，不包含 token、事件正文或连接秘密。"""
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
