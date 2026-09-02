"""Static Aspect 8 contract tests that do not start external services."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from repo_paths import REPO_ROOT, fixture_path


def _load_script(name: str, relative: str):
    path = REPO_ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load {relative}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


checker = _load_script("iteration5_closeout_checker", "scripts/check_iteration5_closeout.py")
harness = _load_script(
    "iteration5_dual_mode_harness", "scripts/run_iteration5_dual_mode_acceptance.py"
)


CONTRACT = REPO_ROOT / "ops/iteration5-dual-mode-acceptance-contract.json"
BASELINE = fixture_path(
    "current", "iteration5", "iteration5_dual_mode_acceptance_baseline_v1.json"
)
MIGRATION = fixture_path(
    "current", "iteration5", "iteration5_dual_mode_acceptance_migration_v1.json"
)


def test_aspect8_contract_and_reviewed_fixtures_exist():
    assert CONTRACT.is_file()
    assert BASELINE.is_file()
    assert MIGRATION.is_file()
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert contract["schema_version"] == "iteration5-dual-mode-acceptance-v1"
    assert contract["manual_reviewed"] is True
    assert contract["auto_accept_current_values"] is False


def test_immutable_acceptance_dataset_is_the_historical_fixture():
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    spec = contract["acceptance_dataset"]
    dataset = json.loads((REPO_ROOT / spec["path"]).read_text(encoding="utf-8"))
    assert spec["immutable"] is True
    assert spec["provider"] == "deterministic_fake"
    assert dataset["dataset_id"] == "iteration4-agent-acceptance-v1"
    assert len(dataset["cases"]) == 18
    assert [case["id"] for case in dataset["cases"]] == spec["case_ids"]
    assert tuple(harness.ACCEPTANCE_CASE_IDS) == tuple(spec["case_ids"])


def test_parent_evidence_and_public_snapshot_are_explicit():
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert sum(len(items) for items in contract["parent_evidence"].values()) >= 9
    assert contract["public_contracts"] == {
        "workflow_count": 19,
        "tool_count": 22,
        "rest_sse_mcp_snapshot": "historical-and-current-contract-tests",
        "health_paths": ["/health"],
        "readiness_paths": ["/ready"],
    }


def test_closeout_checker_is_read_only_and_current_contract_is_checkable():
    report = checker.check_repository(REPO_ROOT)
    assert report["status"] == "pass", report["errors"]
    assert report["scope"]["reads_environment_files"] is False
    assert report["scope"]["reads_user_projects"] is False
    assert report["scope"]["contacts_external_services"] is False


def test_closeout_checker_rejects_write_and_auto_accept_switches():
    with pytest.raises(SystemExit):
        checker._parser().parse_args(["--check", "--accept-current"])
    with pytest.raises(SystemExit):
        checker._parser().parse_args(["--check", "--update"])
    with pytest.raises(SystemExit):
        checker._parser().parse_args(["--check", "--write"])
    with pytest.raises(SystemExit):
        checker._parser().parse_args(["--check", "--delete"])


def test_report_directory_must_be_outside_the_explicit_repo_root():
    with pytest.raises(harness.AcceptanceHarnessError):
        harness._external_report_dir(REPO_ROOT / "aspect8-reports", REPO_ROOT)


def test_runner_source_has_no_shell_or_broad_cleanup_path():
    source = (REPO_ROOT / "scripts/run_iteration5_dual_mode_acceptance.py").read_text(
        encoding="utf-8"
    )
    assert "shell=False" in source
    assert "--pull" in source
    assert "docker system prune" not in source.casefold()
    assert "docker volume prune" not in source.casefold()
    assert "static/projects" not in source
    assert "--accept-current" not in source
