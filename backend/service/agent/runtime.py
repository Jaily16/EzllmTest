"""Internal-only service for durable single-Agent execution.

This module intentionally exposes no FastAPI route.  Trusted callers inject the
project scope and enqueue bounded commands; the worker is the only component
that executes a LangGraph invocation.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import uuid4

from langgraph.types import Command
from pydantic import BaseModel, ConfigDict, Field

from service.agent.budget import RedisAgentBudgetLedger, use_agent_budget
from service.agent.checkpoint import (
    AsyncAgentRedisCheckpointSaver,
    StrictAgentCheckpointSerializer,
    derive_agent_scope_hash,
)
from service.agent.contracts import (
    AgentRunState,
    AgentRunStatus,
    ApprovalDecision,
    RunBudget,
    TrustedProjectScope,
    UsageCounters,
    approval_binding_for,
)
from service.agent.graph import build_agent_graph, graph_plan_hash
from service.agent.context import AgentContextAssembler
from service.agent.coordinator import (
    AgentCommand,
    AgentRedisCoordinator,
    IdempotencyStatus,
    LeaseHandle,
    LeaseLostError,
)
from service.agent.runtime_contracts import (
    AGENT_GRAPH_VERSION,
    AgentGraphEnvelope,
    ApprovalResume,
    ProjectObservation,
)
from service.agent.tool_registry import DEFAULT_TOOL_REGISTRY
from service.agent.tool_schemas import (
    ToolExecutionError,
    ToolExecutionResult,
    ToolExecutionStatus,
)
from infrastructure.observability.agent_telemetry import (
    TraceCarrier,
    agent_span,
    current_agent_trace_carrier,
    use_agent_trace,
)
from service.agent.workbench_contracts import (
    AgentStepEvidence,
    WORKSPACE_ROUTE_BY_OPERATION,
)


class _RuntimeResultModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AgentRunHandle(_RuntimeResultModel):
    run_id: str = Field(min_length=1, max_length=128)
    thread_id: str = Field(min_length=1, max_length=128)
    command_id: str = Field(min_length=1, max_length=128)


async def _resolve(value: Any) -> Any:
    """按照现有优先级解析目标值。"""
    return await value if inspect.isawaitable(value) else value


# 心跳失租约时主动取消执行，阻止旧 worker 在恢复运行后继续产生重复副作用。
async def _run_with_lease_heartbeat(
    coordinator: AgentRedisCoordinator,
    lease: LeaseHandle,
    awaitable,
):
    """基于租约心跳构造运行。

    参数:
        `coordinator`：沿用签名中 `AgentRedisCoordinator` 类型约束的输入。
        `lease`：沿用签名中 `LeaseHandle` 类型约束的输入。
        `awaitable`：调用方传入的现有参数。

    异常:
        `LeaseLostError`：输入、状态或下游结果不满足现有约束时抛出。"""
    stop = asyncio.Event()
    lease_lost = asyncio.Event()
    owner_task = asyncio.current_task()

    async def heartbeat() -> None:
        """处理心跳并返回现有契约规定的结果。"""
        while True:
            try:
                await asyncio.wait_for(
                    stop.wait(),
                    timeout=coordinator.settings.lease_renew_seconds,
                )
                return
            except TimeoutError:
                if not await coordinator.renew_lease(lease):
                    lease_lost.set()
                    if owner_task is not None:
                        owner_task.cancel()
                    return

    task = asyncio.create_task(heartbeat())
    try:
        return await awaitable
    except asyncio.CancelledError:
        if lease_lost.is_set():
            raise LeaseLostError("Agent worker lost its lease fence") from None
        raise
    finally:
        stop.set()
        await task


class _IdempotentToolAdapter:
    def __init__(
        self,
        *,
        delegate: Any,
        coordinator: AgentRedisCoordinator,
        lease: LeaseHandle,
        artifact_reconciler: Callable[..., Any] | None,
        after_tool_hook: Callable[..., Any] | None,
        evidence_hook: Callable[..., Any] | None,
    ) -> None:
        """初始化实例并保存后续操作所需的依赖与状态。"""
        self.delegate = delegate
        self.coordinator = coordinator
        self.lease = lease
        self.artifact_reconciler = artifact_reconciler
        self.after_tool_hook = after_tool_hook
        self.evidence_hook = evidence_hook

    @staticmethod
    def _unknown(tool_name: str, operation: str) -> ToolExecutionResult:
        """处理未知，并保持 `_IdempotentToolAdapter` 的现有状态约束。"""
        return ToolExecutionResult(
            tool_name=tool_name,
            operation=operation,
            status=ToolExecutionStatus.ERROR,
            error=ToolExecutionError(
                code="outcome_unknown",
                category="recovery",
                retryable=False,
                safe_message=(
                    "The prior paid side effect cannot be proven; explicit human "
                    "review is required before any new attempt"
                ),
            ),
        )

    async def invoke(self, tool_name, arguments, context) -> ToolExecutionResult:
        """调用当前适配器封装的下游能力，并返回既有契约规定的结果。

        参数:
            `tool_name`：调用方传入的现有参数。
            `arguments`：符合工具 schema 的参数。
            `context`：调用方传入的现有参数。

        返回:
            `ToolExecutionResult`，内容保持现有调用方契约。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
        state = context.run_state
        if state is None or not state.plan:
            raise ValueError("idempotent execution requires trusted Agent state")
        call = state.plan[state.current_step_index]
        if tool_name != f"workflow_{call.operation}":
            raise ValueError("tool invocation does not match the current plan step")
        definition = DEFAULT_TOOL_REGISTRY.get(tool_name)
        persisted = bool(
            definition.catalog is not None
            and definition.catalog.persistence == "artifact"
        )
        record = await self.coordinator.reserve_idempotency(
            self.lease,
            idempotency_key=call.idempotency_key,
            operation=call.operation,
            persisted=persisted,
        )
        if record.status is IdempotencyStatus.COMPLETED:
            result = ToolExecutionResult.model_validate(record.result)
            if self.evidence_hook is not None:
                await _resolve(self.evidence_hook(call, result, context))
            return result
        if record.status is IdempotencyStatus.OUTCOME_UNKNOWN:
            return self._unknown(tool_name, call.operation)
        if record.status is IdempotencyStatus.STARTED:
            reconciled = None
            if persisted and self.artifact_reconciler is not None:
                reconciled = await _resolve(
                    self.artifact_reconciler(call, context)
                )
            if reconciled is not None:
                result = ToolExecutionResult.model_validate(reconciled)
                await self.coordinator.complete_idempotency(
                    self.lease,
                    call.idempotency_key,
                    result.model_dump(mode="json"),
                )
                if self.evidence_hook is not None:
                    await _resolve(self.evidence_hook(call, result, context))
                return result
            await self.coordinator.mark_outcome_unknown(
                self.lease,
                call.idempotency_key,
                "artifact_not_proven" if persisted else "session_result_not_recorded",
            )
            return self._unknown(tool_name, call.operation)

        await self.coordinator.mark_idempotency_started(
            self.lease, call.idempotency_key
        )
        try:
            result = await self.delegate.invoke(tool_name, arguments, context)
            if self.after_tool_hook is not None:
                await _resolve(self.after_tool_hook(call, result))
            await self.coordinator.complete_idempotency(
                self.lease,
                call.idempotency_key,
                result.model_dump(mode="json"),
            )
            if self.evidence_hook is not None:
                await _resolve(self.evidence_hook(call, result, context))
            return result
        except asyncio.CancelledError:
            if not persisted:
                await self.coordinator.mark_outcome_unknown(
                    self.lease, call.idempotency_key, "cancelled_after_start"
                )
            raise
        except BaseException:
            # A process death can occur after the external effect but before the
            # result is recorded.  Persisted steps reconcile; session steps stop.
            if not persisted:
                try:
                    await self.coordinator.mark_outcome_unknown(
                        self.lease, call.idempotency_key, "execution_interrupted"
                    )
                except Exception:
                    pass
            raise


