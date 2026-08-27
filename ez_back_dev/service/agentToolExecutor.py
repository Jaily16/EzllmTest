"""Approved, project-scoped execution over existing in-process services."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import nullcontext
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, JsonValue, ValidationError

from service import projectSetupService, projectWorkflowStatusService
from service.agentContracts import (
    AgentRunState,
    AgentRunStatus,
    ApprovalBinding,
    TrustedProjectScope,
    approval_is_valid,
    redact_sensitive_text,
)
from service.agentContext import context_payload_fields
from service.agentRetrieval import use_agent_retrieval
from service.agentToolRegistry import (
    DEFAULT_TOOL_REGISTRY,
    RegisteredToolDefinition,
    ToolRegistry,
)
from service.agentToolSchemas import (
    ToolExecutionError,
    ToolExecutionResult,
    ToolExecutionStatus,
    ToolProgress,
    ToolUsageSummary,
    WorkflowToolInput,
)
from service.llmTestPlanStreamService import (
    TestPlanStreamError,
    get_project_analysis_status,
    stream_test_plan,
)
from service.llmWorkflowStreamCore import WorkflowStreamError
from service.llmWorkflowStreamService import stream_llm_workflow


CancelCheck = Callable[[], bool | Awaitable[bool]]
ProgressSink = Callable[[ToolProgress], None | Awaitable[None]]
StreamFactory = Callable[..., AsyncIterator[dict[str, Any]]]


@dataclass(frozen=True)
class ToolInvocationContext:
    project_scope: TrustedProjectScope
    run_state: AgentRunState | None = None
    approval: ApprovalBinding | None = None
    is_cancelled: CancelCheck | None = None
    progress_sink: ProgressSink | None = None
    trace_id: str | None = None
    # Hydrated prerequisite bodies live only for this in-process invocation.
    # They are never part of AgentRunState or a Redis checkpoint.
    execution_arguments: dict[str, JsonValue] | None = None


@dataclass(frozen=True)
class ToolServiceBindings:
    project_setup_status: Callable[[str], Any]
    project_analysis_status: Callable[[str], Any]
    project_workflow_status: Callable[[str], Any]
    stream_test_plan: StreamFactory
    stream_workflow: StreamFactory


def _default_bindings() -> ToolServiceBindings:
    return ToolServiceBindings(
        project_setup_status=projectSetupService.get_status,
        project_analysis_status=get_project_analysis_status,
        project_workflow_status=(
            projectWorkflowStatusService.get_project_workflow_status
        ),
        stream_test_plan=stream_test_plan,
        stream_workflow=stream_llm_workflow,
    )


def _safe_error(
    tool_name: str,
    operation: str | None,
    *,
    code: str,
    category: str,
    message: str,
    retryable: bool = False,
    status: ToolExecutionStatus = ToolExecutionStatus.ERROR,
    invoked: bool = False,
) -> ToolExecutionResult:
    return ToolExecutionResult(
        tool_name=tool_name,
        operation=operation,
        status=status,
        usage=ToolUsageSummary(
            tool_calls=1 if invoked else 0,
            embedding_calls=None if invoked else 0,
        ),
        error=ToolExecutionError(
            code=code,
            category=category,
            retryable=retryable,
            safe_message=redact_sensitive_text(message),
        ),
    )


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _json_value(value: Any) -> JsonValue:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return model_dump(mode="json")
    return value


class AgentToolExecutor:
    def __init__(
        self,
        *,
        registry: ToolRegistry = DEFAULT_TOOL_REGISTRY,
        bindings: ToolServiceBindings | None = None,
    ) -> None:
        self.registry = registry
        self.bindings = bindings or _default_bindings()

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, JsonValue],
        context: ToolInvocationContext,
    ) -> ToolExecutionResult:
        try:
            definition = self.registry.get(tool_name)
        except KeyError:
            return _safe_error(
                tool_name,
                None,
                code="unknown_tool",
                category="validation",
                message="Unknown tool",
            )
        try:
            request = definition.input_model.model_validate(arguments)
        except ValidationError:
            return _safe_error(
                tool_name,
                definition.operation,
                code="invalid_arguments",
                category="validation",
                message="Tool arguments do not match the registered schema",
            )

        if definition.catalog is None:
            return await self._execute_read(definition, context)
        if not isinstance(request, WorkflowToolInput):
            return _safe_error(
                tool_name,
                definition.operation,
                code="invalid_arguments",
                category="validation",
                message="Workflow tool input is invalid",
            )

        approval_error = self._approval_error(definition, request, context)
        if approval_error is not None:
            return approval_error
        if await self._cancel_requested(context):
            raise asyncio.CancelledError
        return await self._execute_workflow(definition, request, context)

    async def _execute_read(
        self,
        definition: RegisteredToolDefinition,
        context: ToolInvocationContext,
    ) -> ToolExecutionResult:
        service = {
            "project_setup_status": self.bindings.project_setup_status,
            "project_analysis_status": self.bindings.project_analysis_status,
            "project_workflow_status": self.bindings.project_workflow_status,
        }[definition.name]
        try:
            value = await _maybe_await(
                service(context.project_scope.project_id)
            )
            return ToolExecutionResult(
                tool_name=definition.name,
                status=ToolExecutionStatus.SUCCESS,
                data=_json_value(value),
                usage=ToolUsageSummary(
                    model_calls=0,
                    embedding_calls=0,
                    tool_calls=1,
                ),
            )
        except projectSetupService.ProjectSetupError as exc:
            return _safe_error(
                definition.name,
                None,
                code="project_status_error",
                category="permanent" if exc.status_code < 500 else "transient",
                message=str(exc),
                retryable=exc.status_code >= 500,
                invoked=True,
            )
        except Exception:
            return _safe_error(
                definition.name,
                None,
                code="internal_error",
                category="transient",
                message="Tool execution failed",
                retryable=True,
                invoked=True,
            )

    def _approval_error(
        self,
        definition: RegisteredToolDefinition,
        request: WorkflowToolInput,
        context: ToolInvocationContext,
    ) -> ToolExecutionResult | None:
        state = context.run_state
        if state is not None and state.project_scope != context.project_scope:
            return _safe_error(
                definition.name,
                definition.operation,
                code="project_scope_mismatch",
                category="validation",
                message="Trusted project scope does not match the run",
            )
        if state is None or context.approval is None:
            return _safe_error(
                definition.name,
                definition.operation,
                code="approval_required",
                category="approval",
                message="A matching human approval is required",
                status=ToolExecutionStatus.APPROVAL_REQUIRED,
            )
        if state.status is not AgentRunStatus.EXECUTING:
            return _safe_error(
                definition.name,
                definition.operation,
                code="approval_required",
                category="approval",
                message="The approved run is not in the executing state",
                status=ToolExecutionStatus.APPROVAL_REQUIRED,
            )
        if state.cancel_requested:
            return _safe_error(
                definition.name,
                definition.operation,
                code="cancelled",
                category="cancelled",
                message="The run was cancelled before execution",
                status=ToolExecutionStatus.CANCELLED,
            )
        if state.usage.tool_calls >= state.budget.max_tool_calls:
            return _safe_error(
                definition.name,
                definition.operation,
                code="tool_budget_exceeded",
                category="budget",
                message="The tool-call budget is exhausted",
            )
        if not state.plan or state.current_step_index >= len(state.plan):
            return _safe_error(
                definition.name,
                definition.operation,
                code="approval_required",
                category="approval",
                message="The approved plan step is unavailable",
                status=ToolExecutionStatus.APPROVAL_REQUIRED,
            )
        planned = state.plan[state.current_step_index]
        planned_arguments = request.planned_arguments()
        if planned.context_bindings:
            planned_arguments = {
                key: value
                for key, value in planned_arguments.items()
                if key not in context_payload_fields(planned.operation)
            }
        expected_risks = definition.resolve_risks(
            regenerate=request.regenerate
        )
        if (
            planned.operation != definition.operation
            or planned.arguments != planned_arguments
            or planned.model_label != request.model_label
            or planned.risks != expected_risks
        ):
            return _safe_error(
                definition.name,
                definition.operation,
                code="approval_required",
                category="approval",
                message="Tool arguments no longer match the approved plan",
                status=ToolExecutionStatus.APPROVAL_REQUIRED,
            )
        if not approval_is_valid(state, planned, context.approval):
            return _safe_error(
                definition.name,
                definition.operation,
                code="approval_required",
                category="approval",
                message="The approval is missing, expired, or invalidated",
                status=ToolExecutionStatus.APPROVAL_REQUIRED,
            )
        return None

    async def _cancel_requested(
        self, context: ToolInvocationContext
    ) -> bool:
        if context.run_state is not None and context.run_state.cancel_requested:
            return True
        if context.is_cancelled is None:
            return False
        return bool(await _maybe_await(context.is_cancelled()))

    async def _execute_workflow(
        self,
        definition: RegisteredToolDefinition,
        request: WorkflowToolInput,
        context: ToolInvocationContext,
    ) -> ToolExecutionResult:
        async def disconnected() -> bool:
            return await self._cancel_requested(context)

        operation = definition.operation
        assert operation is not None
        retrieval_scope = (
            use_agent_retrieval(context.project_scope)
            if context.run_state is not None
            else nullcontext(None)
        )
        retrieval_session = None
        try:
            with retrieval_scope as retrieval_session:
                stream = (
                    self.bindings.stream_test_plan(
                        context.project_scope.project_id,
                        request.model_label,
                        request.regenerate,
                        is_disconnected=disconnected,
                    )
                    if operation == "project_analysis"
                    else self.bindings.stream_workflow(
                        operation,
                        context.project_scope.project_id,
                        request.model_label,
                        request.workflow_payload(),
                        request.regenerate,
                        is_disconnected=disconnected,
                    )
                )
                result = await self._consume_stream(
                    definition, stream, context
                )
                evidence = (
                    retrieval_session.snapshot()
                    if retrieval_session is not None
                    else None
                )
                return result.model_copy(
                    update={"retrieval_evidence": evidence}
                )
        except asyncio.CancelledError:
            raise
        except (WorkflowStreamError, TestPlanStreamError) as exc:
            result = _safe_error(
                definition.name,
                operation,
                code=exc.code,
                category="transient" if exc.retryable else "permanent",
                message=str(exc),
                retryable=exc.retryable,
                invoked=True,
            )
            return result.model_copy(
                update={
                    "retrieval_evidence": (
                        retrieval_session.snapshot()
                        if retrieval_session is not None
                        else None
                    )
                }
            )
        except Exception:
            result = _safe_error(
                definition.name,
                operation,
                code="internal_error",
                category="transient",
                message="Tool execution failed",
                retryable=True,
                invoked=True,
            )
            return result.model_copy(
                update={
                    "retrieval_evidence": (
                        retrieval_session.snapshot()
                        if retrieval_session is not None
                        else None
                    )
                }
            )

    async def _consume_stream(
        self,
        definition: RegisteredToolDefinition,
        stream: AsyncIterator[dict[str, Any]],
        context: ToolInvocationContext,
    ) -> ToolExecutionResult:
        result: JsonValue | None = None
        summary_parts: list[str] = []
        plan_parts: list[str] = []
        menu: JsonValue | None = None
        source_revision: str | None = None
        artifact_key: str | None = None
        saved = False
        from_cache = False
        stale = False
        usage_data: dict[str, Any] = {}
        last_progress = -1.0

        async for item in stream:
            event_name = item.get("event")
            data = item.get("data")
            if not isinstance(data, dict):
                data = {}
            if event_name == "reasoning_delta":
                continue
            if event_name == "progress":
                percent = data.get("percent")
                if isinstance(percent, (int, float)) and percent > last_progress:
                    last_progress = float(percent)
                    if context.progress_sink is not None:
                        progress = ToolProgress(
                            stage=str(data.get("stage") or "progress"),
                            label=str(data.get("label") or "In progress"),
                            progress=float(percent),
                            total=100,
                            current=(
                                data.get("current")
                                if isinstance(data.get("current"), int)
                                else None
                            ),
                            item_total=(
                                data.get("total")
                                if isinstance(data.get("total"), int)
                                else None
                            ),
                        )
                        await _maybe_await(context.progress_sink(progress))
                continue
            if event_name == "summary_delta":
                text = data.get("text")
                if isinstance(text, str):
                    summary_parts.append(text)
                continue
            if event_name == "answer_delta":
                text = data.get("text")
                if isinstance(text, str):
                    plan_parts.append(text)
                continue
            if event_name == "menu":
                menu = data.get("menu")
                continue
            if event_name == "meta":
                source_revision = data.get("source_revision") or source_revision
                artifact_key = data.get("artifact_key") or artifact_key
                continue
            if event_name == "stale":
                stale = True
                source_revision = data.get("source_revision") or source_revision
                artifact_key = data.get("artifact_key") or artifact_key
                continue
            if event_name == "usage":
                usage_data.update(data)
                continue
            if event_name == "artifact":
                artifact_key = data.get("artifact_key") or artifact_key
                source_revision = data.get("source_revision") or source_revision
                from_cache = bool(data.get("from_cache", from_cache))
                continue
            if event_name == "result":
                result = data.get("result")
                continue
            if event_name == "completed":
                saved = bool(data.get("saved", saved))
                from_cache = bool(data.get("from_cache", from_cache))
                source_revision = data.get("source_revision") or source_revision
                artifact_key = data.get("artifact_key") or artifact_key
                usage_data.update(data)

        if definition.operation == "project_analysis":
            result = {
                "summary": "".join(summary_parts),
                "plan": "".join(plan_parts),
                "menu": menu,
            }
        if result is None:
            return _safe_error(
                definition.name,
                definition.operation,
                code="empty_tool_result",
                category="transient",
                message="Workflow completed without a structured result",
                retryable=True,
                invoked=True,
            )
        return ToolExecutionResult(
            tool_name=definition.name,
            operation=definition.operation,
            status=ToolExecutionStatus.SUCCESS,
            data=result,
            from_cache=from_cache,
            saved=saved,
            stale=stale,
            source_revision=source_revision,
            artifact_key=artifact_key,
            usage=ToolUsageSummary(
                input_tokens=_nonnegative_int(usage_data.get("input_tokens")),
                output_tokens=_nonnegative_int(usage_data.get("output_tokens")),
                model_calls=(
                    _nonnegative_int(usage_data.get("model_call_count")) or 0
                ),
                embedding_calls=None,
                tool_calls=1,
                estimated_cost_units=None,
            ),
        )


def _nonnegative_int(value: Any) -> int | None:
    return value if isinstance(value, int) and value >= 0 else None
