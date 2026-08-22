import asyncio
import json
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from dao import testProjectDao
from dao.workflowArtifactDao import WorkflowArtifactRecord
from llm.streaming import ModelStreamEvent, TokenUsage
from langchain_core.documents import Document
from model.ChainJsonModel import ProjectAnalysisDigest, TestMenu as MenuModel
from model.TestProject import (
    Base,
    TestProject as ProjectRow,
    TestProjectInfo as ProjectInfoRow,
    TestProjectWorkflowArtifact as ArtifactRow,
)
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


def _artifact_content(summary="saved summary", plan="saved plan"):
    return json.dumps(
        {"summary": summary, "menu": MENU, "plan": plan},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _artifact(summary="saved summary", plan="saved plan"):
    return WorkflowArtifactRecord(
        project_id="p",
        artifact_key="project_analysis_bundle",
        input_hash="input-hash",
        source_revision="rev-1",
        prompt_version="project-analysis-v2",
        model_label="DeepSeek",
        content=_artifact_content(summary, plan),
        metadata={"budget_profile": "project-analysis-v2"},
    )


def configure_project(
    monkeypatch,
    *,
    overflow=0,
    histories=None,
    artifact=None,
    source_revision="rev-1",
):
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
        "compute_project_source_revision",
        lambda _pid: source_revision,
        raising=False,
    )
    monkeypatch.setattr(
        service,
        "get_fresh_artifact",
        lambda *_args: artifact,
        raising=False,
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
        "generate_all_testdocs_docs",
        lambda _pid: [SimpleNamespace(page_content="all docs", metadata={})],
    )


def install_save_spy(monkeypatch, saved):
    monkeypatch.setattr(
        service.testProjectDao,
        "save_project_analysis_artifact_bundle",
        lambda *args, **kwargs: saved.append((args, kwargs)) or True,
        raising=False,
    )
    monkeypatch.setattr(
        service.testProjectDao,
        "save_project_analysis_bundle",
        lambda *_args: pytest.fail("Task 4 must use the atomic artifact bundle save"),
    )


async def collect_stream(**kwargs):
    return [event async for event in service.stream_test_plan(**kwargs)]


def digest_and_plan_model(calls):
    async def fake_model(_name, prompt_text, max_tokens, **kwargs):
        calls.append((prompt_text, max_tokens, kwargs["request_options"]))
        yield ModelStreamEvent("reasoning", text="分析")
        if "[PROJECT_ANALYSIS_DIGEST" in prompt_text:
            content = json.dumps({"summary": "业务总结", "menu": MENU})
        elif "[TEST_PLAN_FROM_DIGEST_V2]" in prompt_text:
            content = "测试计划"
        else:
            raise AssertionError("unexpected Task 4 prompt")
        yield ModelStreamEvent("content", text=content)
        yield ModelStreamEvent("usage", usage=TokenUsage(10, 3, 5, 18))

    return fake_model


def test_project_analysis_digest_schema_is_nested_and_validated():
    digest = ProjectAnalysisDigest.model_validate(
        {"summary": "evidence-oriented summary", "menu": MENU}
    )

    assert digest.summary == "evidence-oriented summary"
    assert digest.menu.model_dump() == MENU


def test_structural_design_evidence_unlocks_unit_and_integration_false_negatives():
    evidence = service.collect_project_test_evidence(
        [
            Document(
                page_content=(
                    "课程模块通过 REST 接口调用用户服务，系统采用 SpringBoot 分层架构，"
                    "并由控制层、服务层和数据访问层协作完成业务。"
                )
            )
        ]
    )
    candidate = MenuModel.model_validate(
        {**MENU, "unit_test": False, "integration_test": False}
    )

    reconciled = service.reconcile_test_menu(candidate, evidence)

    assert reconciled.unit_test is True
    assert reconciled.integration_test is True
    assert evidence.unit_signal_categories >= 2
    assert evidence.integration_signal_categories >= 2


def test_business_only_text_does_not_force_unit_or_integration():
    evidence = service.collect_project_test_evidence(
        [Document(page_content="平台支持用户登录、课程浏览和博客评论。")]
    )
    candidate = MenuModel.model_validate(
        {**MENU, "unit_test": False, "integration_test": False}
    )

    reconciled = service.reconcile_test_menu(candidate, evidence)

    assert reconciled.unit_test is False
    assert reconciled.integration_test is False


