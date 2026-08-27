from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from service.agentContracts import (
    AgentRunStatus,
    ApprovalDecision,
    RunBudget,
    TrustedProjectScope,
)
from service.agentPlanner import DeterministicAgentPlanner, PlannerProposal
from service.agentRedisCoordinator import AgentRedisCoordinator, AgentRedisSettings
from service.agentRuntimeContracts import ProjectObservation
from service.agentRuntimeService import AgentRuntimeService
from service.agentToolSchemas import (
    ToolExecutionError,
    ToolExecutionResult,
    ToolExecutionStatus,
    ToolUsageSummary,
)


REDIS_URL = os.getenv("EZLLM_TEST_REDIS_URL")


def _budget() -> RunBudget:
    return RunBudget(
        max_steps=3,
        max_elapsed_ms=60_000,
        max_input_tokens=1_000,
        max_output_tokens=1_000,
        max_model_calls=3,
        max_embedding_calls=2,
        max_tool_calls=3,
        max_estimated_cost_units=1_000,
    )


class _Adapter:
    def __init__(self):
        self.calls: list[str] = []

    async def invoke(self, tool_name, arguments, context):
        self.calls.append(tool_name)
        return ToolExecutionResult(
            tool_name=tool_name,
            operation=tool_name.removeprefix("workflow_"),
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
                estimated_cost_units=5,
            ),
        )


def _service(lease_ttl_seconds: int = 10):
    if not REDIS_URL:
        pytest.skip("EZLLM_TEST_REDIS_URL is not configured")
    settings = AgentRedisSettings(
        url=REDIS_URL,
        prefix=f"ezllm:test:aspect3:runtime:{uuid4().hex}",
        lease_ttl_seconds=lease_ttl_seconds,
        lease_renew_seconds=1,
        event_ttl_seconds=60,
        state_ttl_seconds=60,
    )
    coordinator = AgentRedisCoordinator(settings)
    adapter = _Adapter()
    planner = DeterministicAgentPlanner(
        PlannerProposal.model_validate(
            {
                "steps": [
                    {
                        "tool_name": "workflow_ui_case",
                        "arguments": {"info": "synthetic ui"},
                    }
                ]
            }
        )
    )
    service = AgentRuntimeService(
        coordinator=coordinator,
        planner=planner,
        observer=lambda _scope: ProjectObservation(
            setup_stage="ready",
            analysis_ready=True,
            workflow_stage="analysis",
            source_revision="revision-1",
        ),
        tool_adapter=adapter,
        clock=lambda: datetime.now(UTC),
    )
    return service, coordinator, adapter


def test_runtime_start_hitl_approval_completion_and_event_replay():
    async def scenario():
        service, coordinator, adapter = _service()
        scope = TrustedProjectScope(
            project_id="project-a", actor_id="actor-a", scope_version="1"
        )
        try:
            handle = await service.create_run(
                scope,
                "Generate UI cases",
                planner_model="deterministic-planner",
                execution_model="fake-model",
                budget=_budget(),
            )
            await coordinator.ensure_command_group("workers")
            [start] = await coordinator.read_commands(
                "workers", "consumer-a", count=1, block_ms=10
            )
            paused = await service.process_command(start, owner="worker-a")
            assert paused.run_state.status is AgentRunStatus.AWAITING_APPROVAL
            assert adapter.calls == []
            await coordinator.ack_command("workers", start.stream_id)

            await service.approve_run(
                scope,
                handle.thread_id,
                ApprovalDecision.APPROVED,
                expected_plan_hash=paused.approval_request.plan_hash,
            )
            with pytest.raises(ValueError, match="already pending"):
                await service.approve_run(
                    scope,
                    handle.thread_id,
                    ApprovalDecision.APPROVED,
                    expected_plan_hash=paused.approval_request.plan_hash,
                )
            [resume] = await coordinator.read_commands(
                "workers", "consumer-a", count=1, block_ms=10
            )
            completed = await service.process_command(resume, owner="worker-a")
            assert completed.run_state.status is AgentRunStatus.COMPLETED
            assert adapter.calls == ["workflow_ui_case"]
            await service.process_command(resume, owner="worker-b")
            assert adapter.calls == ["workflow_ui_case"]

            loaded = await service.get_run(scope, handle.thread_id)
            assert loaded == completed
            other_scope = scope.model_copy(update={"project_id": "project-b"})
            assert await service.get_run(other_scope, handle.thread_id) is None
            events = await service.replay_events(scope, handle.thread_id, 0)
            assert [event.kind for event in events] == [
                "run_created",
                "awaiting_approval",
                "completed",
            ]
        finally:
            await coordinator.delete_test_namespace()
            await coordinator.aclose()

    asyncio.run(scenario())


