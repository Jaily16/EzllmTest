import asyncio
from dataclasses import dataclass

import pytest
from langchain_core.documents import Document

from llm.streaming import ModelStreamEvent
from service import llmWorkflowCaseStreamService as cases
from service import llmWorkflowStreamCore as core


@dataclass(frozen=True)
class CaseFixture:
    operation: str
    payload: dict
    knowledge_key: str


CASE_FIXTURES = [
    CaseFixture(
        "unit_case",
        {
            "method_type": 1,
            "unit": "Cart",
            "unit_info": "cart info",
            "static_method": "静态黑盒测试",
            "output_type": 0,
        },
        "unit_test_knowledge",
    ),
    CaseFixture(
        "integration_case",
        {
            "strategy_type": 0,
            "strategy": "大爆炸集成(Big Bang Integration)",
            "integration_object": "系统",
            "integration_object_info": "integration info",
            "output_type": 0,
        },
        "integration_test_knowledge",
    ),
    CaseFixture(
        "api_case",
        {
            "info": "api info",
            "test_type": 0,
            "output_type": 0,
            "api_name": "",
        },
        "api_test_knowledge",
    ),
    CaseFixture("ui_case", {"info": "ui info"}, "ui_test_knowledge"),
    CaseFixture("db_case", {"info": "db info"}, "db_test_knowledge"),
    CaseFixture(
        "functional_case",
        {
            "info": "use case info",
            "test_type": 0,
            "output_type": 0,
            "use_case_name": "",
        },
        "functional_test_knowledge",
    ),
    CaseFixture(
        "nonfunctional_case",
        {"info": "nfr info", "method_name": "性能测试"},
        "nonfunctional_test_knowledge",
    ),
    CaseFixture(
        "acceptance_case",
        {"info": "acceptance info"},
        "acceptance_test_knowledge",
    ),
]


def configure(monkeypatch):
    monkeypatch.setattr(
        cases.testProjectDao,
        "get_project_info",
        lambda _pid, info_type: f"cached knowledge {info_type}",
    )
    knowledge_documents = [Document(page_content="testing knowledge")]
    monkeypatch.setattr(
        cases.documentTools,
        "generate_knowledge_docs",
        lambda _pid: knowledge_documents,
    )
    monkeypatch.setattr(
        cases,
        "knowledge_retriever",
        lambda _docs: type(
            "Retriever",
            (),
            {"invoke": lambda self, _query: knowledge_documents},
        )(),
    )

    async def fake_model(_name, prompt_text, _max_tokens, **_kwargs):
        yield ModelStreamEvent("reasoning", text="thinking")
        content = (
            "generated knowledge"
            if "知识库上下文" in prompt_text
            else "generated cases"
        )
        yield ModelStreamEvent("content", text=content)

    monkeypatch.setattr(core, "stream_chat_completion", fake_model)


async def collect(context):
    return [item async for item in cases.stream_case_operation(context)]


@pytest.mark.parametrize("fixture", CASE_FIXTURES, ids=lambda item: item.operation)
def test_each_case_operation_streams_final_answer_and_legacy_result(
    monkeypatch, fixture
):
    configure(monkeypatch)
    if fixture.operation == "nonfunctional_case":
        monkeypatch.setattr(
            cases.testProjectDao, "get_project_info", lambda *_args: False
        )
    context = core.WorkflowContext(
        "p", "DeepSeek", fixture.operation, fixture.payload
    )

    events = asyncio.run(collect(context))

    assert "reasoning_delta" in [item["event"] for item in events]
    assert "generated cases" == "".join(
        item["data"]["text"]
        for item in events
        if item["event"] == "answer_delta"
    )
    result = next(
        item["data"]["result"]
        for item in events
        if item["event"] == "_workflow_result"
    )
    assert result[fixture.knowledge_key]
    assert result["test_cases"] == "generated cases"
    assert any(
        item["event"] == "progress"
        and item["data"]["stage"] == "case_generate"
        for item in events
    )


def test_new_knowledge_is_queued_not_written_by_case_operation(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setattr(
        cases.testProjectDao, "get_project_info", lambda *_args: False
    )
    context = core.WorkflowContext(
        "p", "DeepSeek", "ui_case", {"info": "ui info"}
    )

    events = asyncio.run(collect(context))

    assert any(item["event"] == "_workflow_result" for item in events)
    assert context.pending_info == {14: "generated knowledge"}
