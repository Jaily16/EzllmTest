from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

from repo_paths import REPO_ROOT as ROOT

SCRIPT = ROOT / "scripts" / "check_style_contract.py"
CONTRACT = ROOT / "ops" / "version-contract.json"
STYLE_BASELINE = ROOT / (
    "ez_back_dev/tests/fixtures/current/iteration5/iteration5_style_baseline_v1.json"
)


def _checker():
    spec = importlib.util.spec_from_file_location("iteration5_style_checker", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load(relative: str) -> dict:
    if relative.startswith("ez_back_dev/tests/fixtures/iteration5_"):
        relative = relative.replace(
            "ez_back_dev/tests/fixtures/",
            "ez_back_dev/tests/fixtures/current/iteration5/",
            1,
        )
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def _copy_style_inputs(tmp_path: Path) -> Path:
    baseline = _load(
        "ez_back_dev/tests/fixtures/current/iteration5/iteration5_style_baseline_v1.json"
    )
    contract = _load("ops/version-contract.json")
    copied_root = tmp_path / "repo"
    copied_root.mkdir()
    paths = {
        "ops/version-contract.json",
        "ez_back_dev/tests/fixtures/current/iteration5/iteration5_style_baseline_v1.json",
        "ez_back_dev/tests/fixtures/current/iteration5/iteration5_style_migration_v1.json",
        "ez_back_dev/tests/fixtures/current/iteration5/iteration5_backend_architecture_baseline_v1.json",
        "ez_back_dev/tests/fixtures/current/iteration5/iteration5_backend_migration_v1.json",
        "ez_back_dev/tests/fixtures/current/iteration5/iteration5_frontend_structure_migration_v1.json",
        "ez_back_dev/tests/fixtures/current/iteration5/iteration5_version_migration_v1.json",
        "README.md",
        "docs/versions.md",
        ".editorconfig",
        ".gitattributes",
        "ruff.toml",
        ".prettierrc.json",
        ".prettierignore",
        "ez_front_dev/package.json",
        "ez_front_dev/package-lock.json",
        "ez_front_dev/eslint.config.mjs",
        ".github/workflows/iteration4-offline.yml",
        "scripts/check_style_contract.py",
        "ez_back_dev/requirements-dev.in",
        "ez_back_dev/requirements-dev.txt",
        "ez_back_dev/requirements-dev-windows.txt",
    }
    paths.update(baseline["format_scope"])
    paths.update(baseline["protected_hashes"])
    paths.update(contract["quality_tools"]["paths"].values())
    paths.add(contract["human_doc"])

    structure_migration = _load(
        "ez_back_dev/tests/fixtures/current/iteration5/"
        "iteration5_frontend_structure_migration_v1.json"
    )
    structure_map = {
        item["old_path"].replace("\\", "/"): item["new_path"].replace("\\", "/")
        for batch in structure_migration["batches"]
        for item in batch["paths"]
    }
    architecture = _load(
        "ez_back_dev/tests/fixtures/current/iteration5/"
        "iteration5_backend_architecture_baseline_v1.json"
    )
    backend_map = {
        f"ez_back_dev/{old.replace('.', '/')}.py": f"ez_back_dev/{new.replace('.', '/')}.py"
        for old, new in architecture["module_map"].items()
    }

    def canonical_copy_relative(relative: str) -> str:
        normalized = relative.replace("\\", "/")
        if normalized.startswith("ez_back_dev/tests/fixtures/iteration5_"):
            normalized = normalized.replace(
                "ez_back_dev/tests/fixtures/",
                "ez_back_dev/tests/fixtures/current/iteration5/",
                1,
            )
        normalized = structure_map.get(normalized, normalized)
        normalized = backend_map.get(normalized, normalized)
        return normalized

    for relative in paths:
        relative = canonical_copy_relative(relative)
        source = ROOT / relative
        if not source.is_file():
            continue
        target = copied_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return copied_root


def test_active_style_contract_passes_without_writing():
    report = _checker().check_style_contract(ROOT)
    assert report["status"] == "pass", report["errors"]


def test_style_baseline_is_explicitly_reviewed_and_not_auto_accepted():
    baseline = _load("ez_back_dev/tests/fixtures/iteration5_style_baseline_v1.json")
    assert baseline["schema_version"] == "iteration5-style-baseline-v1"
    assert baseline["manual_reviewed"] is True
    assert baseline["auto_accept_current_values"] is False
    assert baseline["format_scope"]
    assert baseline["manual_review_scope"]
    assert baseline["protected_hashes"]
    assert baseline["comment_coverage"]


def test_quality_tools_are_locked_and_linked_to_the_version_contract():
    contract = _load("ops/version-contract.json")
    quality = contract["quality_tools"]
    assert quality["ruff"]["version"] == "0.16.5"
    assert quality["prettier"]["version"] == "3.9.6"
    assert quality["python_dev_locks"]
    assert quality["paths"]["style_baseline"] == (
        "ez_back_dev/tests/fixtures/iteration5_style_baseline_v1.json"
    )


def test_checker_rejects_a_missing_dev_lock(tmp_path):
    copied_root = _copy_style_inputs(tmp_path)
    lock = copied_root / "ez_back_dev/requirements-dev.txt"
    lock.unlink()
    report = _checker().check_style_contract(copied_root)
    assert report["status"] == "fail"
    assert any(item["id"] == "dev_lock.linux" for item in report["errors"])


def test_checker_rejects_a_non_sha256_dev_lock_hash(tmp_path):
    copied_root = _copy_style_inputs(tmp_path)
    lock = copied_root / "ez_back_dev/requirements-dev.txt"
    text = lock.read_text(encoding="utf-8")
    lock.write_text(text.replace("--hash=sha256:", "--hash=sha512:", 1), encoding="utf-8")
    report = _checker().check_style_contract(copied_root)
    assert report["status"] == "fail"
    assert any(item["id"] == "dev_lock.linux" for item in report["errors"])


def test_checker_rejects_protected_scope_in_a_mutated_baseline(tmp_path):
    copied_root = _copy_style_inputs(tmp_path)
    baseline_path = copied_root / (
        "ez_back_dev/tests/fixtures/current/iteration5/iteration5_style_baseline_v1.json"
    )
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    baseline["format_scope"].append(".env")
    baseline_path.write_text(json.dumps(baseline, ensure_ascii=False), encoding="utf-8")
    report = _checker().check_style_contract(copied_root)
    assert report["status"] == "fail"
    assert any(item["id"].startswith("baseline.scope") for item in report["errors"])


def test_checker_rejects_real_environment_paths():
    checker = _checker()
    try:
        checker._safe_path(ROOT, ".env")
    except checker.ContractError:
        pass
    else:
        raise AssertionError("real .env must be rejected")


def test_required_public_comment_registry_is_present():
    checker = _checker()
    baseline = _load("ez_back_dev/tests/fixtures/iteration5_style_baseline_v1.json")
    registered = {item["symbol"] for item in baseline["comment_coverage"]}
    assert set(checker.REQUIRED_COMMENT_SYMBOLS) <= registered


def test_style_checker_has_no_mutating_accept_or_update_mode():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "accept-current" not in text
    assert "--update" not in text
    assert "--write" not in text
    assert "--fix" not in text


def test_ci_exposes_read_only_style_gates():
    text = (ROOT / ".github/workflows/iteration4-offline.yml").read_text(encoding="utf-8")
    for required in (
        "python scripts/check_style_contract.py --check --format text",
        "ruff check",
        "ruff format --check",
        "npm run format:check",
        "npm run lint -- --no-fix",
        "npm run type-check",
    ):
        assert required in text
    assert "ruff format --write" not in text
    assert "prettier --write" not in text


def test_protected_public_files_are_not_in_style_format_scope():
    baseline = _load("ez_back_dev/tests/fixtures/iteration5_style_baseline_v1.json")
    scope = set(baseline["format_scope"])
    protected = {
        "ez_back_dev/app/agentApi.py",
        "ez_back_dev/app/mcpServer.py",
        "ez_back_dev/app/routers.py",
        "ez_back_dev/service/agentCheckpoint.py",
        "ez_back_dev/service/agentContracts.py",
        "ez_back_dev/service/agentRedisCoordinator.py",
        "ez_back_dev/service/agentRuntimeService.py",
        "ez_back_dev/service/agentToolExecutor.py",
        "ez_back_dev/service/workflowBudget.py",
        "ez_back_dev/service/workflowCatalog.py",
        "ez_front_dev/src/components/AgentWorkbench.vue",
        "ez_front_dev/src/composables/useAgentEvents.ts",
        "ez_front_dev/src/router/index.ts",
    }
    assert protected.isdisjoint(scope)
