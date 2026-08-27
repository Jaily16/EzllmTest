import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "ez_back_dev"
FIXTURES = BACKEND / "tests" / "fixtures"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_aspect7_manifest_chains_history_and_freezes_current_delivery_files():
    manifest = _load("iteration4_aspect7_manifest_v1.json")
    assert manifest["parent"] == {
        "fixture": "iteration4_aspect6_manifest_v1.json",
        "fixture_sha256": _sha256(FIXTURES / "iteration4_aspect6_manifest_v1.json"),
    }
    for relative, expected in manifest["package_manifests"].items():
        assert _sha256(ROOT / relative) == expected
    for relative, expected in manifest["protected_sources"].items():
        if relative not in {
            "README.md",
            "docs/iteration-4-overview.md",
            "docs/iteration-4-prompts.md",
        }:
            assert _sha256(ROOT / relative) == expected
    performance = manifest["performance"]
    assert _sha256(FIXTURES / performance["prechange_fixture"]) == performance[
        "prechange_fixture_sha256"
    ]
    assert _sha256(FIXTURES / performance["gate_fixture"]) == performance[
        "gate_fixture_sha256"
    ]
    assert _sha256(ROOT / "compose.yaml") == manifest["delivery"]["compose_sha256"]
    assert manifest["delivery"]["github_actions_sha256"] == (
        "50F53B22DDA136AF3FD2115229DCFCD9E7CA38428E8A3D228846D1BBA0DA1811"
    )
    assert manifest["delivery"]["hosted_ci_status"] == "awaiting_explicit_push"


def test_aspect7_performance_gate_uses_real_relative_limits_without_claiming_cost():
    baseline = _load("iteration4_aspect7_prechange_performance_v1.json")
    gate = _load("iteration4_aspect7_performance_gate_v1.json")
    assert baseline["sampling"] == {
        "warmups": 5,
        "samples": 30,
        "outliers_discarded": 0,
    }
    benchmark = gate["agent_benchmark"]
    assert benchmark["legacy_p95_regression_ratio"] <= benchmark["legacy_p95_limit"]
    assert (
        benchmark["otel_enabled_over_disabled_p95_ratio"]
        <= benchmark["otel_overhead_limit"]
    )
    assert benchmark["warm_exact_cache_new_model_calls"] == 0
    assert benchmark["warm_exact_cache_new_embedding_calls"] == 0
    assert benchmark["telemetry_export_status"] == "exported"
    vite = gate["vite"]
    assert vite["build_p95_ratio_to_vue_cli"] <= 0.95
    assert vite["dev_ready_p95_ratio_to_vue_cli"] <= 1.0
    for key in (
        "initial_js_ratio",
        "initial_css_ratio",
        "initial_total_ratio",
        "full_build_ratio",
    ):
        assert vite[key] <= 1.05
    assert vite["source_map_count"] == 0
    assert gate["cost"] == {
        "real_provider_calls": 0,
        "real_embedding_calls": 0,
        "real_mysql_calls": 0,
        "real_project_reads": 0,
        "model_currency_cost": 0,
    }


def test_aspect7_compose_and_browser_evidence_is_explicit():
    gate = _load("iteration4_aspect7_performance_gate_v1.json")
    assert gate["browser_matrix"] == {
        "viewports": ["360x800", "768x1024", "1024x768", "1440x900", "1920x1080"],
        "horizontal_overflow_count": 0,
        "console_error_count": 0,
        "minimum_approval_target_px": 44,
        "escape_closed_dialog": True,
        "focus_restored": True,
        "disabled_trace_state": True,
        "instrumented_trace_state": True,
    }
    compose = gate["compose"]
    assert compose["healthy_services"] == 10
    assert compose["tempo_trace_count_observed"] > 0
    assert compose["prometheus_collector_up"] == 1
    assert compose["grafana_datasources"] == ["prometheus", "tempo"]
    assert compose["non_loopback_host_status"] == 421


def test_aspect7_documents_state_security_operations_and_stop_boundary():
    contract = (ROOT / "docs/iteration-4-aspect-7-observability-delivery-contract.md").read_text(
        encoding="utf-8"
    )
    compose = (ROOT / "docs/iteration-4-compose.md").read_text(encoding="utf-8")
    for required in (
        "iteration4-aspect7-v1",
        "otel-genai-safe-v1",
        "disabled by default",
        "prompts, completions, reasoning",
        "1.0394",
        "1.0217",
        "awaiting_explicit_push",
        "Aspect 8 remains out of scope",
    ):
        assert required in contract
    for required in (
        "--env-file ops/compose/.env.local",
        "127.0.0.1:8131",
        "down",
        "Do not add `-v`",
        "real provider key",
    ):
        assert required in compose
