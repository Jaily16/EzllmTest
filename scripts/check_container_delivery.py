"""Read-only Docker delivery contract checker for Iteration 5 Aspect 7.

The checker deliberately inspects only public repository metadata.  It never
loads environment files, contacts Docker, opens a database, or follows a user
data path.  A reviewed migration fixture is the only way for an active file
to differ from the Aspect 7 baseline.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


CONTRACT_RELATIVE = Path("ops/container-delivery-contract.json")
BASELINE_RELATIVE = Path(
    "ez_back_dev/tests/fixtures/current/iteration5/"
    "iteration5_container_delivery_baseline_v1.json"
)
MIGRATION_RELATIVE = Path(
    "ez_back_dev/tests/fixtures/current/iteration5/"
    "iteration5_container_delivery_migration_v1.json"
)
VERSION_RELATIVE = Path("ops/version-contract.json")
MODULAR_RELATIVE = Path("ops/modular-runtime-contract.json")
COMPOSE_RELATIVE = Path("compose.yaml")
OVERLAY_RELATIVE = Path("ops/compose/observability-profile.yaml")
BACKEND_DOCKERFILE = Path("ez_back_dev/Dockerfile")
FRONTEND_DOCKERFILE = Path("ez_front_dev/Dockerfile")
NGINX_RELATIVE = Path("ops/frontend/nginx.conf")
CONFIG_RELATIVE = Path("ez_back_dev/infrastructure/config.py")
DOCKERIGNORE_RELATIVE = Path(".dockerignore")
CI_RELATIVE = Path(".github/workflows/iteration4-offline.yml")
ASPECT8_CONTRACT_RELATIVE = Path("ops/iteration5-dual-mode-acceptance-contract.json")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)
FROM_RE = re.compile(r"^\s*FROM\s+(\S+)(?:\s+AS\s+(\S+))?\s*$", re.IGNORECASE)


class ContractError(ValueError):
    """Raised when a checker input is malformed or outside the safe scope."""


def _safe_path(root: Path, relative: str | Path) -> Path:
    """Resolve one public repository path without accepting user-data roots."""

    value = str(relative).replace("\\", "/")
    if not value or "\x00" in value:
        raise ContractError("empty or NUL path")
    candidate = Path(value)
    if candidate.is_absolute() or any(part == ".." for part in candidate.parts):
        raise ContractError("absolute or parent path is outside the contract")
    lowered = value.casefold()
    protected_fragments = (
        ".env",
        "/.env",
        "static/projects",
        "uploads",
        "volume",
        "user-data",
        "user_data",
    )
    if lowered == ".env" or any(fragment in lowered for fragment in protected_fragments):
        raise ContractError("protected data path is outside the checker scope")
    root_resolved = root.resolve()
    path = (root_resolved / candidate).resolve(strict=False)
    if path != root_resolved and root_resolved not in path.parents:
        raise ContractError("path escapes repository")
    if path.is_symlink():
        raise ContractError("symlink is not an approved contract input")
    return path


def _read_text(root: Path, relative: str | Path) -> str:
    path = _safe_path(root, relative)
    if not path.is_file():
        raise ContractError(f"missing contract input: {relative}")
    try:
        return path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise ContractError(f"unreadable contract input: {relative}") from exc


def _read_json(root: Path, relative: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(_read_text(root, relative))
    except json.JSONDecodeError as exc:
        raise ContractError(f"invalid JSON: {relative}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"JSON object required: {relative}")
    return value


def _normalized_bytes(path: Path) -> bytes:
    payload = path.read_bytes()
    text = payload.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    return (text.rstrip("\n") + "\n").encode("utf-8")


def _raw_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _normalized_sha256(path: Path) -> str:
    return hashlib.sha256(_normalized_bytes(path)).hexdigest()


def _add(report: dict[str, Any], check_id: str, ok: bool, detail: str) -> None:
    item = {"id": check_id, "status": "pass" if ok else "fail", "detail": detail}
    report["checks"].append(item)
    if not ok:
        report["errors"].append(item)


def _load_yaml(root: Path, relative: str | Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - depends on the host toolchain
        raise ContractError("PyYAML is required by the offline compose checker") from exc
    try:
        value = yaml.safe_load(_read_text(root, relative))
    except Exception as exc:  # yaml parser exceptions vary by PyYAML version
        raise ContractError(f"invalid YAML: {relative}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"YAML object required: {relative}")
    return value


def _compose_port(value: Any) -> tuple[str, int] | None:
    if isinstance(value, dict):
        host = str(value.get("host_ip", ""))
        published = value.get("published")
        if published is None:
            return None
        return host, int(published)
    text = str(value)
    text = text.split("/", 1)[0]
    parts = text.split(":")
    if len(parts) == 3:
        return parts[0].strip("[]"), int(parts[1])
    if len(parts) == 2:
        return "", int(parts[0])
    return None


def _compose_published_ports(services: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for name, service in services.items():
        if not isinstance(service, dict):
            continue
        for raw in service.get("ports", []) or []:
            parsed = _compose_port(raw)
            if parsed is None:
                continue
            host, published = parsed
            result[name] = {"host": host, "port": published}
    return result


def _joined(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(_joined(item) for item in value)
    if isinstance(value, dict):
        return " ".join(f"{key}={_joined(item)}" for key, item in value.items())
    return str(value)


def _docker_stages(source: str) -> list[tuple[str, str | None]]:
    stages: list[tuple[str, str | None]] = []
    for line in source.splitlines():
        match = FROM_RE.match(line)
        if match:
            stages.append((match.group(1), match.group(2)))
    return stages


def _check_dockerfiles(root: Path, contract: dict[str, Any], report: dict[str, Any]) -> None:
    version = _read_json(root, VERSION_RELATIVE)
    docker_versions = version.get("dockerfiles", {})
    expected_backend = docker_versions.get("backend_base")
    expected_front_build = docker_versions.get("frontend_build_base")
    expected_front_runtime = docker_versions.get("frontend_runtime_base")

    backend = _read_text(root, BACKEND_DOCKERFILE)
    backend_stages = _docker_stages(backend)
    backend_names = [name for _, name in backend_stages]
    backend_ok = (
        len(backend_stages) >= 2
        and backend_stages[0][0] == expected_backend
        and "dependencies" in backend_names
        and "runtime" in backend_names
        and "--require-hashes" in backend
        and "COPY --from=dependencies" in backend
        and "COPY ez_back_dev /app" in backend
        and "USER 10001:10001" in backend
        and "EXPOSE 8130 8131" in backend
        and "app.main:app" in backend
        and "requirements-dev" not in backend.casefold()
        and "pip-tools" not in backend.casefold()
        and "ruff" not in backend.casefold()
        and not re.search(r"^\s*(?:ARG|ENV)\s+[^\n]*(?:API_KEY|PASSWORD|DATABASE_URL)", backend, re.I | re.M)
        and not re.search(r"^\s*COPY\s+[^\n]*\.env", backend, re.I | re.M)
    )
    _add(report, "docker.backend.multi_stage_and_non_root", backend_ok, "backend build/runtime hardening")

    frontend = _read_text(root, FRONTEND_DOCKERFILE)
    frontend_stages = _docker_stages(frontend)
    frontend_names = [name for _, name in frontend_stages]
    frontend_ok = (
        len(frontend_stages) >= 2
        and frontend_stages[0][0] == expected_front_build
        and frontend_stages[-1][0] == expected_front_runtime
        and "build" in frontend_names
        and "runtime" in frontend_names
        and "npm ci --ignore-scripts --no-audit --no-fund" in frontend
        and re.search(r"^\s*COPY\s+(?:--[^\n]+\s+)*--from=build\s+/app/dist", frontend, re.I | re.M)
        and "ops/frontend/nginx.conf" in frontend
        and re.search(r"^\s*USER\s+(?:nginx|[1-9][0-9]*)\s*$", frontend, re.I | re.M)
        and not re.search(r"^\s*ARG\s+[^\n]*(?:API_KEY|PASSWORD|DATABASE_URL)", frontend, re.I | re.M)
        and not re.search(r"^\s*COPY\s+[^\n]*\.env", frontend, re.I | re.M)
    )
    _add(report, "docker.frontend.non_root_runtime", bool(frontend_ok), "frontend build/runtime hardening")


def _check_nginx(root: Path, report: dict[str, Any]) -> None:
    source = _read_text(root, NGINX_RELATIVE)
    required = (
        "listen 8080;",
        "server_tokens off;",
        "try_files $uri $uri/ /index.html;",
        "X-Content-Type-Options",
        "Referrer-Policy",
        "X-Frame-Options",
    )
    _add(
        report,
        "nginx.runtime_contract",
        all(item in source for item in required) and "listen 80;" not in source,
        "8080 SPA fallback and existing response headers",
    )


def _check_compose(root: Path, contract: dict[str, Any], report: dict[str, Any]) -> None:
    compose = _load_yaml(root, COMPOSE_RELATIVE)
    services = compose.get("services")
    if not isinstance(services, dict):
        raise ContractError("compose services object required")
    expected_services = contract.get("default_services")
    _add(
        report,
        "compose.default_services",
        list(services) == expected_services,
        "default service order and membership",
    )

    expected_ports = contract.get("published_ports")
    actual_ports = _compose_published_ports(services)
    ports_ok = actual_ports == expected_ports and all(
        item.get("host") == "127.0.0.1" for item in actual_ports.values()
    )
    _add(report, "compose.loopback_ports", ports_ok, "published ports remain loopback-only")

    volumes = compose.get("volumes")
    actual_volumes = list(volumes) if isinstance(volumes, dict) else []
    _add(
        report,
        "compose.named_volumes",
        actual_volumes == contract.get("named_volumes"),
        "named volume names are unchanged",
    )
    networks = compose.get("networks")
    networks_ok = isinstance(networks, dict) and networks == contract.get("networks")
    _add(report, "compose.networks", networks_ok, "application/observability network policy")

    for service_name in ("legacy-api", "agent-api", "worker"):
        service = services.get(service_name, {})
        expected = contract["service_security"]["backend"]
        values = {
            "user": str(service.get("user", "")),
            "read_only": service.get("read_only"),
            "cap_drop": service.get("cap_drop"),
            "security_opt": service.get("security_opt"),
        }
        tmpfs = service.get("tmpfs", []) or []
        values["tmpfs"] = tmpfs
        security_ok = (
            values["user"] == expected["user"]
            and values["read_only"] is True
            and values["cap_drop"] == expected["cap_drop"]
            and values["security_opt"] == expected["security_opt"]
            and any(str(item).startswith("/tmp") for item in tmpfs)
            and service.get("privileged") is not True
        )
        _add(report, f"compose.security.{service_name}", security_ok, "least-privilege backend service")

    frontend = services.get("frontend", {})
    expected_frontend = contract["service_security"]["frontend"]
    front_tmpfs = frontend.get("tmpfs", []) or []
    frontend_security_ok = (
        str(frontend.get("user", "")) == expected_frontend["user"]
        and frontend.get("read_only") is True
        and frontend.get("cap_drop") == expected_frontend["cap_drop"]
        and frontend.get("security_opt") == expected_frontend["security_opt"]
        and all(any(str(item).startswith(prefix) for item in front_tmpfs) for prefix in expected_frontend["tmpfs_prefixes"])
        and frontend.get("privileged") is not True
    )
    _add(report, "compose.security.frontend", frontend_security_ok, "least-privilege frontend service")

    health_ok = True
    for name, expected_path in (
        ("legacy-api", "/health"),
        ("agent-api", "/health"),
        ("frontend", "http://127.0.0.1:8080/"),
        ("worker", "ping"),
    ):
        health = services.get(name, {}).get("healthcheck", {})
        health_text = _joined(health.get("test", "")) if isinstance(health, dict) else ""
        if expected_path not in health_text:
            health_ok = False
        if name in {"legacy-api", "agent-api"} and "/ready" in health_text:
            health_ok = False
    _add(report, "compose.healthcheck_boundary", health_ok, "health checks remain separate from readiness")

    project_mount_ok = True
    for name in ("legacy-api", "agent-api", "worker"):
        mount_text = _joined(services.get(name, {}).get("volumes", []))
        if "project_files:/app/static/projects" not in mount_text:
            project_mount_ok = False
    _add(report, "compose.project_files_mount", project_mount_ok, "only approved project volume remains writable")

    for name in ("legacy-api", "agent-api"):
        source = _read_text(root, Path("ez_back_dev/app") / ("main.py" if name == "legacy-api" else "agentApi.py"))
        _add(
            report,
            f"api.{name}.health_readiness",
            '@app.get("/health")' in source and '@app.get("/ready")' in source,
            "health and readiness routes coexist",
        )


def _check_overlay(root: Path, contract: dict[str, Any], report: dict[str, Any]) -> None:
    overlay = _load_yaml(root, OVERLAY_RELATIVE)
    services = overlay.get("services")
    expected = contract["profile_overlay"]
    overlay_ok = isinstance(services, dict) and list(services) == expected["services"]
    if overlay_ok:
        for name, service in services.items():
            overlay_ok = (
                isinstance(service, dict)
                and service.get("profiles") == [expected["profile"]]
                and set(service) == {"profiles"}
            ) and overlay_ok
    overlay_ok = overlay_ok and set(overlay) == {"services"}
    _add(report, "compose.observability_profile", overlay_ok, "profile overlay only marks observability services")


def _check_image_parity(root: Path, report: dict[str, Any]) -> None:
    version = _read_json(root, VERSION_RELATIVE)
    contract = _read_json(root, CONTRACT_RELATIVE)
    compose = _load_yaml(root, COMPOSE_RELATIVE)
    services = compose.get("services", {})
    image_contract = version.get("images", {})
    application_tags = image_contract.get("application_tags", {})
    refs = image_contract.get("refs", {})
    parity_ok = (
        services.get("legacy-api", {}).get("image") == application_tags.get("backend")
        and services.get("agent-api", {}).get("image") == application_tags.get("backend")
        and services.get("worker", {}).get("image") == application_tags.get("backend")
        and services.get("frontend", {}).get("image") == application_tags.get("frontend")
    )
    for name, ref in refs.items():
        if services.get(name, {}).get("image") != ref:
            parity_ok = False
    parity_ok = parity_ok and contract.get("images", {}).get("application", {}) == application_tags
    _add(report, "images.version_contract_parity", parity_ok, "Compose image identity follows version contract")


def _check_config_boundary(root: Path, contract: dict[str, Any], report: dict[str, Any]) -> None:
    source = _read_text(root, CONFIG_RELATIVE)
    policy = contract["secret_file_policy"]
    names = policy["allowlist"]
    names_ok = all(name in source for name in names)
    no_arbitrary = "_FILE" in source and "SECRET_FILE_NAMES" in source
    safe_errors = "invalid secret file configuration" in source
    dotenv_guard = "PYTHON_DOTENV_DISABLED" in source and "load_dotenv" in source
    _add(
        report,
        "config.secret_file_allowlist",
        names_ok and no_arbitrary and safe_errors,
        "secret-file support is explicit and allowlisted",
    )
    _add(report, "config.dotenv_container_guard", dotenv_guard, "container dotenv discovery is explicitly guarded")


def _check_dockerignore(root: Path, contract: dict[str, Any], report: dict[str, Any]) -> None:
    source = _read_text(root, DOCKERIGNORE_RELATIVE)
    lines = {line.strip() for line in source.splitlines() if line.strip() and not line.lstrip().startswith("#")}
    required = set(contract["dockerignore_required"])
    _add(report, "dockerignore.sensitive_paths", required.issubset(lines), "env, caches, build output and user projects excluded")


def _check_modular_parity(root: Path, contract: dict[str, Any], report: dict[str, Any]) -> None:
    modular = _read_json(root, MODULAR_RELATIVE)
    services = modular.get("compose_crosscheck", {}).get("services")
    service_ok = services == contract["default_services"]
    ports = modular.get("compose_crosscheck", {}).get("loopback_published_ports")
    expected_ports = sorted(value["port"] for value in contract["published_ports"].values())
    port_ok = sorted(ports or []) == expected_ports
    _add(report, "modular.compose_service_parity", service_ok and port_ok, "module and Compose service/port sets agree")
    _add(
        report,
        "modular.operations_boundary",
        "no-compose-start" in modular.get("protected_operations", [])
        and "no-compose-stop" in modular.get("protected_operations", [])
        and "no-volume-operation" in modular.get("protected_operations", []),
        "modular runner does not own Compose or volume lifecycle",
    )


def _check_ci(root: Path, contract: dict[str, Any], report: dict[str, Any]) -> None:
    source = _read_text(root, CI_RELATIVE)
    static_check = "python -B scripts/check_container_delivery.py --check --format text" in source
    base_config = "docker compose --env-file ops/compose/.env.example" in source and "config --quiet" in source
    project_ok = contract["ci"]["disposable_project"] in source
    cleanup_ok = "down -v" in source and project_ok
    no_root_data = "docker volume prune" not in source and "docker system prune" not in source
    _add(report, "ci.container_static_gate", static_check, "container checker is a CI read-only gate")
    _add(report, "ci.compose_config_gate", base_config, "Compose config validation remains present")
    _add(report, "ci.disposable_cleanup_scope", cleanup_ok and no_root_data, "CI cleanup remains project-scoped")


def _check_baseline(root: Path, report: dict[str, Any]) -> dict[str, Any]:
    baseline = _read_json(root, BASELINE_RELATIVE)
    _add(
        report,
        "baseline.schema",
        baseline.get("schema_version") == "iteration5-container-delivery-baseline-v1"
        and baseline.get("aspect") == 7,
        "Aspect 7 baseline schema",
    )
    _add(
        report,
        "baseline.manual_review",
        baseline.get("manual_reviewed") is True
        and baseline.get("auto_accept_current_values") is False,
        "manual_reviewed and auto_accept_current_values",
    )
    parent = baseline.get("parent")
    parent_ok = isinstance(parent, dict) and isinstance(parent.get("fixture"), str)
    if parent_ok:
        parent_path = _safe_path(root, parent["fixture"])
        parent_ok = (
            parent_path.is_file()
            and isinstance(parent.get("fixture_sha256"), str)
            and SHA256_RE.fullmatch(parent["fixture_sha256"]) is not None
            and _normalized_sha256(parent_path) == parent["fixture_sha256"].lower()
        )
    _add(report, "baseline.parent_hash", parent_ok, "Aspect 6 migration parent hash")

    protected = baseline.get("protected_paths")
    protected_hashes = baseline.get("protected_hashes")
    protected_ok = isinstance(protected, list) and bool(protected) and isinstance(protected_hashes, dict)
    if protected_ok:
        for relative in protected:
            if not isinstance(relative, str) or not _safe_path(root, relative).is_file():
                protected_ok = False
                break
        for relative, expected in protected_hashes.items():
            if (
                not isinstance(relative, str)
                or not isinstance(expected, str)
                or SHA256_RE.fullmatch(expected) is None
                or _normalized_sha256(_safe_path(root, relative)) != expected.lower()
            ):
                protected_ok = False
                break
    _add(report, "baseline.protected_hashes", protected_ok, "protected immutable files and hashes")
    _add(report, "baseline.removed_paths", baseline.get("removed_paths") == [], "removed_paths")

    snapshots = baseline.get("snapshots")
    snapshot_ok = (
        isinstance(snapshots, dict)
        and snapshots.get("default_services")
        and snapshots.get("observability_services")
        and snapshots.get("published_ports")
        and snapshots.get("named_volumes")
        and snapshots.get("networks")
        and snapshots.get("healthcheck_paths")
        and snapshots.get("readiness_paths")
    )
    _add(report, "baseline.snapshots", bool(snapshot_ok), "reviewed container topology snapshots")
    return baseline


def _check_migration(
    root: Path,
    baseline: dict[str, Any],
    report: dict[str, Any],
    cumulative: dict[str, str] | None = None,
) -> dict[str, str]:
    migration = _read_json(root, MIGRATION_RELATIVE)
    schema_ok = (
        migration.get("schema_version") == "iteration5-container-delivery-migration-v1"
        and migration.get("aspect") == 7
        and migration.get("manual_reviewed") is True
        and migration.get("auto_accept_current_values") is False
        and migration.get("removed_paths") == []
    )
    _add(report, "migration.schema", schema_ok, "reviewed Aspect 7 migration record")
    baseline_path = _safe_path(root, BASELINE_RELATIVE)
    parent_ok = (
        migration.get("parent_baseline") == BASELINE_RELATIVE.as_posix()
        and isinstance(migration.get("parent_baseline_sha256"), str)
        and SHA256_RE.fullmatch(migration["parent_baseline_sha256"]) is not None
        and _normalized_sha256(baseline_path) == migration["parent_baseline_sha256"].lower()
    )
    _add(report, "migration.parent_hash", parent_ok, "baseline hash is explicitly linked")

    batches = migration.get("batches")
    accepted: dict[str, str] = {}
    batches_ok = isinstance(batches, list) and bool(batches)
    seen: set[str] = set()
    required = {
        "old_path",
        "new_path",
        "pre_raw_sha256",
        "pre_normalized_sha256",
        "post_raw_sha256",
        "post_normalized_sha256",
        "hardening",
        "manual_review",
        "isolated_evidence",
        "rollback",
    }
    if isinstance(batches, list):
        for batch in batches:
            if not isinstance(batch, dict) or batch.get("manual_reviewed") is not True:
                batches_ok = False
                continue
            paths = batch.get("paths")
            if not isinstance(paths, list) or not paths:
                batches_ok = False
                continue
            for record in paths:
                if not isinstance(record, dict) or not required.issubset(record):
                    batches_ok = False
                    continue
                new_path = record.get("new_path")
                if not isinstance(new_path, str) or new_path in seen:
                    batches_ok = False
                    continue
                seen.add(new_path)
                try:
                    candidate = _safe_path(root, new_path)
                    current_raw = _raw_sha256(candidate)
                    current_normalized = _normalized_sha256(candidate)
                except (ContractError, OSError, UnicodeError, json.JSONDecodeError):
                    batches_ok = False
                    continue
                post_hash_matches = (
                    not isinstance(record.get("post_raw_sha256"), str)
                    or not isinstance(record.get("post_normalized_sha256"), str)
                    or not SHA256_RE.fullmatch(record["post_raw_sha256"])
                    or not SHA256_RE.fullmatch(record["post_normalized_sha256"])
                    or current_raw != record["post_raw_sha256"].lower()
                    or current_normalized != record["post_normalized_sha256"].lower()
                ) is False
                reviewed_overlay_matches = (
                    isinstance(cumulative, dict)
                    and cumulative.get(new_path) == current_normalized
                )
                if not (post_hash_matches or reviewed_overlay_matches):
                    batches_ok = False
                else:
                    accepted[new_path] = current_normalized
                for field in ("pre_raw_sha256", "pre_normalized_sha256"):
                    value = record.get(field)
                    if value is not None and (
                        not isinstance(value, str) or SHA256_RE.fullmatch(value) is None
                    ):
                        batches_ok = False
                if not isinstance(record.get("hardening"), str) or not record["hardening"].strip():
                    batches_ok = False
                if record.get("manual_review") is not True:
                    batches_ok = False
                if not isinstance(record.get("isolated_evidence"), dict):
                    batches_ok = False
                if not isinstance(record.get("rollback"), str) or not record["rollback"].strip():
                    batches_ok = False
    _add(report, "migration.reviewed_batches", batches_ok, f"reviewed records={len(seen)}")
    return accepted


def _check_aspect8_cumulative_overlay(root: Path, report: dict[str, Any]) -> dict[str, str]:
    """Accept only the explicit, reviewed post-Aspect-7 hash overlay."""

    try:
        contract = _read_json(root, ASPECT8_CONTRACT_RELATIVE)
    except ContractError:
        _add(report, "aspect8.cumulative_overlay", False, "Aspect 8 cumulative overlay is unavailable")
        return {}

    overlay = contract.get("cumulative_overlay")
    allowed = overlay.get("allowed_paths") if isinstance(overlay, dict) else None
    valid = (
        contract.get("schema_version") == "iteration5-dual-mode-acceptance-v1"
        and isinstance(overlay, dict)
        and overlay.get("manual_reviewed") is True
        and overlay.get("auto_accept_current_values") is False
        and isinstance(allowed, dict)
        and bool(allowed)
    )
    accepted: dict[str, str] = {}
    forbidden_fragments = (
        ".env",
        "static/projects",
        "uploads",
        "volume",
        "node_modules",
        "dist",
        "coverage",
        "cache",
        "logs",
        "trace",
        "screenshot",
    )
    required_hashes = (
        "raw_sha256",
        "normalized_sha256",
        "frontend_sha256",
        "modular_sha256",
        "backend_sha256",
    )
    excluded = {
        ASPECT8_CONTRACT_RELATIVE.as_posix(),
        BASELINE_RELATIVE.as_posix(),
        MIGRATION_RELATIVE.as_posix(),
    }
    if isinstance(allowed, dict):
        for relative, evidence in allowed.items():
            if not isinstance(relative, str) or any(char in relative for char in "*?"):
                valid = False
                continue
            if relative in excluded or any(fragment in relative.casefold() for fragment in forbidden_fragments):
                valid = False
                continue
            if not isinstance(evidence, dict) or evidence.get("manual_review") is not True:
                valid = False
                continue
            if not all(
                isinstance(evidence.get(field), str) and SHA256_RE.fullmatch(evidence[field])
                for field in required_hashes
            ):
                valid = False
                continue
            try:
                path = _safe_path(root, relative)
                current_raw = _raw_sha256(path)
                current_normalized = _normalized_sha256(path)
            except (ContractError, OSError, UnicodeError):
                valid = False
                continue
            expected = {
                "raw_sha256": current_raw,
                "normalized_sha256": current_normalized,
                "frontend_sha256": current_normalized,
                "modular_sha256": current_normalized,
                "backend_sha256": current_normalized,
            }
            if any(evidence[field].lower() != expected[field] for field in required_hashes):
                valid = False
                continue
            accepted[relative] = current_normalized
    _add(
        report,
        "aspect8.cumulative_overlay",
        valid,
        f"reviewed current paths={len(accepted)}",
    )
    return accepted


def _check_active_hashes(
    root: Path,
    baseline: dict[str, Any],
    accepted: dict[str, str],
    report: dict[str, Any],
) -> None:
    entries = baseline.get("file_hashes")
    hashes_ok = isinstance(entries, dict) and bool(entries)
    if hashes_ok:
        for relative, record in entries.items():
            try:
                path = _safe_path(root, relative)
                raw = _raw_sha256(path)
                normalized = _normalized_sha256(path)
            except (ContractError, OSError, UnicodeError, json.JSONDecodeError):
                hashes_ok = False
                break
            if not isinstance(record, dict):
                hashes_ok = False
                break
            baseline_match = (
                raw == str(record.get("raw_sha256", "")).lower()
                and normalized == str(record.get("normalized_sha256", "")).lower()
            )
            migration_match = accepted.get(relative) == normalized
            if not baseline_match and not migration_match:
                hashes_ok = False
                break
    _add(report, "baseline.active_hashes", hashes_ok, "active files are baseline or reviewed migration outputs")


def check_repository(root: Path) -> dict[str, Any]:
    root = root.resolve()
    if not root.is_dir():
        raise ContractError("repository root must be a directory")
    report: dict[str, Any] = {
        "schema_version": "iteration5-container-delivery-report-v1",
        "status": "pass",
        "checks": [],
        "errors": [],
        "scope": {"repo_root": root.as_posix(), "reads_environment_files": False},
    }
    contract = _read_json(root, CONTRACT_RELATIVE)
    _add(
        report,
        "contract.schema",
        contract.get("schema_version") == "iteration5-container-delivery-v1"
        and contract.get("aspect") == 7
        and contract.get("auto_accept_current_values") is False,
        "container delivery contract schema",
    )
    serialized = json.dumps(contract, ensure_ascii=False).casefold()
    _add(
        report,
        "contract.non_sensitive",
        all(token not in serialized for token in ("api_key=", "password=", "project-id", "project_id")),
        "contract contains names and policies, not secret values or project scope",
    )
    _check_dockerfiles(root, contract, report)
    _check_nginx(root, report)
    _check_compose(root, contract, report)
    _check_overlay(root, contract, report)
    cumulative = _check_aspect8_cumulative_overlay(root, report)
    _check_image_parity(root, report)
    _check_config_boundary(root, contract, report)
    _check_dockerignore(root, contract, report)
    _check_modular_parity(root, contract, report)
    _check_ci(root, contract, report)
    baseline = _check_baseline(root, report)
    accepted = _check_migration(root, baseline, report, cumulative)
    accepted.update(cumulative)
    _check_active_hashes(root, baseline, accepted, report)
    if report["errors"]:
        report["status"] = "fail"
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check the read-only Aspect 7 container delivery contract.")
    parser.add_argument("--check", action="store_true", help="validate the reviewed repository state")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.check:
        _parser().error("--check is required")
    repo_root = args.repo_root
    if not repo_root.is_absolute():
        print("repository root must be absolute", file=sys.stderr)
        return 2
    try:
        report = check_repository(repo_root)
    except (ContractError, OSError, UnicodeError, ValueError) as exc:
        report = {
            "schema_version": "iteration5-container-delivery-report-v1",
            "status": "error",
            "checks": [],
            "errors": [{"id": "checker.input", "status": "fail", "detail": str(exc)}],
        }
        exit_code = 2
    else:
        exit_code = 0 if report["status"] == "pass" else 1
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"container-delivery: {report['status']}")
        for item in report.get("checks", []):
            print(f"[{item['status']}] {item['id']}: {item['detail']}")
        for item in report.get("errors", []):
            if item not in report.get("checks", []):
                print(f"[fail] {item['id']}: {item['detail']}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
