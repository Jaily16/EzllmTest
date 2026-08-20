import asyncio
import json
from types import SimpleNamespace

import pytest

from llm.streaming import ModelStreamEvent, TokenUsage
from service import llmTestPlanStreamService as service
from tools.InfoType import InfoType


MENU = {
    "test_plan": True,
    "unit_test": True,
    "integration_test": True,
    "api_test": True,
    "ui_test": True,
    "db_test": True,
    "functional_test": True,
    "nonfunctional_test": True,
    "acceptance_test": True,
}


def configure_project(monkeypatch, *, overflow=0, histories=None):
    histories = histories or {}
    monkeypatch.setattr(service.testProjectDao, "find_project", lambda _pid: object())
    monkeypatch.setattr(
        service.testProjectDao,
        "get_project_type",
        lambda _pid: SimpleNamespace(overflow=overflow),
    )
    monkeypatch.setattr(
        service.testProjectDao,
        "get_project_info",
        lambda _pid, info_type: histories.get(info_type, False),
    )
    monkeypatch.setattr(
        service,
        "get_stream_model_metadata",
        lambda name: {"label": name, "provider": "fake", "model": "fake-model"},
    )
    monkeypatch.setattr(
        service.documentTools, "generate_all_testdocs_str", lambda _pid: "all docs"
    )
    monkeypatch.setattr(
        service.documentTools,
        "generate_require_testdocs_str",
        lambda _pid: "requirements",
    )


async def collect_stream(**kwargs):
    return [event async for event in service.stream_test_plan(**kwargs)]


def fake_bundle_model():
    async def fake_model(_name, prompt_text, _max_tokens, **_kwargs):
        yield ModelStreamEvent("reasoning", text="分析")
        if "JSON 必须完整包含" in prompt_text:
            content = json.dumps(MENU)
        elif "软件测试专家" in prompt_text:
            content = "测试计划"
        else:
            content = "业务总结"
        yield ModelStreamEvent("content", text=content)
        yield ModelStreamEvent("usage", usage=TokenUsage(10, 3, 5, 18))

    return fake_model


def test_stuff_stream_generates_complete_bundle_then_saves_once(monkeypatch):
    configure_project(monkeypatch)
    saved = []
    monkeypatch.setattr(
        service.testProjectDao,
        "save_project_analysis_bundle",
        lambda *args: saved.append(args) or True,
    )
    monkeypatch.setattr(service, "stream_chat_completion", fake_bundle_model())

    events = asyncio.run(
        collect_stream(pid="p", llm_name="DeepSeek", regenerate=False)
    )
    event_names = [event["event"] for event in events]

    assert "reasoning_delta" in event_names
    assert next(e for e in events if e["event"] == "summary_delta")["data"][
        "text"
    ] == "业务总结"
    assert next(e for e in events if e["event"] == "answer_delta")["data"][
        "text"
    ] == "测试计划"
    assert next(e for e in events if e["event"] == "menu")["data"]["menu"] == MENU
    assert events[-2]["data"]["percent"] == 100
    assert events[-1] == {
        "event": "completed",
        "data": {"saved": True, "from_cache": False, "ready": True},
    }
    assert len(saved) == 1
    assert saved[0][1:3] == ("业务总结", "测试计划")
    assert json.loads(saved[0][3]) == MENU
    usage = next(event for event in events if event["event"] == "usage")
    assert usage["data"] == TokenUsage(30, 9, 15, 54).as_dict()


def test_complete_cached_bundle_does_not_call_model_or_write_database(monkeypatch):
    configure_project(
        monkeypatch,
        histories={
            InfoType.PROJECT_INITIAL_SUMMARY.value: "saved summary",
            InfoType.PROJECT_TEST_PLAN.value: "saved plan",
            InfoType.PROJECT_TEST_MENU.value: json.dumps(MENU),
        },
    )

    async def fail_model(*_args, **_kwargs):
        raise AssertionError("model must not be called for a complete cached bundle")
        yield

    monkeypatch.setattr(service, "stream_chat_completion", fail_model)
    monkeypatch.setattr(
        service.testProjectDao,
        "save_project_analysis_bundle",
        lambda *_args: pytest.fail("complete cache must not be rewritten"),
    )

    events = asyncio.run(
        collect_stream(pid="p", llm_name="GLM-4.7", regenerate=False)
    )

    assert next(e for e in events if e["event"] == "summary_delta")["data"][
        "text"
    ] == "saved summary"
    assert next(e for e in events if e["event"] == "answer_delta")["data"][
        "text"
    ] == "saved plan"
    assert events[-1]["data"] == {
        "saved": True,
        "from_cache": True,
        "ready": True,
    }


