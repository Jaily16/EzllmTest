from __future__ import annotations

import os

import pytest

from service.agentEvalContracts import EvalSuite
from service.agentEvalRunner import run_eval


def test_reliability_matrix_passes_against_loopback_redis():
    redis_url = os.getenv("EZLLM_TEST_REDIS_URL")
    if not redis_url:
        pytest.skip("EZLLM_TEST_REDIS_URL is not configured")

    report = run_eval(EvalSuite.RELIABILITY, redis_url=redis_url)
    assert len(report.results) == 18
    assert report.decision.passed
    assert all(item.passed for item in report.results)
    metrics = {metric.name: metric.value for metric in report.metrics}
    assert metrics["recovery_success"] == 1.0
    assert metrics["duplicate_side_effect_count"] == 0
    assert metrics["approval_bypass_count"] == 0
    assert metrics["project_isolation_violation_count"] == 0
    assert metrics["model_call_count"] == 0
    assert metrics["embedding_call_count"] == 0


@pytest.mark.parametrize(
    "url",
    [
        "redis://example.com:6379/0",
        "redis://user:password@127.0.0.1:6379/0",
        "rediss://127.0.0.1:6379/0",
    ],
)
def test_reliability_rejects_remote_credentialed_or_tls_urls(url):
    with pytest.raises(ValueError, match="loopback Redis"):
        run_eval(EvalSuite.RELIABILITY, redis_url=url)
