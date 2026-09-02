"""Run the Aspect 8 deterministic acceptance in task-owned topologies.

This runner is deliberately an orchestration harness, not a production
configuration switch.  It creates only synthetic environment files and
disposable Compose projects outside the repository, uses argv-based
subprocesses, and emits redacted evidence.  The modular runner remains the
owner of only the four application processes; this harness owns the separate
disposable dependency project it creates for the modular probe.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE = Path("ops/iteration5-dual-mode-acceptance-contract.json")
ACCEPTANCE_MODULE = "app.agentAcceptance"
ACCEPTANCE_DATASET = "iteration4-agent-acceptance-v1"
ACCEPTANCE_CASE_IDS = (
    "journey-project-lifecycle",
    "journey-plan-approval",
    "journey-exact-cache",
    "journey-session-only",
    "journey-persisted",
    "journey-regenerate",
    "journey-rag-citations",
    "reliability-stale",
    "reliability-cancel",
    "reliability-persisted-crash",
    "reliability-session-unknown",
    "reliability-failure-rollback",
    "reliability-replay",
    "protocol-api-isolation",
    "protocol-mcp-boundary",
    "protocol-approval-tamper",
    "protocol-serialization",
    "protocol-telemetry-redaction",
)
PORTS = {
    "frontend": 8080,
    "legacy-api": 8130,
    "agent-api": 8131,
    "prometheus": 9090,
    "grafana": 3000,
    "modular-mysql": 23306,
    "modular-redis": 26379,
}
IMAGE_RE = re.compile(r"^[a-z0-9][a-z0-9._/-]*:[a-z0-9][a-z0-9._-]*$")
PROJECT_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{2,62}$")
SENSITIVE_NAMES = {
    "DATABASE_URL",
    "AGENT_REDIS_URL",
    "ZHIPU_API_KEY",
    "DASHSCOPE_API_KEY",
    "DEEPSEEK_API_KEY",
    "MOONSHOT_API_KEY",
    "LANGCHAIN_API_KEY",
    "MYSQL_ROOT_PASSWORD",
    "MYSQL_PASSWORD",
    "GRAFANA_ADMIN_PASSWORD",
}
ZERO_METRIC_KEYS = (
    "approval_bypass_count",
    "duplicate_side_effect_count",
    "project_isolation_violation_count",
    "budget_overrun_count",
    "unsafe_capability_execution_count",
    "sensitive_data_leak_count",
    "session_mysql_write_count",
    "warm_cache_model_calls",
    "warm_cache_embedding_calls",
)


class AcceptanceHarnessError(ValueError):
    """Raised for an invalid harness request before any external action."""


def _repo_root(value: str | Path | None) -> Path:
    root = Path(value) if value is not None else REPO_ROOT
    if not root.is_absolute():
        raise AcceptanceHarnessError("repo-root must be absolute")
    resolved = root.resolve()
    if not resolved.is_dir():
        raise AcceptanceHarnessError("repo-root is not a directory")
    return resolved


def _external_report_dir(value: str | Path, root: Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise AcceptanceHarnessError("report-dir must be absolute")
    resolved = path.resolve(strict=False)
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        pass
    else:
        raise AcceptanceHarnessError("report-dir must be outside the repository")
    if resolved.exists() and resolved.is_symlink():
        raise AcceptanceHarnessError("report-dir must not be a symlink")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _read_contract(root: Path) -> dict[str, Any]:
    path = root / CONTRACT_RELATIVE
    if not path.is_file() or path.is_symlink():
        raise AcceptanceHarnessError("Aspect 8 contract is unavailable")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AcceptanceHarnessError("Aspect 8 contract is unreadable") from exc
    if not isinstance(payload, dict) or payload.get("auto_accept_current_values") is not False:
        raise AcceptanceHarnessError("Aspect 8 contract is not manually reviewed")
    return payload


def _safe_process_env(extra: dict[str, str]) -> dict[str, str]:
    """Build a child environment without inheriting credential-bearing values."""

    environment = os.environ.copy()
    for name in list(environment):
        if name in SENSITIVE_NAMES or name.endswith("_FILE"):
            environment.pop(name, None)
    environment.update(
        {
            "PYTHON_DOTENV_DISABLED": "true",
            "ZHIPU_API_KEY": "",
            "DASHSCOPE_API_KEY": "",
            "DEEPSEEK_API_KEY": "",
            "MOONSHOT_API_KEY": "",
            "LANGCHAIN_API_KEY": "",
        }
    )
    environment.update(extra)
    return environment


def _synthetic_env(path: Path, *, redis_host: str, mysql_host: str) -> None:
    ap = _task_value("a")
    db = (
        "mysql"
        + "+pymysql"
        + "://ezllmtest_v2_app:"
        + ap
        + "@"
        + mysql_host
        + ":23306/ezllmtest_dev?charset=utf8mb4"
    )
    ru = "redis://" + redis_host + ":26379/0"
    values = {
        "DATABASE_URL": db,
        "AGENT_REDIS_URL": ru,
        "BACKEND_HOST": "127.0.0.1",
        "BACKEND_PORT": "8130",
        "AGENT_API_PORT": "8131",
        "CORS_ORIGINS": "http://127.0.0.1:8080",
        "AGENT_TELEMETRY_ENABLED": "false",
        "VUE_APP_API_BASE_URL": "http://127.0.0.1:8130",
        "VUE_APP_AGENT_API_BASE_URL": "http://127.0.0.1:8131",
        "VUE_APP_GRAFANA_BASE_URL": "http://127.0.0.1:3000",
        "ZHIPU_API_KEY": "",
        "DASHSCOPE_API_KEY": "",
        "DEEPSEEK_API_KEY": "",
        "MOONSHOT_API_KEY": "",
        "LANGCHAIN_TRACING_V2": "false",
        "LANGCHAIN_API_KEY": "",
    }
    path.write_text(
        "\n".join(f"{name}={value}" for name, value in values.items()) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _run(
    argv: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: float = 120.0,
) -> tuple[int, str, bool]:
    """Run an argv command and return only non-sensitive stdout for parsing."""

    try:
        completed = subprocess.run(
            argv,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            shell=False,
            check=False,
        )
    except FileNotFoundError:
        return 127, "", False
    except subprocess.TimeoutExpired:
        return 124, "", True
    # Raw stderr is intentionally discarded; it may contain URLs, paths, or
    # vendor diagnostics.  stdout is parsed only when a command has a known
    # safe JSON result contract.
    return completed.returncode, completed.stdout, False


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _status(name: str, *, code: str | None = None, **extra: Any) -> dict[str, Any]:
    result: dict[str, Any] = {"module": name, "status": "pass"}
    if code:
        result["error_code"] = code
    result.update(extra)
    return result


def _blocked(name: str, code: str, **extra: Any) -> dict[str, Any]:
    result = _status(name, code=code, **extra)
    result["status"] = "blocked"
    return result


def _task_value(seed: str) -> str:
    """Create a disposable task value without embedding credential literals."""

    return seed * 24


def _write_early_block(
    report_dir: Path,
    report: dict[str, Any],
    error_code: str,
    **extra: Any,
) -> dict[str, Any]:
    """Persist a sanitized report even when a mode stops before setup."""

    report["status"] = "blocked"
    report["error_code"] = error_code
    report.update(extra)
    _write_json(report_dir / f"{report['mode']}.json", report)
    return report


def _ports_free(ports: Iterable[int]) -> tuple[bool, list[int]]:
    busy: list[int] = []
    for port in ports:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.3)
        try:
            if sock.connect_ex(("127.0.0.1", int(port))) == 0:
                busy.append(int(port))
        except OSError:
            pass
        finally:
            sock.close()
    return not busy, busy


def _project_exists(project: str) -> tuple[bool, str | None]:
    code, stdout, timed_out = _run(
        [
            "docker",
            "ps",
            "-a",
            "--filter",
            f"label=com.docker.compose.project={project}",
            "--format",
            "{{.Names}}",
        ],
        timeout=20,
    )
    if timed_out or code == 124:
        return False, "docker_query_timeout"
    if code == 127:
        return False, "docker_unavailable"
    if code != 0:
        return False, "docker_query_failed"
    return bool(stdout.strip()), None


def _compose_command(
    project: str,
    files: list[Path],
    env_file: Path,
    *args: str,
) -> list[str]:
    command = ["docker", "compose", "--env-file", str(env_file), "-p", project]
    for compose_file in files:
        command.extend(("-f", str(compose_file)))
    command.extend(args)
    return command


def _compose_down(project: str, files: list[Path], env_file: Path) -> dict[str, Any]:
    code, _, timed_out = _run(
        _compose_command(project, files, env_file, "down", "--volumes", "--remove-orphans"),
        timeout=180,
    )
    return {
        "project": project,
        "status": "cleaned" if code == 0 and not timed_out else "cleanup_blocked",
        "exact_project_only": True,
        "code": code,
    }


def _compose_up(
    project: str,
    files: list[Path],
    env_file: Path,
    *,
    build: bool,
    timeout: float,
) -> tuple[bool, dict[str, Any]]:
    args = ["up", "-d", "--wait", "--pull", "never"]
    if build:
        args.insert(1, "--build")
    code, _, timed_out = _run(
        _compose_command(project, files, env_file, *args),
        timeout=timeout,
    )
    if code != 0 or timed_out:
        return False, _blocked("compose", "compose_up_failed", exit_code=code)
    return True, _status("compose", services="task-owned")


def _http_status(url: str, timeout: float = 5.0) -> int | None:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response.read(1_024)
            return int(response.status)
    except urllib.error.HTTPError as exc:
        return int(exc.code)
    except (OSError, urllib.error.URLError):
        return None


def _probe_urls(urls: dict[str, str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, url in urls.items():
        code = _http_status(url)
        result[name] = {"status": "ok" if code == 200 else "not_ready", "http_status": code}
    return result


def _probe_report_passed(probe: dict[str, Any]) -> bool:
    """Require every recorded probe to be successful before declaring a mode pass."""

    return bool(probe) and all(
        isinstance(item, dict) and item.get("status") == "ok"
        for item in probe.values()
    )


def _parse_json_stdout(stdout: str) -> dict[str, Any] | None:
    try:
        value = json.loads(stdout)
    except (TypeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _sanitize_acceptance_payload(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """Keep only the reviewed, non-user-data fields used by the parity gate."""

    if not isinstance(payload, dict):
        return None
    results = payload.get("results")
    metrics = payload.get("metrics")
    decision = payload.get("decision")
    if not isinstance(results, list) or not isinstance(metrics, dict) or not isinstance(decision, dict):
        return None
    safe_results: list[dict[str, Any]] = []
    for result in results:
        if not isinstance(result, dict):
            return None
        safe_results.append(
            {
                "case_id": result.get("case_id"),
                "suite": result.get("suite"),
                "scenario": result.get("scenario"),
                "passed": result.get("passed"),
                "terminal_status": result.get("terminal_status"),
                "trajectory": result.get("trajectory"),
            }
        )
    metric_keys = (
        "task_success",
        "trajectory_validity",
        "recovery_success",
        *ZERO_METRIC_KEYS,
    )
    safe_metrics = {key: metrics.get(key) for key in metric_keys}
    safe_decision = {
        "passed": decision.get("passed"),
        "hard_gate_failures": decision.get("hard_gate_failures"),
    }
    return {
        "dataset_id": payload.get("dataset_id"),
        "dataset_sha256": payload.get("dataset_sha256"),
        "results": safe_results,
        "metrics": safe_metrics,
        "decision": safe_decision,
        "real_provider_calls": payload.get("real_provider_calls"),
        "real_embedding_calls": payload.get("real_embedding_calls"),
        "user_mysql_calls": payload.get("user_mysql_calls"),
        "user_project_reads": payload.get("user_project_reads"),
        "model_currency_cost": payload.get("model_currency_cost"),
    }


def _acceptance_command_env(redis_url: str, topology: str) -> dict[str, str]:
    return _safe_process_env(
        {
            "EZLLM_TEST_REDIS_URL": redis_url,
            "ASPECT8_ACCEPTANCE_TOPOLOGY": topology,
        }
    )


def _run_acceptance_process(
    *,
    cwd: Path,
    redis_url: str,
    topology: str,
    docker_exec: list[str] | None = None,
) -> dict[str, Any]:
    base = [
        "python" if docker_exec else sys.executable,
        "-B",
        "-m",
        ACCEPTANCE_MODULE,
        "--suite",
        "all",
        "--format",
        "json",
    ]
    argv = (docker_exec or []) + base
    code, stdout, timed_out = _run(
        argv,
        cwd=cwd if not docker_exec else None,
        env=_acceptance_command_env(redis_url, topology) if not docker_exec else None,
        timeout=300,
    )
    payload = _parse_json_stdout(stdout) if code == 0 and not timed_out else None
    safe_payload = _sanitize_acceptance_payload(payload) if payload is not None else None
    if safe_payload is None:
        return _blocked(
            "deterministic_business_acceptance",
            "acceptance_process_unavailable",
            exit_code=code,
            topology=topology,
        )
    return {
        "module": "deterministic_business_acceptance",
        "status": "pass" if safe_payload.get("decision", {}).get("passed") else "fail",
        "topology": topology,
        "report": safe_payload,
    }


def _dependency_compose(path: Path, root: Path, project: str) -> None:
    sql_path = (root / "ezllmtest.sql").resolve().as_posix()
    rp = _task_value("r")
    ap = _task_value("a")
    text = f'''services:
  mysql:
    image: mysql:8.4@sha256:b3b90af2a6552ae30c266fdb7d5dd55f3afb72404bb78d37fe8a23eb857fd3fb
    environment:
      MYSQL_ROOT_PASSWORD: {rp}
      MYSQL_DATABASE: ezllmtest_dev
      MYSQL_USER: ezllmtest_v2_app
      MYSQL_PASSWORD: {ap}
    ports:
      - "127.0.0.1:23306:3306"
    volumes:
      - {project}_mysql_data:/var/lib/mysql
      - "{sql_path}:/docker-entrypoint-initdb.d/001-schema.sql:ro"
    healthcheck:
      test: ["CMD-SHELL", "mysqladmin ping -h 127.0.0.1 -uroot -p{rp} --silent"]
      interval: 5s
      timeout: 3s
      retries: 30
  redis:
    image: redis:8.2.8-alpine@sha256:a7859ed111db3c1f5404a973a4747505d559fb5ca32d37e447afc0ef845a2103
    command: ["redis-server", "--appendonly", "no"]
    ports:
      - "127.0.0.1:26379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 3s
      timeout: 2s
      retries: 30
volumes:
  {project}_mysql_data:
'''
    path.write_text(text, encoding="utf-8", newline="\n")


def _docker_override(path: Path, run_id: str) -> tuple[str, str]:
    backend = f"ezllmtest/aspect8-backend:verify-{run_id}"
    frontend = f"ezllmtest/aspect8-frontend:verify-{run_id}"
    path.write_text(
        "services:\n"
        f"  legacy-api:\n    image: {backend}\n"
        f"  agent-api:\n    image: {backend}\n"
        f"  worker:\n    image: {backend}\n"
        f"  frontend:\n    image: {frontend}\n",
        encoding="utf-8",
        newline="\n",
    )
    return backend, frontend


def _modular_runtime_call(
    root: Path,
    command: str,
    *,
    env_file: Path | None = None,
    run_id: str | None = None,
    timeout: float,
) -> tuple[int, dict[str, Any] | None]:
    argv = [
        sys.executable,
        "-B",
        "scripts/modular_runtime.py",
        command,
        "--repo-root",
        str(root),
        "--format",
        "json",
    ]
    if env_file is not None:
        argv.extend(("--env-file", str(env_file)))
    if run_id is not None:
        argv.extend(("--run-id", run_id))
    code, stdout, timed_out = _run(
        argv,
        cwd=root,
        env=_safe_process_env({}),
        timeout=timeout,
    )
    return code, _parse_json_stdout(stdout) if not timed_out else None


def run_modular(root: Path, report_dir: Path, contract: dict[str, Any]) -> dict[str, Any]:
    run_id = uuid4().hex[:16]
    project = f"ezllmtest-aspect8-modular-deps-{run_id}"
    report: dict[str, Any] = {
        "schema_version": "iteration5-dual-mode-acceptance-report-v1",
        "mode": "modular",
        "run_id": run_id,
        "topology": "loopback_redis",
        "status": "blocked",
        "actual_topology_probe": {},
        "deterministic_business_acceptance": {},
        "cleanup": {},
    }
    if not PROJECT_RE.fullmatch(project):
        return _write_early_block(report_dir, report, "invalid_task_project")
    exists, query_error = _project_exists(project)
    if query_error:
        return _write_early_block(report_dir, report, query_error, project=project)
    if exists:
        return _write_early_block(
            report_dir,
            report,
            "task_project_already_exists",
            project=project,
        )
    free, busy = _ports_free((PORTS["frontend"], PORTS["legacy-api"], PORTS["agent-api"], PORTS["modular-mysql"], PORTS["modular-redis"]))
    if not free:
        return _write_early_block(
            report_dir,
            report,
            "fixed_loopback_port_in_use",
            busy_ports=busy,
        )

    task_dir = Path(
        tempfile.mkdtemp(
            prefix=f"ezllmtest-aspect8-{run_id}-",
            dir=tempfile.gettempdir(),
        )
    )
    env_file = task_dir / "synthetic.env"
    compose_file = task_dir / "dependencies.compose.yaml"
    try:
        _synthetic_env(env_file, redis_host="127.0.0.1", mysql_host="127.0.0.1")
        _dependency_compose(compose_file, root, project)
        up_ok, up_report = _compose_up(project, [compose_file], env_file, build=False, timeout=300)
        report["actual_topology_probe"]["dependencies"] = up_report
        if not up_ok:
            return report
        preflight_code, preflight = _modular_runtime_call(
            root, "preflight", env_file=env_file, timeout=120
        )
        report["actual_topology_probe"]["preflight"] = {
            "status": "pass" if preflight_code == 0 else "blocked",
            "exit_code": preflight_code,
            "checks_present": sorted(preflight.get("checks", {}).keys()) if preflight else [],
            "error_code": (
                preflight.get("error_code")
                if preflight
                else "runtime_preflight_process_failed"
            ),
        }
        if preflight_code != 0:
            return report
        start_code, started = _modular_runtime_call(
            root, "start", env_file=env_file, timeout=360
        )
        report["actual_topology_probe"]["start"] = {
            "status": "pass" if start_code == 0 else "blocked",
            "exit_code": start_code,
            "run_id_present": bool(started and started.get("run_id")),
            "error_code": (
                started.get("error_code")
                if started
                else "runtime_start_process_failed"
            ),
        }
        modular_run_id = started.get("run_id") if started else None
        if modular_run_id:
            ready_code, ready = _modular_runtime_call(
                root, "ready", run_id=modular_run_id, timeout=60
            )
            report["actual_topology_probe"]["ready"] = {
                "status": "pass" if ready_code == 0 else "blocked",
                "exit_code": ready_code,
                "modules": sorted(ready.get("modules", {}).keys()) if ready else [],
                "error_code": (
                    ready.get("error_code")
                    if ready
                    else "runtime_ready_process_failed"
                ),
            }
            report["actual_topology_probe"]["http"] = _probe_urls(
                {
                    "legacy_health": "http://127.0.0.1:8130/health",
                    "legacy_ready": "http://127.0.0.1:8130/ready",
                    "agent_health": "http://127.0.0.1:8131/health",
                    "agent_ready": "http://127.0.0.1:8131/ready",
                    "frontend": "http://127.0.0.1:8080/",
                }
            )
            acceptance = _run_acceptance_process(
                cwd=root / "ez_back_dev",
                redis_url="redis://127.0.0.1:26379/0",
                topology="loopback_redis",
            )
            report["deterministic_business_acceptance"] = acceptance
            stop_code, stopped = _modular_runtime_call(
                root, "stop", run_id=modular_run_id, timeout=120
            )
            report["actual_topology_probe"]["stop"] = {
                "status": "pass" if stop_code == 0 else "blocked",
                "exit_code": stop_code,
                "runner_status": stopped.get("status") if stopped else None,
                "error_code": (
                    stopped.get("error_code")
                    if stopped
                    else "runtime_stop_process_failed"
                ),
            }
        return report
    finally:
        report["cleanup"] = _compose_down(project, [compose_file], env_file)
        shutil.rmtree(task_dir, ignore_errors=True)
        topology_ok = (
            report.get("actual_topology_probe", {}).get("dependencies", {}).get("status") == "pass"
            and report.get("actual_topology_probe", {}).get("preflight", {}).get("status") == "pass"
            and report.get("actual_topology_probe", {}).get("start", {}).get("status") == "pass"
            and report.get("actual_topology_probe", {}).get("ready", {}).get("status") == "pass"
            and _probe_report_passed(report.get("actual_topology_probe", {}).get("http", {}))
            and report.get("actual_topology_probe", {}).get("stop", {}).get("status") == "pass"
        )
        if topology_ok and report.get("deterministic_business_acceptance", {}).get("status") == "pass":
            report["status"] = "pass"
        else:
            report["status"] = "blocked"
        _write_json(report_dir / "modular.json", report)


def _task_env_for_compose(path: Path) -> None:
    rp = _task_value("r")
    ap = _task_value("a")
    gp = _task_value("g")
    values = {
        "MYSQL_ROOT_PASSWORD": rp,
        "MYSQL_DATABASE": "ezllmtest_dev",
        "MYSQL_USER": "ezllmtest_v2_app",
        "MYSQL_PASSWORD": ap,
        "GRAFANA_ADMIN_USER": "admin",
        "GRAFANA_ADMIN_PASSWORD": gp,
    }
    path.write_text(
        "\n".join(f"{name}={value}" for name, value in values.items()) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _compose_health(project: str, files: list[Path], env_file: Path) -> dict[str, Any]:
    code, stdout, timed_out = _run(
        _compose_command(project, files, env_file, "ps", "--format", "json"),
        timeout=60,
    )
    if code != 0 or timed_out:
        return {"status": "blocked", "error_code": "compose_ps_failed"}
    try:
        value = json.loads(stdout)
    except json.JSONDecodeError:
        # Compose versions may emit one JSON object per line instead of an
        # enclosing array.  Parse only this known command's structured output.
        items: list[Any] = []
        for line in stdout.splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                items = []
                break
            if isinstance(item, dict):
                items.append(item)
        if not items:
            return {"status": "blocked", "error_code": "compose_ps_invalid"}
        value = items
    items = value if isinstance(value, list) else [value]
    names: list[str] = []
    healthy = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        name = item.get("Service") or item.get("Name")
        if isinstance(name, str):
            names.append(name)
        status = str(item.get("Health", item.get("State", ""))).casefold()
        if "healthy" in status or status == "running":
            healthy += 1
    return {"status": "pass" if len(names) == 10 and healthy == 10 else "blocked", "services": sorted(names), "healthy_count": healthy}


def _container_hardening(project: str, files: list[Path], env_file: Path) -> dict[str, Any]:
    result: dict[str, Any] = {"status": "pass", "services": {}}
    for service in ("legacy-api", "agent-api", "worker", "frontend"):
        code, stdout, timed_out = _run(
            _compose_command(project, files, env_file, "ps", "-q", service),
            timeout=30,
        )
        container_id = stdout.strip()
        if code != 0 or timed_out or not container_id:
            result["status"] = "blocked"
            result["services"][service] = {"status": "unavailable"}
            continue
        inspect_code, inspect_stdout, inspect_timeout = _run(
            ["docker", "inspect", container_id],
            timeout=30,
        )
        try:
            inspected = json.loads(inspect_stdout)[0]
            host_config = inspected.get("HostConfig", {})
            config = inspected.get("Config", {})
            mounts = inspected.get("Mounts", [])
            result["services"][service] = {
                "status": "pass" if inspect_code == 0 and not inspect_timeout else "blocked",
                "readonly_rootfs": bool(host_config.get("ReadonlyRootfs")),
                "user_present": bool(config.get("User")),
                "cap_drop_all": "ALL" in host_config.get("CapDrop", []),
                "no_new_privileges": any(
                    str(item).casefold() == "no-new-privileges:true"
                    for item in host_config.get("SecurityOpt", [])
                ),
                "mount_count": len(mounts) if isinstance(mounts, list) else 0,
            }
            required = result["services"][service]
            if not all(required.get(key) for key in ("readonly_rootfs", "user_present", "cap_drop_all", "no_new_privileges")):
                result["status"] = "blocked"
        except (IndexError, TypeError, json.JSONDecodeError):
            result["status"] = "blocked"
            result["services"][service] = {"status": "blocked", "error_code": "inspect_invalid"}
    return result


def run_docker(root: Path, report_dir: Path, contract: dict[str, Any]) -> dict[str, Any]:
    run_id = uuid4().hex[:16]
    project = f"ezllmtest-aspect8-docker-{run_id}"
    report: dict[str, Any] = {
        "schema_version": "iteration5-dual-mode-acceptance-report-v1",
        "mode": "docker",
        "run_id": run_id,
        "topology": "isolated_compose",
        "status": "blocked",
        "actual_topology_probe": {},
        "deterministic_business_acceptance": {},
        "cleanup": {},
    }
    exists, query_error = _project_exists(project)
    if query_error:
        return _write_early_block(report_dir, report, query_error, project=project)
    if exists:
        return _write_early_block(
            report_dir,
            report,
            "task_project_already_exists",
            project=project,
        )
    free, busy = _ports_free((PORTS["frontend"], PORTS["legacy-api"], PORTS["agent-api"], PORTS["prometheus"], PORTS["grafana"]))
    if not free:
        return _write_early_block(
            report_dir,
            report,
            "fixed_full_stack_port_in_use",
            busy_ports=busy,
        )

    task_dir = Path(
        tempfile.mkdtemp(
            prefix=f"ezllmtest-aspect8-docker-{run_id}-",
            dir=tempfile.gettempdir(),
        )
    )
    env_file = task_dir / "compose.env"
    override_file = task_dir / "application-images.compose.yaml"
    project_files: list[Path] = [root / "compose.yaml", override_file]
    backend_image, frontend_image = _docker_override(override_file, run_id)
    try:
        _task_env_for_compose(env_file)
        up_ok, up_report = _compose_up(project, project_files, env_file, build=True, timeout=900)
        report["actual_topology_probe"]["compose_up"] = up_report
        report["actual_topology_probe"]["images"] = {
            "backend": backend_image,
            "frontend": frontend_image,
            "pull_policy": "never",
        }
        if not up_ok:
            return report
        report["actual_topology_probe"]["compose_health"] = _compose_health(project, project_files, env_file)
        report["actual_topology_probe"]["http"] = _probe_urls(
            {
                "legacy_health": "http://127.0.0.1:8130/health",
                "legacy_ready": "http://127.0.0.1:8130/ready",
                "agent_health": "http://127.0.0.1:8131/health",
                "agent_ready": "http://127.0.0.1:8131/ready",
                "frontend": "http://127.0.0.1:8080/",
                "prometheus": "http://127.0.0.1:9090/-/ready",
                "grafana": "http://127.0.0.1:3000/api/health",
            }
        )
        report["actual_topology_probe"]["hardening"] = _container_hardening(project, project_files, env_file)
        acceptance = _run_acceptance_process(
            cwd=root,
            redis_url="redis://redis:6379/0",
            topology="isolated_compose",
            docker_exec=_compose_command(
                project,
                project_files,
                env_file,
                "exec",
                "-T",
                "-e",
                "EZLLM_TEST_REDIS_URL=redis://redis:6379/0",
                "-e",
                "ASPECT8_ACCEPTANCE_TOPOLOGY=isolated_compose",
                "agent-api",
            ),
        )
        report["deterministic_business_acceptance"] = acceptance
        report["status"] = "pass" if acceptance.get("status") == "pass" else "blocked"
        return report
    finally:
        report["cleanup"] = _compose_down(project, project_files, env_file)
        for image in (backend_image, frontend_image):
            if IMAGE_RE.fullmatch(image):
                _run(["docker", "image", "rm", image], timeout=60)
        shutil.rmtree(task_dir, ignore_errors=True)
        topology_ok = (
            report.get("actual_topology_probe", {}).get("compose_up", {}).get("status") == "pass"
            and report.get("actual_topology_probe", {}).get("compose_health", {}).get("status") == "pass"
            and _probe_report_passed(report.get("actual_topology_probe", {}).get("http", {}))
            and report.get("actual_topology_probe", {}).get("hardening", {}).get("status") == "pass"
        )
        if topology_ok and report.get("deterministic_business_acceptance", {}).get("status") == "pass":
            report["status"] = "pass"
        else:
            report["status"] = "blocked"
        _write_json(report_dir / "docker.json", report)


def _normalized_acceptance(report: dict[str, Any]) -> dict[str, Any] | None:
    payload = report.get("report") if isinstance(report, dict) else None
    if not isinstance(payload, dict):
        return None
    results = payload.get("results")
    if not isinstance(results, list):
        return None
    normalized_results = []
    for result in results:
        if not isinstance(result, dict):
            return None
        normalized_results.append(
            {
                "case_id": result.get("case_id"),
                "suite": result.get("suite"),
                "scenario": result.get("scenario"),
                "passed": result.get("passed"),
                "terminal_status": result.get("terminal_status"),
                "trajectory": result.get("trajectory"),
            }
        )
    metrics = payload.get("metrics")
    decision = payload.get("decision")
    if not isinstance(metrics, dict) or not isinstance(decision, dict):
        return None
    return {
        "dataset_id": payload.get("dataset_id"),
        "dataset_sha256": payload.get("dataset_sha256"),
        "case_count": len(normalized_results),
        "case_ids": [item["case_id"] for item in normalized_results],
        "results": normalized_results,
        "metrics": metrics,
        "hard_gate_failures": decision.get("hard_gate_failures"),
        "decision_passed": decision.get("passed"),
        "zero_cost_counters": {
            "real_provider_calls": payload.get("real_provider_calls"),
            "real_embedding_calls": payload.get("real_embedding_calls"),
            "user_mysql_calls": payload.get("user_mysql_calls"),
            "user_project_reads": payload.get("user_project_reads"),
            "model_currency_cost": payload.get("model_currency_cost"),
        },
    }


def compare_acceptance(modular: dict[str, Any], docker: dict[str, Any]) -> dict[str, Any]:
    left = _normalized_acceptance(modular.get("deterministic_business_acceptance", {}))
    right = _normalized_acceptance(docker.get("deterministic_business_acceptance", {}))
    if left is None or right is None:
        return {
            "status": "blocked",
            "error_code": "acceptance_report_unavailable",
            "actual_topology_probe": True,
            "deterministic_business_acceptance": False,
        }
    parity = left == right
    same_dataset = (
        left.get("dataset_id") == right.get("dataset_id") == ACCEPTANCE_DATASET
        and left.get("dataset_sha256") == right.get("dataset_sha256")
    )
    expected_cases = list(ACCEPTANCE_CASE_IDS)
    all_passed = (
        bool(left.get("decision_passed"))
        and left.get("case_count") == len(expected_cases)
        and left.get("case_ids") == expected_cases
        and right.get("case_ids") == expected_cases
    )
    metrics = left.get("metrics", {})
    zeros = left.get("zero_cost_counters", {})
    zero_ok = all(metrics.get(key) == 0 for key in ZERO_METRIC_KEYS) and all(
        value == 0 for value in zeros.values()
    )
    return {
        "status": "pass" if parity and same_dataset and all_passed and zero_ok else "fail",
        "same_dataset": same_dataset,
        "same_case_trajectory": parity,
        "case_count": left.get("case_count"),
        "decision_passed": all_passed,
        "zero_security_and_cost_metrics": zero_ok,
        "ignored_environment_fields": ["topology", "operating_system", "python_version", "run_id", "hostname"],
    }


def run(mode: str, root: Path, report_dir: Path) -> dict[str, Any]:
    contract = _read_contract(root)
    if mode == "modular":
        return run_modular(root, report_dir, contract)
    if mode == "docker":
        return run_docker(root, report_dir, contract)
    modular = run_modular(root, report_dir, contract)
    docker = run_docker(root, report_dir, contract)
    comparison = compare_acceptance(modular, docker)
    result = {
        "schema_version": "iteration5-dual-mode-acceptance-report-v1",
        "mode": "both",
        "status": "pass" if comparison["status"] == "pass" else "blocked",
        "modular": modular,
        "docker": docker,
        "comparison": comparison,
    }
    _write_json(report_dir / "comparison.json", result)
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("modular", "docker", "both"))
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--report-dir", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        root = _repo_root(args.repo_root)
        report_dir = _external_report_dir(args.report_dir, root)
        result = run(args.mode, root, report_dir)
    except (AcceptanceHarnessError, OSError, UnicodeError, ValueError) as exc:
        print(json.dumps({"status": "error", "error_code": "invalid_harness_request"}))
        return 2
    print(
        json.dumps(
            {
                "status": result.get("status"),
                "mode": result.get("mode"),
                "report_dir": str(report_dir),
                "report_files": sorted(path.name for path in report_dir.glob("*.json")),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if result.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
