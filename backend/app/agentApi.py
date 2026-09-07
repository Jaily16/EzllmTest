"""Independent loopback API for the Iteration 4 Agent workbench."""

from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import os
import time
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, Header, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from service.agent.contracts import ApprovalDecision, TrustedProjectScope
from service.agent.runtime_contracts import AGENT_GRAPH_VERSION
from service.agent.factory import build_default_workbench_service
from service.agent.workbench_contracts import (
    AGENT_ACTOR_ID,
    AGENT_API_SCHEMA_VERSION,
    AGENT_SCOPE_VERSION,
    AgentApprovalRequest,
    AgentEditRequest,
    AgentRunCreateRequest,
    public_capabilities,
)
from service.agent.workbench_service import AgentRunConflict, AgentWorkbenchService
from infrastructure.observability.agent_telemetry import (
    agent_span,
    get_agent_telemetry,
    telemetry_public_status,
    use_agent_trace,
)


AGENT_API_HOST = "127.0.0.1"
READINESS_SCHEMA_VERSION = "iteration5-readiness-v1"
_TERMINAL = frozenset({"completed", "cancelled", "failed"})
ProjectExists = Callable[[str], bool | Awaitable[bool]]


def _envelope(status: str, reason: str, data: Any) -> dict[str, Any]:
    """构造符合 Agent API schema 的响应信封。"""
    return {"status": status, "reason": reason, "data": data}


def _response(
    status_code: int, status: str, reason: str, data: Any = None
) -> JSONResponse:
    """将服务结果转换为既有 HTTP 响应。"""
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(_envelope(status, reason, data)),
    )


class AgentApiError(Exception):
    def __init__(self, status_code: int, code: str, reason: str) -> None:
        """初始化实例并保存后续操作所需的依赖与状态。"""
        super().__init__(reason)
        self.status_code = status_code
        self.code = code
        self.reason = reason


