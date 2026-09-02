from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from infrastructure.persistence import project_repository as testProjectDao
from infrastructure.llm.stream import INTERMEDIATE_MAX_TOKENS
from model.ChainJsonModel import (
    ApiList,
    IntegrationTestMenu,
    NonfunctionalTestMethodList,
    QualifiedUnitTestMenu,
    UnitTestMethod,
    UseCaseList,
)
from prompt import promptStr as prompt
from prompt.templates import (
    INTEGRATION_TEST_INFO_MAP_TEMPLATE,
    INTEGRATION_TEST_INFO_REDUCE_TEMPLATE,
    INTEGRATION_TEST_INFO_STUFF_TEMPLATE,
    UNIT_TEST_TYPE_JSON_TEMPLATE,
    UNIT_TEST_UNIT_INFO_MAP_TEMPLATE,
    UNIT_TEST_UNIT_INFO_REDUCE_TEMPLATE,
    UNIT_TEST_UNIT_INFO_STUFF_TEMPLATE,
)
from service.workflow.stream_core import (
    WorkflowContext,
    WorkflowStreamError,
    ensure_connected,
    event,
    parse_structured_result,
    progress,
    prompt_with_content,
    require_integer,
    require_source_revision,
    require_string,
    stream_map_reduce,
    stream_model_call,
    structured_prompt,
)
from service.workflow.long_text import LongTextStrategy, strategy_for
from service.workflow.unit_reference import encode_unit_menu, parse_unit_reference
from service.project import documents as documentTools
from tools.InfoType import InfoType
from service.retrieval.factory import get_project_retriever
from service.retrieval.splitters import (
    testdoc_text_splitter_for_acceptance,
    testdoc_text_splitter_for_db,
    testdoc_text_splitter_for_integration,
    testdoc_text_splitter_for_ui,
    testdoc_text_splitter_for_unit,
    testdoc_text_splitter_for_use_case,
)


@dataclass(frozen=True)
class AnalysisSpec:
    cache_type: int
    source_name: str
    string_loader: Callable[[str], Any]
    document_loader: Callable[[str], Any]
    splitter: Any
    stuff_prompt: str
    map_prompt: str
    reduce_prompt: str
    result_text_key: str | None = None
    structure_model: type[BaseModel] | None = None
    structure_prompt: str | None = None
    result_list_key: str | None = None


ANALYSIS_SPECS: dict[str, AnalysisSpec] = {
    "unit_menu": AnalysisSpec(
        InfoType.PROJECT_UNITS_SUMMARY.value,
        "业务开发设计文档",
        documentTools.generate_design_testdocs_str,
        documentTools.generate_design_testdocs_docs,
        testdoc_text_splitter_for_unit,
        prompt.UNIT_TEST_FIND_UNIT_INFO_STUFF_PROMPT_STR,
        prompt.UNIT_TEST_FIND_UNIT_INFO_MAP_REDUCE_PART_PROMPT_STR,
        prompt.UNIT_TEST_FIND_UNIT_INFO_MAP_REDUCE_TOTAL_PROMPT_STR,
        "text_info",
        QualifiedUnitTestMenu,
        prompt.UNIT_TEST_FIND_UNIT_INFO_JSON_STR,
        "list_info",
    ),
    "api_info": AnalysisSpec(
        InfoType.PROJECT_APIS_SUMMARY.value,
        "业务开发设计文档",
        documentTools.generate_design_testdocs_str,
        documentTools.generate_design_testdocs_docs,
        testdoc_text_splitter_for_unit,
        prompt.API_TEST_SUMMARY_PROMPT_STR,
        prompt.API_TEST_SUMMARY_MAP_PROMPT_STR,
        prompt.API_TEST_SUMMARY_REDUCE_PROMPT_STR,
        "apis_info",
        ApiList,
        prompt.API_TEST_JSON_PROMPT_STR,
        "list",
    ),
    "ui_info": AnalysisSpec(
        InfoType.PROJECT_UI_SUMMARY.value,
        "业务开发设计文档",
        documentTools.generate_design_testdocs_str,
        documentTools.generate_design_testdocs_docs,
        testdoc_text_splitter_for_ui,
        prompt.UI_TEST_SUMMARY_PROMPT_STR,
        prompt.UI_TEST_SUMMARY_MAP_PROMPT_STR,
        prompt.UI_TEST_SUMMARY_REDUCE_PROMPT_STR,
    ),
    "db_info": AnalysisSpec(
        InfoType.PROJECT_DB_SUMMARY.value,
        "业务开发设计文档",
        documentTools.generate_design_testdocs_str,
        documentTools.generate_design_testdocs_docs,
        testdoc_text_splitter_for_db,
        prompt.DATABASE_TEST_SUMMARY_PROMPT_STR,
        prompt.DATABASE_TEST_SUMMARY_MAP_PROMPT_STR,
        prompt.DATABASE_TEST_SUMMARY_REDUCE_PROMPT_STR,
    ),
    "functional_info": AnalysisSpec(
        InfoType.PROJECT_FUNCTIONAL_SUMMARY.value,
        "业务需求文档",
        documentTools.generate_require_testdocs_str,
        documentTools.generate_require_testdocs_docs,
        testdoc_text_splitter_for_use_case,
        prompt.FUNCTIONAL_TEST_SUMMARY_STUFF_PROMPT_STR,
        prompt.FUNCTIONAL_TEST_SUMMARY_MAP_PROMPT_STR,
        prompt.FUNCTIONAL_TEST_SUMMARY_REDUCE_PROMPT_STR,
        "text_info",
        UseCaseList,
        prompt.FUNCTIONAL_TEST_JSON_PROMPT_STR,
        "list_info",
    ),
    "acceptance_info": AnalysisSpec(
        InfoType.PROJECT_ACCEPTANCE_SUMMARY.value,
        "业务需求文档",
        documentTools.generate_require_testdocs_str,
        documentTools.generate_require_testdocs_docs,
        testdoc_text_splitter_for_acceptance,
        prompt.ACCEPTANCE_TEST_SUMMARY_PROMPT_STR,
        prompt.ACCEPTANCE_TEST_SUMMARY_MAP_PROMPT_STR,
        prompt.ACCEPTANCE_TEST_SUMMARY_REDUCE_PROMPT_STR,
    ),
}


