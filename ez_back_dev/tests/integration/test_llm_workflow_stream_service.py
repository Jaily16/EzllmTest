import asyncio

import pytest

from service import llmWorkflowStreamService as service
from llm.streaming import TokenUsage
from service.llmWorkflowStreamCore import event
from service.workflowArtifactService import (
    WorkflowArtifactKey,
    WorkflowArtifactLookup,
)


def configure(monkeypatch):
    monkeypatch.setattr(
        service,
        "get_stream_model_metadata",
        lambda name: {"label": name, "provider": "fake", "model": "fake-model"},
    )
    monkeypatch.setattr(service.testProjectDao, "find_project", lambda _pid: object())
    monkeypatch.setattr(
        service.workflowArtifactService,
        "lookup_workflow_artifact",
        lambda _pid, definition, _payload, model_label: WorkflowArtifactLookup(
            key=WorkflowArtifactKey(
                operation=definition.operation,
                input_hash="input-hash",
                source_revision="source-revision",
                prompt_version=definition.prompt_version,
                model_label=model_label,
            ),
            artifact=None,
            stale=False,
        ),
    )
    monkeypatch.setattr(
        service.workflowArtifactService,
        "validate_workflow_prerequisites",
        lambda *_args: None,
    )


async def collect(**kwargs):
    return [item async for item in service.stream_llm_workflow(**kwargs)]


def test_dispatcher_saves_pending_values_then_emits_public_result(monkeypatch):
    configure(monkeypatch)
    saved = []
    source_revisions = []

    async def fake_analysis(context):
        source_revisions.append(context.source_revision)
        context.usages.append(TokenUsage(2, 1, 3, 6))
        context.pending_info[11] = "summary"
        yield event("answer_delta", text="summary")
        yield event("_workflow_result", result={"apis_info": "summary"})

    monkeypatch.setattr(service, "stream_analysis_operation", fake_analysis)
    monkeypatch.setattr(
        service.workflowArtifactService,
        "save_workflow_artifact",
        lambda pid, _definition, _key, _payload, result, pending, **_kwargs: (
            saved.append((pid, result, pending.copy())) or True
        ),
    )

    events = asyncio.run(
        collect(
            operation="api_info",
            pid="p",
            llm_name="DeepSeek",
            payload={},
        )
    )

    assert saved == [("p", {"apis_info": "summary"}, {11: "summary"})]
    assert source_revisions == ["source-revision"]
    assert next(item for item in events if item["event"] == "result")["data"] == {
        "result": {"apis_info": "summary"}
    }
    assert events[-1]["event"] == "completed"
    meta = next(item["data"] for item in events if item["event"] == "meta")
    usage = next(item["data"] for item in events if item["event"] == "usage")
    completed = events[-1]["data"]
    assert meta["budget"]["final_output_tokens"] == 8_192
    assert usage["model_call_count"] == 1
    assert completed["model_call_count"] == 1
    assert completed["total_tokens"] == 6


def test_disconnect_before_persistence_keeps_pending_values_unwritten(monkeypatch):
    configure(monkeypatch)
    writes = []

    async def fake_analysis(context):
        context.pending_info[11] = "summary"
        yield event("_workflow_result", result="summary")

    monkeypatch.setattr(service, "stream_analysis_operation", fake_analysis)
    monkeypatch.setattr(
        service.workflowArtifactService,
        "save_workflow_artifact",
        lambda *_args, **_kwargs: writes.append(True) or True,
    )
    checks = 0

    async def disconnected():
        nonlocal checks
        checks += 1
        return checks >= 2

    async def consume():
        async for _item in service.stream_llm_workflow(
            "api_info",
            "p",
            "DeepSeek",
            {},
            is_disconnected=disconnected,
        ):
            pass

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(consume())
    assert writes == []


def test_supported_operation_inventory_covers_all_eighteen_workflows():
    assert service.SUPPORTED_WORKFLOW_OPERATIONS == {
        "unit_menu",
        "unit_info",
        "unit_case",
        "integration_menu",
        "integration_info",
        "integration_case",
        "api_info",
        "api_case",
        "ui_info",
        "ui_case",
        "db_info",
        "db_case",
        "functional_info",
        "functional_case",
        "nonfunctional_info",
        "nonfunctional_case",
        "acceptance_info",
        "acceptance_case",
    }
