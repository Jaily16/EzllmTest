# 为 Agent API 与 worker 装配相同运行能力，进程角色仍由显式配置投影区分。
"""Shared construction for the isolated Agent API and worker processes."""

from __future__ import annotations
from ezllmtest.modules.agent.ports.runtime import RuntimeAdapters
from ezllmtest.modules.agent.infrastructure.budget import RedisAgentBudgetLedger
from ezllmtest.modules.agent.infrastructure.checkpoint import AsyncAgentRedisCheckpointSaver, StrictAgentCheckpointSerializer

import asyncio
import json
from typing import Any

from ezllmtest.platform.ai.gateway import get_model_spec, provider_options
from ezllmtest.platform.ai.stream import ModelStreamEvent, stream_chat_completion
from ezllmtest.modules.agent.runtime.tools.internal_adapter import InternalAgentToolAdapter
from ezllmtest.modules.agent.runtime.planning.planner import PLANNER_RESPONSE_FORMAT, ProviderAgentPlanner, build_planner_provider_prompt
from ezllmtest.modules.agent.infrastructure.coordinator import AgentRedisCoordinator, agent_redis_settings_from_environment
from ezllmtest.modules.agent.runtime.state.contracts import ProjectObservation
from ezllmtest.modules.agent.application.runtime import AgentRuntimeService
from ezllmtest.modules.agent.runtime.execution.executor import ToolInvocationContext
from ezllmtest.modules.agent.runtime.memory.context import AgentContextAssembler
from ezllmtest.modules.agent.runtime.tools.schemas import ToolExecutionStatus
from ezllmtest.modules.agent.application.workbench import AgentWorkbenchService
from ezllmtest.modules.agent.infrastructure.workbench_store import AgentWorkbenchStore
from ezllmtest.modules.generation.ports.artifacts import lookup_workflow_artifact
from ezllmtest.modules.generation.domain.catalog import get_workflow_definition
from ezllmtest.modules.generation.domain.budget import WorkflowBudgetProfile


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
    """把可信运行状态交给注册模型规划路径，模型只返回候选计划，不取得执行权。"""

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
    """将项目公开状态响应转为观察数据，异常或不完整响应不能冒充准备完成。"""
    if result.status is not ToolExecutionStatus.SUCCESS or not isinstance(
        result.data, dict
    ):
        raise RuntimeError("project status observation failed")
    return result.data


def _text(value: Any, default: str) -> str:
    """从已取得项目信息中提取文本值，不在此辅助函数额外读取资料或调用模型。"""
    return value if isinstance(value, str) and value else default


async def _default_observer(
    adapter: InternalAgentToolAdapter, scope
) -> ProjectObservation:
    """通过项目与生成域的 public 接口读取可信准备状态及产物事实，为图观察提供输入。"""
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
    """通过有效产物快照核对先前工具结果，无法证明的副作用不能自动重做。"""
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
    from ezllmtest.modules.agent.runtime.tools.schemas import ToolExecutionResult, ToolUsageSummary

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
    """为 Agent API 和 worker 构造同一套协调器、预算账本、工具和 checkpoint 工厂；实际消费由各入口生命周期启动。"""
    coordinator = AgentRedisCoordinator(agent_redis_settings_from_environment())
    adapter = InternalAgentToolAdapter()
    store = AgentWorkbenchStore(coordinator)
    def checkpoint(command, lease):
        """将受租约保护的存储依赖绑定给 checkpoint adapter。"""
        return AsyncAgentRedisCheckpointSaver(
            coordinator.redis,
            scope_hash=command.scope_hash,
            graph_version=command.graph_version,
            lease_owner=lease.owner,
            fence_token=lease.fence,
            prefix=f"{coordinator.settings.prefix}:checkpoint",
            coordination_prefix=coordinator.settings.prefix,
            ttl_seconds=max(60, coordinator.settings.state_ttl_seconds),
        )

    return AgentRuntimeService(
        runtime_adapters=RuntimeAdapters(StrictAgentCheckpointSerializer(), RedisAgentBudgetLedger(coordinator), checkpoint),
        coordinator=coordinator,
        planner=ProviderAgentPlanner(_provider_plan),
        observer=lambda scope: _default_observer(adapter, scope),
        tool_adapter=adapter,
        artifact_reconciler=_default_artifact_reconciler,
        workbench_store=store,
        context_assembler=AgentContextAssembler(),
    )


def build_default_workbench_service() -> AgentWorkbenchService:
    """由 bootstrap 统一装配 runtime 与工作台存储，业务层不自行构造 Redis adapter。"""
    runtime = build_default_runtime_service()
    if not isinstance(runtime.workbench_store, AgentWorkbenchStore):
        raise RuntimeError("default runtime has no workbench store")
    return AgentWorkbenchService(runtime, runtime.workbench_store)
