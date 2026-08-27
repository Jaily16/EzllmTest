"""Dependency-free measurement primitives for the Aspect 1 protocol."""

from __future__ import annotations

import math
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field


REQUIRED_METRICS = {
    "approval_bypass_count",
    "approval_bypass_rate",
    "cache_hit_rate",
    "duplicate_side_effect_count",
    "embedding_call_count",
    "estimated_cost_units",
    "input_tokens",
    "latency_p50_ms",
    "latency_p95_ms",
    "model_call_count",
    "otel_overhead_ratio",
    "output_tokens",
    "project_isolation_violation_count",
    "rag_index_build_count",
    "rag_index_reuse_count",
    "rag_mrr",
    "rag_recall_at_k",
    "recovery_success",
    "structured_output_validity",
    "task_success",
    "throughput_tasks_per_second",
    "tool_call_count",
    "tool_selection_accuracy",
    "trajectory_validity",
    "ttfe_ms",
}


class _MeasurementModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class LatencySummary(_MeasurementModel):
    sample_count: int = Field(gt=0)
    latency_p50_ms: float = Field(ge=0)
    latency_p95_ms: float = Field(ge=0)
    ttfe_p50_ms: float = Field(ge=0)
    ttfe_p95_ms: float = Field(ge=0)
    throughput_tasks_per_second: float = Field(ge=0)


class OptionalMetric(_MeasurementModel):
    value: float | None
    reason: str | None


def nearest_rank_percentile(samples: Sequence[float], percentile: int) -> float:
    if not samples:
        raise ValueError("samples are required")
    if not 0 < percentile <= 100:
        raise ValueError("percentile must be in (0, 100]")
    if any(value < 0 or not math.isfinite(value) for value in samples):
        raise ValueError("samples must be finite and non-negative")
    ordered = sorted(samples)
    rank = max(1, math.ceil(percentile / 100 * len(ordered)))
    return ordered[rank - 1]


def summarize_latency(
    *,
    latency_samples_ms: Sequence[float],
    ttfe_samples_ms: Sequence[float],
    completed_count: int,
    elapsed_ms: float,
) -> LatencySummary:
    if len(latency_samples_ms) != len(ttfe_samples_ms):
        raise ValueError("latency and TTFE sample counts must match")
    if completed_count < 0:
        raise ValueError("completed_count must be non-negative")
    if elapsed_ms <= 0:
        raise ValueError("elapsed_ms must be positive")
    return LatencySummary(
        sample_count=len(latency_samples_ms),
        latency_p50_ms=nearest_rank_percentile(latency_samples_ms, 50),
        latency_p95_ms=nearest_rank_percentile(latency_samples_ms, 95),
        ttfe_p50_ms=nearest_rank_percentile(ttfe_samples_ms, 50),
        ttfe_p95_ms=nearest_rank_percentile(ttfe_samples_ms, 95),
        throughput_tasks_per_second=completed_count / (elapsed_ms / 1_000),
    )


def relative_gate_passes(
    baseline: float,
    candidate: float,
    *,
    max_ratio: float,
) -> bool:
    if baseline <= 0 or candidate < 0 or max_ratio <= 0:
        raise ValueError("baseline and max_ratio must be positive")
    return candidate / baseline <= max_ratio


def calculate_otel_overhead(
    *,
    disabled_p95_ms: float,
    enabled_p95_ms: float | None,
    runtime_available: bool,
) -> OptionalMetric:
    if not runtime_available:
        return OptionalMetric(value=None, reason="runtime_not_installed")
    if disabled_p95_ms <= 0:
        raise ValueError("disabled_p95_ms must be positive")
    if enabled_p95_ms is None or enabled_p95_ms < 0:
        raise ValueError("enabled_p95_ms is required when runtime is available")
    return OptionalMetric(
        value=(enabled_p95_ms - disabled_p95_ms) / disabled_p95_ms,
        reason=None,
    )
