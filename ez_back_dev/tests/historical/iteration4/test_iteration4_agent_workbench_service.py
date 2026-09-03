from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from service.agentContracts import ApprovalDecision, TrustedProjectScope
from service.agentPlanner import DeterministicAgentPlanner, PlannerProposal
from service.agentRedisCoordinator import AgentRedisCoordinator, AgentRedisSettings
from service.agentRuntimeContracts import ProjectObservation
from service.agentRuntimeService import AgentRuntimeService
from service.agentToolSchemas import (
    ToolExecutionResult,
    ToolExecutionStatus,
    ToolUsageSummary,
)
from service.agentWorkbenchContracts import (
    AgentBudgetPreset,
    AgentRunCreateRequest,
)
from service.agentWorkbenchService import (
    AgentRunConflict,
    AgentWorkbenchService,
)
from service.agentWorkbenchStore import AgentWorkbenchStore


REDIS_URL = os.getenv("EZLLM_TEST_REDIS_URL")


class _Adapter:
    def __init__(self):
        self.calls = 0

    async def invoke(self, tool_name, arguments, context):
        self.calls += 1
        return ToolExecutionResult(
            tool_name=tool_name,
            operation="ui_case",
            status=ToolExecutionStatus.SUCCESS,
            data={"cases": [{"name": "synthetic UI"}]},
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


def _services():
    if not REDIS_URL:
        pytest.skip("EZLLM_TEST_REDIS_URL is not configured")
    coordinator = AgentRedisCoordinator(
        AgentRedisSettings(
            url=REDIS_URL,
            prefix=f"ezllm:test:aspect4:service:{uuid4().hex}",
            lease_ttl_seconds=10,
            lease_renew_seconds=1,
            event_ttl_seconds=60,
            state_ttl_seconds=60,
        )
    )
    store = AgentWorkbenchStore(coordinator)
    adapter = _Adapter()
    runtime = AgentRuntimeService(
        coordinator=coordinator,
        planner=DeterministicAgentPlanner(
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
        ),
        observer=lambda _scope: ProjectObservation(
            setup_stage="setup_complete",
            analysis_ready=True,
            workflow_stage="analysis_ready",
            source_revision="revision-1",
        ),
        tool_adapter=adapter,
        workbench_store=store,
    )
    return AgentWorkbenchService(runtime, store), runtime, coordinator, adapter


async def _next_command(runtime, coordinator, owner="worker-a"):
    await coordinator.ensure_command_group("aspect4-workers")
    commands = await coordinator.read_commands(
        "aspect4-workers", owner, count=1, block_ms=50
    )
    assert len(commands) == 1
    result = await runtime.process_command(commands[0], owner=owner)
    await coordinator.ack_command("aspect4-workers", commands[0].stream_id)
    return result


def test_create_single_active_approve_complete_and_project_scoped_history():
    async def scenario():
        service, runtime, coordinator, adapter = _services()
        scope = TrustedProjectScope(
            project_id="project-a",
            actor_id="local-workbench",
            scope_version="iteration4-aspect4-v1",
        )
        other = scope.model_copy(update={"project_id": "project-b"})
        try:
            handle = await service.create_run(
                scope,
                AgentRunCreateRequest(
                    goal="Generate UI tests",
                    model_label="GLM-4.7",
                    budget_preset=AgentBudgetPreset.FOCUSED,
                ),
            )
            with pytest.raises(AgentRunConflict):
                await service.create_run(
                    scope,
                    AgentRunCreateRequest(
                        goal="Second run",
                        model_label="GLM-4.7",
                    ),
                )
            assert await service.get_run(other, handle.thread_id) is None

            await _next_command(runtime, coordinator)
            awaiting = await service.get_run(scope, handle.thread_id)
            assert awaiting is not None and awaiting.can_approve
            assert awaiting.approval is not None

            await service.decide_approval(
                scope,
                handle.thread_id,
                ApprovalDecision.APPROVED,
                awaiting.approval.plan_hash,
            )
            await _next_command(runtime, coordinator)
            completed = await service.get_run(scope, handle.thread_id)
            assert completed is not None
            assert completed.status.value == "completed"
            assert completed.active is False
            assert len(completed.evidence) == 1
            assert completed.evidence[0].retention == "artifact"
            assert completed.evidence[0].session_result is None
            assert completed.evidence[0].workspace_route == "/ui"
            assert adapter.calls == 1

            history = await service.list_runs(scope)
            assert [item.thread_id for item in history.runs] == [handle.thread_id]
            assert history.active_thread_id is None
            events = await service.replay_events(scope, handle.thread_id, 0)
            assert [event.kind for event in events] == [
                "queued",
                "planning",
                "approval_required",
                "approval_submitted",
                "executing",
                "tool_succeeded",
                "completed",
            ]
        finally:
            await coordinator.delete_test_namespace()
            await coordinator.aclose()

    asyncio.run(scenario())


def test_edit_requires_current_plan_hash_and_cancel_is_idempotent():
    async def scenario():
        service, runtime, coordinator, _adapter = _services()
        scope = TrustedProjectScope(
            project_id="project-a",
            actor_id="local-workbench",
            scope_version="iteration4-aspect4-v1",
        )
        try:
            handle = await service.create_run(
                scope,
                AgentRunCreateRequest(
                    goal="Generate UI tests", model_label="GLM-4.7"
                ),
            )
            await _next_command(runtime, coordinator)
            view = await service.get_run(scope, handle.thread_id)
            assert view and view.approval
            with pytest.raises(ValueError, match="plan hash"):
                await service.edit_run(
                    scope, handle.thread_id, "Changed goal", "0" * 64
                )

            await service.cancel_run(scope, handle.thread_id)
            await _next_command(runtime, coordinator)
            first = await service.cancel_run(scope, handle.thread_id)
            second = await service.cancel_run(scope, handle.thread_id)
            assert first.status.value == second.status.value == "cancelled"
        finally:
            await coordinator.delete_test_namespace()
            await coordinator.aclose()

    asyncio.run(scenario())