def test_small_document_uses_one_digest_call_and_one_plan_call(monkeypatch):
    configure_project(monkeypatch)
    calls = []
    saved = []
    install_save_spy(monkeypatch, saved)
    monkeypatch.setattr(service, "stream_chat_completion", digest_and_plan_model(calls))

    events = asyncio.run(
        collect_stream(pid="p", llm_name="DeepSeek", regenerate=False)
    )

    assert len(calls) == 2
    assert "all docs" in calls[0][0]
    assert "all docs" not in calls[1][0]
    assert "业务总结" in calls[1][0]
    assert "unit_test" in calls[1][0]
    assert calls[0][1] == 2_048
    assert calls[0][2]["extra_body"] == {"thinking": {"type": "disabled"}}
    assert calls[1][1] == 8_192
    assert calls[1][2]["reasoning_effort"] == "high"
    assert next(e for e in events if e["event"] == "summary_delta")["data"][
        "text"
    ] == "业务总结"
    assert next(e for e in events if e["event"] == "answer_delta")["data"][
        "text"
    ] == "测试计划"
    assert next(e for e in events if e["event"] == "menu")["data"]["menu"] == MENU
    meta = next(e for e in events if e["event"] == "meta")["data"]
    assert meta["budget_profile"] == "project-analysis-v2"
    assert meta["budget"]["map_output_tokens"] == 1_024
    assert meta["budget"]["final_output_tokens"] == 8_192
    assert meta["source_revision"] == "rev-1"
    assert events[-1] == {
        "event": "completed",
        "data": {
            "saved": True,
            "from_cache": False,
            "ready": True,
            "artifact_key": "project_analysis_bundle",
            "model_call_count": 2,
            "input_tokens": 20,
            "reasoning_tokens": 6,
            "output_tokens": 10,
            "total_tokens": 36,
        },
    }
    assert len(saved) == 1
    args, kwargs = saved[0]
    assert args[0:4] == (
        "p",
        "业务总结",
        "测试计划",
        json.dumps(MENU, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
    )
    assert kwargs["artifact_key"] == "project_analysis_bundle"
    assert kwargs["source_revision"] == "rev-1"
    assert kwargs["prompt_version"] == "project-analysis-v2"
    usage = next(event for event in events if event["event"] == "usage")
    assert usage["data"] == {
        **TokenUsage(20, 6, 10, 36).as_dict(),
        "model_call_count": 2,
    }


def test_complete_fresh_artifact_uses_zero_model_and_document_calls(monkeypatch):
    cached = _artifact()
    lookups = []
    configure_project(monkeypatch, artifact=cached)
    monkeypatch.setattr(
        service,
        "get_fresh_artifact",
        lambda *args: lookups.append(args) or cached,
        raising=False,
    )

    async def fail_model(*_args, **_kwargs):
        raise AssertionError("fresh artifact must not call a model")
        yield

    monkeypatch.setattr(service, "stream_chat_completion", fail_model)
    monkeypatch.setattr(
        service.documentTools,
        "generate_all_testdocs_str",
        lambda _pid: pytest.fail("fresh artifact must not load documents"),
    )
    monkeypatch.setattr(
        service.testProjectDao,
        "save_project_analysis_artifact_bundle",
        lambda *_args, **_kwargs: pytest.fail("fresh artifact must not be rewritten"),
        raising=False,
    )

    events = asyncio.run(
        collect_stream(pid="p", llm_name="DeepSeek", regenerate=False)
    )

    assert len(lookups) == 1
    assert lookups[0][0] == "p"
    assert lookups[0][1] == "project_analysis_bundle"
    assert lookups[0][2] == "rev-1"
    assert lookups[0][4:] == ("project-analysis-v2", "DeepSeek")
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
        "artifact_key": "project_analysis_bundle",
        "model_call_count": 0,
        "input_tokens": None,
        "reasoning_tokens": None,
        "output_tokens": None,
        "total_tokens": None,
    }


def test_legacy_bundle_without_revision_key_is_regenerated_once(monkeypatch):
    configure_project(
        monkeypatch,
        histories={
            InfoType.PROJECT_INITIAL_SUMMARY.value: "legacy summary",
            InfoType.PROJECT_TEST_PLAN.value: "legacy plan",
            InfoType.PROJECT_TEST_MENU.value: json.dumps(MENU),
        },
    )
    calls = []
    saved = []
    install_save_spy(monkeypatch, saved)
    monkeypatch.setattr(service, "stream_chat_completion", digest_and_plan_model(calls))

    events = asyncio.run(
        collect_stream(pid="p", llm_name="DeepSeek", regenerate=False)
    )

    assert len(calls) == 2
    assert len(saved) == 1
    assert events[-1]["data"]["from_cache"] is False


