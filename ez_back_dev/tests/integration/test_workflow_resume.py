from __future__ import annotations

import asyncio
import json
import os
from dataclasses import replace
from typing import Any

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session as SqlAlchemySession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


os.environ["PYTHON_DOTENV_DISABLED"] = "1"
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
for provider_key in (
    "ZHIPU_API_KEY",
    "DASHSCOPE_API_KEY",
    "DEEPSEEK_API_KEY",
    "MOONSHOT_API_KEY",
):
    os.environ[provider_key] = ""

from model.TestProject import (
    Base,
    TestProject as ProjectRow,
    TestProjectInfo as ProjectInfoRow,
    TestProjectWorkflowArtifact as WorkflowArtifactRow,
)
from service import llmWorkflowStreamService as dispatcher
from service import workflowArtifactService as artifacts
from service.llmWorkflowStreamCore import WorkflowStreamError, event
from service.workflowArtifactService import WorkflowArtifactKey
from service.workflowCatalog import get_workflow_definition


WORKFLOW_PAYLOADS: dict[str, dict[str, Any]] = {
    "unit_menu": {},
    "unit_info": {"unit": "Cart"},
    "unit_case": {
        "method_type": 1,
        "static_method": "静态黑盒测试",
        "unit": "Cart",
        "unit_info": "cart analysis",
        "output_type": 0,
    },
    "integration_menu": {},
    "integration_info": {"integration_type": 2, "name": "Order"},
    "integration_case": {
        "strategy_type": 0,
        "strategy": "大爆炸集成",
        "integration_object": "Order",
        "integration_object_info": "integration analysis",
        "output_type": 0,
    },
    "api_info": {},
    "api_case": {
        "test_type": 1,
        "output_type": 0,
        "api_name": "/orders",
        "info": "api analysis",
    },
    "ui_info": {},
    "ui_case": {"info": "ui analysis"},
    "db_info": {},
    "db_case": {"info": "database analysis"},
    "functional_info": {},
    "functional_case": {
        "test_type": 1,
        "output_type": 0,
        "use_case_name": "创建订单",
        "info": "functional analysis",
    },
    "nonfunctional_info": {},
    "nonfunctional_case": {
        "method_name": "性能测试",
        "info": "nonfunctional analysis",
    },
    "acceptance_info": {},
    "acceptance_case": {"info": "acceptance analysis"},
}

ANALYSIS_OPERATIONS = tuple(
    operation
    for operation in WORKFLOW_PAYLOADS
    if get_workflow_definition(operation).phase == "analysis"
)
SESSION_ONLY_OPERATIONS = tuple(
    operation
    for operation in WORKFLOW_PAYLOADS
    if operation
    in {
        "unit_case",
        "integration_case",
        "api_case",
        "functional_case",
        "nonfunctional_case",
    }
)
PERSISTED_OPERATIONS = tuple(
    operation
    for operation in WORKFLOW_PAYLOADS
    if operation not in SESSION_ONLY_OPERATIONS
)


def _session_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as session:
        session.add(ProjectRow(id="EzResume", name="resume project"))
        session.commit()
    return engine, factory


