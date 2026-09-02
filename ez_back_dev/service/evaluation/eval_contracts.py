"""Strict JSON contracts for the offline Iteration 4 Agent evaluation gate."""

from __future__ import annotations

import math
import re
from enum import Enum
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)
from service.agent.contracts import ToolRisk

EVAL_PROTOCOL_VERSION = "iteration4-aspect6-v1"
EVAL_SEED = 20260827


class EvalSuite(str, Enum):
    CORE = "core"
    SECURITY = "security"
    RELIABILITY = "reliability"
    ALL = "all"


class EvalCaseKind(str, Enum):
    TOOL_SELECTION = "tool_selection"
    JOURNEY = "journey"
    ATTACK = "attack"
    RELIABILITY = "reliability"


class _EvalModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )


class EvalCounters(_EvalModel):
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    model_calls: int = Field(default=0, ge=0)
    embedding_calls: int = Field(default=0, ge=0)
    tool_calls: int = Field(default=0, ge=0)
    estimated_cost_units: int = Field(default=0, ge=0)


class EvalExpectation(_EvalModel):
    tool_name: str | None = Field(default=None, max_length=128)
    operation: str | None = Field(default=None, max_length=64)
    risks: tuple[ToolRisk, ...] = ()
    approval: Literal[
        "not_required",
        "required",
        "approved",
        "rejected",
        "expired",
        "invalidated",
        "missing",
    ]
    terminal_status: Literal["completed", "awaiting_approval", "cancelled", "failed", "blocked"]
    retention: Literal["none", "artifact", "session"] = "none"
    trajectory: tuple[str, ...] = Field(min_length=1, max_length=32)
    counters: EvalCounters = Field(default_factory=EvalCounters)
    side_effects: int = Field(default=0, ge=0)
    error_code: str | None = Field(default=None, max_length=128)
    blocked: bool = False
    structured_output_valid: bool = True
    recovery_success: bool | None = None
    artifact_preserved: bool | None = None
    cache_hit: bool | None = None
    rag_recall_at_4: float | None = Field(default=None, ge=0, le=1)
    rag_mrr: float | None = Field(default=None, ge=0, le=1)
    rag_ndcg_at_4: float | None = Field(default=None, ge=0, le=1)
    citation_coverage: float | None = Field(default=None, ge=0, le=1)

    @field_validator("risks")
    @classmethod
    def _risks_are_canonical(cls, value: tuple[ToolRisk, ...]):
        if (
            len(value) != len(set(value))
            or tuple(sorted(value, key=lambda item: item.value)) != value
        ):
            raise ValueError("eval risks must be unique and sorted")
        return value


class EvalCase(_EvalModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{2,95}$")
    suite: EvalSuite
    kind: EvalCaseKind
    scenario: str = Field(pattern=r"^[a-z0-9][a-z0-9_]{2,95}$")
    category: str = Field(pattern=r"^[a-z0-9][a-z0-9_]{2,63}$")
    project_slot: Literal["alpha", "alpine"] = "alpha"
    goal: str | None = Field(default=None, min_length=1, max_length=1_000)
    expected: EvalExpectation

    @model_validator(mode="after")
    def _kind_matches_suite(self):
        allowed = {
            EvalSuite.CORE: {
                EvalCaseKind.TOOL_SELECTION,
                EvalCaseKind.JOURNEY,
            },
            EvalSuite.SECURITY: {EvalCaseKind.ATTACK},
            EvalSuite.RELIABILITY: {EvalCaseKind.RELIABILITY},
        }
        if self.suite is EvalSuite.ALL or self.kind not in allowed[self.suite]:
            raise ValueError("eval case kind does not match its suite")
        return self


class EvalFixtureParent(_EvalModel):
    fixture: str = Field(pattern=r"^[a-zA-Z0-9_.-]+\.json$")
    sha256: str = Field(pattern=r"^[0-9A-F]{64}$")


class EvalDataset(_EvalModel):
    schema_version: Literal[1] = 1
    dataset_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,63}$")
    dataset_version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    seed: Literal[20260827] = EVAL_SEED
    provider: Literal["deterministic_fake"] = "deterministic_fake"
    description: str = Field(min_length=1, max_length=512)
    parent: EvalFixtureParent | None = None
    tasks: tuple[EvalCase, ...] = Field(min_length=1, max_length=256)

    @model_validator(mode="after")
    def _task_ids_are_unique(self):
        ids = [item.id for item in self.tasks]
        if len(ids) != len(set(ids)):
            raise ValueError("eval case IDs must be unique")
        suites = {item.suite for item in self.tasks}
        if len(suites) != 1:
            raise ValueError("one eval fixture must contain exactly one suite")
        return self


