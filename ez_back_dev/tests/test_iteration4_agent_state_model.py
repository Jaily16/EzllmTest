from datetime import UTC, datetime, timedelta

import pytest

from service.agentContracts import (
    AgentError,
    AgentRunState,
    AgentRunStatus,
    AgentTransitionEvent,
    ApprovalDecision,
    PlannedToolCall,
    RunBudget,
    ToolRisk,
    TransitionKind,
    TrustedProjectScope,
    UsageCounters,
    approval_binding_for,
    transition,
)


NOW = datetime(2026, 8, 27, tzinfo=UTC)


def _budget(max_tool_calls: int = 4) -> RunBudget:
    return RunBudget(
        max_steps=4,
        max_elapsed_ms=30_000,
        max_input_tokens=10_000,
        max_output_tokens=5_000,
        max_model_calls=4,
        max_embedding_calls=2,
        max_tool_calls=max_tool_calls,
        max_estimated_cost_units=1_000,
    )


def _call(read_only: bool = False) -> PlannedToolCall:
    return PlannedToolCall(
        step_id="step-1",
        operation="project_analysis" if read_only else "ui_case",
        arguments={} if read_only else {"info": "synthetic"},
        risks={ToolRisk.READ_ONLY}
        if read_only
        else {ToolRisk.PAID, ToolRisk.PERSISTENT},
        idempotency_key="run-1:plan-1:step-1",
        model_label="deterministic-fake",
    )


def _created() -> AgentRunState:
    return AgentRunState(
        run_id="run-1",
        thread_id="thread-1",
        project_scope=TrustedProjectScope(
            project_id="synthetic-alpha",
            actor_id="offline-evaluator",
            scope_version="scope-v1",
        ),
        source_revision="revision-a",
        goal="Synthetic goal",
        budget=_budget(),
    )


def _planned(call: PlannedToolCall) -> AgentRunState:
    state = transition(
        _created(), AgentTransitionEvent(kind=TransitionKind.START_PLANNING)
    )
    return transition(
        state,
        AgentTransitionEvent(kind=TransitionKind.PLAN_READY, plan=(call,)),
    )


def test_read_only_happy_path_reaches_completion_without_approval():
    state = _planned(_call(read_only=True))
    assert state.status == AgentRunStatus.EXECUTING

    state = transition(
        state, AgentTransitionEvent(kind=TransitionKind.TOOL_STARTED)
    )
    state = transition(
        state,
        AgentTransitionEvent(
            kind=TransitionKind.TOOL_SUCCEEDED,
            usage=UsageCounters(tool_calls=1, elapsed_ms=10),
            side_effect_committed=False,
        ),
    )
    state = transition(
        state,
        AgentTransitionEvent(kind=TransitionKind.VALIDATION_SUCCEEDED),
    )
    assert state.status == AgentRunStatus.COMPLETED


def test_paid_or_persistent_step_cannot_execute_without_exact_approval():
    call = _call()
    state = _planned(call)
    assert state.status == AgentRunStatus.AWAITING_APPROVAL

    with pytest.raises(ValueError, match="illegal transition"):
        transition(state, AgentTransitionEvent(kind=TransitionKind.TOOL_STARTED))

    approval = approval_binding_for(
        state,
        call,
        decision=ApprovalDecision.APPROVED,
        decided_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
        nonce="approval-1",
    )
    state = transition(
        state,
        AgentTransitionEvent(
            kind=TransitionKind.APPROVED,
            approval=approval,
            occurred_at=NOW,
        ),
    )
    assert state.status == AgentRunStatus.EXECUTING


def test_plan_edit_stale_and_cancel_invalidate_approval_or_execution():
    call = _call()
    state = _planned(call)
    approval = approval_binding_for(
        state,
        call,
        decision=ApprovalDecision.APPROVED,
        decided_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
        nonce="approval-1",
    )

    edited = transition(
        state, AgentTransitionEvent(kind=TransitionKind.PLAN_EDITED)
    )
    assert edited.status == AgentRunStatus.PLANNING
    assert edited.plan_version == state.plan_version + 1
    assert edited.pending_approval is None

    stale = transition(
        state, AgentTransitionEvent(kind=TransitionKind.STALE_DETECTED)
    )
    assert stale.status == AgentRunStatus.PLANNING
    assert stale.pending_approval is None

    executing = transition(
        state,
        AgentTransitionEvent(
            kind=TransitionKind.APPROVED,
            approval=approval,
            occurred_at=NOW,
        ),
    )
    cancelled = transition(
        executing, AgentTransitionEvent(kind=TransitionKind.CANCEL_REQUESTED)
    )
    assert cancelled.status == AgentRunStatus.CANCELLED
    with pytest.raises(ValueError, match="terminal state"):
        transition(
            cancelled, AgentTransitionEvent(kind=TransitionKind.TOOL_STARTED)
        )


def test_budget_is_monotonic_and_exhaustion_blocks_the_next_side_effect():
    state = _planned(_call(read_only=True))
    with pytest.raises(ValueError, match="usage counters must be monotonic"):
        transition(
            state.model_copy(
                update={"usage": UsageCounters(tool_calls=1, elapsed_ms=5)}
            ),
            AgentTransitionEvent(
                kind=TransitionKind.TOOL_SUCCEEDED,
                usage=UsageCounters(tool_calls=0, elapsed_ms=6),
            ),
        )

    with pytest.raises(ValueError, match="budget exceeded"):
        transition(
            state,
            AgentTransitionEvent(
                kind=TransitionKind.TOOL_SUCCEEDED,
                usage=UsageCounters(tool_calls=5, elapsed_ms=10),
            ),
        )


def test_retryable_failure_recovers_by_reconciling_idempotency_first():
    call = _call(read_only=True)
    state = _planned(call)
    state = transition(
        state, AgentTransitionEvent(kind=TransitionKind.TOOL_STARTED)
    )
    failed = transition(
        state,
        AgentTransitionEvent(
            kind=TransitionKind.TOOL_FAILED,
            error=AgentError(
                code="checkpoint_interrupted",
                category="transient",
                retryable=True,
                safe_message="Execution interrupted",
            ),
        ),
    )
    recovering = transition(
        failed,
        AgentTransitionEvent(
            kind=TransitionKind.RECOVERY_STARTED,
            checkpoint_id="checkpoint-1",
        ),
    )
    reconciled = transition(
        recovering,
        AgentTransitionEvent(
            kind=TransitionKind.RECOVERY_RECONCILED,
            side_effect_committed=True,
        ),
    )

    assert failed.status == AgentRunStatus.FAILED
    assert recovering.status == AgentRunStatus.RECOVERING
    assert reconciled.status == AgentRunStatus.VALIDATING
    assert reconciled.recovery_from_checkpoint == "checkpoint-1"
    assert len(reconciled.tool_attempts) == 1


@pytest.mark.parametrize(
    ("status", "kind"),
    [
        (AgentRunStatus.CREATED, TransitionKind.TOOL_STARTED),
        (AgentRunStatus.PLANNING, TransitionKind.APPROVED),
        (AgentRunStatus.AWAITING_APPROVAL, TransitionKind.TOOL_SUCCEEDED),
        (AgentRunStatus.VALIDATING, TransitionKind.TOOL_STARTED),
        (AgentRunStatus.FAILED, TransitionKind.PLAN_READY),
    ],
)
def test_illegal_status_event_pairs_are_rejected(status, kind):
    state = _created().model_copy(update={"status": status})
    with pytest.raises(ValueError, match="illegal transition"):
        transition(state, AgentTransitionEvent(kind=kind))
