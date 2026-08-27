from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from service.agentContracts import (
    AgentRunState,
    ApprovalDecision,
    PlannedToolCall,
    RunBudget,
    ToolRisk,
    TrustedProjectScope,
    approval_binding_for,
    approval_is_valid,
    redact_sensitive_text,
    requires_approval,
    typed_tool_definition_for,
    typed_tool_definitions,
)


def _budget() -> RunBudget:
    return RunBudget(
        max_steps=8,
        max_elapsed_ms=30_000,
        max_input_tokens=100_000,
        max_output_tokens=32_768,
        max_model_calls=8,
        max_embedding_calls=2,
        max_tool_calls=8,
        max_estimated_cost_units=10_000,
    )


def _scope(project_id: str = "synthetic-alpha") -> TrustedProjectScope:
    return TrustedProjectScope(
        project_id=project_id,
        actor_id="offline-evaluator",
        scope_version="scope-v1",
    )


def _call(**changes) -> PlannedToolCall:
    values = {
        "step_id": "step-1",
        "operation": "ui_case",
        "arguments": {"info": "synthetic ui description"},
        "risks": {ToolRisk.PAID, ToolRisk.PERSISTENT},
        "idempotency_key": "run-1:plan-1:step-1",
        "model_label": "deterministic-fake",
    }
    values.update(changes)
    return PlannedToolCall(**values)


def _state(call: PlannedToolCall | None = None) -> AgentRunState:
    return AgentRunState(
        run_id="run-1",
        thread_id="thread-1",
        project_scope=_scope(),
        source_revision="revision-a",
        goal="Generate a synthetic UI test case",
        plan=(() if call is None else (call,)),
        budget=_budget(),
    )


def test_contract_models_are_strict_and_json_safe():
    state = _state(_call())
    restored = AgentRunState.model_validate_json(state.model_dump_json())

    assert restored == state
    assert state.model_config["extra"] == "forbid"
    for forbidden in (
        "prompt",
        "completion",
        "reasoning",
        "scratchpad",
        "document_body",
    ):
        assert forbidden not in type(state).model_fields

    with pytest.raises(ValidationError):
        AgentRunState.model_validate({**state.model_dump(), "reasoning": "hidden"})


@pytest.mark.parametrize(
    "forbidden_key",
    [
        "pid",
        "project_id",
        "user_id",
        "scope",
        "api_key",
        "authorization",
        "password",
        "prompt",
        "reasoning",
        "raw_document",
    ],
)
def test_model_tool_arguments_cannot_supply_scope_or_sensitive_payloads(
    forbidden_key,
):
    with pytest.raises(ValidationError, match="forbidden tool argument key"):
        _call(arguments={"info": "safe", forbidden_key: "not-allowed"})


def test_catalog_is_the_operation_source_of_truth():
    with pytest.raises(ValidationError, match="unknown workflow operation"):
        _call(operation="arbitrary_shell")


def test_workbench_and_loopback_mcp_can_share_one_catalog_derived_definition():
    definitions = typed_tool_definitions()

    assert len(definitions) == 19
    assert len({item.operation for item in definitions}) == 19
    assert typed_tool_definition_for("ui_case") == next(
        item for item in definitions if item.operation == "ui_case"
    )
    assert typed_tool_definition_for("ui_case").persistence == "artifact"
    assert typed_tool_definition_for("unit_case").persistence == "session"


def test_sensitive_assignments_are_redacted_before_safe_logging():
    assigned_key = "api_" + "key" + "=" + "synthetic-value"
    assert (
        redact_sensitive_text(f"provider {assigned_key} failed")
        == "provider api_key=[REDACTED] failed"
    )
    assert redact_sensitive_text("token budget exceeded") == "token budget exceeded"

    with pytest.raises(ValidationError, match="must be redacted"):
        AgentRunState(
            run_id="run-secret",
            thread_id="thread-secret",
            project_scope=_scope(),
            source_revision="revision-a",
            goal="debug password" + "=" + "synthetic-value",
            budget=_budget(),
        )


def test_risk_contract_requires_approval_for_every_side_effect():
    assert not requires_approval({ToolRisk.READ_ONLY})
    assert requires_approval({ToolRisk.PAID})
    assert requires_approval({ToolRisk.PERSISTENT})
    assert requires_approval(
        {ToolRisk.PAID, ToolRisk.PERSISTENT, ToolRisk.REGENERATE}
    )

    with pytest.raises(ValidationError, match="regenerate risk"):
        _call(risks={ToolRisk.REGENERATE})
    with pytest.raises(ValidationError, match="read_only risk"):
        _call(risks={ToolRisk.READ_ONLY, ToolRisk.PAID})


def test_approval_is_bound_to_exact_run_plan_scope_revision_call_and_budget():
    call = _call()
    state = _state(call).model_copy(update={"plan_version": 3})
    now = datetime(2026, 8, 27, tzinfo=UTC)
    approval = approval_binding_for(
        state,
        call,
        decision=ApprovalDecision.APPROVED,
        decided_at=now,
        expires_at=now + timedelta(minutes=5),
        nonce="approval-nonce-1",
    )

    assert approval_is_valid(state, call, approval, now=now)
    assert not approval_is_valid(
        state.model_copy(update={"source_revision": "revision-b"}),
        call,
        approval,
        now=now,
    )
    assert not approval_is_valid(
        state.model_copy(update={"project_scope": _scope("synthetic-beta")}),
        call,
        approval,
        now=now,
    )
    assert not approval_is_valid(
        state,
        call.model_copy(update={"model_label": "different-model"}),
        approval,
        now=now,
    )
    assert not approval_is_valid(
        state,
        call.model_copy(update={"arguments": {"info": "changed"}}),
        approval,
        now=now,
    )
    assert not approval_is_valid(
        state,
        call,
        approval,
        now=now + timedelta(minutes=6),
    )
