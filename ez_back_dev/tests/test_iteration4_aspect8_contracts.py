import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "ez_back_dev" / "tests" / "fixtures"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_aspect8_manifest_layers_on_aspect7_without_dependency_or_api_drift():
    manifest = _load("iteration4_aspect8_manifest_v1.json")
    assert manifest["parent"] == {
        "fixture": "iteration4_aspect7_manifest_v1.json",
        "fixture_sha256": _sha256(FIXTURES / "iteration4_aspect7_manifest_v1.json"),
    }
    for relative, expected in manifest["package_manifests"].items():
        assert _sha256(ROOT / relative) == expected
    for relative, expected in manifest["protected_sources"].items():
        assert _sha256(ROOT / relative) == expected
    for relative, hashes in manifest["intentional_document_updates"].items():
        assert hashes["parent_sha256"] == _load("iteration4_aspect7_manifest_v1.json")[
            "protected_sources"
        ][relative]
        assert _sha256(ROOT / relative) == hashes["aspect8_sha256"]
    assert _sha256(ROOT / manifest["acceptance"]["dataset"]) == manifest[
        "acceptance"
    ]["dataset_sha256"]
    assert _sha256(ROOT / manifest["acceptance"]["gate"]) == manifest[
        "acceptance"
    ]["gate_sha256"]
    assert _sha256(ROOT / manifest["closeout"]["path"]) == manifest["closeout"][
        "sha256"
    ]
    assert _sha256(ROOT / manifest["delivery"]["github_actions"]) == manifest[
        "delivery"
    ]["github_actions_sha256"]


def test_aspect8_gate_records_only_real_offline_evidence():
    gate = _load("iteration4_aspect8_gate_v1.json")
    assert gate["acceptance"]["case_count"] == 18
    assert gate["acceptance"]["passed"] == 18
    assert gate["acceptance"]["task_success"] == 1
    assert gate["acceptance"]["trajectory_validity"] == 1
    assert gate["acceptance"]["recovery_success"] == 1
    assert gate["security"] == {
        "approval_bypass_count": 0,
        "duplicate_side_effect_count": 0,
        "project_isolation_violation_count": 0,
        "budget_overrun_count": 0,
        "unsafe_capability_execution_count": 0,
        "sensitive_data_leak_count": 0,
    }
    assert gate["cache"] == {
        "warm_exact_cache_new_model_calls": 0,
        "warm_exact_cache_new_embedding_calls": 0,
    }
    assert gate["cost"] == {
        "real_provider_calls": 0,
        "real_embedding_calls": 0,
        "user_mysql_calls": 0,
        "user_project_reads": 0,
        "model_currency_cost": 0,
    }
    assert gate["release"]["hosted_ci"] == "awaiting_explicit_push"
    assert gate["release"]["git_operations"] == []


def test_iteration4_public_surfaces_remain_frozen():
    from app.agentApi import app as agent_app
    from app.main import app as legacy_app
    from service.agentToolRegistry import DEFAULT_TOOL_REGISTRY
    from service.workflowCatalog import WORKFLOW_DEFINITIONS

    assert len(WORKFLOW_DEFINITIONS) == 19
    assert len(DEFAULT_TOOL_REGISTRY.definitions()) == 22
    assert not any(
        getattr(route, "path", "").startswith("/agent/")
        for route in legacy_app.routes
    )
    agent_paths = {
        getattr(route, "path", "")
        for route in agent_app.routes
        if getattr(route, "path", "").startswith("/agent/v1")
    }
    assert len(agent_paths) == 8


def test_acceptance_closes_tool_and_recovery_metric_gaps():
    graph = (ROOT / "ez_back_dev/service/agentGraph.py").read_text(encoding="utf-8")
    runtime = (ROOT / "ez_back_dev/service/agentRuntimeService.py").read_text(
        encoding="utf-8"
    )
    assert '"ezllm.agent.tool.calls"' in graph
    assert '"ezllm.agent.tool.duration"' in graph
    assert '"operation": call.operation' in graph
    assert '"ezllm.agent.recovery"' in runtime
    assert 'command.kind == "recover"' in runtime
