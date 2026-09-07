from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, TypeVar

from pydantic import BaseModel
from langchain_core.documents import Document

from prompt.templates import (
    build_grounded_prompt,
    build_structured_output_prompt,
)
from infrastructure.llm.stream import (
    FINAL_MAX_TOKENS,
    INTERMEDIATE_MAX_TOKENS,
    TokenUsage,
    combine_token_usage,
    ensure_non_empty_response,
    stream_chat_completion,
)
from infrastructure.llm.gateway import provider_options
from service.workflow.test_plan import TEST_PLAN_MINIMUM_TIMEOUT_SECONDS
from service.workflow.budget import (
    bound_prompt_context,
    profile_for,
    stage_for_model_call,
)
from service.workflow.long_text import effective_context_budget
from service.project.documents import num_tokens_from_string


DisconnectCheck = Callable[[], Awaitable[bool]]
StructuredModel = TypeVar("StructuredModel", bound=BaseModel)


class WorkflowStreamError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: int = 500,
        retryable: bool = True,
    ) -> None:
        """初始化实例并保存后续操作所需的依赖与状态。"""
        super().__init__(message)
        self.code = code
        self.status = status
        self.retryable = retryable


@dataclass
class WorkflowContext:
    pid: str
    llm_name: str
    operation: str
    payload: dict[str, Any]
    regenerate: bool = False
    is_disconnected: DisconnectCheck | None = None
    usages: list[TokenUsage] = field(default_factory=list)
    pending_info: dict[int, str] = field(default_factory=dict)
    source_revision: str | None = None


def event(event_name: str, **data: Any) -> dict[str, Any]:
    """处理事件并返回现有契约规定的结果。"""
    return {"event": event_name, "data": data}


def progress(
    stage: str,
    label: str,
    percent: int,
    *,
    current: int | None = None,
    total: int | None = None,
) -> dict[str, Any]:
    """处理进度并返回现有契约规定的结果。"""
    return event(
        "progress",
        stage=stage,
        label=label,
        percent=percent,
        current=current,
        total=total,
    )


async def ensure_connected(context: WorkflowContext) -> None:
    """确保连接状态，并遵循现有调用契约。

    参数:
        `context`：沿用签名中 `WorkflowContext` 类型约束的输入。

    异常:
        `CancelledError`：输入、状态或下游结果不满足现有约束时抛出。"""
    if context.is_disconnected is not None and await context.is_disconnected():
        raise asyncio.CancelledError


def require_source_revision(context: WorkflowContext) -> str:
    """读取并校验当前项目 source revision。

    参数:
        `context`：沿用签名中 `WorkflowContext` 类型约束的输入。

    返回:
        `str`，内容保持现有调用方契约。

    异常:
        `WorkflowStreamError`：输入、状态或下游结果不满足现有约束时抛出。"""
    if not context.source_revision:
        raise WorkflowStreamError(
            "source_revision_missing",
            "项目文档版本尚未确定",
            status=422,
            retryable=False,
        )
    return context.source_revision


def prompt_with_content(template: str, content: str) -> str:
    """基于内容构造提示词。"""
    return f"{template}\n\n{content}"


def require_string(payload: dict[str, Any], name: str, *, allow_empty: bool = False) -> str:
    """读取并校验非空字符串字段。

    参数:
        `payload`：符合现有契约的载荷。
        `name`：目标名称。
        `allow_empty`：沿用签名中 `bool` 类型约束的输入。

    返回:
        `str`，内容保持现有调用方契约。

    异常:
        `WorkflowStreamError`：输入、状态或下游结果不满足现有约束时抛出。"""
    value = payload.get(name)
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise WorkflowStreamError(
            "invalid_payload",
            f"请求缺少有效字段：{name}",
            status=422,
            retryable=False,
        )
    return value


def require_integer(payload: dict[str, Any], name: str) -> int:
    """读取并校验整数字段。

    参数:
        `payload`：符合现有契约的载荷。
        `name`：目标名称。

    返回:
        `int`，内容保持现有调用方契约。

    异常:
        `WorkflowStreamError`：输入、状态或下游结果不满足现有约束时抛出。"""
    value = payload.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise WorkflowStreamError(
            "invalid_payload",
            f"请求缺少有效字段：{name}",
            status=422,
            retryable=False,
        )
    return value


