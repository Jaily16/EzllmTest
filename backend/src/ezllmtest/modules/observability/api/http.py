# 本机观测 HTTP 边界：ingestion 始终校验 token，查询只返回脱敏存储投影。
"""Independent loopback API for the Iteration 6 local observability UI."""

from __future__ import annotations

import asyncio
import hmac
import inspect
import json
from ezllmtest.platform import configuration as runtime_values
import time
import urllib.error
import urllib.request
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ezllmtest.modules.observability.ports.storage import ObservabilityStorageError, ObservabilityStore
from ezllmtest.platform.telemetry.contracts import LogBatch, MetricBatch, SpanBatch, TRACE_ID
from ezllmtest.modules.observability.schemas.query import OBSERVABILITY_SCHEMA_VERSION, WINDOW_MILLISECONDS, window_start_ms
from ezllmtest.modules.observability.application.overview import build_metric_overview


OBSERVABILITY_HOST = "127.0.0.1"
MAX_BODY_BYTES = 1_048_576
HealthProbe = Callable[[], dict[str, Any] | Awaitable[dict[str, Any]]]


def _payload(status: str, data: Any = None) -> dict[str, Any]:
    """把状态和数据封装到带观测 schema 版本的响应信封。"""
    return {
        "schema_version": OBSERVABILITY_SCHEMA_VERSION,
        "status": status,
        "data": data,
    }


