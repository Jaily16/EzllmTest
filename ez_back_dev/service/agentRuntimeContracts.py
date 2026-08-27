"""Strict, JSON-only contracts for the Aspect 3 Agent runtime."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    model_validator,
)

from service.agentContracts import (
    AgentRunState,
    ApprovalBinding,
    ApprovalDecision,
    ToolRisk,
)
from service.agentToolSchemas import ToolExecutionResult
from service.agentTelemetry import TraceCarrier


AGENT_GRAPH_VERSION = "iteration4-aspect3-v1"


class _RuntimeModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )


class ProjectObservation(_RuntimeModel):
    """Safe status facts; never includes project documents or prompts."""

    setup_stage: str = Field(min_length=1, max_length=64)
    analysis_ready: bool
    workflow_stage: str = Field(min_length=1, max_length=64)
    completed_operations: tuple[str, ...] = ()
    stale_operations: tuple[str, ...] = ()
    source_revision: str | None = Field(default=None, max_length=128)


class ApprovalRequest(_RuntimeModel):
    schema_version: Literal[1] = 1
    run_id: str = Field(min_length=1, max_length=128)
    plan_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    plan_version: int = Field(ge=1)
    step_id: str = Field(min_length=1, max_length=128)
    operation: str = Field(min_length=1, max_length=64)
    risks: tuple[ToolRisk, ...] = Field(min_length=1)
    expires_at: AwareDatetime


class ApprovalResume(_RuntimeModel):
    """Resume data accepted only after trusted-host validation."""

    schema_version: Literal[1] = 1
    decision: ApprovalDecision
    expected_plan_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    binding: ApprovalBinding | None = None
    edited_goal: str | None = Field(default=None, min_length=1, max_length=4_000)

    @model_validator(mode="after")
    def _decision_payload_is_coherent(self):
        if self.decision is ApprovalDecision.APPROVED and self.binding is None:
            raise ValueError("approved resume requires a trusted binding")
        if self.decision is ApprovalDecision.EDITED and self.edited_goal is None:
            raise ValueError("edited resume requires an edited goal")
        if self.decision is not ApprovalDecision.EDITED and self.edited_goal is not None:
            raise ValueError("edited_goal is only valid for edited decisions")
        if self.decision is not ApprovalDecision.APPROVED and self.binding is not None:
            raise ValueError("binding is only valid for approved decisions")
        return self


class AgentGraphEnvelope(_RuntimeModel):
    schema_version: Literal[1] = 1
    graph_version: Literal["iteration4-aspect3-v1"] = AGENT_GRAPH_VERSION
    run_state: AgentRunState
    started_at: AwareDatetime
    deadline_at: AwareDatetime
    planner_model: str = Field(min_length=1, max_length=128)
    execution_model: str = Field(min_length=1, max_length=128)
    trace_carrier: TraceCarrier | None = None
    observation: ProjectObservation | None = None
    approval_request: ApprovalRequest | None = None
    tool_result: ToolExecutionResult | None = None
    session_result_ref: str | None = Field(default=None, max_length=256)
    recovery_requested: bool = False
    safe_runtime_data: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _temporal_and_revision_binding(self):
        if self.deadline_at <= self.started_at:
            raise ValueError("deadline must follow the absolute start time")
        if (
            self.observation is not None
            and self.observation.source_revision is not None
            and self.observation.source_revision != self.run_state.source_revision
        ):
            raise ValueError("observation revision does not match the run")
        return self


def utc_timestamp(value: datetime) -> str:
    """Return an ISO timestamp without introducing a free-form log field."""

    return value.isoformat()
