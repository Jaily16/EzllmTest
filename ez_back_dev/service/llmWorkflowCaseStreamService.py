from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from dao import testProjectDao
from prompt import promptStr as prompt
from prompt.templates import (
    ACCEPTANCE_TEST_GENERATE_TEST_CASE_TEMPLATE,
    APIS_TEST_GENERATE_TEST_CASE_TEMPLATE,
    API_TEST_GENERATE_TEST_CASE_TEMPLATE,
    API_TEST_INFO_MAP_REDUCE_TEMPLATE,
    API_TEST_INFO_TEMPLATE,
    DATABASE_TEST_GENERATE_TEST_CASE_TEMPLATE,
    FUNCTIONAL_TEST_GENERATE_ALL_TEST_CASE_TEMPLATE,
    FUNCTIONAL_TEST_GENERATE_ONE_TEST_CASE_TEMPLATE,
    INTEGRATION_TEST_GENERATE_TEST_CASE_TEMPLATE,
    INTEGRATION_TEST_STRATEGY_KNOWLEDGE_TEMPLATE,
    NONFUNCTIONAL_TEST_GENERATE_TEST_CASE_TEMPLATE,
    NONFUNCTIONAL_TEST_KNOWLEDGE_TEMPLATE,
    UI_TEST_GENERATE_TEST_CASE_TEMPLATE,
    UNIT_TEST_GENERATE_TEST_CASE_TEMPLATE_2,
    USE_CASE_INFO_MAP_REDUCE_TEMPLATE,
    USE_CASE_INFO_MAP_TEMPLATE,
    USE_CASE_INFO_TEMPLATE,
)
from service.llmWorkflowStreamCore import (
    WorkflowContext,
    WorkflowStreamError,
    ensure_connected,
    event,
    progress,
    rag_prompt,
    require_integer,
    require_string,
    stream_map_reduce,
    stream_model_call,
)
from tools import documentTools
from tools.InfoType import InfoType
from vectorstore.retrievers import (
    api_retriever,
    knowledge_retriever,
    require_retriever,
)


@dataclass(frozen=True)
class KnowledgeSpec:
    key: str
    cache_type: int | None
    question: str
    label: str


def _output_template(output_type: int) -> str:
    if output_type == 0:
        return prompt.UNIT_TEST_CASE_TXT_TEMPLATE
    if output_type == 1:
        return prompt.UNIT_TEST_CASE_MD_TEMPLATE
    if output_type == 2:
        return prompt.UNIT_TEST_CASE_XML_TEMPLATE
    if output_type == 3:
        return prompt.UNIT_TEST_CASE_CSV_TEMPLATE
    raise WorkflowStreamError(
        "invalid_payload",
        "测试用例输出格式无效",
        status=422,
        retryable=False,
    )