async def _model_value(
    context: WorkflowContext,
    prompt_text: str,
    *,
    stage: str,
    label: str,
    output_event: str | None = None,
    max_tokens: int | None = None,
) -> AsyncIterator[dict[str, Any]]:
    value = ""
    kwargs: dict[str, Any] = {}
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    async for item in stream_model_call(
        context,
        prompt_text,
        stage=stage,
        label=label,
        output_event=output_event,
        **kwargs,
    ):
        if item["event"] == "_model_completed":
            value = item["data"]["content"]
        else:
            yield item
    yield event("_workflow_value", value=value)


async def _map_reduce_value(
    context: WorkflowContext,
    documents: list[Any],
    *,
    map_prompt: str,
    reduce_prompt: str,
    stage_prefix: str,
    label: str,
    start_percent: int = 30,
    end_percent: int = 70,
) -> AsyncIterator[dict[str, Any]]:
    async for item in stream_map_reduce(
        context,
        documents,
        map_prompt=map_prompt,
        reduce_prompt=reduce_prompt,
        stage_prefix=stage_prefix,
        label=label,
        start_percent=start_percent,
        end_percent=end_percent,
    ):
        yield item


async def stream_configured_analysis(
    context: WorkflowContext,
    spec: AnalysisSpec,
    *,
    include_structure: bool = True,
) -> AsyncIterator[dict[str, Any]]:
    history, project_type = await asyncio.gather(
        asyncio.to_thread(
            testProjectDao.get_project_info,
            context.pid,
            spec.cache_type,
        ),
        asyncio.to_thread(testProjectDao.get_project_type, context.pid),
    )
    if not project_type:
        raise WorkflowStreamError(
            "project_not_ready",
            "项目尚未完成文档类型分析",
            status=422,
            retryable=False,
        )
    yield progress("cache", "正在检查已保存的分析结果", 12)
    generated = context.regenerate or not history
    text_result = str(history or "")

    if generated:
        yield progress("documents", f"正在读取{spec.source_name}", 20)
        source_documents = await asyncio.to_thread(
            spec.document_loader, context.pid
        )
        if not source_documents:
            raise WorkflowStreamError(
                "documents_missing",
                f"没有找到可分析的{spec.source_name}",
                status=422,
                retryable=False,
            )
        source_text = documentTools.docs_to_string(source_documents)
        source_tokens = await asyncio.to_thread(
            documentTools.num_tokens_from_string, source_text
        )
        selected_strategy = strategy_for(context.operation, source_tokens)
        if selected_strategy is LongTextStrategy.MAP_REDUCE:
            documents = await asyncio.to_thread(
                spec.splitter.split_documents, source_documents
            )
            yield progress(
                "split",
                f"{spec.source_name}拆分完成",
                28,
                current=0,
                total=len(documents),
            )
            async for item in _map_reduce_value(
                context,
                documents,
                map_prompt=spec.map_prompt,
                reduce_prompt=spec.reduce_prompt,
                stage_prefix=context.operation,
                label=f"分析{spec.source_name}",
            ):
                if item["event"] == "_workflow_value":
                    text_result = item["data"]["value"]
                else:
                    yield item
        else:
            yield progress("prepare", "文档与提示词准备完成", 30)
            async for item in _model_value(
                context,
                prompt_with_content(spec.stuff_prompt, source_text),
                stage=f"{context.operation}_generate",
                label=f"正在分析{spec.source_name}",
                output_event="answer_delta",
            ):
                if item["event"] == "_workflow_value":
                    text_result = item["data"]["value"]
                else:
                    yield item
        context.pending_info[spec.cache_type] = text_result
    else:
        yield event("answer_delta", text=text_result)
        yield progress("cache", "已读取保存的分析结果", 70)

    structured_value: dict[str, Any] | None = None
    if include_structure and spec.structure_model and spec.structure_prompt:
        await ensure_connected(context)
        yield progress("structured", "正在提取可选择的测试对象", 78)
        structured_content = ""
        async for item in _model_value(
            context,
            structured_prompt(
                spec.structure_prompt + text_result,
                spec.structure_model,
            ),
            stage=f"{context.operation}_structured",
            label="正在整理结构化选项",
        ):
            if item["event"] == "_workflow_value":
                structured_content = item["data"]["value"]
            else:
                yield item
        parsed_structure = parse_structured_result(
            structured_content, spec.structure_model
        )
        structured_value = (
            encode_unit_menu(parsed_structure).model_dump()
            if context.operation == "unit_menu"
            else parsed_structure.model_dump()
        )
        yield progress("structured", "测试对象提取完成", 88)

    if spec.result_text_key:
        result: Any = {spec.result_text_key: text_result}
        if spec.result_list_key:
            result[spec.result_list_key] = structured_value
    else:
        result = text_result
    yield event("_workflow_result", result=result)