def test_old_project_with_summary_and_plan_only_generates_menu(monkeypatch):
    configure_project(
        monkeypatch,
        histories={
            InfoType.PROJECT_INITIAL_SUMMARY.value: "saved summary",
            InfoType.PROJECT_TEST_PLAN.value: "saved plan",
        },
    )
    calls = []

    async def menu_model(_name, prompt_text, _max_tokens, **_kwargs):
        calls.append(prompt_text)
        yield ModelStreamEvent("content", text=json.dumps(MENU))

    saved = []
    monkeypatch.setattr(service, "stream_chat_completion", menu_model)
    monkeypatch.setattr(
        service.testProjectDao,
        "save_project_analysis_bundle",
        lambda *args: saved.append(args) or True,
    )

    events = asyncio.run(
        collect_stream(pid="p", llm_name="DeepSeek", regenerate=False)
    )

    assert len(calls) == 1
    assert saved[0][1:3] == ("saved summary", "saved plan")
    assert next(e for e in events if e["event"] == "menu")["data"]["menu"] == MENU


def test_map_reduce_reports_plan_chunks_and_only_streams_final_outputs(monkeypatch):
    configure_project(monkeypatch, overflow=1)
    source_docs = [SimpleNamespace(page_content="source")]
    split_docs = [
        SimpleNamespace(page_content="chunk one"),
        SimpleNamespace(page_content="chunk two"),
    ]
    monkeypatch.setattr(
        service.documentTools, "generate_all_testdocs_docs", lambda _pid: source_docs
    )
    monkeypatch.setattr(
        service.documentTools,
        "generate_require_testdocs_docs",
        lambda _pid: source_docs,
    )
    monkeypatch.setattr(
        service.testdoc_text_splitter_for_menu,
        "split_documents",
        lambda _docs: split_docs,
    )
    monkeypatch.setattr(
        service.testdoc_text_splitter_for_acceptance,
        "split_documents",
        lambda _docs: split_docs,
    )
    monkeypatch.setattr(
        service.testProjectDao, "save_project_analysis_bundle", lambda *_args: True
    )
    call_number = 0

    async def fake_model(_name, prompt_text, _max_tokens, **_kwargs):
        nonlocal call_number
        call_number += 1
        yield ModelStreamEvent("reasoning", text=f"thought-{call_number}")
        content = json.dumps(MENU) if "JSON 必须完整包含" in prompt_text else f"content-{call_number}"
        yield ModelStreamEvent("content", text=content)
        yield ModelStreamEvent("usage", usage=TokenUsage(2, 1, 1, 4))

    monkeypatch.setattr(service, "stream_chat_completion", fake_model)

    events = asyncio.run(
        collect_stream(pid="p", llm_name="通义千问", regenerate=True)
    )

    assert call_number == 7
    assert [e["data"]["text"] for e in events if e["event"] == "summary_delta"] == [
        "content-3"
    ]
    assert [e["data"]["text"] for e in events if e["event"] == "answer_delta"] == [
        "content-6"
    ]
    map_progress = [
        e["data"]
        for e in events
        if e["event"] == "progress" and e["data"]["stage"] == "map"
    ]
    assert [(item["current"], item["total"]) for item in map_progress] == [
        (1, 2),
        (2, 2),
    ]


def test_invalid_menu_does_not_write_database(monkeypatch):
    configure_project(monkeypatch)
    writes = []

    async def invalid_menu_model(_name, prompt_text, _max_tokens, **_kwargs):
        content = "not json" if "JSON 必须完整包含" in prompt_text else "generated"
        yield ModelStreamEvent("content", text=content)

    monkeypatch.setattr(service, "stream_chat_completion", invalid_menu_model)
    monkeypatch.setattr(
        service.testProjectDao,
        "save_project_analysis_bundle",
        lambda *_args: writes.append(True) or True,
    )

    with pytest.raises(service.TestPlanStreamError) as raised:
        asyncio.run(collect_stream(pid="p", llm_name="DeepSeek", regenerate=True))
    assert raised.value.code == "menu_parse_error"
    assert writes == []


def test_disconnect_before_persistence_does_not_write_database(monkeypatch):
    configure_project(monkeypatch)
    writes = []
    monkeypatch.setattr(service, "stream_chat_completion", fake_bundle_model())
    monkeypatch.setattr(
        service.testProjectDao,
        "save_project_analysis_bundle",
        lambda *_args: writes.append(True) or True,
    )
    checks = 0

    async def disconnected():
        nonlocal checks
        checks += 1
        return checks >= 7

    async def consume():
        async for _event in service.stream_test_plan(
            "p", "DeepSeek", True, is_disconnected=disconnected
        ):
            pass

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(consume())
    assert writes == []


def test_menu_parser_accepts_markdown_fence_and_status_reports_ready(monkeypatch):
    fenced = f"```json\n{json.dumps(MENU)}\n```"
    assert service._parse_test_menu(fenced) == MENU
    configure_project(
        monkeypatch,
        histories={
            InfoType.PROJECT_INITIAL_SUMMARY.value: "summary",
            InfoType.PROJECT_TEST_PLAN.value: "plan",
            InfoType.PROJECT_TEST_MENU.value: fenced,
        },
    )

    status = asyncio.run(service.get_project_analysis_status("p"))

    assert status == {
        "summary_ready": True,
        "plan_ready": True,
        "menu_ready": True,
        "ready": True,
        "menu": MENU,
    }
