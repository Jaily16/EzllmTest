import json
import os

import pytest

from service.agentAcceptanceContracts import AcceptanceSuite
from service.agentAcceptanceRunner import run_acceptance
from service.agentEvalRunner import _environment, validate_loopback_redis_url


REDIS_URL = os.getenv("EZLLM_TEST_REDIS_URL")


def test_acceptance_all_is_deterministic_safe_and_passes():
    if not REDIS_URL:
        pytest.skip("loopback Redis is required")
    first = run_acceptance(AcceptanceSuite.ALL, redis_url=REDIS_URL)
    second = run_acceptance(AcceptanceSuite.ALL, redis_url=REDIS_URL)
    assert first.decision.passed is True
    assert len(first.results) == 18
    assert all(result.passed for result in first.results)
    assert first.metrics.task_success == 1
    assert first.metrics.trajectory_validity == 1
    assert first.metrics.recovery_success == 1
    assert first.metrics.approval_bypass_count == 0
    assert first.metrics.duplicate_side_effect_count == 0
    assert first.metrics.project_isolation_violation_count == 0
    assert first.metrics.budget_overrun_count == 0
    assert first.metrics.unsafe_capability_execution_count == 0
    assert first.metrics.sensitive_data_leak_count == 0
    assert first.metrics.warm_cache_model_calls == 0
    assert first.metrics.warm_cache_embedding_calls == 0
    assert [x.model_dump() for x in first.results] == [
        x.model_dump() for x in second.results
    ]

    rendered = json.dumps(first.model_dump(mode="json"), ensure_ascii=False)
    for forbidden in (
        "reasoning_delta",
        "traceparent",
        "redis://",
        "DATABASE_URL",
        "BEGIN PRIVATE KEY",
        "C:\\\\",
    ):
        assert forbidden not in rendered


def test_acceptance_suite_filtering_is_exact():
    if not REDIS_URL:
        pytest.skip("loopback Redis is required")
    report = run_acceptance(AcceptanceSuite.PROTOCOL, redis_url=REDIS_URL)
    assert report.suite is AcceptanceSuite.PROTOCOL
    assert len(report.results) == 5
    assert {item.suite for item in report.results} == {AcceptanceSuite.PROTOCOL}


@pytest.mark.parametrize(
    "url",
    [
        "redis://example.invalid:6379/0",
        "redis://user:secret@127.0.0.1:6379/0",
        "rediss://127.0.0.1:6379/0",
    ],
)
def test_acceptance_rejects_remote_or_credentialed_redis(url):
    with pytest.raises(ValueError, match="loopback Redis"):
        run_acceptance(AcceptanceSuite.ALL, redis_url=url)


def test_explicit_isolated_compose_mode_allows_only_redis_service(monkeypatch):
    monkeypatch.setenv("ASPECT8_ACCEPTANCE_TOPOLOGY", "isolated_compose")
    assert validate_loopback_redis_url("redis://redis:6379/0") == "redis://redis:6379/0"
    with pytest.raises(ValueError, match="loopback Redis"):
        validate_loopback_redis_url("redis://example.invalid:6379/0")


def test_runtime_image_without_git_uses_frozen_baseline_revision(monkeypatch):
    monkeypatch.setattr(
        "service.agentEvalRunner.subprocess.run",
        lambda *args, **kwargs: (_ for _ in ()).throw(FileNotFoundError()),
    )
    assert _environment("loopback_redis").git_revision == (
        "3c49e864a523a4af4c0f3efd4f845e8ce7b1caed"
    )
