"""Independent loopback API for the Iteration 6 local observability UI."""

from __future__ import annotations

import argparse
import asyncio
import hmac
import inspect
import json
import os
import re
import time
import urllib.error
import urllib.request
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from infrastructure.observability.storage import (
    ObservabilityStorageError,
    ObservabilityStore,
)
from service.observability.contracts import (
    LogBatch,
    MetricBatch,
    OBSERVABILITY_SCHEMA_VERSION,
    SpanBatch,
    TRACE_ID,
    WINDOW_MILLISECONDS,
    window_start_ms,
)
from service.observability.overview import build_metric_overview


OBSERVABILITY_HOST = "127.0.0.1"
MAX_BODY_BYTES = 1_048_576
HealthProbe = Callable[[], dict[str, Any] | Awaitable[dict[str, Any]]]


def _payload(status: str, data: Any = None) -> dict[str, Any]:
    """构造内部逻辑载荷。"""
    return {
        "schema_version": OBSERVABILITY_SCHEMA_VERSION,
        "status": status,
        "data": data,
    }


class LoopbackHostMiddleware:
    def __init__(self, app, *, allow_test_host: bool = False) -> None:
        """初始化实例并保存后续操作所需的依赖与状态。"""
        self.app = app
        self.allowed = {"127.0.0.1", "localhost", "[::1]"}
        if allow_test_host:
            self.allowed.add("testserver")

    async def __call__(self, scope, receive, send) -> None:
        """以可调用对象形式执行该实例封装的处理流程。"""
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
        """初始化实例并保存后续操作所需的依赖与状态。"""
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        """以可调用对象形式执行该实例封装的处理流程。

        参数:
            `scope`：调用方传入的现有参数。
            `receive`：调用方传入的现有参数。
            `send`：调用方传入的现有参数。"""
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
                """回放receive，并遵循现有调用契约。"""
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
    """通过 loopback HTTP 获取并校验安全 JSON 响应。"""
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
    """探测本地托管模块的健康状态并返回降级安全结果。

    返回:
        `dict[str, Any]`，内容保持现有调用方契约。"""
    (legacy_status, legacy), (agent_status, agent), (frontend_status, _) = (
        await asyncio.gather(
            asyncio.to_thread(
                _http_json, os.environ.get("EZLLMTEST_LEGACY_READY_URL", "")
            ),
            asyncio.to_thread(
                _http_json, os.environ.get("EZLLMTEST_AGENT_READY_URL", "")
            ),
            asyncio.to_thread(
                _http_json, os.environ.get("EZLLMTEST_FRONTEND_URL", "")
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
    """解析健康状态，并遵循现有调用契约。"""
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
    """构建 loopback-only 本地观测 API，并绑定安全查询与 ingestion 契约。

    参数:
        `store`：沿用签名中 `ObservabilityStore` 类型约束的输入。
        `ingest_token`：沿用签名中 `str` 类型约束的输入。
        `allowed_origins`：沿用签名中 `tuple[str, ...]` 类型约束的输入。
        `health_probe`：沿用签名中 `HealthProbe` 类型约束的输入。
        `allow_test_host`：沿用签名中 `bool` 类型约束的输入。
        `cleanup_interval_seconds`：沿用签名中 `float` 类型约束的输入。

    返回:
        `FastAPI`，内容保持现有调用方契约。

    异常:
        `ValueError, HTTPException`：输入、状态或下游结果不满足现有约束时抛出。

    副作用:
        可能访问本地观测 SQLite；不得读取或写入产品业务数据。

    不变量:
        只接受允许字段，并保持保留期、行数上限与完整 Trace 删除约束。"""
    if not ingest_token or any(character.isspace() for character in ingest_token):
        raise ValueError("observability ingest token is invalid")

    stop_cleanup = asyncio.Event()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        """管理 FastAPI 应用启动与关闭期间的资源生命周期。

        参数:
            `_app`：沿用签名中 `FastAPI` 类型约束的输入。

        副作用:
            可能访问本地观测 SQLite；不得读取或写入产品业务数据。

        不变量:
            只接受允许字段，并保持保留期、行数上限与完整 Trace 删除约束。"""
        store.open()
        await asyncio.to_thread(store.cleanup)

        async def cleanup_loop() -> None:
            """清理LOOP，并遵循现有调用契约。"""
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
        """处理validation错误并返回现有契约规定的结果。"""
        return JSONResponse(
            status_code=422,
            content=_payload("validation_failed"),
        )

    @app.exception_handler(ObservabilityStorageError)
    async def storage_error(_request: Request, _exc: ObservabilityStorageError):
        """处理存储错误并返回现有契约规定的结果。"""
        return JSONResponse(
            status_code=503,
            content=_payload("storage_unavailable"),
        )

    @app.exception_handler(HTTPException)
    async def http_error(_request: Request, exc: HTTPException):
        """处理HTTP错误并返回现有契约规定的结果。"""
        return JSONResponse(
            status_code=exc.status_code,
            content=_payload(
                "ingest_forbidden" if exc.status_code == 403 else "request_rejected"
            ),
        )

    @app.exception_handler(Exception)
    async def internal_error(_request: Request, _exc: Exception):
        """处理内部错误并返回现有契约规定的结果。"""
        return JSONResponse(
            status_code=500,
            content=_payload("request_failed_safely"),
        )

    def authorize(token: str | None) -> None:
        """校验本地观测 ingestion token，拒绝未授权写入。

        参数:
            `token`：沿用签名中 `str | None` 类型约束的输入。

        异常:
            `HTTPException`：输入、状态或下游结果不满足现有约束时抛出。"""
        if token is None or not hmac.compare_digest(token, ingest_token):
            raise HTTPException(status_code=403, detail="ingest_forbidden")

    @app.get("/health", description="\f")
    async def health():
        """\f
        处理 `GET /health` 请求，并沿用既有状态码、响应 schema 与安全边界。"""
        return _payload("ok", {"service": "observability-api"})

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


def build_parser() -> argparse.ArgumentParser:
    """构建当前命令行入口的参数解析器。"""
    parser = argparse.ArgumentParser(description="EzllmTest local observability API")
    parser.add_argument("--port", type=int)
    return parser


def main(argv: list[str] | None = None) -> int:
    """解析命令行参数并执行当前模块的本地入口。

    参数:
        `argv`：沿用签名中 `list[str] | None` 类型约束的输入。

    返回:
        `int`，内容保持现有调用方契约。

    异常:
        `SystemExit`：输入、状态或下游结果不满足现有约束时抛出。"""
    args = build_parser().parse_args(argv)
    host = os.environ.get("OBSERVABILITY_HOST", OBSERVABILITY_HOST)
    port = args.port or int(os.environ.get("OBSERVABILITY_PORT", "8140"))
    if host != OBSERVABILITY_HOST or not 1 <= port <= 65_535:
        raise SystemExit("observability_config:loopback_or_port_required")
    path = Path(os.environ["OBSERVABILITY_DATABASE_PATH"])
    store = ObservabilityStore(
        path,
        retention_days=int(os.environ.get("OBSERVABILITY_RETENTION_DAYS", "7")),
        max_rows=int(os.environ.get("OBSERVABILITY_MAX_ROWS", "100000")),
    )
    token = os.environ.get("EZLLMTEST_OBSERVABILITY_INGEST_TOKEN", "")
    origins = tuple(
        item.strip()
        for item in os.environ.get(
            "OBSERVABILITY_CORS_ORIGINS",
            "http://127.0.0.1:8180,http://localhost:8180",
        ).split(",")
        if item.strip()
    )
    app = create_observability_app(
        store,
        ingest_token=token,
        allowed_origins=origins,
    )
    uvicorn.run(app, host=host, port=port, log_level="warning", access_log=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