# runtime 串联审批、预算、checkpoint、工具执行和恢复；每一步都必须保留可审计结果。
class AgentRuntimeService:
    def __init__(
        self,
        *,
        coordinator: AgentRedisCoordinator,
        planner: Any,
        observer: Callable[[TrustedProjectScope], Any],
        tool_adapter: Any,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        artifact_reconciler: Callable[..., Any] | None = None,
        after_tool_hook: Callable[..., Any] | None = None,
        workbench_store: Any | None = None,
        context_assembler: AgentContextAssembler | None = None,
    ) -> None:
        """初始化实例并保存后续操作所需的依赖与状态。

        参数:
            `coordinator`：沿用签名中 `AgentRedisCoordinator` 类型约束的输入。
            `planner`：沿用签名中 `Any` 类型约束的输入。
            `observer`：沿用签名中 `Callable[[TrustedProjectScope], Any]` 类型约束的输入。
            `tool_adapter`：沿用签名中 `Any` 类型约束的输入。
            `clock`：沿用签名中 `Callable[[], datetime]` 类型约束的输入。
            `artifact_reconciler`：沿用签名中 `Callable[..., Any] | None` 类型约束的输入。
            `after_tool_hook`：沿用签名中 `Callable[..., Any] | None` 类型约束的输入。
            `workbench_store`：沿用签名中 `Any | None` 类型约束的输入。
            `context_assembler`：沿用签名中 `AgentContextAssembler | None` 类型约束的输入。"""
        self.coordinator = coordinator
        self.planner = planner
        self.observer = observer
        self.tool_adapter = tool_adapter
        self.clock = clock
        self.artifact_reconciler = artifact_reconciler
        self.after_tool_hook = after_tool_hook
        self.workbench_store = workbench_store
        self.context_assembler = context_assembler
        self.serializer = StrictAgentCheckpointSerializer()
        self.budget_ledger = RedisAgentBudgetLedger(coordinator)

    async def _record_workbench_evidence(self, call, result, context) -> None:
        """记录工作台证据，并遵循现有调用契约。

        参数:
            `call`：调用方传入的现有参数。
            `result`：调用方传入的现有参数。
            `context`：调用方传入的现有参数。"""
        if self.workbench_store is None:
            return
        definition = DEFAULT_TOOL_REGISTRY.get(f"workflow_{call.operation}")
        usage = result.usage
        evidence = AgentStepEvidence(
            step_id=call.step_id,
            operation=call.operation,
            retention=definition.retention,
            status=(
                "success"
                if result.status is ToolExecutionStatus.SUCCESS
                else "cancelled"
                if result.status is ToolExecutionStatus.CANCELLED
                else "stale"
                if result.status is ToolExecutionStatus.STALE
                else "error"
            ),
            saved=result.saved,
            from_cache=result.from_cache,
            source_revision=result.source_revision,
            artifact_key=result.artifact_key,
            workspace_route=WORKSPACE_ROUTE_BY_OPERATION.get(call.operation),
            session_result=(
                result.data
                if definition.retention == "session"
                and result.status is ToolExecutionStatus.SUCCESS
                else None
            ),
            usage=UsageCounters(
                steps=1 if usage.tool_calls else 0,
                input_tokens=usage.input_tokens or 0,
                output_tokens=usage.output_tokens or 0,
                model_calls=usage.model_calls,
                embedding_calls=usage.embedding_calls or 0,
                tool_calls=usage.tool_calls,
                estimated_cost_units=usage.estimated_cost_units or 0,
            ),
            error_code=result.error.code if result.error else None,
            safe_message=result.error.safe_message if result.error else None,
            retrieval_evidence=result.retrieval_evidence,
        )
        scope_hash = self._scope_hash(context.project_scope)
        await self.workbench_store.put_evidence(
            scope_hash, context.run_state.thread_id, evidence
        )
        kind = (
            "tool_succeeded"
            if result.status is ToolExecutionStatus.SUCCESS
            else "tool_failed"
        )
        await self.workbench_store.append_timeline_event(
            scope_hash,
            context.run_state.thread_id,
            f"tool:{call.idempotency_key}:{result.status.value}",
            {
                "kind": kind,
                "occurred_at": self.clock().isoformat(),
                "status": context.run_state.status.value,
                "step_id": call.step_id,
                "operation": call.operation,
                "saved": result.saved,
                "from_cache": result.from_cache,
                "artifact_key": result.artifact_key,
                "error_code": result.error.code if result.error else None,
                "safe_message": (
                    result.error.safe_message if result.error else None
                ),
            },
        )

    async def _record_workbench_progress(self, run_state, progress) -> None:
        """记录工作台进度，并遵循现有调用契约。

        参数:
            `run_state`：调用方传入的现有参数。
            `progress`：调用方传入的现有参数。"""
        if self.workbench_store is None:
            return
        call = run_state.plan[run_state.current_step_index]
        percent = min(
            100.0,
            max(
                0.0,
                (
                    float(progress.progress) / float(progress.total) * 100.0
                    if progress.total
                    else float(progress.progress)
                ),
            ),
        )
        bucket = min(100, int(percent // 5) * 5)
        if not await self.workbench_store.accept_progress(
            self._scope_hash(run_state.project_scope),
            run_state.thread_id,
            f"{call.step_id}:{progress.stage}",
            bucket,
        ):
            return
        await self.workbench_store.append_timeline_event(
            self._scope_hash(run_state.project_scope),
            run_state.thread_id,
            f"progress:{call.step_id}:{progress.stage}:{bucket}",
            {
                "kind": "progress",
                "occurred_at": self.clock().isoformat(),
                "status": run_state.status.value,
                "step_id": call.step_id,
                "operation": call.operation,
                "stage": progress.stage,
                "label": progress.label,
                "percent": percent,
            },
        )

    async def _record_workbench_lifecycle(
        self,
        *,
        scope_hash: str,
        thread_id: str,
        event_id: str,
        kind: str,
        status: AgentRunStatus,
        step_id: str | None = None,
        operation: str | None = None,
        error_code: str | None = None,
        safe_message: str | None = None,
    ) -> None:
        """记录工作台生命周期，并遵循现有调用契约。

        参数:
            `scope_hash`：沿用签名中 `str` 类型约束的输入。
            `thread_id`：Agent 运行线程 ID。
            `event_id`：沿用签名中 `str` 类型约束的输入。
            `kind`：沿用签名中 `str` 类型约束的输入。
            `status`：沿用签名中 `AgentRunStatus` 类型约束的输入。
            `step_id`：沿用签名中 `str | None` 类型约束的输入。
            `operation`：工作流操作名。
            `error_code`：沿用签名中 `str | None` 类型约束的输入。
            `safe_message`：沿用签名中 `str | None` 类型约束的输入。"""
        if self.workbench_store is None:
            return
        await self.workbench_store.append_timeline_event(
            scope_hash,
            thread_id,
            event_id,
            {
                "kind": kind,
                "occurred_at": self.clock().isoformat(),
                "status": status.value,
                "step_id": step_id,
                "operation": operation,
                "error_code": error_code,
                "safe_message": safe_message,
            },
        )

    def _scope_hash(self, scope: TrustedProjectScope) -> str:
        """计算作用域的稳定哈希。"""
        return derive_agent_scope_hash(scope, AGENT_GRAPH_VERSION)

    def _storage_id(self, scope_hash: str, thread_id: str) -> str:
        """返回当前存储ID。"""
        return self.coordinator.storage_id(
            scope_hash, AGENT_GRAPH_VERSION, thread_id
        )

    def _state_key(self, kind: str, storage_id: str) -> str:
        """构造state键，并保持现有命名空间格式。"""
        return self.coordinator._key(kind, storage_id)

    async def _store_model(
        self, key: str, value: dict[str, Any], *, nx: bool = False
    ) -> bool:
        """保存模型，并遵循现有调用契约。

        参数:
            `key`：沿用签名中 `str` 类型约束的输入。
            `value`：待处理的值。
            `nx`：沿用签名中 `bool` 类型约束的输入。

        返回:
            `bool`，内容保持现有调用方契约。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
        content_type, payload = self.serializer.dumps_typed(value)
        if content_type != "ezllm-safe-json-v1":
            raise ValueError("unexpected safe runtime content type")
        result = await self.coordinator.redis.set(
            key,
            payload,
            ex=self.coordinator.settings.state_ttl_seconds,
            nx=nx,
        )
        return bool(result)

    async def _load_model(self, key: str) -> dict[str, Any] | None:
        """加载模型，并遵循现有调用契约。

        参数:
            `key`：沿用签名中 `str` 类型约束的输入。

        返回:
            `dict[str, Any] | None`，内容保持现有调用方契约。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
        payload = await self.coordinator.redis.get(key)
        if payload is None:
            return None
        value = self.serializer.loads_typed(("ezllm-safe-json-v1", payload))
        if not isinstance(value, dict):
            raise ValueError("stored Agent runtime value is invalid")
        return value

    async def _enqueue_command(
        self,
        *,
        scope_hash: str,
        thread_id: str,
        command_id: str,
        kind: Literal["start", "resume", "recover"],
        trace_carrier: TraceCarrier | None,
    ) -> str:
        """入队命令，并遵循现有调用契约。

        参数:
            `scope_hash`：沿用签名中 `str` 类型约束的输入。
            `thread_id`：Agent 运行线程 ID。
            `command_id`：沿用签名中 `str` 类型约束的输入。
            `kind`：沿用签名中 `Literal['start', 'resume', 'recover']` 类型约束的输入。
            `trace_carrier`：沿用签名中 `TraceCarrier | None` 类型约束的输入。

        返回:
            `str`，内容保持现有调用方契约。"""
        started = time.perf_counter()
        with use_agent_trace(trace_carrier) as telemetry:
            with agent_span(
                "agent.command.enqueue",
                {"agent.command.kind": kind},
                always=True,
            ):
                result = await self.coordinator.enqueue_command(
                    scope_hash=scope_hash,
                    graph_version=AGENT_GRAPH_VERSION,
                    thread_id=thread_id,
                    command_id=command_id,
                    kind=kind,
                    traceparent=(
                        trace_carrier.traceparent if trace_carrier else None
                    ),
                )
        telemetry.counter(
            "ezllm.agent.commands.enqueued", labels={"command_kind": kind}
        )
        telemetry.histogram(
            "ezllm.agent.commands.enqueue.duration",
            (time.perf_counter() - started) * 1_000,
            {"command_kind": kind},
        )
        return result

    async def create_run(
        self,
        scope: TrustedProjectScope,
        goal: str,
        planner_model: str,
        execution_model: str,
        budget: RunBudget,
    ) -> AgentRunHandle:
        """创建运行，并遵循现有调用契约。

        参数:
            `scope`：沿用签名中 `TrustedProjectScope` 类型约束的输入。
            `goal`：沿用签名中 `str` 类型约束的输入。
            `planner_model`：沿用签名中 `str` 类型约束的输入。
            `execution_model`：沿用签名中 `str` 类型约束的输入。
            `budget`：沿用签名中 `RunBudget` 类型约束的输入。

        返回:
            `AgentRunHandle`，内容保持现有调用方契约。

        异常:
            `ValueError, RuntimeError`：输入、状态或下游结果不满足现有约束时抛出。"""
        with use_agent_trace() as telemetry:
            with agent_span(
                "agent.run", {"agent.status": "created"}, always=True
            ):
                trace_carrier = current_agent_trace_carrier()
        telemetry.counter(
            "ezllm.agent.runs.created", labels={"status": "created"}
        )
        observation = ProjectObservation.model_validate(
            await _resolve(self.observer(scope))
        )
        if not observation.source_revision:
            raise ValueError("Agent run requires a source revision")
        now = self.clock()
        run_id = f"run-{uuid4().hex}"
        thread_id = f"thread-{uuid4().hex}"
        command_id = f"command-{uuid4().hex}"
        state = AgentRunState(
            run_id=run_id,
            thread_id=thread_id,
            project_scope=scope,
            source_revision=observation.source_revision,
            goal=goal,
            budget=budget,
        )
        envelope = AgentGraphEnvelope(
            run_state=state,
            started_at=now,
            deadline_at=now + timedelta(milliseconds=budget.max_elapsed_ms),
            planner_model=planner_model,
            execution_model=execution_model,
            trace_carrier=trace_carrier,
        )
        scope_hash = self._scope_hash(scope)
        storage_id = self._storage_id(scope_hash, thread_id)
        creator = await self.coordinator.acquire_lease(
            scope_hash,
            AGENT_GRAPH_VERSION,
            thread_id,
            f"creator-{uuid4().hex}",
        )
        if creator is None:
            raise RuntimeError("new Agent thread unexpectedly has an active lease")
        try:
            await self.budget_ledger.initialize(
                creator,
                budget,
                started_at=envelope.started_at,
                deadline_at=envelope.deadline_at,
            )
            await self._store_model(
                self._state_key("run-descriptor", storage_id),
                envelope.model_dump(mode="json"),
                nx=True,
            )
            await self._store_model(
                self._state_key("run-view", storage_id),
                envelope.model_dump(mode="json"),
            )
            await self.coordinator.append_event(
                creator, "run_created", {"status": state.status.value}
            )
        finally:
            await self.coordinator.release_lease(creator)
        await self._enqueue_command(
            scope_hash=scope_hash,
            thread_id=thread_id,
            command_id=command_id,
            kind="start",
            trace_carrier=trace_carrier,
        )
        return AgentRunHandle(
            run_id=run_id, thread_id=thread_id, command_id=command_id
        )

    async def get_run(
        self, scope: TrustedProjectScope, thread_id: str
    ) -> AgentGraphEnvelope | None:
        """获取运行，并遵循现有调用契约。"""
        scope_hash = self._scope_hash(scope)
        storage_id = self._storage_id(scope_hash, thread_id)
        raw = await self._load_model(self._state_key("run-view", storage_id))
        return AgentGraphEnvelope.model_validate(raw) if raw is not None else None

    async def approve_run(
        self,
        scope: TrustedProjectScope,
        thread_id: str,
        decision: ApprovalDecision,
        expected_plan_hash: str,
    ) -> str:
        """批准运行，并遵循现有调用契约。

        参数:
            `scope`：沿用签名中 `TrustedProjectScope` 类型约束的输入。
            `thread_id`：Agent 运行线程 ID。
            `decision`：沿用签名中 `ApprovalDecision` 类型约束的输入。
            `expected_plan_hash`：沿用签名中 `str` 类型约束的输入。

        返回:
            `str`，内容保持现有调用方契约。

        异常:
            `KeyError, ValueError, RuntimeError`：输入、状态或下游结果不满足现有约束时抛出。

        不变量:
            审批结果必须继续绑定当前项目、revision、plan hash 与一次性凭据。"""
        envelope = await self.get_run(scope, thread_id)
        if envelope is None:
            raise KeyError("Agent thread was not found in the trusted project scope")
        if envelope.run_state.status is not AgentRunStatus.AWAITING_APPROVAL:
            raise ValueError("Agent thread is not awaiting approval")
        request = envelope.approval_request
        if request is None or request.plan_hash != expected_plan_hash:
            raise ValueError("approval plan hash does not match")
        now = self.clock()
        if now >= request.expires_at and decision is ApprovalDecision.APPROVED:
            raise ValueError("approval request has expired")
        scope_hash = self._scope_hash(scope)
        storage_id = self._storage_id(scope_hash, thread_id)
        control_key = self._state_key("resume-control", storage_id)
        if await self.coordinator.redis.exists(control_key):
            raise ValueError("an approval decision is already pending")
        lease = await self.coordinator.acquire_lease(
            scope_hash,
            AGENT_GRAPH_VERSION,
            thread_id,
            f"approval-{uuid4().hex}",
        )
        if lease is None:
            raise RuntimeError("Agent thread is currently leased by a worker")
        try:
            binding = None
            if decision is ApprovalDecision.APPROVED:
                nonce = f"approval-{uuid4().hex}"
                if not await self.coordinator.issue_approval_nonce(lease, nonce):
                    raise RuntimeError("approval nonce collision")
                call = envelope.run_state.plan[envelope.run_state.current_step_index]
                binding = approval_binding_for(
                    envelope.run_state,
                    call,
                    decision=decision,
                    decided_at=now,
                    expires_at=request.expires_at,
                    nonce=nonce,
                )
            resume = ApprovalResume(
                decision=decision,
                expected_plan_hash=expected_plan_hash,
                binding=binding,
            )
            if not await self._store_model(
                control_key, resume.model_dump(mode="json"), nx=True
            ):
                raise ValueError("an approval decision is already pending")
        finally:
            await self.coordinator.release_lease(lease)
        command_id = f"command-{uuid4().hex}"
        await self._enqueue_command(
            scope_hash=scope_hash,
            thread_id=thread_id,
            command_id=command_id,
            kind="resume",
            trace_carrier=envelope.trace_carrier,
        )
        return command_id

    async def edit_run(
        self,
        scope: TrustedProjectScope,
        thread_id: str,
        edited_goal: str,
    ) -> str:
        """处理EDIT运行，并保持 `AgentRuntimeService` 的现有状态约束。

        参数:
            `scope`：沿用签名中 `TrustedProjectScope` 类型约束的输入。
            `thread_id`：Agent 运行线程 ID。
            `edited_goal`：沿用签名中 `str` 类型约束的输入。

        返回:
            `str`，内容保持现有调用方契约。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
        envelope = await self.get_run(scope, thread_id)
        if envelope is None or envelope.approval_request is None:
            raise ValueError("Agent thread has no editable approval request")
        scope_hash = self._scope_hash(scope)
        storage_id = self._storage_id(scope_hash, thread_id)
        resume = ApprovalResume(
            decision=ApprovalDecision.EDITED,
            expected_plan_hash=envelope.approval_request.plan_hash,
            edited_goal=edited_goal,
        )
        if not await self._store_model(
            self._state_key("resume-control", storage_id),
            resume.model_dump(mode="json"),
            nx=True,
        ):
            raise ValueError("an approval decision is already pending")
        command_id = f"command-{uuid4().hex}"
        await self._enqueue_command(
            scope_hash=scope_hash,
            thread_id=thread_id,
            command_id=command_id,
            kind="resume",
            trace_carrier=envelope.trace_carrier,
        )
        return command_id

    async def cancel_run(
        self, scope: TrustedProjectScope, thread_id: str
    ) -> None:
        """取消运行，并遵循现有调用契约。

        参数:
            `scope`：沿用签名中 `TrustedProjectScope` 类型约束的输入。
            `thread_id`：Agent 运行线程 ID。

        异常:
            `KeyError`：输入、状态或下游结果不满足现有约束时抛出。"""
        if await self.get_run(scope, thread_id) is None:
            raise KeyError("Agent thread was not found in the trusted project scope")
        await self.coordinator.request_cancel_by_identity(
            self._scope_hash(scope), AGENT_GRAPH_VERSION, thread_id
        )

    async def recover_run(
        self, scope: TrustedProjectScope, thread_id: str
    ) -> str:
        """恢复运行，并遵循现有调用契约。

        参数:
            `scope`：沿用签名中 `TrustedProjectScope` 类型约束的输入。
            `thread_id`：Agent 运行线程 ID。

        返回:
            `str`，内容保持现有调用方契约。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
        envelope = await self.get_run(scope, thread_id)
        if (
            envelope is None
            or envelope.run_state.status is not AgentRunStatus.FAILED
            or envelope.run_state.last_error is None
            or not envelope.run_state.last_error.retryable
        ):
            raise ValueError("Agent thread is not eligible for recovery")
        command_id = f"command-{uuid4().hex}"
        await self._enqueue_command(
            scope_hash=self._scope_hash(scope),
            thread_id=thread_id,
            command_id=command_id,
            kind="recover",
            trace_carrier=envelope.trace_carrier,
        )
        return command_id

    async def replay_events(
        self,
        scope: TrustedProjectScope,
        thread_id: str,
        after_sequence: int,
    ):
        """回放事件，并遵循现有调用契约。

        参数:
            `scope`：沿用签名中 `TrustedProjectScope` 类型约束的输入。
            `thread_id`：Agent 运行线程 ID。
            `after_sequence`：沿用签名中 `int` 类型约束的输入。

        异常:
            `KeyError`：输入、状态或下游结果不满足现有约束时抛出。"""
        if await self.get_run(scope, thread_id) is None:
            raise KeyError("Agent thread was not found in the trusted project scope")
        return await self.coordinator.replay_events_by_identity(
            self._scope_hash(scope),
            AGENT_GRAPH_VERSION,
            thread_id,
            after_sequence,
        )

    async def process_command(
        self, command: AgentCommand, *, owner: str
    ) -> AgentGraphEnvelope:
        """处理命令，并遵循现有调用契约。

        参数:
            `command`：沿用签名中 `AgentCommand` 类型约束的输入。
            `owner`：沿用签名中 `str` 类型约束的输入。

        返回:
            `AgentGraphEnvelope`，内容保持现有调用方契约。"""
        started = time.perf_counter()
        with use_agent_trace(command.trace_carrier) as telemetry:
            telemetry.active_runs(1, {"status": "active"})
            try:
                with agent_span(
                    "agent.command.worker",
                    {"agent.command.kind": command.kind},
                    always=True,
                ):
                    with agent_span(
                        "agent.run", {"agent.status": "active"}, always=True
                    ):
                        result = await self._process_command(command, owner=owner)
            finally:
                telemetry.active_runs(-1, {"status": "active"})
        telemetry.counter(
            "ezllm.agent.commands.processed",
            labels={
                "command_kind": command.kind,
                "status": result.run_state.status.value,
            },
        )
        telemetry.histogram(
            "ezllm.agent.commands.duration",
            (time.perf_counter() - started) * 1_000,
            {
                "command_kind": command.kind,
                "status": result.run_state.status.value,
            },
        )
        if command.kind == "recover":
            telemetry.counter(
                "ezllm.agent.recovery",
                labels={"status": result.run_state.status.value},
            )
        return result

    async def _process_command(
        self, command: AgentCommand, *, owner: str
    ) -> AgentGraphEnvelope:
        """处理命令，并遵循现有调用契约。

        参数:
            `command`：沿用签名中 `AgentCommand` 类型约束的输入。
            `owner`：沿用签名中 `str` 类型约束的输入。

        返回:
            `AgentGraphEnvelope`，内容保持现有调用方契约。

        异常:
            `ValueError, KeyError, PermissionError, RuntimeError`：输入、状态或下游结果不满足现有约束时抛出。"""
        if command.graph_version != AGENT_GRAPH_VERSION:
            raise ValueError("worker command graph version is unsupported")
        storage_id = self._storage_id(command.scope_hash, command.thread_id)
        processed_key = self._state_key(
            "processed-command",
            f"{storage_id}:{command.command_id}",
        )
        if await self.coordinator.redis.exists(processed_key):
            raw = await self._load_model(self._state_key("run-view", storage_id))
            if raw is None:
                raise ValueError("processed Agent command has no run view")
            return AgentGraphEnvelope.model_validate(raw)
        raw_descriptor = await self._load_model(
            self._state_key("run-descriptor", storage_id)
        )
        if raw_descriptor is None:
            raise KeyError("Agent run descriptor is unavailable")
        descriptor = AgentGraphEnvelope.model_validate(raw_descriptor)
        if self._scope_hash(descriptor.run_state.project_scope) != command.scope_hash:
            raise PermissionError("worker command project scope does not match")
        current = await self.get_run(
            descriptor.run_state.project_scope, command.thread_id
        )
        if current is None:
            raise KeyError("Agent run view is unavailable")
        if current.run_state.status in {
            AgentRunStatus.COMPLETED,
            AgentRunStatus.CANCELLED,
        }:
            await self.coordinator.redis.set(
                processed_key,
                "1",
                ex=self.coordinator.settings.state_ttl_seconds,
            )
            if self.workbench_store is not None:
                await self.workbench_store.release_active(
                    command.scope_hash, command.thread_id
                )
            return current
        lease = await self.coordinator.acquire_lease(
            command.scope_hash,
            command.graph_version,
            command.thread_id,
            owner,
        )
        if lease is None:
            raise RuntimeError("Agent thread is already leased")
        saver = AsyncAgentRedisCheckpointSaver(
            self.coordinator.redis,
            scope_hash=command.scope_hash,
            graph_version=command.graph_version,
            lease_owner=lease.owner,
            fence_token=lease.fence,
            prefix=f"{self.coordinator.settings.prefix}:checkpoint",
            coordination_prefix=self.coordinator.settings.prefix,
            ttl_seconds=max(60, self.coordinator.settings.state_ttl_seconds),
        )
        adapter = _IdempotentToolAdapter(
            delegate=self.tool_adapter,
            coordinator=self.coordinator,
            lease=lease,
            artifact_reconciler=self.artifact_reconciler,
            after_tool_hook=self.after_tool_hook,
            evidence_hook=(
                self._record_workbench_evidence
                if self.workbench_store is not None
                else None
            ),
        )
        graph = build_agent_graph(
            observer=self.observer,
            planner=self.planner,
            tool_adapter=adapter,
            checkpointer=saver,
            clock=self.clock,
            cancel_checker=lambda _state: self.coordinator.is_cancelled(lease),
            progress_sink=(
                self._record_workbench_progress
                if self.workbench_store is not None
                else None
            ),
            context_assembler=self.context_assembler,
        )
        config = saver.runtime_config(lease.storage_id)
        guard = self.budget_ledger.sync_guard(
            lease,
            model_max_output_tokens=max(
                1,
                current.run_state.budget.max_output_tokens
                // current.run_state.budget.max_model_calls,
            ),
        )
        resume: ApprovalResume | None = None
        try:
            if command.kind == "start":
                await self._record_workbench_lifecycle(
                    scope_hash=command.scope_hash,
                    thread_id=command.thread_id,
                    event_id=f"command:{command.command_id}:planning",
                    kind="planning",
                    status=current.run_state.status,
                )
                graph_input: Any = {
                    "envelope": descriptor.model_dump(mode="json")
                }
            elif command.kind == "resume":
                raw_resume = await self._load_model(
                    self._state_key("resume-control", storage_id)
                )
                if raw_resume is None:
                    raise ValueError("trusted approval resume data is unavailable")
                resume = ApprovalResume.model_validate(raw_resume)
                nonce_claimed = (
                    resume.binding is None
                    or await self.coordinator.claim_approval_nonce(
                        lease, resume.binding.nonce, command.command_id
                    )
                )
                if not nonce_claimed:
                    raise PermissionError("approval nonce is invalid or already claimed")
                if resume.decision is ApprovalDecision.APPROVED:
                    request = current.approval_request
                    await self._record_workbench_lifecycle(
                        scope_hash=command.scope_hash,
                        thread_id=command.thread_id,
                        event_id=f"command:{command.command_id}:executing",
                        kind="executing",
                        status=AgentRunStatus.EXECUTING,
                        step_id=request.step_id if request else None,
                        operation=request.operation if request else None,
                    )
                graph_input = Command(resume=resume.model_dump(mode="json"))
            else:
                recovered = current.model_copy(
                    update={
                        "recovery_requested": True,
                        "safe_runtime_data": {
                            **current.safe_runtime_data,
                            "checkpoint_id": "redis-recovery",
                            "reconciled_side_effect": False,
                        },
                    }
                )
                await graph.aupdate_state(
                    config, {"envelope": recovered.model_dump(mode="json")}
                )
                graph_input = None
            with use_agent_budget(guard):
                result = await _run_with_lease_heartbeat(
                    self.coordinator,
                    lease,
                    graph.ainvoke(
                        graph_input, config, durability="sync"
                    ),
                )
            envelope = AgentGraphEnvelope.model_validate(result["envelope"])
            await self._store_model(
                self._state_key("run-view", storage_id),
                envelope.model_dump(mode="json"),
            )
            event_kind = (
                "awaiting_approval"
                if envelope.run_state.status is AgentRunStatus.AWAITING_APPROVAL
                else envelope.run_state.status.value
            )
            await self.coordinator.append_event(
                lease, event_kind, {"status": envelope.run_state.status.value}
            )
            status = envelope.run_state.status
            if status is AgentRunStatus.AWAITING_APPROVAL:
                request = envelope.approval_request
                await self._record_workbench_lifecycle(
                    scope_hash=command.scope_hash,
                    thread_id=command.thread_id,
                    event_id=(
                        f"approval-required:{request.plan_hash}:{request.step_id}"
                        if request is not None
                        else f"approval-required:{command.command_id}"
                    ),
                    kind="approval_required",
                    status=status,
                    step_id=request.step_id if request else None,
                    operation=request.operation if request else None,
                )
            elif status in {
                AgentRunStatus.COMPLETED,
                AgentRunStatus.CANCELLED,
                AgentRunStatus.FAILED,
            }:
                error = envelope.run_state.last_error
                await self._record_workbench_lifecycle(
                    scope_hash=command.scope_hash,
                    thread_id=command.thread_id,
                    event_id=f"terminal:{status.value}",
                    kind=status.value,
                    status=status,
                    error_code=error.code if error else None,
                    safe_message=error.safe_message if error else None,
                )
            if resume is not None and resume.binding is not None:
                if not await self.coordinator.finalize_approval_nonce(
                    lease, resume.binding.nonce, command.command_id
                ):
                    raise PermissionError("approval nonce finalization failed")
            await self.coordinator.redis.set(
                processed_key,
                "1",
                ex=self.coordinator.settings.state_ttl_seconds,
            )
            if command.kind == "resume":
                await self.coordinator.redis.delete(
                    self._state_key("resume-control", storage_id)
                )
            if (
                self.workbench_store is not None
                and envelope.run_state.status
                in {
                    AgentRunStatus.COMPLETED,
                    AgentRunStatus.CANCELLED,
                    AgentRunStatus.FAILED,
                }
            ):
                await self.workbench_store.release_active(
                    command.scope_hash, command.thread_id
                )
            return envelope
        finally:
            guard.close()
            await self.coordinator.release_lease(lease)
