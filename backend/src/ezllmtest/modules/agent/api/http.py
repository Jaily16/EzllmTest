# 本机 Agent 工作台 HTTP 边界：校验来源、解析请求并调用可信工作台服务。
"""Independent loopback API for the Iteration 4 Agent workbench."""

from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import os
from ezllmtest.platform import configuration as runtime_values
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

from ezllmtest.modules.agent.domain.contracts import ApprovalDecision, TrustedProjectScope
from ezllmtest.modules.agent.runtime.state.contracts import AGENT_GRAPH_VERSION
from ezllmtest.modules.agent.schemas.workbench import AGENT_ACTOR_ID, AGENT_API_SCHEMA_VERSION, AGENT_SCOPE_VERSION, AgentApprovalRequest, AgentEditRequest, AgentRunCreateRequest, public_capabilities
from ezllmtest.modules.agent.application.workbench import AgentRunConflict, AgentWorkbenchService
from ezllmtest.platform.telemetry.agent_telemetry import agent_span, get_agent_telemetry, telemetry_public_status, use_agent_trace


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
        """保存 HTTP 状态、稳定错误码和可展示原因，供 Agent 异常处理器统一生成响应。"""
        super().__init__(reason)
        self.status_code = status_code
        self.code = code
        self.reason = reason


class LoopbackHostMiddleware:
    """Reject non-loopback Host headers without exposing configuration."""

    def __init__(self, app, *, allow_test_host: bool = False) -> None:
        """仅允许本机 Host；testserver 必须由测试装配显式启用，不放宽生产请求的来源限制。"""
        self.app = app
        self.allowed = {"127.0.0.1", "localhost", "[::1]"}
        if allow_test_host:
            self.allowed.add("testserver")

    async def __call__(self, scope, receive, send) -> None:
        """从 HTTP/WebSocket Host 提取本机主机名；非允许值直接返回 421，不进入应用。"""
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
        """保存下游 ASGI 应用；请求级观测在中间件调用时记录，不在构造阶段导出。"""
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        """为允许的 Agent 请求建立脱敏 trace 上下文，不把请求正文写入观测。"""
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
    """通过项目 public 接口在线程中核对项目存在性，避免 API 层直接访问仓储实现。"""
    import ezllmtest.modules.projects.public as testProjectDao

    return await asyncio.to_thread(testProjectDao.find_project, pid) is not None


async def _resolve_bool(value: bool | Awaitable[bool]) -> bool:
    """统一处理同步布尔值与异步存在性检查结果，让测试与真实装配使用同一入口。"""
    return bool(await value) if inspect.isawaitable(value) else bool(value)


def _scope(pid: str) -> TrustedProjectScope:
    """把宿主提供的项目与操作者身份构造为可信 scope，不接收模型授予的权限。"""
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
    service: AgentWorkbenchService,
    owns_service: bool = False,
    *,
    project_exists: ProjectExists | None = None,
    allowed_origins: tuple[str, ...] | None = None,
    allow_test_host: bool = False,
    heartbeat_seconds: float = 15.0,
    poll_seconds: float = 0.25,
) -> FastAPI:
    """装配独立工作台 API、中间件和安全异常映射，运行执行由服务和 worker 负责。"""
    workbench = service
    project_check = project_exists or _default_project_exists

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        """应用关闭时只释放本应用自己构造的协调器，调用方注入的依赖由调用方管理。"""
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
                for origin in runtime_values.get(
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
        """校验请求对应项目并建立可信身份，后续运行操作都使用该 scope。"""
        if not await _resolve_bool(project_check(pid)):
            raise AgentApiError(
                404,
                "agent_project_not_found",
                "Project was not found",
            )
        return _scope(pid)

    async def existing_run(pid: str, thread_id: str):
        """在可信 scope 下确认运行存在，避免通过线程 ID 跨项目访问。"""
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
        """把已分类的 Agent 错误代码、原因和状态直接编码为稳定响应信封。"""
        return _response(exc.status_code, exc.code, exc.reason)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request, _exc: RequestValidationError
    ):
        """请求校验失败只返回固定原因，不回显输入值或 Pydantic 错误正文。"""
        return _response(
            422,
            "agent_validation_error",
            "Agent request validation failed",
        )

    @app.exception_handler(Exception)
    async def internal_error_handler(_request: Request, _exc: Exception):
        """未知异常统一返回安全的 500 响应，不把异常正文发给浏览器。"""
        return _response(
            500,
            "agent_internal_error",
            "Agent request failed safely",
        )

    # 检查 Redis 与普通 worker 心跳并返回遥测摘要；不消费验收心跳不计为普通 worker。
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

    # 只有 Redis 可用且存在普通 worker 才返回就绪；不消费验收模式保持 503 的真实限制。
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

    # 返回静态能力清单，包含工具与运行边界，不启动规划或队列消费。
    @app.get("/agent/v1/capabilities", description="\f")
    async def capabilities():
        """\f
        处理 `GET /agent/v1/capabilities` 请求，并沿用既有状态码、响应 schema 与安全边界。"""
        return _envelope(
            "success", "Agent capabilities", public_capabilities()
        )

    # 先确认可信项目 scope，再分页读取运行摘要，跨项目 thread 不可越界。
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

    # 验证创建请求并提交工作台服务，不在 HTTP 处理函数直接执行模型或工具。
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

    # 通过项目与 thread 的一致性检查后返回运行快照，不执行恢复命令。
    @app.get("/agent/v1/projects/{pid}/runs/{thread_id}", description="\f")
    async def get_run(pid: str, thread_id: str):
        """\f
        处理 `GET /agent/v1/projects/{pid}/runs/{thread_id}` 请求，并沿用既有状态码、响应 schema 与安全边界。

        参数:
            `pid`：项目 ID。
            `thread_id`：Agent 运行线程 ID。"""
        _scope_value, view = await existing_run(pid, thread_id)
        return _envelope("success", "Agent run", view)

    # 把用户审批交给服务核验运行与绑定，HTTP 请求本身不能跳过图的恢复检查。
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

    # 提交允许状态下的编辑，不直接修改正在执行的图对象。
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

    # 记录用户取消意图，由运行层在副作用边界处理停止。
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

    # 提交受状态与活动槽约束的恢复请求，不把未知结果当作可自动重复执行。
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

    # 从有界时间线恢复 SSE，并按游标和终态结束；订阅不创建或执行新任务。
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
            """按 sequence 重放有界事件；保留窗口缺口发送 replay_reset，终态或客户端离开后停止并定期发送心跳。"""
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
            """为 SSE 连接记录打开、关闭及首事件耗时；关闭统计放在 finally，连接失败不绕过收尾。"""
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
