"""Static contract tests for the Aspect 6 modular runtime surface."""

from __future__ import annotations

import json
import importlib.util
import subprocess
import sys
import time
from tempfile import TemporaryDirectory
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[4]
CONTRACT_PATH = REPO_ROOT / "ops" / "modular-runtime-contract.json"
BASELINE_PATH = (
    REPO_ROOT
    / "ez_back_dev"
    / "tests"
    / "fixtures"
    / "current"
    / "iteration5"
    / "iteration5_modular_runtime_baseline_v1.json"
)
CHECKER_PATH = REPO_ROOT / "scripts" / "check_modular_runtime.py"
RUNTIME_PATH = REPO_ROOT / "scripts" / "modular_runtime.py"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_runtime_module():
    spec = importlib.util.spec_from_file_location("aspect6_modular_runtime", RUNTIME_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_modular_runtime_contract_is_explicit_and_non_sensitive() -> None:
    assert CONTRACT_PATH.is_file()
    contract = _read_json(CONTRACT_PATH)

    assert contract["schema_version"] == "iteration5-modular-runtime-v1"
    assert contract["managed_start_order"] == [
        "legacy-api",
        "agent-api",
        "worker",
        "frontend",
    ]
    assert contract["external_dependencies"] == ["mysql", "redis"]
    assert contract["runner_owned"] == [
        "legacy-api",
        "agent-api",
        "worker",
        "frontend",
    ]
    assert contract["auto_accept_current_values"] is False
    serialized = json.dumps(contract, ensure_ascii=False).casefold()
    for forbidden in ("api_key", "password", "project-id", "project_id"):
        assert forbidden not in serialized


def test_modular_runtime_baseline_requires_manual_parent_and_protection() -> None:
    assert BASELINE_PATH.is_file()
    baseline = _read_json(BASELINE_PATH)

    assert baseline["schema_version"] == "iteration5-modular-runtime-baseline-v1"
    assert baseline["aspect"] == 6
    assert baseline["manual_reviewed"] is True
    assert baseline["auto_accept_current_values"] is False
    assert baseline["parent"]["fixture"]
    assert baseline["parent"]["fixture_sha256"]
    assert baseline["protected_paths"]
    assert baseline["removed_paths"] == []


def test_modular_runtime_checker_passes_the_reviewed_contract() -> None:
    assert CHECKER_PATH.is_file()
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            str(CHECKER_PATH),
            "--check",
            "--repo-root",
            str(REPO_ROOT),
            "--format",
            "json",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_modular_runtime_cli_has_no_mutating_modes() -> None:
    result = subprocess.run(
        [sys.executable, "-B", str(CHECKER_PATH), "--help"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    source = result.stdout
    for option in ("--accept-current", "--update", "--write", "--delete"):
        assert option not in source


def test_modular_runtime_preserves_existing_health_routes_in_source() -> None:
    legacy_source = (REPO_ROOT / "ez_back_dev" / "app" / "main.py").read_text(
        encoding="utf-8"
    )
    agent_source = (REPO_ROOT / "ez_back_dev" / "app" / "agentApi.py").read_text(
        encoding="utf-8"
    )
    assert '@app.get("/health")' in legacy_source
    assert '@app.get("/health")' in agent_source


def test_explicit_env_file_parser_rejects_unknown_names() -> None:
    runtime = _load_runtime_module()
    with TemporaryDirectory(prefix="ezllmtest-aspect6-", dir=str(REPO_ROOT.parent)) as directory:
        env_file = Path(directory) / "runtime.env"
        env_file.write_text(
            "DATABASE_URL=sqlite://\nUNKNOWN_RUNTIME_VALUE=1\n",
            encoding="utf-8",
        )

        values = runtime._parse_env_file(str(env_file))
        with pytest.raises(runtime.RuntimeErrorBase):
            runtime._validate_env_names(REPO_ROOT, values)


def test_frontend_child_environment_filters_backend_values() -> None:
    runtime = _load_runtime_module()
    with TemporaryDirectory(prefix="ezllmtest-aspect6-", dir=str(REPO_ROOT.parent)) as directory:
        env_file = Path(directory) / "runtime.env"
        sensitive_name = "ZHIPU" + "_API_KEY"
        env_file.write_text(
            "DATABASE_URL=sqlite://\n"
            "AGENT_REDIS_URL=redis://127.0.0.1:6379/0\n"
            + sensitive_name
            + "=fixture-only\n"
            "VUE_APP_API_BASE_URL=http://127.0.0.1:8130\n",
            encoding="utf-8",
        )

        values = runtime._parse_env_file(str(env_file))
        child = runtime._safe_child_env(REPO_ROOT, values, frontend=True)

        assert child["VUE_APP_API_BASE_URL"] == "http://127.0.0.1:8130"
        assert sensitive_name not in child


def test_runtime_state_path_cannot_be_inside_repository() -> None:
    runtime = _load_runtime_module()
    state_path = runtime._state_root("0123456789abcdef")

    assert REPO_ROOT not in state_path.parents


def test_process_stop_requires_matching_identity() -> None:
    runtime = _load_runtime_module()
    process = subprocess.Popen(
        [sys.executable, "-B", "-c", "import time; time.sleep(30)"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        identity = None
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            identity = runtime._process_identity(process.pid)
            if identity is not None:
                break
            time.sleep(0.1)
        if identity is None:
            process.terminate()
            process.wait(timeout=5)
            pytest.skip("host cannot provide process identity metadata")

        record = {
            "pid": process.pid,
            "creation_time": identity["creation_time"],
            "command_fingerprint": runtime._fingerprint(
                identity["command_line"].split()
            ),
        }
        assert runtime._identity_matches(record)
        assert runtime._terminate_record(record, timeout=2)
        assert runtime._process_identity(process.pid) is None
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