def test_cancel_is_observed_before_the_approved_side_effect():
    async def scenario():
        service, coordinator, adapter = _service()
        scope = TrustedProjectScope(
            project_id="project-a", actor_id="actor-a", scope_version="1"
        )
        try:
            handle = await service.create_run(
                scope,
                "Generate UI cases",
                planner_model="deterministic-planner",
                execution_model="fake-model",
                budget=_budget(),
            )
            await coordinator.ensure_command_group("workers")
            [start] = await coordinator.read_commands(
                "workers", "consumer-a", count=1, block_ms=10
            )
            paused = await service.process_command(start, owner="worker-a")
            await coordinator.ack_command("workers", start.stream_id)
            await service.cancel_run(scope, handle.thread_id)
            await service.approve_run(
                scope,
                handle.thread_id,
                ApprovalDecision.APPROVED,
                expected_plan_hash=paused.approval_request.plan_hash,
            )
            [resume] = await coordinator.read_commands(
                "workers", "consumer-a", count=1, block_ms=10
            )
            cancelled = await service.process_command(resume, owner="worker-a")
            assert cancelled.run_state.status is AgentRunStatus.CANCELLED
            assert adapter.calls == []
        finally:
            await coordinator.delete_test_namespace()
            await coordinator.aclose()

    asyncio.run(scenario())


def test_worker_renews_the_fenced_lease_during_a_long_tool_call():
    async def scenario():
        service, coordinator, adapter = _service(lease_ttl_seconds=2)
        original = adapter.invoke

        async def slow_invoke(*args, **kwargs):
            await asyncio.sleep(2.2)
            return await original(*args, **kwargs)

        adapter.invoke = slow_invoke
        scope = TrustedProjectScope(
            project_id="project-a", actor_id="actor-a", scope_version="1"
        )
        try:
            handle = await service.create_run(
                scope,
                "Generate UI cases",
                planner_model="deterministic-planner",
                execution_model="fake-model",
                budget=_budget(),
            )
            await coordinator.ensure_command_group("workers")
            [start] = await coordinator.read_commands(
                "workers", "consumer-a", count=1, block_ms=10
            )
            paused = await service.process_command(start, owner="worker-a")
            await coordinator.ack_command("workers", start.stream_id)
            await service.approve_run(
                scope,
                handle.thread_id,
                ApprovalDecision.APPROVED,
                expected_plan_hash=paused.approval_request.plan_hash,
            )
            [resume] = await coordinator.read_commands(
                "workers", "consumer-a", count=1, block_ms=10
            )
            completed = await service.process_command(resume, owner="worker-a")
            assert completed.run_state.status is AgentRunStatus.COMPLETED
            assert adapter.calls == ["workflow_ui_case"]
        finally:
            await coordinator.delete_test_namespace()
            await coordinator.aclose()

    asyncio.run(scenario())


def test_retryable_failure_recovery_reconciles_before_new_approval():
    async def scenario():
        service, coordinator, adapter = _service()

        async def retryable_failure(tool_name, _arguments, _context):
            adapter.calls.append(tool_name)
            return ToolExecutionResult(
                tool_name=tool_name,
                operation="ui_case",
                status=ToolExecutionStatus.ERROR,
                error=ToolExecutionError(
                    code="temporary_failure",
                    category="transient",
                    retryable=True,
                    safe_message="Temporary failure",
                ),
            )

        adapter.invoke = retryable_failure
        scope = TrustedProjectScope(
            project_id="project-a", actor_id="actor-a", scope_version="1"
        )
        try:
            handle = await service.create_run(
                scope,
                "Generate UI cases",
                planner_model="deterministic-planner",
                execution_model="fake-model",
                budget=_budget(),
            )
            await coordinator.ensure_command_group("workers")
            [start] = await coordinator.read_commands(
                "workers", "consumer-a", count=1, block_ms=10
            )
            paused = await service.process_command(start, owner="worker-a")
            await coordinator.ack_command("workers", start.stream_id)
            await service.approve_run(
                scope,
                handle.thread_id,
                ApprovalDecision.APPROVED,
                expected_plan_hash=paused.approval_request.plan_hash,
            )
            [resume] = await coordinator.read_commands(
                "workers", "consumer-a", count=1, block_ms=10
            )
            failed = await service.process_command(resume, owner="worker-a")
            assert failed.run_state.status is AgentRunStatus.FAILED
            await coordinator.ack_command("workers", resume.stream_id)

            await service.recover_run(scope, handle.thread_id)
            [recover] = await coordinator.read_commands(
                "workers", "consumer-b", count=1, block_ms=10
            )
            reconciled = await service.process_command(
                recover, owner="worker-b"
            )
            assert reconciled.run_state.status is AgentRunStatus.AWAITING_APPROVAL
            assert reconciled.run_state.recovery_from_checkpoint == "redis-recovery"
            assert adapter.calls == ["workflow_ui_case"]
        finally:
            await coordinator.delete_test_namespace()
            await coordinator.aclose()

    asyncio.run(scenario())
