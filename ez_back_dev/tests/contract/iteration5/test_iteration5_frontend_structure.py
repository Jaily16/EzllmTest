from __future__ import annotations

import importlib.util
import json
import hashlib
import sys
from pathlib import Path

import pytest

from repo_paths import fixture_path
from repo_paths import REPO_ROOT as ROOT

SCRIPT = ROOT / "scripts" / "check_frontend_structure.py"
SPEC = importlib.util.spec_from_file_location("check_frontend_structure", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
checker = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = checker
SPEC.loader.exec_module(checker)


BASELINE = fixture_path(
    "current", "iteration5", "iteration5_frontend_structure_baseline_v1.json"
)
MIGRATION = fixture_path(
    "current", "iteration5", "iteration5_frontend_structure_migration_v1.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_baseline_is_explicit_and_reviewed():
    baseline = _load(BASELINE)
    assert baseline["schema_version"] == "iteration5-frontend-structure-baseline-v1"
    assert baseline["manual_reviewed"] is True
    assert baseline["auto_accept_current_values"] is False
    assert baseline["source_path_map"]
    assert baseline["route_snapshot"]["paths"]
    assert baseline["removed_paths"] == []


def test_migration_fixture_has_no_implicit_accept_or_wildcard_delete():
    migration = _load(MIGRATION)
    assert migration["manual_reviewed"] is True
    assert migration["auto_accept_current_values"] is False
    assert migration["removed_paths"] == [
        "ez_front_dev/src/assets/static/image/acceptanceTest.png",
        "ez_front_dev/src/assets/static/image/apiTest.png",
        "ez_front_dev/src/assets/static/image/functionalTest.png",
        "ez_front_dev/src/assets/static/image/integrationTest.png",
        "ez_front_dev/src/assets/static/image/nonfunctionalTest.png",
        "ez_front_dev/src/assets/static/image/testPlan.png",
        "ez_front_dev/src/assets/static/image/UITest.png",
        "ez_front_dev/src/assets/static/image/unitTest.png",
        "ez_front_dev/src/assets/static/image/databaseTest.png",
    ]
    assert all("*" not in path and "?" not in path for path in migration["removed_paths"])
    removal_batch = next(
        item for item in migration["batches"] if item["id"] == "legacy-test-image-precise-removal"
    )
    assert {item["old_path"] for item in removal_batch["paths"]} == set(
        migration["removed_paths"]
    )


def test_canonical_map_is_explicit_for_routes_and_assets():
    baseline = _load(BASELINE)
    route = baseline["route_snapshot"]
    assert route["functional"]["operation"] == "functional_case"
    assert route["functional"]["lazy_loaded"] is True
    assert route["agent"]["lazy_loaded"] is True
    assert "ez_front_dev/src/assets/static/image/ezlogo-workbench-v2.png" in baseline[
        "asset_snapshot"
    ]


def test_active_asset_moves_preserve_reviewed_binary_hashes():
    migration = _load(MIGRATION)
    batch = next(
        item for item in migration["batches"] if item["id"] == "active-asset-canonical-move"
    )
    assert len(batch["paths"]) == 12
    for record in batch["paths"]:
        old_path = ROOT / record["old_path"]
        new_path = ROOT / record["new_path"]
        assert record["content_preserved"] is True
        assert record["manual_review"] is True
        assert not old_path.exists()
        assert new_path.is_file()
        actual = hashlib.sha256(new_path.read_bytes()).hexdigest()
        assert actual == record["post_hash"] == record["pre_hash"]


def test_checker_accepts_only_the_reviewed_canonical_state():
    report = checker.check_repository(ROOT)
    assert report.exit_code == 0, report.errors


def test_document_redirect_stubs_map_to_reviewed_byte_preserving_moves():
    migration = _load(MIGRATION)
    redirects = migration["redirect_stubs"]
    assert len(redirects) == 43
    records = {}
    for batch in migration["batches"]:
        for record in batch["paths"]:
            if record["old_path"].startswith("docs/"):
                records.setdefault(record["old_path"], []).append(record)
    for redirect in redirects:
        old = ROOT / redirect["old_path"]
        new = ROOT / redirect["new_path"]
        assert old.is_file()
        assert new.is_file()
        assert old.read_bytes() != new.read_bytes()
        assert "frontend-structure.md" in old.read_text(encoding="utf-8")
        matching = records[redirect["old_path"]]
        move_record = next(
            record
            for record in reversed(matching)
            if record["new_path"] == redirect["new_path"]
            and record["content_preserved"] is True
        )
        latest_record = next(
            record
            for record in reversed(matching)
            if record["new_path"] == redirect["new_path"]
        )
        assert move_record["manual_review"] is True
        assert latest_record["manual_review"] is True
        later_hash = checker._later_reviewed_hashes(ROOT).get(redirect["new_path"])
        assert checker.normalized_sha256(new).lower() in {
            str(latest_record["post_hash"]).lower(),
            str(later_hash).lower(),
        }


def test_checker_rejects_auto_accepting_a_modified_migration_fixture():
    migration = _load(MIGRATION)
    migration["auto_accept_current_values"] = True
    report = checker.CheckReport()
    checker._validate_migration(ROOT, migration, report)
    assert report.exit_code == 1
    assert any("auto-accept" in item for item in report.errors)


def test_safe_path_rejects_protected_and_outside_targets():
    safe = ROOT / "ez_front_dev/src/App.vue"
    assert checker.validate_migration_path(
        ROOT, safe, ["ez_front_dev/src"]
    ) == (True, "ok")
    assert checker.validate_migration_path(
        ROOT, ROOT / ".env", ["ez_front_dev/src"]
    ) == (False, "protected_path")
    assert checker.validate_migration_path(
        ROOT, ROOT / "example" / "file.txt", ["ez_front_dev/src"]
    ) == (False, "protected_path")
    assert checker.validate_migration_path(
        ROOT, ROOT.parent / "outside.txt", ["ez_front_dev/src"]
    ) == (False, "path_escapes_repository_root")


def test_safe_path_checker_contains_reparse_protection_without_creating_links():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "is_symlink()" in source
    assert "st_file_attributes" in source
    assert checker.validate_migration_path(
        ROOT, "ez_front_dev/src/nonexistent-safe-target.vue", ["ez_front_dev/src"]
    ) == (True, "ok")


def test_checker_cli_surface_is_read_only():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "def main" in source
    assert "check_repository" in source
    for forbidden in ("--accept-current", "--update", "--write", "--delete"):
        with pytest.raises(SystemExit):
            checker._parse_args(["--check", forbidden])
