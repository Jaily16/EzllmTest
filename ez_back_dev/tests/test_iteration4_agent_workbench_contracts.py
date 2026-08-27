from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from service.agentContracts import AgentRunStatus, ToolRisk, UsageCounters
from service.agentWorkbenchContracts import (
    AgentApprovalView,
    AgentBudgetView,
    AgentBudgetPreset,
    AgentPlanStepView,
    AgentRunCreateRequest,
    AgentRunView,
    AgentStepEvidence,
    AgentTimelineEvent,
    budget_for_preset,
    public_capabilities,
)


def test_budget_presets_are_catalog_derived_and_bounded():
    focused = budget_for_preset(AgentBudgetPreset.FOCUSED)
    standard = budget_for_preset(AgentBudgetPreset.STANDARD)

    assert focused.max_steps == focused.max_tool_calls == 3
    assert focused.max_elapsed_ms == 20 * 60 * 1_000
    assert focused.max_model_calls == 12
    assert focused.max_embedding_calls == 6
    assert focused.max_input_tokens == 12 * 64_000
    assert focused.max_output_tokens == 12 * 12_288
    assert focused.max_estimated_cost_units == (
        focused.max_input_tokens + focused.max_output_tokens
    )

    assert standard.max_steps == standard.max_tool_calls == 8
    assert standard.max_elapsed_ms == 45 * 60 * 1_000
    assert standard.max_model_calls == 32
    assert standard.max_embedding_calls == 16


def test_create_request_accepts_only_public_model_and_budget_preset():
    request = AgentRunCreateRequest(
        goal="Generate UI coverage",
        model_label="GLM-4.7",
    )
    assert request.budget_preset is AgentBudgetPreset.FOCUSED

    for payload in (
        {"goal": "x", "model_label": "unknown"},
        {"goal": "x", "model_label": "GLM-4.7", "budget_preset": "custom"},
        {
            "goal": "x",
            "model_label": "GLM-4.7",
            "project_id": "forbidden",
        },
        {
            "goal": "x",
            "model_label": "GLM-4.7",
            "max_steps": 99,
        },
    ):
        with pytest.raises(ValidationError):
            AgentRunCreateRequest.model_validate(payload)


def test_public_views_are_strict_and_omit_runtime_authority():
    now = datetime.now(UTC)
    approval = AgentApprovalView(
        plan_hash="a" * 64,
        plan_version=1,
        step_id="step-1",
        operation="ui_case",
        risks=(ToolRisk.PAID, ToolRisk.PERSISTENT),
        expires_at=now,
        expired=False,
    )
    step = AgentPlanStepView(
        step_id="step-1",
        operation="ui_case",
        arguments={"info": "safe"},
        risks=(ToolRisk.PAID, ToolRisk.PERSISTENT),
        model_label="GLM-4.7",
        retention="artifact",
        current=True,
    )
    evidence = AgentStepEvidence(
        step_id="step-1",
        operation="ui_case",
        retention="artifact",
        status="success",
        saved=True,
        from_cache=False,
        source_revision="rev-1",
        artifact_key="ui_case",
        workspace_route="/ui",
        usage=UsageCounters(tool_calls=1),
    )
    view = AgentRunView(
        run_id="run-1",
        thread_id="thread-1",
        goal="Generate UI coverage",
        status=AgentRunStatus.AWAITING_APPROVAL,
        source_revision="rev-1",
        created_at=now,
        deadline_at=now,
        expires_at=now,
        model_label="GLM-4.7",
        budget=AgentBudgetView.from_usage(
            AgentBudgetPreset.FOCUSED, UsageCounters()
        ),
        plan_version=1,
        current_step_index=0,
        plan=(step,),
        approval=approval,
        evidence=(evidence,),
        last_event_sequence=1,
        worker_available=True,
        active=True,
        can_approve=True,
        can_edit=True,
        can_cancel=True,
        can_recover=False,
    )
    encoded = view.model_dump(mode="json")
    forbidden = {
        "actor_id",
        "scope_version",
        "scope_hash",
        "approval_binding",
        "nonce",
        "idempotency_key",
        "checkpoint",
        "prompt",
        "reasoning",
        "traceback",
    }
    assert forbidden.isdisjoint(str(encoded).lower())
    assert encoded["trace_id"] is None
    assert encoded["trace_status"] == "not_instrumented"


def test_timeline_and_session_evidence_reject_sensitive_result_keys():
    event = AgentTimelineEvent(
        sequence=1,
        kind="queued",
        occurred_at=datetime.now(UTC),
        status=AgentRunStatus.CREATED,
    )
    assert event.sequence == 1

    with pytest.raises(ValidationError):
        AgentStepEvidence(
            step_id="step-1",
            operation="unit_case",
            retention="session",
            status="success",
            session_result={"reasoning": "secret"},
            usage=UsageCounters(),
        )


def test_capabilities_publish_two_presets_and_no_trace_claim():
    capabilities = public_capabilities()
    assert [item["name"] for item in capabilities["budget_presets"]] == [
        "focused",
        "standard",
    ]
    assert capabilities["trace_status"] == "not_instrumented"
    assert capabilities["single_agent"] is True
    assert capabilities["chain_of_thought"] is False
