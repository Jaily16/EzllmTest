import asyncio
import json
from dataclasses import replace
from types import SimpleNamespace

import pytest
from langchain_core.documents import Document

from llm.streaming import ModelStreamEvent
from service import llmWorkflowAnalysisStreamService as analysis
from service import llmWorkflowStreamCore as core


UNIT_MENU = {
    "subsystem_menu": {
        "subsystem_test": True,
        "subsystem_list": [
            {
                "display_name": "系统子系统",
                "qualified_name": "系统/系统子系统",
                "source_hint": "架构章节",
            }
        ],
    },
    "module_menu": {
        "module_test": True,
        "module_list": [
            {
                "display_name": "订单模块",
                "qualified_name": "系统/系统子系统/订单模块",
                "source_hint": "模块章节",
            }
        ],
    },
    "class_menu": {
        "class_test": True,
        "class_list": [
            {
                "display_name": "OrderService类",
                "qualified_name": "order.OrderService",
                "source_hint": "订单模块/OrderService",
            }
        ],
    },
    "function_menu": {
        "function_test": True,
        "function_list": [
            {
                "display_name": "create方法",
                "qualified_name": "order.OrderService.create(request)",
                "source_hint": "订单模块/OrderService",
            },
            {
                "display_name": "create方法",
                "qualified_name": "invoice.InvoiceService.create(request)",
                "source_hint": "发票模块/InvoiceService",
            },
        ],
    },
}
INTEGRATION_MENU = {
    "subsystem_integration_test": True,
    "subsystem_integration_menu": {
        "subsystem_test": True,
        "subsystem_list": ["system"],
    },
    "module_integration_menu": {
        "module_test": True,
        "module_list": ["module"],
    },
    "class_integration_menu": {
        "class_test": True,
        "class_list": ["Class"],
    },
}


def structured_response(prompt_text):
    if '"subsystem_integration_test"' in prompt_text:
        return INTEGRATION_MENU
    if '"subsystem_menu"' in prompt_text:
        return UNIT_MENU
    if '"black_box"' in prompt_text:
        return {"black_box": True, "white_box": True}
    if '"api_list"' in prompt_text:
        return {"api_list": ["/v1/items"]}
    if '"use_case_list"' in prompt_text:
        return {"use_case_list": ["创建订单"]}
    if '"method_list"' in prompt_text:
        return {"method_list": ["性能测试"]}
    return None


def configure(monkeypatch):
    monkeypatch.setattr(
        analysis.testProjectDao,
        "get_project_info",
        lambda *_args: False,
    )
    monkeypatch.setattr(
        analysis.testProjectDao,
        "get_project_type",
        lambda _pid: SimpleNamespace(overflow=0),
    )

    async def fake_model(_name, prompt_text, _max_tokens, **_kwargs):
        value = structured_response(prompt_text)
        yield ModelStreamEvent("reasoning", text="thinking")
        yield ModelStreamEvent(
            "content",
            text=json.dumps(value, ensure_ascii=False) if value else "generated text",
        )

    monkeypatch.setattr(core, "stream_chat_completion", fake_model)

    async def fake_project_retriever(
        _pid, _corpus, _source_revision, source_documents
    ):
        return SimpleNamespace(invoke=lambda _query: source_documents)

    monkeypatch.setattr(
        analysis, "get_project_retriever", fake_project_retriever
    )


async def collect(context):
    return [
        item
        async for item in analysis.stream_analysis_operation(context)
    ]


@pytest.mark.parametrize(
    ("operation", "expected_key"),
    [
        ("unit_menu", "text_info"),
        ("api_info", "apis_info"),
        ("ui_info", None),
        ("db_info", None),
        ("functional_info", "text_info"),
        ("acceptance_info", None),
    ],
)
def test_configured_analysis_operations_stream_answer_and_result(
    monkeypatch, operation, expected_key
):
    configure(monkeypatch)
    original = analysis.ANALYSIS_SPECS[operation]
    monkeypatch.setitem(
        analysis.ANALYSIS_SPECS,
        operation,
        replace(
            original,
            string_loader=lambda _pid: "document content",
            document_loader=lambda _pid: [Document(page_content="document content")],
        ),
    )
    context = core.WorkflowContext("p", "DeepSeek", operation, {})

    events = asyncio.run(collect(context))

    names = [item["event"] for item in events]
    assert "reasoning_delta" in names
    assert "answer_delta" in names
    result = next(
        item["data"]["result"]
        for item in events
        if item["event"] == "_workflow_result"
    )
    if expected_key:
        assert result[expected_key] == "generated text"
    else:
        assert result == "generated text"
    assert context.pending_info[original.cache_type] == "generated text"


