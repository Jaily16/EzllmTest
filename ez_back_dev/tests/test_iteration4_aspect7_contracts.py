import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "ez_back_dev"
FIXTURES = BACKEND / "tests" / "fixtures"


def _sha256(path: Path) -> str:
    payload = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(payload).hexdigest().upper()


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_aspect7_manifest_chains_history_and_freezes_current_delivery_files():
    manifest = _load("iteration4_aspect7_manifest_v1.json")
    assert manifest["parent"] == {
        "fixture": "iteration4_aspect6_manifest_v1.json",
        "fixture_sha256": _sha256(FIXTURES / "iteration4_aspect6_manifest_v1.json"),
    }
    assert manifest["package_manifests"] == {
        "ez_back_dev/requirements.txt": "7FE551B074A6D49A4E8A82E71ECF7F6B9D73207631BA4EEAF02764453A293932",
        "ez_front_dev/package.json": "031E98C3451EA5073419FB439F4FA2567728621A96B88B4D8600D638014EF42D",
        "ez_front_dev/package-lock.json": "402B195DD3B3146A94F796A4365F02B66642CB36C353D587E57DA3116C944700",
    }
    assert manifest["protected_sources"] == {
        "ez_back_dev/app/main.py": "DBEC0E6438CC0F96669B67F78B6B04CF96365BD2271C4A2485FF8E97BB3162E6",
        "ez_back_dev/app/routers.py": "A3DDD017C3D50B30ED6FD65A5138F7D8A8F70BA8245C788A1210155AD3FD30A1",
        "ez_back_dev/service/workflowCatalog.py": "E9265C343F3768CF7F924ACE0056E47D5471A5976826E55CAF230F81A9CAAC6A",
        "README.md": "71ADFD7358A4DFAF5F254CD5584BDB606C7CD4FFC0B045DB96F4391BAB7D8AFE",
        "docs/iteration-4-overview.md": "8E4FC33E3139E313BAA39E832D9D8CE765918383301E3135CFEB377BAB0DC786",
        "docs/iteration-4-prompts.md": "34653AEFBECB2B4ACAE22311930929E21AA0F4C25881E40404629B5AA3247C0D",
    }
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
