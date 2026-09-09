# 输出项目分析三件套的阶段事件，全部成功后才确认保存和就绪。
from __future__ import annotations
from ezllmtest.modules.generation.schemas.errors import TestPlanStreamError

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import replace
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

import ezllmtest.modules.projects.public as testProjectDao
from ezllmtest.modules.generation.ports.artifact_store import get_fresh_artifact
from ezllmtest.platform.ai.stream import FINAL_MAX_TOKENS, INTERMEDIATE_MAX_TOKENS, TokenUsage, combine_token_usage, ensure_non_empty_response, get_stream_model_metadata, stream_chat_completion
from ezllmtest.platform.ai.gateway import LLMError, get_model_spec, is_kimi_k3, provider_options
from ezllmtest.modules.generation.schemas.analysis import ProjectAnalysisDigest, TestMenu
import ezllmtest.modules.generation.domain.prompts.text as prompt
from ezllmtest.modules.generation.application.test_plan import TEST_PLAN_MINIMUM_TIMEOUT_SECONDS
from ezllmtest.modules.projects.public import artifact_input_hash, compute_project_source_revision
from ezllmtest.modules.projects.public import collect_project_test_evidence, reconcile_test_menu
from ezllmtest.modules.generation.domain.long_text import LongTextStrategy, effective_context_budget, strategy_for
from ezllmtest.modules.generation.application.stream_core import split_documents_within_budget
from ezllmtest.modules.generation.domain.catalog import get_workflow_definition
from ezllmtest.modules.generation.domain.budget import BudgetStage, WorkflowBudgetProfile, bound_prompt_context, profile_for, stage_for_model_call
import ezllmtest.modules.projects.public as documentTools
from ezllmtest.modules.projects.public import InfoType
from ezllmtest.modules.knowledge.public import testdoc_text_splitter_for_menu


DisconnectCheck = Callable[[], Awaitable[bool]]

PROJECT_ANALYSIS_OPERATION = "project_analysis"
PROJECT_ANALYSIS_PROMPT_VERSION = "project-analysis-v2"
PROJECT_ANALYSIS_BUDGET_PROFILE = "project-analysis-v2"
PROJECT_ANALYSIS_GENERATION_POLICY = "bounded-thinking-high-v2"
PROJECT_ANALYSIS_REPAIR_MAX_CHARS = 12_000
PROJECT_ANALYSIS_ARTIFACT_KEY = get_workflow_definition(
    PROJECT_ANALYSIS_OPERATION
).result_artifact
PROJECT_ANALYSIS_INPUT_HASH = artifact_input_hash(
    PROJECT_ANALYSIS_OPERATION, {}
)


class _ProjectAnalysisBundle(BaseModel):
    summary: str = Field(min_length=1)
    menu: TestMenu
    plan: str = Field(min_length=1)




def _event(event: str, **data: Any) -> dict[str, Any]:
    """组织项目初始分析流的事件信封，不在构造事件时写网络或数据库。"""
    return {"event": event, "data": data}


def _progress(
    stage: str,
    label: str,
    percent: int,
    *,
    current: int | None = None,
    total: int | None = None,
) -> dict[str, Any]:
    """为项目摘要、菜单与计划阶段生成统一进度事件。"""
    return _event(
        "progress",
        stage=stage,
        label=label,
        percent=percent,
        current=current,
        total=total,
    )


async def _ensure_connected(is_disconnected: DisconnectCheck | None) -> None:
    """在下一次模型调用或最终保存前检查断连，取消后不得把草稿提交为有效结果。"""
    if is_disconnected is not None and await is_disconnected():
        raise asyncio.CancelledError


def _prompt(template: str, content: str) -> str:
    """将既定指令与所选资料组织为模型上下文，具体预算在调用边界限制。"""
    return f"{template}\n\n{content}"


