import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from service.agentCheckpoint import (
    AsyncAgentRedisCheckpointSaver,
    StrictAgentCheckpointSerializer,
    derive_agent_scope_hash,
)
from service.agentContracts import (
    AgentError,
    AgentRunState,
    AgentRunStatus,
    AgentTransitionEvent,
    ApprovalDecision,
    RunBudget,
    TrustedProjectScope,
    TransitionKind,
    approval_binding_for,
    transition,
)
from service.agentGraph import build_agent_graph, graph_plan_hash
from service.agentPlanner import DeterministicAgentPlanner, PlannerProposal
from service.agentRedisCoordinator import AgentRedisCoordinator, AgentRedisSettings
from service.agentRuntimeContracts import (
    AgentGraphEnvelope,
    ApprovalResume,
    ProjectObservation,
)
from service.agentToolSchemas import (
    ToolExecutionResult,
    ToolExecutionStatus,
    ToolUsageSummary,
)


FIXED_NOW = datetime(2026, 8, 27, tzinfo=UTC)


def _envelope() -> AgentGraphEnvelope:
    state = AgentRunState(
        run_id="run-graph",
        thread_id="thread-graph",
        project_scope=TrustedProjectScope(
            project_id="project-a", actor_id="actor-a", scope_version="1"
        ),
        source_revision="revision-1",
        goal="Generate UI test cases",
        budget=RunBudget(
            max_steps=3,
            max_elapsed_ms=60_000,
            max_input_tokens=2_000,
            max_output_tokens=2_000,
            max_model_calls=3,
            max_embedding_calls=2,
            max_tool_calls=3,
            max_estimated_cost_units=10_000,
        ),
    )
    return AgentGraphEnvelope(
        run_state=state,
        started_at=FIXED_NOW,
        deadline_at=FIXED_NOW + timedelta(minutes=1),
        planner_model="deterministic-fake",
        execution_model="deterministic-fake",
    )


def _planner():
    return DeterministicAgentPlanner(
        PlannerProposal.model_validate(
            {
                "steps": [
                    {
                        "tool_name": "workflow_ui_case",
                        "arguments": {"info": "synthetic UI summary"},
                    }
                ]
            }
        )
    )


class _FakeAdapter:
    def __init__(self):
        self.calls = []

    async def invoke(self, tool_name, arguments, context):
        self.calls.append((tool_name, arguments, context.project_scope.project_id))
        return ToolExecutionResult(
            tool_name=tool_name,
            operation="ui_case",
            status=ToolExecutionStatus.SUCCESS,
            data={"cases": [{"name": "synthetic"}]},
            saved=True,
            source_revision="revision-1",
            artifact_key="ui_case",
            usage=ToolUsageSummary(
                input_tokens=10,
                output_tokens=20,
                model_calls=1,
                embedding_calls=0,
                tool_calls=1,
                estimated_cost_units=30,
            ),
        )


class _MultiStepAdapter:
    def __init__(self):
        self.calls = []

    async def invoke(self, tool_name, arguments, context):
        operation = tool_name.removeprefix("workflow_")
        self.calls.append(operation)
        return ToolExecutionResult(
            tool_name=tool_name,
            operation=operation,
            status=ToolExecutionStatus.SUCCESS,
            data={"status": "synthetic"},
            saved=True,
            source_revision="revision-1",
            artifact_key=operation,
            usage=ToolUsageSummary(
                input_tokens=10,
                output_tokens=20,
                model_calls=1,
                embedding_calls=0,
                tool_calls=1,
                estimated_cost_units=30,
            ),
        )


async def _observe(_scope):
    return ProjectObservation(
        setup_stage="setup_complete",
        analysis_ready=True,
        workflow_stage="analysis_ready",
        source_revision="revision-1",
    )


def _compiled(adapter):
    return build_agent_graph(
        observer=_observe,
        planner=_planner(),
        tool_adapter=adapter,
        checkpointer=InMemorySaver(),
        clock=lambda: FIXED_NOW,
    )