def parse_structured_result(
    content: str, model: type[StructuredModel]
) -> StructuredModel:
    """解析结构化结果，并遵循现有调用契约。

    参数:
        `content`：沿用签名中 `str` 类型约束的输入。
        `model`：沿用签名中 `type[StructuredModel]` 类型约束的输入。

    返回:
        `StructuredModel`，内容保持现有调用方契约。

    异常:
        `WorkflowStreamError`：输入、状态或下游结果不满足现有约束时抛出。"""
    stripped = content.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start < 0 or end < start:
        raise WorkflowStreamError(
            "structured_output_error",
            "模型未返回有效的结构化结果，请重试",
            status=502,
            retryable=True,
        )
    try:
        return model.model_validate_json(stripped[start : end + 1])
    except (ValueError, TypeError) as exc:
        raise WorkflowStreamError(
            "structured_output_error",
            "模型返回的结构化结果格式无效，请重试",
            status=502,
            retryable=True,
        ) from exc


def structured_prompt(prompt_text: str, model: type[BaseModel]) -> str:
    """处理结构化提示词并返回现有契约规定的结果。"""
    schema = json.dumps(model.model_json_schema(), ensure_ascii=False)
    return build_structured_output_prompt(prompt_text, schema)


async def stream_model_call(
    context: WorkflowContext,
    prompt_text: str,
    *,
    stage: str,
    label: str,
    max_tokens: int | None = None,
    output_event: str | None = None,
    instruction_text: str | None = None,
    context_text: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """在预算、取消与错误边界内流式调用选定模型，并按既有事件顺序输出分片。

    参数:
        `context`：沿用签名中 `WorkflowContext` 类型约束的输入。
        `prompt_text`：沿用签名中 `str` 类型约束的输入。
        `stage`：沿用签名中 `str` 类型约束的输入。
        `label`：沿用签名中 `str` 类型约束的输入。
        `max_tokens`：沿用签名中 `int | None` 类型约束的输入。
        `output_event`：沿用签名中 `str | None` 类型约束的输入。
        `instruction_text`：沿用签名中 `str | None` 类型约束的输入。
        `context_text`：沿用签名中 `str | None` 类型约束的输入。

    返回:
        `AsyncIterator[dict[str, Any]]`，内容保持现有调用方契约。"""
    budget_stage = stage_for_model_call(stage)
    budget = profile_for(context.operation, budget_stage)
    requested_max_tokens = max_tokens or FINAL_MAX_TOKENS
    effective_max_tokens = min(
        requested_max_tokens,
        budget.output_token_limit,
    )
    request_options = provider_options(budget, context.llm_name)
    request_options["max_tokens"] = min(
        int(request_options["max_tokens"]),
        effective_max_tokens,
    )
    context_budget = effective_context_budget(
        context.operation,
        budget_stage,
        context.llm_name,
    )
    if context_text is None:
        instruction = ""
        source_context = prompt_text
    else:
        instruction = instruction_text if instruction_text is not None else prompt_text
        source_context = context_text
    bounded = bound_prompt_context(instruction, source_context, context_budget)
    if bounded.reduced:
        yield progress(
            f"{stage}_context_reduce",
            "输入上下文已按 Token 预算压缩",
            0,
            current=bounded.selected_context_tokens,
            total=bounded.input_context_tokens,
        )
    content_parts: list[str] = []
    usage: TokenUsage | None = None
    async for model_event in stream_chat_completion(
        context.llm_name,
        bounded.prompt,
        effective_max_tokens,
        minimum_timeout_seconds=TEST_PLAN_MINIMUM_TIMEOUT_SECONDS,
        request_options=request_options,
    ):
        if model_event.kind == "reasoning":
            yield event(
                "reasoning_delta",
                stage=stage,
                label=label,
                text=model_event.text,
            )
        elif model_event.kind == "content":
            content_parts.append(model_event.text)
            if output_event:
                yield event(output_event, text=model_event.text)
        elif model_event.kind == "usage":
            usage = model_event.usage
    content = ensure_non_empty_response(
        context.llm_name, "".join(content_parts)
    )
    context.usages.append(usage or TokenUsage())
    yield event("_model_completed", content=content)


def _split_text_within_budget(
    text: str,
    max_tokens: int,
    token_counter: Callable[[str], int],
) -> list[str]:
    """拆分文本within预算，并遵循现有调用契约。

    参数:
        `text`：沿用签名中 `str` 类型约束的输入。
        `max_tokens`：沿用签名中 `int` 类型约束的输入。
        `token_counter`：沿用签名中 `Callable[[str], int]` 类型约束的输入。

    返回:
        `list[str]`，内容保持现有调用方契约。"""
    if not text:
        return []
    if token_counter(text) <= max_tokens:
        return [text]
    parts: list[str] = []
    remaining = text
    while remaining:
        if token_counter(remaining) <= max_tokens:
            parts.append(remaining)
            break
        low = 1
        high = len(remaining)
        while low < high:
            midpoint = (low + high + 1) // 2
            if token_counter(remaining[:midpoint]) <= max_tokens:
                low = midpoint
            else:
                high = midpoint - 1
        cut = max(low, 1)
        boundary = max(
            remaining.rfind("\n", max(0, cut // 2), cut),
            remaining.rfind(" ", max(0, cut // 2), cut),
        )
        if boundary > 0:
            cut = boundary + 1
        part = remaining[:cut]
        if not part:
            part = remaining[:1]
            cut = 1
        parts.append(part)
        remaining = remaining[cut:]
    return parts


def partition_texts_within_budget(
    values: Sequence[str],
    max_tokens: int,
    *,
    token_counter: Callable[[str], int] = num_tokens_from_string,
) -> list[list[str]]:
    """分组texts within预算，并遵循现有调用契约。

    参数:
        `values`：沿用签名中 `Sequence[str]` 类型约束的输入。
        `max_tokens`：沿用签名中 `int` 类型约束的输入。
        `token_counter`：沿用签名中 `Callable[[str], int]` 类型约束的输入。

    返回:
        `list[list[str]]`，内容保持现有调用方契约。

    异常:
        `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""

    if max_tokens <= 0:
        raise ValueError("max_tokens must be positive")
    pieces = [
        piece
        for value in values
        for piece in _split_text_within_budget(value, max_tokens, token_counter)
        if piece
    ]
    batches: list[list[str]] = []
    current: list[str] = []
    for piece in pieces:
        candidate = "\n\n".join([*current, piece])
        if current and token_counter(candidate) > max_tokens:
            batches.append(current)
            current = [piece]
        else:
            current.append(piece)
    if current:
        batches.append(current)
    return batches


def split_documents_within_budget(
    documents: Sequence[Any],
    max_tokens: int,
    *,
    token_counter: Callable[[str], int] = num_tokens_from_string,
) -> list[Any]:
    """拆分文档within预算，并遵循现有调用契约。

    参数:
        `documents`：沿用签名中 `Sequence[Any]` 类型约束的输入。
        `max_tokens`：沿用签名中 `int` 类型约束的输入。
        `token_counter`：沿用签名中 `Callable[[str], int]` 类型约束的输入。

    返回:
        `list[Any]`，内容保持现有调用方契约。"""

    result: list[Any] = []
    for document in documents:
        content = str(getattr(document, "page_content", ""))
        parts = _split_text_within_budget(content, max_tokens, token_counter)
        if len(parts) <= 1:
            if parts:
                result.append(document)
            continue
        metadata = dict(getattr(document, "metadata", {}) or {})
        for index, part in enumerate(parts):
            result.append(
                Document(
                    page_content=part,
                    metadata={
                        **metadata,
                        "budget_chunk": index,
                        "budget_chunk_count": len(parts),
                    },
                )
            )
    return result


async def stream_map_reduce(
    context: WorkflowContext,
    documents: Sequence[Any],
    *,
    map_prompt: str,
    reduce_prompt: str,
    stage_prefix: str,
    label: str,
    start_percent: int = 30,
    end_percent: int = 70,
    output_event: str = "answer_delta",
) -> AsyncIterator[dict[str, Any]]:
    """流式处理映射reduce，并遵循现有调用契约。

    参数:
        `context`：沿用签名中 `WorkflowContext` 类型约束的输入。
        `documents`：沿用签名中 `Sequence[Any]` 类型约束的输入。
        `map_prompt`：沿用签名中 `str` 类型约束的输入。
        `reduce_prompt`：沿用签名中 `str` 类型约束的输入。
        `stage_prefix`：沿用签名中 `str` 类型约束的输入。
        `label`：沿用签名中 `str` 类型约束的输入。
        `start_percent`：沿用签名中 `int` 类型约束的输入。
        `end_percent`：沿用签名中 `int` 类型约束的输入。
        `output_event`：沿用签名中 `str` 类型约束的输入。

    返回:
        `AsyncIterator[dict[str, Any]]`，内容保持现有调用方契约。

    异常:
        `WorkflowStreamError`：输入、状态或下游结果不满足现有约束时抛出。"""
    if not documents:
        raise WorkflowStreamError(
            "documents_empty",
            "文档拆分或检索后没有可分析的内容",
            status=422,
            retryable=False,
        )
    map_budget = effective_context_budget(
        context.operation,
        "map",
        context.llm_name,
    )
    map_documents = split_documents_within_budget(documents, map_budget)
    summaries: list[str] = []
    total = len(map_documents)
    map_end = max(start_percent, end_percent - 10)
    for index, document in enumerate(map_documents, start=1):
        await ensure_connected(context)
        value = ""
        async for item in stream_model_call(
            context,
            "",
            stage=f"{stage_prefix}_map_{index}",
            label=f"{label}：分块 {index}/{total}",
            max_tokens=INTERMEDIATE_MAX_TOKENS,
            instruction_text=map_prompt,
            context_text=document.page_content,
        ):
            if item["event"] == "_model_completed":
                value = item["data"]["content"]
            else:
                yield item
        summaries.append(value)
        yield progress(
            f"{stage_prefix}_map",
            f"{label}：已完成分块 {index}/{total}",
            start_percent + round((map_end - start_percent) * index / total),
            current=index,
            total=total,
        )
    reduce_budget = effective_context_budget(
        context.operation,
        "final",
        context.llm_name,
    )
    level = 0
    batches = partition_texts_within_budget(summaries, reduce_budget)
    while len(batches) > 1:
        if level >= 8:
            raise WorkflowStreamError(
                "reduce_not_converging",
                "长文档分层汇总未能收敛，请缩小文档范围后重试",
                status=422,
                retryable=True,
            )
        reduced_level: list[str] = []
        for batch_index, batch in enumerate(batches, start=1):
            await ensure_connected(context)
            yield progress(
                f"{stage_prefix}_reduce_level_{level}",
                f"{label}：分层汇总 {batch_index}/{len(batches)}",
                map_end,
                current=batch_index,
                total=len(batches),
            )
            value = ""
            async for item in stream_model_call(
                context,
                "",
                stage=f"{stage_prefix}_reduce_level_{level}_{batch_index}",
                label=f"{label}：分层汇总",
                instruction_text=reduce_prompt,
                context_text="\n\n".join(batch),
            ):
                if item["event"] == "_model_completed":
                    value = item["data"]["content"]
                else:
                    yield item
            reduced_level.append(value)
        summaries = reduced_level
        batches = partition_texts_within_budget(summaries, reduce_budget)
        level += 1

    await ensure_connected(context)
    yield progress(f"{stage_prefix}_reduce", f"{label}：正在汇总", map_end)
    result = ""
    final_context = "\n\n".join(batches[0]) if batches else ""
    async for item in stream_model_call(
        context,
        "",
        stage=f"{stage_prefix}_reduce",
        label=f"{label}：汇总生成",
        output_event=output_event,
        instruction_text=reduce_prompt,
        context_text=final_context,
    ):
        if item["event"] == "_model_completed":
            result = item["data"]["content"]
        else:
            yield item
    yield event("_workflow_value", value=result)


def aggregate_usage(context: WorkflowContext) -> dict[str, int | None]:
    """汇总用量，并遵循现有调用契约。"""
    return combine_token_usage(context.usages).as_dict()


def usage_counters(context: WorkflowContext) -> dict[str, int | None]:
    """处理用量counters并返回现有契约规定的结果。"""
    return {
        **aggregate_usage(context),
        "model_call_count": len(context.usages),
    }


def rag_prompt(question: str, context_text: str) -> str:
    """处理RAG提示词并返回现有契约规定的结果。"""
    return build_grounded_prompt(
        f"回答问题：{question}",
        context_text,
        context_label="知识库上下文",
    )
