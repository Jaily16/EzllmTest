"""Strict public-free contracts for the Iteration 4 offline closeout gate."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ACCEPTANCE_PROTOCOL_VERSION = "iteration4-aspect8-v1"
ACCEPTANCE_SEED = 20260827


class AcceptanceSuite(str, Enum):
    JOURNEY = "journey"
    RELIABILITY = "reliability"
    PROTOCOL = "protocol"
    ALL = "all"


class _AcceptanceModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )


class AcceptanceCase(_AcceptanceModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,95}$")
    suite: AcceptanceSuite
    scenario: str = Field(pattern=r"^[a-z0-9][a-z0-9_]{2,95}$")
    expected_status: Literal["completed", "cancelled", "failed", "blocked"]
    expected_trajectory: tuple[str, ...] = Field(min_length=2, max_length=16)

    @model_validator(mode="after")
    def _case_cannot_use_all(self):
        if self.suite is AcceptanceSuite.ALL:
            raise ValueError("acceptance cases cannot use the all suite")
        return self


class AcceptanceDataset(_AcceptanceModel):
    schema_version: Literal[1] = 1
    dataset_id: Literal["iteration4-agent-acceptance-v1"]
    dataset_version: Literal["1.0.0"]
    seed: Literal[20260827] = ACCEPTANCE_SEED
    provider: Literal["deterministic_fake"] = "deterministic_fake"
    projects: tuple[Literal["alpha", "alpine"], Literal["alpha", "alpine"]]
    cases: tuple[AcceptanceCase, ...] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def _dataset_is_isolated_and_unique(self):
        if self.projects != ("alpha", "alpine"):
            raise ValueError("acceptance projects must be the isolated fixed pair")
        ids = [case.id for case in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("acceptance case IDs must be unique")
        return self


class AcceptanceCaseResult(_AcceptanceModel):
    case_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,95}$")
    suite: AcceptanceSuite
    scenario: str = Field(pattern=r"^[a-z0-9][a-z0-9_]{2,95}$")
    passed: bool
    terminal_status: Literal["completed", "cancelled", "failed", "blocked"]
    trajectory: tuple[str, ...] = Field(min_length=2, max_length=16)
    error_code: str | None = Field(default=None, max_length=96)


class AcceptanceMetrics(_AcceptanceModel):
    task_success: float = Field(ge=0, le=1)
    trajectory_validity: float = Field(ge=0, le=1)
    recovery_success: float = Field(ge=0, le=1)
    approval_bypass_count: Literal[0] = 0
    duplicate_side_effect_count: Literal[0] = 0
    project_isolation_violation_count: Literal[0] = 0
    budget_overrun_count: Literal[0] = 0
    unsafe_capability_execution_count: Literal[0] = 0
    sensitive_data_leak_count: Literal[0] = 0
    session_mysql_write_count: Literal[0] = 0
    warm_cache_model_calls: Literal[0] = 0
    warm_cache_embedding_calls: Literal[0] = 0


class AcceptanceEnvironment(_AcceptanceModel):
    protocol_version: Literal["iteration4-aspect8-v1"] = ACCEPTANCE_PROTOCOL_VERSION
    python_version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    operating_system: str = Field(pattern=r"^[A-Za-z0-9_.-]{2,64}$")
    topology: Literal["loopback_redis", "isolated_compose"]
    requirements_sha256: str = Field(pattern=r"^[0-9A-F]{64}$")
    npm_manifest_sha256: str = Field(pattern=r"^[0-9A-F]{64}$")
    npm_lock_sha256: str = Field(pattern=r"^[0-9A-F]{64}$")


class AcceptanceGateDecision(_AcceptanceModel):
    passed: bool
    hard_gate_failures: tuple[str, ...] = ()
    real_model_evaluation: Literal["not_authorized"] = "not_authorized"
    hosted_ci_status: Literal["awaiting_explicit_push"] = "awaiting_explicit_push"


class AcceptanceRunReport(_AcceptanceModel):
    schema_version: Literal[1] = 1
    suite: AcceptanceSuite
    seed: Literal[20260827] = ACCEPTANCE_SEED
    dataset_id: Literal["iteration4-agent-acceptance-v1"]
    dataset_sha256: str = Field(pattern=r"^[0-9A-F]{64}$")
    environment: AcceptanceEnvironment
    results: tuple[AcceptanceCaseResult, ...] = Field(min_length=1, max_length=64)
    metrics: AcceptanceMetrics
    decision: AcceptanceGateDecision
    real_provider_calls: Literal[0] = 0
    real_embedding_calls: Literal[0] = 0
    user_mysql_calls: Literal[0] = 0
    user_project_reads: Literal[0] = 0
    model_currency_cost: Literal[0] = 0
