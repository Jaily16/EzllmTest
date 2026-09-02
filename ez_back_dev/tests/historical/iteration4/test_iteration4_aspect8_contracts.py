import hashlib
import json
from pathlib import Path


from repo_paths import FIXTURES_ROOT
from repo_paths import REPO_ROOT as ROOT

FIXTURES = FIXTURES_ROOT / "historical" / "iteration4"


def _sha256(path: Path) -> str:
    payload = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(payload).hexdigest().upper()


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_aspect8_manifest_remains_immutable_historical_evidence():
    manifest = _load("iteration4_aspect8_manifest_v1.json")
    assert manifest["parent"] == {
        "fixture": "iteration4_aspect7_manifest_v1.json",
        "fixture_sha256": _sha256(FIXTURES / "iteration4_aspect7_manifest_v1.json"),
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
    }
    for relative, hashes in manifest["intentional_document_updates"].items():
        assert hashes["parent_sha256"] == _load("iteration4_aspect7_manifest_v1.json")[
            "protected_sources"
        ][relative]
    assert {
        relative: hashes["aspect8_sha256"]
        for relative, hashes in manifest["intentional_document_updates"].items()
    } == {
        "README.md": "2FF73C5013AF94886D4787484A641778B42AC479E992B78A0B1F48E92320A6FC",
        "docs/iteration-4-overview.md": "DCFBDBD99F70642B28BD5CBE7CBEDD7394EC8C69B46D19408F0AAC2C6DB490DB",
        "docs/iteration-4-prompts.md": "5EB3FF9093BD9845DD5617BB40FDD3719935E0BA4EDE4B3559246838F59BCFC2",
    }
    assert _sha256(FIXTURES / Path(manifest["acceptance"]["dataset"]).name) == manifest[
        "acceptance"
    ]["dataset_sha256"]
    assert _sha256(FIXTURES / Path(manifest["acceptance"]["gate"]).name) == manifest[
        "acceptance"
    ]["gate_sha256"]
    assert manifest["closeout"] == {
        "path": "docs/iteration-4-closeout.md",
        "sha256": "62F8D2E7C498C2B3C97EA0424F407D833A8821D094A932EF67B0E59A42B39A2A",
    }
    assert len(manifest["delivery"]["github_actions_sha256"]) == 64


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
    graph = (ROOT / "ez_back_dev/service/agent/graph.py").read_text(encoding="utf-8")
    runtime = (ROOT / "ez_back_dev/service/agent/runtime.py").read_text(
        encoding="utf-8"
    )
    assert '"ezllm.agent.tool.calls"' in graph
    assert '"ezllm.agent.tool.duration"' in graph
    assert '"operation": call.operation' in graph
    assert '"ezllm.agent.recovery"' in runtime
    assert 'command.kind == "recover"' in runtime
