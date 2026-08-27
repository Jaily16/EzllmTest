"""Trusted host facade that exposes safe Agent workbench operations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from service.agentCheckpoint import derive_agent_scope_hash
from service.agentContracts import (
    AgentRunStatus,
    ApprovalDecision,
    TrustedProjectScope,
)
from service.agentGraph import graph_plan_hash
from service.agentRuntimeContracts import AGENT_GRAPH_VERSION
from service.agentRuntimeService import AgentRunHandle, AgentRuntimeService
from service.agentToolRegistry import DEFAULT_TOOL_REGISTRY
from service.agentWorkbenchContracts import (
    AgentApprovalView,
    AgentBudgetPreset,
    AgentBudgetView,
    AgentPlanStepView,
    AgentContextBindingView,
    AgentRunCreateRequest,
    AgentRunList,
    AgentRunSummary,
    AgentRunView,
    AgentTimelineEvent,
    budget_for_preset,
)
from service.agentWorkbenchStore import AgentWorkbenchStore
from service.agentTelemetry import get_agent_telemetry


_ACTIVE_STATUSES = {
    AgentRunStatus.CREATED,
    AgentRunStatus.PLANNING,
    AgentRunStatus.AWAITING_APPROVAL,
    AgentRunStatus.EXECUTING,
    AgentRunStatus.VALIDATING,
    AgentRunStatus.RECOVERING,
}


class AgentRunConflict(RuntimeError):
    pass


class AgentWorkbenchService:
    def __init__(
        self,
        runtime: AgentRuntimeService,
        store: AgentWorkbenchStore,
        *,
        clock=lambda: datetime.now(UTC),
    ) -> None:
        self.runtime = runtime
        self.store = store
        self.clock = clock

    @staticmethod
    def scope_hash(scope: TrustedProjectScope) -> str:
        return derive_agent_scope_hash(scope, AGENT_GRAPH_VERSION)

    async def _append(
        self,
        scope_hash: str,
        thread_id: str,
        event_id: str,
        kind: str,
        status: AgentRunStatus,
        **data,
    ) -> int:
        return await self.store.append_timeline_event(
            scope_hash,
            thread_id,
            event_id,
            {
                "kind": kind,
                "occurred_at": self.clock().isoformat(),
                "status": status.value,
                **data,
            },
        )

    async def _clear_stale_active(
        self, scope: TrustedProjectScope, scope_hash: str
    ) -> str | None:
        active = await self.store.active_thread(scope_hash)
        if active is None:
            return None
        envelope = await self.runtime.get_run(scope, active)
        if envelope is not None and envelope.run_state.status in _ACTIVE_STATUSES:
            return active
        await self.store.release_active(scope_hash, active)
        return None

    async def create_run(
        self,
        scope: TrustedProjectScope,
        request: AgentRunCreateRequest,
    ) -> AgentRunHandle:
        scope_hash = self.scope_hash(scope)
        active = await self._clear_stale_active(scope, scope_hash)
        if active is not None:
            raise AgentRunConflict("project already has an active Agent run")
        reservation = f"creating-{uuid4().hex}"
        if not await self.store.reserve_active(scope_hash, reservation):
            raise AgentRunConflict("project already has an active Agent run")
        try:
            budget = request.budget_preset
            now = self.clock()
            handle = await self.runtime.create_run(
                scope,
                request.goal,
                request.model_label,
                request.model_label,
                budget_for_preset(budget),
            )
            await self.store.register_run(
                scope_hash, handle.thread_id, budget, now
            )
            if not await self.store.commit_active(
                scope_hash, reservation, handle.thread_id
            ):
                raise AgentRunConflict("active Agent run reservation was lost")
            await self._append(
                scope_hash,
                handle.thread_id,
                "run:queued",
                "queued",
                AgentRunStatus.CREATED,
            )
            return handle
        except BaseException:
            await self.store.release_active(scope_hash, reservation)
            raise

    async def get_run(
        self, scope: TrustedProjectScope, thread_id: str
    ) -> AgentRunView | None:
        scope_hash = self.scope_hash(scope)
        metadata = await self.store.run_metadata(scope_hash, thread_id)
        if metadata is None:
            return None
        envelope = await self.runtime.get_run(scope, thread_id)
        if envelope is None:
            return None
        run = envelope.run_state
        storage_id = self.runtime._storage_id(scope_hash, thread_id)
        ledger_usage = await self.runtime.budget_ledger.snapshot_by_identity(
            storage_id
        )
        usage = ledger_usage or run.usage
        active = await self.store.active_thread(scope_hash) == thread_id
        now = self.clock()
        plan = []
        for index, call in enumerate(run.plan):
            definition = DEFAULT_TOOL_REGISTRY.get(
                f"workflow_{call.operation}"
            )
            plan.append(
                AgentPlanStepView(
                    step_id=call.step_id,
                    operation=call.operation,
                    arguments=call.arguments,
                    risks=tuple(sorted(call.risks, key=lambda item: item.value)),
                    model_label=call.model_label,
                    retention=definition.retention,
                    current=index == run.current_step_index,
                    context_bindings=tuple(
                        AgentContextBindingView(
                            payload_field=binding.payload_field,
                            source_operation=binding.source_operation,
                            artifact_key=binding.artifact_key,
                            source_revision=binding.source_revision,
                            result_path=binding.result_path,
                            content_sha256=binding.content_sha256,
                        )
                        for binding in call.context_bindings
                    ),
                )
            )
        approval = None
        if envelope.approval_request is not None:
            request = envelope.approval_request
            approval = AgentApprovalView(
                plan_hash=request.plan_hash,
                plan_version=request.plan_version,
                step_id=request.step_id,
                operation=request.operation,
                risks=request.risks,
                expires_at=request.expires_at,
                expired=now >= request.expires_at,
            )
        bounds = await self.store.timeline_bounds(scope_hash, thread_id)
        retryable = bool(run.last_error and run.last_error.retryable)
        telemetry = get_agent_telemetry()
        trace_id = (
            envelope.trace_carrier.trace_id
            if telemetry.enabled and envelope.trace_carrier is not None
            else None
        )
        return AgentRunView(
            run_id=run.run_id,
            thread_id=run.thread_id,
            goal=run.goal,
            status=run.status,
            source_revision=run.source_revision,
            created_at=metadata.created_at,
            deadline_at=envelope.deadline_at,
            expires_at=metadata.created_at
            + timedelta(seconds=self.store.ttl),
            model_label=envelope.execution_model,
            budget=AgentBudgetView.from_usage(metadata.budget_preset, usage),
            plan_version=run.plan_version,
            current_step_index=run.current_step_index,
            plan=tuple(plan),
            approval=approval,
            evidence=await self.store.get_evidence(scope_hash, thread_id),
            last_error=run.last_error,
            last_event_sequence=bounds[1] if bounds else 0,
            worker_available=await self.store.worker_available(),
            active=active,
            can_approve=(
                run.status is AgentRunStatus.AWAITING_APPROVAL
                and approval is not None
                and not approval.expired
            ),
            can_edit=(
                run.status is AgentRunStatus.AWAITING_APPROVAL
                and approval is not None
            ),
            can_cancel=run.status in _ACTIVE_STATUSES,
            can_recover=(run.status is AgentRunStatus.FAILED and retryable),
            trace_id=trace_id,
            trace_status=(
                "instrumented" if trace_id is not None else "not_instrumented"
            ),
        )

    async def list_runs(
        self,
        scope: TrustedProjectScope,
        *,
        limit: int = 20,
        before: int | None = None,
    ) -> AgentRunList:
        scope_hash = self.scope_hash(scope)
        await self._clear_stale_active(scope, scope_hash)
        threads, next_cursor = await self.store.list_run_threads(
            scope_hash, limit=limit, before=before
        )
        summaries: list[AgentRunSummary] = []
        for thread_id in threads:
            view = await self.get_run(scope, thread_id)
            if view is None:
                continue
            summaries.append(
                AgentRunSummary(
                    run_id=view.run_id,
                    thread_id=view.thread_id,
                    goal=view.goal,
                    status=view.status,
                    model_label=view.model_label,
                    budget_preset=view.budget.preset,
                    created_at=view.created_at,
                    active=view.active,
                )
            )
        return AgentRunList(
            runs=tuple(summaries),
            active_thread_id=await self.store.active_thread(scope_hash),
            next_cursor=next_cursor,
        )

    async def decide_approval(
        self,
        scope: TrustedProjectScope,
        thread_id: str,
        decision: ApprovalDecision,
        expected_plan_hash: str,
    ) -> str:
        if decision not in {ApprovalDecision.APPROVED, ApprovalDecision.REJECTED}:
            raise ValueError("public approval decision is unsupported")
        command_id = await self.runtime.approve_run(
            scope, thread_id, decision, expected_plan_hash
        )
        view = await self.get_run(scope, thread_id)
        if view is None:
            raise KeyError("Agent thread was not found")
        await self._append(
            self.scope_hash(scope),
            thread_id,
            f"approval:{view.plan_version}:{decision.value}",
            "approval_submitted",
            view.status,
            step_id=(view.approval.step_id if view.approval else None),
            operation=(view.approval.operation if view.approval else None),
        )
        return command_id

    async def edit_run(
        self,
        scope: TrustedProjectScope,
        thread_id: str,
        goal: str,
        expected_plan_hash: str,
    ) -> str:
        envelope = await self.runtime.get_run(scope, thread_id)
        request = envelope.approval_request if envelope is not None else None
        if request is None or request.plan_hash != expected_plan_hash:
            raise ValueError("edit plan hash does not match")
        command_id = await self.runtime.edit_run(scope, thread_id, goal)
        await self._append(
            self.scope_hash(scope),
            thread_id,
            f"replanning:{request.plan_version}",
            "replanning",
            envelope.run_state.status,
            step_id=request.step_id,
            operation=request.operation,
        )
        return command_id

    async def cancel_run(
        self, scope: TrustedProjectScope, thread_id: str
    ) -> AgentRunView:
        view = await self.get_run(scope, thread_id)
        if view is None:
            raise KeyError("Agent thread was not found")
        if view.status in {AgentRunStatus.COMPLETED, AgentRunStatus.CANCELLED}:
            return view
        if view.status is AgentRunStatus.FAILED:
            raise AgentRunConflict("failed run cannot be cancelled")
        if view.status is AgentRunStatus.AWAITING_APPROVAL and view.approval:
            await self.runtime.approve_run(
                scope,
                thread_id,
                ApprovalDecision.REJECTED,
                view.approval.plan_hash,
            )
        else:
            await self.runtime.cancel_run(scope, thread_id)
        await self._append(
            self.scope_hash(scope),
            thread_id,
            f"cancel:{view.plan_version}",
            "cancel_requested",
            view.status,
        )
        refreshed = await self.get_run(scope, thread_id)
        if refreshed is None:
            raise KeyError("Agent thread was not found")
        return refreshed

    async def recover_run(
        self, scope: TrustedProjectScope, thread_id: str
    ) -> str:
        scope_hash = self.scope_hash(scope)
        active = await self._clear_stale_active(scope, scope_hash)
        if active is not None and active != thread_id:
            raise AgentRunConflict("project already has an active Agent run")
        reservation = f"recovering-{uuid4().hex}"
        if active is None and not await self.store.reserve_active(
            scope_hash, reservation
        ):
            raise AgentRunConflict("project already has an active Agent run")
        try:
            command_id = await self.runtime.recover_run(scope, thread_id)
            if active is None and not await self.store.commit_active(
                scope_hash, reservation, thread_id
            ):
                raise AgentRunConflict("active Agent recovery reservation was lost")
            await self._append(
                scope_hash,
                thread_id,
                f"recovering:{command_id}",
                "recovering",
                AgentRunStatus.RECOVERING,
            )
            return command_id
        except BaseException:
            if active is None:
                await self.store.release_active(scope_hash, reservation)
            raise

    async def replay_events(
        self,
        scope: TrustedProjectScope,
        thread_id: str,
        after_sequence: int,
    ) -> tuple[AgentTimelineEvent, ...]:
        if await self.get_run(scope, thread_id) is None:
            raise KeyError("Agent thread was not found")
        return await self.store.replay_timeline(
            self.scope_hash(scope), thread_id, after_sequence
        )
