"""Shared construction for the isolated Agent API and worker processes."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from infrastructure.llm.gateway import SUPPORTED_MODEL_LABEL
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


async def _provider_plan(request: dict[str, Any]) -> dict[str, Any]:
    """Request structured planning while discarding all reasoning events."""

    prompt = build_planner_provider_prompt(request)
    content: list[str] = []
    async for event in stream_chat_completion(
        SUPPORTED_MODEL_LABEL,
        prompt,
        4_096,
        request_options={
            "max_tokens": 4_096,
            "temperature": 0,
            "extra_body": {"thinking": {"type": "disabled"}},
            "response_format": PLANNER_RESPONSE_FORMAT,
        },
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
    if result.status is not ToolExecutionStatus.SUCCESS or not isinstance(
        result.data, dict
    ):
        raise RuntimeError("project status observation failed")
    return result.data


def _text(value: Any, default: str) -> str:
    return value if isinstance(value, str) and value else default


async def _default_observer(
    adapter: InternalAgentToolAdapter, scope
) -> ProjectObservation:
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
    runtime = build_default_runtime_service()
    if not isinstance(runtime.workbench_store, AgentWorkbenchStore):
        raise RuntimeError("default runtime has no workbench store")
    return AgentWorkbenchService(runtime, runtime.workbench_store)