async def stream_nonfunctional_info(
    context: WorkflowContext,
) -> AsyncIterator[dict[str, Any]]:
    history = await asyncio.to_thread(
        testProjectDao.get_project_info,
        context.pid,
        InfoType.PROJECT_NONFUNCTIONAL_SUMMARY.value,
    )
    text_result = str(history or "")
    if context.regenerate or not text_result:
        yield progress("documents", "正在读取业务需求文档", 18)
        source_documents = await asyncio.to_thread(
            documentTools.generate_require_testdocs_docs, context.pid
        )
        if not source_documents:
            raise WorkflowStreamError(
                "documents_missing",
                "没有找到可分析的业务需求文档",
                status=422,
                retryable=False,
            )
        query = (
            "非功能性需求：性能、可扩展性、可靠性、可用性、安全性、可维护性、"
            "兼容性、响应时间、容量、数据完整性、灾难恢复、合规性和监控"
        )
        yield progress("retrieval", "正在向量检索非功能性需求", 28)
        retriever = await get_project_retriever(
            context.pid,
            "requirements",
            require_source_revision(context),
            source_documents,
        )
        documents = await asyncio.to_thread(retriever.invoke, query)
        document_text = documentTools.docs_to_meaningful_strings(documents)
        if not document_text:
            raise WorkflowStreamError(
                "retrieval_empty",
                "没有检索到非功能性需求相关内容",
                status=422,
                retryable=False,
            )
        async for item in _model_value(
            context,
            prompt_with_content(
                prompt.NONFUNCTIONAL_TEST_SUMMARY_PROMPT_STR,
                document_text,
            ),
            stage="nonfunctional_info_generate",
            label="正在分析非功能性需求",
            output_event="answer_delta",
        ):
            if item["event"] == "_workflow_value":
                text_result = item["data"]["value"]
            else:
                yield item
        context.pending_info[
            InfoType.PROJECT_NONFUNCTIONAL_SUMMARY.value
        ] = text_result
    else:
        yield event("answer_delta", text=text_result)
        yield progress("cache", "已读取保存的非功能性需求分析", 70)

    yield progress("structured", "正在提取非功能性测试类型", 78)
    structured_content = ""
    async for item in _model_value(
        context,
        structured_prompt(
            prompt.NONFUNCTIONAL_TEST_JSON_PROMPT_STR + text_result,
            NonfunctionalTestMethodList,
        ),
        stage="nonfunctional_info_structured",
        label="正在整理非功能性测试类型",
        max_tokens=INTERMEDIATE_MAX_TOKENS,
    ):
        if item["event"] == "_workflow_value":
            structured_content = item["data"]["value"]
        else:
            yield item
    methods = parse_structured_result(
        structured_content, NonfunctionalTestMethodList
    ).model_dump()
    yield event(
        "_workflow_result",
        result={"nonfunctional_info": text_result, "list": methods},
    )


