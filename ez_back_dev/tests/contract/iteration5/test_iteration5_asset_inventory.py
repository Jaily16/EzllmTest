from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
from pathlib import Path

import pytest


from repo_paths import REPO_ROOT as ROOT
SCRIPT = ROOT / "scripts" / "iteration5_asset_inventory.py"
_SPEC = importlib.util.spec_from_file_location("iteration5_asset_inventory", SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
inventory = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(inventory)


def test_classification_matrix_does_not_use_filename_age_as_deletion_evidence():
    cases = {
        ".env": "Protected user data",
        "ez_back_dev/static/projects/upload.pdf": "Protected user data",
        "docs/iteration-4-closeout.md": "Historical evidence",
        "ez_back_dev/app/__pycache__/module.cpython-311.pyc": "Generated disposable",
        "ez_front_dev/dist/assets/app.js": "Generated disposable",
        "ez_front_dev/src/assets/logo.png": "Duplicate candidate",
        "ez_front_dev/src/components/FounctionalTest.vue": "Legacy candidate",
        "ez_back_dev/service/agentGraph.py": "Protected product asset",
        "untracked/unknown.bin": "Unknown",
    }
    for path, expected in cases.items():
        assert inventory.classify_path(path, tracked=not path.startswith("untracked")) == expected
        assert inventory.proposed_action(expected) != "delete"


def _workspace_temp_dir() -> Path:
    return Path(tempfile.mkdtemp(prefix=".aspect1-test-", dir=ROOT))


def test_protected_user_data_is_metadata_only():
    tmp_path = _workspace_temp_dir()
    try:
        protected = tmp_path / ".env"
        protected.write_text("SECRET=must-not-be-read\n", encoding="utf-8")
        record = inventory.build_asset_record(
            tmp_path,
            ".env",
            status={"scope": "ignored", "status": "!!"},
            hash_paths={".env"},
            reference=True,
        )
        assert record["classification"] == "Protected user data"
        assert record["exists"] == "present"
        assert record["size_bytes"] is None
        assert record["sha256"] is None
        assert record["reference_evidence"] == []
        assert record["protection"] == "existence_only_no_read_no_size_no_hash"
    finally:
        shutil.rmtree(tmp_path)


def test_git_status_collapses_protected_children_to_metadata_boundaries():
    snapshot = inventory.git_snapshot(ROOT)
    records = snapshot["status"] + snapshot["status_matching"]
    paths = [record["path"] for record in records]
    protected_roots = {
        "example/": ROOT / "example",
        "ez_back_dev/static/projects/": ROOT / "ez_back_dev" / "static" / "projects",
    }
    for protected_path, root in protected_roots.items():
        if root.exists():
            assert protected_path in paths
    assert all(
        not path.startswith("example/") or path == "example/"
        for path in paths
    )
    assert all(
        not path.startswith("ez_back_dev/static/projects/")
        or path == "ez_back_dev/static/projects/"
        for path in paths
    )
    assert all(
        "metadata_only_no_child_paths" in record.values()
        for record in records
        if record["path"] in protected_roots and protected_roots[record["path"]].exists()
    )


def test_normalized_hash_is_cross_platform_and_json_is_canonical():
    tmp_path = _workspace_temp_dir()
    try:
        text_file = tmp_path / "sample.txt"
        text_file.write_bytes(b"\xef\xbb\xbfalpha\r\nbeta\r\n")
        first = inventory.normalized_sha256(text_file)
        text_file.write_bytes(b"alpha\nbeta\n")
        assert inventory.normalized_sha256(text_file) == first

        json_file = tmp_path / "sample.json"
        json_file.write_text('{"b": 2, "a": 1}\n', encoding="utf-8")
        first = inventory.normalized_sha256(json_file)
        json_file.write_text('{\n  "a": 1,\n  "b": 2\n}\n', encoding="utf-8")
        assert inventory.normalized_sha256(json_file) == first
    finally:
        shutil.rmtree(tmp_path)


def test_safe_path_rejects_root_escape_and_protected_roots():
    tmp_path = _workspace_temp_dir()
    try:
        approved = tmp_path / "safe"
        approved.mkdir()
        candidate = approved / ".pytest_cache" / "v" / "cache"
        candidate.parent.mkdir(parents=True)
        candidate.write_text("cache", encoding="utf-8")

        allowed = inventory.validate_candidate_path(
            tmp_path,
            candidate,
            approved_roots=["safe"],
        )
        assert allowed["allowed"] is True

        assert inventory.validate_candidate_path(
            tmp_path,
            approved,
            approved_roots=["safe"],
        )["reason"] == "outside_approved_root"
        assert inventory.validate_candidate_path(
            tmp_path,
            tmp_path / ".." / "outside.txt",
            approved_roots=["safe"],
        )["reason"] == "path_escapes_repository_root"
        assert inventory.validate_candidate_path(
            tmp_path,
            ".env",
            approved_roots=["safe"],
        )["reason"] == "protected_path"
        assert inventory.validate_candidate_path(
            tmp_path,
            "example/project.json",
            approved_roots=["safe"],
        )["reason"] == "protected_path"
    finally:
        shutil.rmtree(tmp_path)


def test_safe_path_rejects_symlink_or_reparse_point_when_supported():
    tmp_path = _workspace_temp_dir()
    try:
        approved = tmp_path / "safe"
        approved.mkdir()
        target = tmp_path / "target"
        target.mkdir()
        link = approved / "link"
        try:
            link.symlink_to(target, target_is_directory=True)
        except (OSError, NotImplementedError):
            pytest.skip("symlink creation is unavailable on this Windows runner")
        result = inventory.validate_candidate_path(
            tmp_path,
            link / "file.txt",
            approved_roots=["safe"],
        )
        assert result == {"allowed": False, "reason": "symlink_or_reparse_point"}
    finally:
        shutil.rmtree(tmp_path)


def test_reference_audit_reports_channels_without_executing_code():
    tmp_path = _workspace_temp_dir()
    try:
        (tmp_path / "router.ts").write_text(
            "const view = () => import('./FounctionalTest.vue')\n", encoding="utf-8"
        )
        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "test_contract.py").write_text(
            "# FounctionalTest.vue is part of this contract fixture\n", encoding="utf-8"
        )
        (tmp_path / "docs.md").write_text("See FounctionalTest.vue\n", encoding="utf-8")
        evidence = inventory.find_references(tmp_path, "FounctionalTest.vue")
        assert {item["channel"] for item in evidence} == {
            "vue_router_template_css",
            "test_or_fixture",
            "documentation",
        }
    finally:
        shutil.rmtree(tmp_path)