def _configure_dispatcher(monkeypatch, factory, revision):
    monkeypatch.setattr(artifacts, "Session", factory)
    monkeypatch.setattr(
        artifacts,
        "compute_project_source_revision",
        lambda _pid: revision["value"],
    )
    monkeypatch.setattr(
        artifacts,
        "validate_workflow_prerequisites",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(dispatcher.testProjectDao, "find_project", lambda _pid: object())
    monkeypatch.setattr(
        dispatcher,
        "get_stream_model_metadata",
        lambda name: {"label": name, "provider": "mock", "model": "mock-model"},
    )


async def _collect(**kwargs):
    return [item async for item in dispatcher.stream_llm_workflow(**kwargs)]


@pytest.mark.parametrize("operation", PERSISTED_OPERATIONS)
def test_identical_workflow_request_resumes_without_provider_calls(
    monkeypatch, operation
):
    _engine, factory = _session_factory()
    revision = {"value": "rev-1"}
    _configure_dispatcher(monkeypatch, factory, revision)
    provider_calls = 0
    embedding_builds = 0

    async def fake_workflow(context):
        nonlocal provider_calls, embedding_builds
        provider_calls += 1
        embedding_builds += 1
        context.pending_info[11] = f"legacy-{context.operation}"
        yield event("answer_delta", text=f"answer-{context.operation}")
        yield event(
            "_workflow_result",
            result={"operation": context.operation, "test_cases": "saved cases"},
        )

    monkeypatch.setattr(dispatcher, "stream_analysis_operation", fake_workflow)
    monkeypatch.setattr(dispatcher, "stream_case_operation", fake_workflow)
    writes: list[str] = []
    real_save = artifacts.save_workflow_artifact

    def tracked_save(*args, **kwargs):
        writes.append(operation)
        return real_save(*args, **kwargs)

    monkeypatch.setattr(artifacts, "save_workflow_artifact", tracked_save)
    request = {
        "operation": operation,
        "pid": "EzResume",
        "llm_name": "DeepSeek",
        "payload": WORKFLOW_PAYLOADS[operation],
    }

    first = asyncio.run(_collect(**request))
    first_counts = (provider_calls, embedding_builds)
    second = asyncio.run(_collect(**request))

    assert first_counts == (1, 1)
    assert (provider_calls, embedding_builds) == first_counts
    assert writes == [operation]
    assert next(item for item in first if item["event"] == "completed")["data"][
        "from_cache"
    ] is False
    assert next(item for item in second if item["event"] == "completed")["data"][
        "from_cache"
    ] is True
    assert next(item for item in second if item["event"] == "result")["data"][
        "result"
    ] == {"operation": operation, "test_cases": "saved cases"}
    assert any(item["event"] == "artifact" for item in first)
    assert any(item["event"] == "artifact" for item in second)
    with factory() as session:
        assert len(session.scalars(select(WorkflowArtifactRow)).all()) == 1
        assert session.get(ProjectInfoRow, ("EzResume", 11)).info == (
            f"legacy-{operation}"
        )


@pytest.mark.parametrize("operation", SESSION_ONLY_OPERATIONS)
def test_selected_target_case_is_session_only_and_never_resumed(
    monkeypatch, operation
):
    _engine, factory = _session_factory()
    revision = {"value": "rev-1"}
    _configure_dispatcher(monkeypatch, factory, revision)
    provider_calls = 0

    async def fake_case(context):
        nonlocal provider_calls
        provider_calls += 1
        yield event("_workflow_result", result={"test_cases": context.operation})

    monkeypatch.setattr(dispatcher, "stream_case_operation", fake_case)
    request = {
        "operation": operation,
        "pid": "EzResume",
        "llm_name": "DeepSeek",
        "payload": WORKFLOW_PAYLOADS[operation],
    }

    first = asyncio.run(_collect(**request))
    second = asyncio.run(_collect(**request))

    assert provider_calls == 2
    for events in (first, second):
        assert not any(item["event"] == "artifact" for item in events)
        completed = next(item for item in events if item["event"] == "completed")
        assert completed["data"]["saved"] is False
        assert completed["data"]["from_cache"] is False
    with factory() as session:
        assert session.scalars(select(WorkflowArtifactRow)).all() == []


@pytest.mark.parametrize("operation", ANALYSIS_OPERATIONS)
def test_saved_analysis_resumes_across_model_selection_without_provider_calls(
    monkeypatch, operation
):
    _engine, factory = _session_factory()
    revision = {"value": "rev-1"}
    _configure_dispatcher(monkeypatch, factory, revision)
    provider_calls = 0

    async def fake_analysis(context):
        nonlocal provider_calls
        provider_calls += 1
        yield event(
            "_workflow_result",
            result={"operation": context.operation, "saved": True},
        )

    monkeypatch.setattr(dispatcher, "stream_analysis_operation", fake_analysis)
    request = {
        "operation": operation,
        "pid": "EzResume",
        "payload": WORKFLOW_PAYLOADS[operation],
    }

    asyncio.run(_collect(llm_name="DeepSeek", **request))
    resumed = asyncio.run(_collect(llm_name="GLM-4.7", **request))

    assert provider_calls == 1
    artifact_event = next(item for item in resumed if item["event"] == "artifact")
    assert artifact_event["data"]["from_cache"] is True
    assert artifact_event["data"]["model_label"] == "DeepSeek"
    assert next(item for item in resumed if item["event"] == "result")["data"][
        "result"
    ] == {"operation": operation, "saved": True}
    with factory() as session:
        rows = session.scalars(select(WorkflowArtifactRow)).all()
    assert len(rows) == 1
    assert rows[0].model_label == "DeepSeek"


def test_relevant_input_revision_prompt_and_regenerate_are_cache_misses(
    monkeypatch,
):
    _engine, factory = _session_factory()
    revision = {"value": "rev-1"}
    _configure_dispatcher(monkeypatch, factory, revision)
    calls = 0
    regenerate_flags: list[bool] = []

    async def fake_analysis(context):
        nonlocal calls
        calls += 1
        regenerate_flags.append(context.regenerate)
        yield event("_workflow_result", result={"unit": context.payload["unit"]})

    monkeypatch.setattr(dispatcher, "stream_analysis_operation", fake_analysis)
    base_definition = get_workflow_definition("unit_info")
    prompt_version = {"value": base_definition.prompt_version}
    monkeypatch.setattr(
        dispatcher,
        "get_workflow_definition",
        lambda _operation: replace(
            base_definition, prompt_version=prompt_version["value"]
        ),
    )

    def execute(payload, *, llm_name="DeepSeek", regenerate=False):
        return asyncio.run(
            _collect(
                operation="unit_info",
                pid="EzResume",
                llm_name=llm_name,
                payload=payload,
                regenerate=regenerate,
            )
        )

    execute({"unit": "Cart"})
    execute({"unit": "Cart"})
    assert calls == 1

    execute({"unit": "Order"})
    assert calls == 2

    revision["value"] = "rev-2"
    stale_events = execute({"unit": "Order"})
    assert calls == 3
    assert any(item["event"] == "stale" for item in stale_events)

    prompt_version["value"] = "unit-info-v3-test"
    execute({"unit": "Order"})
    assert calls == 4

    resumed = execute({"unit": "Order"}, llm_name="GLM-4.7")
    assert calls == 4
    assert next(item for item in resumed if item["event"] == "artifact")["data"][
        "model_label"
    ] == "DeepSeek"

    execute({"unit": "Order"}, llm_name="GLM-4.7", regenerate=True)
    assert calls == 5
    assert regenerate_flags == [False, True, True, True, True]
    with factory() as session:
        rows = session.scalars(select(WorkflowArtifactRow)).all()
    assert {row.model_label for row in rows} >= {"DeepSeek", "GLM-4.7"}


def test_case_artifact_stores_normalized_selection_and_final_result(monkeypatch):
    _engine, factory = _session_factory()
    monkeypatch.setattr(artifacts, "Session", factory)
    definition = get_workflow_definition("unit_case")
    key = WorkflowArtifactKey(
        operation="unit_case",
        input_hash="input-hash",
        source_revision="rev-1",
        prompt_version=definition.prompt_version,
        model_label="DeepSeek",
    )
    payload = WORKFLOW_PAYLOADS["unit_case"]
    result = {
        "unit_test_knowledge": "knowledge answer",
        "test_cases": "final case body",
    }

    assert artifacts.save_workflow_artifact(
        "EzResume",
        definition,
        key,
        payload,
        result,
        {3: "knowledge answer"},
        call_count=3,
    )

    with factory() as session:
        row = session.scalar(select(WorkflowArtifactRow))
        stored = json.loads(row.content)
        metadata = json.loads(row.metadata_json)
    assert stored == {
        "version": 1,
        "operation": "unit_case",
        "selection": {
            "method_type": 1,
            "output_type": 0,
            "static_method": "静态黑盒测试",
            "unit": "Cart",
        },
        "result": result,
    }
    assert "cart analysis" not in row.content
    assert metadata == {"call_count": 3, "operation": "unit_case"}


def test_failed_atomic_replacement_preserves_artifact_and_legacy_seed(monkeypatch):
    engine, factory = _session_factory()
    monkeypatch.setattr(artifacts, "Session", factory)
    definition = get_workflow_definition("api_info")
    key = WorkflowArtifactKey(
        operation="api_info",
        input_hash="input-hash",
        source_revision="rev-1",
        prompt_version=definition.prompt_version,
        model_label="DeepSeek",
    )
    assert artifacts.save_workflow_artifact(
        "EzResume",
        definition,
        key,
        {},
        {"apis_info": "old result", "list": {"api_list": ["/old"]}},
        {11: "old result"},
        call_count=2,
    )

    class FailingCommitSession(SqlAlchemySession):
        def commit(self):
            raise RuntimeError("sanitized commit failure")

    monkeypatch.setattr(
        artifacts,
        "Session",
        sessionmaker(bind=engine, class_=FailingCommitSession),
    )
    assert not artifacts.save_workflow_artifact(
        "EzResume",
        definition,
        key,
        {},
        {"apis_info": "new result", "list": {"api_list": ["/new"]}},
        {11: "new result"},
        call_count=2,
    )

    with factory() as session:
        artifact_row = session.scalar(select(WorkflowArtifactRow))
        legacy_row = session.get(ProjectInfoRow, ("EzResume", 11))
    assert json.loads(artifact_row.content)["result"]["apis_info"] == "old result"
    assert legacy_row.info == "old result"


def test_stale_document_provider_failure_leaves_previous_artifact_readable(
    monkeypatch,
):
    _engine, factory = _session_factory()
    revision = {"value": "rev-1"}
    _configure_dispatcher(monkeypatch, factory, revision)
    should_fail = {"value": False}

    async def fake_analysis(_context):
        if should_fail["value"]:
            raise WorkflowStreamError("provider_error", "safe failure")
        yield event("_workflow_result", result="old result")

    monkeypatch.setattr(dispatcher, "stream_analysis_operation", fake_analysis)
    request = {
        "operation": "ui_info",
        "pid": "EzResume",
        "llm_name": "DeepSeek",
        "payload": {},
    }
    asyncio.run(_collect(**request))
    revision["value"] = "rev-2"
    should_fail["value"] = True

    with pytest.raises(WorkflowStreamError, match="safe failure"):
        asyncio.run(_collect(**request))

    with factory() as session:
        rows = session.scalars(select(WorkflowArtifactRow)).all()
    assert len(rows) == 1
    assert rows[0].source_revision == "rev-1"
    assert json.loads(rows[0].content)["result"] == "old result"


def test_prerequisites_accept_legacy_seed_or_legacy_payload_compatibility(
    monkeypatch,
):
    _engine, factory = _session_factory()
    monkeypatch.setattr(artifacts, "Session", factory)
    with factory() as session:
        session.add_all(
            [
                ProjectInfoRow(id="EzResume", info_type=1, info="summary"),
                ProjectInfoRow(id="EzResume", info_type=22, info="plan"),
                ProjectInfoRow(id="EzResume", info_type=23, info="menu"),
            ]
        )
        session.commit()

    artifacts.validate_workflow_prerequisites(
        "EzResume",
        get_workflow_definition("api_info"),
        {},
        "rev-1",
    )
    artifacts.validate_workflow_prerequisites(
        "EzResume",
        get_workflow_definition("unit_case"),
        {"unit_info": "legacy client supplied analysis"},
        "rev-1",
    )

    with pytest.raises(WorkflowStreamError) as captured:
        artifacts.validate_workflow_prerequisites(
            "EzResume",
            get_workflow_definition("integration_case"),
            {},
            "rev-1",
        )
    assert captured.value.code == "workflow_prerequisite_missing"


def test_revision_aware_prerequisite_history_is_authoritative_over_legacy_seed(
    monkeypatch,
):
    _engine, factory = _session_factory()
    monkeypatch.setattr(artifacts, "Session", factory)
    definition = get_workflow_definition("project_analysis")
    key = WorkflowArtifactKey(
        operation="project_analysis",
        input_hash="analysis-input",
        source_revision="rev-old",
        prompt_version=definition.prompt_version,
        model_label="DeepSeek",
    )
    assert artifacts.save_workflow_artifact(
        "EzResume",
        definition,
        key,
        {},
        {"summary": "old", "plan": "old", "menu": {}},
        {
            1: "legacy summary",
            22: "legacy plan",
            23: "legacy menu",
        },
        call_count=2,
    )

    with pytest.raises(WorkflowStreamError) as captured:
        artifacts.validate_workflow_prerequisites(
            "EzResume",
            get_workflow_definition("api_info"),
            {},
            "rev-current",
        )
    assert captured.value.code == "workflow_prerequisite_missing"


def test_same_revision_artifact_marked_stale_is_not_resumed(monkeypatch):
    _engine, factory = _session_factory()
    monkeypatch.setattr(artifacts, "Session", factory)
    monkeypatch.setattr(
        artifacts, "compute_project_source_revision", lambda _pid: "rev-1"
    )
    definition = get_workflow_definition("db_info")
    key = artifacts.build_workflow_artifact_key(
        "EzResume", definition, {}, "DeepSeek"
    )
    assert artifacts.save_workflow_artifact(
        "EzResume",
        definition,
        key,
        {},
        "old result",
        {},
        call_count=1,
    )
    with factory() as session:
        row = session.scalar(select(WorkflowArtifactRow))
        row.metadata_json = json.dumps(
            {"stale_for_source_revision": "rev-2"},
            separators=(",", ":"),
        )
        session.commit()

    lookup = artifacts.lookup_workflow_artifact(
        "EzResume", definition, {}, "DeepSeek"
    )

    assert lookup.artifact is None
    assert lookup.stale is True
