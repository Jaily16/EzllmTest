"""Run and inspect the explicit, loopback-only modular EzLLM stack."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import secrets
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit


def _load_configuration_schema():
    path = Path(__file__).resolve().parents[1] / "backend/infrastructure/runtime_config.py"
    spec = importlib.util.spec_from_file_location("_ezllm_runtime_config", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


configuration = _load_configuration_schema()
CONTRACT_RELATIVE = Path("infrastructure/runtime/modular-runtime-contract.json")
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
    "EZLLMTEST_OBSERVABILITY_INGEST_URL",
    "EZLLMTEST_OBSERVABILITY_INGEST_TOKEN",
    "EZLLMTEST_LEGACY_READY_URL",
    "EZLLMTEST_AGENT_READY_URL",
    "EZLLMTEST_FRONTEND_URL",
}
MODEL_ENV_NAMES = frozenset(
    f"{provider}_{suffix}"
    for provider in ("ZHIPU", "DASHSCOPE", "DEEPSEEK", "MOONSHOT")
    for suffix in ("API_KEY", "BASE_URL", "CHAT_MODEL", "TIMEOUT_SECONDS")
) | {"ZHIPU_EMBEDDING_MODEL"}
MODEL_SECRET_FILE_NAMES = frozenset(
    f"{provider}_API_KEY_FILE"
    for provider in ("ZHIPU", "DASHSCOPE", "DEEPSEEK", "MOONSHOT")
)


class RuntimeErrorBase(configuration.RuntimeConfigurationError):
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
    if contract.get("schema_version") != "iteration6-modular-runtime-v2":
        raise RuntimeErrorBase("unsupported modular runtime contract")
    if contract.get("auto_accept_current_values") is not False:
        raise RuntimeErrorBase("runtime contract is not manually reviewed")
    return contract


def _parse_env_file(path_value: str) -> dict[str, str]:
    return configuration.read_env_file(path_value, configuration.LEGACY_FIELDS)


def _parse_model_env_lines(lines: Iterable[str]) -> dict[str, str]:
    """Retain only explicit model fields, without evaluating unrelated config."""
    selected: dict[str, str] = {}
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        name = line.partition("=")[0].strip()
        if name in MODEL_SECRET_FILE_NAMES:
            raise RuntimeErrorBase("model env-file cannot reference another secret file")
        if name not in MODEL_ENV_NAMES:
            continue
        _, separator, value = line.partition("=")
        if not separator or name in selected:
            raise RuntimeErrorBase("model env-file contains invalid or duplicate selected fields")
        value = value.strip()
        if value.startswith(("'", '"')):
            quote = value[0]
            closing = value.find(quote, 1)
            if closing < 1 or (value[closing + 1:].strip() and not value[closing + 1:].lstrip().startswith("#")):
                raise RuntimeErrorBase("model env-file contains an invalid quoted value")
            value = value[1:closing]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        if any(character in value for character in ("\x00", "\r", "\n")):
            raise RuntimeErrorBase("model env-file contains an invalid selected value")
        selected[name] = value
    return selected


def _read_model_env_file(path_value: str) -> dict[str, str]:
    path = Path(path_value)
    if not path.is_absolute():
        raise RuntimeErrorBase("model env-file must be an explicit absolute path")
    try:
        for candidate in (path, *path.parents):
            attributes = getattr(candidate.lstat(), "st_file_attributes", 0)
            if candidate.is_symlink() or attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
                raise RuntimeErrorBase("model env-file cannot use a reparse path")
        if not path.is_file():
            raise RuntimeErrorBase("model env-file must be an explicit regular file")
        with path.open("r", encoding="utf-8-sig") as stream:
            return _parse_model_env_lines(stream)
    except (OSError, UnicodeError):
        raise RuntimeErrorBase("model env-file cannot be read") from None


def _merge_model_values(primary: dict[str, str], model_values: dict[str, str]) -> dict[str, str]:
    if set(model_values).difference(MODEL_ENV_NAMES):
        raise RuntimeErrorBase("model source contains non-model fields")
    merged = primary.copy()
    for name, value in model_values.items():
        if name in merged and merged[name] != value:
            raise RuntimeErrorBase("model settings conflict between explicit sources")
        merged[name] = value
    return merged


def _load_runtime_values(root: Path, env_file: str, model_env_file: str | None = None, moonshot_model: str | None = None) -> dict[str, str]:
    values = _parse_env_file(env_file)
    _validate_env_names(root, values)
    if model_env_file is not None:
        values = _merge_model_values(values, _read_model_env_file(model_env_file))
        _validate_env_names(root, values)
    if moonshot_model is not None:
        if moonshot_model != "kimi-k3":
            raise RuntimeErrorBase("unsupported explicit Moonshot model override")
        # Explicit non-secret selection; never edit either source or silently
        # migrate a configured model when the operator omits this argument.
        values["MOONSHOT_CHAT_MODEL"] = moonshot_model
    return values


def _validate_env_names(root: Path, values: dict[str, str]) -> None:
    configuration.validate_fields(values, configuration.LEGACY_FIELDS)


def _safe_child_env(
    root: Path, values: dict[str, str], *, module: str
) -> dict[str, str]:
    del root
    return configuration.isolated_environment(values, role=module)


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


def _tcp_port(value: str | int) -> int:
    if not re.fullmatch(r"[0-9]{1,5}", str(value)) or not 1 <= int(value) <= 65_535:
        raise RuntimeErrorBase("service port must be a decimal TCP port")
    return int(value)


def _runtime_contract(root: Path, values: dict[str, str], frontend_port: int) -> dict[str, Any]:
    contract = _load_contract(root)
    contract["modules"]["legacy-api"]["host"] = values.get("BACKEND_HOST", "127.0.0.1")
    contract["modules"]["observability-api"]["host"] = values.get(
        "OBSERVABILITY_HOST", "127.0.0.1"
    )
    ports = {
        "observability-api": _tcp_port(values.get("OBSERVABILITY_PORT", "8140")),
        "legacy-api": _tcp_port(values.get("BACKEND_PORT", "8130")),
        "agent-api": _tcp_port(values.get("AGENT_API_PORT", "8131")),
        "frontend": _tcp_port(frontend_port),
    }
    if len(set(ports.values())) != len(ports):
        raise RuntimeErrorBase("managed service ports must be distinct")
    for name, port in ports.items():
        item = contract["modules"][name]
        item["port"] = port
        command = item["command"]
        if "--port" in command:
            command[command.index("--port") + 1] = str(port)
    return contract


def _validate_required_config(root: Path, values: dict[str, str]) -> None:
    if not values.get("DATABASE_URL") and not values.get("DATABASE_URL_FILE"):
        raise RuntimeErrorBase("explicit env-file must define DATABASE_URL")
    if not values.get("AGENT_REDIS_URL"):
        raise RuntimeErrorBase("explicit env-file must define AGENT_REDIS_URL")
    if not values.get("OBSERVABILITY_DATABASE_PATH"):
        raise RuntimeErrorBase(
            "explicit observability configuration must define its database path"
        )
    configuration.explicit_observability_database_path(
        values["OBSERVABILITY_DATABASE_PATH"],
        observability_directory=root / "observability",
    )
    for name in ("BACKEND_HOST", "OBSERVABILITY_HOST"):
        if values.get(name) and values[name].casefold() not in {
            host.casefold().strip("[]") for host in LOOPBACK_HOSTS
        }:
            raise RuntimeErrorBase("modular runtime requires a loopback backend host")
    for name, default in (
        ("BACKEND_PORT", "8130"),
        ("AGENT_API_PORT", "8131"),
        ("OBSERVABILITY_PORT", "8140"),
    ):
        _tcp_port(values.get(name, default))
    for name, value in values.items():
        if SENSITIVE_ENV_RE.search(name) and any(
            marker.casefold() in value.casefold()
            for marker in ("replace_with_", "<", "CHANGE_ME")
        ):
            raise RuntimeErrorBase("required configuration contains a placeholder")
    for name in (
        "VUE_APP_API_BASE_URL",
        "VUE_APP_AGENT_API_BASE_URL",
        "VUE_APP_OBSERVABILITY_API_BASE_URL",
    ):
        value = values.get(name)
        if value and not _validate_loopback_url(value):
            raise RuntimeErrorBase("frontend service URLs must target loopback")


def _validate_frontend_config(root: Path, values: dict[str, str]) -> None:
    _validate_env_names(root, values)
    for name in (
        "VUE_APP_API_BASE_URL",
        "VUE_APP_AGENT_API_BASE_URL",
        "VUE_APP_OBSERVABILITY_API_BASE_URL",
    ):
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
    checks = {}
    for name, probe, key in (
        ("database", _probe_database, "DATABASE_URL"),
        ("redis", _probe_redis, "AGENT_REDIS_URL"),
    ):
        try:
            value = values.get(key, "")
            if key == "DATABASE_URL":
                value = configuration.resolve_secret_reference(key, values.get(key), values.get("DATABASE_URL_FILE"))
                configuration.validate_fields({key: value}, configuration.BACKEND_FIELDS)
                if not value:
                    raise RuntimeErrorBase("explicit database configuration is empty")
            checks[name] = probe(value)
        except Exception:
            # Driver exceptions can contain connection values; never render them.
            checks[name] = {"status": "unavailable"}
    return checks


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
    powershell = shutil.which("pwsh") or shutil.which("powershell")
    if powershell is None:
        return None
    try:
        result = subprocess.run(
            [powershell, "-NoProfile", "-NonInteractive", "-Command", command],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
            shell=False,
            creationflags=subprocess.CREATE_NO_WINDOW,
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
    if fields[2] == "Z":
        # A terminated child remains visible as a zombie until its parent
        # reaps it; treat that state as exited for safe ownership polling.
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
    elif command[0] == "node":
        node = shutil.which("node")
        entry = _repo_path(root, item["working_dir"] + "/" + command[1])
        if node is None or not entry.is_file():
            raise RuntimeErrorBase("frontend requires installed Node and Vite dependencies")
        command[0], command[1] = node, str(entry)
    elif command[0] == "npm" and os.name == "nt":
        command[0] = "npm.cmd"
    cwd = _repo_path(root, item["working_dir"])
    if not cwd.is_dir():
        raise RuntimeErrorBase(f"module working directory is missing: {module}")
    return command, cwd


def _http_probe(host: str, port: int, path: str, timeout: float) -> dict[str, Any]:
    url_host = f"[{host}]" if ":" in host and not host.startswith("[") else host
    url = f"http://{url_host}:{port}{path}"
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
    for name in ("observability-api", "legacy-api", "agent-api", "frontend"):
        item = contract["modules"][name]
        address = (item["host"], int(item["port"]))
        family = socket.AF_INET6 if ":" in item["host"] else socket.AF_INET
        sock = socket.socket(family, socket.SOCK_STREAM)
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
    http_modules = tuple(
        name
        for name in ("observability-api", "legacy-api", "agent-api", "frontend")
        if name in state.get("modules", {})
    )
    for name in http_modules:
        item = contract["modules"][name]
        readiness = item["readiness"]
        modules[name] = _http_probe(
            item["host"], item["port"], readiness["path"], timeout=2.0
        )
    if "worker" in state.get("modules", {}):
        worker = state["modules"]["worker"]
        modules["worker"] = {
            "status": "managed",
            "heartbeat_via": "agent-api/ready",
            "process": "running" if _identity_matches(worker) else "not_running",
        }
    ready = bool(http_modules) and all(
        modules[name].get("status") == "ok" for name in http_modules
    ) and (
        "worker" not in modules or modules["worker"]["process"] == "running"
    )
    return {"status": "ready" if ready else "not_ready", "modules": modules}


def _prepare_configuration(
    root: Path, env_file: str | None, frontend_env_file: str | None,
    frontend_port: int | None = None, model_env_file: str | None = None,
    moonshot_model: str | None = None, *, backend_env_file: str | None = None,
    observability_env_file: str | None = None,
) -> tuple[dict[str, str], dict[str, str], int, str]:
    new_mode = backend_env_file is not None or observability_env_file is not None
    if new_mode:
        if any(value is not None for value in (env_file, model_env_file, moonshot_model, frontend_port)):
            raise RuntimeErrorBase("new and legacy configuration arguments cannot be mixed")
        if not all((backend_env_file, frontend_env_file, observability_env_file)):
            raise RuntimeErrorBase("three explicit configuration files are required")
        loaded = configuration.load_three_files(backend_env_file, frontend_env_file, observability_env_file)
        values, frontend_values = loaded.backend_environment(), loaded.frontend
        selected_port, mode = loaded.frontend_port, "three-file"
    else:
        if env_file is None:
            raise RuntimeErrorBase("explicit configuration mode is required")
        values = _load_runtime_values(root, env_file, model_env_file, moonshot_model)
        selected_port = _tcp_port(8080 if frontend_port is None else frontend_port)
        # Legacy defaults are explicit here, independent of new-mode defaults.
        values.setdefault("BACKEND_PORT", "8130")
        values.setdefault("AGENT_API_PORT", "8131")
        values.setdefault("BACKEND_HOST", "127.0.0.1")
        values.setdefault("CORS_ORIGINS", f"http://127.0.0.1:{selected_port}")
        values.setdefault("AGENT_TELEMETRY_ENABLED", "false")
        values.setdefault("AGENT_TELEMETRY_SERVICE_NAME", "ezllm-agent")
        values.setdefault("AGENT_OTEL_EXPORT_TIMEOUT_MS", "2000")
        values.setdefault("AGENT_OTEL_METRIC_INTERVAL_MS", "30000")
        values.setdefault("OBSERVABILITY_HOST", "127.0.0.1")
        values.setdefault("OBSERVABILITY_PORT", "8140")
        values.setdefault(
            "OBSERVABILITY_DATABASE_PATH",
            str(root / "observability" / "data" / "ezllmtest-observability.sqlite3"),
        )
        values.setdefault("OBSERVABILITY_RETENTION_DAYS", "7")
        values.setdefault("OBSERVABILITY_MAX_ROWS", "100000")
        values.setdefault(
            "OBSERVABILITY_CORS_ORIGINS",
            f"http://127.0.0.1:{selected_port},http://localhost:{selected_port}",
        )
        frontend_values = {name: value for name, value in values.items() if name in configuration.FRONTEND_FIELDS}
        if frontend_env_file:
            frontend_values.update(configuration.read_env_file(frontend_env_file, configuration.FRONTEND_FIELDS))
        if "FRONTEND_PORT" in frontend_values and int(frontend_values["FRONTEND_PORT"]) != selected_port:
            raise RuntimeErrorBase("conflicting frontend port sources")
        frontend_values.setdefault("VUE_APP_API_BASE_URL", f"http://127.0.0.1:{values['BACKEND_PORT']}")
        frontend_values.setdefault("VUE_APP_AGENT_API_BASE_URL", f"http://127.0.0.1:{values['AGENT_API_PORT']}")
        frontend_values.setdefault(
            "VUE_APP_OBSERVABILITY_API_BASE_URL",
            f"http://127.0.0.1:{values['OBSERVABILITY_PORT']}",
        )
        mode = "legacy-explicit-deprecated"
    _validate_env_names(root, values)
    _validate_required_config(root, values)
    _validate_frontend_config(root, frontend_values)
    _runtime_contract(root, values, selected_port)
    return values, frontend_values, selected_port, mode


def _config_check(root: Path, **arguments) -> dict[str, Any]:
    _, _, _, mode = _prepare_configuration(root, **arguments)
    return {"status": "ready", "configuration_mode": mode, "external_probes": False}


def _preflight(root: Path, env_file: str | None, frontend_env_file: str | None, frontend_port: int | None = None, model_env_file: str | None = None, moonshot_model: str | None = None, *, backend_env_file: str | None = None, observability_env_file: str | None = None) -> dict[str, Any]:
    values, _, _, mode = _prepare_configuration(root, env_file, frontend_env_file, frontend_port, model_env_file, moonshot_model, backend_env_file=backend_env_file, observability_env_file=observability_env_file)
    checks = _external_preflight(root, values)
    ok = all(item.get("status") == "ok" for item in checks.values())
    return {"status": "ready" if ok else "not_ready", "checks": checks, "configuration_mode": mode}


def _start(root: Path, env_file: str | None, frontend_env_file: str | None, timeout: float, frontend_port: int | None = None, model_env_file: str | None = None, moonshot_model: str | None = None, *, backend_env_file: str | None = None, observability_env_file: str | None = None) -> dict[str, Any]:
    values, frontend_values, selected_port, mode = _prepare_configuration(root, env_file, frontend_env_file, frontend_port, model_env_file, moonshot_model, backend_env_file=backend_env_file, observability_env_file=observability_env_file)
    contract = _runtime_contract(root, values, selected_port)
    external = _external_preflight(root, values)
    if any(item.get("status") != "ok" for item in external.values()):
        return {"status": "not_ready", "checks": external, "error_code": "dependencies_not_ready"}
    if not _ports_available(contract):
        return {"status": "not_ready", "error_code": "port_in_use"}

    run_id = uuid.uuid4().hex
    ingest_token = secrets.token_urlsafe(32)
    run_root = _state_root(run_id)
    logs_root = run_root / "logs"
    logs_root.mkdir(parents=True, exist_ok=False)
    state: dict[str, Any] = {
        "schema_version": "iteration6-modular-runtime-state-v2",
        "run_id": run_id,
        "repo_root": str(root),
        "created_at": datetime.now(UTC).isoformat(),
        "configuration_mode": mode,
        "explicit_model_source_used": model_env_file is not None,
        "explicit_moonshot_model": moonshot_model,
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
                module=module,
            )
            observability = contract["modules"]["observability-api"]
            ingest_url = (
                f"http://{observability['host']}:{observability['port']}"
            )
            if module in {"observability-api", "agent-api", "worker"}:
                creation_env["EZLLMTEST_OBSERVABILITY_INGEST_URL"] = ingest_url
                creation_env["EZLLMTEST_OBSERVABILITY_INGEST_TOKEN"] = ingest_token
            if module == "observability-api":
                legacy = contract["modules"]["legacy-api"]
                agent = contract["modules"]["agent-api"]
                frontend = contract["modules"]["frontend"]
                creation_env["EZLLMTEST_LEGACY_READY_URL"] = (
                    f"http://{legacy['host']}:{legacy['port']}/ready"
                )
                creation_env["EZLLMTEST_AGENT_READY_URL"] = (
                    f"http://{agent['host']}:{agent['port']}/ready"
                )
                creation_env["EZLLMTEST_FRONTEND_URL"] = (
                    f"http://{frontend['host']}:{frontend['port']}/"
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
                creationflags=((subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW) if os.name == "nt" else 0),
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
            "expected_host": contract["modules"][module].get("host"),
            "status": "running",
        }
        started.append(module)
        _write_state(run_root, state)

    try:
        launch("observability-api")
        item = contract["modules"]["observability-api"]
        if _wait_http(item["host"], item["port"], "/ready", timeout).get("status") != "ok":
            raise RuntimeErrorBase("observability API did not become ready")

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
    except (OSError, configuration.RuntimeConfigurationError, subprocess.SubprocessError) as exc:
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
    for name in ("observability-api", "legacy-api", "agent-api", "frontend"):
        record = state.get("modules", {}).get(name, {})
        if not record:
            continue
        if record.get("expected_port") is not None:
            contract["modules"][name]["port"] = _tcp_port(record["expected_port"])
        if record.get("expected_host") in {"127.0.0.1", "localhost", "::1"}:
            contract["modules"][name]["host"] = record["expected_host"]
    result = _probe_run_readiness(contract, state)
    result["run_id"] = run_id
    return result


def _stop(run_id: str) -> dict[str, Any]:
    run_root, state = _read_state(run_id)
    modules: dict[str, Any] = {}
    unsafe = False
    for name in (
        "frontend",
        "worker",
        "agent-api",
        "legacy-api",
        "observability-api",
    ):
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
    for name in ("config-check", "preflight", "start"):
        child = subparsers.add_parser(name)
        child.add_argument("--repo-root", dest="sub_repo_root")
        child.add_argument("--format", dest="sub_format", choices=("text", "json"))
        child.add_argument("--env-file", help="Deprecated explicit legacy configuration; never combined with the three-file mode")
        child.add_argument("--backend-env-file")
        child.add_argument("--observability-env-file")
        child.add_argument("--model-env-file", help="Explicit model-only env source; never overrides infrastructure fields")
        child.add_argument("--moonshot-model", choices=("kimi-k3",), help="Explicit model-only override after env sources; does not edit them")
        child.add_argument("--frontend-env-file")
        child.add_argument("--frontend-port", type=int, help="Legacy mode only; three-file mode uses FRONTEND_PORT")
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
        if args.command in {"config-check", "preflight", "start"}:
            arguments = {
                "env_file": args.env_file, "frontend_env_file": args.frontend_env_file,
                "frontend_port": args.frontend_port, "model_env_file": args.model_env_file,
                "moonshot_model": args.moonshot_model, "backend_env_file": args.backend_env_file,
                "observability_env_file": args.observability_env_file,
            }
            if args.command == "config-check":
                payload = _config_check(root, **arguments)
            elif args.command == "preflight":
                payload = _preflight(root, **arguments)
            else:
                payload = _start(root, timeout=args.timeout, **arguments)
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
        if isinstance(exc, configuration.RuntimeConfigurationError):
            payload["detail"] = str(exc)
        _emit(payload, output_format if "output_format" in locals() else "text")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