def test_baseline_hash_manifest_has_no_missing_required_files():
    manifest = inventory.build_hash_manifest(ROOT)
    assert manifest["hash_policy"] == inventory.HASH_POLICY
    assert manifest["missing"] == []
    assert set(inventory.REQUIRED_HASH_PATHS).issubset(manifest["files"])


def test_migrated_document_hashes_resolve_to_canonical_content_not_redirect_stub():
    manifest = inventory.build_hash_manifest(ROOT)
    entry = manifest["files"]["docs/iteration-4-overview.md"]
    canonical = ROOT / "docs/history/iteration-4/iteration-4-overview.md"
    redirect = ROOT / "docs/iteration-4-overview.md"

    assert entry["resolved_path"] == "docs/history/iteration-4/iteration-4-overview.md"
    assert entry["sha256"] == inventory.normalized_sha256(canonical)
    assert entry["sha256"] != inventory.normalized_sha256(redirect)


def test_canonical_historical_documents_keep_historical_classification():
    assert (
        inventory.classify_path("docs/history/iteration-4/iteration-4-overview.md")
        == "Historical evidence"
    )


def test_migrated_document_hashes_resolve_to_canonical_content_not_redirect_stub():
    manifest = inventory.build_hash_manifest(ROOT)
    entry = manifest["files"]["docs/iteration-4-overview.md"]
    canonical = ROOT / "docs/history/iteration-4/iteration-4-overview.md"
    redirect = ROOT / "docs/iteration-4-overview.md"

    assert entry["resolved_path"] == "docs/history/iteration-4/iteration-4-overview.md"
    assert entry["sha256"] == inventory.normalized_sha256(canonical)
    assert entry["sha256"] != inventory.normalized_sha256(redirect)


def test_canonical_historical_documents_keep_historical_classification():
    assert (
        inventory.classify_path("docs/history/iteration-4/iteration-4-overview.md")
        == "Historical evidence"
    )


def test_inventory_module_has_no_destructive_operation_surface():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "def delete" not in source
    assert "shutil.rmtree" not in source
    assert "Path.unlink" not in source
    assert "--dry-run" in source
    assert "no apply mode exists" in source


def test_inventory_fixture_is_explicitly_reviewed_and_not_auto_accepting():
    fixture = json.loads(
        (
            ROOT
            / "ez_back_dev/tests/fixtures/current/iteration5/iteration5_asset_inventory_v1.json"
        ).read_text(
            encoding="utf-8"
        )
    )
    assert fixture["schema_version"] == "iteration5-asset-inventory-v1"
    assert fixture["review_policy"] == "manual_review_required"
    assert fixture["auto_accept_current_values"] is False
    assert set(fixture["classification_enum"]) == set(inventory.CLASSIFICATIONS)
    for asset in fixture["assets"]:
        assert set(("scope", "path_or_resource", "classification", "source", "proposed_action", "recovery", "review_state")) <= set(asset)
        assert asset["review_state"] in {"reviewed", "protected"}
