"""Fail-open local HTTP exporters with strict, content-free serialization."""

from __future__ import annotations

import atexit
import json
import os
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

from service.observability.contracts import (
    ATTRIBUTE_KEYS,
    LOG_FIELDS,
    METRIC_KINDS,
    LogRecord,
    MetricRecord,
    SpanRecord,
)


class LocalTelemetryTransport:
    """Bounded loopback transport; callers receive only a boolean outcome."""

    def __init__(self, base_url: str, token: str, *, timeout_ms: int) -> None:
        """初始化实例并保存后续操作所需的依赖与状态。

        参数:
            `base_url`：沿用签名中 `str` 类型约束的输入。
            `token`：沿用签名中 `str` 类型约束的输入。
            `timeout_ms`：沿用签名中 `int` 类型约束的输入。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
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
        if not token or any(character.isspace() for character in token):
            raise ValueError("local telemetry token is invalid")
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout_ms / 1_000
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def post(self, kind: str, records: Iterable[dict[str, Any]]) -> bool:
        """向 loopback 观测 ingestion 端点发送一个脱敏批次。

        参数:
            `kind`：沿用签名中 `str` 类型约束的输入。
            `records`：沿用签名中 `Iterable[dict[str, Any]]` 类型约束的输入。

        返回:
            `bool`，内容保持现有调用方契约。"""
        if kind not in {"spans", "metrics", "logs"}:
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
                    "X-EzllmTest-Ingest-Token": self.token,
                },
                method="POST",
            )
            with self.opener.open(request, timeout=self.timeout) as response:
                return response.status == 202
        except (OSError, ValueError, urllib.error.URLError):
            return False

    def post_chunks(self, kind: str, records: list[dict[str, Any]]) -> bool:
        """按批次上限拆分并发送脱敏观测记录。

        参数:
            `kind`：沿用签名中 `str` 类型约束的输入。
            `records`：沿用签名中 `list[dict[str, Any]]` 类型约束的输入。

        返回:
            `bool`，内容保持现有调用方契约。

        副作用:
            可能向本地观测队列或 loopback 服务发送脱敏遥测副本。

        不变量:
            观测失败不得阻断业务，且禁止发送 prompt、项目正文、凭据或 traceback。"""
        return all(
            self.post(kind, records[start : start + 256])
            for start in range(0, len(records), 256)
        )


def _service(resource: Any) -> str:
    """返回当前已绑定的服务实例。"""
    attributes = getattr(resource, "attributes", {}) or {}
    value = attributes.get("service.name", "ezllm-agent")
    return str(value)[:63]


class LocalSpanExporter(SpanExporter):
    def __init__(self, transport: LocalTelemetryTransport) -> None:
        """初始化实例并保存后续操作所需的依赖与状态。"""
        self.transport = transport

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
        """关闭当前组件并释放其后台资源。"""
        return None


class LocalMetricExporter(MetricExporter):
    def __init__(self, transport: LocalTelemetryTransport) -> None:
        """初始化实例并保存后续操作所需的依赖与状态。"""
        super().__init__()
        self.transport = transport
        self._previous: dict[tuple[Any, ...], tuple[Any, ...]] = {}

    @staticmethod
    def _labels(point: Any) -> dict[str, str]:
        """构造符合低基数约束的指标标签。"""
        return {
            str(key): str(value)[:64]
            for key, value in dict(getattr(point, "attributes", {}) or {}).items()
        }

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
        """在既有超时边界内刷新待发送的观测数据。"""
        del timeout_millis
        return True

    def shutdown(self, timeout_millis: float = 30_000, **kwargs) -> None:
        """关闭当前组件并释放其后台资源。"""
        del timeout_millis, kwargs


class _LocalLogSink:
    def __init__(self, transport: LocalTelemetryTransport) -> None:
        """初始化实例并保存后续操作所需的依赖与状态。

        参数:
            `transport`：沿用签名中 `LocalTelemetryTransport` 类型约束的输入。

        副作用:
            可能向本地观测队列或 loopback 服务发送脱敏遥测副本。

        不变量:
            观测失败不得阻断业务，且禁止发送 prompt、项目正文、凭据或 traceback。"""
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
        """发送内部逻辑，并遵循现有调用契约。

        参数:
            `payload`：符合现有契约的载荷。

        副作用:
            可能向本地观测队列或 loopback 服务发送脱敏遥测副本。

        不变量:
            观测失败不得阻断业务，且禁止发送 prompt、项目正文、凭据或 traceback。"""
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
        """执行当前组件封装的单次内部任务。

        副作用:
            可能向本地观测队列或 loopback 服务发送脱敏遥测副本。

        不变量:
            观测失败不得阻断业务，且禁止发送 prompt、项目正文、凭据或 traceback。"""
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
        """关闭当前组件并释放其后台资源。"""
        self.stop_event.set()
        self.thread.join(timeout=1.5)


_sink_lock = threading.Lock()
_sink: _LocalLogSink | None = None


def _transport_from_environment() -> LocalTelemetryTransport | None:
    """从环境变量解析传输层，并校验现有数据约束。

    返回:
        `LocalTelemetryTransport | None`，内容保持现有调用方契约。

    副作用:
        可能向本地观测队列或 loopback 服务发送脱敏遥测副本。

    不变量:
        观测失败不得阻断业务，且禁止发送 prompt、项目正文、凭据或 traceback。"""
    enabled = os.environ.get("AGENT_TELEMETRY_ENABLED", "false").casefold()
    if enabled not in {"true", "1"}:
        return None
    url = os.environ.get("EZLLMTEST_OBSERVABILITY_INGEST_URL", "")
    token = os.environ.get("EZLLMTEST_OBSERVABILITY_INGEST_TOKEN", "")
    try:
        timeout = int(os.environ.get("AGENT_OTEL_EXPORT_TIMEOUT_MS", "2000"))
        return LocalTelemetryTransport(url, token, timeout_ms=timeout)
    except (TypeError, ValueError):
        return None


def emit_safe_log(payload: dict[str, Any]) -> None:
    """发送安全日志，并遵循现有调用契约。

    参数:
        `payload`：符合现有契约的载荷。

    副作用:
        可能向本地观测队列或 loopback 服务发送脱敏遥测副本。

    不变量:
        观测失败不得阻断业务，且禁止发送 prompt、项目正文、凭据或 traceback。"""
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
    """关闭安全日志接收器，并遵循现有调用契约。"""
    global _sink
    with _sink_lock:
        if _sink is not None:
            _sink.shutdown()
            _sink = None


atexit.register(shutdown_safe_log_sink)