def _json_object(content: str) -> dict[str, Any]:
    """清理 JSON 代码围栏并要求对象形状，解析失败由上层映射为安全流错误。"""
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
        raise ValueError("JSON object not found")
    value = json.loads(stripped[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("JSON value is not an object")
    return value


def _parse_test_menu(content: str) -> dict[str, bool]:
    """按 TestMenu 校验模型输出，非法菜单不能开放下游工作区。"""
    try:
        return TestMenu.model_validate(_json_object(content)).model_dump()
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        raise TestPlanStreamError(
            "menu_parse_error",
            "模型返回的测试菜单格式无效，请重试",
            status=502,
            retryable=True,
        ) from exc


def _parse_cached_test_menu(content: str | bool | None) -> dict[str, bool] | None:
    """缓存菜单按同一结构规则解析；损坏缓存视为不可复用，不阻止重新生成。"""
    if not content or not isinstance(content, str):
        return None
    try:
        return _parse_test_menu(content)
    except TestPlanStreamError:
        return None


def _parse_project_analysis_digest(content: str) -> ProjectAnalysisDigest:
    """校验摘要和推荐菜单的联合结构，使计划生成基于同一份证据化摘要。"""
    try:
        return ProjectAnalysisDigest.model_validate(_json_object(content))
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        raise TestPlanStreamError(
            "digest_parse_error",
            "模型返回的项目分析结构无效，请重试",
            status=502,
            retryable=True,
        ) from exc


def _parse_cached_bundle(content: str) -> _ProjectAnalysisBundle | None:
    """严格解析已保存三件套，字段或 JSON 无效时按缓存缺失处理。"""
    try:
        return _ProjectAnalysisBundle.model_validate(_json_object(content))
    except (json.JSONDecodeError, ValueError, TypeError):
        return None


def _digest_schema() -> str:
    """返回供模型使用的结构化输出 schema，字段描述属于提示词内容而非可随意改写注释。"""
    return json.dumps(
        ProjectAnalysisDigest.model_json_schema(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _digest_prompt(template: str, content: str) -> str:
    """把资料与摘要 schema 组织为联合分析请求，保持既有模板内容不变。"""
    return (
        f"{template}\n\nJSON Schema:\n{_digest_schema()}"
        f"\n\n待分析内容:\n{content}"
    )


def _digest_instruction(template: str) -> str:
    """提供摘要与菜单的结构化输出约束，不自行发起模型调用。"""
    return f"{template}\n\nJSON Schema:\n{_digest_schema()}\n\n待分析内容:"


async def get_project_analysis_status(pid: str) -> dict[str, Any]:
    """并发读取摘要、计划和菜单，仅三者均有效才返回整体 ready。"""
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


def _project_analysis_budget(
    stage: BudgetStage, llm_name: str
) -> WorkflowBudgetProfile:
    """按模型与阶段选择初始分析预算，保留特定模型的上下文/输出限制。"""
    budget = profile_for(PROJECT_ANALYSIS_OPERATION, stage)
    # DeepSeek's medium alias maps to high. Retain that actual middle tier,
    # increasing only its final completion allowance (thinking plus answer).
    if stage == "final" and get_model_spec(llm_name).provider == "deepseek":
        return replace(
            budget, final_output_tokens=16_384,
            reasoning_mode="balanced", reasoning_budget=None,
        )
    if stage == "final" and is_kimi_k3(llm_name):
        return replace(budget, reasoning_mode="balanced", reasoning_budget=None)
    if is_kimi_k3(llm_name):
        return replace(budget, reasoning_mode="low", reasoning_budget=None)
    return budget


def _project_analysis_options(
    budget: WorkflowBudgetProfile, llm_name: str
) -> dict[str, Any]:
    """生成该阶段 provider 请求参数，特定模型选项由统一模型注册表约束。"""
    options = provider_options(budget, llm_name)
    if budget.stage == "final" and (
        is_kimi_k3(llm_name) or get_model_spec(llm_name).provider == "deepseek"
    ):
        # Scope the high-effort override here, leaving generic K3 calls at low.
        options.update(reasoning_mode=budget.reasoning_mode, reasoning_effort="high")
    return options


def _project_analysis_generation_policy(llm_name: str) -> str:
    """取得用于缓存身份的模型生成策略，策略变化不能静默复用旧分析。"""
    if get_model_spec(llm_name).provider == "deepseek":
        return "bounded-thinking-ds16k-v3"
    return PROJECT_ANALYSIS_GENERATION_POLICY


def _analysis_cache_matches(artifact: Any, metadata: dict[str, str]) -> bool:
    """DeepSeek 与 Kimi K3 缓存额外核对实际模型和生成策略，防止策略变化后误复用。"""
    label = metadata["label"]
    if get_model_spec(label).provider != "deepseek" and not is_kimi_k3(label):
        return True
    recorded = getattr(artifact, "metadata", None)
    return isinstance(recorded, dict) and (
        recorded.get("model") == metadata["model"]
        and recorded.get("generation_policy") == _project_analysis_generation_policy(label)
    )


async def _stream_model_call(
    llm_name: str,
    prompt_text: str,
    max_tokens: int,
    *,
    stage: str,
    stage_label: str,
    output_event: str | None,
    instruction_text: str | None = None,
    context_text: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """在阶段预算内流式调用并累计用量，空响应或不完整结果不能进入保存阶段。"""
    budget_stage = stage_for_model_call(stage)
    budget = _project_analysis_budget(budget_stage, llm_name)
    effective_max_tokens = min(max_tokens, budget.output_token_limit)
    request_options = _project_analysis_options(budget, llm_name)
    request_options["max_tokens"] = min(
        int(request_options["max_tokens"]),
        effective_max_tokens,
    )
    context_budget = effective_context_budget(
        PROJECT_ANALYSIS_OPERATION,
        budget_stage,
        llm_name,
    )
    if context_text is None:
        instruction = ""
        source_context = prompt_text
    else:
        instruction = instruction_text if instruction_text is not None else prompt_text
        source_context = context_text
    bounded = bound_prompt_context(instruction, source_context, context_budget)
    if bounded.reduced:
        yield _progress(
            f"{stage}_context_reduce",
            "输入上下文已按 Token 预算压缩",
            0,
            current=bounded.selected_context_tokens,
            total=bounded.input_context_tokens,
        )
    content_parts: list[str] = []
    call_usage: TokenUsage | None = None

    async for model_event in stream_chat_completion(
        llm_name,
        bounded.prompt,
        effective_max_tokens,
        minimum_timeout_seconds=TEST_PLAN_MINIMUM_TIMEOUT_SECONDS,
        request_options=request_options,
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
    yield _event("model_call_completed", content=content, usage=call_usage)


async def _collect_model_call(
    llm_name: str,
    prompt_text: str,
    max_tokens: int,
    *,
    stage: str,
    stage_label: str,
    output_event: str | None,
    instruction_text: str | None = None,
    context_text: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """消费内部模型流并收集结果与用量，供需要组合多个阶段的流程使用。"""
    async for item in _stream_model_call(
        llm_name,
        prompt_text,
        max_tokens,
        stage=stage,
        stage_label=stage_label,
        output_event=output_event,
        instruction_text=instruction_text,
        context_text=context_text,
    ):
        yield item


async def _run_collected_call(
    llm_name: str,
    prompt_text: str,
    max_tokens: int,
    *,
    stage: str,
    stage_label: str,
    output_event: str | None = None,
    instruction_text: str | None = None,
    context_text: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """运行已封装的阶段调用并保留结果收集约定，不额外创建用户任务。"""
    async for item in _collect_model_call(
        llm_name,
        prompt_text,
        max_tokens,
        stage=stage,
        stage_label=stage_label,
        output_event=output_event,
        instruction_text=instruction_text,
        context_text=context_text,
    ):
        yield item


async def stream_test_plan(
    pid: str,
    llm_name: str,
    regenerate: bool,
    *,
    is_disconnected: DisconnectCheck | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """先检查可恢复缓存，再从同一摘要形成菜单和计划；完整校验且连接仍有效时原子保存联合结果。"""
    project, project_type = await asyncio.gather(
        asyncio.to_thread(testProjectDao.find_project, pid),
        asyncio.to_thread(testProjectDao.get_project_type, pid),
    )
    if not project or not project_type:
        raise TestPlanStreamError(
            "project_not_ready",
            "项目不存在或尚未完成文档类型分析",
            status=404,
            retryable=False,
        )
    try:
        source_revision = await asyncio.to_thread(
            compute_project_source_revision, pid
        )
    except (OSError, RuntimeError, TypeError, ValueError):
        raise TestPlanStreamError(
            "source_revision_error",
            "项目文档版本读取失败",
            status=500,
            retryable=True,
        ) from None

    metadata = get_stream_model_metadata(llm_name)
    public_budget = _project_analysis_budget("final", llm_name).public_metadata()
    yield _event(
        "meta",
        request_id=uuid4().hex,
        operation=PROJECT_ANALYSIS_OPERATION,
        budget_profile=PROJECT_ANALYSIS_BUDGET_PROFILE,
        budget=public_budget,
        source_revision=source_revision,
        **metadata,
    )
    yield _progress("validate", "正在校验项目、模型和文档版本", 8)
    await _ensure_connected(is_disconnected)

    cached_bundle = None
    if not regenerate:
        cached_artifact = await asyncio.to_thread(
            get_fresh_artifact,
            pid,
            PROJECT_ANALYSIS_ARTIFACT_KEY,
            source_revision,
            PROJECT_ANALYSIS_INPUT_HASH,
            PROJECT_ANALYSIS_PROMPT_VERSION,
            llm_name,
        )
        if cached_artifact is not None and _analysis_cache_matches(cached_artifact, metadata):
            cached_bundle = _parse_cached_bundle(cached_artifact.content)
    if cached_bundle is not None:
        cached_menu = cached_bundle.menu
        if not cached_menu.unit_test or not cached_menu.integration_test:
            try:
                cached_documents = await asyncio.to_thread(
                    documentTools.generate_all_testdocs_docs, pid
                )
                cached_menu = reconcile_test_menu(
                    cached_menu,
                    collect_project_test_evidence(cached_documents),
                )
            except LLMError:
                raise
            except Exception:
                cached_menu = cached_bundle.menu
        yield _event("summary_delta", text=cached_bundle.summary)
        yield _event("answer_delta", text=cached_bundle.plan)
        yield _event("menu", menu=cached_menu.model_dump())
        yield _event(
            "usage",
            input_tokens=None,
            reasoning_tokens=None,
            output_tokens=None,
            total_tokens=None,
            model_call_count=0,
        )
        yield _progress("completed", "已读取当前文档版本的保存结果", 100)
        yield _event(
            "completed",
            saved=True,
            from_cache=True,
            ready=True,
            artifact_key=PROJECT_ANALYSIS_ARTIFACT_KEY,
            model_call_count=0,
            input_tokens=None,
            reasoning_tokens=None,
            output_tokens=None,
            total_tokens=None,
        )
        return

    usages: list[TokenUsage] = []
    source_documents = await asyncio.to_thread(
        documentTools.generate_all_testdocs_docs, pid
    )
    if not source_documents:
        raise TestPlanStreamError(
            "documents_missing",
            "没有找到可用于业务分析的项目文档",
            status=422,
            retryable=False,
        )
    all_documents_text = documentTools.docs_to_string(source_documents)
    source_tokens = await asyncio.to_thread(
        documentTools.num_tokens_from_string, all_documents_text
    )
    long_text_strategy = strategy_for(PROJECT_ANALYSIS_OPERATION, source_tokens)
    digest_instruction = ""
    digest_context = ""
    digest_stage = "digest_generate"
    digest_label = "正在生成业务摘要和测试菜单"
    project_evidence = collect_project_test_evidence(source_documents)

    if long_text_strategy is LongTextStrategy.MAP_REDUCE:
        yield _progress("digest_documents", "业务文档加载完成", 15)
        documents = await asyncio.to_thread(
            testdoc_text_splitter_for_menu.split_documents,
            source_documents,
        )
        documents = split_documents_within_budget(
            documents,
            effective_context_budget(
                PROJECT_ANALYSIS_OPERATION, "map", llm_name
            ),
        )
        if not documents:
            raise TestPlanStreamError(
                "documents_empty",
                "业务文档拆分后没有可分析的内容",
                status=422,
                retryable=False,
            )
        evidence_parts: list[str] = []
        total = len(documents)
        for index, document in enumerate(documents, start=1):
            await _ensure_connected(is_disconnected)
            content = ""
            usage: TokenUsage | None = None
            async for item in _run_collected_call(
                llm_name,
                "",
                INTERMEDIATE_MAX_TOKENS,
                stage=f"digest_map_{index}",
                stage_label=f"正在提取业务文档证据 {index}/{total}",
                instruction_text=prompt.PROJECT_ANALYSIS_DIGEST_MAP_PROMPT_STR,
                context_text=document.page_content,
            ):
                if item["event"] == "model_call_completed":
                    content = item["data"]["content"]
                    usage = item["data"]["usage"]
                else:
                    yield item
            evidence_parts.append(content)
            usages.append(usage or TokenUsage())
            yield _progress(
                "digest_map",
                f"已提取业务文档证据 {index}/{total}",
                15 + round(25 * index / total),
                current=index,
                total=total,
            )
        digest_instruction = _digest_instruction(
            prompt.PROJECT_ANALYSIS_DIGEST_REDUCE_PROMPT_STR
        )
        digest_context = "\n\n".join(evidence_parts)
        digest_stage = "digest_reduce"
        digest_label = "正在合并业务摘要并生成测试菜单"
    else:
        yield _progress("digest_documents", "业务文档加载完成", 20)
        digest_instruction = _digest_instruction(
            prompt.PROJECT_ANALYSIS_DIGEST_STUFF_PROMPT_STR
        )
        digest_context = all_documents_text

    await _ensure_connected(is_disconnected)
    yield _progress(digest_stage, digest_label, 45)
    digest_content = ""
    digest_usage: TokenUsage | None = None
    async for item in _run_collected_call(
        llm_name,
        "",
        INTERMEDIATE_MAX_TOKENS,
        stage=digest_stage,
        stage_label=digest_label,
        instruction_text=digest_instruction,
        context_text=digest_context,
    ):
        if item["event"] == "model_call_completed":
            digest_content = item["data"]["content"]
            digest_usage = item["data"]["usage"]
        else:
            yield item
    usages.append(digest_usage or TokenUsage())
    try:
        digest = _parse_project_analysis_digest(digest_content)
    except TestPlanStreamError:
        await _ensure_connected(is_disconnected)
        yield _progress("digest_repair", "正在修复项目分析结构", 52)
        repair_content = ""
        repair_usage: TokenUsage | None = None
        repair_prompt = prompt.PROJECT_ANALYSIS_DIGEST_REPAIR_PROMPT_STR.format(
            schema=_digest_schema(),
            invalid_output=digest_content[:PROJECT_ANALYSIS_REPAIR_MAX_CHARS],
        )
        async for item in _run_collected_call(
            llm_name,
            repair_prompt,
            INTERMEDIATE_MAX_TOKENS,
            stage="digest_repair",
            stage_label="正在修复项目分析结构",
        ):
            if item["event"] == "model_call_completed":
                repair_content = item["data"]["content"]
                repair_usage = item["data"]["usage"]
            else:
                yield item
        usages.append(repair_usage or TokenUsage())
        digest = _parse_project_analysis_digest(repair_content)

    if project_evidence is not None:
        digest = ProjectAnalysisDigest(
            summary=digest.summary,
            menu=reconcile_test_menu(digest.menu, project_evidence),
        )

    yield _event("summary_delta", text=digest.summary)
    yield _progress("digest_generated", "业务摘要和测试菜单已生成", 60)

    enabled_tests = ", ".join(
        name for name, enabled in digest.menu.model_dump().items() if enabled
    )
    final_prompt = prompt.TEST_PLAN_FROM_DIGEST_TEMPLATE.format(
        summary=digest.summary,
        enabled_tests=enabled_tests,
    )
    await _ensure_connected(is_disconnected)
    yield _progress("plan_generate", "正在根据规范化摘要生成测试计划", 70)
    final_content = ""
    final_usage: TokenUsage | None = None
    async for item in _run_collected_call(
        llm_name,
        final_prompt,
        FINAL_MAX_TOKENS,
        stage="plan_generate",
        stage_label="正在生成完整测试计划",
        output_event="answer_delta",
    ):
        if item["event"] == "model_call_completed":
            final_content = item["data"]["content"]
            final_usage = item["data"]["usage"]
        else:
            yield item
    usages.append(final_usage or TokenUsage())
    yield _event("menu", menu=digest.menu.model_dump())
    yield _progress("menu_generated", "测试计划和测试菜单已生成", 88)

    aggregate_usage = combine_token_usage(usages)
    usage_counters = {
        **aggregate_usage.as_dict(),
        "model_call_count": len(usages),
    }
    yield _event("usage", **usage_counters)
    yield _progress("generated", "业务分析结果已准备完成", 92)
    await _ensure_connected(is_disconnected)

    menu_json = json.dumps(
        digest.menu.model_dump(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    artifact_content = json.dumps(
        {
            "summary": digest.summary,
            "menu": digest.menu.model_dump(),
            "plan": final_content,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    metadata_json = json.dumps(
        {
            "budget_profile": PROJECT_ANALYSIS_BUDGET_PROFILE,
            "model": metadata["model"],
            "generation_policy": _project_analysis_generation_policy(llm_name),
            "call_count": len(usages),
            "operation": PROJECT_ANALYSIS_OPERATION,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    yield _progress("persist", "正在原子保存分析结果", 96)
    await _ensure_connected(is_disconnected)
    saved = await asyncio.to_thread(
        testProjectDao.save_project_analysis_artifact_bundle,
        pid,
        digest.summary,
        final_content,
        menu_json,
        artifact_key=PROJECT_ANALYSIS_ARTIFACT_KEY,
        input_hash=PROJECT_ANALYSIS_INPUT_HASH,
        source_revision=source_revision,
        prompt_version=PROJECT_ANALYSIS_PROMPT_VERSION,
        model_label=llm_name,
        artifact_content=artifact_content,
        metadata_json=metadata_json,
    )
    if not saved:
        raise TestPlanStreamError(
            "persistence_error",
            "分析结果已生成，但保存数据库失败",
            status=500,
            retryable=True,
        )

    yield _progress("completed", "业务分析、测试计划和测试菜单已生成并保存", 100)
    yield _event(
        "completed",
        saved=True,
        from_cache=False,
        ready=True,
        artifact_key=PROJECT_ANALYSIS_ARTIFACT_KEY,
        **usage_counters,
    )