async def stream_unit_info(
    context: WorkflowContext,
) -> AsyncIterator[dict[str, Any]]:
    unit = require_string(context.payload, "unit")
    unit_type_value = context.payload.get("unit_type", "")
    if not isinstance(unit_type_value, str):
        raise WorkflowStreamError(
            "invalid_payload",
            "请求字段 unit_type 必须是字符串",
            status=422,
            retryable=False,
        )
    target = parse_unit_reference(unit, unit_type_value)
    yield progress("documents", "正在读取业务开发设计文档", 18)
    source_documents = await asyncio.to_thread(
        documentTools.generate_design_testdocs_docs, context.pid
    )
    if not source_documents:
        raise WorkflowStreamError(
            "documents_missing",
            "没有找到业务开发设计文档",
            status=422,
            retryable=False,
        )
    yield progress("retrieval", f"正在检索与 {target.display_name} 相关的文档", 28)
    retriever = await get_project_retriever(
        context.pid,
        "design",
        require_source_revision(context),
        source_documents,
    )
    documents = await asyncio.to_thread(retriever.invoke, target.retrieval_query)
    document_text = documentTools.docs_to_string(documents)
    if not document_text:
        raise WorkflowStreamError(
            "retrieval_empty",
            f"没有检索到与 {target.prompt_label} 相关的文档",
            status=422,
            retryable=False,
        )
    unit_info = ""
    async for item in _model_value(
        context,
        UNIT_TEST_UNIT_INFO_STUFF_TEMPLATE.format(
            unit=target.prompt_label, docs=document_text
        ),
        stage="unit_info_generate",
        label=f"正在分析单元 {target.display_name}",
        output_event="answer_delta",
    ):
        if item["event"] == "_workflow_value":
            unit_info = item["data"]["value"]
        else:
            yield item
    yield progress("structured", "正在判断适用的单元测试方法", 80)
    method_content = ""
    async for item in _model_value(
        context,
        structured_prompt(
            UNIT_TEST_TYPE_JSON_TEMPLATE.format(
                unit=target.prompt_label, content=unit_info
            ),
            UnitTestMethod,
        ),
        stage="unit_info_method",
        label="正在判断黑盒/白盒测试适用性",
        max_tokens=INTERMEDIATE_MAX_TOKENS,
    ):
        if item["event"] == "_workflow_value":
            method_content = item["data"]["value"]
        else:
            yield item
    methods = parse_structured_result(method_content, UnitTestMethod).model_dump()
    yield event(
        "_workflow_result",
        result={"unit_info": unit_info, "test_type": methods},
    )


