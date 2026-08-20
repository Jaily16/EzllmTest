from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, TypeVar

from pydantic import BaseModel

from llm.streaming import (
    FINAL_MAX_TOKENS,
    INTERMEDIATE_MAX_TOKENS,
    TokenUsage,
    combine_token_usage,
    ensure_non_empty_response,
    stream_chat_completion,
)
from service.llmTestPlanService import TEST_PLAN_MINIMUM_TIMEOUT_SECONDS


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


def event(event_name: str, **data: Any) -> dict[str, Any]:
    return {"event": event_name, "data": data}


def progress(
    stage: str,
    label: str,
    percent: int,
    *,
    current: int | None = None,
    total: int | None = None,
) -> dict[str, Any]:
    return event(
        "progress",
        stage=stage,
        label=label,
        percent=percent,
        current=current,
        total=total,
    )


async def ensure_connected(context: WorkflowContext) -> None:
    if context.is_disconnected is not None and await context.is_disconnected():
        raise asyncio.CancelledError


def prompt_with_content(template: str, content: str) -> str:
    return f"{template}\n\n{content}"


def require_string(payload: dict[str, Any], name: str, *, allow_empty: bool = False) -> str:
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
    schema = json.dumps(model.model_json_schema(), ensure_ascii=False)
    return (
        f"{prompt_text}\n\n请只输出一个符合以下 JSON Schema 的 JSON 对象，"
        f"不要输出 Markdown 或解释文字：\n{schema}"
    )


async def stream_model_call(
    context: WorkflowContext,
    prompt_text: str,
    *,
    stage: str,
    label: str,
    max_tokens: int = FINAL_MAX_TOKENS,
    output_event: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    content_parts: list[str] = []
    usage: TokenUsage | None = None
    async for model_event in stream_chat_completion(
        context.llm_name,
        prompt_text,
        max_tokens,
        minimum_timeout_seconds=TEST_PLAN_MINIMUM_TIMEOUT_SECONDS,
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
    if not documents:
        raise WorkflowStreamError(
            "documents_empty",
            "文档拆分或检索后没有可分析的内容",
            status=422,
            retryable=False,
        )
    summaries: list[str] = []
    total = len(documents)
    map_end = max(start_percent, end_percent - 10)
    for index, document in enumerate(documents, start=1):
        await ensure_connected(context)
        value = ""
        async for item in stream_model_call(
            context,
            prompt_with_content(map_prompt, document.page_content),
            stage=f"{stage_prefix}_map_{index}",
            label=f"{label}：分块 {index}/{total}",
            max_tokens=INTERMEDIATE_MAX_TOKENS,
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
    await ensure_connected(context)
    yield progress(
        f"{stage_prefix}_reduce",
        f"{label}：正在汇总",
        map_end,
    )
    result = ""
    async for item in stream_model_call(
        context,
        prompt_with_content(reduce_prompt, "\n\n".join(summaries)),
        stage=f"{stage_prefix}_reduce",
        label=f"{label}：汇总生成",
        output_event=output_event,
    ):
        if item["event"] == "_model_completed":
            result = item["data"]["content"]
        else:
            yield item
    yield event("_workflow_value", value=result)


def aggregate_usage(context: WorkflowContext) -> dict[str, int | None]:
    return combine_token_usage(context.usages).as_dict()


def rag_prompt(question: str, context_text: str) -> str:
    return (
        "请仅根据以下检索到的软件测试知识库上下文回答问题；若上下文不足，请明确说明。"
        f"\n\n知识库上下文：\n{context_text}\n\n问题：\n{question}"
    )
