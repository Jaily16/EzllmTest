"""Shared construction for the isolated Agent API and worker processes."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from infrastructure.llm.gateway import get_model_spec, provider_options
from infrastructure.llm.stream import ModelStreamEvent, stream_chat_completion
from service.agent.internal_adapter import InternalAgentToolAdapter
from service.agent.planner import (
    PLANNER_RESPONSE_FORMAT,
    ProviderAgentPlanner,
    build_planner_provider_prompt,
)
from service.agent.coordinator import (
    AgentRedisCoordinator,
    agent_redis_settings_from_environment,
)
from service.agent.runtime_contracts import ProjectObservation
from service.agent.runtime import AgentRuntimeService
from service.agent.executor import ToolInvocationContext
from service.agent.context import AgentContextAssembler
from service.agent.tool_schemas import ToolExecutionStatus
from service.agent.workbench_service import AgentWorkbenchService
from service.agent.workbench_store import AgentWorkbenchStore
from service.workflow.artifacts import lookup_workflow_artifact
from service.workflow.catalog import get_workflow_definition
from service.workflow.budget import WorkflowBudgetProfile


_PLANNER_PROFILE = WorkflowBudgetProfile(
    map_output_tokens=4_096,
    structured_output_tokens=4_096,
    final_output_tokens=4_096,
    max_context_tokens=64_000,
    reasoning_mode="off",
    reasoning_budget=None,
    stage="structured",
)


async def _provider_plan(
    request: dict[str, Any], *, model_label: str
) -> dict[str, Any]:
    """处理provider计划并返回现有契约规定的结果。

    参数:
        `request`：当前请求对象。
        `model_label`：可信模型标签。

    返回:
        `dict[str, Any]`，内容保持现有调用方契约。

    异常:
        `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""

    get_model_spec(model_label)
    prompt = build_planner_provider_prompt(request)
    options = provider_options(_PLANNER_PROFILE, model_label)
    options["response_format"] = PLANNER_RESPONSE_FORMAT
    # K3 supplies its own reasoning-compatible sampling policy. Do not pass
    # the legacy GLM thinking toggle or temperature override to that model.
    if "temperature" in options:
        options["temperature"] = 0
    content: list[str] = []
    async for event in stream_chat_completion(
        model_label,
        prompt,
        4_096,
        request_options=options,
    ):
        if isinstance(event, ModelStreamEvent) and event.kind == "content":
            content.append(event.text)
    try:
        value = json.loads("".join(content))
    except json.JSONDecodeError as exc:
        raise ValueError("planner returned invalid structured output") from exc
    if not isinstance(value, dict):
        raise ValueError("planner returned invalid structured output")
    return value


def _status_data(result) -> dict[str, Any]:
    """处理状态DATA并返回现有契约规定的结果。

    参数:
        `result`：调用方传入的现有参数。

    返回:
        `dict[str, Any]`，内容保持现有调用方契约。

    异常:
        `RuntimeError`：输入、状态或下游结果不满足现有约束时抛出。"""
    if result.status is not ToolExecutionStatus.SUCCESS or not isinstance(
        result.data, dict
    ):
        raise RuntimeError("project status observation failed")
    return result.data


def _text(value: Any, default: str) -> str:
    """处理文本并返回现有契约规定的结果。"""
    return value if isinstance(value, str) and value else default


async def _default_observer(
    adapter: InternalAgentToolAdapter, scope
) -> ProjectObservation:
    """构造默认观察器。

    参数:
        `adapter`：沿用签名中 `InternalAgentToolAdapter` 类型约束的输入。
        `scope`：调用方传入的现有参数。

    返回:
        `ProjectObservation`，内容保持现有调用方契约。"""
    context = ToolInvocationContext(project_scope=scope)
    setup = _status_data(await adapter.invoke("project_setup_status", {}, context))
    analysis = _status_data(
        await adapter.invoke("project_analysis_status", {}, context)
    )
    workflow = _status_data(
        await adapter.invoke("project_workflow_status", {}, context)
    )
    completed = workflow.get("completed_operations", ())
    stale = workflow.get("stale_operations", ())
    return ProjectObservation(
        setup_stage=_text(setup.get("stage"), "unknown"),
        analysis_ready=bool(
            analysis.get("ready", analysis.get("analysis_ready", False))
        ),
        workflow_stage=_text(workflow.get("stage"), "unknown"),
        completed_operations=(
            tuple(item for item in completed if isinstance(item, str))
            if isinstance(completed, (list, tuple))
            else ()
        ),
        stale_operations=(
            tuple(item for item in stale if isinstance(item, str))
            if isinstance(stale, (list, tuple))
            else ()
        ),
        source_revision=(
            workflow.get("source_revision") or setup.get("source_revision")
        ),
    )


async def _default_artifact_reconciler(call, context):
    """构造默认产物协调器。

    参数:
        `call`：调用方传入的现有参数。
        `context`：调用方传入的现有参数。"""
    definition = get_workflow_definition(call.operation)
    payload = {
        key: value
        for key, value in (
            context.execution_arguments or call.arguments
        ).items()
        if key != "regenerate"
    }
    lookup = await asyncio.to_thread(
        lookup_workflow_artifact,
        context.project_scope.project_id,
        definition,
        payload,
        call.model_label,
    )
    if (
        lookup.artifact is None
        or context.run_state is None
        or lookup.key.source_revision != context.run_state.source_revision
    ):
        return None
    from service.agent.tool_schemas import ToolExecutionResult, ToolUsageSummary

    return ToolExecutionResult(
        tool_name=f"workflow_{call.operation}",
        operation=call.operation,
        status=ToolExecutionStatus.SUCCESS,
        data=lookup.artifact.result,
        from_cache=True,
        saved=True,
        source_revision=lookup.artifact.key.source_revision,
        artifact_key=definition.result_artifact,
        usage=ToolUsageSummary(
            input_tokens=0,
            output_tokens=0,
            model_calls=0,
            embedding_calls=0,
            tool_calls=0,
            estimated_cost_units=0,
        ),
    )


def build_default_runtime_service() -> AgentRuntimeService:
    """构建默认运行时服务，并遵循现有调用契约。"""
    coordinator = AgentRedisCoordinator(agent_redis_settings_from_environment())
    adapter = InternalAgentToolAdapter()
    store = AgentWorkbenchStore(coordinator)
    return AgentRuntimeService(
        coordinator=coordinator,
        planner=ProviderAgentPlanner(_provider_plan),
        observer=lambda scope: _default_observer(adapter, scope),
        tool_adapter=adapter,
        artifact_reconciler=_default_artifact_reconciler,
        workbench_store=store,
        context_assembler=AgentContextAssembler(),
    )


def build_default_workbench_service() -> AgentWorkbenchService:
    """构建默认工作台服务，并遵循现有调用契约。

    返回:
        `AgentWorkbenchService`，内容保持现有调用方契约。

    异常:
        `RuntimeError`：输入、状态或下游结果不满足现有约束时抛出。"""
    runtime = build_default_runtime_service()
    if not isinstance(runtime.workbench_store, AgentWorkbenchStore):
        raise RuntimeError("default runtime has no workbench store")
    return AgentWorkbenchService(runtime, runtime.workbench_store)