def test_unit_menu_encodes_qualified_references_as_compatible_strings(monkeypatch):
    configure(monkeypatch)
    original = analysis.ANALYSIS_SPECS["unit_menu"]
    monkeypatch.setitem(
        analysis.ANALYSIS_SPECS,
        "unit_menu",
        replace(
            original,
            document_loader=lambda _pid: [Document(page_content="document content")],
        ),
    )

    events = asyncio.run(
        collect(core.WorkflowContext("p", "DeepSeek", "unit_menu", {}))
    )
    result = next(
        item["data"]["result"]
        for item in events
        if item["event"] == "_workflow_result"
    )
    values = result["list_info"]["function_menu"]["function_list"]

    assert len(values) == 2
    assert all(isinstance(value, str) for value in values)
    assert values[0] != values[1]
    assert "order.OrderService.create(request)" in values[0]


def test_exhaustive_analysis_routes_by_actual_tokens_not_legacy_overflow(
    monkeypatch,
):
    configure(monkeypatch)
    monkeypatch.setattr(
        analysis.testProjectDao,
        "get_project_type",
        lambda _pid: SimpleNamespace(overflow=4),
    )
    original = analysis.ANALYSIS_SPECS["unit_menu"]
    monkeypatch.setitem(
        analysis.ANALYSIS_SPECS,
        "unit_menu",
        replace(
            original,
            document_loader=lambda _pid: [Document(page_content="small design")],
        ),
    )
    monkeypatch.setattr(
        analysis.documentTools,
        "num_tokens_from_string",
        lambda _text: 100,
    )
    context = core.WorkflowContext("p", "DeepSeek", "unit_menu", {})

    events = asyncio.run(collect(context))

    assert not any(
        item["event"] == "progress" and item["data"]["stage"] == "split"
        for item in events
    )


def test_focused_retrieval_does_not_map_reduce_an_already_selected_context(
    monkeypatch,
):
    configure(monkeypatch)
    documents = [Document(page_content="class Cart")]
    monkeypatch.setattr(
        analysis.documentTools,
        "generate_design_testdocs_docs",
        lambda _pid: documents,
    )
    monkeypatch.setattr(
        analysis.documentTools,
        "num_tokens_from_string",
        lambda _text: 100_000,
    )
    context = core.WorkflowContext(
        "p",
        "DeepSeek",
        "unit_info",
        {"unit": "Cart"},
        source_revision="rev-1",
    )

    events = asyncio.run(collect(context))

    stages = [
        item["data"]["stage"]
        for item in events
        if item["event"] == "progress"
    ]
    assert not any("unit_info_map" in stage for stage in stages)


def test_nonfunctional_analysis_streams_retrieval_and_method_list(monkeypatch):
    configure(monkeypatch)
    documents = [Document(page_content="性能要求")]
    retrieval_calls = []

    async def fake_project_retriever(
        pid, corpus, source_revision, source_documents
    ):
        retrieval_calls.append(
            (pid, corpus, source_revision, source_documents)
        )
        return SimpleNamespace(invoke=lambda _query: documents)

    monkeypatch.setattr(
        analysis, "get_project_retriever", fake_project_retriever
    )
    monkeypatch.setattr(
        analysis.documentTools,
        "generate_require_testdocs_docs",
        lambda _pid: documents,
    )
    monkeypatch.setattr(
        analysis.documentTools, "num_tokens_from_string", lambda _text: 10
    )
    context = core.WorkflowContext(
        "p", "DeepSeek", "nonfunctional_info", {}, source_revision="rev-1"
    )

    events = asyncio.run(collect(context))

    result = next(
        item["data"]["result"]
        for item in events
        if item["event"] == "_workflow_result"
    )
    assert result["nonfunctional_info"] == "generated text"
    assert result["list"]["method_list"] == ["性能测试"]
    assert any(
        item["event"] == "progress"
        and item["data"]["stage"] == "retrieval"
        for item in events
    )
    assert retrieval_calls == [
        ("p", "requirements", "rev-1", documents)
    ]


