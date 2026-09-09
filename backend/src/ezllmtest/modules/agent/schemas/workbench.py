# 工作台公开 DTO 只暴露受限状态、摘要和证据；类 docstring 保持协议描述稳定。
"""Public, redacted contracts for the local Aspect 4 Agent workbench."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
import os
from ezllmtest.platform import configuration as runtime_values
from typing import Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_validator,
    model_validator,
)

from ezllmtest.platform.ai.gateway import list_model_labels
from ezllmtest.platform.configuration_schema import BUDGET_DEFAULTS, positive_integer
from ezllmtest.modules.agent.domain.contracts import AgentError, AgentRunStatus, RunBudget, ToolRisk, UsageCounters
from ezllmtest.modules.agent.runtime.state.contracts import AGENT_GRAPH_VERSION
from ezllmtest.modules.agent.runtime.tools.registry import DEFAULT_TOOL_REGISTRY
from ezllmtest.modules.agent.runtime.tools.schemas import ToolRetrievalEvidence
from ezllmtest.platform.telemetry.agent_telemetry import telemetry_public_status


AGENT_API_SCHEMA_VERSION = 1
AGENT_SCOPE_VERSION = "iteration4-aspect4-v1"
AGENT_ACTOR_ID = "local-workbench"


class _PublicModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        protected_namespaces=(),
    )


class AgentBudgetPreset(str, Enum):
    FOCUSED = "focused"
    STANDARD = "standard"


_PRESET_SHAPE = {
    AgentBudgetPreset.FOCUSED: {
        "max_steps": 3,
        "max_elapsed_ms": 20 * 60 * 1_000,
        "max_model_calls": 12,
        "max_embedding_calls": 6,
    },
    AgentBudgetPreset.STANDARD: {
        "max_steps": 8,
        "max_elapsed_ms": 45 * 60 * 1_000,
        "max_model_calls": 32,
        "max_embedding_calls": 16,
    },
}


def budget_for_preset(preset: AgentBudgetPreset | str) -> RunBudget:
    """把允许的预算档位映射为明确运行上限，未知档位不推测额度。"""
    selected = AgentBudgetPreset(preset)
    shape = _PRESET_SHAPE[selected]
    # These limits belong to a whole run, not to the current workflow catalog.
    prefix = f"AGENT_{selected.value.upper()}_MAX_"
    input_name, output_name = prefix + "INPUT_TOKENS", prefix + "OUTPUT_TOKENS"
    input_tokens = positive_integer(input_name, runtime_values.get(input_name, str(BUDGET_DEFAULTS[input_name])))
    output_tokens = positive_integer(output_name, runtime_values.get(output_name, str(BUDGET_DEFAULTS[output_name])))
    return RunBudget(
        max_steps=shape["max_steps"],
        max_elapsed_ms=shape["max_elapsed_ms"],
        max_input_tokens=input_tokens,
        max_output_tokens=output_tokens,
        max_model_calls=shape["max_model_calls"],
        max_embedding_calls=shape["max_embedding_calls"],
        max_tool_calls=shape["max_steps"],
        max_estimated_cost_units=input_tokens + output_tokens,
    )


class AgentBudgetRemaining(_PublicModel):
    max_steps: int = Field(ge=0)
    max_elapsed_ms: int = Field(ge=0)
    max_input_tokens: int = Field(ge=0)
    max_output_tokens: int = Field(ge=0)
    max_model_calls: int = Field(ge=0)
    max_embedding_calls: int = Field(ge=0)
    max_tool_calls: int = Field(ge=0)
    max_estimated_cost_units: int = Field(ge=0)


class AgentBudgetView(_PublicModel):
    preset: AgentBudgetPreset
    limits: RunBudget
    usage: UsageCounters
    remaining: AgentBudgetRemaining
    cost_unit: Literal["synthetic_test_unit"] = "synthetic_test_unit"

    @classmethod
    def from_usage(
        cls,
        preset: AgentBudgetPreset,
        usage: UsageCounters,
        *,
        limits: RunBudget,
    ) -> "AgentBudgetView":
        # Old runs retain their creation-time ledger and approval budgets.
        """将预算上限和已用量投影为工作台可见信息，不暴露 Redis 账本内容。"""
        return cls(
            preset=preset,
            limits=limits,
            usage=usage,
            remaining=AgentBudgetRemaining(
                max_steps=max(0, limits.max_steps - usage.steps),
                max_elapsed_ms=max(0, limits.max_elapsed_ms - usage.elapsed_ms),
                max_input_tokens=max(
                    0, limits.max_input_tokens - usage.input_tokens
                ),
                max_output_tokens=max(
                    0, limits.max_output_tokens - usage.output_tokens
                ),
                max_model_calls=max(
                    0, limits.max_model_calls - usage.model_calls
                ),
                max_embedding_calls=max(
                    0, limits.max_embedding_calls - usage.embedding_calls
                ),
                max_tool_calls=max(
                    0, limits.max_tool_calls - usage.tool_calls
                ),
                max_estimated_cost_units=max(
                    0,
                    limits.max_estimated_cost_units
                    - usage.estimated_cost_units,
                ),
            ),
        )


class AgentRunCreateRequest(_PublicModel):
    goal: str = Field(min_length=1, max_length=4_000)
    model_label: str = Field(min_length=1, max_length=128)
    budget_preset: AgentBudgetPreset = AgentBudgetPreset.FOCUSED

    @field_validator("model_label")
    @classmethod
    def _known_model(cls, value: str) -> str:
        """创建运行前核验模型标签属于注册表，不接受任意 provider 名称。"""
        if value not in list_model_labels():
            raise ValueError("unsupported public model label")
        return value


class AgentApprovalRequest(_PublicModel):
    decision: Literal["approved", "rejected"]
    expected_plan_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class AgentEditRequest(_PublicModel):
    goal: str = Field(min_length=1, max_length=4_000)
    expected_plan_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


_PUBLIC_FORBIDDEN_KEYS = frozenset(
    {
        "api_key",
        "authorization",
        "chain_of_thought",
        "completion",
        "cookie",
        "credential",
        "document_body",
        "document_content",
        "idempotency_key",
        "nonce",
        "password",
        "prompt",
        "raw_document",
        "reasoning",
        "scratchpad",
        "secret",
        "traceback",
    }
)


def _validate_public_json(value: JsonValue, path: str = "value") -> None:
    """递归约束工作台公开数据，禁止运行秘密或不安全对象进入响应。"""
    if isinstance(value, dict):
        for key, nested in value.items():
            if key.strip().lower() in _PUBLIC_FORBIDDEN_KEYS:
                raise ValueError(f"forbidden public key: {path}.{key}")
            _validate_public_json(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _validate_public_json(nested, f"{path}[{index}]")


class AgentContextBindingView(_PublicModel):
    payload_field: str = Field(min_length=1, max_length=64)
    source_operation: str = Field(min_length=1, max_length=64)
    artifact_key: str = Field(min_length=1, max_length=128)
    source_revision: str = Field(min_length=1, max_length=128)
    result_path: tuple[str, ...] = ()
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class AgentPlanStepView(_PublicModel):
    step_id: str = Field(min_length=1, max_length=128)
    operation: str = Field(min_length=1, max_length=64)
    arguments: dict[str, JsonValue] = Field(default_factory=dict)
    risks: tuple[ToolRisk, ...] = Field(min_length=1)
    model_label: str = Field(min_length=1, max_length=128)
    retention: Literal["artifact", "session"]
    current: bool = False
    context_bindings: tuple[AgentContextBindingView, ...] = ()

    @field_validator("arguments")
    @classmethod
    def _safe_arguments(cls, value: dict[str, JsonValue]):
        """递归检查计划参数可公开性，越界 JSON 内容不能进入工作台 DTO。"""
        _validate_public_json(value, "arguments")
        return value


class AgentApprovalView(_PublicModel):
    plan_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    plan_version: int = Field(ge=1)
    step_id: str = Field(min_length=1, max_length=128)
    operation: str = Field(min_length=1, max_length=64)
    risks: tuple[ToolRisk, ...] = Field(min_length=1)
    expires_at: AwareDatetime
    expired: bool


class AgentStepEvidence(_PublicModel):
    schema_version: Literal[1] = 1
    step_id: str = Field(min_length=1, max_length=128)
    operation: str = Field(min_length=1, max_length=64)
    retention: Literal["artifact", "session"]
    status: Literal["success", "cancelled", "stale", "error"]
    saved: bool = False
    from_cache: bool = False
    source_revision: str | None = Field(default=None, max_length=128)
    artifact_key: str | None = Field(default=None, max_length=128)
    workspace_route: str | None = Field(default=None, max_length=64)
    session_result: JsonValue | None = None
    usage: UsageCounters
    error_code: str | None = Field(default=None, max_length=128)
    safe_message: str | None = Field(default=None, max_length=512)
    retrieval_evidence: ToolRetrievalEvidence | None = None

    @field_validator("session_result")
    @classmethod
    def _safe_result(cls, value: JsonValue | None):
        """只允许通过公开 JSON 校验的会话结果进入证据视图。"""
        if value is not None:
            _validate_public_json(value, "session_result")
        return value

    @model_validator(mode="after")
    def _retention_matches_result(self):
        """核验结果状态与保留方式一致，不把 session-only 或失败结果标记为已持久化。"""
        if self.retention == "artifact" and self.session_result is not None:
            raise ValueError("persisted evidence cannot duplicate artifact content")
        return self


class AgentTimelineEvent(_PublicModel):
    schema_version: Literal[1] = 1
    sequence: int = Field(ge=1)
    kind: Literal[
        "queued",
        "planning",
        "approval_required",
        "approval_submitted",
        "replanning",
        "cancel_requested",
        "executing",
        "progress",
        "tool_succeeded",
        "tool_failed",
        "stale",
        "recovering",
        "completed",
        "cancelled",
        "failed",
    ]
    occurred_at: AwareDatetime
    status: AgentRunStatus
    step_id: str | None = Field(default=None, max_length=128)
    operation: str | None = Field(default=None, max_length=64)
    stage: str | None = Field(default=None, max_length=128)
    label: str | None = Field(default=None, max_length=512)
    percent: float | None = Field(default=None, ge=0, le=100)
    saved: bool | None = None
    from_cache: bool | None = None
    artifact_key: str | None = Field(default=None, max_length=128)
    error_code: str | None = Field(default=None, max_length=128)
    safe_message: str | None = Field(default=None, max_length=512)


class AgentRunSummary(_PublicModel):
    run_id: str = Field(min_length=1, max_length=128)
    thread_id: str = Field(min_length=1, max_length=128)
    goal: str = Field(min_length=1, max_length=4_000)
    status: AgentRunStatus
    model_label: str = Field(min_length=1, max_length=128)
    budget_preset: AgentBudgetPreset
    created_at: AwareDatetime
    active: bool


class AgentRunList(_PublicModel):
    runs: tuple[AgentRunSummary, ...]
    active_thread_id: str | None = Field(default=None, max_length=128)
    next_cursor: int | None = Field(default=None, ge=1)


class AgentRunView(_PublicModel):
    schema_version: Literal[1] = 1
    run_id: str = Field(min_length=1, max_length=128)
    thread_id: str = Field(min_length=1, max_length=128)
    goal: str = Field(min_length=1, max_length=4_000)
    status: AgentRunStatus
    source_revision: str = Field(min_length=1, max_length=128)
    created_at: AwareDatetime
    deadline_at: AwareDatetime
    expires_at: AwareDatetime
    model_label: str = Field(min_length=1, max_length=128)
    budget: AgentBudgetView
    plan_version: int = Field(ge=0)
    current_step_index: int = Field(ge=0)
    plan: tuple[AgentPlanStepView, ...] = ()
    approval: AgentApprovalView | None = None
    evidence: tuple[AgentStepEvidence, ...] = ()
    last_error: AgentError | None = None
    last_event_sequence: int = Field(ge=0)
    worker_available: bool
    active: bool
    can_approve: bool
    can_edit: bool
    can_cancel: bool
    can_recover: bool
    trace_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    trace_status: Literal["not_instrumented", "instrumented"] = (
        "not_instrumented"
    )


WORKSPACE_ROUTE_BY_OPERATION = {
    "project_analysis": "/plan",
    "unit_menu": "/unit",
    "unit_info": "/unit",
    "unit_case": "/unit",
    "integration_menu": "/integration",
    "integration_info": "/integration",
    "integration_case": "/integration",
    "api_info": "/api",
    "api_case": "/api",
    "ui_info": "/ui",
    "ui_case": "/ui",
    "db_info": "/database",
    "db_case": "/database",
    "functional_info": "/functional",
    "functional_case": "/functional",
    "nonfunctional_info": "/nfunctional",
    "nonfunctional_case": "/nfunctional",
    "acceptance_info": "/acceptance",
    "acceptance_case": "/acceptance",
}


def public_capabilities() -> dict[str, JsonValue]:
    """生成工作台支持的静态能力说明，公开列表不构成真实模型或 worker 就绪证明。"""
    telemetry = telemetry_public_status()
    return {
        "schema_version": AGENT_API_SCHEMA_VERSION,
        "graph_version": AGENT_GRAPH_VERSION,
        "scope_version": AGENT_SCOPE_VERSION,
        "models": list_model_labels(),
        "budget_presets": [
            {
                "name": preset.value,
                "budget": budget_for_preset(preset).model_dump(mode="json"),
                "cost_unit": "synthetic_test_unit",
            }
            for preset in AgentBudgetPreset
        ],
        "risks": [risk.value for risk in ToolRisk],
        "single_agent": True,
        "chain_of_thought": False,
        "trace_status": telemetry["trace_status"],
        "telemetry": telemetry,
        "retrieval": {
            "strategy": "dense_v1",
            "policy_version": "iteration4-aspect5-v1",
            "citation_mode": "metadata_only",
            "rerank_enabled": False,
            "agent_only": True,
        },
    }
