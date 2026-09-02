from __future__ import annotations

import json
import os

from app.agentBenchmark import build_parser, main
from service.agentBenchmarkContracts import BenchmarkReport
from service.agentBenchmarkRunner import run_benchmark


def test_benchmark_cli_has_only_fixed_safe_switches(capsys):
    parser = build_parser()
    options = {
        option for action in parser._actions for option in action.option_strings
    }
    assert options == {"-h", "--help", "--suite", "--telemetry", "--format"}
    assert not {
        "--provider", "--model", "--project", "--redis-url", "--output",
        "--dataset", "--host",
    } & options
    # This exercises a real wall-clock gate. A busy shared host may legitimately
    # return exit 1; the CLI contract is the report and its honest exit code,
    # not a fabricated timing pass inside pytest.
    exit_code = main(["--suite", "legacy", "--telemetry", "disabled", "--format", "json"])
    assert exit_code in {0, 1}
    payload = json.loads(capsys.readouterr().out)
    report = BenchmarkReport.model_validate(payload)
    assert exit_code == (0 if report.passed else 1)
    assert report.real_provider_calls == 0
    assert report.real_embedding_calls == 0
    assert report.real_mysql_calls == 0
    rendered = json.dumps(payload, sort_keys=True).lower()
    for forbidden in (
        "prompt", "completion", "reasoning", "redis://", "database_url",
        "project_id", "traceback",
    ):
        assert forbidden not in rendered


def test_agent_benchmark_requires_credential_free_loopback_redis(monkeypatch):
    monkeypatch.delenv("EZLLM_TEST_REDIS_URL", raising=False)
    assert main(["--suite", "agent", "--telemetry", "disabled"]) == 2
    monkeypatch.setenv("EZLLM_TEST_REDIS_URL", "redis://user:secret@127.0.0.1:6379/0")
    assert main(["--suite", "agent", "--telemetry", "disabled"]) == 2


def test_legacy_benchmark_is_reproducible_shape_and_relative_gate():
    report = run_benchmark("legacy", "disabled")
    assert len(report.cases) == 1
    case = report.cases[0]
    assert case.warmups == 5 and case.samples == 30
    assert case.latency_p95_ms >= case.latency_p50_ms > 0
    assert case.safe_first_event
    assert {gate.name for gate in report.gates} == {
        "legacy_p95_regression",
        "otel_p95_overhead",
        "warm_exact_cache_zero_model_embedding",
    }
