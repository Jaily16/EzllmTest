# 把已脱敏遥测投递到本机观测端，token 重取与导出失败不能阻断业务。
"""Fail-open local HTTP exporters with strict, content-free serialization."""

from __future__ import annotations
from ezllmtest.platform.security.session_token import provider as token_provider

import atexit
import json
import os
from ezllmtest.platform import configuration as runtime_values
import queue
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any, Iterable
from urllib.parse import urlsplit

from opentelemetry.sdk.metrics.export import MetricExportResult, MetricExporter
from opentelemetry.sdk.trace.export import SpanExportResult, SpanExporter

from ezllmtest.platform.telemetry.contracts import ATTRIBUTE_KEYS, LOG_FIELDS, METRIC_KINDS, LogRecord, MetricRecord, SpanRecord


class LocalTelemetryTransport:
    """Bounded loopback transport; callers receive only a boolean outcome."""

    def __init__(self, base_url: str, token: str, *, timeout_ms: int) -> None:
        """限制投递目标为本地受控端点，禁用环境代理并设置超时；凭据仅保留在本进程对象中。"""
        try:
            parsed = urlsplit(base_url)
            valid = (
                parsed.scheme == "http"
                and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
                and parsed.port is not None
                and 1 <= parsed.port <= 65_535
                and parsed.username is None
                and parsed.password is None
                and parsed.path in {"", "/"}
                and not parsed.query
                and not parsed.fragment
            )
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("local telemetry endpoint must use loopback")
        if (not token and token_provider() is None) or any(character.isspace() for character in token):
            raise ValueError("local telemetry token is invalid")
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout_ms / 1_000
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def post(self, kind: str, records: Iterable[dict[str, Any]]) -> bool:
        """对脱敏记录构造有界批次，使用内存凭据投递；鉴权失败使缓存失效，传输错误返回失败而不阻断产品。"""
        if kind not in {"spans", "metrics", "logs"}:
            return False
        credentials = token_provider()
        token = credentials.get() if credentials is not None else self.token
        if not token:
            return False
        items = list(records)
        if not 1 <= len(items) <= 256:
            return False
        try:
            payload = json.dumps(
                {"records": items},
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            if len(payload) > 1_048_576:
                return False
            request = urllib.request.Request(
                f"{self.base_url}/internal/v1/telemetry/{kind}",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Content-Length": str(len(payload)),
                    "X-EzllmTest-Ingest-Token": token,
                },
                method="POST",
            )
            with self.opener.open(request, timeout=self.timeout) as response:
                return response.status == 202
        except (OSError, ValueError, urllib.error.URLError):
            if credentials is not None:
                credentials.invalidate()
            return False

    def post_chunks(self, kind: str, records: list[dict[str, Any]]) -> bool:
        """每批最多发送 256 条记录，逐批返回综合结果，避免单个 HTTP 请求无限膨胀。"""
        return all(
            self.post(kind, records[start : start + 256])
            for start in range(0, len(records), 256)
        )


def _service(resource: Any) -> str:
    """从资源中提取服务名并限制长度，未提供时使用既有默认服务标签。"""
    attributes = getattr(resource, "attributes", {}) or {}
    value = attributes.get("service.name", "ezllm-agent")
    return str(value)[:63]


class LocalSpanExporter(SpanExporter):
    def __init__(self, transport: LocalTelemetryTransport) -> None:
        """复用本地遥测传输对象，由传输层统一处理鉴权、IPC token 和投递失败。"""
        self.transport = transport

    def export(self, spans) -> SpanExportResult:
        """从 OTel span 提取共享 schema 允许字段后投递，禁止属性不进入传输结果。"""
        records: list[dict[str, Any]] = []
        try:
            for span in spans:
                context = span.context
                parent = span.parent
                attributes = {
                    key: value
                    for key, value in dict(span.attributes or {}).items()
                    if key in ATTRIBUTE_KEYS
                }
                item = SpanRecord(
                    trace_id=f"{context.trace_id:032x}",
                    span_id=f"{context.span_id:016x}",
                    parent_span_id=(
                        f"{parent.span_id:016x}" if parent is not None and parent.is_valid else None
                    ),
                    service=_service(span.resource),
                    name=span.name,
                    started_at_ms=span.start_time // 1_000_000,
                    ended_at_ms=span.end_time // 1_000_000,
                    duration_ms=(span.end_time - span.start_time) / 1_000_000,
                    status=str(span.status.status_code.name).lower(),
                    attributes=attributes,
                )
                records.append(item.model_dump(mode="json"))
            return (
                SpanExportResult.SUCCESS
                if records and self.transport.post_chunks("spans", records)
                else SpanExportResult.FAILURE
            )
        except (TypeError, ValueError):
            return SpanExportResult.FAILURE

    def shutdown(self) -> None:
        """同步本地 span exporter 没有独立后台资源，shutdown 是接口兼容的空操作。"""
        return None


