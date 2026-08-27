from __future__ import annotations

from service.agentEvalContracts import EvalCaseKind, EvalSuite
from service.agentEvalRunner import (
    CORE_DATASET_PATH,
    RELIABILITY_DATASET_PATH,
    SECURITY_DATASET_PATH,
    load_eval_dataset,
)


def test_core_v2_has_exact_tool_and_journey_matrix():
    dataset = load_eval_dataset(CORE_DATASET_PATH)
    assert dataset.schema_version == 1
    assert dataset.dataset_version == "2.0.0"
    assert dataset.seed == 20260827
    assert dataset.provider == "deterministic_fake"
    assert len(dataset.tasks) == 39
    assert sum(case.kind is EvalCaseKind.TOOL_SELECTION for case in dataset.tasks) == 22
    assert sum(case.kind is EvalCaseKind.JOURNEY for case in dataset.tasks) == 17
    assert {case.suite for case in dataset.tasks} == {EvalSuite.CORE}


def test_security_and_reliability_fixtures_cover_every_required_family():
    security = load_eval_dataset(SECURITY_DATASET_PATH)
    reliability = load_eval_dataset(RELIABILITY_DATASET_PATH)

    assert {case.category for case in security.tasks} == {
        "approval_tamper",
        "arbitrary_capability",
        "data_leak",
        "planner_authority",
        "project_isolation",
        "prompt_injection",
        "protocol_boundary",
        "serialization",
    }
    assert {case.category for case in reliability.tasks} == {
        "active_slot",
        "approval_replay",
        "cache",
        "cancel",
        "crash_recovery",
        "evidence_rebuild",
        "lease_fencing",
        "redis_loss",
        "replay",
        "stale",
    }
    assert len(reliability.tasks) == 18
