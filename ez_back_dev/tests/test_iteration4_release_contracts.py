import hashlib
import importlib.metadata
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "ez_back_dev" / "tests" / "fixtures"


def _sha256(path: Path) -> str:
    payload = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(payload).hexdigest().upper()


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_release_manifest_layers_on_immutable_aspect8_evidence():
    manifest = _load("iteration4_release_manifest_v1.json")
    assert manifest["hash_policy"] == "sha256_canonical_lf_v1"
    assert manifest["release_dependency_fix"] == ["numpy==1.26.4"]
    assert manifest["parent"] == {
        "fixture": "iteration4_aspect8_manifest_v1.json",
        "fixture_sha256": _sha256(FIXTURES / "iteration4_aspect8_manifest_v1.json"),
    }
    for group in ("package_manifests", "protected_sources", "final_documents"):
        for relative, expected in manifest[group].items():
            assert _sha256(ROOT / relative) == expected
    for evidence in ("quality_script", "e2e_script"):
        item = manifest["real_model_acceptance"][evidence]
        assert _sha256(ROOT / item["path"]) == item["sha256"]
    delivery = manifest["delivery"]
    assert _sha256(ROOT / delivery["workflow"]) == delivery["workflow_sha256"]


def test_release_hash_policy_is_cross_platform_and_numpy_is_explicit(tmp_path):
    sample = tmp_path / "sample.txt"
    sample.write_bytes(b"alpha\nbeta\n")
    linux_hash = _sha256(sample)
    sample.write_bytes(b"alpha\r\nbeta\r\n")
    assert _sha256(sample) == linux_hash
    requirements = (ROOT / "ez_back_dev/requirements.txt").read_text(encoding="utf-8")
    assert "numpy==1.26.4" in requirements.splitlines()
    assert importlib.metadata.version("numpy") == "1.26.4"


def test_release_manifest_records_real_acceptance_without_overclaiming_cost():
    acceptance = _load("iteration4_release_manifest_v1.json")[
        "real_model_acceptance"
    ]
    assert acceptance["planner"] == {"passed": 6, "total": 6}
    assert acceptance["rag"] == {"passed": 3, "total": 3, "real_embedding": True}
    assert acceptance["e2e"] == {
        "trajectory": ["ui_info", "ui_case"],
        "terminal_status": "completed",
        "approval_count": 2,
        "model_calls": 4,
        "embedding_calls": 2,
        "tool_calls": 2,
    }
    assert all(value == 0 for value in acceptance["isolation"].values())
    assert acceptance["model_currency_cost"] is None
    assert acceptance["currency_cost_reason"] == (
        "provider_did_not_return_currency_cost"
    )


def test_release_documents_use_dynamic_ci_status_and_exact_vite_runbook():
    manifest = _load("iteration4_release_manifest_v1.json")
    delivery = manifest["delivery"]
    assert delivery == {
        "target_branch": "main",
        "target_remote": "origin",
        "workflow": ".github/workflows/iteration4-offline.yml",
        "workflow_sha256": "7F7CC9AA9C657F55786184D2C7072B72039A780A36877FB52DDB05B8D138F994",
        "badge": "https://github.com/Jaily16/EzllmTest/actions/workflows/iteration4-offline.yml/badge.svg?branch=main",
        "hosted_ci_status": "dynamic_after_push",
        "feature_branch_push": False,
        "tag_created": False,
        "github_release_created": False,
    }
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    closeout = (ROOT / "docs/iteration-4-closeout.md").read_text(encoding="utf-8")
    assert "npm run serve -- --port 8080 --strictPort" in readme
    assert delivery["badge"] in readme
    assert delivery["badge"] in closeout
    assert "真实客户项目、生产负载或用户 MySQL" in readme
    assert "真实客户项目、生产负载或用户 MySQL" in closeout
    for stale in ("真实模型 Agent 质量验收未执行", "awaiting_explicit_push"):
        assert stale not in readme
        assert stale not in closeout