def test_graph_interrupts_for_approval_then_executes_exactly_once():
    adapter = _FakeAdapter()
    graph = _compiled(adapter)
    config = {"configurable": {"thread_id": "graph-approved"}}

    first = asyncio.run(
        graph.ainvoke(
            {"envelope": _envelope().model_dump(mode="json")},
            config,
            durability="sync",
        )
    )
    assert adapter.calls == []
    assert first["__interrupt__"]
    paused = AgentGraphEnvelope.model_validate(first["envelope"])
    assert paused.run_state.status is AgentRunStatus.AWAITING_APPROVAL
    assert paused.approval_request is not None
    assert paused.approval_request.plan_hash == graph_plan_hash(paused.run_state)
    StrictAgentCheckpointSerializer().dumps_typed(first)

    call = paused.run_state.plan[0]
    binding = approval_binding_for(
        paused.run_state,
        call,
        decision=ApprovalDecision.APPROVED,
        decided_at=FIXED_NOW,
        expires_at=FIXED_NOW + timedelta(minutes=10),
        nonce="trusted-nonce",
    )
    resumed = asyncio.run(
        graph.ainvoke(
            Command(
                resume=ApprovalResume(
                    decision=ApprovalDecision.APPROVED,
                    expected_plan_hash=paused.approval_request.plan_hash,
                    binding=binding,
                ).model_dump(mode="json")
            ),
            config,
            durability="sync",
        )
    )
    completed = AgentGraphEnvelope.model_validate(resumed["envelope"])
    assert completed.run_state.status is AgentRunStatus.COMPLETED
    assert len(adapter.calls) == 1
    assert adapter.calls[0][0] == "workflow_ui_case"
    assert adapter.calls[0][2] == "project-a"

    terminal = asyncio.run(
        graph.ainvoke(
            Command(resume={"decision": "approved"}),
            config,
            durability="sync",
        )
    )
    assert AgentGraphEnvelope.model_validate(
        terminal["envelope"]
    ).run_state.status is AgentRunStatus.COMPLETED
    assert len(adapter.calls) == 1


def test_graph_advances_a_frozen_multistep_plan_without_replanning():
    adapter = _MultiStepAdapter()
    planner = DeterministicAgentPlanner(
        PlannerProposal.model_validate(
            {
                "steps": [
                    {"tool_name": "workflow_ui_info", "arguments": {}},
                    {"tool_name": "workflow_ui_case", "arguments": {}},
                ]
            }
        )
    )
    graph = build_agent_graph(
        observer=_observe,
        planner=planner,
        tool_adapter=adapter,
        checkpointer=InMemorySaver(),
        clock=lambda: FIXED_NOW,
    )
    config = {"configurable": {"thread_id": "graph-multistep"}}

    first = asyncio.run(
        graph.ainvoke(
            {"envelope": _envelope().model_dump(mode="json")},
            config,
            durability="sync",
        )
    )
    first_paused = AgentGraphEnvelope.model_validate(first["envelope"])
    assert first_paused.approval_request.operation == "ui_info"

    first_call = first_paused.run_state.plan[0]
    first_binding = approval_binding_for(
        first_paused.run_state,
        first_call,
        decision=ApprovalDecision.APPROVED,
        decided_at=FIXED_NOW,
        expires_at=FIXED_NOW + timedelta(minutes=10),
        nonce="trusted-nonce-1",
    )
    second = asyncio.run(
        graph.ainvoke(
            Command(
                resume=ApprovalResume(
                    decision=ApprovalDecision.APPROVED,
                    expected_plan_hash=first_paused.approval_request.plan_hash,
                    binding=first_binding,
                ).model_dump(mode="json")
            ),
            config,
            durability="sync",
        )
    )
    second_paused = AgentGraphEnvelope.model_validate(second["envelope"])
    assert second_paused.run_state.current_step_index == 1
    assert second_paused.approval_request.operation == "ui_case"
    assert [call.operation for call in second_paused.run_state.plan] == [
        "ui_info",
        "ui_case",
    ]
    assert adapter.calls == ["ui_info"]

    second_call = second_paused.run_state.plan[1]
    second_binding = approval_binding_for(
        second_paused.run_state,
        second_call,
        decision=ApprovalDecision.APPROVED,
        decided_at=FIXED_NOW,
        expires_at=FIXED_NOW + timedelta(minutes=10),
        nonce="trusted-nonce-2",
    )
    completed = asyncio.run(
        graph.ainvoke(
            Command(
                resume=ApprovalResume(
                    decision=ApprovalDecision.APPROVED,
                    expected_plan_hash=second_paused.approval_request.plan_hash,
                    binding=second_binding,
                ).model_dump(mode="json")
            ),
            config,
            durability="sync",
        )
    )
    terminal = AgentGraphEnvelope.model_validate(completed["envelope"])
    assert terminal.run_state.status is AgentRunStatus.COMPLETED
    assert adapter.calls == ["ui_info", "ui_case"]


