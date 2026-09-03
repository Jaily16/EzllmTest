"""Pure report-normalization tests for the Aspect 8 harness."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory

from repo_paths import REPO_ROOT


def _load_harness():
    path = REPO_ROOT / "scripts/run_iteration5_dual_mode_acceptance.py"
    spec = importlib.util.spec_from_file_location("aspect8_harness_unit", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


harness = _load_harness()


def _payload():
    case_ids = [
        "journey-project-lifecycle",
        "journey-plan-approval",
        "journey-exact-cache",
        "journey-session-only",
        "journey-persisted",
        "journey-regenerate",
        "journey-rag-citations",
        "reliability-stale",
        "reliability-cancel",
        "reliability-persisted-crash",
        "reliability-session-unknown",
        "reliability-failure-rollback",
        "reliability-replay",
        "protocol-api-isolation",
        "protocol-mcp-boundary",
        "protocol-approval-tamper",
        "protocol-serialization",
        "protocol-telemetry-redaction",
    ]
    return {
        "dataset_id": "iteration4-agent-acceptance-v1",
        "dataset_sha256": "A" * 64,
        "results": [
            {
                "case_id": case_id,
                "suite": "journey" if case_id.startswith("journey-") else "reliability" if case_id.startswith("reliability-") else "protocol",
                "scenario": case_id,
                "passed": True,
                "terminal_status": "completed",
                "trajectory": ["observe", "completed"],
                "project_id": "must-not-be-compared",
            }
            for case_id in case_ids
        ],
        "metrics": {
            "approval_bypass_count": 0,
            "duplicate_side_effect_count": 0,
            "project_isolation_violation_count": 0,
            "budget_overrun_count": 0,
            "unsafe_capability_execution_count": 0,
            "sensitive_data_leak_count": 0,
            "session_mysql_write_count": 0,
            "warm_cache_model_calls": 0,
            "warm_cache_embedding_calls": 0,
        },
        "decision": {"passed": True, "hard_gate_failures": []},
        "real_provider_calls": 0,
        "real_embedding_calls": 0,
        "user_mysql_calls": 0,
        "user_project_reads": 0,
        "model_currency_cost": 0,
    }


def test_normalization_ignores_environment_and_project_fields():
    report = {"report": _payload()}
    normalized = harness._normalized_acceptance(report)
    assert normalized is not None
    assert "project_id" not in str(normalized)
    assert "topology" not in normalized
    assert normalized["case_count"] == 18


def test_compare_returns_blocked_when_either_business_report_is_missing():
    result = harness.compare_acceptance(
        {"deterministic_business_acceptance": {"status": "blocked"}},
        {"deterministic_business_acceptance": {"status": "blocked"}},
    )
    assert result["status"] == "blocked"
    assert result["error_code"] == "acceptance_report_unavailable"


def test_compare_requires_same_deterministic_report_and_zero_gates():
    left = {"deterministic_business_acceptance": {"report": _payload()}}
    right = {"deterministic_business_acceptance": {"report": _payload()}}
    result = harness.compare_acceptance(left, right)
    assert result["status"] == "pass"
    assert result["same_dataset"] is True
    assert result["same_case_trajectory"] is True
    assert result["zero_security_and_cost_metrics"] is True


def test_acceptance_payload_sanitizer_drops_user_and_environment_fields():
    payload = _payload() | {
        "environment": {"topology": "isolated_compose", "request_body": "secret"},
        "project_id": "must-not-be-written",
        "prompt": "must-not-be-written",
        "traceback": "must-not-be-written",
    }
    sanitized = harness._sanitize_acceptance_payload(payload)
    assert sanitized is not None
    serialized = str(sanitized)
    assert "project_id" not in serialized
    assert "prompt" not in serialized
    assert "traceback" not in serialized
    assert "request_body" not in serialized
    assert sanitized["results"][0]["case_id"] == "journey-project-lifecycle"


def test_compare_rejects_a_shared_but_wrong_case_set():
    payload = _payload()
    payload["results"] = payload["results"][:-1]
    left = {"deterministic_business_acceptance": {"report": payload}}
    right = {"deterministic_business_acceptance": {"report": _payload()}}
    result = harness.compare_acceptance(left, right)
    assert result["status"] == "fail"
    assert result["same_case_trajectory"] is False


def test_early_block_writes_a_mode_report_without_runtime_secrets():
    report = {
        "schema_version": "iteration5-dual-mode-acceptance-report-v1",
        "mode": "docker",
        "status": "blocked",
    }
    with TemporaryDirectory(prefix="ezllmtest-aspect8-unit-", dir=str(REPO_ROOT.parent)) as directory:
        report_dir = Path(directory)
        result = harness._write_early_block(
            report_dir,
            report,
            "fixed_full_stack_port_in_use",
            busy_ports=[9090],
        )
        saved = (report_dir / "docker.json").read_text(encoding="utf-8")
        assert result["status"] == "blocked"
        assert result["error_code"] == "fixed_full_stack_port_in_use"
        assert '"busy_ports": [\n    9090\n  ]' in saved
        assert "DATABASE_URL" not in saved
