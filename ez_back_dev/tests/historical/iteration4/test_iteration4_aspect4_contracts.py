from __future__ import annotations

import json
from pathlib import Path

from app.agentApi import AGENT_API_HOST, app as agent_app, build_parser
from app.main import app as main_app


from repo_paths import canonical_document_path, fixture_path
from repo_paths import REPO_ROOT as PROJECT_ROOT
BACKEND_ROOT = PROJECT_ROOT / "ez_back_dev"
FIXTURE = fixture_path("historical", "iteration4", "iteration4_aspect4_manifest_v1.json")
BASELINE = fixture_path("historical", "iteration3", "iteration3_contract_baseline_v1.json")
CONTRACT = canonical_document_path(
    "docs/iteration-4-aspect-4-agent-workbench-contract.md"
)


def _routes(app):
    return sorted(
        (method.upper(), path)
        for path, methods in app.openapi()["paths"].items()
        for method in methods
        if method.upper() in {"GET", "POST", "PUT", "DELETE", "PATCH"}
        and path != "/ready"
    )


def test_aspect4_manifest_has_no_dependency_or_protected_source_drift():
    manifest = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert manifest["approved_dependency_changes"] == []
    assert manifest["package_manifests"]["ez_back_dev/requirements.txt"] == (
        "54EB1002BA00AEE7F11546990EEF78EFB0A4AC52ED5F850AC1A119203E8969AD"
    )
    assert manifest["configuration_examples"] == {
        ".env.example": "53F15FCBCA75DD173F7E60E05B9EA1AD7C1731E7B858FC1ECF14BA409FA966C5",
        "ez_front_dev/.env.example": "A28021C3A08A3BFA4F6F797E5683AC5D5F4A039161BAD622E2C48E922BE34E40",
    }
    assert manifest["protected_sources"] == {
        "ez_back_dev/app/main.py": "DBEC0E6438CC0F96669B67F78B6B04CF96365BD2271C4A2485FF8E97BB3162E6",
        "ez_back_dev/app/routers.py": "A3DDD017C3D50B30ED6FD65A5138F7D8A8F70BA8245C788A1210155AD3FD30A1",
        "ez_back_dev/service/workflowCatalog.py": "E9265C343F3768CF7F924ACE0056E47D5471A5976826E55CAF230F81A9CAAC6A",
    }
    assert manifest["agent_api"] == {
        "host": "127.0.0.1",
        "default_port": 8131,
        "schema_version": 1,
        "mounted_in_main_fastapi": False,
        "trace_status": "not_instrumented",
    }


def test_legacy_routes_remain_frozen_and_agent_api_is_separate():
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    expected = sorted(
        (item["method"], item["path"]) for item in baseline["public_routes"]
    )
    assert _routes(main_app) == expected
    assert not any(path.startswith("/agent/v1") for _, path in _routes(main_app))
    agent_paths = {path for _, path in _routes(agent_app)}
    assert "/agent/v1/projects/{pid}/runs" in agent_paths
    assert "/agent/v1/projects/{pid}/runs/{thread_id}/events" in agent_paths


def test_agent_api_cli_and_environment_are_loopback_and_bounded():
    parser = build_parser()
    destinations = {action.dest for action in parser._actions}
    assert destinations.issuperset({"port"})
    assert destinations.isdisjoint({"host", "project", "actor", "scope"})
    assert AGENT_API_HOST == "127.0.0.1"
    backend_env = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")
    frontend_env = (PROJECT_ROOT / "ez_front_dev" / ".env.example").read_text(
        encoding="utf-8"
    )
    assert "AGENT_API_PORT=8131" in backend_env
    assert "AGENT_WORKER_HEARTBEAT_TTL_SECONDS=30" in backend_env
    assert "VUE_APP_AGENT_API_BASE_URL=http://127.0.0.1:8131" in frontend_env


def test_public_sources_exclude_cot_and_arbitrary_execution_capabilities():
    sources = "\n".join(
        (BACKEND_ROOT / path).read_text(encoding="utf-8")
        for path in (
            "app/agentApi.py",
            "service/agent/workbench_service.py",
            "service/agent/workbench_store.py",
        )
    ).lower()
    for forbidden in (
        "reasoning_delta",
        "subprocess.",
        "os.system",
        "\neval(",
        "\nexec(",
        "testclient",
        "mcp.client",
    ):
        assert forbidden not in sources


def test_aspect4_document_records_runtime_ui_security_and_deferred_boundaries():
    text = CONTRACT.read_text(encoding="utf-8")
    for term in (
        "127.0.0.1",
        "8131",
        "one active run per project",
        "replay_reset",
        "7 days",
        "4 MiB",
        "synthetic_test_unit",
        "local-workbench",
        "Trace ID 尚未启用（Aspect 7）",
        "No dependency",
        "No provider, embedding or MySQL call",
    ):
        assert term in text