def test_graph_rejection_cancels_without_tool_execution():
    adapter = _FakeAdapter()
    graph = _compiled(adapter)
    config = {"configurable": {"thread_id": "graph-rejected"}}
    first = asyncio.run(
        graph.ainvoke(
            {"envelope": _envelope().model_dump(mode="json")}, config
        )
    )
    paused = AgentGraphEnvelope.model_validate(first["envelope"])
    result = asyncio.run(
        graph.ainvoke(
            Command(
                resume=ApprovalResume(
                    decision=ApprovalDecision.REJECTED,
                    expected_plan_hash=paused.approval_request.plan_hash,
                ).model_dump(mode="json")
            ),
            config,
        )
    )
    assert AgentGraphEnvelope.model_validate(result["envelope"]).run_state.status is AgentRunStatus.CANCELLED
    assert adapter.calls == []


def test_graph_rejects_mismatched_plan_hash_before_tool_execution():
    adapter = _FakeAdapter()
    graph = _compiled(adapter)
    config = {"configurable": {"thread_id": "graph-mismatch"}}
    first = asyncio.run(
        graph.ainvoke(
            {"envelope": _envelope().model_dump(mode="json")}, config
        )
    )
    paused = AgentGraphEnvelope.model_validate(first["envelope"])
    call = paused.run_state.plan[0]
    binding = approval_binding_for(
        paused.run_state,
        call,
        decision=ApprovalDecision.APPROVED,
        decided_at=FIXED_NOW,
        expires_at=FIXED_NOW + timedelta(minutes=10),
        nonce="trusted-nonce",
    )

    with pytest.raises(ValueError, match="plan hash"):
        asyncio.run(
            graph.ainvoke(
                Command(
                    resume=ApprovalResume(
                        decision=ApprovalDecision.APPROVED,
                        expected_plan_hash="f" * 64,
                        binding=binding,
                    ).model_dump(mode="json")
                ),
                config,
            )
        )
    assert adapter.calls == []


def test_graph_has_the_frozen_single_agent_node_set():
    graph = _compiled(_FakeAdapter())
    assert {
        "observe",
        "plan",
        "validate_plan",
        "request_approval",
        "await_approval",
        "execute",
        "validate_result",
        "advance",
        "complete",
        "fail",
        "recover",
        "reconcile",
    }.issubset(graph.get_graph().nodes)


