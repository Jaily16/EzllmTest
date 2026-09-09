# 以显式节点和状态转换组织单 Agent 规划、审批、执行与恢复。
"""Explicit single-Agent LangGraph for approved, resumable workflow execution."""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, TypedDict, cast

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from ezllmtest.modules.agent.domain.contracts import AgentError, AgentRunState, AgentRunStatus, AgentTransitionEvent, ApprovalDecision, TransitionKind, UsageCounters, transition
from ezllmtest.modules.agent.runtime.memory.context import AgentContextAssembler, ContextAssemblyError
from ezllmtest.modules.agent.ports.budget import reserve_tool_budget
from ezllmtest.modules.agent.runtime.planning.planner import AgentPlanner, compile_planned_calls
from ezllmtest.modules.agent.runtime.state.contracts import AgentGraphEnvelope, ApprovalRequest, ApprovalResume, ProjectObservation
from ezllmtest.modules.agent.runtime.execution.executor import ToolInvocationContext
from ezllmtest.modules.agent.runtime.tools.schemas import ToolExecutionResult, ToolExecutionStatus
from ezllmtest.platform.telemetry.agent_telemetry import agent_span, current_agent_trace_carrier, get_agent_telemetry


class AgentGraphState(TypedDict):
    envelope: dict[str, Any]