class LoopbackHostMiddleware:
    def __init__(self, app, *, allow_test_host: bool = False) -> None:
        """仅允许本机 Host；testserver 必须由测试装配显式启用，不放宽生产请求的来源限制。"""
        self.app = app
        self.allowed = {"127.0.0.1", "localhost", "[::1]"}
        if allow_test_host:
            self.allowed.add("testserver")

    async def __call__(self, scope, receive, send) -> None:
        """只允许本机 HTTP/WebSocket Host，非法来源直接返回 421，后续鉴权仍照常执行。"""
        if scope["type"] in {"http", "websocket"}:
            headers = dict(scope.get("headers", ()))
            raw_host = headers.get(b"host", b"").decode("ascii", "ignore")
            if raw_host.startswith("["):
                host = raw_host.split("]", 1)[0] + "]"
            else:
                host = raw_host.rsplit(":", 1)[0] if ":" in raw_host else raw_host
            if host.casefold() not in self.allowed:
                response = JSONResponse(
                    status_code=421,
                    content=_payload("host_rejected"),
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


class ContentLengthMiddleware:
    def __init__(self, app) -> None:
        """保存下游 ASGI 应用，载荷长度限制在每次请求进入时执行。"""
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        """在读取 ingestion 载荷前约束请求长度，避免超大数据占满观测进程。"""
        if scope["type"] == "http" and scope.get("method") == "POST":
            headers = dict(scope.get("headers", ()))
            raw = headers.get(b"content-length", b"").decode("ascii", "ignore")
            if raw and (not raw.isdecimal() or int(raw) > MAX_BODY_BYTES):
                response = JSONResponse(
                    status_code=413,
                    content=_payload("payload_too_large"),
                )
                await response(scope, receive, send)
                return

            messages: list[dict[str, Any]] = []
            actual_size = 0
            while True:
                message = await receive()
                messages.append(message)
                if message["type"] == "http.disconnect":
                    break
                if message["type"] != "http.request":
                    continue
                actual_size += len(message.get("body", b""))
                if actual_size > MAX_BODY_BYTES:
                    response = JSONResponse(
                        status_code=413,
                        content=_payload("payload_too_large"),
                    )
                    await response(scope, receive, send)
                    return
                if not message.get("more_body", False):
                    break

            message_index = 0

            async def replay_receive() -> dict[str, Any]:
                """按顺序向下游重放已校验长度的请求体消息，耗尽后返回终止帧。"""
                nonlocal message_index
                if message_index < len(messages):
                    message = messages[message_index]
                    message_index += 1
                    return message
                return {"type": "http.request", "body": b"", "more_body": False}

            await self.app(scope, replay_receive, send)
            return

        await self.app(scope, receive, send)


def _http_json(url: str) -> tuple[int | None, dict[str, Any]]:
    """以一秒超时读取最多 64 KiB 的健康响应，非 JSON 或超大内容按无结构化数据处理。"""
    try:
        request = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(request, timeout=1.0) as response:
            body = response.read(65_537)
            if len(body) > 65_536:
                return response.status, {}
            try:
                parsed = json.loads(body.decode("utf-8"))
            except (UnicodeError, json.JSONDecodeError):
                parsed = {}
            return response.status, parsed if isinstance(parsed, dict) else {}
    except (OSError, ValueError, urllib.error.URLError):
        return None, {}


async def _default_health_probe() -> dict[str, Any]:
    """并发探测产品、Agent 和前端公开健康端点，汇总状态时不查询项目正文或任务队列。"""
    (legacy_status, legacy), (agent_status, agent), (frontend_status, _) = (
        await asyncio.gather(
            asyncio.to_thread(
                _http_json, runtime_values.get("EZLLMTEST_LEGACY_READY_URL", "")
            ),
            asyncio.to_thread(
                _http_json, runtime_values.get("EZLLMTEST_AGENT_READY_URL", "")
            ),
            asyncio.to_thread(
                _http_json, runtime_values.get("EZLLMTEST_FRONTEND_URL", "")
            ),
        )
    )
    legacy_checks = legacy.get("checks", {}) if isinstance(legacy, dict) else {}
    agent_checks = agent.get("checks", {}) if isinstance(agent, dict) else {}
    return {
        "frontend": "ok" if frontend_status == 200 else "unavailable",
        "legacy-api": "ok" if legacy_status == 200 else "unavailable",
        "agent-api": "ok" if agent_status == 200 else "unavailable",
        "worker": (
            "ok" if agent_checks.get("worker") == "available" else "unavailable"
        ),
        "mysql": "ok" if legacy_checks.get("database") == "ok" else "unavailable",
        "redis": "ok" if agent_checks.get("redis") == "ok" else "unavailable",
    }


async def _resolve_health(probe: HealthProbe) -> dict[str, Any]:
    """兼容同步及异步健康探针，同步探针放入线程避免阻塞事件循环。"""
    if not inspect.iscoroutinefunction(probe):
        return await asyncio.to_thread(probe)
    result = probe()
    if asyncio.iscoroutine(result):
        return await result
    return result


def create_observability_app(
    store: ObservabilityStore,
    *,
    ingest_token: str,
    allowed_origins: tuple[str, ...],
    health_probe: HealthProbe = _default_health_probe,
    allow_test_host: bool = False,
    cleanup_interval_seconds: float = 3_600,
) -> FastAPI:
    """装配本地查询与受鉴权 ingestion；存储只在 lifespan 打开，公开异常采用安全信封。"""
    if not ingest_token or any(character.isspace() for character in ingest_token):
        raise ValueError("observability ingest token is invalid")

    stop_cleanup = asyncio.Event()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        """打开本实例观测存储并在退出时关闭，原有保留策略由存储生命周期负责。"""
        store.open()
        await asyncio.to_thread(store.cleanup)

        async def cleanup_loop() -> None:
            """按间隔执行 SQLite 保留清理，停止信号可结束等待；存储清理失败留待下轮重试。"""
            while not stop_cleanup.is_set():
                try:
                    await asyncio.wait_for(
                        stop_cleanup.wait(), timeout=cleanup_interval_seconds
                    )
                except TimeoutError:
                    try:
                        await asyncio.to_thread(store.cleanup)
                    except ObservabilityStorageError:
                        continue

        task = asyncio.create_task(cleanup_loop())
        try:
            yield
        finally:
            stop_cleanup.set()
            await task
            store.close()

    app = FastAPI(
        title="EzllmTest Local Observability API",
        version=OBSERVABILITY_SCHEMA_VERSION,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(allowed_origins),
        allow_credentials=False,
        allow_methods=["GET", "OPTIONS"],
        allow_headers=["Content-Type"],
    )
    app.add_middleware(ContentLengthMiddleware)
    app.add_middleware(LoopbackHostMiddleware, allow_test_host=allow_test_host)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, _exc: RequestValidationError):
        """把输入校验异常转换为稳定错误类别，不回显原始字段值。"""
        return JSONResponse(
            status_code=422,
            content=_payload("validation_failed"),
        )

    @app.exception_handler(ObservabilityStorageError)
    async def storage_error(_request: Request, _exc: ObservabilityStorageError):
        """将存储不可用映射为安全响应，不泄露 SQLite 路径或 SQL 正文。"""
        return JSONResponse(
            status_code=503,
            content=_payload("storage_unavailable"),
        )

    @app.exception_handler(HTTPException)
    async def http_error(_request: Request, exc: HTTPException):
        """保留协议状态码并收敛响应内容，避免任意异常细节进入页面。"""
        return JSONResponse(
            status_code=exc.status_code,
            content=_payload(
                "ingest_forbidden" if exc.status_code == 403 else "request_rejected"
            ),
        )

    @app.exception_handler(Exception)
    async def internal_error(_request: Request, _exc: Exception):
        """对未预期异常返回固定错误，不向客户端泄露堆栈和数据。"""
        return JSONResponse(
            status_code=500,
            content=_payload("request_failed_safely"),
        )

    def authorize(token: str | None) -> None:
        """验证 ingestion 的内存 token；缺失或错误必须拒绝，查询可用性不能绕过此边界。"""
        if token is None or not hmac.compare_digest(token, ingest_token):
            raise HTTPException(status_code=403, detail="ingest_forbidden")

    # 返回观测进程存活标记，不把此接口等同于 SQLite 就绪。
    @app.get("/health", description="\f")
    async def health():
        """\f
        处理 `GET /health` 请求，并沿用既有状态码、响应 schema 与安全边界。"""
        return _payload("ok", {"service": "observability-api"})

    # 根据本地存储就绪结果返回 200 或 503，失败只报告安全状态。
    @app.get("/ready", description="\f")
    async def ready():
        """\f
        处理 `GET /ready` 请求，并沿用既有状态码、响应 schema 与安全边界。"""
        okay = await asyncio.to_thread(store.ready)
        return JSONResponse(
            status_code=200 if okay else 503,
            content=_payload(
                "ready" if okay else "not_ready",
                {"checks": {"storage": "ok" if okay else "unavailable"}},
            ),
        )

    # 公开查询窗口、分页上限与七天/十万行保留策略，不暴露内部 token。
    @app.get("/observability/v1/capabilities", description="\f")
    async def capabilities():
        """\f
        处理 `GET /observability/v1/capabilities` 请求，并沿用既有状态码、响应 schema 与安全边界。"""
        return _payload(
            "success",
            {
                "windows": list(WINDOW_MILLISECONDS),
                "default_window": "1h",
                "maximum_page_size": 200,
                "retention_days": store.retention_days,
                "maximum_rows": store.max_rows,
                "row_limits": {
                    "spans": store.span_limit,
                    "metrics": store.metric_limit,
                    "logs": store.log_limit,
                },
                "content_policy": "metadata_only",
            },
        )

    # 并发读取健康状态、窗口指标和存储计数，再进行纯聚合生成总览。
    @app.get("/observability/v1/overview", description="\f")
    async def overview(
        window: str = Query(default="1h", pattern="^(?:15m|1h|6h|24h|7d)$")
    ):
        """\f
        处理 `GET /observability/v1/overview` 请求，并沿用既有状态码、响应 schema 与安全边界。

        参数:
            `window`：查询时间窗口。"""
        now_ms = int(time.time() * 1_000)
        since_ms = window_start_ms(window, now_ms=now_ms)
        health_state, metrics, counts = await asyncio.gather(
            _resolve_health(health_probe),
            asyncio.to_thread(store.metrics_since, since_ms),
            asyncio.to_thread(store.counts),
        )
        return _payload(
            "success",
            {
                "generated_at_ms": now_ms,
                "window": window,
                "health": {"observability-api": "ok", **health_state},
                "storage": counts,
                "metrics": build_metric_overview(
                    metrics, since_ms=since_ms, now_ms=now_ms
                ),
            },
        )

    # 校验查询窗口和筛选后返回 trace 摘要，不在列表接口重放业务或返回全部细节。
    @app.get("/observability/v1/traces", description="\f")
    async def traces(
        window: str = Query(default="1h", pattern="^(?:15m|1h|6h|24h|7d)$"),
        status: str | None = Query(default=None, pattern="^(?:ok|error)$"),
        limit: int = Query(default=50, ge=1, le=200),
        before: int | None = Query(default=None, ge=1),
    ):
        """\f
        处理 `GET /observability/v1/traces` 请求，并沿用既有状态码、响应 schema 与安全边界。

        参数:
            `window`：查询时间窗口。
            `status`：沿用签名中 `str | None` 类型约束的输入。
            `limit`：结果数量上限。
            `before`：分页游标上界。"""
        items = await asyncio.to_thread(
            store.trace_summaries,
            since_ms=window_start_ms(window),
            status=status,
            limit=limit,
            before=before,
        )
        return _payload("success", {"items": items, "next": items[-1]["cursor"] if items else None})

    # 校验 Trace ID 后读取详情，非法 ID 返回 422，已不存在记录返回 404。
    @app.get("/observability/v1/traces/{trace_id}", description="\f")
    async def trace_detail(trace_id: str):
        """\f
        处理 `GET /observability/v1/traces/{trace_id}` 请求，并沿用既有状态码、响应 schema 与安全边界。

        参数:
            `trace_id`：Trace ID。"""
        if not TRACE_ID.fullmatch(trace_id):
            return JSONResponse(status_code=422, content=_payload("invalid_trace_id"))
        item = await asyncio.to_thread(store.trace_detail, trace_id)
        if item is None:
            return JSONResponse(status_code=404, content=_payload("trace_not_found"))
        return _payload("success", item)

    # 返回有界的脱敏日志列表，窗口和过滤条件受 API schema 限制。
    @app.get("/observability/v1/logs", description="\f")
    async def logs(
        window: str = Query(default="1h", pattern="^(?:15m|1h|6h|24h|7d)$"),
        level: str | None = Query(default=None, pattern="^(?:info|warning|error)$"),
        service: str | None = Query(
            default=None,
            min_length=1,
            max_length=63,
            pattern="^[a-z0-9][a-z0-9._-]*$",
        ),
        limit: int = Query(default=50, ge=1, le=200),
        before: int | None = Query(default=None, ge=1),
    ):
        """\f
        处理 `GET /observability/v1/logs` 请求，并沿用既有状态码、响应 schema 与安全边界。

        参数:
            `window`：查询时间窗口。
            `level`：沿用签名中 `str | None` 类型约束的输入。
            `service`：沿用签名中 `str | None` 类型约束的输入。
            `limit`：结果数量上限。
            `before`：分页游标上界。"""
        items = await asyncio.to_thread(
            store.logs,
            since_ms=window_start_ms(window),
            level=level,
            service=service,
            limit=limit,
            before=before,
        )
        return _payload("success", {"items": items, "next": items[-1]["cursor"] if items else None})

    # 先鉴权并校验 span 批次，再交给本地存储；禁止绕过共享脱敏 schema。
    @app.post("/internal/v1/telemetry/spans", status_code=202, description="\f")
    async def ingest_spans(
        batch: SpanBatch,
        token: str | None = Header(default=None, alias="X-EzllmTest-Ingest-Token"),
    ):
        """\f
        处理 `POST /internal/v1/telemetry/spans` 请求，并沿用既有状态码、响应 schema 与安全边界。

        参数:
            `batch`：沿用签名中 `SpanBatch` 类型约束的输入。
            `token`：沿用签名中 `str | None` 类型约束的输入。"""
        authorize(token)
        inserted = await asyncio.to_thread(store.insert_spans, batch.records)
        return _payload("accepted", {"accepted": inserted})

    # 鉴权后接收允许的指标批次，任意标签或不合法桶结构不得写入。
    @app.post("/internal/v1/telemetry/metrics", status_code=202, description="\f")
    async def ingest_metrics(
        batch: MetricBatch,
        token: str | None = Header(default=None, alias="X-EzllmTest-Ingest-Token"),
    ):
        """\f
        处理 `POST /internal/v1/telemetry/metrics` 请求，并沿用既有状态码、响应 schema 与安全边界。

        参数:
            `batch`：沿用签名中 `MetricBatch` 类型约束的输入。
            `token`：沿用签名中 `str | None` 类型约束的输入。"""
        authorize(token)
        inserted = await asyncio.to_thread(store.insert_metrics, batch.records)
        return _payload("accepted", {"accepted": inserted})

    # 鉴权后保存固定事件和字段组成的日志，不接收自由异常或模型正文。
    @app.post("/internal/v1/telemetry/logs", status_code=202, description="\f")
    async def ingest_logs(
        batch: LogBatch,
        token: str | None = Header(default=None, alias="X-EzllmTest-Ingest-Token"),
    ):
        """\f
        处理 `POST /internal/v1/telemetry/logs` 请求，并沿用既有状态码、响应 schema 与安全边界。

        参数:
            `batch`：沿用签名中 `LogBatch` 类型约束的输入。
            `token`：沿用签名中 `str | None` 类型约束的输入。"""
        authorize(token)
        inserted = await asyncio.to_thread(store.insert_logs, batch.records)
        return _payload("accepted", {"accepted": inserted})

    return app