def test_graph_interrupt_and_resume_round_trip_through_safe_redis_saver():
    redis_url = os.getenv("EZLLM_TEST_REDIS_URL")
    if not redis_url:
        pytest.skip("local Redis integration gate is not enabled")

    async def scenario():
        prefix = f"ezllm:test:aspect3:graph:{uuid4().hex}"
        settings = AgentRedisSettings(
            url=redis_url,
            prefix=prefix,
            lease_ttl_seconds=10,
            lease_renew_seconds=1,
            state_ttl_seconds=60,
        )
        coordinator = AgentRedisCoordinator(settings)
        adapter = _FakeAdapter()
        envelope = _envelope()
        scope_hash = derive_agent_scope_hash(
            envelope.run_state.project_scope, envelope.graph_version
        )
        lease = await coordinator.acquire_lease(
            scope_hash,
            envelope.graph_version,
            envelope.run_state.thread_id,
            "worker-a",
        )
        assert lease is not None
        saver = AsyncAgentRedisCheckpointSaver(
            coordinator.redis,
            scope_hash=scope_hash,
            graph_version=envelope.graph_version,
            lease_owner=lease.owner,
            fence_token=lease.fence,
            prefix=f"{prefix}:checkpoint",
            coordination_prefix=prefix,
            ttl_seconds=60,
        )
        graph = build_agent_graph(
            observer=lambda _scope: ProjectObservation(
                setup_stage="ready",
                analysis_ready=True,
                workflow_stage="analysis",
                source_revision="revision-1",
            ),
            planner=DeterministicAgentPlanner(
                PlannerProposal.model_validate(
                    {
                        "steps": [
                            {
                                "tool_name": "workflow_ui_case",
                                "arguments": {
                                    "info": "synthetic ui",
                                    "regenerate": False,
                                },
                            }
                        ]
                    }
                )
            ),
            tool_adapter=adapter,
            checkpointer=saver,
            clock=lambda: FIXED_NOW,
        )
        config = saver.runtime_config(lease.storage_id)
        try:
            first = await graph.ainvoke(
                {"envelope": envelope.model_dump(mode="json")},
                config,
                durability="sync",
            )
            paused = AgentGraphEnvelope.model_validate(first["envelope"])
            call = paused.run_state.plan[0]
            binding = approval_binding_for(
                paused.run_state,
                call,
                decision=ApprovalDecision.APPROVED,
                decided_at=FIXED_NOW,
                expires_at=FIXED_NOW + timedelta(minutes=10),
                nonce="redis-approved-nonce",
            )
            resumed = await graph.ainvoke(
                Command(
                    resume=ApprovalResume(
                        decision=ApprovalDecision.APPROVED,
                        expected_plan_hash=paused.approval_request.plan_hash,
                        binding=binding,
                    ).model_dump(mode="json")
                ),
                config,
                durability="sync",
            )
            assert AgentGraphEnvelope.model_validate(
                resumed["envelope"]
            ).run_state.status is AgentRunStatus.COMPLETED
            assert len(adapter.calls) == 1
        finally:
            await coordinator.delete_test_namespace()
            await coordinator.aclose()

    asyncio.run(scenario())


def test_retryable_failure_reconciles_before_requesting_new_approval():
    adapter = _FakeAdapter()
    graph = _compiled(adapter)
    seed_config = {"configurable": {"thread_id": "recovery-seed"}}
    first = asyncio.run(
        graph.ainvoke(
            {"envelope": _envelope().model_dump(mode="json")}, seed_config
        )
    )
    paused = AgentGraphEnvelope.model_validate(first["envelope"])
    binding = approval_binding_for(
        paused.run_state,
        paused.run_state.plan[0],
        decision=ApprovalDecision.APPROVED,
        decided_at=FIXED_NOW,
        expires_at=FIXED_NOW + timedelta(minutes=10),
        nonce="recovery-seed",
    )
    executing = transition(
        paused.run_state,
        AgentTransitionEvent(
            kind=TransitionKind.APPROVED,
            approval=binding,
            occurred_at=FIXED_NOW,
        ),
    )
    executing = transition(
        executing,
        AgentTransitionEvent(
            kind=TransitionKind.TOOL_STARTED, occurred_at=FIXED_NOW
        ),
    )
    failed = transition(
        executing,
        AgentTransitionEvent(
            kind=TransitionKind.TOOL_FAILED,
            error=AgentError(
                code="worker_interrupted",
                category="transient",
                retryable=True,
                safe_message="Worker interrupted",
            ),
            occurred_at=FIXED_NOW,
        ),
    )
    recovery_input = paused.model_copy(
        update={
            "run_state": failed,
            "recovery_requested": True,
            "safe_runtime_data": {
                "checkpoint_id": "checkpoint-1",
                "reconciled_side_effect": False,
            },
        }
    )
    recovered = asyncio.run(
        graph.ainvoke(
            {"envelope": recovery_input.model_dump(mode="json")},
            {"configurable": {"thread_id": "recovery-run"}},
        )
    )
    state = AgentGraphEnvelope.model_validate(recovered["envelope"])
    assert state.run_state.status is AgentRunStatus.AWAITING_APPROVAL
    assert state.run_state.recovery_from_checkpoint == "checkpoint-1"
    assert state.approval_request is not None
    assert adapter.calls == []