def graph_plan_hash(state: AgentRunState) -> str:
    """对当前计划生成稳定身份，用于把审批和恢复绑定到同一组工具调用。"""
    plan = []
    for item in state.plan:
        payload = item.model_dump(mode="json")
        # Pydantic serializes a frozenset as a JSON array.  Canonicalize that
        # array explicitly so a checkpoint round-trip cannot invalidate an
        # otherwise identical approval.
        payload["risks"] = sorted(risk.value for risk in item.risks)
        plan.append(payload)
    canonical = json.dumps(
        {
            "run_id": state.run_id,
            "plan_version": state.plan_version,
            "project_scope": state.project_scope.model_dump(mode="json"),
            "source_revision": state.source_revision,
            "budget": state.budget.model_dump(mode="json"),
            "plan": plan,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


async def _resolve(value: Any) -> Any:
    """接受同步值或 awaitable，统一注入回调的调用方式，不额外调度业务任务。"""
    return await value if inspect.isawaitable(value) else value


def _load(state: AgentGraphState) -> AgentGraphEnvelope:
    """将图中的 payload 严格解码为运行契约，拒绝损坏或越界恢复状态。"""
    return AgentGraphEnvelope.model_validate(state["envelope"])


def _dump(envelope: AgentGraphEnvelope) -> AgentGraphState:
    """将类型化运行状态转换为 JSON 图载荷，不序列化任意 Python 对象。"""
    return {"envelope": envelope.model_dump(mode="json")}


def _usage_after_tool(
    envelope: AgentGraphEnvelope,
    result: ToolExecutionResult,
    now: datetime,
) -> UsageCounters:
    """将已完成工具报告的用量并入运行账本，保持累计用量不会因恢复倒退。"""
    previous = envelope.run_state.usage
    usage = result.usage
    elapsed = max(
        previous.elapsed_ms,
        max(0, int((now - envelope.started_at).total_seconds() * 1000)),
    )
    return UsageCounters(
        steps=previous.steps + 1,
        elapsed_ms=elapsed,
        input_tokens=previous.input_tokens + (usage.input_tokens or 0),
        output_tokens=previous.output_tokens + (usage.output_tokens or 0),
        model_calls=previous.model_calls + usage.model_calls,
        embedding_calls=previous.embedding_calls + (usage.embedding_calls or 0),
        tool_calls=previous.tool_calls + usage.tool_calls,
        estimated_cost_units=(
            previous.estimated_cost_units + (usage.estimated_cost_units or 0)
        ),
    )


def _usage_fits(state: AgentRunState, usage: UsageCounters) -> bool:
    """逐维度比较实际用量与预算，任何维度超限都不能继续推进。"""
    return (
        usage.steps <= state.budget.max_steps
        and usage.elapsed_ms <= state.budget.max_elapsed_ms
        and usage.input_tokens <= state.budget.max_input_tokens
        and usage.output_tokens <= state.budget.max_output_tokens
        and usage.model_calls <= state.budget.max_model_calls
        and usage.embedding_calls <= state.budget.max_embedding_calls
        and usage.tool_calls <= state.budget.max_tool_calls
        and usage.estimated_cost_units <= state.budget.max_estimated_cost_units
    )


def build_agent_graph(
    *,
    observer: Callable[[Any], Any],
    planner: AgentPlanner,
    tool_adapter: Any,
    checkpointer: Any,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    cancel_checker: Callable[[AgentRunState], Any] | None = None,
    progress_sink: Callable[[AgentRunState, Any], Any] | None = None,
    approval_ttl: timedelta = timedelta(minutes=15),
    context_assembler: AgentContextAssembler | None = None,
):
    """显式连接观察、规划、审批、执行、校验和恢复节点；所有副作用仍经过工具 adapter 和运行状态约束。"""

    async def observe(state: AgentGraphState) -> AgentGraphState:
        """读取可信项目状态并形成规划上下文，不让模型自行声明项目身份或准备结果。"""
        envelope = _load(state)
        observation = ProjectObservation.model_validate(
            await _resolve(observer(envelope.run_state.project_scope))
        )
        run_state = envelope.run_state
        if (
            observation.source_revision is not None
            and observation.source_revision != run_state.source_revision
        ):
            if run_state.status in {
                AgentRunStatus.AWAITING_APPROVAL,
                AgentRunStatus.EXECUTING,
                AgentRunStatus.VALIDATING,
            }:
                run_state = transition(
                    run_state,
                    AgentTransitionEvent(
                        kind=TransitionKind.STALE_DETECTED,
                        new_source_revision=observation.source_revision,
                        occurred_at=clock(),
                    ),
                )
            else:
                run_state = run_state.model_copy(
                    update={"source_revision": observation.source_revision}
                )
        return _dump(
            envelope.model_copy(
                update={"run_state": run_state, "observation": observation}
            )
        )

    async def plan(state: AgentGraphState) -> AgentGraphState:
        """调用注入规划器生成目录内候选调用，计划仍需经过独立校验和审批。"""
        envelope = _load(state)
        run_state = envelope.run_state
        now = clock()
        if now >= envelope.deadline_at:
            if run_state.status is AgentRunStatus.CREATED:
                run_state = transition(
                    run_state,
                    AgentTransitionEvent(
                        kind=TransitionKind.START_PLANNING, occurred_at=now
                    ),
                )
            run_state = transition(
                run_state,
                AgentTransitionEvent(
                    kind=TransitionKind.BUDGET_EXHAUSTED, occurred_at=now
                ),
            )
            return _dump(envelope.model_copy(update={"run_state": run_state}))
        if run_state.status is AgentRunStatus.CREATED:
            run_state = transition(
                run_state,
                AgentTransitionEvent(
                    kind=TransitionKind.START_PLANNING, occurred_at=now
                ),
            )
        if run_state.status is not AgentRunStatus.PLANNING:
            raise ValueError("planner can run only in planning state")
        if envelope.observation is None:
            raise ValueError("planner requires a safe project observation")
        with agent_span(
            "agent.plan",
            {"gen_ai.request.model": envelope.planner_model},
        ):
            proposal = await planner.plan(
                goal=run_state.goal,
                observation=envelope.observation,
                max_steps=run_state.budget.max_steps,
                model_label=envelope.planner_model,
            )
        calls = compile_planned_calls(
            run_state, proposal, execution_model=envelope.execution_model
        )
        run_state = transition(
            run_state,
            AgentTransitionEvent(
                kind=TransitionKind.PLAN_READY,
                plan=calls,
                occurred_at=now,
            ),
        )
        return _dump(
            envelope.model_copy(
                update={
                    "run_state": run_state,
                    "approval_request": None,
                    "tool_result": None,
                }
            )
        )

    def validate_plan(state: AgentGraphState) -> AgentGraphState:
        """核验计划的工具、参数、预算和前置条件，不把模型建议直接视为执行授权。"""
        envelope = _load(state)
        run_state = envelope.run_state
        if not run_state.plan or run_state.plan_version < 1:
            raise ValueError("validated plan is unavailable")
        if len(run_state.plan) > run_state.budget.max_steps:
            raise ValueError("validated plan exceeds the step budget")
        graph_plan_hash(run_state)
        return state

    async def request_approval(state: AgentGraphState) -> AgentGraphState:
        """为待执行计划形成绑定信息并进入人工审批状态，不在等待期间调用付费工具。"""
        envelope = _load(state)
        run_state = envelope.run_state
        if run_state.status is not AgentRunStatus.AWAITING_APPROVAL:
            return _dump(envelope.model_copy(update={"approval_request": None}))
        call = run_state.plan[run_state.current_step_index]
        if context_assembler is not None:
            try:
                call = await asyncio.to_thread(
                    context_assembler.bind_call, run_state, call
                )
            except ContextAssemblyError as exc:
                code = str(exc)
                if code == "context_stale":
                    run_state = transition(
                        run_state,
                        AgentTransitionEvent(
                            kind=TransitionKind.STALE_DETECTED,
                            occurred_at=clock(),
                        ),
                    )
                elif code in {"context_body_in_plan", "context_binding_required"}:
                    run_state = transition(
                        run_state,
                        AgentTransitionEvent(
                            kind=TransitionKind.PLAN_EDITED,
                            occurred_at=clock(),
                        ),
                    )
                else:
                    run_state = transition(
                        run_state,
                        AgentTransitionEvent(
                            kind=TransitionKind.CONTEXT_UNAVAILABLE,
                            error=AgentError(
                                code=code,
                                category="validation",
                                retryable=False,
                                safe_message=(
                                    "Trusted prerequisite context is unavailable; "
                                    "run the prerequisite analysis and replan"
                                ),
                            ),
                            occurred_at=clock(),
                        ),
                    )
                return _dump(
                    envelope.model_copy(
                        update={
                            "run_state": run_state,
                            "approval_request": None,
                        }
                    )
                )
            plan = list(run_state.plan)
            plan[run_state.current_step_index] = call
            run_state = run_state.model_copy(update={"plan": tuple(plan)})
        request = ApprovalRequest(
            run_id=run_state.run_id,
            plan_hash=graph_plan_hash(run_state),
            plan_version=run_state.plan_version,
            step_id=call.step_id,
            operation=call.operation,
            risks=tuple(sorted(call.risks, key=lambda item: item.value)),
            expires_at=clock() + approval_ttl,
        )
        return _dump(
            envelope.model_copy(
                update={
                    "run_state": run_state,
                    "approval_request": request,
                }
            )
        )

    def await_approval(state: AgentGraphState) -> AgentGraphState:
        """处理图中断恢复的审批载荷，确认授权仍匹配当前计划、版本和有效期。"""
        envelope = _load(state)
        request = envelope.approval_request
        if request is None:
            raise ValueError("approval request is unavailable")
        raw_resume = interrupt(request.model_dump(mode="json"))
        resume = ApprovalResume.model_validate(raw_resume)
        if resume.expected_plan_hash != graph_plan_hash(envelope.run_state):
            raise ValueError("approval plan hash does not match")
        run_state = envelope.run_state
        now = clock()
        if resume.decision is ApprovalDecision.APPROVED:
            run_state = transition(
                run_state,
                AgentTransitionEvent(
                    kind=TransitionKind.APPROVED,
                    approval=resume.binding,
                    occurred_at=now,
                ),
            )
        elif resume.decision is ApprovalDecision.EDITED:
            run_state = run_state.model_copy(update={"goal": resume.edited_goal})
            run_state = transition(
                run_state,
                AgentTransitionEvent(
                    kind=TransitionKind.PLAN_EDITED, occurred_at=now
                ),
            )
        elif resume.decision is ApprovalDecision.EXPIRED:
            run_state = transition(
                run_state,
                AgentTransitionEvent(
                    kind=TransitionKind.APPROVAL_EXPIRED, occurred_at=now
                ),
            )
        else:
            run_state = transition(
                run_state,
                AgentTransitionEvent(kind=TransitionKind.REJECTED, occurred_at=now),
            )
        return _dump(
            envelope.model_copy(
                update={"run_state": run_state, "approval_request": None}
            )
        )

    async def execute(state: AgentGraphState) -> AgentGraphState:
        """只执行当前获准步骤；工具层继续核验 scope、预算、取消和幂等身份。"""
        envelope = _load(state)
        run_state = envelope.run_state
        now = clock()
        if now >= envelope.deadline_at:
            run_state = transition(
                run_state,
                AgentTransitionEvent(
                    kind=TransitionKind.BUDGET_EXHAUSTED, occurred_at=now
                ),
            )
            return _dump(envelope.model_copy(update={"run_state": run_state}))
        if cancel_checker is not None and bool(
            await _resolve(cancel_checker(run_state))
        ):
            run_state = transition(
                run_state,
                AgentTransitionEvent(
                    kind=TransitionKind.CANCEL_REQUESTED, occurred_at=now
                ),
            )
            return _dump(envelope.model_copy(update={"run_state": run_state}))
        call = run_state.plan[run_state.current_step_index]
        execution_arguments = dict(call.arguments)
        if context_assembler is not None:
            try:
                execution_arguments = await asyncio.to_thread(
                    context_assembler.hydrate_call, run_state, call
                )
            except ContextAssemblyError:
                run_state = transition(
                    run_state,
                    AgentTransitionEvent(
                        kind=TransitionKind.STALE_DETECTED,
                        occurred_at=now,
                    ),
                )
                return _dump(
                    envelope.model_copy(
                        update={"run_state": run_state, "tool_result": None}
                    )
                )
        run_state = transition(
            run_state,
            AgentTransitionEvent(kind=TransitionKind.TOOL_STARTED, occurred_at=now),
        )
        trace_carrier = current_agent_trace_carrier()
        context = ToolInvocationContext(
            project_scope=run_state.project_scope,
            run_state=run_state,
            approval=run_state.pending_approval,
            is_cancelled=(
                (lambda: cancel_checker(run_state))
                if cancel_checker is not None
                else None
            ),
            progress_sink=(
                (lambda progress: progress_sink(run_state, progress))
                if progress_sink is not None
                else None
            ),
            execution_arguments=execution_arguments,
            trace_id=(trace_carrier.trace_id if trace_carrier else None),
        )
        tool_started = time.perf_counter()
        tool_status = "error"
        telemetry = get_agent_telemetry()
        try:
            reserve_tool_budget()
            with agent_span(
                "agent.tool",
                {
                    "agent.operation": call.operation,
                    "agent.tool.name": f"workflow_{call.operation}",
                },
            ):
                result = await tool_adapter.invoke(
                    f"workflow_{call.operation}",
                    {"model_label": call.model_label, **execution_arguments},
                    context,
                )
            tool_status = result.status.value
        except asyncio.CancelledError:
            tool_status = "cancelled"
            raise
        finally:
            telemetry.counter(
                "ezllm.agent.tool.calls",
                labels={
                    "operation": call.operation,
                    "status": tool_status,
                },
            )
            telemetry.histogram(
                "ezllm.agent.tool.duration",
                (time.perf_counter() - tool_started) * 1_000,
                {
                    "operation": call.operation,
                    "status": tool_status,
                },
            )
        return _dump(
            envelope.model_copy(
                update={"run_state": run_state, "tool_result": result}
            )
        )

    def validate_result(state: AgentGraphState) -> AgentGraphState:
        """核验工具结果和实际用量后推进状态，失败结果不能标记为有效完成。"""
        envelope = _load(state)
        run_state = envelope.run_state
        if run_state.status in {
            AgentRunStatus.CANCELLED,
            AgentRunStatus.FAILED,
            AgentRunStatus.PLANNING,
        }:
            return state
        result = envelope.tool_result
        if result is None:
            error = AgentError(
                code="missing_tool_result",
                category="transient",
                retryable=True,
                safe_message="Tool execution did not return a result",
            )
            run_state = transition(
                run_state,
                AgentTransitionEvent(
                    kind=TransitionKind.TOOL_FAILED,
                    error=error,
                    occurred_at=clock(),
                ),
            )
            return _dump(envelope.model_copy(update={"run_state": run_state}))
        now = clock()
        if result.status is ToolExecutionStatus.CANCELLED:
            run_state = transition(
                run_state,
                AgentTransitionEvent(
                    kind=TransitionKind.CANCEL_REQUESTED, occurred_at=now
                ),
            )
        elif result.stale or result.status is ToolExecutionStatus.STALE:
            run_state = transition(
                run_state,
                AgentTransitionEvent(
                    kind=TransitionKind.STALE_DETECTED,
                    new_source_revision=result.source_revision,
                    occurred_at=now,
                ),
            )
            # The previous observation is now revision-stale.  Clearing it is
            # required both for strict envelope validation and to force a fresh
            # read before the next plan.
            envelope = envelope.model_copy(update={"observation": None})
        elif result.status is ToolExecutionStatus.SUCCESS:
            usage = _usage_after_tool(envelope, result, now)
            if not _usage_fits(run_state, usage):
                run_state = transition(
                    run_state,
                    AgentTransitionEvent(
                        kind=TransitionKind.BUDGET_EXHAUSTED, occurred_at=now
                    ),
                )
            else:
                run_state = transition(
                    run_state,
                    AgentTransitionEvent(
                        kind=TransitionKind.TOOL_SUCCEEDED,
                        usage=usage,
                        side_effect_committed=result.saved,
                        occurred_at=now,
                    ),
                )
        else:
            safe_error = result.error
            category = "approval" if result.status is ToolExecutionStatus.APPROVAL_REQUIRED else (
                "transient" if safe_error is None or safe_error.retryable else "permanent"
            )
            error = AgentError(
                code=safe_error.code if safe_error else "tool_execution_failed",
                category=cast(Any, category),
                retryable=bool(safe_error and safe_error.retryable),
                safe_message=(
                    safe_error.safe_message
                    if safe_error
                    else "Tool execution failed"
                ),
            )
            run_state = transition(
                run_state,
                AgentTransitionEvent(
                    kind=TransitionKind.TOOL_FAILED,
                    error=error,
                    occurred_at=now,
                ),
            )
        return _dump(envelope.model_copy(update={"run_state": run_state}))

    def advance(state: AgentGraphState) -> AgentGraphState:
        """由状态转换规则推进工具步骤，使用明确的尝试状态决定下一个图节点。"""
        envelope = _load(state)
        if envelope.run_state.status is not AgentRunStatus.VALIDATING:
            return state
        run_state = transition(
            envelope.run_state,
            AgentTransitionEvent(
                kind=TransitionKind.VALIDATION_SUCCEEDED, occurred_at=clock()
            ),
        )
        return _dump(
            envelope.model_copy(
                update={"run_state": run_state, "tool_result": None}
            )
        )

    def complete(state: AgentGraphState) -> AgentGraphState:
        """将所有必需步骤完成的运行收束到成功终态，不在终态额外调用模型。"""
        envelope = _load(state)
        if envelope.run_state.status not in {
            AgentRunStatus.COMPLETED,
            AgentRunStatus.CANCELLED,
        }:
            raise ValueError("complete node requires a terminal state")
        return state

    def fail(state: AgentGraphState) -> AgentGraphState:
        """将不可继续的运行收束到失败状态，保留已有有效结果和安全错误信息。"""
        if _load(state).run_state.status is not AgentRunStatus.FAILED:
            raise ValueError("fail node requires a failed state")
        return state

    def recover(state: AgentGraphState) -> AgentGraphState:
        """恢复节点先标记恢复状态并检查已保存进度，不直接重执行未知副作用。"""
        envelope = _load(state)
        if envelope.run_state.status is not AgentRunStatus.FAILED:
            return state
        checkpoint_id = envelope.safe_runtime_data.get("checkpoint_id")
        if not envelope.recovery_requested or not isinstance(checkpoint_id, str):
            return state
        run_state = transition(
            envelope.run_state,
            AgentTransitionEvent(
                kind=TransitionKind.RECOVERY_STARTED,
                checkpoint_id=checkpoint_id,
                occurred_at=clock(),
            ),
        )
        return _dump(envelope.model_copy(update={"run_state": run_state}))

    def reconcile(state: AgentGraphState) -> AgentGraphState:
        """恢复时先对齐当前项目版本、执行状态和已有结果，再决定是否允许继续。"""
        envelope = _load(state)
        if envelope.run_state.status is not AgentRunStatus.RECOVERING:
            return state
        committed = envelope.safe_runtime_data.get("reconciled_side_effect")
        if type(committed) is not bool:
            raise ValueError("recovery reconciliation outcome is unavailable")
        run_state = transition(
            envelope.run_state,
            AgentTransitionEvent(
                kind=TransitionKind.RECOVERY_RECONCILED,
                side_effect_committed=committed,
                occurred_at=clock(),
            ),
        )
        return _dump(envelope.model_copy(update={"run_state": run_state}))

    def start_route(state: AgentGraphState) -> str:
        """根据运行当前状态选择规划、审批等待或执行入口，避免恢复运行重新从头开始。"""
        envelope = _load(state)
        status = envelope.run_state.status
        if status is AgentRunStatus.FAILED and envelope.recovery_requested:
            return "recover"
        if status is AgentRunStatus.RECOVERING:
            return "reconcile"
        if status is AgentRunStatus.EXECUTING:
            return "execute"
        if status is AgentRunStatus.VALIDATING:
            return "advance"
        if status in {AgentRunStatus.COMPLETED, AgentRunStatus.CANCELLED}:
            return "complete"
        return "observe"

    def status_route(state: AgentGraphState) -> str:
        """根据运行状态选择下一节点，避免终态或待审批状态直接进入执行。"""
        status = _load(state).run_state.status
        if status is AgentRunStatus.AWAITING_APPROVAL:
            return "await_approval"
        if status is AgentRunStatus.EXECUTING:
            return "execute"
        if status is AgentRunStatus.VALIDATING:
            return "advance"
        if status is AgentRunStatus.PLANNING:
            return "plan"
        if status is AgentRunStatus.FAILED:
            return "fail"
        if status in {AgentRunStatus.COMPLETED, AgentRunStatus.CANCELLED}:
            return "complete"
        if status is AgentRunStatus.RECOVERING:
            return "reconcile"
        raise ValueError(f"unroutable Agent state: {status.value}")

    def fail_route(state: AgentGraphState) -> str:
        """失败路径返回明确终止分支，不把失败状态推进为正常工具执行。"""
        envelope = _load(state)
        return "recover" if envelope.recovery_requested else "end"

    def instrument_node(name: str, function):
        """为图节点增加低基数观测，观测载荷不包含业务输入或模型正文。"""
        async def wrapped(state: AgentGraphState) -> AgentGraphState:
            """在观测上下文中调用原节点并转发其结果和异常，不改变状态机迁移。"""
            started = time.perf_counter()
            telemetry = get_agent_telemetry()
            status = "error"
            try:
                with agent_span(f"agent.graph.{name}"):
                    result = await _resolve(function(state))
                status = _load(result).run_state.status.value
                return result
            finally:
                telemetry.counter(
                    "ezllm.agent.graph.nodes",
                    labels={"operation": name, "status": status},
                )
                telemetry.histogram(
                    "ezllm.agent.graph.node.duration",
                    (time.perf_counter() - started) * 1_000,
                    {"operation": name, "status": status},
                )

        return wrapped

    builder = StateGraph(AgentGraphState)
    builder.add_node("observe", instrument_node("observe", observe))
    builder.add_node("plan", instrument_node("plan", plan))
    builder.add_node(
        "validate_plan", instrument_node("validate_plan", validate_plan)
    )
    builder.add_node(
        "request_approval",
        instrument_node("request_approval", request_approval),
    )
    builder.add_node(
        "await_approval", instrument_node("await_approval", await_approval)
    )
    builder.add_node("execute", instrument_node("execute", execute))
    builder.add_node(
        "validate_result", instrument_node("validate_result", validate_result)
    )
    builder.add_node("advance", instrument_node("advance", advance))
    builder.add_node("complete", instrument_node("complete", complete))
    builder.add_node("fail", instrument_node("fail", fail))
    builder.add_node("recover", instrument_node("recover", recover))
    builder.add_node("reconcile", instrument_node("reconcile", reconcile))

    builder.add_conditional_edges(
        START,
        start_route,
        {
            "observe": "observe",
            "recover": "recover",
            "reconcile": "reconcile",
            "execute": "execute",
            "advance": "advance",
            "complete": "complete",
        },
    )
    builder.add_edge("observe", "plan")
    builder.add_edge("plan", "validate_plan")
    builder.add_edge("validate_plan", "request_approval")
    builder.add_conditional_edges(
        "request_approval",
        status_route,
        {
            "await_approval": "await_approval",
            "execute": "execute",
            "plan": "observe",
            "fail": "fail",
            "complete": "complete",
        },
    )
    builder.add_conditional_edges(
        "await_approval",
        status_route,
        {
            "execute": "execute",
            "plan": "observe",
            "complete": "complete",
        },
    )
    builder.add_edge("execute", "validate_result")
    builder.add_conditional_edges(
        "validate_result",
        status_route,
        {
            "advance": "advance",
            "plan": "observe",
            "fail": "fail",
            "complete": "complete",
        },
    )
    builder.add_conditional_edges(
        "advance",
        status_route,
        {
            "await_approval": "request_approval",
            "execute": "execute",
            "plan": "observe",
            "complete": "complete",
            "fail": "fail",
        },
    )
    builder.add_conditional_edges(
        "fail", fail_route, {"recover": "recover", "end": END}
    )
    builder.add_edge("recover", "reconcile")
    builder.add_conditional_edges(
        "reconcile",
        status_route,
        {
            "advance": "advance",
            "await_approval": "request_approval",
            "execute": "execute",
            "fail": "fail",
            "complete": "complete",
        },
    )
    builder.add_edge("complete", END)
    return builder.compile(checkpointer=checkpointer)
