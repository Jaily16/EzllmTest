"""Static and historical contracts for Iteration 5 Aspect 7."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
CONTRACT = ROOT / "ops" / "container-delivery-contract.json"
BASELINE = (
    ROOT
    / "ez_back_dev"
    / "tests"
    / "fixtures"
    / "current"
    / "iteration5"
    / "iteration5_container_delivery_baseline_v1.json"
)
MIGRATION = (
    ROOT
    / "ez_back_dev"
    / "tests"
    / "fixtures"
    / "current"
    / "iteration5"
    / "iteration5_container_delivery_migration_v1.json"
)
CHECKER = ROOT / "scripts" / "check_container_delivery.py"
ASPECT6_MIGRATION = (
    ROOT
    / "ez_back_dev"
    / "tests"
    / "fixtures"
    / "current"
    / "iteration5"
    / "iteration5_modular_runtime_migration_v1.json"
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalized_sha256(path: Path) -> str:
    payload = path.read_bytes()
    text = payload.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    payload = (text.rstrip("\n") + "\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _load_checker():
    spec = importlib.util.spec_from_file_location("iteration5_container_delivery", CHECKER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_container_contract_is_explicit_and_non_sensitive() -> None:
    assert CONTRACT.is_file()
    contract = _load_json(CONTRACT)

    assert contract["schema_version"] == "iteration5-container-delivery-v1"
    assert contract["aspect"] == 7
    assert contract["auto_accept_current_values"] is False
    assert contract["default_services"] == [
        "frontend",
        "legacy-api",
        "agent-api",
        "worker",
        "mysql",
        "redis",
        "otel-collector",
        "prometheus",
        "tempo",
        "grafana",
    ]
    assert contract["observability_services"] == [
        "otel-collector",
        "prometheus",
        "tempo",
        "grafana",
    ]
    serialized = json.dumps(contract, ensure_ascii=False).casefold()
    for forbidden in (
        "api_key=",
        "password=",
        "/run/secrets/",
        "project-id",
        "project_id",
    ):
        assert forbidden not in serialized


def test_container_baseline_has_manual_parent_and_protected_hashes() -> None:
    assert BASELINE.is_file()
    baseline = _load_json(BASELINE)
    assert baseline["schema_version"] == "iteration5-container-delivery-baseline-v1"
    assert baseline["aspect"] == 7
    assert baseline["manual_reviewed"] is True
    assert baseline["auto_accept_current_values"] is False
    assert baseline["parent"]["fixture"]
    assert baseline["parent"]["fixture_sha256"]
    assert baseline["protected_paths"]
    assert baseline["protected_hashes"]
    assert baseline["removed_paths"] == []

    parent = ROOT / baseline["parent"]["fixture"]
    assert _normalized_sha256(parent) == baseline["parent"]["fixture_sha256"]


def test_container_migration_is_reviewed_and_does_not_remove_paths() -> None:
    assert MIGRATION.is_file()
    migration = _load_json(MIGRATION)
    assert migration["schema_version"] == "iteration5-container-delivery-migration-v1"
    assert migration["aspect"] == 7
    assert migration["manual_reviewed"] is True
    assert migration["auto_accept_current_values"] is False
    assert migration["removed_paths"] == []
    assert isinstance(migration["batches"], list)


def test_parent_aspect6_migration_hash_is_immutable() -> None:
    baseline = _load_json(BASELINE)
    parent = ROOT / baseline["parent"]["fixture"]
    assert parent == ASPECT6_MIGRATION
    assert _normalized_sha256(parent) == baseline["parent"]["fixture_sha256"]


def test_container_checker_accepts_only_the_reviewed_state() -> None:
    assert CHECKER.is_file()
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            str(CHECKER),
            "--check",
            "--repo-root",
            str(ROOT),
            "--format",
            "json",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_container_checker_has_no_mutating_modes() -> None:
    result = subprocess.run(
        [sys.executable, "-B", str(CHECKER), "--help"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    for option in (
        "--accept-current",
        "--update",
        "--write",
        "--build",
        "--start",
        "--stop",
        "--delete",
        "--prune",
    ):
        assert option not in result.stdout


def test_dockerignore_protects_env_and_user_project_files() -> None:
    source = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    for pattern in (".env", "**/.env", "**/node_modules", "**/dist", "ez_back_dev/static/projects"):
        assert pattern in source


def test_protected_previous_iteration_hashes_are_not_replaced_by_aspect7() -> None:
    baseline = _load_json(BASELINE)
    for relative, expected in baseline["protected_hashes"].items():
        path = ROOT / relative
        assert path.is_file(), relative
        assert _normalized_sha256(path) == expected, relative