class EvalObservedOutcome(_EvalModel):
    tool_name: str | None = Field(default=None, max_length=128)
    operation: str | None = Field(default=None, max_length=64)
    risks: tuple[ToolRisk, ...] = ()
    approval: str = Field(min_length=1, max_length=32)
    terminal_status: str = Field(min_length=1, max_length=32)
    retention: str = Field(min_length=1, max_length=16)
    trajectory: tuple[str, ...] = Field(min_length=1, max_length=32)
    counters: EvalCounters = Field(default_factory=EvalCounters)
    side_effects: int = Field(default=0, ge=0)
    error_code: str | None = Field(default=None, max_length=128)
    blocked: bool = False
    structured_output_valid: bool = True
    recovery_success: bool | None = None
    artifact_preserved: bool | None = None
    cache_hit: bool | None = None
    rag_recall_at_4: float | None = Field(default=None, ge=0, le=1)
    rag_mrr: float | None = Field(default=None, ge=0, le=1)
    rag_ndcg_at_4: float | None = Field(default=None, ge=0, le=1)
    citation_coverage: float | None = Field(default=None, ge=0, le=1)
    logical_latency_ms: float = Field(default=1, ge=0)
    ttfe_ms: float = Field(default=0.25, ge=0)
    approval_bypass_count: int = Field(default=0, ge=0)
    duplicate_side_effect_count: int = Field(default=0, ge=0)
    project_isolation_violation_count: int = Field(default=0, ge=0)
    budget_overrun_count: int = Field(default=0, ge=0)
    unsafe_capability_execution_count: int = Field(default=0, ge=0)
    sensitive_data_leak_count: int = Field(default=0, ge=0)


class EvalCaseResult(_EvalModel):
    case_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{2,95}$")
    suite: EvalSuite
    passed: bool
    trajectory: tuple[str, ...] = Field(min_length=1, max_length=32)
    terminal_status: str = Field(min_length=1, max_length=32)
    tool_name: str | None = Field(default=None, max_length=128)
    operation: str | None = Field(default=None, max_length=64)
    error_code: str | None = Field(default=None, max_length=128)
    counters: EvalCounters = Field(default_factory=EvalCounters)
    side_effects: int = Field(default=0, ge=0)
    task_success: bool = False
    trajectory_valid: bool = False
    tool_selection_correct: bool = False
    structured_output_correct: bool = False
    recovery_success: bool | None = None
    blocked: bool = False
    cache_hit: bool | None = None
    rag_recall_at_4: float | None = Field(default=None, ge=0, le=1)
    rag_mrr: float | None = Field(default=None, ge=0, le=1)
    rag_ndcg_at_4: float | None = Field(default=None, ge=0, le=1)
    citation_coverage: float | None = Field(default=None, ge=0, le=1)
    logical_latency_ms: float = Field(default=1, ge=0)
    ttfe_ms: float = Field(default=0.25, ge=0)
    approval_bypass_count: int = Field(default=0, ge=0)
    duplicate_side_effect_count: int = Field(default=0, ge=0)
    project_isolation_violation_count: int = Field(default=0, ge=0)
    budget_overrun_count: int = Field(default=0, ge=0)
    unsafe_capability_execution_count: int = Field(default=0, ge=0)
    sensitive_data_leak_count: int = Field(default=0, ge=0)


