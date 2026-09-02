import hashlib
import json
from pathlib import Path

from app.main import app
from app.mcpServer import LOOPBACK_HOST, _parser


from repo_paths import canonical_document_path, fixture_path
from repo_paths import REPO_ROOT as PROJECT_ROOT
BASELINE_PATH = (
    fixture_path("historical", "iteration3", "iteration3_contract_baseline_v1.json")
)
MANIFEST_PATH = (
    fixture_path("historical", "iteration4", "iteration4_aspect2_manifest_v1.json")
)
CONTRACT_PATH = canonical_document_path(
    "docs/iteration-4-aspect-2-tool-mcp-contract.md"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _routes():
    return sorted(
        {
            (method.upper(), path)
            for path, methods in app.openapi()["paths"].items()
            for method in methods
            if method.upper() in {"GET", "POST", "PUT", "DELETE", "PATCH"}
            and path != "/ready"
        }
    )


def test_manifest_snapshot_layers_the_approved_mcp_change_over_iteration3():
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest["schema_version"] == 1
    assert manifest["parent"] == {
        "fixture": "iteration3_contract_baseline_v1.json",
        "requirements_sha256": baseline["package_manifests"][
            "ez_back_dev/requirements.txt"
        ],
    }
    assert manifest["approved_direct_dependency"] == "mcp==2.1.1"
    # This fixture is immutable historical evidence.  Aspect 3 layers a new
    # current-manifest fixture instead of rewriting this captured hash.
    assert manifest["package_manifests"]["ez_back_dev/requirements.txt"] == (
        "D0203C1049B50F09FE00FAC5F42EDD962202E61B00EB885DD817914E74B7B380"
    )
    assert manifest["package_manifests"]["ez_front_dev/package.json"] == (
        "769EC529E786375A8DCDB5FCE27C1A4A44D5DDEDC3B9946E2850DEA8477BD5C3"
    )
    assert manifest["package_manifests"]["ez_front_dev/package-lock.json"] == (
        "C93CDE311DB8675A62A781E20F613DD291D049743CF30A684EE3B94EA074DEAA"
    )


def test_aspect2_historical_manifest_contains_only_the_approved_mcp_change():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["approved_direct_dependency"] == "mcp==2.1.1"
    assert manifest["package_manifests"]["ez_back_dev/requirements.txt"] == (
        "D0203C1049B50F09FE00FAC5F42EDD962202E61B00EB885DD817914E74B7B380"
    )
    assert manifest["approved_direct_dependency"] == "mcp==2.1.1"


def test_public_fastapi_routes_remain_the_iteration3_snapshot():
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    expected = sorted(
        (item["method"], item["path"])
        for item in baseline["public_routes"]
    )
    assert _routes() == expected
    assert "/mcp" not in app.openapi()["paths"]


def test_loopback_cli_has_no_remote_host_option():
    parser = _parser()
    destinations = {action.dest for action in parser._actions}
    assert "host" not in destinations
    assert LOOPBACK_HOST == "127.0.0.1"


def test_internal_executor_has_no_http_or_mcp_self_call():
    source = (
        PROJECT_ROOT
        / "ez_back_dev"
        / "service"
        / "agentToolExecutor.py"
    ).read_text(encoding="utf-8")
    for forbidden in (
        "TestClient",
        "requests.",
        "httpx.",
        "Client(",
        "127.0.0.1",
        "localhost",
    ):
        assert forbidden not in source


def test_aspect2_contract_documents_boundaries_and_protocol_semantics():
    document = CONTRACT_PATH.read_text(encoding="utf-8")
    required = (
        "22 tools",
        "19 workflow",
        "workflow catalog",
        "trusted runtime",
        "application service layer",
        "approval_required",
        "Streamable HTTP",
        "127.0.0.1",
        "tools",
        "resources",
        "prompts",
        "progress",
        "cancellation",
        "errors",
        "reasoning_delta",
        "No public FastAPI route change",
        "Aspect 3",
    )
    for term in required:
        assert term in document
    for forbidden in (
        "arbitrary file tool",
        "arbitrary shell tool",
        "arbitrary network tool",
    ):
        assert forbidden in document.lower()
