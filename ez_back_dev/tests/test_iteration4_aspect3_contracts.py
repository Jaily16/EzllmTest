from __future__ import annotations

import hashlib
import importlib.metadata
import json
from pathlib import Path

from app.main import app
from service.agentWorker import build_parser


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "ez_back_dev"
FIXTURE = (
    BACKEND_ROOT / "tests" / "fixtures" / "iteration4_aspect3_manifest_v1.json"
)
BASELINE = (
    BACKEND_ROOT / "tests" / "fixtures" / "iteration3_contract_baseline_v1.json"
)
CONTRACT = PROJECT_ROOT / "docs" / "iteration-4-aspect-3-runtime-contract.md"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _routes():
    return sorted(
        (method.upper(), path)
        for path, methods in app.openapi()["paths"].items()
        for method in methods
        if method.upper() in {"GET", "POST", "PUT", "DELETE", "PATCH"}
    )


def test_aspect3_manifest_layers_only_the_approved_safe_runtime_dependencies():
    manifest = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert manifest["approved_direct_dependencies"] == [
        "langgraph==1.2.11",
        "langgraph-checkpoint==4.2.0",
        "redis==6.4.0",
    ]
    assert manifest["excluded_dependencies"] == [
        "langgraph-checkpoint-redis",
        "redisvl",
    ]
    assert manifest["package_manifests"] == {
        "ez_back_dev/requirements.txt": "54EB1002BA00AEE7F11546990EEF78EFB0A4AC52ED5F850AC1A119203E8969AD",
        "ez_front_dev/package.json": "769EC529E786375A8DCDB5FCE27C1A4A44D5DDEDC3B9946E2850DEA8477BD5C3",
        "ez_front_dev/package-lock.json": "C93CDE311DB8675A62A781E20F613DD291D049743CF30A684EE3B94EA074DEAA",
    }
    # Aspect 3 remains immutable historical evidence. Aspect 4 intentionally
    # layers two new example variable names and validates the current file in
    # its own manifest instead of rewriting this captured hash.
    assert manifest["configuration_files"] == {
        ".env.example": (
            "F69E336329C23C2901ADDD8C1FA75749885DC4F34507A5B2BEA9431492D2A25B"
        )
    }
    assert importlib.metadata.version("langgraph") == "1.2.11"
    assert importlib.metadata.version("langgraph-checkpoint") == "4.2.0"
    assert importlib.metadata.version("redis") == "6.4.0"


def test_public_routes_remain_the_iteration3_contract():
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    expected = sorted(
        (item["method"], item["path"]) for item in baseline["public_routes"]
    )
    assert _routes() == expected
    source = (BACKEND_ROOT / "app" / "main.py").read_text(encoding="utf-8")
    assert "agentRuntime" not in source
    assert "agentWorker" not in source


def test_worker_cli_cannot_supply_scope_redis_or_approval_authority():
    parser = build_parser()
    destinations = {action.dest for action in parser._actions}
    assert destinations.issuperset({"once", "consumer"})
    assert destinations.isdisjoint(
        {"host", "port", "redis_url", "project", "scope", "approval"}
    )


def test_env_example_declares_only_bounded_internal_agent_runtime_settings():
    names = {
        line.split("=", 1)[0]
        for line in (PROJECT_ROOT / ".env.example").read_text(
            encoding="utf-8"
        ).splitlines()
        if line and not line.startswith("#") and "=" in line
    }
    assert {
        "AGENT_REDIS_URL",
        "AGENT_REDIS_PREFIX",
        "AGENT_CHECKPOINT_TTL_SECONDS",
        "AGENT_IDEMPOTENCY_TTL_SECONDS",
        "AGENT_CANCEL_TTL_SECONDS",
        "AGENT_EVENT_TTL_SECONDS",
        "AGENT_EVENT_MAX_LENGTH",
        "AGENT_LEASE_TTL_SECONDS",
        "AGENT_LEASE_RENEW_SECONDS",
        "AGENT_COMMAND_CLAIM_SECONDS",
        "LANGGRAPH_STRICT_MSGPACK",
    }.issubset(names)
    env_text = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")
    assert "AGENT_REDIS_URL=redis://127.0.0.1:6379/0" in env_text


def test_checkpoint_source_has_no_pickle_dynamic_import_or_upstream_redis_saver():
    source = (BACKEND_ROOT / "service" / "agentCheckpoint.py").read_text(
        encoding="utf-8"
    )
    lowered = source.lower()
    assert "import pickle" not in lowered
    assert "importlib" not in lowered
    assert "async-redissaver" not in lowered
    assert "redisvl" not in lowered
    assert "ezllm-safe-json-v1" in source


def test_runtime_has_no_http_mcp_shell_file_or_dynamic_python_self_call():
    source = "\n".join(
        (BACKEND_ROOT / "service" / name).read_text(encoding="utf-8")
        for name in (
            "agentGraph.py",
            "agentRuntimeService.py",
            "agentWorker.py",
        )
    )
    for forbidden in (
        "TestClient",
        "requests.",
        "httpx.",
        "mcp.client",
        "subprocess.",
        "os.system",
        "eval(",
        "exec(",
    ):
        assert forbidden not in source


def test_aspect3_contract_records_security_recovery_and_deferred_boundaries():
    document = CONTRACT.read_text(encoding="utf-8")
    required = (
        "LangGraph 1.2.11",
        "single Agent",
        "BaseCheckpointSaver",
        "SerializerProtocol",
        "ezllm-safe-json-v1",
        "constructor",
        "owner:fence",
        "outcome_unknown",
        "approval nonce",
        "7 days",
        "1 hour",
        "2,000",
        "chain-of-thought",
        "No public REST/SSE change",
        "Aspect 4",
    )
    for term in required:
        assert term in document
