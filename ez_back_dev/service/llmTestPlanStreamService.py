from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any
from uuid import uuid4

from dao import testProjectDao
from llm.streaming import (
    FINAL_MAX_TOKENS,
    INTERMEDIATE_MAX_TOKENS,
    TokenUsage,
    combine_token_usage,
    ensure_non_empty_response,
    get_stream_model_metadata,
    stream_chat_completion,
)
from model.ChainJsonModel import TestMenu
from prompt import promptStr as prompt
from service.llmTestPlanService import TEST_PLAN_MINIMUM_TIMEOUT_SECONDS
from tools import documentTools
from tools.InfoType import InfoType
from vectorstore.splitter import (
    testdoc_text_splitter_for_acceptance,
    testdoc_text_splitter_for_menu,
)


DisconnectCheck = Callable[[], Awaitable[bool]]


class TestPlanStreamError(RuntimeError):
    def __init__(
        self, code: str, message: str, *, status: int = 500, retryable: bool = True
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.retryable = retryable


def _event(event: str, **data: Any) -> dict[str, Any]:
    return {"event": event, "data": data}


def _progress(
    stage: str,
    label: str,
    percent: int,
    *,
    current: int | None = None,
    total: int | None = None,
) -> dict[str, Any]:
    return _event(
        "progress",
        stage=stage,
        label=label,
        percent=percent,
        current=current,
        total=total,
    )


async def _ensure_connected(is_disconnected: DisconnectCheck | None) -> None:
    if is_disconnected is not None and await is_disconnected():
        raise asyncio.CancelledError


def _prompt(template: str, content: str) -> str:
    return f"{template} \n\n{content}"


def _parse_test_menu(content: str) -> dict[str, bool]:
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
        raise TestPlanStreamError(
            "menu_parse_error",
            "模型未返回有效的测试菜单，请重试",
            status=502,
            retryable=True,
        )
    try:
        value = json.loads(stripped[start : end + 1])
        return TestMenu.model_validate(value).model_dump()
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        raise TestPlanStreamError(
            "menu_parse_error",
            "模型返回的测试菜单格式无效，请重试",
            status=502,
            retryable=True,
        ) from exc


def _parse_cached_test_menu(content: str | bool | None) -> dict[str, bool] | None:
    if not content or not isinstance(content, str):
        return None
    try:
        return _parse_test_menu(content)
    except TestPlanStreamError:
        return None


async def get_project_analysis_status(pid: str) -> dict[str, Any]:
    summary, plan, menu_content = await asyncio.gather(
        asyncio.to_thread(
            testProjectDao.get_project_info,
            pid,
            InfoType.PROJECT_INITIAL_SUMMARY.value,
        ),
        asyncio.to_thread(
            testProjectDao.get_project_info,
            pid,
            InfoType.PROJECT_TEST_PLAN.value,
        ),
        asyncio.to_thread(
            testProjectDao.get_project_info,
            pid,
            InfoType.PROJECT_TEST_MENU.value,
        ),
    )
    menu = _parse_cached_test_menu(menu_content)
    summary_ready = bool(summary)
    plan_ready = bool(plan)
    menu_ready = menu is not None
    return {
        "summary_ready": summary_ready,
        "plan_ready": plan_ready,
        "menu_ready": menu_ready,
        "ready": summary_ready and plan_ready and menu_ready,
        "menu": menu,
    }


async def _stream_model_call(
    llm_name: str,
    prompt_text: str,
    max_tokens: int,
    *,
    stage: str,
    stage_label: str,
    output_event: str | None,
) -> AsyncIterator[dict[str, Any]]:
    content_parts: list[str] = []
    call_usage: TokenUsage | None = None

    async for model_event in stream_chat_completion(
        llm_name,
        prompt_text,
        max_tokens,
        minimum_timeout_seconds=TEST_PLAN_MINIMUM_TIMEOUT_SECONDS,
    ):
        if model_event.kind == "reasoning":
            yield _event(
                "reasoning_delta",
                stage=stage,
                label=stage_label,
                text=model_event.text,
            )
        elif model_event.kind == "content":
            content_parts.append(model_event.text)
            if output_event:
                yield _event(output_event, text=model_event.text)
        elif model_event.kind == "usage":
            call_usage = model_event.usage

    content = ensure_non_empty_response(llm_name, "".join(content_parts))
    yield _event(
        "model_call_completed",
        content=content,
        usage=call_usage,
    )


async def _collect_model_call(
    llm_name: str,
    prompt_text: str,
    max_tokens: int,
    *,
    stage: str,
    stage_label: str,
    output_event: str | None,
) -> AsyncIterator[dict[str, Any]]:
    async for item in _stream_model_call(
        llm_name,
        prompt_text,
        max_tokens,
        stage=stage,
        stage_label=stage_label,
        output_event=output_event,
    ):
        yield item


async def stream_test_plan(
    pid: str,
    llm_name: str,
    regenerate: bool,
    *,
    is_disconnected: DisconnectCheck | None = None,
) -> AsyncIterator[dict[str, Any]]:
    metadata = get_stream_model_metadata(llm_name)
    yield _event("meta", request_id=uuid4().hex, **metadata)
    yield _progress("validate", "正在校验项目和模型", 5)
    await _ensure_connected(is_disconnected)

    project, project_type, summary_history, plan_history, menu_history = await asyncio.gather(
        asyncio.to_thread(testProjectDao.find_project, pid),
        asyncio.to_thread(testProjectDao.get_project_type, pid),
        asyncio.to_thread(
            testProjectDao.get_project_info,
            pid,
            InfoType.PROJECT_INITIAL_SUMMARY.value,
        ),
        asyncio.to_thread(
            testProjectDao.get_project_info,
            pid,
            InfoType.PROJECT_TEST_PLAN.value,
        ),
        asyncio.to_thread(
            testProjectDao.get_project_info,
            pid,
            InfoType.PROJECT_TEST_MENU.value,
        ),
    )
    if not project or not project_type:
        raise TestPlanStreamError(
            "project_not_ready",
            "项目不存在或尚未完成文档类型分析",
            status=404,
            retryable=False,
        )

    yield _progress("project", "已读取项目资料和历史分析结果", 10)
    await _ensure_connected(is_disconnected)

    cached_menu = _parse_cached_test_menu(menu_history)
    if summary_history and plan_history and cached_menu is not None and not regenerate:
        yield _event("summary_delta", text=summary_history)
        yield _event("answer_delta", text=plan_history)
        yield _event("menu", menu=cached_menu)
        yield _event(
            "usage",
            input_tokens=None,
            reasoning_tokens=None,
            output_tokens=None,
            total_tokens=None,
        )
        yield _progress("completed", "已读取保存的业务分析、测试计划和测试菜单", 100)
        yield _event("completed", saved=True, from_cache=True, ready=True)
        return

    usages: list[TokenUsage] = []
    overflow = project_type.overflow

    summary_content = str(summary_history or "")
    summary_was_generated = regenerate or not summary_content
    if summary_was_generated:
        if overflow:
            summary_source_documents = await asyncio.to_thread(
                documentTools.generate_all_testdocs_docs, pid
            )
            if not summary_source_documents:
                raise TestPlanStreamError(
                    "documents_missing",
                    "没有找到可用于业务分析的项目文档",
                    status=422,
                    retryable=False,
                )
            yield _progress("summary_documents", "业务文档加载完成", 15)
            summary_documents = await asyncio.to_thread(
                testdoc_text_splitter_for_menu.split_documents,
                summary_source_documents,
            )
            if not summary_documents:
                raise TestPlanStreamError(
                    "documents_empty",
                    "业务文档拆分后没有可分析的内容",
                    status=422,
                    retryable=False,
                )
            summary_parts: list[str] = []
            summary_total = len(summary_documents)
            yield _progress(
                "summary_prepare",
                "业务分析提示词准备完成",
                18,
                current=0,
                total=summary_total,
            )
            for index, document in enumerate(summary_documents, start=1):
                await _ensure_connected(is_disconnected)
                call_content = ""
                call_usage: TokenUsage | None = None
                label = f"正在分析业务文档分块 {index}/{summary_total}"
                async for item in _collect_model_call(
                    llm_name,
                    _prompt(
                        prompt.TESTDOC_SUMMARY_MAP_REDUCE_PART_PROMPT_STR,
                        document.page_content,
                    ),
                    INTERMEDIATE_MAX_TOKENS,
                    stage=f"summary_map_{index}",
                    stage_label=label,
                    output_event=None,
                ):
                    if item["event"] == "model_call_completed":
                        call_content = item["data"]["content"]
                        call_usage = item["data"]["usage"]
                    else:
                        yield item
                summary_parts.append(call_content)
                usages.append(call_usage or TokenUsage())
                yield _progress(
                    "summary_map",
                    f"已完成业务文档分块 {index}/{summary_total}",
                    18 + round(12 * index / summary_total),
                    current=index,
                    total=summary_total,
                )
            summary_prompt = _prompt(
                prompt.TESTDOC_SUMMARY_MAP_REDUCE_TOTAL_PROMPT_STR,
                "\n\n".join(summary_parts),
            )
            summary_stage = "summary_reduce"
            summary_label = "正在汇总业务初步分析与总结"
        else:
            all_documents_text = await asyncio.to_thread(
                documentTools.generate_all_testdocs_str, pid
            )
            if not all_documents_text:
                raise TestPlanStreamError(
                    "documents_missing",
                    "没有找到可用于业务分析的项目文档",
                    status=422,
                    retryable=False,
                )
            yield _progress("summary_documents", "业务文档加载完成", 15)
            summary_prompt = _prompt(
                prompt.TESTDOC_SUMMARY_STUFF_PROMPT_STR,
                all_documents_text,
            )
            summary_stage = "summary_generate"
            summary_label = "正在生成业务初步分析与总结"

        await _ensure_connected(is_disconnected)
        yield _progress(summary_stage, summary_label, 32)
        summary_usage: TokenUsage | None = None
        async for item in _collect_model_call(
            llm_name,
            summary_prompt,
            FINAL_MAX_TOKENS,
            stage=summary_stage,
            stage_label=summary_label,
            output_event="summary_delta",
        ):
            if item["event"] == "model_call_completed":
                summary_content = item["data"]["content"]
                summary_usage = item["data"]["usage"]
            else:
                yield item
        usages.append(summary_usage or TokenUsage())
        yield _progress("summary_generated", "业务初步分析与总结已生成", 38)
    else:
        yield _event("summary_delta", text=summary_content)
        yield _progress("summary_cached", "已读取保存的业务初步分析与总结", 38)

    final_content = str(plan_history or "")
    if regenerate or not final_content:
        if overflow in (1, 4):
            source_documents = await asyncio.to_thread(
                documentTools.generate_require_testdocs_docs, pid
            )
            if not source_documents:
                raise TestPlanStreamError(
                    "documents_missing",
                    "没有找到可用于生成测试计划的需求文档",
                    status=422,
                    retryable=False,
                )
            yield _progress("plan_documents", "测试计划所需的需求文档加载完成", 42)
            await _ensure_connected(is_disconnected)

            documents = await asyncio.to_thread(
                testdoc_text_splitter_for_acceptance.split_documents,
                source_documents,
            )
            if not documents:
                raise TestPlanStreamError(
                    "documents_empty",
                    "需求文档拆分后没有可分析的内容",
                    status=422,
                    retryable=False,
                )
            total = len(documents)
            yield _progress(
                "plan_prepare", "测试计划提示词准备完成", 45, current=0, total=total
            )

            summaries: list[str] = []
            for index, document in enumerate(documents, start=1):
                await _ensure_connected(is_disconnected)
                stage = f"plan_map_{index}"
                label = f"正在分析测试计划文档分块 {index}/{total}"
                result_content = ""
                result_usage: TokenUsage | None = None
                async for item in _collect_model_call(
                    llm_name,
                    _prompt(
                        prompt.TEST_PLAN_MAP_REDUCE_PART_PROMPT_STR,
                        document.page_content,
                    ),
                    INTERMEDIATE_MAX_TOKENS,
                    stage=stage,
                    stage_label=label,
                    output_event=None,
                ):
                    if item["event"] == "model_call_completed":
                        result_content = item["data"]["content"]
                        result_usage = item["data"]["usage"]
                    else:
                        yield item
                summaries.append(result_content)
                usages.append(result_usage or TokenUsage())
                yield _progress(
                    "map",
                    f"已完成测试计划文档分块 {index}/{total}",
                    45 + round(20 * index / total),
                    current=index,
                    total=total,
                )

            final_prompt = _prompt(
                prompt.TEST_PLAN_MAP_REDUCE_TOTAL_PROMPT_STR,
                "\n\n".join(summaries),
            )
            final_stage = "plan_reduce"
            final_label = "正在汇总并生成完整测试计划"
        else:
            requirement_text = await asyncio.to_thread(
                documentTools.generate_require_testdocs_str, pid
            )
            if not requirement_text:
                raise TestPlanStreamError(
                    "documents_missing",
                    "没有找到可用于生成测试计划的需求文档",
                    status=422,
                    retryable=False,
                )
            yield _progress("plan_documents", "测试计划所需的需求文档加载完成", 42)
            yield _progress("plan_prepare", "测试计划提示词准备完成", 45)
            final_prompt = _prompt(prompt.TEST_PLAN_STUFF_PROMPT_STR, requirement_text)
            final_stage = "plan_generate"
            final_label = "正在生成完整测试计划"

        await _ensure_connected(is_disconnected)
        yield _progress(final_stage, final_label, 68)
        final_usage: TokenUsage | None = None
        async for item in _collect_model_call(
            llm_name,
            final_prompt,
            FINAL_MAX_TOKENS,
            stage=final_stage,
            stage_label=final_label,
            output_event="answer_delta",
        ):
            if item["event"] == "model_call_completed":
                final_content = item["data"]["content"]
                final_usage = item["data"]["usage"]
            else:
                yield item
        usages.append(final_usage or TokenUsage())
        yield _progress("plan_generated", "测试计划已生成", 76)
    else:
        yield _event("answer_delta", text=final_content)
        yield _progress("plan_cached", "已读取保存的测试计划", 76)

    menu = cached_menu
    if regenerate or summary_was_generated or menu is None:
        await _ensure_connected(is_disconnected)
        yield _progress("menu_generate", "正在分析并生成可用测试菜单", 82)
        menu_prompt = (
            prompt.TESTDOC_JSON_MENU_PROMPT_STR
            + summary_content
            + "\n\n请只输出一个 JSON 对象，不要输出 Markdown。JSON 必须完整包含以下布尔字段："
            + ", ".join(TestMenu.model_fields)
            + "。"
        )
        menu_content = ""
        menu_usage: TokenUsage | None = None
        async for item in _collect_model_call(
            llm_name,
            menu_prompt,
            INTERMEDIATE_MAX_TOKENS,
            stage="menu_generate",
            stage_label="正在判断项目支持的测试类型",
            output_event=None,
        ):
            if item["event"] == "model_call_completed":
                menu_content = item["data"]["content"]
                menu_usage = item["data"]["usage"]
            else:
                yield item
        usages.append(menu_usage or TokenUsage())
        menu = _parse_test_menu(menu_content)
    if menu is None:
        raise TestPlanStreamError(
            "menu_parse_error",
            "测试菜单生成失败，请重试",
            status=502,
            retryable=True,
        )
    yield _event("menu", menu=menu)
    yield _progress("menu_generated", "测试菜单已生成", 90)

    aggregate_usage = combine_token_usage(usages)
    yield _event("usage", **aggregate_usage.as_dict())
    yield _progress("generated", "业务分析、测试计划和测试菜单已准备完成", 92)
    await _ensure_connected(is_disconnected)

    yield _progress("persist", "正在保存业务分析结果", 95)
    await _ensure_connected(is_disconnected)
    saved = await asyncio.to_thread(
        testProjectDao.save_project_analysis_bundle,
        pid,
        summary_content,
        final_content,
        json.dumps(menu, ensure_ascii=False),
    )
    if not saved:
        raise TestPlanStreamError(
            "persistence_error",
            "分析结果已生成，但保存数据库失败",
            status=500,
            retryable=True,
        )

    yield _progress("completed", "业务分析、测试计划和测试菜单已生成并保存", 100)
    yield _event("completed", saved=True, from_cache=False, ready=True)