class LoopbackHostMiddleware:
    """Reject non-loopback Host headers without exposing configuration."""

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
            if host.lower() not in self.allowed:
                response = _response(
                    421,
                    "agent_host_rejected",
                    "Agent API accepts loopback hosts only",
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


class AgentTelemetryMiddleware:
    """Manual HTTP boundary with no URL, header, body, or project attributes."""

    def __init__(self, app) -> None:
        """初始化实例并保存后续操作所需的依赖与状态。"""
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        """以可调用对象形式执行该实例封装的处理流程。

        参数:
            `scope`：调用方传入的现有参数。
            `receive`：调用方传入的现有参数。
            `send`：调用方传入的现有参数。"""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if scope.get("path") in {"/health", "/ready"}:
            await self.app(scope, receive, send)
            return
        method = str(scope.get("method", "GET"))[:16]
        with use_agent_trace():
            with agent_span(
                "http.agent_api",
                {
                    "http.request.method": method,
                    "server.address": "agent-api",
                },
                always=True,
            ):
                await self.app(scope, receive, send)


async def _default_project_exists(pid: str) -> bool:
    """构造默认项目存在。"""
    from dao import testProjectDao

    return await asyncio.to_thread(testProjectDao.find_project, pid) is not None


async def _resolve_bool(value: bool | Awaitable[bool]) -> bool:
    """解析BOOL，并遵循现有调用契约。"""
    return bool(await value) if inspect.isawaitable(value) else bool(value)


def _scope(pid: str) -> TrustedProjectScope:
    """处理作用域并返回现有契约规定的结果。"""
    return TrustedProjectScope(
        project_id=pid,
        actor_id=AGENT_ACTOR_ID,
        scope_version=AGENT_SCOPE_VERSION,
    )


# Agent SSE 以单调 sequence 支持断线恢复；payload 只包含允许展示的状态和脱敏错误。
def _sse_event(sequence: int, payload: dict[str, Any]) -> bytes:
    """编码符合现有事件名与 JSON 结构的 SSE 帧。"""
    content = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return (
        f"id: {sequence}\nevent: agent_event\ndata: {content}\n\n"
    ).encode("utf-8")


# Agent API 的审批、取消和恢复入口必须共享项目 scope 与 idempotency 校验。
def create_agent_api_app(
    service: AgentWorkbenchService | None = None,
    *,
    project_exists: ProjectExists | None = None,
    allowed_origins: tuple[str, ...] | None = None,
    allow_test_host: bool = False,
    heartbeat_seconds: float = 15.0,
    poll_seconds: float = 0.25,
) -> FastAPI:
    """构建 loopback-only Agent API，并绑定现有运行服务与错误处理契约。

    参数:
        `service`：沿用签名中 `AgentWorkbenchService | None` 类型约束的输入。
        `project_exists`：沿用签名中 `ProjectExists | None` 类型约束的输入。
        `allowed_origins`：沿用签名中 `tuple[str, ...] | None` 类型约束的输入。
        `allow_test_host`：沿用签名中 `bool` 类型约束的输入。
        `heartbeat_seconds`：沿用签名中 `float` 类型约束的输入。
        `poll_seconds`：沿用签名中 `float` 类型约束的输入。

    返回:
        `FastAPI`，内容保持现有调用方契约。

    异常:
        `AgentApiError`：输入、状态或下游结果不满足现有约束时抛出。"""
    owns_service = service is None
    workbench = service or build_default_workbench_service()
    project_check = project_exists or _default_project_exists

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        """管理 FastAPI 应用启动与关闭期间的资源生命周期。"""
        yield
        if owns_service:
            await workbench.runtime.coordinator.aclose()

    app = FastAPI(
        title="EzLLM Test Agent API",
        version="iteration4-aspect4-v1",
        lifespan=lifespan,
    )
    app.state.agent_workbench = workbench
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(
            allowed_origins
            or tuple(
                origin.strip()
                for origin in os.environ.get(
                    "CORS_ORIGINS", "http://127.0.0.1:8180,http://localhost:8180"
                ).split(",")
                if origin.strip()
            )
        ),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Last-Event-ID"],
    )
    app.add_middleware(
        LoopbackHostMiddleware, allow_test_host=allow_test_host
    )
    app.add_middleware(AgentTelemetryMiddleware)

    async def trusted_scope(pid: str) -> TrustedProjectScope:
        """根据项目与 source revision 构造可信 Agent 作用域。

        参数:
            `pid`：项目 ID。

        返回:
            `TrustedProjectScope`，内容保持现有调用方契约。

        异常:
            `AgentApiError`：输入、状态或下游结果不满足现有约束时抛出。"""
        if not await _resolve_bool(project_check(pid)):
            raise AgentApiError(
                404,
                "agent_project_not_found",
                "Project was not found",
            )
        return _scope(pid)

    async def existing_run(pid: str, thread_id: str):
        """读取并校验指定项目下的现有 Agent 运行。

        参数:
            `pid`：项目 ID。
            `thread_id`：Agent 运行线程 ID。

        异常:
            `AgentApiError`：输入、状态或下游结果不满足现有约束时抛出。"""
        scope = await trusted_scope(pid)
        view = await workbench.get_run(scope, thread_id)
        if view is None:
            raise AgentApiError(
                404,
                "agent_thread_not_found_or_expired",
                "Agent thread was not found or has expired",
            )
        return scope, view

    @app.exception_handler(AgentApiError)
    async def agent_api_error_handler(_request: Request, exc: AgentApiError):
        """处理agent API错误异常或事件，并转换为既有安全响应。"""
        return _response(exc.status_code, exc.code, exc.reason)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request, _exc: RequestValidationError
    ):
        """处理validation错误异常或事件，并转换为既有安全响应。"""
        return _response(
            422,
            "agent_validation_error",
            "Agent request validation failed",
        )

    @app.exception_handler(Exception)
    async def internal_error_handler(_request: Request, _exc: Exception):
        """处理内部错误异常或事件，并转换为既有安全响应。"""
        return _response(
            500,
            "agent_internal_error",
            "Agent request failed safely",
        )

    @app.get("/health", description="\f")
    async def health():
        """\f
        处理 `GET /health` 请求，并沿用既有状态码、响应 schema 与安全边界。"""
        redis_ok = False
        try:
            redis_ok = bool(await workbench.store.redis.ping())
        except Exception:
            redis_ok = False
        worker_ok = await workbench.store.worker_available() if redis_ok else False
        return _envelope(
            "success" if redis_ok else "agent_unavailable",
            "Agent API health",
            {
                "redis": "ok" if redis_ok else "unavailable",
                "worker": "available" if worker_ok else "unavailable",
                "schema_version": AGENT_API_SCHEMA_VERSION,
                "graph_version": AGENT_GRAPH_VERSION,
                "telemetry": telemetry_public_status(),
            },
        )

    @app.get("/ready")
    async def readiness():
        """Return only loopback-safe Redis and worker readiness state.\f
        处理 `GET /ready` 请求，并沿用既有状态码、响应 schema 与安全边界。"""
        redis_ok = False
        try:
            redis_ok = bool(await workbench.store.redis.ping())
        except Exception:
            redis_ok = False
        worker_ok = False
        if redis_ok:
            try:
                worker_ok = bool(await workbench.store.worker_available())
            except Exception:
                worker_ok = False
        ready = redis_ok and worker_ok
        return JSONResponse(
            status_code=200 if ready else 503,
            content={
                "schema_version": READINESS_SCHEMA_VERSION,
                "service": "agent-api",
                "status": "ready" if ready else "not_ready",
                "checks": {
                    "redis": "ok" if redis_ok else "unavailable",
                    "worker": "available" if worker_ok else "unavailable",
                },
            },
        )

    @app.get("/agent/v1/capabilities", description="\f")
    async def capabilities():
        """\f
        处理 `GET /agent/v1/capabilities` 请求，并沿用既有状态码、响应 schema 与安全边界。"""
        return _envelope(
            "success", "Agent capabilities", public_capabilities()
        )

    @app.get("/agent/v1/projects/{pid}/runs", description="\f")
    async def list_runs(
        pid: str,
        limit: int = Query(default=20, ge=1, le=50),
        before: int | None = Query(default=None, ge=1),
    ):
        """\f
        处理 `GET /agent/v1/projects/{pid}/runs` 请求，并沿用既有状态码、响应 schema 与安全边界。

        参数:
            `pid`：项目 ID。
            `limit`：结果数量上限。
            `before`：分页游标上界。"""
        scope = await trusted_scope(pid)
        result = await workbench.list_runs(scope, limit=limit, before=before)
        return _envelope("success", "Agent runs", result)

    @app.post("/agent/v1/projects/{pid}/runs", status_code=201, description="\f")
    async def create_run(pid: str, request: AgentRunCreateRequest):
        """\f
        处理 `POST /agent/v1/projects/{pid}/runs` 请求，并沿用既有状态码、响应 schema 与安全边界。

        参数:
            `pid`：项目 ID。
            `request`：当前请求对象。

        异常:
            `AgentApiError`：输入、状态或下游结果不满足现有约束时抛出。"""
        scope = await trusted_scope(pid)
        try:
            handle = await workbench.create_run(scope, request)
        except AgentRunConflict as exc:
            raise AgentApiError(409, "agent_run_conflict", str(exc)) from None
        return _envelope("success", "Agent run queued", handle)

    @app.get("/agent/v1/projects/{pid}/runs/{thread_id}", description="\f")
    async def get_run(pid: str, thread_id: str):
        """\f
        处理 `GET /agent/v1/projects/{pid}/runs/{thread_id}` 请求，并沿用既有状态码、响应 schema 与安全边界。

        参数:
            `pid`：项目 ID。
            `thread_id`：Agent 运行线程 ID。"""
        _scope_value, view = await existing_run(pid, thread_id)
        return _envelope("success", "Agent run", view)

    @app.post("/agent/v1/projects/{pid}/runs/{thread_id}/approval", description="\f")
    async def approve(
        pid: str, thread_id: str, request: AgentApprovalRequest
    ):
        """\f
        处理 `POST /agent/v1/projects/{pid}/runs/{thread_id}/approval` 请求，并沿用既有状态码、响应 schema 与安全边界。

        参数:
            `pid`：项目 ID。
            `thread_id`：Agent 运行线程 ID。
            `request`：当前请求对象。

        异常:
            `AgentApiError`：输入、状态或下游结果不满足现有约束时抛出。"""
        scope, _view = await existing_run(pid, thread_id)
        try:
            command_id = await workbench.decide_approval(
                scope,
                thread_id,
                ApprovalDecision(request.decision),
                request.expected_plan_hash,
            )
        except ValueError as exc:
            raise AgentApiError(
                409, "agent_approval_conflict", str(exc)
            ) from None
        return _envelope(
            "success", "Agent approval submitted", {"command_id": command_id}
        )

    @app.post("/agent/v1/projects/{pid}/runs/{thread_id}/edit", description="\f")
    async def edit(pid: str, thread_id: str, request: AgentEditRequest):
        """\f
        处理 `POST /agent/v1/projects/{pid}/runs/{thread_id}/edit` 请求，并沿用既有状态码、响应 schema 与安全边界。

        参数:
            `pid`：项目 ID。
            `thread_id`：Agent 运行线程 ID。
            `request`：当前请求对象。

        异常:
            `AgentApiError`：输入、状态或下游结果不满足现有约束时抛出。"""
        scope, _view = await existing_run(pid, thread_id)
        try:
            command_id = await workbench.edit_run(
                scope,
                thread_id,
                request.goal,
                request.expected_plan_hash,
            )
        except ValueError as exc:
            raise AgentApiError(
                409, "agent_edit_conflict", str(exc)
            ) from None
        return _envelope(
            "success", "Agent replanning queued", {"command_id": command_id}
        )

    @app.post("/agent/v1/projects/{pid}/runs/{thread_id}/cancel", description="\f")
    async def cancel(pid: str, thread_id: str):
        """\f
        处理 `POST /agent/v1/projects/{pid}/runs/{thread_id}/cancel` 请求，并沿用既有状态码、响应 schema 与安全边界。

        参数:
            `pid`：项目 ID。
            `thread_id`：Agent 运行线程 ID。

        异常:
            `AgentApiError`：输入、状态或下游结果不满足现有约束时抛出。"""
        scope, _view = await existing_run(pid, thread_id)
        try:
            view = await workbench.cancel_run(scope, thread_id)
        except AgentRunConflict as exc:
            raise AgentApiError(
                409, "agent_cancel_conflict", str(exc)
            ) from None
        return _envelope("success", "Agent cancellation requested", view)

    @app.post("/agent/v1/projects/{pid}/runs/{thread_id}/recover", description="\f")
    async def recover(pid: str, thread_id: str):
        """\f
        处理 `POST /agent/v1/projects/{pid}/runs/{thread_id}/recover` 请求，并沿用既有状态码、响应 schema 与安全边界。

        参数:
            `pid`：项目 ID。
            `thread_id`：Agent 运行线程 ID。

        异常:
            `AgentApiError`：输入、状态或下游结果不满足现有约束时抛出。"""
        scope, _view = await existing_run(pid, thread_id)
        try:
            command_id = await workbench.recover_run(scope, thread_id)
        except AgentRunConflict as exc:
            raise AgentApiError(
                409, "agent_run_conflict", str(exc)
            ) from None
        except ValueError as exc:
            raise AgentApiError(
                409, "agent_recovery_conflict", str(exc)
            ) from None
        return _envelope(
            "success", "Agent recovery queued", {"command_id": command_id}
        )

    @app.get("/agent/v1/projects/{pid}/runs/{thread_id}/events", description="\f")
    async def events(
        pid: str,
        thread_id: str,
        request: Request,
        after_sequence: int = Query(default=0, ge=0),
        last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    ):
        """\f
        处理 `GET /agent/v1/projects/{pid}/runs/{thread_id}/events` 请求，并沿用既有状态码、响应 schema 与安全边界。

        参数:
            `pid`：项目 ID。
            `thread_id`：Agent 运行线程 ID。
            `request`：当前请求对象。
            `after_sequence`：沿用签名中 `int` 类型约束的输入。
            `last_event_id`：沿用签名中 `str | None` 类型约束的输入。"""
        scope, initial = await existing_run(pid, thread_id)
        if last_event_id and last_event_id.isdigit():
            after_sequence = max(after_sequence, int(last_event_id))

        async def stream_impl():
            """流式处理IMPL，并遵循现有调用契约。"""
            cursor = after_sequence
            bounds = await workbench.store.timeline_bounds(
                workbench.scope_hash(scope), thread_id
            )
            if bounds is not None and cursor and cursor < bounds[0] - 1:
                cursor = bounds[1]
                yield _sse_event(
                    cursor,
                    {
                        "schema_version": 1,
                        "sequence": cursor,
                        "kind": "replay_reset",
                        "reason": "retention_gap",
                    },
                )
            heartbeat_elapsed = 0.0
            terminal = initial.status.value in _TERMINAL
            while True:
                timeline = await workbench.replay_events(
                    scope, thread_id, cursor
                )
                for event in timeline:
                    cursor = event.sequence
                    yield _sse_event(cursor, event.model_dump(mode="json"))
                    if event.kind in _TERMINAL:
                        return
                if terminal:
                    return
                if await request.is_disconnected():
                    return
                await asyncio.sleep(poll_seconds)
                heartbeat_elapsed += poll_seconds
                if heartbeat_elapsed >= heartbeat_seconds:
                    yield b": heartbeat\n\n"
                    heartbeat_elapsed = 0.0
                latest = await workbench.get_run(scope, thread_id)
                if latest is None:
                    return
                terminal = latest.status.value in _TERMINAL

        async def stream():
            """流式处理内部逻辑，并遵循现有调用契约。"""
            started = time.perf_counter()
            first_event = True
            telemetry = get_agent_telemetry()
            telemetry.counter(
                "ezllm.agent.sse.connections", labels={"status": "opened"}
            )
            try:
                with agent_span("agent.sse"):
                    async for chunk in stream_impl():
                        if first_event and not chunk.startswith(b":"):
                            telemetry.histogram(
                                "ezllm.agent.sse.ttfe",
                                (time.perf_counter() - started) * 1_000,
                                {"status": "success"},
                            )
                            first_event = False
                        yield chunk
            finally:
                telemetry.counter(
                    "ezllm.agent.sse.connections",
                    labels={"status": "closed"},
                )

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
            },
        )

    return app


def build_parser() -> argparse.ArgumentParser:
    """构建当前命令行入口的参数解析器。"""
    parser = argparse.ArgumentParser(description="EzLLM Agent loopback API")
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("AGENT_API_PORT", "8231")),
    )
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
    if not 1 <= args.port <= 65_535:
        raise SystemExit("Agent API port must be between 1 and 65535")
    if os.environ.get("AGENT_API_BIND_MODE", "loopback") != "loopback":
        raise SystemExit("Agent API supports loopback binding only")
    uvicorn.run(
        "app.agentApi:app",
        host=AGENT_API_HOST,
        port=args.port,
        log_level="info",
    )
    return 0


app = create_agent_api_app()


if __name__ == "__main__":
    raise SystemExit(main())
