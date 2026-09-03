"""Static architecture and migration contracts for Iteration 5 Aspect 4."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


from repo_paths import REPO_ROOT as ROOT, canonical_document_path


_RELOCATED_PATHS = {
    "ez_back_dev/tests/fixtures/iteration3_contract_baseline_v1.json":
        "ez_back_dev/tests/fixtures/historical/iteration3/iteration3_contract_baseline_v1.json",
    "ez_back_dev/tests/fixtures/iteration4_release_manifest_v1.json":
        "ez_back_dev/tests/fixtures/historical/iteration4/iteration4_release_manifest_v1.json",
    "ez_back_dev/tests/fixtures/iteration5_style_migration_v1.json":
        "ez_back_dev/tests/fixtures/current/iteration5/iteration5_style_migration_v1.json",
}
FIXTURE_PATH = ROOT / (
    "ez_back_dev/tests/fixtures/current/iteration5/"
    "iteration5_backend_architecture_baseline_v1.json"
)
CHECKER_PATH = ROOT / "scripts/check_backend_boundaries.py"


def _repository_path(relative: str) -> Path:
    if relative.replace("\\", "/").startswith("docs/"):
        return canonical_document_path(relative)
    return ROOT / _RELOCATED_PATHS.get(relative, relative)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_checker():
    spec = importlib.util.spec_from_file_location("iteration5_backend_boundaries", CHECKER_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError(f"unable to load {CHECKER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _normalized_sha256(path: Path) -> str:
    payload = path.read_bytes()
    if path.suffix.casefold() == ".json":
        value = json.loads(payload.decode("utf-8-sig"))
        payload = (
            json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            .encode("utf-8")
            + b"\n"
        )
    else:
        payload = payload.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
        payload = (payload.rstrip("\n") + "\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def test_canonical_package_map_is_explicit_and_not_auto_accepted():
    fixture = _load_json(FIXTURE_PATH)
    assert fixture["schema_version"] == "iteration5-backend-architecture-v1"
    assert fixture["aspect"] == 4
    assert fixture["canonical_packages"]
    assert fixture["module_map"]
    assert fixture["auto_accept_current_values"] is False
    assert fixture["manual_reviewed"] is True


def test_checker_accepts_canonical_packages_and_explicit_shims():
    checker = _load_checker()
    report = checker.check_repository(ROOT)
    assert report["status"] == "pass"
    assert report["errors"] == []


def test_public_contract_snapshot_is_read_from_immutable_parent_fixture():
    fixture = _load_json(FIXTURE_PATH)
    parent = _repository_path(fixture["parent"]["fixture"])
    assert parent.is_file()
    assert _normalized_sha256(parent) == fixture["parent"]["fixture_sha256"]
    public = _load_json(
        ROOT / "ez_back_dev/tests/fixtures/historical/iteration3/"
        "iteration3_contract_baseline_v1.json"
    )
    assert public["workflow_count"] == 19
    assert len(public["workflows"]) == 19
    assert public["retention"]["preliminary_analysis"] == "persisted"


def test_historical_fixture_hashes_are_explicit_and_unchanged():
    fixture = _load_json(FIXTURE_PATH)
    for relative, expected in fixture["historical_hashes"].items():
        path = _repository_path(relative)
        assert path.is_file(), relative
        assert _normalized_sha256(path) == expected, relative


def test_unknown_dynamic_imports_are_not_silently_accepted():
    fixture = _load_json(FIXTURE_PATH)
    assert fixture["unresolved_dynamic_imports"] == []
    assert fixture["dynamic_import_exceptions"]


def test_removed_paths_are_empty_until_separate_review():
    fixture = _load_json(FIXTURE_PATH)
    assert fixture["removed_paths"] == []