def test_unit_info_streams_retrieval_text_and_test_methods(monkeypatch):
    configure(monkeypatch)
    documents = [Document(page_content="class Cart")]
    retrieval_calls = []
    retrieval_queries = []

    async def fake_project_retriever(
        pid, corpus, source_revision, source_documents
    ):
        retrieval_calls.append(
            (pid, corpus, source_revision, source_documents)
        )
        return SimpleNamespace(
            invoke=lambda query: retrieval_queries.append(query) or documents
        )

    monkeypatch.setattr(
        analysis.documentTools,
        "generate_design_testdocs_docs",
        lambda _pid: documents,
    )
    monkeypatch.setattr(
        analysis,
        "get_project_retriever",
        fake_project_retriever,
        raising=False,
    )
    monkeypatch.setattr(
        analysis.documentTools, "num_tokens_from_string", lambda _text: 10
    )
    context = core.WorkflowContext(
        "p",
        "DeepSeek",
        "unit_info",
        {
            "unit": "create方法 ｜ order.OrderService.create(request) ｜ 订单模块/OrderService",
            "unit_type": "函数单元测试",
        },
    )
    context.source_revision = "rev-1"

    events = asyncio.run(collect(context))

    result = next(
        item["data"]["result"]
        for item in events
        if item["event"] == "_workflow_result"
    )
    assert result == {
        "unit_info": "generated text",
        "test_type": {"black_box": True, "white_box": True},
    }
    assert retrieval_calls == [("p", "design", "rev-1", documents)]
    assert retrieval_queries == [
        "函数单元测试 create方法 order.OrderService.create(request) 订单模块/OrderService"
    ]


def test_integration_menu_and_info_have_streamed_results(monkeypatch):
    configure(monkeypatch)
    menu_context = core.WorkflowContext(
        "p",
        "DeepSeek",
        "integration_menu",
        {"units_info": "units"},
    )
    menu_events = asyncio.run(collect(menu_context))
    menu_result = next(
        item["data"]["result"]
        for item in menu_events
        if item["event"] == "_workflow_result"
    )
    assert menu_result == INTEGRATION_MENU

    monkeypatch.setattr(
        analysis.documentTools,
        "generate_design_testdocs_docs",
        lambda _pid: [Document(page_content="design docs")],
    )
    info_context = core.WorkflowContext(
        "p",
        "DeepSeek",
        "integration_info",
        {"integration_type": 0, "name": ""},
    )
    info_events = asyncio.run(collect(info_context))
    assert next(
        item["data"]["result"]
        for item in info_events
        if item["event"] == "_workflow_result"
    ) == "generated text"


def test_named_integration_info_reuses_revision_scoped_design_index(
    monkeypatch,
):
    configure(monkeypatch)
    documents = [Document(page_content="module checkout")]
    retrieval_calls = []
    monkeypatch.setattr(
        analysis.documentTools,
        "generate_design_testdocs_docs",
        lambda _pid: documents,
    )

    async def fake_project_retriever(
        pid, corpus, source_revision, source_documents
    ):
        retrieval_calls.append(
            (pid, corpus, source_revision, source_documents)
        )
        return SimpleNamespace(invoke=lambda _query: documents)

    monkeypatch.setattr(
        analysis, "get_project_retriever", fake_project_retriever
    )
    context = core.WorkflowContext(
        "p",
        "DeepSeek",
        "integration_info",
        {"integration_type": 2, "name": "checkout"},
        source_revision="rev-1",
    )

    events = asyncio.run(collect(context))

    assert any(item["event"] == "_workflow_result" for item in events)
    assert retrieval_calls == [("p", "design", "rev-1", documents)]
