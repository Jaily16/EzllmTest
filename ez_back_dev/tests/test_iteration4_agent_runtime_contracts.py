from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from service.agentContracts import (
    AgentRunState,
    ApprovalDecision,
    RunBudget,
    TrustedProjectScope,
)
from service.agentRuntimeContracts import (
    AGENT_GRAPH_VERSION,
    AgentGraphEnvelope,
    ApprovalRequest,
    ApprovalResume,
    ProjectObservation,
)


def _state() -> AgentRunState:
    return AgentRunState(
        run_id="run-1",
        thread_id="thread-1",
        project_scope=TrustedProjectScope(
            project_id="project-a", actor_id="actor-a", scope_version="1"
        ),
        source_revision="revision-1",
        goal="Generate UI test cases",
        budget=RunBudget(
            max_steps=4,
            max_elapsed_ms=60_000,
            max_input_tokens=2_000,
            max_output_tokens=2_000,
            max_model_calls=4,
            max_embedding_calls=2,
            max_tool_calls=4,
            max_estimated_cost_units=10_000,
        ),
    )


def test_agent_graph_envelope_is_strict_json_without_cot_fields():
    started = datetime(2026, 8, 27, tzinfo=UTC)
    envelope = AgentGraphEnvelope(
        run_state=_state(),
        started_at=started,
        deadline_at=started + timedelta(minutes=1),
        planner_model="deterministic-fake",
        execution_model="deterministic-fake",
        observation=ProjectObservation(
            setup_stage="setup_complete",
            analysis_ready=True,
            workflow_stage="analysis_ready",
            completed_operations=(),
            stale_operations=(),
            source_revision="revision-1",
        ),
    )

    payload = envelope.model_dump(mode="json")
    serialized = envelope.model_dump_json()
    assert payload["graph_version"] == AGENT_GRAPH_VERSION
    for forbidden in (
        "prompt",
        "completion",
        "reasoning",
        "scratchpad",
        "document_body",
        "traceback",
    ):
        assert forbidden not in serialized.lower()

    with pytest.raises(ValidationError):
        AgentGraphEnvelope.model_validate({**payload, "reasoning": "hidden"})


def test_agent_graph_deadline_and_revision_must_match_trusted_state():
    started = datetime(2026, 8, 27, tzinfo=UTC)
    with pytest.raises(ValidationError):
        AgentGraphEnvelope(
            run_state=_state(),
            started_at=started,
            deadline_at=started,
            planner_model="fake",
            execution_model="fake",
        )
    with pytest.raises(ValidationError):
        AgentGraphEnvelope(
            run_state=_state(),
            started_at=started,
            deadline_at=started + timedelta(seconds=1),
            planner_model="fake",
            execution_model="fake",
            observation=ProjectObservation(
                setup_stage="setup_complete",
                analysis_ready=True,
                workflow_stage="analysis_ready",
                source_revision="other-revision",
            ),
        )


def test_approval_resume_carries_only_host_validated_decision_and_binding():
    request = ApprovalRequest(
        run_id="run-1",
        plan_hash="a" * 64,
        plan_version=1,
        step_id="step-1",
        operation="ui_case",
        risks=("paid", "persistent"),
        expires_at=datetime(2026, 8, 27, 0, 15, tzinfo=UTC),
    )
    resume = ApprovalResume(
        decision=ApprovalDecision.REJECTED,
        expected_plan_hash=request.plan_hash,
    )
    assert resume.decision is ApprovalDecision.REJECTED
    with pytest.raises(ValidationError):
        ApprovalResume.model_validate(
            {
                "decision": "approved",
                "expected_plan_hash": request.plan_hash,
                "project_id": "model-supplied",
            }
        )
