import asyncio
from datetime import UTC, datetime, timedelta
from functools import wraps
from types import SimpleNamespace

import pytest

from service.agentContracts import (
    AgentRunState,
    AgentRunStatus,
    ApprovalDecision,
    PlannedToolCall,
    RunBudget,
    TrustedProjectScope,
    approval_binding_for,
)
from service.agentToolExecutor import (
    AgentToolExecutor,
    ToolInvocationContext,
    ToolServiceBindings,
)
from service.agentToolRegistry import build_default_tool_registry
from service.agentToolSchemas import ToolExecutionStatus
from service.llmWorkflowStreamCore import WorkflowStreamError


def _async_test(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        return asyncio.run(function(*args, **kwargs))

    return wrapper


def _budget():
    return RunBudget(
        max_steps=5,
        max_elapsed_ms=60_000,
        max_input_tokens=100_000,
        max_output_tokens=20_000,
        max_model_calls=20,
        max_embedding_calls=10,
        max_tool_calls=10,
        max_estimated_cost_units=10_000,
    )


def _scope(project_id="project-a"):
    return TrustedProjectScope(
        project_id=project_id,
        actor_id="trusted-user",
        scope_version="v1",
    )


def _approved_context(operation, arguments, *, project_id="project-a"):
    registry = build_default_tool_registry()
    definition = registry.get(f"workflow_{operation}")
    model = definition.input_model.model_validate(arguments)
    call = PlannedToolCall(
        step_id="step-1",
        operation=operation,
        arguments=model.planned_arguments(),
        risks=definition.resolve_risks(regenerate=model.regenerate),
        idempotency_key="run-1:step-1",
        model_label=model.model_label,
    )
    state = AgentRunState(
        run_id="run-1",
        thread_id="thread-1",
        project_scope=_scope(project_id),
        source_revision="rev-1",
        goal="Generate tests",
        plan_version=1,
        plan=(call,),
        status=AgentRunStatus.EXECUTING,
        budget=_budget(),
    )
    now = datetime.now(UTC)
    approval = approval_binding_for(
        state,
        call,
        decision=ApprovalDecision.APPROVED,
        decided_at=now - timedelta(seconds=1),
        expires_at=now + timedelta(minutes=5),
        nonce="approval-1",
    )
    state = state.model_copy(update={"pending_approval": approval})
    return ToolInvocationContext(
        project_scope=_scope(project_id),
        run_state=state,
        approval=approval,
    )


def _bindings(*, workflow_stream=None, plan_stream=None):
    async def default_workflow(*_args, **_kwargs):
        yield {"event": "result", "data": {"result": {"ok": True}}}
        yield {
            "event": "completed",
            "data": {
                "saved": False,
                "from_cache": False,
                "operation": "unit_case",
                "artifact_key": "unit_case",
                "source_revision": "rev-1",
                "model_call_count": 1,
                "input_tokens": 10,
                "output_tokens": 5,
            },
        }

    async def default_plan(*_args, **_kwargs):
        yield {"event": "summary_delta", "data": {"text": "summary"}}
        yield {"event": "answer_delta", "data": {"text": "plan"}}
        yield {"event": "menu", "data": {"menu": {"ui_test": True}}}
        yield {
            "event": "completed",
            "data": {
                "saved": True,
                "from_cache": False,
                "artifact_key": "project_analysis_bundle",
                "model_call_count": 2,
                "input_tokens": 20,
                "output_tokens": 10,
            },
        }

    return ToolServiceBindings(
        project_setup_status=lambda pid: SimpleNamespace(
            model_dump=lambda mode="json": {
                "pid": pid,
                "stage": "setup_complete",
            }
        ),
        project_analysis_status=lambda pid: _async_value(
            {"pid": pid, "ready": True}
        ),
        project_workflow_status=lambda pid: SimpleNamespace(
            model_dump=lambda mode="json": {
                "pid": pid,
                "stage": "analysis_ready",
            }
        ),
        stream_test_plan=plan_stream or default_plan,
        stream_workflow=workflow_stream or default_workflow,
    )


async def _async_value(value):
    return value


@_async_test
@pytest.mark.parametrize(
    "tool_name",
    [
        "project_setup_status",
        "project_analysis_status",
        "project_workflow_status",
    ],
)
async def test_read_tools_use_only_trusted_scope(tool_name):
    executor = AgentToolExecutor(bindings=_bindings())
    result = await executor.execute(
        tool_name, {}, ToolInvocationContext(project_scope=_scope())
    )
    assert result.status is ToolExecutionStatus.SUCCESS
    assert result.data["pid"] == "project-a"
    assert result.usage.model_calls == 0
    assert result.usage.embedding_calls == 0


@_async_test
async def test_workflow_is_blocked_before_service_without_matching_approval():
    calls = 0

    async def forbidden(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        yield

    executor = AgentToolExecutor(bindings=_bindings(workflow_stream=forbidden))
    result = await executor.execute(
        "workflow_ui_case",
        {"model_label": "DeepSeek", "info": "ui"},
        ToolInvocationContext(project_scope=_scope()),
    )
    assert result.status is ToolExecutionStatus.APPROVAL_REQUIRED
    assert result.error.code == "approval_required"
    assert calls == 0


@_async_test
async def test_cross_project_state_is_blocked_before_service():
    calls = 0

    async def forbidden(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        yield

    arguments = {"model_label": "DeepSeek", "info": "ui"}
    context = _approved_context("ui_case", arguments)
    context = ToolInvocationContext(
        project_scope=_scope("project-b"),
        run_state=context.run_state,
        approval=context.approval,
    )
    executor = AgentToolExecutor(bindings=_bindings(workflow_stream=forbidden))
    result = await executor.execute("workflow_ui_case", arguments, context)
    assert result.status is ToolExecutionStatus.ERROR
    assert result.error.code == "project_scope_mismatch"
    assert calls == 0


@_async_test
async def test_approved_workflow_filters_reasoning_and_normalizes_progress():
    emitted = []

    async def stream(operation, pid, llm_name, payload, regenerate, **kwargs):
        assert (operation, pid, llm_name, payload, regenerate) == (
            "ui_case",
            "project-a",
            "DeepSeek",
            {"info": "ui"},
            False,
        )
        assert kwargs["is_disconnected"] is not None
        yield {"event": "progress", "data": {"stage": "a", "label": "A", "percent": 10}}
        yield {"event": "reasoning_delta", "data": {"text": "never expose"}}
        yield {"event": "progress", "data": {"stage": "same", "label": "same", "percent": 10}}
        yield {"event": "progress", "data": {"stage": "back", "label": "back", "percent": 5}}
        yield {"event": "progress", "data": {"stage": "b", "label": "B", "percent": 80}}
        yield {"event": "usage", "data": {"input_tokens": 12, "output_tokens": 7, "model_call_count": 1}}
        yield {"event": "artifact", "data": {"artifact_key": "ui_case", "source_revision": "rev-1", "status": "saved", "from_cache": False}}
        yield {"event": "result", "data": {"result": {"test_cases": "cases"}}}
        yield {"event": "completed", "data": {"saved": True, "from_cache": False, "artifact_key": "ui_case", "source_revision": "rev-1"}}

    async def sink(progress):
        emitted.append(progress)

    arguments = {"model_label": "DeepSeek", "info": "ui"}
    approved = _approved_context("ui_case", arguments)
    context = ToolInvocationContext(
        project_scope=approved.project_scope,
        run_state=approved.run_state,
        approval=approved.approval,
        progress_sink=sink,
    )
    result = await AgentToolExecutor(
        bindings=_bindings(workflow_stream=stream)
    ).execute("workflow_ui_case", arguments, context)

    assert result.status is ToolExecutionStatus.SUCCESS
    assert result.data == {"test_cases": "cases"}
    assert result.saved is True
    assert result.usage.input_tokens == 12
    assert [item.progress for item in emitted] == [10, 80]
    assert "reasoning" not in result.model_dump_json().lower()


@_async_test
async def test_project_analysis_builds_a_structured_result_without_raw_events():
    arguments = {"model_label": "DeepSeek", "regenerate": False}
    result = await AgentToolExecutor(bindings=_bindings()).execute(
        "workflow_project_analysis",
        arguments,
        _approved_context("project_analysis", arguments),
    )
    assert result.status is ToolExecutionStatus.SUCCESS
    assert result.data == {
        "summary": "summary",
        "plan": "plan",
        "menu": {"ui_test": True},
    }
    assert result.saved is True


@_async_test
async def test_cancellation_propagates_into_the_existing_generator():
    cancelled = False

    async def stream(*_args, **_kwargs):
        nonlocal cancelled
        try:
            yield {"event": "progress", "data": {"stage": "a", "label": "A", "percent": 10}}
            await asyncio.Future()
        except asyncio.CancelledError:
            cancelled = True
            raise

    arguments = {"model_label": "DeepSeek", "info": "ui"}
    task = asyncio.create_task(
        AgentToolExecutor(bindings=_bindings(workflow_stream=stream)).execute(
            "workflow_ui_case",
            arguments,
            _approved_context("ui_case", arguments),
        )
    )
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert cancelled is True


@_async_test
async def test_expected_and_unexpected_errors_are_sanitized():
    async def expected(*_args, **_kwargs):
        raise WorkflowStreamError(
            "provider_failed",
            "api_key=real-secret",
            status=502,
            retryable=True,
        )
        yield

    arguments = {"model_label": "DeepSeek", "info": "ui"}
    expected_result = await AgentToolExecutor(
        bindings=_bindings(workflow_stream=expected)
    ).execute(
        "workflow_ui_case",
        arguments,
        _approved_context("ui_case", arguments),
    )
    assert expected_result.error.code == "provider_failed"
    assert "real-secret" not in expected_result.error.safe_message

    async def unexpected(*_args, **_kwargs):
        raise RuntimeError("database password=secret and local path")
        yield

    unexpected_result = await AgentToolExecutor(
        bindings=_bindings(workflow_stream=unexpected)
    ).execute(
        "workflow_ui_case",
        arguments,
        _approved_context("ui_case", arguments),
    )
    assert unexpected_result.error.code == "internal_error"
    assert unexpected_result.error.safe_message == "Tool execution failed"
    assert "secret" not in unexpected_result.model_dump_json().lower()
