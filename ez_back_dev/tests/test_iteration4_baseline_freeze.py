import hashlib
import json
import os
from pathlib import Path


os.environ["PYTHON_DOTENV_DISABLED"] = "1"
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
for provider_key in (
    "ZHIPU_API_KEY",
    "DASHSCOPE_API_KEY",
    "DEEPSEEK_API_KEY",
    "MOONSHOT_API_KEY",
):
    os.environ[provider_key] = ""

from app.main import app
from service.workflowBudget import profile_for
from service.workflowCatalog import WORKFLOW_DEFINITIONS
from vectorstore import indexRegistry
from vectorstore.retrievers import (
    DESIGN_RETRIEVAL_POLICY,
    KNOWLEDGE_RETRIEVAL_POLICY,
    REQUIREMENTS_RETRIEVAL_POLICY,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASELINE_PATH = (
    Path(__file__).parent / "fixtures" / "iteration3_contract_baseline_v1.json"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _workflow_snapshot() -> list[dict[str, object]]:
    return [
        {
            "operation": item.operation,
            "phase": item.phase,
            "prerequisites": list(item.prerequisites),
            "result_artifact": item.result_artifact,
            "cache_artifacts": list(item.cache_artifacts),
            "source_corpus": item.source_corpus,
            "supports_regenerate": item.supports_regenerate,
            "prompt_version": item.prompt_version,
            "selection_fields": list(item.selection_fields),
            "prerequisite_payload_fields": list(
                item.prerequisite_payload_fields
            ),
            "persistence": item.persistence,
            "budget": profile_for(item.operation).public_metadata(),
        }
        for item in WORKFLOW_DEFINITIONS
    ]


def _route_snapshot() -> list[dict[str, str]]:
    routes = []
    for path, methods in app.openapi()["paths"].items():
        for method in methods:
            if method.upper() in {"GET", "POST", "PUT", "DELETE", "PATCH"}:
                routes.append({"method": method.upper(), "path": path})
    return sorted(routes, key=lambda item: (item["path"], item["method"]))


def test_iteration3_workflow_and_route_snapshot_is_frozen():
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))

    assert baseline["schema_version"] == 1
    assert baseline["workflow_count"] == 19
    assert _workflow_snapshot() == baseline["workflows"]
    assert _route_snapshot() == baseline["public_routes"]
    assert baseline["rest_envelope"] == ["status", "reason", "data"]
    assert baseline["sse_events"] == [
        "answer_delta",
        "artifact",
        "completed",
        "error",
        "menu",
        "meta",
        "progress",
        "reasoning_delta",
        "result",
        "stale",
        "summary_delta",
        "usage",
    ]


def test_iteration3_artifact_rag_reliability_and_retention_are_frozen():
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))

    assert baseline["artifact_identity"] == [
        "project_id",
        "artifact_key",
        "input_hash",
        "source_revision",
        "model_label",
    ]
    assert baseline["rag"] == {
        "index_capacity": indexRegistry.INDEX_CAPACITY,
        "index_idle_ttl_seconds": indexRegistry.INDEX_IDLE_TTL_SECONDS,
        "index_key": [
            "project_id",
            "corpus",
            "source_revision",
            "embedding_identity",
        ],
        "retrieval_policies": {
            "design": DESIGN_RETRIEVAL_POLICY.__dict__,
            "knowledge": KNOWLEDGE_RETRIEVAL_POLICY.__dict__,
            "requirements": REQUIREMENTS_RETRIEVAL_POLICY.__dict__,
        },
    }
    assert baseline["reliability"] == {
        "cancel_before_next_side_effect": True,
        "delayed_persistence": True,
        "exact_cache": True,
        "failed_regeneration_preserves_previous": True,
        "regeneration_lock": True,
        "revision_stale_detection": True,
        "warm_index_reuse": True,
    }
    assert baseline["retention"] == {
        "persisted_case_operations": [
            "acceptance_case",
            "db_case",
            "ui_case",
        ],
        "preliminary_analysis": "persisted",
        "session_only_case_operations": [
            "api_case",
            "functional_case",
            "integration_case",
            "nonfunctional_case",
            "unit_case",
        ],
    }


def test_iteration3_package_manifest_snapshot_remains_historical_evidence():
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))

    assert baseline["package_manifests"] == {
        "ez_back_dev/requirements.txt": (
            "131F71733433D2806083756DFB2B5E315B66A678E304EBA6EB3E82FF0F4C7FEF"
        ),
        "ez_front_dev/package.json": (
            "769EC529E786375A8DCDB5FCE27C1A4A44D5DDEDC3B9946E2850DEA8477BD5C3"
        ),
        "ez_front_dev/package-lock.json": (
            "C93CDE311DB8675A62A781E20F613DD291D049743CF30A684EE3B94EA074DEAA"
        ),
    }
