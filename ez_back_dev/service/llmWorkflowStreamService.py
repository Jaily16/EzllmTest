from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

from dao import testProjectDao
from llm.streaming import get_stream_model_metadata
from service.llmWorkflowAnalysisStreamService import stream_analysis_operation
from service.llmWorkflowCaseStreamService import stream_case_operation
from service.llmWorkflowStreamCore import (
    DisconnectCheck,
    WorkflowContext,
    WorkflowStreamError,
    aggregate_usage,
    ensure_connected,
    event,
    progress,
)


ANALYSIS_OPERATIONS = {
    "unit_menu",
    "unit_info",
    "integration_menu",
    "integration_info",
    "api_info",
    "ui_info",
    "db_info",
    "functional_info",
    "nonfunctional_info",
    "acceptance_info",
}
CASE_OPERATIONS = {
    "unit_case",
    "integration_case",
    "api_case",
    "ui_case",
    "db_case",
    "functional_case",
    "nonfunctional_case",
    "acceptance_case",
}
SUPPORTED_WORKFLOW_OPERATIONS = ANALYSIS_OPERATIONS | CASE_OPERATIONS


def ensure_supported_workflow(operation: str) -> None:
    if operation not in SUPPORTED_WORKFLOW_OPERATIONS:
        raise WorkflowStreamError(
            "unsupported_operation",
            f"不支持的流式操作：{operation}",
            status=400,
            retryable=False,
        )


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
    metadata = get_stream_model_metadata(llm_name)
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
    yield progress("workflow", "流式执行链已启动", 10)

    result: Any = None
    stream = (
        stream_analysis_operation(context)
        if operation in ANALYSIS_OPERATIONS
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

    yield event("usage", **aggregate_usage(context))
    yield progress("generated", "模型输出已完整生成", 93)
    await ensure_connected(context)
    if context.pending_info:
        yield progress("persist", "正在保存可复用的分析结果", 96)
        saved = await asyncio.to_thread(
            testProjectDao.save_project_info_values,
            pid,
            context.pending_info,
        )
        if not saved:
            raise WorkflowStreamError(
                "persistence_error",
                "模型结果已生成，但保存数据库失败",
                status=500,
                retryable=True,
            )
    await ensure_connected(context)
    yield event("result", result=result)
    yield progress("completed", "流式执行完成", 100)
    yield event(
        "completed",
        saved=True,
        from_cache=False,
        operation=operation,
    )
