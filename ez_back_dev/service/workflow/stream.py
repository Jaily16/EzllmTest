from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

from infrastructure.persistence import project_repository as testProjectDao
from infrastructure.llm.stream import get_stream_model_metadata
from service.workflow import artifacts as workflowArtifactService
from service.workflow.analysis_stream import stream_analysis_operation
from service.workflow.case_stream import stream_case_operation
from service.workflow.stream_core import (
    DisconnectCheck,
    WorkflowContext,
    WorkflowStreamError,
    ensure_connected,
    event,
    progress,
    usage_counters,
)
from service.workflow.catalog import (
    get_workflow_definition,
    list_workflow_definitions,
)
from service.workflow.budget import profile_for


_GENERIC_WORKFLOW_DEFINITIONS = tuple(
    definition
    for definition in list_workflow_definitions()
    if definition.phase != "project"
)
ANALYSIS_OPERATIONS = {
    definition.operation
    for definition in _GENERIC_WORKFLOW_DEFINITIONS
    if definition.phase == "analysis"
}
CASE_OPERATIONS = {
    definition.operation
    for definition in _GENERIC_WORKFLOW_DEFINITIONS
    if definition.phase == "case"
}
SUPPORTED_WORKFLOW_OPERATIONS = ANALYSIS_OPERATIONS | CASE_OPERATIONS


def ensure_supported_workflow(operation: str) -> None:
    try:
        definition = get_workflow_definition(operation)
    except KeyError:
        definition = None
    if definition is None or definition.operation not in SUPPORTED_WORKFLOW_OPERATIONS:
        raise WorkflowStreamError(
            "unsupported_operation",
            f"不支持的流式操作：{operation}",
            status=400,
            retryable=False,
        )


def _cached_answer_text(result: Any) -> str:
    if isinstance(result, str):
        return result
    if not isinstance(result, dict):
        return ""
    for key in (
        "test_cases",
        "unit_info",
        "apis_info",
        "text_info",
        "nonfunctional_info",
    ):
        value = result.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


async def stream_llm_workflow(
    operation: str,
    pid: str,
    llm_name: str,
    payload: dict[str, Any],
    regenerate: bool = False,
    *,
    is_disconnected: DisconnectCheck | None = None,
) -> AsyncIterator[dict[str, Any]]:
    ensure_supported_workflow(operation)
    definition = get_workflow_definition(operation)
    if regenerate and not definition.supports_regenerate:
        raise WorkflowStreamError(
            "regenerate_not_supported",
            f"当前工作流不支持重新生成：{operation}",
            status=422,
            retryable=False,
        )
    metadata = get_stream_model_metadata(llm_name)
    public_budget = profile_for(operation, "final").public_metadata()
    context = WorkflowContext(
        pid=pid,
        llm_name=llm_name,
        operation=operation,
        payload=payload,
        regenerate=regenerate,
        is_disconnected=is_disconnected,
    )
    yield event(
        "meta",
        request_id=uuid4().hex,
        operation=operation,
        artifact_key=definition.result_artifact,
        prompt_version=definition.prompt_version,
        source_corpus=definition.source_corpus,
        persistence=definition.persistence,
        budget=public_budget,
        **metadata,
    )
    yield progress("validate", "正在校验项目、操作和模型", 5)
    await ensure_connected(context)
    project = await asyncio.to_thread(testProjectDao.find_project, pid)
    if not project:
        raise WorkflowStreamError(
            "project_not_found",
            "项目不存在",
            status=404,
            retryable=False,
        )
    if definition.persistence == "artifact":
        lookup = await asyncio.to_thread(
            workflowArtifactService.lookup_workflow_artifact,
            pid,
            definition,
            payload,
            metadata["label"],
        )
    else:
        key = await asyncio.to_thread(
            workflowArtifactService.build_workflow_artifact_key,
            pid,
            definition,
            payload,
            metadata["label"],
        )
        lookup = workflowArtifactService.WorkflowArtifactLookup(
            key=key,
            artifact=None,
            stale=False,
            has_history=False,
        )
    context.source_revision = lookup.key.source_revision
    await asyncio.to_thread(
        workflowArtifactService.validate_workflow_prerequisites,
        pid,
        definition,
        payload,
        lookup.key.source_revision,
    )
    if lookup.stale:
        yield event(
            "stale",
            operation=operation,
            artifact_key=definition.result_artifact,
            source_revision=lookup.key.source_revision,
            reason="source_revision_changed",
        )
    if lookup.artifact is None and lookup.has_history:
        context.regenerate = True
    if lookup.artifact is not None and not regenerate:
        cached_result = lookup.artifact.result
        yield progress("cache", "已读取保存的工作流结果", 92)
        cached_answer = _cached_answer_text(cached_result)
        if cached_answer:
            yield event("answer_delta", text=cached_answer)
        counters = usage_counters(context)
        yield event("usage", **counters)
        yield event(
            "artifact",
            operation=operation,
            artifact_key=definition.result_artifact,
            source_revision=lookup.artifact.key.source_revision,
            prompt_version=lookup.artifact.key.prompt_version,
            model_label=lookup.artifact.key.model_label,
            status="resumed",
            from_cache=True,
        )
        await ensure_connected(context)
        yield event("result", result=cached_result)
        yield progress("completed", "已恢复保存的工作流结果", 100)
        yield event(
            "completed",
            saved=True,
            from_cache=True,
            operation=operation,
            artifact_key=definition.result_artifact,
            source_revision=lookup.key.source_revision,
            **counters,
        )
        return
    yield progress("workflow", "流式执行链已启动", 10)

    result: Any = None
    stream = (
        stream_analysis_operation(context)
        if definition.phase == "analysis"
        else stream_case_operation(context)
    )
    async for item in stream:
        if item["event"] == "_workflow_result":
            result = item["data"]["result"]
        else:
            yield item
    if result is None:
        raise WorkflowStreamError(
            "empty_workflow_result",
            "流式执行链没有返回有效结果",
            status=502,
            retryable=True,
        )

    counters = usage_counters(context)
    yield event("usage", **counters)
    yield progress("generated", "模型输出已完整生成", 93)
    await ensure_connected(context)
    saved = False
    if definition.persistence == "artifact":
        yield progress("persist", "正在保存可复用的工作流结果", 96)
        saved = await asyncio.to_thread(
            workflowArtifactService.save_workflow_artifact,
            pid,
            definition,
            lookup.key,
            payload,
            result,
            context.pending_info,
            call_count=len(context.usages),
        )
        if not saved:
            raise WorkflowStreamError(
                "persistence_error",
                "模型结果已生成，但保存数据库失败",
                status=500,
                retryable=True,
            )
        await ensure_connected(context)
        yield event(
            "artifact",
            operation=operation,
            artifact_key=definition.result_artifact,
            source_revision=lookup.key.source_revision,
            prompt_version=lookup.key.prompt_version,
            model_label=lookup.key.model_label,
            status="saved",
            from_cache=False,
        )
    yield event("result", result=result)
    yield progress("completed", "流式执行完成", 100)
    yield event(
        "completed",
        saved=saved,
        from_cache=False,
        operation=operation,
        artifact_key=definition.result_artifact,
        source_revision=lookup.key.source_revision,
        **counters,
    )