class EvalMetric(_EvalModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]{2,95}$")
    value: float | None
    numerator: int | None = Field(default=None, ge=0)
    denominator: int | None = Field(default=None, ge=0)
    reason: str | None = Field(default=None, max_length=128)

    @field_validator("value")
    @classmethod
    def _value_is_finite(cls, value: float | None):
        if value is not None and not math.isfinite(value):
            raise ValueError("eval metric values must be finite")
        return value

    @model_validator(mode="after")
    def _na_has_reason(self):
        if (self.value is None) != (self.reason is not None):
            raise ValueError("N/A eval metrics require exactly one reason")
        return self


class EvalEnvironment(_EvalModel):
    protocol_version: Literal["iteration4-aspect6-v1"] = EVAL_PROTOCOL_VERSION
    git_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    python_version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    operating_system: str = Field(pattern=r"^[A-Za-z0-9_.-]{2,64}$")
    topology: Literal["in_memory", "loopback_redis"]
    requirements_sha256: str = Field(pattern=r"^[0-9A-F]{64}$")
    npm_manifest_sha256: str = Field(pattern=r"^[0-9A-F]{64}$")
    npm_lock_sha256: str = Field(pattern=r"^[0-9A-F]{64}$")


class EvalGateDecision(_EvalModel):
    passed: bool
    hard_gate_failures: tuple[str, ...] = ()
    performance_gate: Literal["N/A"] = "N/A"
    performance_reason: Literal["controlled_performance_and_telemetry_deferred_to_aspect7"] = (
        "controlled_performance_and_telemetry_deferred_to_aspect7"
    )
    real_model_evaluation: Literal["not_authorized"] = "not_authorized"


class EvalRunReport(_EvalModel):
    schema_version: Literal[1] = 1
    suite: EvalSuite
    seed: Literal[20260827] = EVAL_SEED
    dataset_ids: tuple[str, ...] = Field(min_length=1, max_length=3)
    dataset_sha256: tuple[str, ...] = Field(min_length=1, max_length=3)
    environment: EvalEnvironment
    results: tuple[EvalCaseResult, ...] = Field(min_length=1, max_length=512)
    metrics: tuple[EvalMetric, ...] = Field(min_length=1, max_length=128)
    decision: EvalGateDecision

    @field_validator("dataset_sha256")
    @classmethod
    def _dataset_hashes_are_canonical(cls, value: tuple[str, ...]):
        if any(re.fullmatch(r"[0-9A-F]{64}", item) is None for item in value):
            raise ValueError("dataset hashes must be uppercase SHA-256 values")
        return value


_FORBIDDEN_REPORT_KEYS = {
    "authorization",
    "completion",
    "cookie",
    "credential",
    "document_body",
    "password",
    "project_id",
    "prompt",
    "raw_document",
    "reasoning",
    "redis_url",
    "scratchpad",
    "secret",
    "traceback",
}
_WINDOWS_PATH = re.compile(r"(?i)\b[a-z]:\\")
_FORBIDDEN_REPORT_VALUES = (
    "SENSITIVE_DOCUMENT_SENTINEL",
    "FAKE_API_KEY_VALUE",
    "redis://",
    "rediss://",
)


def assert_safe_eval_payload(value: Any, path: str = "report") -> None:
    """Reject raw authority, secrets, bodies, and local paths in Eval output."""

    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    if isinstance(value, dict):
        for key, nested in value.items():
            if not isinstance(key, str):
                raise ValueError(f"unsafe eval payload at {path}: non-string key")
            if key.strip().lower() in _FORBIDDEN_REPORT_KEYS:
                raise ValueError(f"unsafe eval payload at {path}: forbidden key")
            assert_safe_eval_payload(nested, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            assert_safe_eval_payload(nested, f"{path}[{index}]")
    elif isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"unsafe eval payload at {path}: non-finite number")
    elif isinstance(value, str):
        if _WINDOWS_PATH.search(value) or any(
            marker.lower() in value.lower() for marker in _FORBIDDEN_REPORT_VALUES
        ):
            raise ValueError(f"unsafe eval payload at {path}: sensitive value")