def test_large_document_uses_one_map_per_chunk_then_digest_and_plan(monkeypatch):
    configure_project(monkeypatch, overflow=4)
    source_docs = [SimpleNamespace(page_content="source", metadata={})]
    split_docs = [
        SimpleNamespace(page_content="chunk one"),
        SimpleNamespace(page_content="chunk two"),
    ]
    monkeypatch.setattr(
        service.documentTools, "generate_all_testdocs_docs", lambda _pid: source_docs
    )
    monkeypatch.setattr(
        service.testdoc_text_splitter_for_menu,
        "split_documents",
        lambda _docs: split_docs,
    )
    monkeypatch.setattr(
        service.documentTools,
        "num_tokens_from_string",
        lambda _text: 64_001,
    )
    monkeypatch.setattr(
        service.documentTools,
        "generate_require_testdocs_docs",
        lambda _pid: pytest.fail("plan generation must not reload requirement docs"),
        raising=False,
    )
    calls = []
    saved = []
    install_save_spy(monkeypatch, saved)

    async def fake_model(_name, prompt_text, _max_tokens, **_kwargs):
        calls.append(prompt_text)
        if "[PROJECT_ANALYSIS_DIGEST_MAP_V2]" in prompt_text:
            content = f"evidence-{len(calls)}"
        elif "[PROJECT_ANALYSIS_DIGEST_REDUCE_V2]" in prompt_text:
            content = json.dumps({"summary": "large summary", "menu": MENU})
        elif "[TEST_PLAN_FROM_DIGEST_V2]" in prompt_text:
            content = "large plan"
        else:
            raise AssertionError("separate menu or plan-map call detected")
        yield ModelStreamEvent("content", text=content)
        yield ModelStreamEvent("usage", usage=TokenUsage(2, 1, 1, 4))

    monkeypatch.setattr(service, "stream_chat_completion", fake_model)

    events = asyncio.run(
        collect_stream(pid="p", llm_name="通义千问", regenerate=True)
    )

    assert len(calls) == 4
    assert sum("[PROJECT_ANALYSIS_DIGEST_MAP_V2]" in item for item in calls) == 2
    assert sum("[PROJECT_ANALYSIS_DIGEST_REDUCE_V2]" in item for item in calls) == 1
    assert sum("[TEST_PLAN_FROM_DIGEST_V2]" in item for item in calls) == 1
    assert all("[PROJECT_ANALYSIS_MENU" not in item for item in calls)
    assert [e["data"]["text"] for e in events if e["event"] == "summary_delta"] == [
        "large summary"
    ]
    assert [e["data"]["text"] for e in events if e["event"] == "answer_delta"] == [
        "large plan"
    ]
    assert len(saved) == 1


def test_invalid_digest_gets_one_bounded_repair_without_source_documents(monkeypatch):
    configure_project(monkeypatch)
    calls = []
    saved = []
    install_save_spy(monkeypatch, saved)

    async def repair_model(_name, prompt_text, _max_tokens, **_kwargs):
        calls.append(prompt_text)
        if "[PROJECT_ANALYSIS_DIGEST_REPAIR_V2]" in prompt_text:
            content = json.dumps({"summary": "repaired summary", "menu": MENU})
        elif "[PROJECT_ANALYSIS_DIGEST_STUFF_V2]" in prompt_text:
            content = "invalid-digest-output" + "x" * 20_000
        elif "[TEST_PLAN_FROM_DIGEST_V2]" in prompt_text:
            content = "repaired plan"
        else:
            raise AssertionError("unexpected prompt")
        yield ModelStreamEvent("content", text=content)

    monkeypatch.setattr(service, "stream_chat_completion", repair_model)

    events = asyncio.run(
        collect_stream(pid="p", llm_name="DeepSeek", regenerate=True)
    )

    assert len(calls) == 3
    assert "all docs" in calls[0]
    assert "invalid-digest-output" in calls[1]
    assert "all docs" not in calls[1]
    assert len(calls[1]) < 16_000
    assert "all docs" not in calls[2]
    assert len(saved) == 1
    assert next(e for e in events if e["event"] == "summary_delta")["data"][
        "text"
    ] == "repaired summary"


def test_invalid_digest_and_failed_repair_do_not_write_database(monkeypatch):
    configure_project(monkeypatch)
    writes = []
    install_save_spy(monkeypatch, writes)
    calls = []

    async def invalid_model(_name, prompt_text, _max_tokens, **_kwargs):
        calls.append(prompt_text)
        yield ModelStreamEvent("content", text="not json")

    monkeypatch.setattr(service, "stream_chat_completion", invalid_model)

    with pytest.raises(service.TestPlanStreamError) as raised:
        asyncio.run(collect_stream(pid="p", llm_name="DeepSeek", regenerate=True))

    assert raised.value.code == "digest_parse_error"
    assert len(calls) == 2
    assert writes == []


