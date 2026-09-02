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
from urllib.parse import urlparse

from opentelemetry import context as otel_context
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
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
from pydantic import BaseModel, ConfigDict, Field, field_validator


TELEMETRY_SCHEMA_VERSION = "iteration4-aspect7-v1"
GENAI_SAFE_POLICY_VERSION = "otel-genai-safe-v1"
_TRACEPARENT = re.compile(r"^00-([0-9a-f]{32})-([0-9a-f]{16})-(00|01)$")
_SERVICE_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]{0,62}$")
_SPAN_NAME = re.compile(
    r"^(?:http\.agent_api|mcp\.request|agent\.(?:command(?:\.enqueue|\.worker)?|"
    r"run|graph\.[a-z_]+|plan|tool|retrieval|checkpoint|validation|recovery|sse)|"
    r"gen_ai\.(?:chat|embeddings))$"
)
_ATTRIBUTE_KEYS = frozenset(
    {
        "agent.cache", "agent.checkpoint.kind", "agent.command.kind",
        "agent.error.type", "agent.operation", "agent.retention", "agent.status",
        "agent.tool.name", "gen_ai.operation.name", "gen_ai.output.type",
        "gen_ai.provider.name", "gen_ai.request.model",
        "gen_ai.usage.input_tokens", "gen_ai.usage.output_tokens",
        "http.request.method", "retrieval.corpus", "retrieval.index.action",
        "retrieval.strategy", "server.address",
    }
)
_METRIC_LABEL_KEYS = frozenset(
    {
        "cache", "checkpoint_kind", "command_kind", "corpus", "model",
        "operation", "retention", "status", "strategy",
    }
)


class TelemetrySettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    enabled: bool = False
    endpoint: str = "http://127.0.0.1:4317"
    service_name: str = "ezllm-agent"
    export_timeout_ms: int = Field(default=2_000, ge=100, le=30_000)
    metric_interval_ms: int = Field(default=30_000, ge=1_000, le=300_000)

    @field_validator("service_name")
    @classmethod
    def _safe_service_name(cls, value: str) -> str:
        if not _SERVICE_NAME.fullmatch(value):
            raise ValueError("telemetry service name is invalid")
        return value

    @field_validator("endpoint")
    @classmethod
    def _controlled_endpoint(cls, value: str) -> str:
        parsed = urlparse(value)
        if (
            parsed.scheme != "http"
            or parsed.hostname
            not in {"127.0.0.1", "localhost", "::1", "otel-collector"}
            or parsed.port != 4317
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "OTLP endpoint must be the controlled loopback or Compose collector"
            )
        return value.rstrip("/")

    @classmethod
    def from_environment(
        cls, *, service_name: str = "ezllm-agent"
    ) -> "TelemetrySettings":
        import os

        enabled = os.environ.get("AGENT_TELEMETRY_ENABLED", "false").lower()
        if enabled not in {"true", "false", "1", "0"}:
            raise ValueError("AGENT_TELEMETRY_ENABLED must be true or false")

        def integer(name: str, default: int) -> int:
            raw = os.environ.get(name)
            if raw is None:
                return default
            try:
                return int(raw)
            except ValueError as exc:
                raise ValueError(f"{name} must be an integer") from exc

        return cls(
            enabled=enabled in {"true", "1"},
            endpoint=os.environ.get(
                "AGENT_OTLP_ENDPOINT", "http://127.0.0.1:4317"
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
        return self.traceparent.split("-", 3)[1]

    @property
    def span_id(self) -> str:
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
        self._delegate = delegate
        self._status = status

    def export(self, spans) -> SpanExportResult:
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
        try:
            result = self._delegate.force_flush(timeout_millis)
            return True if result is None else bool(result)
        except BaseException:
            self._status.failed_batches += 1
            self._status.last_error = "export_failed"
            return False

    def shutdown(self) -> None:
        try:
            self._delegate.shutdown()
        except BaseException:
            self._status.failed_batches += 1
            self._status.last_error = "export_failed"


class _SafeMetricExporter(MetricExporter):
    def __init__(
        self, delegate: MetricExporter, status: TelemetryExportStatus
    ) -> None:
        super().__init__()
        self._delegate = delegate
        self._status = status

    def export(self, metrics_data, timeout_millis: float = 10_000, **kwargs):
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
        try:
            result = self._delegate.force_flush(timeout_millis=timeout_millis)
            return True if result is None else bool(result)
        except BaseException:
            self._status.failed_batches += 1
            self._status.last_error = "metric_export_failed"
            return False

    def shutdown(self, timeout_millis: float = 30_000, **kwargs) -> None:
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
        self.settings = settings
        self.export_status = TelemetryExportStatus()
        self._tracer_provider: TracerProvider | None = None
        self._meter_provider: MeterProvider | None = None
        self._meter: Meter | None = None
        self._counters: dict[str, Any] = {}
        self._histograms: dict[str, Any] = {}
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
        raw_span_exporter = span_exporter or OTLPSpanExporter(
            endpoint=settings.endpoint,
            insecure=True,
            timeout=settings.export_timeout_ms / 1_000,
        )
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
        # metric exporter is also supplied.  It must never contact OTLP by surprise.
        if metric_exporter is None and span_exporter is not None:
            return
        raw_metric_exporter = metric_exporter or OTLPMetricExporter(
            endpoint=settings.endpoint,
            insecure=True,
            timeout=settings.export_timeout_ms / 1_000,
        )
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
        return self.settings.enabled

    @staticmethod
    def _attributes(values: Mapping[str, Any] | None) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for key, value in (values or {}).items():
            if key not in _ATTRIBUTE_KEYS:
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
        return {
            key: str(value)[:64]
            for key, value in (values or {}).items()
            if key in _METRIC_LABEL_KEYS and isinstance(value, (str, bool))
        }

    @contextmanager
    def span(
        self,
        name: str,
        attributes: Mapping[str, Any] | None = None,
        *,
        links: tuple[Link, ...] = (),
    ) -> Iterator[Any]:
        if not _SPAN_NAME.fullmatch(name):
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
        if not self.enabled or self._meter is None:
            return
        if not name.startswith("ezllm.agent."):
            raise ValueError("Agent metric name is invalid")
        instrument = self._counters.get(name)
        if instrument is None:
            instrument = self._meter.create_counter(name)
            self._counters[name] = instrument
        instrument.add(amount, self._labels(labels))

    def histogram(
        self, name: str, value: float, labels: Mapping[str, Any] | None = None
    ) -> None:
        if not self.enabled or self._meter is None:
            return
        if not name.startswith("ezllm.agent.") or value < 0:
            raise ValueError("Agent metric sample is invalid")
        instrument = self._histograms.get(name)
        if instrument is None:
            instrument = self._meter.create_histogram(name, unit="ms")
            self._histograms[name] = instrument
        instrument.record(value, self._labels(labels))

    def active_runs(
        self, delta: int, labels: Mapping[str, Any] | None = None
    ) -> None:
        if self._active_runs is not None:
            self._active_runs.add(delta, self._labels(labels))

    def force_flush(self, timeout_ms: int | None = None) -> bool:
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
    global _telemetry
    if _telemetry is None:
        with _telemetry_lock:
            if _telemetry is None:
                _telemetry = AgentTelemetry(TelemetrySettings.from_environment())
    return _telemetry


def replace_agent_telemetry_for_tests(
    value: AgentTelemetry | None,
) -> AgentTelemetry | None:
    global _telemetry
    previous = _telemetry
    _telemetry = value
    return previous


@contextmanager
def use_agent_trace(
    carrier: TraceCarrier | None = None,
) -> Iterator[AgentTelemetry]:
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
    telemetry = get_agent_telemetry()
    if not always and not _agent_trace_active.get():
        yield trace.INVALID_SPAN
        return
    with telemetry.span(name, attributes) as span:
        yield span


def current_agent_trace_carrier() -> TraceCarrier | None:
    if not _agent_trace_active.get():
        return None
    return get_agent_telemetry().current_trace_carrier()


def agent_trace_is_active() -> bool:
    return _agent_trace_active.get()


# 对外只返回脱敏的 telemetry 状态，不把 exporter 错误或 trace 内容暴露给客户端。
def telemetry_public_status() -> dict[str, Any]:
    telemetry = get_agent_telemetry()
    return {
        "mode": "enabled" if telemetry.enabled else "disabled",
        "schema_version": TELEMETRY_SCHEMA_VERSION,
        "genai_policy": GENAI_SAFE_POLICY_VERSION,
        "trace_status": (
            "instrumented" if telemetry.enabled else "not_instrumented"
        ),
    }
