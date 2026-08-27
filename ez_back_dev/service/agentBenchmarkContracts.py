"""Strict public-safe contracts for the Aspect 7 offline benchmark."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _BenchmarkModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, str_strip_whitespace=True,
        protected_namespaces=(),
    )


class BenchmarkSuite(str, Enum):
    LEGACY = "legacy"
    AGENT = "agent"
    ALL = "all"


class BenchmarkTelemetryMode(str, Enum):
    DISABLED = "disabled"
    ENABLED = "enabled"
    COMPARE = "compare"


class BenchmarkCaseResult(_BenchmarkModel):
    case_id: str = Field(pattern=r"^[a-z0-9_]+$", max_length=96)
    telemetry: Literal["disabled", "enabled"]
    size: Literal["small", "large"]
    concurrency: Literal[1, 4]
    warmups: Literal[5] = 5
    samples: Literal[30] = 30
    latency_p50_ms: float = Field(ge=0)
    latency_p95_ms: float = Field(ge=0)
    ttfe_p50_ms: float | None = Field(default=None, ge=0)
    ttfe_p95_ms: float | None = Field(default=None, ge=0)
    throughput_tasks_per_second: float = Field(ge=0)
    error_rate: float = Field(ge=0, le=1)
    model_calls: int = Field(ge=0)
    embedding_calls: int = Field(ge=0)
    tool_calls: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cache_hits: int = Field(ge=0)
    safe_first_event: bool


class BenchmarkGate(_BenchmarkModel):
    name: str = Field(pattern=r"^[a-z0-9_]+$")
    status: Literal["pass", "fail", "not_applicable"]
    ratio: float | None = Field(default=None, ge=0)
    limit: float | None = Field(default=None, ge=0)
    reason: str | None = Field(default=None, max_length=128)


class BenchmarkReport(_BenchmarkModel):
    schema_version: Literal[1] = 1
    fixture_version: Literal["iteration4-agent-performance-v1"] = (
        "iteration4-agent-performance-v1"
    )
    suite: BenchmarkSuite
    telemetry_mode: BenchmarkTelemetryMode
    seed: Literal[20260827] = 20260827
    environment: dict[str, str]
    cases: tuple[BenchmarkCaseResult, ...]
    gates: tuple[BenchmarkGate, ...]
    telemetry_export_status: Literal[
        "disabled", "exported", "export_failed", "not_flushed"
    ]
    real_provider_calls: Literal[0] = 0
    real_embedding_calls: Literal[0] = 0
    real_mysql_calls: Literal[0] = 0
    estimated_cost_currency: None = None

    @property
    def passed(self) -> bool:
        return all(gate.status != "fail" for gate in self.gates)
