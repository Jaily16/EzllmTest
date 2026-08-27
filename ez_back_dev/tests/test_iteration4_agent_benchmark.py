import json
from pathlib import Path

import pytest

from service.agentMeasurement import (
    REQUIRED_METRICS,
    calculate_otel_overhead,
    nearest_rank_percentile,
    relative_gate_passes,
    summarize_latency,
)


DATASET_PATH = (
    Path(__file__).parent / "fixtures" / "iteration4_agent_eval_v1.json"
)


def test_versioned_synthetic_dataset_covers_the_required_matrix():
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))

    assert dataset["schema_version"] == 1
    assert dataset["dataset_version"] == "1.0.0"
    assert dataset["seed"] == 20260827
    assert dataset["provider"] == "deterministic_fake"
    assert len(dataset["projects"]) == 2
    assert {project["project_id"] for project in dataset["projects"]} == {
        "synthetic-alpha",
        "synthetic-alpine",
    }
    assert {task["scenario"] for task in dataset["tasks"]} == {
        "approval_bypass_attempt",
        "approval_expired",
        "approval_rejected",
        "cancel_before_side_effect",
        "cross_project_isolation",
        "exact_cache_hit",
        "failed_tool_preserves_artifact",
        "first_preliminary_analysis",
        "invalid_structured_output",
        "persisted_ui_case",
        "rag_revision_reuse",
        "read_only_status",
        "recover_after_side_effect",
        "regenerate_ui_case",
        "revision_change_reapproval",
        "session_only_unit_case",
        "warm_rag_cache_hit",
    }
    assert all(task["project_id"].startswith("synthetic-") for task in dataset["tasks"])
    assert all("expected" in task for task in dataset["tasks"])


def test_metric_dictionary_is_complete():
    assert REQUIRED_METRICS == {
        "approval_bypass_rate",
        "approval_bypass_count",
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


def test_nearest_rank_latency_and_throughput_are_deterministic():
    samples = list(range(1, 31))
    summary = summarize_latency(
        latency_samples_ms=samples,
        ttfe_samples_ms=[value / 2 for value in samples],
        completed_count=30,
        elapsed_ms=60,
    )

    assert nearest_rank_percentile(samples, 50) == 15
    assert nearest_rank_percentile(samples, 95) == 29
    assert summary.latency_p50_ms == 15
    assert summary.latency_p95_ms == 29
    assert summary.ttfe_p50_ms == 7.5
    assert summary.throughput_tasks_per_second == 500


def test_relative_gates_never_claim_an_unmeasured_improvement():
    assert relative_gate_passes(100, 114.9, max_ratio=1.15)
    assert not relative_gate_passes(100, 115.1, max_ratio=1.15)
    with pytest.raises(ValueError, match="positive"):
        relative_gate_passes(0, 0, max_ratio=1.15)


def test_otel_overhead_is_na_until_a_real_runtime_is_available():
    unavailable = calculate_otel_overhead(
        disabled_p95_ms=100,
        enabled_p95_ms=None,
        runtime_available=False,
    )
    assert unavailable.value is None
    assert unavailable.reason == "runtime_not_installed"

    measured = calculate_otel_overhead(
        disabled_p95_ms=100,
        enabled_p95_ms=104,
        runtime_available=True,
    )
    assert measured.value == pytest.approx(0.04)
    assert measured.reason is None
