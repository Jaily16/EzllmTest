"""Run and inspect the explicit, loopback-only modular EzLLM stack."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


CONTRACT_RELATIVE = Path("ops/modular-runtime-contract.json")
STATE_ROOT_NAME = "ezllmtest-modular-runtime"
RUN_ID_RE = re.compile(r"^[a-f0-9]{16,64}$")
ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1", "[::1]"}
READINESS_SCHEMA_VERSION = "iteration5-readiness-v1"
EXPECTED_TABLES = {
    "tb_project_design_testdoc",
    "tb_project_info",
    "tb_project_knowledge",
    "tb_project_requirement_testdoc",
    "tb_project_type",
    "tb_test_project",
    "tb_project_workflow_artifact",
}
SENSITIVE_ENV_RE = re.compile(
    r"(?:_API_KEY$|PASSWORD|SECRET|TOKEN|DATABASE_URL$|REDIS_URL$)",
    re.IGNORECASE,
)
INTERNAL_ENV_NAMES = {
    "PYTHON_DOTENV_DISABLED",
    "EZLLMTEST_VITE_ENV_DIR",
}


class RuntimeErrorBase(ValueError):
    """Raised for safe, user-actionable runtime configuration errors."""


def _repo_root(value: str | None) -> Path:
    root = Path(value) if value else Path(__file__).resolve().parents[1]
    if not root.is_absolute():
        raise RuntimeErrorBase("repo-root must be an absolute path")
    root = root.resolve()
    if not root.is_dir():
        raise RuntimeErrorBase("repo-root is not a directory")
    return root


def _repo_path(root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute():
        raise RuntimeErrorBase("repository paths must be relative")
    candidate = (root / path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise RuntimeErrorBase("repository path escapes repo-root") from exc
    if any(part.casefold() == ".env" for part in path.parts):
        raise RuntimeErrorBase("implicit environment files are not allowed")
    return candidate


def _read_json(root: Path, relative: str) -> dict[str, Any]:
    path = _repo_path(root, relative)
    if not path.is_file():
        raise RuntimeErrorBase(f"missing runtime contract: {relative}")
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeErrorBase("runtime contract cannot be read") from exc
    if not isinstance(value, dict):
        raise RuntimeErrorBase("runtime contract must be a JSON object")
    return value


def _load_contract(root: Path) -> dict[str, Any]:
    contract = _read_json(root, str(CONTRACT_RELATIVE))
    if contract.get("schema_version") != "iteration5-modular-runtime-v1":
        raise RuntimeErrorBase("unsupported modular runtime contract")
    if contract.get("auto_accept_current_values") is not False:
        raise RuntimeErrorBase("runtime contract is not manually reviewed")
    return contract


def _read_env_names(root: Path, relative: str) -> set[str]:
    path = _repo_path(root, relative)
    if not path.is_file():
        raise RuntimeErrorBase(f"missing environment name source: {relative}")
    names: set[str] = set()
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        name = line.split("=", 1)[0].strip()
        if ENV_NAME_RE.fullmatch(name):
            names.add(name)
    return names


def _parse_env_file(path_value: str) -> dict[str, str]:
    path = Path(path_value)
    if not path.is_absolute():
        raise RuntimeErrorBase("env-file must be an explicit absolute path")
    if path.is_symlink() or not path.is_file():
        raise RuntimeErrorBase("env-file must be an explicit regular file")
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeError) as exc:
        raise RuntimeErrorBase("env-file cannot be read") from exc
    for line_number, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        name, separator, value = line.partition("=")
        if not separator or not ENV_NAME_RE.fullmatch(name.strip()):
            raise RuntimeErrorBase(f"invalid env-file entry at line {line_number}")
        name = name.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        values[name] = value
    return values


def _validate_env_names(root: Path, values: dict[str, str]) -> None:
    contract = _load_contract(root)
    sources = contract["source_documents"]
    allowed = _read_env_names(root, sources["backend_env_names"])
    allowed.update(_read_env_names(root, sources["frontend_env_names"]))
    allowed.update(INTERNAL_ENV_NAMES)
    unknown = sorted(set(values).difference(allowed))
    if unknown:
        raise RuntimeErrorBase("env-file contains unknown variable names")


def _safe_child_env(root: Path, values: dict[str, str], *, frontend: bool) -> dict[str, str]:
    _validate_env_names(root, values)
    source_names = set(values)
    source_names.update(_read_env_names(root, ".env.example"))
    source_names.update(_read_env_names(root, "ez_front_dev/.env.example"))
    child = os.environ.copy()
    for name in source_names | INTERNAL_ENV_NAMES:
        child.pop(name, None)
    if frontend:
        child.update(
            {
                name: value
                for name, value in values.items()
                if name.startswith("VUE_APP_") or name.startswith("VITE_")
            }
        )
    else:
        child.update(values)
        child["PYTHON_DOTENV_DISABLED"] = "true"
    return child


def _validate_loopback_url(value: str, *, allow_path: bool = True) -> bool:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password:
        return False
    host = parsed.hostname.casefold() if parsed.hostname else ""
    if host not in {item.casefold().strip("[]") for item in LOOPBACK_HOSTS}:
        return False
    return allow_path or parsed.path in {"", "/"}


def _validate_required_config(root: Path, values: dict[str, str]) -> None:
    if not values.get("DATABASE_URL"):
        raise RuntimeErrorBase("explicit env-file must define DATABASE_URL")
    if not values.get("AGENT_REDIS_URL"):
        raise RuntimeErrorBase("explicit env-file must define AGENT_REDIS_URL")
    for name in ("BACKEND_HOST",):
        if values.get(name) and values[name].casefold() not in {
            host.casefold().strip("[]") for host in LOOPBACK_HOSTS
        }:
            raise RuntimeErrorBase("modular runtime requires a loopback backend host")
    for name, expected in (("BACKEND_PORT", "8130"), ("AGENT_API_PORT", "8131")):
        if values.get(name) and values[name] != expected:
            raise RuntimeErrorBase("modular runtime uses the fixed local service ports")
    for name, value in values.items():
        if SENSITIVE_ENV_RE.search(name) and any(
            marker.casefold() in value.casefold()
            for marker in ("replace_with_", "<", "CHANGE_ME")
        ):
            raise RuntimeErrorBase("required configuration contains a placeholder")
    for name in ("VUE_APP_API_BASE_URL", "VUE_APP_AGENT_API_BASE_URL", "VUE_APP_GRAFANA_BASE_URL"):
        value = values.get(name)
        if value and not _validate_loopback_url(value):
            raise RuntimeErrorBase("frontend service URLs must target loopback")


def _validate_frontend_config(root: Path, values: dict[str, str]) -> None:
    _validate_env_names(root, values)
    for name in ("VUE_APP_API_BASE_URL", "VUE_APP_AGENT_API_BASE_URL", "VUE_APP_GRAFANA_BASE_URL"):
        value = values.get(name)
        if value and not _validate_loopback_url(value):
            raise RuntimeErrorBase("frontend service URLs must target loopback")


def _probe_database(database_url: str) -> dict[str, Any]:
    """Run only SELECT probes; imports database clients after configuration validation."""
    try:
        from sqlalchemy import create_engine, text
    except ImportError as exc:
        raise RuntimeErrorBase("database probe requires the locked runtime environment") from exc
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            rows = connection.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = DATABASE()"
                )
            )
            tables = {str(row[0]) for row in rows}
    finally:
        engine.dispose()
    missing = sorted(EXPECTED_TABLES.difference(tables))
    return {"status": "ok" if not missing else "schema_incomplete", "missing": missing}


def _probe_redis(redis_url: str) -> dict[str, Any]:
    try:
        import redis
    except ImportError as exc:
        raise RuntimeErrorBase("Redis probe requires the locked runtime environment") from exc
    client = redis.Redis.from_url(redis_url)
    try:
        ok = bool(client.ping())
    finally:
        client.close()
    return {"status": "ok" if ok else "unavailable"}


def _external_preflight(root: Path, values: dict[str, str]) -> dict[str, Any]:
    _validate_required_config(root, values)
    database = _probe_database(values["DATABASE_URL"])
    redis = _probe_redis(values["AGENT_REDIS_URL"])
    return {"database": database, "redis": redis}


def _safe_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)


def _emit(payload: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print(_safe_json(payload))
        return
    status = payload.get("status", "unknown")
    print(f"status={status}")
    for name, item in payload.get("modules", {}).items():
        if isinstance(item, dict):
            print(f"{name}: {item.get('status', 'unknown')}")
    for name, item in payload.get("checks", {}).items():
        if isinstance(item, dict):
            print(f"{name}: {item.get('status', 'unknown')}")
    if payload.get("run_id"):
        print(f"run_id={payload['run_id']}")
    if payload.get("error_code"):
        print(f"error_code={payload['error_code']}")


def _state_root(run_id: str) -> Path:
    if not RUN_ID_RE.fullmatch(run_id):
        raise RuntimeErrorBase("run-id is invalid")
    root = Path(tempfile.gettempdir()).resolve() / STATE_ROOT_NAME
    repository = Path(__file__).resolve().parents[1]
    try:
        root.relative_to(repository)
    except ValueError:
        pass
    else:
        raise RuntimeErrorBase("runtime state cannot be inside the repository")
    if root.exists() and root.is_symlink():
        raise RuntimeErrorBase("runtime state root is a symlink")
    run_root = root / run_id
    if run_root.exists() and run_root.is_symlink():
        raise RuntimeErrorBase("runtime state directory is a symlink")
    return run_root


def _write_state(run_root: Path, state: dict[str, Any]) -> None:
    run_root.mkdir(parents=True, exist_ok=True)
    state_path = run_root / "state.json"
    temporary = run_root / "state.json.tmp"
    temporary.write_text(_safe_json(state) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(state_path)


def _read_state(run_id: str) -> tuple[Path, dict[str, Any]]:
    run_root = _state_root(run_id)
    state_path = run_root / "state.json"
    if not state_path.is_file():
        raise RuntimeErrorBase("run-id state was not found")
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeErrorBase("run-id state is invalid") from exc
    if not isinstance(state, dict) or state.get("run_id") != run_id:
        raise RuntimeErrorBase("run-id state identity is invalid")
    return run_root, state


def _fingerprint(argv: list[str]) -> str:
    return hashlib.sha256(
        json.dumps(argv, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _windows_identity(pid: int) -> dict[str, str] | None:
    command = (
        "$p=Get-CimInstance Win32_Process -Filter \"ProcessId = "
        + str(pid)
        + "\";"
        "$g=Get-Process -Id "
        + str(pid)
        + """ -ErrorAction SilentlyContinue;"""
        "if ($null -eq $p -or $null -eq $g) { exit 3 };"
        "$start=$g.StartTime.ToUniversalTime().ToString('o');"
        "Write-Output ($start + [char]9 + $p.CommandLine)"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
            shell=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    line = result.stdout.strip()
    if "\t" not in line:
        return None
    start, command_line = line.split("\t", 1)
    return {"creation_time": start, "command_line": command_line}


def _posix_identity(pid: int) -> dict[str, str] | None:
    proc = Path("/proc") / str(pid)
    try:
        command_line = (proc / "cmdline").read_bytes().replace(b"\x00", b" ").decode(
            "utf-8", "replace"
        )
        stat = (proc / "stat").read_text(encoding="ascii")
    except (OSError, UnicodeError):
        return None
    fields = stat.split()
    if len(fields) <= 21:
        return None
    return {"creation_time": fields[21], "command_line": command_line.strip()}


def _process_identity(pid: int) -> dict[str, str] | None:
    if os.name == "nt":
        return _windows_identity(pid)
    return _posix_identity(pid)


def _identity_matches(record: dict[str, Any]) -> bool:
    pid = record.get("pid")
    if not isinstance(pid, int) or pid <= 0:
        return False
    observed = _process_identity(pid)
    if observed is None:
        return False
    expected_command_hash = record.get("command_fingerprint")
    expected_creation = record.get("creation_time")
    if not isinstance(expected_command_hash, str) or not isinstance(expected_creation, str):
        return False
    return (
        observed["creation_time"] == expected_creation
        and _fingerprint(observed["command_line"].split()) == expected_command_hash
    )


def _wait_for_exit(pid: int, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _process_identity(pid) is None:
            return True
        time.sleep(0.1)
    return _process_identity(pid) is None


def _terminate_record(record: dict[str, Any], timeout: float = 5.0) -> bool:
    if not _identity_matches(record):
        return False
    pid = int(record["pid"])
    if os.name == "nt":
        # npm.cmd can exit while its node child keeps serving the frontend.
        # The identity check above proves ownership of the recorded root;
        # terminate that exact process tree so a managed run cannot leak a
        # child listener into the next run.  No PID discovery or broad kill is
        # allowed here.
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T"],
            check=False,
            capture_output=True,
            text=True,
            shell=False,
        )
        if _wait_for_exit(pid, timeout):
            return True
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            check=False,
            capture_output=True,
            text=True,
            shell=False,
        )
        return _wait_for_exit(pid, timeout)
    try:
        os.kill(pid, signal.SIGTERM)
    except (OSError, ProcessLookupError):
        return _process_identity(pid) is None
    if _wait_for_exit(pid, timeout):
        return True
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass
    return _wait_for_exit(pid, timeout)


def _module_command(root: Path, module: str, contract: dict[str, Any]) -> tuple[list[str], Path]:
    item = contract["modules"][module]
    command = list(item["command"])
    if command[0] == "python":
        command[0] = sys.executable
    elif command[0] == "npm" and os.name == "nt":
        command[0] = "npm.cmd"
    cwd = _repo_path(root, item["working_dir"])
    if not cwd.is_dir():
        raise RuntimeErrorBase(f"module working directory is missing: {module}")
    return command, cwd


def _http_probe(host: str, port: int, path: str, timeout: float) -> dict[str, Any]:
    url = f"http://{host}:{port}{path}"
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(16_384)
            code = int(response.status)
    except urllib.error.HTTPError as exc:
        body = exc.read(16_384)
        code = int(exc.code)
    except (OSError, urllib.error.URLError):
        return {"status": "unavailable", "http_status": None}
    result: dict[str, Any] = {
        "status": "ok" if 200 <= code < 300 else "not_ready",
        "http_status": code,
    }
    if path == "/ready":
        try:
            payload = json.loads(body.decode("utf-8"))
            if isinstance(payload, dict) and payload.get("schema_version") == READINESS_SCHEMA_VERSION:
                result["readiness_status"] = payload.get("status")
                result["checks"] = payload.get("checks", {})
        except (UnicodeError, json.JSONDecodeError):
            result["status"] = "invalid_response"
    return result


def _wait_http(host: str, port: int, path: str, timeout: float, *, endpoint_only: bool = False) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    latest: dict[str, Any] = {"status": "unavailable", "http_status": None}
    while time.monotonic() < deadline:
        latest = _http_probe(host, port, path, min(2.0, max(0.1, deadline - time.monotonic())))
        if latest.get("http_status") in ({200, 503} if endpoint_only else {200}):
            return latest
        time.sleep(0.2)
    return latest


def _ports_available(contract: dict[str, Any]) -> bool:
    for name in ("legacy-api", "agent-api", "frontend"):
        item = contract["modules"][name]
        address = (item["host"], int(item["port"]))
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        try:
            connected = sock.connect_ex(address) == 0
        except OSError:
            connected = True
        finally:
            sock.close()
        if connected:
            return False
    return True


def _probe_run_readiness(contract: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    modules: dict[str, Any] = {}
    for name in ("legacy-api", "agent-api", "frontend"):
        item = contract["modules"][name]
        readiness = item["readiness"]
        modules[name] = _http_probe(
            item["host"], item["port"], readiness["path"], timeout=2.0
        )
    worker = state.get("modules", {}).get("worker", {})
    modules["worker"] = {
        "status": "managed",
        "heartbeat_via": "agent-api/ready",
        "process": "running" if _identity_matches(worker) else "not_running",
    }
    ready = all(
        modules[name].get("status") == "ok"
        for name in ("legacy-api", "agent-api", "frontend")
    ) and modules["worker"]["process"] == "running"
    return {"status": "ready" if ready else "not_ready", "modules": modules}


def _preflight(root: Path, env_file: str, frontend_env_file: str | None) -> dict[str, Any]:
    values = _parse_env_file(env_file)
    _validate_env_names(root, values)
    _validate_required_config(root, values)
    if frontend_env_file:
        frontend_values = _parse_env_file(frontend_env_file)
        _validate_frontend_config(root, frontend_values)
    checks = _external_preflight(root, values)
    ok = all(item.get("status") == "ok" for item in checks.values())
    return {"status": "ready" if ok else "not_ready", "checks": checks}


def _start(root: Path, env_file: str, frontend_env_file: str | None, timeout: float) -> dict[str, Any]:
    contract = _load_contract(root)
    values = _parse_env_file(env_file)
    _validate_env_names(root, values)
    _validate_required_config(root, values)
    frontend_values = values.copy()
    if frontend_env_file:
        frontend_values.update(_parse_env_file(frontend_env_file))
        _validate_frontend_config(root, frontend_values)
    external = _external_preflight(root, values)
    if any(item.get("status") != "ok" for item in external.values()):
        return {"status": "not_ready", "checks": external, "error_code": "dependencies_not_ready"}
    if not _ports_available(contract):
        return {"status": "not_ready", "error_code": "port_in_use"}

    run_id = uuid.uuid4().hex
    run_root = _state_root(run_id)
    logs_root = run_root / "logs"
    logs_root.mkdir(parents=True, exist_ok=False)
    state: dict[str, Any] = {
        "schema_version": "iteration5-modular-runtime-state-v1",
        "run_id": run_id,
        "repo_root": str(root),
        "created_at": datetime.now(UTC).isoformat(),
        "status": "starting",
        "modules": {},
    }
    _write_state(run_root, state)
    started: list[str] = []

    def launch(module: str) -> None:
        command, cwd = _module_command(root, module, contract)
        log_path = logs_root / f"{module}.log"
        with log_path.open("ab") as log_file:
            creation_env = _safe_child_env(
                root,
                frontend_values if module == "frontend" else values,
                frontend=module == "frontend",
            )
            if module == "frontend":
                env_dir = run_root / "frontend-env"
                env_dir.mkdir(parents=True, exist_ok=True)
                creation_env["EZLLMTEST_VITE_ENV_DIR"] = str(env_dir)
            process = subprocess.Popen(
                command,
                cwd=cwd,
                env=creation_env,
                stdin=subprocess.DEVNULL,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                shell=False,
                creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0),
                start_new_session=(os.name != "nt"),
            )
        deadline = time.monotonic() + 5.0
        identity = None
        while time.monotonic() < deadline:
            identity = _process_identity(process.pid)
            if identity is not None:
                break
            time.sleep(0.1)
        if identity is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            raise RuntimeErrorBase(f"cannot prove process ownership: {module}")
        state["modules"][module] = {
            "pid": process.pid,
            "creation_time": identity["creation_time"],
            "command_fingerprint": _fingerprint(identity["command_line"].split()),
            "expected_port": contract["modules"][module].get("port"),
            "status": "running",
        }
        started.append(module)
        _write_state(run_root, state)

    try:
        launch("legacy-api")
        item = contract["modules"]["legacy-api"]
        if _wait_http(item["host"], item["port"], "/ready", timeout, endpoint_only=False).get("status") != "ok":
            raise RuntimeErrorBase("legacy API did not become ready")

        launch("agent-api")
        item = contract["modules"]["agent-api"]
        if _wait_http(item["host"], item["port"], "/ready", timeout, endpoint_only=True).get("http_status") not in {200, 503}:
            raise RuntimeErrorBase("Agent API did not start")

        launch("worker")
        if _wait_http(item["host"], item["port"], "/ready", timeout, endpoint_only=False).get("status") != "ok":
            raise RuntimeErrorBase("Agent worker did not become ready")

        launch("frontend")
        item = contract["modules"]["frontend"]
        if _wait_http(item["host"], item["port"], "/", timeout, endpoint_only=False).get("status") != "ok":
            raise RuntimeErrorBase("frontend did not become ready")
        state["status"] = "ready"
        _write_state(run_root, state)
        return {"status": "ready", "run_id": run_id, "modules": state["modules"]}
    except (OSError, RuntimeErrorBase, subprocess.SubprocessError) as exc:
        for module in reversed(started):
            _terminate_record(state["modules"].get(module, {}))
        state["status"] = "failed"
        state["error_code"] = "startup_failed"
        _write_state(run_root, state)
        return {"status": "failed", "run_id": run_id, "error_code": "startup_failed"}


def _status(run_id: str) -> dict[str, Any]:
    _, state = _read_state(run_id)
    modules: dict[str, Any] = {}
    for name, record in state.get("modules", {}).items():
        modules[name] = {
            "status": "running" if _identity_matches(record) else "not_running",
            "port": record.get("expected_port"),
        }
    ok = bool(modules) and all(item["status"] == "running" for item in modules.values())
    return {"status": "ready" if ok else "not_ready", "run_id": run_id, "modules": modules}


def _ready(run_id: str) -> dict[str, Any]:
    _, state = _read_state(run_id)
    contract = _load_contract(Path(state["repo_root"]))
    result = _probe_run_readiness(contract, state)
    result["run_id"] = run_id
    return result


def _stop(run_id: str) -> dict[str, Any]:
    run_root, state = _read_state(run_id)
    modules: dict[str, Any] = {}
    unsafe = False
    for name in ("frontend", "worker", "agent-api", "legacy-api"):
        record = state.get("modules", {}).get(name)
        if not isinstance(record, dict):
            continue
        if _terminate_record(record):
            modules[name] = {"status": "stopped"}
        else:
            modules[name] = {"status": "ownership_unproven"}
            unsafe = True
    if not unsafe:
        state["status"] = "stopped"
        _write_state(run_root, state)
    return {
        "status": "failed" if unsafe else "stopped",
        "run_id": run_id,
        "modules": modules,
        "error_code": "ownership_unproven" if unsafe else None,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("preflight", "start"):
        child = subparsers.add_parser(name)
        child.add_argument("--repo-root", dest="sub_repo_root")
        child.add_argument("--format", dest="sub_format", choices=("text", "json"))
        child.add_argument("--env-file", required=True)
        child.add_argument("--frontend-env-file")
        child.add_argument("--timeout", type=float, default=30.0)
    for name in ("status", "ready", "stop"):
        child = subparsers.add_parser(name)
        child.add_argument("--repo-root", dest="sub_repo_root")
        child.add_argument("--format", dest="sub_format", choices=("text", "json"))
        child.add_argument("--run-id", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        root = _repo_root(getattr(args, "sub_repo_root", None) or args.repo_root)
        output_format = getattr(args, "sub_format", None) or args.format
        if args.command == "preflight":
            payload = _preflight(root, args.env_file, args.frontend_env_file)
        elif args.command == "start":
            payload = _start(root, args.env_file, args.frontend_env_file, args.timeout)
        elif args.command == "status":
            payload = _status(args.run_id)
        elif args.command == "ready":
            payload = _ready(args.run_id)
        else:
            payload = _stop(args.run_id)
        _emit(payload, output_format)
        return 0 if payload.get("status") in {"ready", "stopped"} else 1
    except (RuntimeErrorBase, OSError, ValueError) as exc:
        payload = {"status": "error", "error_code": "invalid_runtime_request"}
        _emit(payload, output_format if "output_format" in locals() else "text")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
