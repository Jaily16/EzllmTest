import hashlib
import json
from pathlib import Path


from repo_paths import canonical_document_path
from repo_paths import FIXTURES_ROOT
from repo_paths import REPO_ROOT as ROOT

FIXTURES = FIXTURES_ROOT / "historical" / "iteration4"


def _repository_path(relative: str) -> Path:
    if relative.replace("\\", "/").startswith("docs/"):
        return canonical_document_path(relative)
    return ROOT / relative


def _sha256(path: Path) -> str:
    payload = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(payload).hexdigest().upper()


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _aspect3_style_changed_paths() -> set[str]:
    migration = json.loads(
        (
            FIXTURES_ROOT
            / "current"
            / "iteration5"
            / "iteration5_style_migration_v1.json"
        ).read_text(encoding="utf-8")
    )
    return {
        relative
        for batch in migration["batches"]
        for relative in batch["paths"]
    }


def _aspect4_backend_changed_paths() -> set[str]:
    migration = json.loads(
        (
            FIXTURES_ROOT
            / "current"
            / "iteration5"
            / "iteration5_backend_migration_v1.json"
        ).read_text(encoding="utf-8")
    )
    changed: set[str] = set()
    for batch in migration["batches"]:
        changed.update(batch.get("source_paths", []))
        changed.update(batch.get("canonical_paths", []))
    return changed


def test_release_manifest_layers_on_immutable_aspect8_evidence():
    manifest = _load("iteration4_release_manifest_v1.json")
    assert manifest["hash_policy"] == "sha256_canonical_lf_v1"
    assert manifest["release_dependency_fix"] == ["numpy==1.26.4"]
    assert manifest["parent"] == {
        "fixture": "iteration4_aspect8_manifest_v1.json",
        "fixture_sha256": _sha256(FIXTURES / "iteration4_aspect8_manifest_v1.json"),
    }
    style_changed = _aspect3_style_changed_paths() | _aspect4_backend_changed_paths()
    for relative, expected in manifest["protected_sources"].items():
        assert len(expected) == 64
        if relative not in style_changed:
            assert _sha256(_repository_path(relative)) == expected
    assert set(manifest["package_manifests"]) == {
        "ez_back_dev/requirements.txt",
        "ez_front_dev/package.json",
        "ez_front_dev/package-lock.json",
    }
    assert all(
        len(value) == 64 and all(char in "0123456789ABCDEF" for char in value)
        for value in manifest["package_manifests"].values()
    )
    assert manifest["final_documents"] == {
        "README.md": "8A75D6A45CCEB72CF238BD40542606FAC26ACB41C1FB8DACC7189BAFA2DC1269",
        "docs/iteration-4-closeout.md": "309D5CC938F06A13761AAEB365C5EEF9C1C96958FAFB168F4D317642354D8EA7",
        "docs/iteration-4-overview.md": "22A68F865B42EFED7DD799600FA2FB817590888F4627082D70249A10CE0F1363",
        "docs/iteration-4-prompts.md": "8726B09057E7A4D0D3FF38246C037953D75033CE330735B8A7960A63C2B56867",
        "docs/iteration-4-live-model-acceptance.md": "E085676E0594BBEF5045B6852934CEBA024B2E3FD68C3ACB6F9E0984C24778AF",
    }
    # README 会在后续迭代继续演进；Iteration 4 的其余收口文档保持不可变。
    for relative, expected in manifest["final_documents"].items():
        if relative != "README.md":
            assert _sha256(_repository_path(relative)) == expected
    for evidence in ("quality_script", "e2e_script"):
        item = manifest["real_model_acceptance"][evidence]
        if item["path"] not in style_changed:
            assert _sha256(_repository_path(item["path"])) == item["sha256"]
    delivery = manifest["delivery"]
    assert len(delivery["workflow_sha256"]) == 64
    assert all(char in "0123456789ABCDEF" for char in delivery["workflow_sha256"])


def test_release_hash_policy_is_cross_platform_and_numpy_is_explicit(tmp_path):
    sample = tmp_path / "sample.txt"
    sample.write_bytes(b"alpha\nbeta\n")
    linux_hash = _sha256(sample)
    sample.write_bytes(b"alpha\r\nbeta\r\n")
    assert _sha256(sample) == linux_hash
    historical = _load("iteration4_release_manifest_v1.json")
    assert historical["release_dependency_fix"] == ["numpy==1.26.4"]


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
    closeout = canonical_document_path("docs/iteration-4-closeout.md").read_text(
        encoding="utf-8"
    )
    assert "npm run serve -- --port 8080 --strictPort" in readme
    assert delivery["badge"] in readme
    assert delivery["badge"] in closeout
    assert "真实客户项目、生产负载或用户 MySQL" in readme
    assert "真实客户项目、生产负载或用户 MySQL" in closeout
    for stale in ("真实模型 Agent 质量验收未执行", "awaiting_explicit_push"):
        assert stale not in readme
        assert stale not in closeout