def test_disconnect_before_persistence_keeps_previous_bundle(monkeypatch):
    configure_project(monkeypatch)
    writes = []
    install_save_spy(monkeypatch, writes)
    monkeypatch.setattr(service, "stream_chat_completion", digest_and_plan_model([]))
    disconnected_now = False

    async def disconnected():
        return disconnected_now

    async def consume():
        nonlocal disconnected_now
        async for item in service.stream_test_plan(
            "p", "DeepSeek", True, is_disconnected=disconnected
        ):
            if item["event"] == "menu":
                disconnected_now = True

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(consume())
    assert writes == []


def test_digest_parser_accepts_markdown_fence_and_status_remains_compatible(
    monkeypatch,
):
    fenced_digest = (
        "```json\n"
        + json.dumps({"summary": "summary", "menu": MENU})
        + "\n```"
    )
    assert service._parse_project_analysis_digest(fenced_digest).model_dump() == {
        "summary": "summary",
        "menu": MENU,
    }
    fenced_menu = f"```json\n{json.dumps(MENU)}\n```"
    assert service._parse_test_menu(fenced_menu) == MENU
    configure_project(
        monkeypatch,
        histories={
            InfoType.PROJECT_INITIAL_SUMMARY.value: "summary",
            InfoType.PROJECT_TEST_PLAN.value: "plan",
            InfoType.PROJECT_TEST_MENU.value: fenced_menu,
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


def _seed_analysis_bundle(factory):
    with factory() as session:
        session.add(ProjectRow(id="p", name="project"))
        session.add_all(
            [
                ProjectInfoRow(
                    id="p",
                    info_type=InfoType.PROJECT_INITIAL_SUMMARY.value,
                    info="old summary",
                ),
                ProjectInfoRow(
                    id="p",
                    info_type=InfoType.PROJECT_TEST_PLAN.value,
                    info="old plan",
                ),
                ProjectInfoRow(
                    id="p",
                    info_type=InfoType.PROJECT_TEST_MENU.value,
                    info=json.dumps(MENU),
                ),
                ArtifactRow(
                    project_id="p",
                    artifact_key="project_analysis_bundle",
                    input_hash="input-hash",
                    source_revision="rev-1",
                    prompt_version="project-analysis-v2",
                    model_label="DeepSeek",
                    content=_artifact_content("old summary", "old plan"),
                    metadata_json="{}",
                ),
            ]
        )
        session.commit()


def _save_atomic_bundle():
    return testProjectDao.save_project_analysis_artifact_bundle(
        "p",
        "new summary",
        "new plan",
        json.dumps(MENU),
        artifact_key="project_analysis_bundle",
        input_hash="input-hash",
        source_revision="rev-1",
        prompt_version="project-analysis-v2",
        model_label="DeepSeek",
        artifact_content=_artifact_content("new summary", "new plan"),
        metadata_json='{"budget_profile":"project-analysis-v2"}',
    )


def test_analysis_artifact_and_legacy_bundle_are_replaced_atomically(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    _seed_analysis_bundle(factory)
    monkeypatch.setattr(testProjectDao, "Session", factory)

    assert _save_atomic_bundle() is True

    with factory() as session:
        info = {
            row.info_type: row.info
            for row in session.scalars(select(ProjectInfoRow)).all()
        }
        artifact = session.scalar(select(ArtifactRow))
    assert info[InfoType.PROJECT_INITIAL_SUMMARY.value] == "new summary"
    assert info[InfoType.PROJECT_TEST_PLAN.value] == "new plan"
    assert json.loads(artifact.content)["plan"] == "new plan"


def test_failed_atomic_replace_preserves_previous_valid_bundle(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    _seed_analysis_bundle(factory)
    monkeypatch.setattr(testProjectDao, "Session", factory)

    def fail_commit(_session):
        raise RuntimeError("synthetic commit failure")

    event.listen(factory.class_, "before_commit", fail_commit)
    try:
        assert _save_atomic_bundle() is False
    finally:
        event.remove(factory.class_, "before_commit", fail_commit)

    with factory() as session:
        info = {
            row.info_type: row.info
            for row in session.scalars(select(ProjectInfoRow)).all()
        }
        artifact = session.scalar(select(ArtifactRow))
    assert info[InfoType.PROJECT_INITIAL_SUMMARY.value] == "old summary"
    assert info[InfoType.PROJECT_TEST_PLAN.value] == "old plan"
    assert json.loads(artifact.content)["plan"] == "old plan"
