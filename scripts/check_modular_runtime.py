"""Validate the Aspect 6 modular runtime contract without starting services."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


CONTRACT_RELATIVE = Path("ops/modular-runtime-contract.json")
BASELINE_RELATIVE = Path(
    "ez_back_dev/tests/fixtures/current/iteration5/"
    "iteration5_modular_runtime_baseline_v1.json"
)
MIGRATION_RELATIVE = Path(
    "ez_back_dev/tests/fixtures/current/iteration5/"
    "iteration5_modular_runtime_migration_v1.json"
)
ASPECT8_CONTRACT_RELATIVE = Path("ops/iteration5-dual-mode-acceptance-contract.json")
SCHEMA_VERSION = "iteration5-modular-runtime-v1"
BASELINE_SCHEMA = "iteration5-modular-runtime-baseline-v1"
MIGRATION_SCHEMA = "iteration5-modular-runtime-migration-v1"
READINESS_SCHEMA = "iteration5-readiness-v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)
ENV_FILE_RE = re.compile(r"(?:^|[\\/])\.env(?:$|[\\/])", re.IGNORECASE)
SECRET_VALUE_RE = re.compile(
    r"(?:sk-[A-Za-z0-9]|mysql(?:\+\w+)?://|redis://|replace_with_|BEGIN\s+[^\n]+PRIVATE KEY)",
    re.IGNORECASE,
)
FORBIDDEN_OPERATION_RE = re.compile(
    r"(?:docker\s+compose\s+(?:up|down|rm|stop)|volume\s+(?:rm|prune)|\b(?:drop|insert|update|delete|alter|create)\b|cmd\s*/c|powershell\s+-command|bash\s+-c|sh\s+-c)",
    re.IGNORECASE,
)


class ContractError(ValueError):
    """Raised when an Aspect 6 input is malformed or unsafe to inspect."""


def _safe_root(value: str | None) -> Path:
    root = Path(value) if value else Path(__file__).resolve().parents[1]
    if not root.is_absolute():
        raise ContractError("repo-root must be an absolute path")
    resolved = root.resolve()
    if not resolved.is_dir():
        raise ContractError(f"repo-root is not a directory: {resolved}")
    return resolved


def _safe_path(root: Path, relative: str) -> Path:
    candidate_relative = Path(relative)
    if candidate_relative.is_absolute():
        raise ContractError(f"absolute repository path is not allowed: {relative}")
    if ENV_FILE_RE.search(relative) and not relative.replace("\\", "/").endswith(
        ".env.example"
    ):
        raise ContractError(f"real environment file is not inspectable: {relative}")
    candidate = (root / candidate_relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ContractError(f"repository path escapes root: {relative}") from exc
    return candidate


def _read_text(root: Path, relative: str) -> str:
    path = _safe_path(root, relative)
    if not path.is_file():
        raise ContractError(f"missing input: {relative}")
    return path.read_text(encoding="utf-8-sig")


def _read_json(root: Path, relative: str) -> dict[str, Any]:
    try:
        value = json.loads(_read_text(root, relative))
    except json.JSONDecodeError as exc:
        raise ContractError(f"invalid JSON: {relative}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"JSON object required: {relative}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _normalized_sha256(path: Path) -> str:
    """Hash reviewed text files after normalizing the transport newline form."""
    payload = path.read_bytes()
    text = payload.decode("utf-8-sig")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _add(report: dict[str, Any], check_id: str, ok: bool, detail: str) -> None:
    item = {"id": check_id, "status": "pass" if ok else "fail", "detail": detail}
    report["checks"].append(item)
    if not ok:
        report["errors"].append(item)


def _aspect8_overlay_hash(root: Path, relative: str, field: str) -> str | None:
    """Return a reviewed Aspect 8 hash for one exact later-changed path."""

    try:
        contract = _read_json(root, str(ASPECT8_CONTRACT_RELATIVE))
    except (ContractError, OSError, UnicodeError, ValueError):
        return None
    overlay = contract.get("cumulative_overlay")
    allowed = overlay.get("allowed_paths") if isinstance(overlay, dict) else None
    if not isinstance(overlay, dict) or overlay.get("manual_reviewed") is not True:
        return None
    evidence = allowed.get(relative) if isinstance(allowed, dict) else None
    if not isinstance(evidence, dict) or evidence.get("manual_review") is not True:
        return None
    value = evidence.get(field)
    return value if isinstance(value, str) and SHA256_RE.fullmatch(value) else None


def _walk_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        result: list[str] = []
        for key, item in value.items():
            result.extend(_walk_strings(key))
            result.extend(_walk_strings(item))
        return result
    if isinstance(value, list):
        result = []
        for item in value:
            result.extend(_walk_strings(item))
        return result
    return []


def _has_route(source: str, path: str) -> bool:
    return bool(re.search(rf"@app\.get\(\s*['\"]{re.escape(path)}['\"]", source))


def _check_baseline(root: Path, report: dict[str, Any]) -> None:
    baseline = _read_json(root, str(BASELINE_RELATIVE))
    _add(
        report,
        "baseline.schema",
        baseline.get("schema_version") == BASELINE_SCHEMA,
        str(baseline.get("schema_version")),
    )
    _add(report, "baseline.aspect", baseline.get("aspect") == 6, str(baseline.get("aspect")))
    _add(
        report,
        "baseline.manual_review",
        baseline.get("manual_reviewed") is True
        and baseline.get("auto_accept_current_values") is False,
        "manual_reviewed and auto_accept_current_values",
    )
    parent = baseline.get("parent")
    parent_ok = isinstance(parent, dict) and isinstance(parent.get("fixture"), str)
    parent_hash_ok = False
    if parent_ok:
        parent_path = _safe_path(root, parent["fixture"])
        parent_hash_ok = bool(
            parent_path.is_file()
            and isinstance(parent.get("fixture_sha256"), str)
            and SHA256_RE.fullmatch(parent["fixture_sha256"])
            and _sha256(parent_path) == parent["fixture_sha256"].lower()
        )
    _add(report, "baseline.parent_hash", parent_ok and parent_hash_ok, "parent fixture hash")
    protected = baseline.get("protected_paths")
    protected_ok = isinstance(protected, list) and bool(protected)
    if protected_ok:
        for relative in protected:
            if not isinstance(relative, str):
                protected_ok = False
                break
            path = _safe_path(root, relative)
            if not path.is_file():
                protected_ok = False
                break
    _add(report, "baseline.protected_paths", protected_ok, "protected path list")
    protected_hashes = baseline.get("protected_hashes")
    hashes_ok = isinstance(protected_hashes, dict) and bool(protected_hashes)
    if hashes_ok:
        for relative, expected in protected_hashes.items():
            if not isinstance(relative, str) or not isinstance(expected, str):
                hashes_ok = False
                break
            path = _safe_path(root, relative)
            if not path.is_file() or not SHA256_RE.fullmatch(expected):
                hashes_ok = False
                break
            actual_hash = _sha256(path)
            reviewed_hash = _aspect8_overlay_hash(root, relative, "raw_sha256")
            actual_normalized_hash = _normalized_sha256(path)
            reviewed_normalized_hash = _aspect8_overlay_hash(root, relative, "normalized_sha256")
            if (
                actual_hash != expected.lower()
                and actual_hash != (reviewed_hash or "").lower()
                and actual_normalized_hash != (reviewed_normalized_hash or "").lower()
            ):
                hashes_ok = False
                break
    _add(report, "baseline.protected_hashes", hashes_ok, "protected SHA-256 values")
    _add(report, "baseline.removed_paths", baseline.get("removed_paths") == [], "removed_paths")


def _check_migration(root: Path, report: dict[str, Any]) -> None:
    migration = _read_json(root, str(MIGRATION_RELATIVE))
    _add(
        report,
        "migration.schema",
        migration.get("schema_version") == MIGRATION_SCHEMA,
        str(migration.get("schema_version")),
    )
    _add(
        report,
        "migration.manual_review",
        migration.get("manual_reviewed") is True
        and migration.get("auto_accept_current_values") is False,
        "manual_reviewed and auto_accept_current_values",
    )
    removed = migration.get("removed_paths")
    _add(report, "migration.removed_paths", removed == [], "removed_paths")
    batches = migration.get("batches")
    batches_ok = isinstance(batches, list) and bool(batches)
    parent = migration.get("parent_baseline")
    parent_hash = migration.get("parent_baseline_sha256")
    baseline_path = root / BASELINE_RELATIVE
    parent_ok = (
        parent == BASELINE_RELATIVE.as_posix()
        and isinstance(parent_hash, str)
        and SHA256_RE.fullmatch(parent_hash) is not None
        and baseline_path.is_file()
        and _normalized_sha256(baseline_path) == parent_hash.lower()
    )
    _add(report, "migration.parent_hash", parent_ok, "parent baseline normalized SHA-256")

    protected_paths: set[str] = set()
    try:
        baseline = _read_json(root, str(BASELINE_RELATIVE))
        protected_paths = {
            value for value in baseline.get("protected_paths", []) if isinstance(value, str)
        }
    except (ContractError, OSError, UnicodeError, ValueError):
        batches_ok = False

    record_count = 0
    seen_destinations: set[str] = set()
    required_fields = {
        "old_path",
        "new_path",
        "pre_hash",
        "post_hash",
        "content_preserved",
        "manual_review",
        "redirect_stub",
    }
    if isinstance(batches, list):
        for batch in batches:
            if not isinstance(batch, dict) or not isinstance(batch.get("id"), str):
                batches_ok = False
                continue
            if batch.get("manual_reviewed") is not True:
                batches_ok = False
            paths = batch.get("paths")
            if not isinstance(paths, list) or not paths:
                batches_ok = False
                continue
            for record in paths:
                record_count += 1
                if not isinstance(record, dict) or not required_fields.issubset(record):
                    batches_ok = False
                    continue
                old_path = record.get("old_path")
                if old_path is not None:
                    if not isinstance(old_path, str):
                        batches_ok = False
                    else:
                        try:
                            old_candidate = _safe_path(root, old_path)
                            if not old_candidate.is_file():
                                batches_ok = False
                        except (ContractError, OSError):
                            batches_ok = False
                new_path = record.get("new_path")
                if not isinstance(new_path, str) or not new_path:
                    batches_ok = False
                    continue
                if new_path in seen_destinations:
                    batches_ok = False
                seen_destinations.add(new_path)
                try:
                    candidate = _safe_path(root, new_path)
                    if not candidate.is_file() or new_path in protected_paths:
                        batches_ok = False
                    else:
                        current_hash = _normalized_sha256(candidate)
                        reviewed_hash = _aspect8_overlay_hash(root, new_path, "modular_sha256")
                        if record.get("post_hash") != current_hash and current_hash != (reviewed_hash or "").lower():
                            batches_ok = False
                except (ContractError, OSError, UnicodeError):
                    batches_ok = False
                pre_hash = record.get("pre_hash")
                if pre_hash is not None and (
                    not isinstance(pre_hash, str) or SHA256_RE.fullmatch(pre_hash) is None
                ):
                    batches_ok = False
                post_hash = record.get("post_hash")
                if not isinstance(post_hash, str) or SHA256_RE.fullmatch(post_hash) is None:
                    batches_ok = False
                if not isinstance(record.get("content_preserved"), bool):
                    batches_ok = False
                if record.get("manual_review") is not True:
                    batches_ok = False
                if not isinstance(record.get("redirect_stub"), bool):
                    batches_ok = False
    if record_count == 0:
        batches_ok = False
    _add(report, "migration.records", batches_ok, f"reviewed records={record_count}")


def _check_contract(root: Path, report: dict[str, Any]) -> dict[str, Any]:
    contract = _read_json(root, str(CONTRACT_RELATIVE))
    _add(
        report,
        "contract.schema",
        contract.get("schema_version") == SCHEMA_VERSION,
        str(contract.get("schema_version")),
    )
    _add(
        report,
        "contract.readiness_schema",
        contract.get("readiness_schema_version") == READINESS_SCHEMA,
        str(contract.get("readiness_schema_version")),
    )
    _add(
        report,
        "contract.manual_acceptance_guard",
        contract.get("auto_accept_current_values") is False,
        str(contract.get("auto_accept_current_values")),
    )
    serialized = "\n".join(_walk_strings(contract))
    _add(
        report,
        "contract.no_sensitive_values",
        not SECRET_VALUE_RE.search(serialized),
        "contract contains names and policies only",
    )
    _add(
        report,
        "contract.no_forbidden_operations",
        not FORBIDDEN_OPERATION_RE.search(serialized),
        "contract contains no destructive or shell operations",
    )

    expected_external = ["mysql", "redis"]
    expected_owned = ["legacy-api", "agent-api", "worker", "frontend"]
    _add(
        report,
        "contract.external_dependencies",
        contract.get("external_dependencies") == expected_external,
        str(contract.get("external_dependencies")),
    )
    _add(
        report,
        "contract.runner_owned",
        contract.get("runner_owned") == expected_owned,
        str(contract.get("runner_owned")),
    )
    _add(
        report,
        "contract.start_order",
        contract.get("managed_start_order") == expected_owned,
        str(contract.get("managed_start_order")),
    )
    _add(
        report,
        "contract.stop_order",
        contract.get("managed_stop_order") == list(reversed(expected_owned)),
        str(contract.get("managed_stop_order")),
    )

    modules = contract.get("modules")
    module_ok = isinstance(modules, dict)
    if module_ok:
        for name in expected_external:
            item = modules.get(name)
            module_ok = module_ok and isinstance(item, dict) and item.get("runner_managed") is False
        for name in expected_owned:
            item = modules.get(name)
            module_ok = module_ok and isinstance(item, dict) and item.get("runner_managed") is True
    _add(report, "contract.module_ownership", module_ok, "external and managed ownership")

    for relative in (
        "ez_back_dev/serve.py",
        "ez_back_dev/app/main.py",
        "ez_back_dev/app/agentApi.py",
        "ez_back_dev/app/agentWorker.py",
        "ez_front_dev/package.json",
        "ez_front_dev/vite.config.ts",
        "compose.yaml",
        "README.md",
        "docs/operations/modular-runtime.md",
        "ops/modular/run.ps1",
        "ops/modular/run.sh",
    ):
        try:
            ok = _safe_path(root, relative).is_file()
        except ContractError:
            ok = False
        _add(report, f"contract.path.{relative}", ok, relative)

    command_ok = True
    for name in expected_owned:
        item = modules.get(name) if isinstance(modules, dict) else None
        command = item.get("command") if isinstance(item, dict) else None
        if not isinstance(command, list) or not command or any(not isinstance(part, str) for part in command):
            command_ok = False
        elif FORBIDDEN_OPERATION_RE.search(" ".join(command)):
            command_ok = False
    _add(report, "contract.commands", command_ok, "argv command templates")

    compose_text = _read_text(root, "compose.yaml")
    compose_services = contract.get("compose_crosscheck", {}).get("services", [])
    services_ok = all(re.search(rf"^\s{{2}}{re.escape(service)}:", compose_text, re.MULTILINE) for service in compose_services)
    _add(report, "contract.compose.services", services_ok, "compose service names")
    ports = contract.get("compose_crosscheck", {}).get("loopback_published_ports", [])
    ports_ok = all(f"127.0.0.1:{port}:{port}" in compose_text for port in ports)
    _add(report, "contract.compose.loopback_ports", ports_ok, "compose loopback ports")

    legacy_source = _read_text(root, "ez_back_dev/app/main.py")
    agent_source = _read_text(root, "ez_back_dev/app/agentApi.py")
    _add(report, "contract.legacy.health_route", _has_route(legacy_source, "/health"), "legacy /health")
    _add(report, "contract.agent.health_route", _has_route(agent_source, "/health"), "agent /health")
    _add(report, "contract.legacy.ready_route", _has_route(legacy_source, "/ready"), "legacy /ready")
    _add(report, "contract.agent.ready_route", _has_route(agent_source, "/ready"), "agent /ready")

    runner_path = _safe_path(root, "scripts/modular_runtime.py")
    runner_ok = runner_path.is_file()
    runner_source = ""
    if runner_ok:
        runner_source = runner_path.read_text(encoding="utf-8")
        try:
            ast.parse(runner_source)
            syntax_ok = True
        except SyntaxError:
            syntax_ok = False
        runner_ok = syntax_ok and all(
            token in runner_source
            for token in ("preflight", "start", "status", "ready", "stop", "PYTHON_DOTENV_DISABLED")
        )
        runner_ok = runner_ok and "tempfile.gettempdir" in runner_source
        runner_ok = runner_ok and not re.search(
            r"(?:docker\s+compose|volume\s+(?:rm|prune)|\b(?:DROP\s+TABLE|INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|ALTER\s+TABLE|CREATE\s+TABLE)\b|shell\s*=\s*True)",
            runner_source,
            re.IGNORECASE,
        )
    _add(report, "contract.runner", runner_ok, "read-only config and owned-process runner")

    environment_ok = all(
        token in runner_source
        for token in (
            "--env-file",
            "explicit absolute path",
            "PYTHON_DOTENV_DISABLED",
            "_probe_database",
            "_probe_redis",
        )
    )
    environment_ok = environment_ok and 'PROJECT_ROOT / ".env"' not in runner_source
    _add(report, "contract.explicit_environment", environment_ok, "explicit env-file policy")

    vite_source = _read_text(root, "ez_front_dev/vite.config.ts")
    _add(
        report,
        "contract.vite.external_env_dir",
        "EZLLMTEST_VITE_ENV_DIR" in vite_source and "envDir" in vite_source,
        "Vite envDir override",
    )
    for relative in ("ops/modular/run.ps1", "ops/modular/run.sh"):
        wrapper_source = _read_text(root, relative)
        wrapper_ok = "modular_runtime.py" in wrapper_source and not re.search(
            r"(?:cmd\s*/c|docker\s+compose\s+(?:down|rm)|volume\s+(?:rm|prune))",
            wrapper_source,
            re.IGNORECASE,
        )
        _add(report, f"contract.wrapper.{relative}", wrapper_ok, relative)

    documentation = contract.get("documentation")
    documentation_ok = isinstance(documentation, dict)
    if documentation_ok:
        guide = _read_text(root, documentation["operator_guide"])
        documentation_ok = all(
            token in guide
            for token in (
                "preflight",
                "readiness",
                "安全停机",
                "PYTHON_DOTENV_DISABLED",
                "MySQL",
                "Redis",
            )
        )
    _add(report, "contract.documentation", documentation_ok, "operator guide")

    checker_path = _safe_path(root, "scripts/check_modular_runtime.py")
    checker_ok = checker_path.is_file()
    if checker_ok:
        checker_source = checker_path.read_text(encoding="utf-8")
        checker_ok = all(
            token in checker_source
            for token in ("--check", "--repo-root", "--format", "ContractError")
        )
    _add(report, "contract.checker", checker_ok, "static checker interface")

    _check_baseline(root, report)
    _check_migration(root, report)
    return contract


def check(root: Path) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "checks": [],
        "errors": [],
    }
    try:
        _check_contract(root, report)
    except (ContractError, OSError, UnicodeError, ValueError) as exc:
        report["status"] = "error"
        report["errors"].append({"id": "checker.input", "detail": str(exc)})
    if report["errors"]:
        report["status"] = "fail"
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", required=True)
    parser.add_argument("--repo-root")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    try:
        root = _safe_root(args.repo_root)
        report = check(root)
    except ContractError as exc:
        report = {
            "schema_version": SCHEMA_VERSION,
            "status": "error",
            "checks": [],
            "errors": [{"id": "checker.arguments", "detail": str(exc)}],
        }
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    else:
        for item in report["checks"]:
            print(f"[{item['status'].upper()}] {item['id']}: {item['detail']}")
        for item in report["errors"]:
            if item not in report["checks"]:
                print(f"[ERROR] {item['id']}: {item['detail']}")
        print(f"status={report['status']}")
    if report["status"] == "pass":
        return 0
    if any(item.get("id") == "checker.arguments" for item in report["errors"]):
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
