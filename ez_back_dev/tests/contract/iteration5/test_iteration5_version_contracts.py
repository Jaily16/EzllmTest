from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path


from repo_paths import REPO_ROOT as ROOT
SCRIPT = ROOT / "scripts" / "check_version_contract.py"


def _checker():
    spec = importlib.util.spec_from_file_location("iteration5_version_checker", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _contract():
    return json.loads(
        (ROOT / "ops" / "version-contract.json").read_text(encoding="utf-8")
    )


def _copy_contract_inputs(tmp_path: Path) -> Path:
    checker = _checker()
    contract = _contract()
    copied_root = tmp_path / "repo"
    copied_root.mkdir()
    paths = {
        "ops/version-contract.json",
        "README.md",
        contract["human_doc"],
        contract["runtime"]["python"]["dockerfile"],
        contract["runtime"]["node"]["dockerfile"],
        contract["runtime"]["python"]["ci_workflow"],
        contract["python_lock"]["input"],
        *contract["python_lock"]["locks"].values(),
        contract["node_lock"]["manifest"],
        contract["node_lock"]["lock"],
        contract["images"]["compose"],
    }
    for relative in paths:
        source = ROOT / relative
        target = copied_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    assert checker.check_contract(copied_root)["status"] == "pass"
    return copied_root


def test_active_contract_has_expected_schema_and_targets():
    contract = _contract()
    assert contract["schema_version"] == "iteration5-version-contract-v1"
    assert contract["product_release"] == "0.1.0"
    assert contract["runtime"]["python"]["line"] == "3.11"
    assert contract["runtime"]["node"]["line"] == "24"
    assert contract["runtime"]["node"]["npm_major"] == 11
    assert contract["python_lock"]["generator"] == {
        "name": "pip-tools",
        "version": "7.6.1",
    }


def test_checker_passes_current_contract_without_writing():
    report = _checker().check_contract(ROOT)
    assert report["status"] == "pass", report["errors"]


def test_checker_rejects_a_missing_lock(tmp_path):
    copied_root = _copy_contract_inputs(tmp_path)
    lock = copied_root / _contract()["python_lock"]["locks"]["linux"]
    lock.unlink()
    report = _checker().check_contract(copied_root)
    assert report["status"] == "fail"
    assert any(item["id"] == "python_lock.linux" for item in report["errors"])


def test_checker_rejects_a_hashless_requirement(tmp_path):
    copied_root = _copy_contract_inputs(tmp_path)
    lock = copied_root / _contract()["python_lock"]["locks"]["linux"]
    text = lock.read_text(encoding="utf-8")
    lock.write_text(text.replace("--hash=sha256:", "--hash=sha256:", 1).replace("--hash=sha256:", "--hash=sha512:", 1), encoding="utf-8")
    report = _checker().check_contract(copied_root)
    assert report["status"] == "fail"
    assert any(item["id"] == "python_lock.linux" for item in report["errors"])


def test_checker_rejects_a_mutable_compose_image_tag(tmp_path):
    copied_root = _copy_contract_inputs(tmp_path)
    compose = copied_root / _contract()["images"]["compose"]
    text = compose.read_text(encoding="utf-8")
    compose.write_text(text.replace("0.1.0", "iteration5-test", 1), encoding="utf-8")
    report = _checker().check_contract(copied_root)
    assert report["status"] == "fail"
    assert any(item["id"] == "compose.app_tags" for item in report["errors"])


def test_checker_never_reads_real_environment_paths():
    checker = _checker()
    try:
        checker._safe_path(ROOT, ".env")
    except checker.ContractError:
        pass
    else:
        raise AssertionError("real .env must be rejected")


def test_checker_has_no_auto_accept_mode():
    assert "accept-current" not in SCRIPT.read_text(encoding="utf-8")
    assert "--update" not in SCRIPT.read_text(encoding="utf-8")


def test_quality_tools_are_additive_and_dev_only():
    contract = _contract()
    quality = contract["quality_tools"]
    assert quality["ruff"] == {
        "name": "ruff",
        "version": "0.16.5",
        "config": "ruff.toml",
        "policy": "format and lint only the explicit Aspect 3 baseline scope",
    }
    assert quality["prettier"] == {
        "name": "prettier",
        "version": "3.9.6",
        "config": ".prettierrc.json",
        "policy": "format and check only the explicit active frontend/config/document scope",
    }
    assert quality["python_dev_locks"]["generator"] == {
        "name": "pip-tools",
        "version": "7.6.1",
    }
