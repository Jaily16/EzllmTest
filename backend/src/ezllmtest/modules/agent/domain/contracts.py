# 单 Agent 的纯业务契约与审批绑定规则，不连接 Redis 或读取项目文件。
"""Pure Aspect 1 contracts for a future single-Agent LangGraph runtime.

This module deliberately performs no I/O and imports no Agent runtime,
checkpointer, Redis, MCP, or telemetry package.  The models are a reference
contract for later aspects, not an enabled execution path.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_validator,
    model_validator,
)

from ezllmtest.modules.generation.public import get_workflow_definition, list_workflow_definitions


class _ContractModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )


class ToolRisk(str, Enum):
    READ_ONLY = "read_only"
    PAID = "paid"
    PERSISTENT = "persistent"
    REGENERATE = "regenerate"


class AgentRunStatus(str, Enum):
    CREATED = "created"
    PLANNING = "planning"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    VALIDATING = "validating"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"
    RECOVERING = "recovering"


class ApprovalDecision(str, Enum):
    APPROVED = "approved"
    EDITED = "edited"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ToolAttemptStatus(str, Enum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class TransitionKind(str, Enum):
    START_PLANNING = "start_planning"
    PLAN_READY = "plan_ready"
    PLAN_EDITED = "plan_edited"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPROVAL_EXPIRED = "approval_expired"
    TOOL_STARTED = "tool_started"
    TOOL_SUCCEEDED = "tool_succeeded"
    TOOL_FAILED = "tool_failed"
    VALIDATION_SUCCEEDED = "validation_succeeded"
    VALIDATION_FAILED = "validation_failed"
    CANCEL_REQUESTED = "cancel_requested"
    STALE_DETECTED = "stale_detected"
    RECOVERY_STARTED = "recovery_started"
    RECOVERY_RECONCILED = "recovery_reconciled"
    BUDGET_EXHAUSTED = "budget_exhausted"
    CONTEXT_UNAVAILABLE = "context_unavailable"


class TrustedProjectScope(_ContractModel):
    """Project authority supplied by the trusted runtime, never by a model."""

    project_id: str = Field(min_length=1, max_length=128)
    actor_id: str = Field(min_length=1, max_length=128)
    scope_version: str = Field(min_length=1, max_length=64)


class TypedToolDefinition(_ContractModel):
    """Transport-neutral workflow tool metadata shared by future adapters."""

    schema_version: Literal[1] = 1
    operation: str = Field(min_length=1, max_length=64)
    phase: Literal["project", "analysis", "case"]
    selection_fields: tuple[str, ...]
    prerequisite_payload_fields: tuple[str, ...]
    persistence: Literal["artifact", "session"]
    supports_regenerate: bool


class RunBudget(_ContractModel):
    max_steps: int = Field(gt=0)
    max_elapsed_ms: int = Field(gt=0)
    max_input_tokens: int = Field(gt=0)
    max_output_tokens: int = Field(gt=0)
    max_model_calls: int = Field(gt=0)
    max_embedding_calls: int = Field(gt=0)
    max_tool_calls: int = Field(gt=0)
    max_estimated_cost_units: int = Field(gt=0)


class UsageCounters(_ContractModel):
    steps: int = Field(default=0, ge=0)
    elapsed_ms: int = Field(default=0, ge=0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    model_calls: int = Field(default=0, ge=0)
    embedding_calls: int = Field(default=0, ge=0)
    tool_calls: int = Field(default=0, ge=0)
    estimated_cost_units: int = Field(default=0, ge=0)


class ContextBinding(_ContractModel):
    """Metadata-only reference to a trusted prerequisite artifact.

    The artifact body is deliberately absent.  It is loaded just in time by
    the trusted worker and must never become checkpoint data.
    """

    payload_field: str = Field(min_length=1, max_length=64)
    source_operation: str = Field(min_length=1, max_length=64)
    artifact_key: str = Field(min_length=1, max_length=128)
    source_revision: str = Field(min_length=1, max_length=128)
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    prompt_version: str = Field(min_length=1, max_length=128)
    model_label: str = Field(min_length=1, max_length=128)
    result_path: tuple[str, ...] = ()
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


_FORBIDDEN_ARGUMENT_KEYS = {
    "api_key",
    "authorization",
    "completion",
    "cookie",
    "document_body",
    "password",
    "passwd",
    "pid",
    "project_id",
    "prompt",
    "raw_document",
    "reasoning",
    "scope",
    "scratchpad",
    "secret",
    "token",
    "user_id",
}


def _validate_safe_json(value: JsonValue, path: str = "arguments") -> None:
    """递归约束计划参数为安全 JSON，拒绝携带运行权威或不允许内容的结构。"""
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = key.strip().lower()
            if normalized in _FORBIDDEN_ARGUMENT_KEYS:
                raise ValueError(f"forbidden tool argument key: {path}.{key}")
            _validate_safe_json(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _validate_safe_json(nested, f"{path}[{index}]")


class PlannedToolCall(_ContractModel):
    step_id: str = Field(min_length=1, max_length=128)
    operation: str = Field(min_length=1, max_length=64)
    arguments: dict[str, JsonValue] = Field(default_factory=dict)
    risks: frozenset[ToolRisk] = Field(min_length=1)
    idempotency_key: str = Field(min_length=1, max_length=256)
    model_label: str = Field(min_length=1, max_length=128)
    context_bindings: tuple[ContextBinding, ...] = ()

    @field_validator("operation")
    @classmethod
    def _operation_must_exist_in_catalog(cls, operation: str) -> str:
        """计划操作必须属于固定 workflow 目录，不能通过名称动态发现任意能力。"""
        try:
            get_workflow_definition(operation)
        except KeyError as exc:
            raise ValueError(
                f"unknown workflow operation: {operation}"
            ) from exc
        return operation

    @field_validator("arguments")
    @classmethod
    def _arguments_are_safe(cls, arguments: dict[str, JsonValue]):
        """在计划对象建立时拒绝参数中的禁止字段，不能由模型注入可信 scope 或执行权。"""
        _validate_safe_json(arguments)
        return arguments

    @model_validator(mode="after")
    def _risks_are_coherent(self):
        """校验操作的付费、持久化和重新生成风险是否自洽，审批必须覆盖真实副作用。"""
        if ToolRisk.READ_ONLY in self.risks and len(self.risks) != 1:
            raise ValueError("read_only risk cannot be combined with side effects")
        if ToolRisk.REGENERATE in self.risks and not {
            ToolRisk.PAID,
            ToolRisk.PERSISTENT,
        }.issubset(self.risks):
            raise ValueError(
                "regenerate risk requires paid and persistent risks"
            )
        return self


class ApprovalBinding(_ContractModel):
    run_id: str = Field(min_length=1, max_length=128)
    plan_version: int = Field(ge=1)
    step_id: str = Field(min_length=1, max_length=128)
    operation: str = Field(min_length=1, max_length=64)
    arguments_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    risks_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    project_id: str = Field(min_length=1, max_length=128)
    source_revision: str = Field(min_length=1, max_length=128)
    model_label: str = Field(min_length=1, max_length=128)
    budget_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    nonce: str = Field(min_length=1, max_length=256)
    decision: ApprovalDecision
    decided_at: AwareDatetime
    expires_at: AwareDatetime

    @model_validator(mode="after")
    def _expiry_follows_decision(self):
        """审批到期时间必须晚于决定时间，避免无有效窗口的授权进入恢复流程。"""
        if self.expires_at <= self.decided_at:
            raise ValueError("approval expiry must follow decision time")
        return self


class AgentError(_ContractModel):
    code: str = Field(min_length=1, max_length=128)
    category: Literal[
        "validation", "approval", "budget", "transient", "permanent", "stale"
    ]
    retryable: bool
    safe_message: str = Field(min_length=1, max_length=512)

    @field_validator("safe_message")
    @classmethod
    def _redact_safe_message(cls, value: str) -> str:
        """在模型字段校验时脱敏错误消息中的敏感赋值，避免异常内容进入公开状态。"""
        return redact_sensitive_text(value)


class ToolAttempt(_ContractModel):
    step_id: str = Field(min_length=1, max_length=128)
    operation: str = Field(min_length=1, max_length=64)
    idempotency_key: str = Field(min_length=1, max_length=256)
    status: ToolAttemptStatus
    side_effect_committed: bool = False


class AgentRunState(_ContractModel):
    schema_version: Literal[1] = 1
    run_id: str = Field(min_length=1, max_length=128)
    thread_id: str = Field(min_length=1, max_length=128)
    project_scope: TrustedProjectScope
    source_revision: str = Field(min_length=1, max_length=128)
    goal: str = Field(min_length=1, max_length=4_000)
    plan_version: int = Field(default=0, ge=0)
    plan: tuple[PlannedToolCall, ...] = ()
    current_step_index: int = Field(default=0, ge=0)
    status: AgentRunStatus = AgentRunStatus.CREATED
    pending_approval: ApprovalBinding | None = None
    approvals: tuple[ApprovalBinding, ...] = ()
    tool_attempts: tuple[ToolAttempt, ...] = ()
    artifact_refs: tuple[str, ...] = ()
    budget: RunBudget
    usage: UsageCounters = Field(default_factory=UsageCounters)
    cancel_requested: bool = False
    event_sequence: int = Field(default=0, ge=0)
    last_error: AgentError | None = None
    recovery_from_checkpoint: str | None = Field(default=None, max_length=256)

    @field_validator("goal")
    @classmethod
    def _goal_must_not_contain_assigned_secrets(cls, value: str) -> str:
        """拒绝将赋值形式的秘密放入目标，防止秘密进入计划和运行状态。"""
        if redact_sensitive_text(value) != value:
            raise ValueError("goal contains sensitive data that must be redacted")
        return value

    @model_validator(mode="after")
    def _plan_fits_budget(self):
        """在状态建模时检查计划规模是否超出运行预算，不能等执行后再解释超额。"""
        if len(self.plan) > self.budget.max_steps:
            raise ValueError("plan exceeds max_steps budget")
        if self.plan and self.current_step_index >= len(self.plan):
            raise ValueError("current_step_index is outside the plan")
        return self


class AgentTransitionEvent(_ContractModel):
    kind: TransitionKind
    plan: tuple[PlannedToolCall, ...] = ()
    approval: ApprovalBinding | None = None
    usage: UsageCounters | None = None
    error: AgentError | None = None
    side_effect_committed: bool | None = None
    checkpoint_id: str | None = Field(default=None, max_length=256)
    new_source_revision: str | None = Field(default=None, max_length=128)
    occurred_at: AwareDatetime | None = None


def _stable_hash(value: Any) -> str:
    """使用稳定键序和紧凑 JSON 计算摘要，供审批输入绑定保持确定性。"""
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


_SENSITIVE_ASSIGNMENT = re.compile(
    r"(?i)\b(api[_-]?key|authorization|cookie|password|passwd|secret)"
    r"\s*([:=])\s*([^\s,;]+)"
)


def redact_sensitive_text(value: str) -> str:
    """将错误文本收敛为允许公开的稳定脱敏消息。"""

    return _SENSITIVE_ASSIGNMENT.sub(
        lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]",
        value,
    )


def typed_tool_definitions() -> tuple[TypedToolDefinition, ...]:
    """将 19 个工作流目录项投影为类型化工具契约，保留选择字段、前置输入和持久化语义。"""
    # 工作台与 MCP 必须共享 workflow catalog，避免两个入口产生不同的工具契约。

    return tuple(
        TypedToolDefinition(
            operation=item.operation,
            phase=item.phase,
            selection_fields=item.selection_fields,
            prerequisite_payload_fields=item.prerequisite_payload_fields,
            persistence=item.persistence,
            supports_regenerate=item.supports_regenerate,
        )
        for item in list_workflow_definitions()
    )


def typed_tool_definition_for(operation: str) -> TypedToolDefinition:
    """按 operation 从唯一目录构造工具契约；未知操作由目录查询拒绝。"""
    definition = get_workflow_definition(operation)
    return TypedToolDefinition(
        operation=definition.operation,
        phase=definition.phase,
        selection_fields=definition.selection_fields,
        prerequisite_payload_fields=definition.prerequisite_payload_fields,
        persistence=definition.persistence,
        supports_regenerate=definition.supports_regenerate,
    )


def _arguments_hash(call: PlannedToolCall) -> str:
    """把工具参数与上下文绑定一起纳入审批摘要，防止批准后切换输入来源。"""
    return _stable_hash(
        {
            "arguments": call.arguments,
            "context_bindings": [
                binding.model_dump(mode="json")
                for binding in call.context_bindings
            ],
        }
    )


def _risks_hash(call: PlannedToolCall) -> str:
    """对排序后的风险集合计算稳定摘要，风险变化必须使原审批失效。"""
    return _stable_hash(sorted(risk.value for risk in call.risks))


def _budget_hash(budget: RunBudget) -> str:
    """对完整运行预算计算摘要，将授权额度绑定到已批准计划。"""
    return _stable_hash(budget.model_dump(mode="json"))


def requires_approval(risks: set[ToolRisk] | frozenset[ToolRisk]) -> bool:
    """付费、持久化或强制重生成任一风险都要求审批，纯只读风险可直接通过。"""
    return bool(
        set(risks)
        & {ToolRisk.PAID, ToolRisk.PERSISTENT, ToolRisk.REGENERATE}
    )


def approval_binding_for(
    state: AgentRunState,
    call: PlannedToolCall,
    *,
    decision: ApprovalDecision,
    decided_at: datetime,
    expires_at: datetime,
    nonce: str,
) -> ApprovalBinding:
    """把审批绑定到项目、revision、模型、计划参数、上下文和预算身份，任一变化需重新核验。"""
    if state.plan_version < 1:
        raise ValueError("approval requires a versioned plan")
    return ApprovalBinding(
        run_id=state.run_id,
        plan_version=state.plan_version,
        step_id=call.step_id,
        operation=call.operation,
        arguments_hash=_arguments_hash(call),
        risks_hash=_risks_hash(call),
        project_id=state.project_scope.project_id,
        source_revision=state.source_revision,
        model_label=call.model_label,
        budget_hash=_budget_hash(state.budget),
        nonce=nonce,
        decision=decision,
        decided_at=decided_at,
        expires_at=expires_at,
    )


# 审批绑定同时校验计划、项目 revision、预算和参数摘要，防止旧计划重放副作用。
def approval_is_valid(
    state: AgentRunState,
    call: PlannedToolCall,
    approval: ApprovalBinding,
    *,
    now: datetime | None = None,
) -> bool:
    """同时核对审批身份、风险和时间窗口，过期或与当前计划不符的决定不授予执行权。"""
    checked_at = now or datetime.now(UTC)
    return (
        approval.decision == ApprovalDecision.APPROVED
        and approval.run_id == state.run_id
        and approval.plan_version == state.plan_version
        and approval.step_id == call.step_id
        and approval.operation == call.operation
        and approval.arguments_hash == _arguments_hash(call)
        and approval.risks_hash == _risks_hash(call)
        and approval.project_id == state.project_scope.project_id
        and approval.source_revision == state.source_revision
        and approval.model_label == call.model_label
        and approval.budget_hash == _budget_hash(state.budget)
        and approval.decided_at <= checked_at < approval.expires_at
    )


_USAGE_TO_BUDGET = {
    "steps": "max_steps",
    "elapsed_ms": "max_elapsed_ms",
    "input_tokens": "max_input_tokens",
    "output_tokens": "max_output_tokens",
    "model_calls": "max_model_calls",
    "embedding_calls": "max_embedding_calls",
    "tool_calls": "max_tool_calls",
    "estimated_cost_units": "max_estimated_cost_units",
}


def _validated_usage(
    previous: UsageCounters,
    current: UsageCounters | None,
    budget: RunBudget,
) -> UsageCounters:
    """验证并合并用量计数，拒绝负数或使累计消耗倒退的状态更新。"""
    if current is None:
        return previous
    for usage_field, budget_field in _USAGE_TO_BUDGET.items():
        previous_value = getattr(previous, usage_field)
        current_value = getattr(current, usage_field)
        if current_value < previous_value:
            raise ValueError("usage counters must be monotonic")
        if current_value > getattr(budget, budget_field):
            raise ValueError(f"budget exceeded: {usage_field}")
    return current


def _current_call(state: AgentRunState) -> PlannedToolCall:
    """按当前执行位置取得计划调用，为状态迁移提供唯一的步骤上下文。"""
    if not state.plan or state.current_step_index >= len(state.plan):
        raise ValueError("current plan step is unavailable")
    return state.plan[state.current_step_index]


def _updated_attempts(
    state: AgentRunState,
    status: ToolAttemptStatus,
    *,
    side_effect_committed: bool = False,
) -> tuple[ToolAttempt, ...]:
    """只更新最后一次工具尝试的状态及副作用提交标记，保留更早尝试历史。"""
    if not state.tool_attempts:
        return state.tool_attempts
    last = state.tool_attempts[-1]
    updated = last.model_copy(
        update={
            "status": status,
            "side_effect_committed": side_effect_committed,
        }
    )
    return (*state.tool_attempts[:-1], updated)


_LEGAL_EVENTS = {
    AgentRunStatus.CREATED: {TransitionKind.START_PLANNING},
    AgentRunStatus.PLANNING: {
        TransitionKind.PLAN_READY,
        TransitionKind.CANCEL_REQUESTED,
        TransitionKind.BUDGET_EXHAUSTED,
    },
    AgentRunStatus.AWAITING_APPROVAL: {
        TransitionKind.APPROVED,
        TransitionKind.PLAN_EDITED,
        TransitionKind.REJECTED,
        TransitionKind.APPROVAL_EXPIRED,
        TransitionKind.CANCEL_REQUESTED,
        TransitionKind.STALE_DETECTED,
        TransitionKind.BUDGET_EXHAUSTED,
        TransitionKind.CONTEXT_UNAVAILABLE,
    },
    AgentRunStatus.EXECUTING: {
        TransitionKind.TOOL_STARTED,
        TransitionKind.TOOL_SUCCEEDED,
        TransitionKind.TOOL_FAILED,
        TransitionKind.CANCEL_REQUESTED,
        TransitionKind.STALE_DETECTED,
        TransitionKind.BUDGET_EXHAUSTED,
    },
    AgentRunStatus.VALIDATING: {
        TransitionKind.VALIDATION_SUCCEEDED,
        TransitionKind.VALIDATION_FAILED,
        TransitionKind.CANCEL_REQUESTED,
        TransitionKind.STALE_DETECTED,
        TransitionKind.BUDGET_EXHAUSTED,
    },
    AgentRunStatus.FAILED: {TransitionKind.RECOVERY_STARTED},
    AgentRunStatus.RECOVERING: {
        TransitionKind.RECOVERY_RECONCILED,
        TransitionKind.CANCEL_REQUESTED,
        TransitionKind.BUDGET_EXHAUSTED,
    },
    AgentRunStatus.COMPLETED: set(),
    AgentRunStatus.CANCELLED: set(),
}


# 状态迁移是持久化运行记录的唯一边界；非法事件必须在写入 checkpoint 前被拒绝。
def transition(
    state: AgentRunState,
    event: AgentTransitionEvent,
) -> AgentRunState:
    """依据当前状态和事件执行允许的迁移，并校验审批、预算及结果条件；非法跳转明确拒绝。"""

    if state.status in {AgentRunStatus.COMPLETED, AgentRunStatus.CANCELLED}:
        raise ValueError(f"terminal state cannot transition: {state.status.value}")
    if event.kind not in _LEGAL_EVENTS[state.status]:
        raise ValueError(
            f"illegal transition: {state.status.value} + {event.kind.value}"
        )

    updates: dict[str, Any] = {"event_sequence": state.event_sequence + 1}
    occurred_at = event.occurred_at or datetime.now(UTC)

    if event.kind == TransitionKind.START_PLANNING:
        updates["status"] = AgentRunStatus.PLANNING

    elif event.kind == TransitionKind.PLAN_READY:
        if not event.plan:
            raise ValueError("plan_ready requires at least one step")
        if len(event.plan) > state.budget.max_steps:
            raise ValueError("plan exceeds max_steps budget")
        updates.update(
            plan=event.plan,
            plan_version=state.plan_version + 1,
            current_step_index=0,
            pending_approval=None,
            approvals=(),
            last_error=None,
            status=(
                AgentRunStatus.AWAITING_APPROVAL
                if requires_approval(event.plan[0].risks)
                else AgentRunStatus.EXECUTING
            ),
        )

    elif event.kind in {TransitionKind.PLAN_EDITED, TransitionKind.STALE_DETECTED}:
        updates.update(
            status=AgentRunStatus.PLANNING,
            plan=(),
            current_step_index=0,
            plan_version=state.plan_version + 1,
            pending_approval=None,
            approvals=(),
            last_error=(
                AgentError(
                    code="source_revision_changed",
                    category="stale",
                    retryable=False,
                    safe_message="Source revision changed; replan is required",
                )
                if event.kind == TransitionKind.STALE_DETECTED
                else None
            ),
        )
        if event.new_source_revision:
            updates["source_revision"] = event.new_source_revision

    elif event.kind == TransitionKind.APPROVED:
        call = _current_call(state)
        if event.approval is None or not approval_is_valid(
            state, call, event.approval, now=occurred_at
        ):
            raise ValueError("approval is missing, expired, or does not match")
        updates.update(
            status=AgentRunStatus.EXECUTING,
            pending_approval=event.approval,
            approvals=(*state.approvals, event.approval),
        )

    elif event.kind in {
        TransitionKind.REJECTED,
        TransitionKind.APPROVAL_EXPIRED,
        TransitionKind.CANCEL_REQUESTED,
    }:
        updates.update(
            status=AgentRunStatus.CANCELLED,
            cancel_requested=True,
            pending_approval=None,
        )

    elif event.kind == TransitionKind.TOOL_STARTED:
        call = _current_call(state)
        if state.cancel_requested:
            raise ValueError("cancel requested before side effect")
        if state.usage.tool_calls >= state.budget.max_tool_calls:
            raise ValueError("budget exceeded: tool_calls")
        if requires_approval(call.risks):
            if state.pending_approval is None or not approval_is_valid(
                state, call, state.pending_approval, now=occurred_at
            ):
                raise ValueError("valid approval is required before tool execution")
        updates["tool_attempts"] = (
            *state.tool_attempts,
            ToolAttempt(
                step_id=call.step_id,
                operation=call.operation,
                idempotency_key=call.idempotency_key,
                status=ToolAttemptStatus.RUNNING,
            ),
        )

    elif event.kind == TransitionKind.TOOL_SUCCEEDED:
        usage = _validated_usage(state.usage, event.usage, state.budget)
        updates.update(
            status=AgentRunStatus.VALIDATING,
            usage=usage,
            tool_attempts=_updated_attempts(
                state,
                ToolAttemptStatus.SUCCEEDED,
                side_effect_committed=bool(event.side_effect_committed),
            ),
        )

    elif event.kind == TransitionKind.TOOL_FAILED:
        if event.error is None:
            raise ValueError("tool_failed requires a safe error")
        updates.update(
            status=AgentRunStatus.FAILED,
            last_error=event.error,
            tool_attempts=_updated_attempts(
                state,
                ToolAttemptStatus.FAILED,
                side_effect_committed=bool(event.side_effect_committed),
            ),
        )

    elif event.kind == TransitionKind.VALIDATION_SUCCEEDED:
        if state.current_step_index + 1 >= len(state.plan):
            updates.update(
                status=AgentRunStatus.COMPLETED,
                pending_approval=None,
            )
        else:
            next_step_index = state.current_step_index + 1
            next_call = state.plan[next_step_index]
            updates.update(
                status=(
                    AgentRunStatus.AWAITING_APPROVAL
                    if requires_approval(next_call.risks)
                    else AgentRunStatus.EXECUTING
                ),
                current_step_index=next_step_index,
                pending_approval=None,
            )

    elif event.kind == TransitionKind.VALIDATION_FAILED:
        if event.error is None:
            raise ValueError("validation_failed requires a safe error")
        updates.update(status=AgentRunStatus.FAILED, last_error=event.error)

    elif event.kind == TransitionKind.RECOVERY_STARTED:
        if state.last_error is None or not state.last_error.retryable:
            raise ValueError("failure is not recoverable")
        if not event.checkpoint_id:
            raise ValueError("recovery requires a checkpoint id")
        _validated_usage(state.usage, state.usage, state.budget)
        updates.update(
            status=AgentRunStatus.RECOVERING,
            recovery_from_checkpoint=event.checkpoint_id,
        )

    elif event.kind == TransitionKind.RECOVERY_RECONCILED:
        if event.side_effect_committed is None:
            raise ValueError("recovery must reconcile idempotency outcome")
        if event.side_effect_committed:
            updates.update(
                status=AgentRunStatus.VALIDATING,
                tool_attempts=_updated_attempts(
                    state,
                    ToolAttemptStatus.SUCCEEDED,
                    side_effect_committed=True,
                ),
            )
        else:
            call = _current_call(state)
            updates.update(
                status=(
                    AgentRunStatus.AWAITING_APPROVAL
                    if requires_approval(call.risks)
                    else AgentRunStatus.EXECUTING
                ),
                pending_approval=None,
            )

    elif event.kind == TransitionKind.BUDGET_EXHAUSTED:
        updates.update(
            status=AgentRunStatus.FAILED,
            last_error=AgentError(
                code="run_budget_exhausted",
                category="budget",
                retryable=False,
                safe_message="Agent run budget was exhausted",
            ),
        )

    elif event.kind == TransitionKind.CONTEXT_UNAVAILABLE:
        if event.error is None:
            raise ValueError("context_unavailable requires a safe error")
        updates.update(status=AgentRunStatus.FAILED, last_error=event.error)

    return state.model_copy(update=updates)