async def _integration_document_prompt(
    context: WorkflowContext,
    integration_type: int,
    unit_name: str,
) -> AsyncIterator[dict[str, Any]]:
    map_prompt = ""
    reduce_prompt = ""
    stuff_prompt = ""
    documents: list[Any] = []
    document_text = ""
    use_map = False
    project_type = await asyncio.to_thread(testProjectDao.get_project_type, context.pid)
    if not project_type:
        raise WorkflowStreamError(
            "project_not_ready", "项目文档类型尚未分析", status=422, retryable=False
        )
    yield progress("documents", "正在读取业务开发设计文档", 18)
    if integration_type in (0, 1):
        source_documents = await asyncio.to_thread(
            documentTools.generate_design_testdocs_docs, context.pid
        )
        if source_documents:
            document_text = documentTools.docs_to_string(source_documents)
        source_tokens = await asyncio.to_thread(
            documentTools.num_tokens_from_string, document_text
        )
        if strategy_for(
            "integration_info", source_tokens, source_mode="exhaustive"
        ) is LongTextStrategy.MAP_REDUCE:
            documents = await asyncio.to_thread(
                testdoc_text_splitter_for_integration.split_documents,
                source_documents,
            )
            use_map = True
        if integration_type == 0:
            map_prompt = prompt.INTEGRATION_TEST_SYSTEM_INFO_MAP_PROMPT_STR
            reduce_prompt = prompt.INTEGRATION_TEST_SYSTEM_INFO_REDUCE_PROMPT_STR
            stuff_prompt = prompt.INTEGRATION_TEST_SYSTEM_INFO_STUFF_PROMPT_STR
        else:
            map_prompt = prompt.INTEGRATION_TEST_SUBSYSTEM_INFO_MAP_PROMPT_STR
            reduce_prompt = prompt.INTEGRATION_TEST_SUBSYSTEM_INFO_REDUCE_PROMPT_STR
            stuff_prompt = prompt.INTEGRATION_TEST_SUBSYSTEM_INFO_STUFF_PROMPT_STR
    else:
        source_documents = await asyncio.to_thread(
            documentTools.generate_design_testdocs_docs, context.pid
        )
        yield progress("retrieval", f"正在检索与 {unit_name} 相关的集成信息", 28)
        retriever = await get_project_retriever(
            context.pid,
            "design",
            require_source_revision(context),
            source_documents,
        )
        documents = await asyncio.to_thread(retriever.invoke, unit_name)
        document_text = documentTools.docs_to_string(documents)
        if integration_type == 2:
            unit_type = "类(class)或模块"
        elif integration_type == 3:
            unit_type = "类(class)或函数"
        else:
            unit_type = "函数"
        stuff_prompt = INTEGRATION_TEST_INFO_STUFF_TEMPLATE.format(
            integration_unit=unit_name,
            unit_type=unit_type,
            docs=document_text,
        )
    if not documents and not document_text:
        raise WorkflowStreamError(
            "documents_missing",
            "没有找到可用于集成测试分析的文档",
            status=422,
            retryable=False,
        )
    result = ""
    if use_map:
        async for item in _map_reduce_value(
            context,
            documents,
            map_prompt=map_prompt,
            reduce_prompt=reduce_prompt,
            stage_prefix="integration_info",
            label="分析集成测试对象",
        ):
            if item["event"] == "_workflow_value":
                result = item["data"]["value"]
            else:
                yield item
    else:
        final_prompt = (
            stuff_prompt
            if integration_type not in (0, 1)
            else prompt_with_content(stuff_prompt, document_text)
        )
        async for item in _model_value(
            context,
            final_prompt,
            stage="integration_info_generate",
            label="正在分析集成测试对象",
            output_event="answer_delta",
        ):
            if item["event"] == "_workflow_value":
                result = item["data"]["value"]
            else:
                yield item
    yield event("_workflow_result", result=result)


async def stream_integration_menu(
    context: WorkflowContext,
) -> AsyncIterator[dict[str, Any]]:
    units_info = context.payload.get("units_info")
    if not isinstance(units_info, str) or not units_info.strip():
        units_info = await asyncio.to_thread(
            testProjectDao.get_project_info,
            context.pid,
            InfoType.PROJECT_UNITS_SUMMARY.value,
        )
    if not units_info:
        unit_result: dict[str, Any] | None = None
        async for item in stream_configured_analysis(
            context, ANALYSIS_SPECS["unit_menu"], include_structure=False
        ):
            if item["event"] == "_workflow_result":
                unit_result = item["data"]["result"]
            else:
                yield item
        if not isinstance(unit_result, dict):
            raise WorkflowStreamError("unit_analysis_error", "单元信息分析失败")
        units_info = unit_result["text_info"]
    yield progress("structured", "正在生成集成测试菜单", 80)
    menu_content = ""
    async for item in _model_value(
        context,
        structured_prompt(
            prompt.INTEGRATION_TEST_MENU_JSON_STR + str(units_info),
            IntegrationTestMenu,
        ),
        stage="integration_menu_structured",
        label="正在判断可用的集成测试类型",
        max_tokens=INTERMEDIATE_MAX_TOKENS,
    ):
        if item["event"] == "_workflow_value":
            menu_content = item["data"]["value"]
        else:
            yield item
    result = parse_structured_result(
        menu_content, IntegrationTestMenu
    ).model_dump()
    yield event("_workflow_result", result=result)


async def stream_analysis_operation(
    context: WorkflowContext,
) -> AsyncIterator[dict[str, Any]]:
    if context.operation in ANALYSIS_SPECS:
        async for item in stream_configured_analysis(
            context, ANALYSIS_SPECS[context.operation]
        ):
            yield item
    elif context.operation == "nonfunctional_info":
        async for item in stream_nonfunctional_info(context):
            yield item
    elif context.operation == "unit_info":
        async for item in stream_unit_info(context):
            yield item
    elif context.operation == "integration_menu":
        async for item in stream_integration_menu(context):
            yield item
    elif context.operation == "integration_info":
        integration_type = require_integer(context.payload, "integration_type")
        unit_name = require_string(
            context.payload, "name", allow_empty=integration_type in (0, 1)
        )
        async for item in _integration_document_prompt(
            context, integration_type, unit_name
        ):
            yield item
    else:
        raise WorkflowStreamError(
            "unsupported_operation",
            f"不支持的流式操作：{context.operation}",
            status=400,
            retryable=False,
        )