async def _model_value(
    context: WorkflowContext,
    prompt_text: str,
    *,
    stage: str,
    label: str,
    output_event: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    value = ""
    async for item in stream_model_call(
        context,
        prompt_text,
        stage=stage,
        label=label,
        output_event=output_event,
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
    start_percent: int,
    end_percent: int,
    output_event: str | None = None,
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
        output_event=output_event or "_hidden_delta",
    ):
        if item["event"] == "_hidden_delta":
            continue
        yield item


async def _knowledge_bundle(
    context: WorkflowContext,
    specs: list[KnowledgeSpec],
    *,
    start_percent: int = 25,
    end_percent: int = 62,
) -> AsyncIterator[dict[str, Any]]:
    values: dict[str, str] = {}
    missing: list[KnowledgeSpec] = []
    yield progress("knowledge_cache", "正在检查已保存的测试知识", start_percent)
    for spec in specs:
        history = None
        if spec.cache_type is not None and not context.regenerate:
            history = await asyncio.to_thread(
                testProjectDao.get_project_info,
                context.pid,
                spec.cache_type,
            )
        if history:
            values[spec.key] = str(history)
        else:
            missing.append(spec)

    retriever = None
    if missing:
        await ensure_connected(context)
        yield progress(
            "knowledge_documents",
            "正在读取并构建测试知识库向量索引",
            start_percent + 5,
        )
        documents = await asyncio.to_thread(
            documentTools.generate_knowledge_docs, context.pid
        )
        if not documents:
            raise WorkflowStreamError(
                "knowledge_missing",
                "项目测试知识库为空，无法继续生成测试用例",
                status=422,
                retryable=False,
            )
        retriever = await asyncio.to_thread(knowledge_retriever, documents)

    total = len(missing)
    for index, spec in enumerate(missing, start=1):
        await ensure_connected(context)
        yield progress(
            "knowledge_retrieval",
            f"正在检索{spec.label} ({index}/{total})",
            start_percent + 8 + round(12 * index / max(total, 1)),
            current=index,
            total=total,
        )
        context_documents = await asyncio.to_thread(
            retriever.invoke, spec.question
        )
        context_text = documentTools.docs_to_meaningful_strings(
            context_documents
        )
        knowledge = ""
        async for item in _model_value(
            context,
            rag_prompt(spec.question, context_text),
            stage=f"knowledge_{spec.key}",
            label=f"正在整理{spec.label}",
        ):
            if item["event"] == "_workflow_value":
                knowledge = item["data"]["value"]
            else:
                yield item
        values[spec.key] = knowledge
        if spec.cache_type is not None:
            context.pending_info[spec.cache_type] = knowledge
    yield progress("knowledge_ready", "测试知识准备完成", end_percent)
    yield event("_workflow_value", value=values)


async def _final_case_result(
    context: WorkflowContext,
    prompt_text: str,
    result: dict[str, Any],
    *,
    label: str,
) -> AsyncIterator[dict[str, Any]]:
    await ensure_connected(context)
    yield progress("case_generate", label, 72)
    test_cases = ""
    async for item in _model_value(
        context,
        prompt_text,
        stage="case_generate",
        label=label,
        output_event="answer_delta",
    ):
        if item["event"] == "_workflow_value":
            test_cases = item["data"]["value"]
        else:
            yield item
    result["test_cases"] = test_cases
    yield progress("case_generated", "测试用例生成完成", 92)
    yield event("_workflow_result", result=result)


async def stream_unit_case(
    context: WorkflowContext,
) -> AsyncIterator[dict[str, Any]]:
    method_type = require_integer(context.payload, "method_type")
    unit = require_string(context.payload, "unit")
    unit_info = require_string(context.payload, "unit_info")
    static_method = require_string(context.payload, "static_method")
    output_type = require_integer(context.payload, "output_type")
    method_cache = (
        InfoType.PROJECT_STATIC_BLACKBOX_KNOWLEDGE.value
        if method_type == 1
        else InfoType.PROJECT_STATIC_WHITEBOX_KNOWLEDGE.value
    )
    method_question = (
        prompt.UNIT_TEST_KNOWLEDGE_TEMPLATE_BLACKBOX_STR
        if method_type == 1
        else prompt.UNIT_TEST_KNOWLEDGE_TEMPLATE_WHITEBOX_STR
    )
    knowledge: dict[str, str] = {}
    async for item in _knowledge_bundle(
        context,
        [
            KnowledgeSpec(
                "unit_test_knowledge",
                InfoType.PROJECT_UNIT_TEST_KNOWLEDGE.value,
                prompt.UNIT_TEST_KNOWLEDGE_STR,
                "单元测试知识",
            ),
            KnowledgeSpec(
                "unit_method_knowledge",
                method_cache,
                method_question,
                f"{static_method}知识",
            ),
        ],
    ):
        if item["event"] == "_workflow_value":
            knowledge = item["data"]["value"]
        else:
            yield item
    case_prompt = UNIT_TEST_GENERATE_TEST_CASE_TEMPLATE_2.format(
        unit_test_knowledge=knowledge["unit_test_knowledge"],
        static_method=static_method,
        unit_test_method_knowledge=knowledge["unit_method_knowledge"],
        unit=unit,
        case_template=_output_template(output_type),
        unit_info=unit_info,
    )
    async for item in _final_case_result(
        context,
        case_prompt,
        knowledge,
        label=f"正在为 {unit} 生成单元测试用例",
    ):
        yield item


async def stream_integration_case(
    context: WorkflowContext,
) -> AsyncIterator[dict[str, Any]]:
    strategy_type = require_integer(context.payload, "strategy_type")
    strategy = require_string(context.payload, "strategy")
    integration_object = require_string(context.payload, "integration_object")
    integration_info = require_string(context.payload, "integration_object_info")
    output_type = require_integer(context.payload, "output_type")
    strategy_caches = [
        InfoType.PROJECT_INTEGRATION_BIGBANG_KNOWLEDGE.value,
        InfoType.PROJECT_INTEGRATION_TOP_DOWN_KNOWLEDGE.value,
        InfoType.PROJECT_INTEGRATION_BOTTOM_UP_KNOWLEDGE.value,
        InfoType.PROJECT_INTEGRATION_SANDWICH_KNOWLEDGE.value,
    ]
    if strategy_type < 0 or strategy_type >= len(strategy_caches):
        raise WorkflowStreamError(
            "invalid_payload", "集成测试策略无效", status=422, retryable=False
        )
    knowledge: dict[str, str] = {}
    async for item in _knowledge_bundle(
        context,
        [
            KnowledgeSpec(
                "integration_test_knowledge",
                InfoType.PROJECT_INTEGRATION_TEST_KNOWLEDGE.value,
                prompt.INTEGRATION_TEST_KNOWLEDGE_STR,
                "集成测试知识",
            ),
            KnowledgeSpec(
                "static_blackbox_knowledge",
                InfoType.PROJECT_STATIC_BLACKBOX_KNOWLEDGE.value,
                prompt.UNIT_TEST_KNOWLEDGE_TEMPLATE_BLACKBOX_STR,
                "静态黑盒测试知识",
            ),
            KnowledgeSpec(
                "integration_strategy_knowledge",
                strategy_caches[strategy_type],
                INTEGRATION_TEST_STRATEGY_KNOWLEDGE_TEMPLATE.format(
                    strategy=strategy
                ),
                f"{strategy}策略知识",
            ),
        ],
    ):
        if item["event"] == "_workflow_value":
            knowledge = item["data"]["value"]
        else:
            yield item
    case_prompt = INTEGRATION_TEST_GENERATE_TEST_CASE_TEMPLATE.format(
        integration_test_knowledge=knowledge["integration_test_knowledge"],
        static_method="静态黑盒测试",
        strategy=strategy,
        strategy_knowledge=knowledge["integration_strategy_knowledge"],
        blackbox_knowledge=knowledge["static_blackbox_knowledge"],
        integration_unit=integration_object,
        case_template=_output_template(output_type),
        integration_unit_info=integration_info,
    )
    async for item in _final_case_result(
        context,
        case_prompt,
        knowledge,
        label=f"正在为 {integration_object} 生成集成测试用例",
    ):
        yield item


async def _named_api_info(
    context: WorkflowContext, api_name: str
) -> AsyncIterator[dict[str, Any]]:
    yield progress("documents", "正在读取并检索 API 设计文档", 14)
    source_documents = await asyncio.to_thread(
        documentTools.generate_design_testdocs_docs, context.pid
    )
    documents = await asyncio.to_thread(
        lambda: api_retriever(source_documents).invoke(api_name)
    )
    document_text = documentTools.docs_to_meaningful_strings(documents)
    if not document_text:
        raise WorkflowStreamError(
            "retrieval_empty",
            f"没有检索到 API {api_name} 的文档信息",
            status=422,
            retryable=False,
        )
    tokens = await asyncio.to_thread(
        documentTools.num_tokens_from_string, document_text
    )
    result = ""
    if tokens > 14500:
        async for item in _map_reduce_value(
            context,
            documents,
            map_prompt=API_TEST_INFO_MAP_REDUCE_TEMPLATE.format(
                api_name=api_name
            ),
            reduce_prompt=API_TEST_INFO_MAP_REDUCE_TEMPLATE.format(
                api_name=api_name
            ),
            stage_prefix="api_detail",
            label=f"分析 API {api_name}",
            start_percent=15,
            end_percent=35,
        ):
            if item["event"] == "_workflow_value":
                result = item["data"]["value"]
            else:
                yield item
    else:
        async for item in _model_value(
            context,
            API_TEST_INFO_TEMPLATE.format(api_name=api_name, docs=document_text),
            stage="api_detail",
            label=f"正在分析 API {api_name}",
        ):
            if item["event"] == "_workflow_value":
                result = item["data"]["value"]
            else:
                yield item
    yield event("_workflow_value", value=result)


async def stream_api_case(
    context: WorkflowContext,
) -> AsyncIterator[dict[str, Any]]:
    test_type = require_integer(context.payload, "test_type")
    output_type = require_integer(context.payload, "output_type")
    info = require_string(context.payload, "info")
    api_name = require_string(
        context.payload, "api_name", allow_empty=test_type == 0
    )
    if test_type == 1:
        async for item in _named_api_info(context, api_name):
            if item["event"] == "_workflow_value":
                info = item["data"]["value"]
            else:
                yield item
    knowledge: dict[str, str] = {}
    async for item in _knowledge_bundle(
        context,
        [
            KnowledgeSpec(
                "api_test_knowledge",
                InfoType.PROJECT_API_TEST_KNOWLEDGE.value,
                prompt.API_TEST_KNOWLEDGE_STR,
                "API 接口测试知识",
            )
        ],
        start_percent=36 if test_type == 1 else 20,
    ):
        if item["event"] == "_workflow_value":
            knowledge = item["data"]["value"]
        else:
            yield item
    template = (
        API_TEST_GENERATE_TEST_CASE_TEMPLATE
        if test_type == 1
        else APIS_TEST_GENERATE_TEST_CASE_TEMPLATE
    )
    values: dict[str, Any] = {
        "api_test_knowledge": knowledge["api_test_knowledge"],
        "content": info,
        "case_template": _output_template(output_type),
    }
    if test_type == 1:
        values["api_name"] = api_name
    async for item in _final_case_result(
        context,
        template.format(**values),
        knowledge,
        label="正在生成 API 接口测试用例",
    ):
        yield item


async def _named_use_case_info(
    context: WorkflowContext, use_case_name: str
) -> AsyncIterator[dict[str, Any]]:
    yield progress("documents", "正在读取并检索需求用例文档", 14)
    source_documents = await asyncio.to_thread(
        documentTools.generate_require_testdocs_docs, context.pid
    )
    documents = await asyncio.to_thread(
        lambda: require_retriever(source_documents).invoke(use_case_name)
    )
    document_text = documentTools.docs_to_meaningful_strings(documents)
    if not document_text:
        raise WorkflowStreamError(
            "retrieval_empty",
            f"没有检索到用例 {use_case_name} 的文档信息",
            status=422,
            retryable=False,
        )
    tokens = await asyncio.to_thread(
        documentTools.num_tokens_from_string, document_text
    )
    result = ""
    if tokens > 14500:
        async for item in _map_reduce_value(
            context,
            documents,
            map_prompt=USE_CASE_INFO_MAP_TEMPLATE.format(
                use_case_name=use_case_name
            ),
            reduce_prompt=USE_CASE_INFO_MAP_REDUCE_TEMPLATE.format(
                use_case_name=use_case_name
            ),
            stage_prefix="use_case_detail",
            label=f"分析用例 {use_case_name}",
            start_percent=15,
            end_percent=35,
        ):
            if item["event"] == "_workflow_value":
                result = item["data"]["value"]
            else:
                yield item
    else:
        async for item in _model_value(
            context,
            USE_CASE_INFO_TEMPLATE.format(
                use_case_name=use_case_name, docs=document_text
            ),
            stage="use_case_detail",
            label=f"正在分析用例 {use_case_name}",
        ):
            if item["event"] == "_workflow_value":
                result = item["data"]["value"]
            else:
                yield item
    yield event("_workflow_value", value=result)


async def stream_functional_case(
    context: WorkflowContext,
) -> AsyncIterator[dict[str, Any]]:
    test_type = require_integer(context.payload, "test_type")
    output_type = require_integer(context.payload, "output_type")
    info = require_string(context.payload, "info")
    use_case_name = require_string(
        context.payload, "use_case_name", allow_empty=test_type == 0
    )
    if test_type == 1:
        async for item in _named_use_case_info(context, use_case_name):
            if item["event"] == "_workflow_value":
                info = item["data"]["value"]
            else:
                yield item
    knowledge: dict[str, str] = {}
    async for item in _knowledge_bundle(
        context,
        [
            KnowledgeSpec(
                "functional_test_knowledge",
                InfoType.PROJECT_FUNCTION_TEST_KNOWLEDGE.value,
                prompt.FUNCTIONAL_TEST_KNOWLEDGE_STR,
                "系统功能性测试知识",
            )
        ],
        start_percent=36 if test_type == 1 else 20,
    ):
        if item["event"] == "_workflow_value":
            knowledge = item["data"]["value"]
        else:
            yield item
    template = (
        FUNCTIONAL_TEST_GENERATE_ONE_TEST_CASE_TEMPLATE
        if test_type == 1
        else FUNCTIONAL_TEST_GENERATE_ALL_TEST_CASE_TEMPLATE
    )
    values: dict[str, Any] = {
        "functional_test_knowledge": knowledge[
            "functional_test_knowledge"
        ],
        "content": info,
        "case_template": _output_template(output_type),
    }
    if test_type == 1:
        values["use_case"] = use_case_name
    async for item in _final_case_result(
        context,
        template.format(**values),
        knowledge,
        label="正在生成系统功能性测试用例",
    ):
        yield item


async def _simple_case(
    context: WorkflowContext,
    *,
    knowledge_spec: KnowledgeSpec,
    info_key: str,
    template: Any,
    template_values: dict[str, Any],
    label: str,
) -> AsyncIterator[dict[str, Any]]:
    info = require_string(context.payload, "info")
    knowledge: dict[str, str] = {}
    async for item in _knowledge_bundle(context, [knowledge_spec], start_percent=20):
        if item["event"] == "_workflow_value":
            knowledge = item["data"]["value"]
        else:
            yield item
    values = {**template_values, info_key: knowledge[knowledge_spec.key], "content": info}
    async for item in _final_case_result(
        context,
        template.format(**values),
        knowledge,
        label=label,
    ):
        yield item


async def stream_nonfunctional_case(
    context: WorkflowContext,
) -> AsyncIterator[dict[str, Any]]:
    info = require_string(context.payload, "info")
    method_name = require_string(context.payload, "method_name")
    knowledge: dict[str, str] = {}
    async for item in _knowledge_bundle(
        context,
        [
            KnowledgeSpec(
                "nonfunctional_test_knowledge",
                None,
                NONFUNCTIONAL_TEST_KNOWLEDGE_TEMPLATE.format(
                    test_name=method_name
                ),
                f"{method_name}知识",
            )
        ],
        start_percent=20,
    ):
        if item["event"] == "_workflow_value":
            knowledge = item["data"]["value"]
        else:
            yield item
    async for item in _final_case_result(
        context,
        NONFUNCTIONAL_TEST_GENERATE_TEST_CASE_TEMPLATE.format(
            knowledge=knowledge["nonfunctional_test_knowledge"],
            content=info,
            test_name=method_name,
        ),
        knowledge,
        label=f"正在生成{method_name}用例",
    ):
        yield item


async def stream_case_operation(
    context: WorkflowContext,
) -> AsyncIterator[dict[str, Any]]:
    if context.operation == "unit_case":
        async for item in stream_unit_case(context):
            yield item
    elif context.operation == "integration_case":
        async for item in stream_integration_case(context):
            yield item
    elif context.operation == "api_case":
        async for item in stream_api_case(context):
            yield item
    elif context.operation == "functional_case":
        async for item in stream_functional_case(context):
            yield item
    elif context.operation == "ui_case":
        async for item in _simple_case(
            context,
            knowledge_spec=KnowledgeSpec(
                "ui_test_knowledge",
                InfoType.PROJECT_UI_TEST_KNOWLEDGE.value,
                prompt.UI_TEST_KNOWLEDGE_STR,
                "前端 UI 测试知识",
            ),
            info_key="ui_test_knowledge",
            template=UI_TEST_GENERATE_TEST_CASE_TEMPLATE,
            template_values={},
            label="正在生成前端 UI 测试用例",
        ):
            yield item
    elif context.operation == "db_case":
        async for item in _simple_case(
            context,
            knowledge_spec=KnowledgeSpec(
                "db_test_knowledge",
                InfoType.PROJECT_DB_TEST_KNOWLEDGE.value,
                prompt.DATABASE_TEST_KNOWLEDGE_STR,
                "数据库测试知识",
            ),
            info_key="db_test_knowledge",
            template=DATABASE_TEST_GENERATE_TEST_CASE_TEMPLATE,
            template_values={},
            label="正在生成数据库测试用例",
        ):
            yield item
    elif context.operation == "acceptance_case":
        async for item in _simple_case(
            context,
            knowledge_spec=KnowledgeSpec(
                "acceptance_test_knowledge",
                InfoType.PROJECT_ACCEPTANCE_TEST_KNOWLEDGE.value,
                prompt.ACCEPTANCE_TEST_KNOWLEDGE_STR,
                "验收测试知识",
            ),
            info_key="acceptance_test_knowledge",
            template=ACCEPTANCE_TEST_GENERATE_TEST_CASE_TEMPLATE,
            template_values={},
            label="正在生成验收测试用例",
        ):
            yield item
    elif context.operation == "nonfunctional_case":
        async for item in stream_nonfunctional_case(context):
            yield item
    else:
        raise WorkflowStreamError(
            "unsupported_operation",
            f"不支持的流式操作：{context.operation}",
            status=400,
            retryable=False,
        )