class LocalMetricExporter(MetricExporter):
    def __init__(self, transport: LocalTelemetryTransport) -> None:
        """复用本地遥测传输并初始化上次指标快照，用于避免重复发送未变化的数据点。"""
        super().__init__()
        self.transport = transport
        self._previous: dict[tuple[Any, ...], tuple[Any, ...]] = {}

    @staticmethod
    def _labels(point: Any) -> dict[str, str]:
        """把指标点标签转为受限长度文本，后续 wire schema 继续校验允许字段。"""
        return {
            str(key): str(value)[:64]
            for key, value in dict(getattr(point, "attributes", {}) or {}).items()
        }

    def export(self, metrics_data, timeout_millis: float = 10_000, **kwargs):
        """把允许的计数和直方图转换为本地 wire 记录，并维护累计到增量的状态；不发送任意观测对象。"""
        del timeout_millis, kwargs
        records: list[dict[str, Any]] = []
        try:
            for resource_metrics in metrics_data.resource_metrics:
                service = _service(resource_metrics.resource)
                for scope_metrics in resource_metrics.scope_metrics:
                    for metric in scope_metrics.metrics:
                        data = metric.data
                        for point in data.data_points:
                            labels = self._labels(point)
                            observed = int(point.time_unix_nano // 1_000_000)
                            started = int(point.start_time_unix_nano // 1_000_000)
                            key = (
                                service,
                                metric.name,
                                tuple(sorted(labels.items())),
                                started,
                            )
                            if hasattr(point, "bucket_counts"):
                                current = (
                                    int(point.count),
                                    float(point.sum),
                                    tuple(int(value) for value in point.bucket_counts),
                                )
                                previous = self._previous.get(key)
                                if previous is None or current[0] < previous[0]:
                                    count, total, buckets = current
                                else:
                                    count = current[0] - previous[0]
                                    total = current[1] - previous[1]
                                    buckets = tuple(
                                        current[2][index] - previous[2][index]
                                        for index in range(len(current[2]))
                                    )
                                self._previous[key] = current
                                if count == 0:
                                    continue
                                item = MetricRecord(
                                    observed_at_ms=observed,
                                    start_time_ms=started,
                                    service=service,
                                    name=metric.name,
                                    kind="histogram",
                                    count=count,
                                    total=total,
                                    minimum=(
                                        float(point.min) if point.min is not None else None
                                    ),
                                    maximum=(
                                        float(point.max) if point.max is not None else None
                                    ),
                                    bounds=[float(value) for value in point.explicit_bounds],
                                    bucket_counts=list(buckets),
                                    labels=labels,
                                )
                            else:
                                current_value = float(point.value)
                                if METRIC_KINDS.get(metric.name) == "gauge":
                                    value = current_value
                                    kind = "gauge"
                                else:
                                    previous = self._previous.get(key)
                                    value = (
                                        current_value
                                        if previous is None or current_value < float(previous[0])
                                        else current_value - float(previous[0])
                                    )
                                    kind = "counter"
                                self._previous[key] = (current_value,)
                                if kind == "counter" and value == 0:
                                    continue
                                item = MetricRecord(
                                    observed_at_ms=observed,
                                    start_time_ms=started,
                                    service=service,
                                    name=metric.name,
                                    kind=kind,
                                    value=value,
                                    labels=labels,
                                )
                            records.append(item.model_dump(mode="json"))
            return (
                MetricExportResult.SUCCESS
                if not records or self.transport.post_chunks("metrics", records)
                else MetricExportResult.FAILURE
            )
        except (AttributeError, IndexError, TypeError, ValueError):
            return MetricExportResult.FAILURE

    def force_flush(self, timeout_millis: float = 10_000) -> bool:
        """本地指标 exporter 同步投递，无待刷缓冲；force_flush 直接成功。"""
        del timeout_millis
        return True

    def shutdown(self, timeout_millis: float = 30_000, **kwargs) -> None:
        """本地指标 exporter 不持有独立后台线程，关闭参数仅为 SDK 接口兼容。"""
        del timeout_millis, kwargs


class _LocalLogSink:
    def __init__(self, transport: LocalTelemetryTransport) -> None:
        """建立有界队列和后台投递线程，日志生产者不在业务调用栈中等待 HTTP。"""
        self.transport = transport
        self.queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=1_024)
        self.stop_event = threading.Event()
        self.thread = threading.Thread(
            target=self._run,
            name="ezllm-local-log-export",
            daemon=True,
        )
        self.thread.start()

    def emit(self, payload: dict[str, Any]) -> None:
        """校验安全日志结构后非阻塞入队，队列满或格式错误只影响观测。"""
        try:
            timestamp = datetime.fromisoformat(str(payload["timestamp"]))
            fields = {
                key: value for key, value in payload.items() if key in LOG_FIELDS
            }
            record = LogRecord(
                observed_at_ms=int(timestamp.timestamp() * 1_000),
                level=str(payload["level"]),
                service=str(payload["service"]),
                event=str(payload["event"]),
                fields=fields,
            )
            self.queue.put_nowait(record.model_dump(mode="json"))
        except (KeyError, TypeError, ValueError, queue.Full):
            return

    def _run(self) -> None:
        """从有界队列收集小批次并通过本地传输发送，停止信号负责结束后台循环。"""
        while not self.stop_event.is_set():
            records: list[dict[str, Any]] = []
            try:
                records.append(self.queue.get(timeout=1.0))
            except queue.Empty:
                continue
            while len(records) < 64:
                try:
                    records.append(self.queue.get_nowait())
                except queue.Empty:
                    break
            self.transport.post("logs", records)

    def shutdown(self) -> None:
        """通知日志线程停止并最多等待 1.5 秒，避免退出阶段无限阻塞。"""
        self.stop_event.set()
        self.thread.join(timeout=1.5)


_sink_lock = threading.Lock()
_sink: _LocalLogSink | None = None


def _transport_from_environment() -> LocalTelemetryTransport | None:
    """仅在已装配快照启用遥测时创建本机传输，凭据提供者和超时按显式配置衔接，不发现 dotenv。"""
    enabled = runtime_values.get("AGENT_TELEMETRY_ENABLED", "false").casefold()
    if enabled not in {"true", "1"}:
        return None
    url = runtime_values.get("EZLLMTEST_OBSERVABILITY_INGEST_URL", "")
    token = runtime_values.get("EZLLMTEST_OBSERVABILITY_INGEST_TOKEN", "")
    try:
        timeout = int(runtime_values.get("AGENT_OTEL_EXPORT_TIMEOUT_MS", "2000"))
        return LocalTelemetryTransport(url, token, timeout_ms=timeout)
    except (TypeError, ValueError):
        return None


def emit_safe_log(payload: dict[str, Any]) -> None:
    """仅在遥测可用时延迟建立日志 sink，投递失败不传播为业务异常。"""
    global _sink
    if _sink is None:
        with _sink_lock:
            if _sink is None:
                transport = _transport_from_environment()
                if transport is None:
                    return
                _sink = _LocalLogSink(transport)
    _sink.emit(payload)


def shutdown_safe_log_sink() -> None:
    """正常关闭后台日志 sink 并清空进程引用，不删除已存观测数据。"""
    global _sink
    with _sink_lock:
        if _sink is not None:
            _sink.shutdown()
            _sink = None


atexit.register(shutdown_safe_log_sink)
