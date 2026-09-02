"""Read-only Aspect 8 closeout and dual-mode acceptance contract checker.

The checker only reads explicitly named repository metadata and immutable
fixtures.  It never loads an environment file, contacts Docker, databases,
Redis, providers, or user projects, and it has no baseline-acceptance or
cleanup mode.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


CONTRACT_RELATIVE = Path("ops/iteration5-dual-mode-acceptance-contract.json")
BASELINE_RELATIVE = Path(
    "ez_back_dev/tests/fixtures/current/iteration5/"
    "iteration5_dual_mode_acceptance_baseline_v1.json"
)
MIGRATION_RELATIVE = Path(
    "ez_back_dev/tests/fixtures/current/iteration5/"
    "iteration5_dual_mode_acceptance_migration_v1.json"
)
SCHEMA_VERSION = "iteration5-dual-mode-acceptance-check-v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)
FORBIDDEN_SWITCHES = {
    "--accept-current",
    "--update",
    "--write",
    "--delete",
    "--prune",
}
FORBIDDEN_OUTPUT_TOKENS = (
    "api_key=",
    "password=",
    "database_url=",
    "redis_url=",
    "traceback",
    "request_body",
    "user_content",
    "sk-",
    "begin private key",
)
# These markers describe the report policy itself.  The checker must reject
# actual values or assignments, not the names of fields that the policy
# requires it to omit.
SENSITIVE_VALUE_PATTERNS = (
    re.compile(r"(?:api_key|password|database_url|redis_url)\s*=\s*[^\s,}]+", re.IGNORECASE),
    re.compile(r"(?:mysql|redis)://[^\s\"']+", re.IGNORECASE),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b", re.IGNORECASE),
    re.compile(r"begin private key", re.IGNORECASE),
)


class ContractError(ValueError):
    """Raised when a public closeout input is malformed or unsafe."""


def _safe_root(value: str | Path | None) -> Path:
    root = Path(value) if value is not None else Path(__file__).resolve().parents[1]
    if not root.is_absolute():
        raise ContractError("repo-root must be absolute")
    resolved = root.resolve()
    if not resolved.is_dir():
        raise ContractError("repo-root is not a directory")
    return resolved


def _safe_path(root: Path, relative: str | Path, *, allow_env_marker: bool = False) -> Path:
    value = str(relative).replace("\\", "/")
    candidate = Path(value)
    if not value or "\x00" in value or candidate.is_absolute() or ".." in candidate.parts:
        raise ContractError("invalid repository path")
    lowered = value.casefold()
    if lowered == ".env" or ("/.env" in lowered or lowered.startswith(".env")):
        if not allow_env_marker or not lowered.endswith(".env.example"):
            raise ContractError("environment files are not inspectable")
    forbidden_fragments = (
        "static/projects",
        "node_modules",
        "dist",
        "coverage",
        ".pytest_cache",
        ".ruff_cache",
        "volume",
        "uploads",
    )
    if any(fragment in lowered for fragment in forbidden_fragments):
        raise ContractError("generated, user-data, or volume path is outside the checker scope")
    resolved = (root / candidate).resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ContractError("repository path escapes root") from exc
    if resolved.is_symlink():
        raise ContractError("symlink is not an approved contract input")
    return resolved


def _read_text(root: Path, relative: str | Path) -> str:
    path = _safe_path(root, relative)
    if not path.is_file():
        raise ContractError(f"missing public input: {relative}")
    try:
        return path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise ContractError(f"unreadable public input: {relative}") from exc


def _read_json(root: Path, relative: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(_read_text(root, relative))
    except json.JSONDecodeError as exc:
        raise ContractError(f"invalid JSON input: {relative}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"JSON object required: {relative}")
    return value


def normalized_bytes(path: Path) -> bytes:
    """Return a stable UTF-8/LF representation for reviewed text evidence."""

    payload = path.read_bytes()
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError:
        return payload
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return (text.rstrip("\n") + "\n").encode("utf-8")


def normalized_sha256(path: Path) -> str:
    return hashlib.sha256(normalized_bytes(path)).hexdigest().upper()


def _add(report: dict[str, Any], check_id: str, ok: bool, detail: str) -> None:
    item = {"id": check_id, "status": "pass" if ok else "fail", "detail": detail}
    report["checks"].append(item)
    if not ok:
        report["errors"].append(item)


def _all_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        values: list[str] = []
        for key, item in value.items():
            values.extend(_all_strings(key))
            values.extend(_all_strings(item))
        return values
    if isinstance(value, list):
        values = []
        for item in value:
            values.extend(_all_strings(item))
        return values
    return []


def _contains_sensitive_value(value: str) -> bool:
    return any(pattern.search(value) is not None for pattern in SENSITIVE_VALUE_PATTERNS)


def _check_parent_evidence(root: Path, contract: dict[str, Any], report: dict[str, Any]) -> None:
    groups = contract.get("parent_evidence")
    ok = isinstance(groups, dict) and bool(groups)
    count = 0
    if ok:
        for group_name, entries in groups.items():
            if not isinstance(group_name, str) or not isinstance(entries, list):
                ok = False
                continue
            for entry in entries:
                count += 1
                if not isinstance(entry, dict):
                    ok = False
                    continue
                path_value = entry.get("path")
                expected = entry.get("normalized_sha256")
                if not isinstance(path_value, str) or not isinstance(expected, str):
                    ok = False
                    continue
                try:
                    path = _safe_path(root, path_value)
                except ContractError:
                    ok = False
                    continue
                if not path.is_file() or not SHA256_RE.fullmatch(expected):
                    ok = False
                    continue
                if normalized_sha256(path) != expected.upper():
                    ok = False
    _add(report, "parent.evidence_hashes", ok and count >= 9, f"reviewed inputs={count}")


def _check_acceptance_dataset(root: Path, contract: dict[str, Any], report: dict[str, Any]) -> None:
    spec = contract.get("acceptance_dataset")
    ok = isinstance(spec, dict)
    if not ok:
        _add(report, "acceptance.dataset", False, "dataset specification is missing")
        return
    path_value = spec.get("path")
    try:
        path = _safe_path(root, path_value)
    except (ContractError, TypeError):
        _add(report, "acceptance.dataset", False, "dataset path is not safe")
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        _add(report, "acceptance.dataset", False, "historical dataset is unreadable")
        return
    cases = payload.get("cases") if isinstance(payload, dict) else None
    ids = [item.get("id") for item in cases] if isinstance(cases, list) else []
    ok = (
        path.is_file()
        and spec.get("immutable") is True
        and spec.get("provider") == "deterministic_fake"
        and payload.get("dataset_id") == spec.get("dataset_id")
        and len(cases or []) == spec.get("case_count")
        and ids == spec.get("case_ids")
        and normalized_sha256(path) == str(spec.get("normalized_sha256", "")).upper()
    )
    _add(report, "acceptance.immutable_dataset", ok, f"cases={len(ids)}")


def _service_names(compose_text: str) -> list[str]:
    in_services = False
    names: list[str] = []
    for line in compose_text.splitlines():
        if line.strip() == "services:":
            in_services = True
            continue
        if in_services and line and not line.startswith(" "):
            break
        if in_services:
            match = re.match(r"^  ([A-Za-z0-9][A-Za-z0-9_-]*):\s*$", line)
            if match:
                names.append(match.group(1))
    return names


def _check_topologies(root: Path, contract: dict[str, Any], report: dict[str, Any]) -> None:
    topologies = contract.get("topologies")
    modular = topologies.get("loopback_redis") if isinstance(topologies, dict) else None
    docker = topologies.get("isolated_compose") if isinstance(topologies, dict) else None
    modular_ok = (
        isinstance(modular, dict)
        and modular.get("dependency_ports") == {"mysql": 23306, "redis": 26379}
        and modular.get("runner_must_not_manage")
        == ["mysql", "redis", "mcp", "observability"]
    )
    _add(report, "topology.modular_boundary", modular_ok, "task-owned dependencies are external to modular runner")
    compose_path = _safe_path(root, "compose.yaml")
    compose_names = _service_names(compose_path.read_text(encoding="utf-8"))
    expected = docker.get("service_count") == 10 if isinstance(docker, dict) else False
    expected = expected and compose_names == [
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
    if isinstance(docker, dict):
        expected = expected and docker.get("published_ports") == [8080, 8130, 8131, 9090, 3000]
    _add(report, "topology.compose_snapshot", expected, f"services={len(compose_names)}")


def _check_runner_sources(root: Path, report: dict[str, Any]) -> None:
    paths = (
        "scripts/run_iteration5_dual_mode_acceptance.py",
        "scripts/modular_runtime.py",
    )
    source_parts: list[str] = []
    ok = True
    for relative in paths:
        path = _safe_path(root, relative)
        if not path.is_file():
            ok = False
            continue
        source = path.read_text(encoding="utf-8")
        source_parts.append(source)
        if relative.endswith("run_iteration5_dual_mode_acceptance.py"):
            ok = ok and all(
                token in source
                for token in (
                    "shell=False",
                    "--pull",
                    "report-dir",
                    "tempfile.gettempdir",
                    "ASPECT8_ACCEPTANCE_TOPOLOGY",
                )
            )
        if relative.endswith("modular_runtime.py"):
            ok = ok and all(
                token in source
                for token in ("--env-file", "PYTHON_DOTENV_DISABLED", "shell=False", "tempfile.gettempdir")
            )
    serialized = "\n".join(source_parts).casefold()
    ok = ok and not any(token in serialized for token in ("docker system prune", "docker volume prune", "docker volume rm"))
    _add(report, "runner.safety", ok, "argv execution, external reports and exact disposable cleanup policy")


def _check_evaluation_paths(root: Path, report: dict[str, Any]) -> None:
    acceptance = _read_text(root, "ez_back_dev/service/evaluation/acceptance_runner.py")
    evaluation = _read_text(root, "ez_back_dev/service/evaluation/eval_runner.py")
    expected = "tests / \"fixtures\" / \"historical\" / \"iteration4\""
    acceptance_ok = "HISTORICAL_FIXTURE_ROOT" in acceptance and "iteration4_agent_acceptance_v1.json" in acceptance
    evaluation_ok = all(
        token in evaluation
        for token in (
            'FIXTURE_ROOT = BACKEND_ROOT / "tests" / "fixtures" / "historical" / "iteration4"',
            'CORE_DATASET_PATH = FIXTURE_ROOT / "iteration4_agent_eval_v2.json"',
            'ASPECT7_MANIFEST_PATH = FIXTURE_ROOT / "iteration4_aspect7_manifest_v1.json"',
        )
    )
    old_root_reference = "tests / \"fixtures\" / \"iteration4_agent_"
    ok = acceptance_ok and evaluation_ok and old_root_reference not in acceptance
    _add(report, "evaluation.historical_fixture_paths", ok, expected)


def _check_baseline(root: Path, contract: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    baseline = _read_json(root, BASELINE_RELATIVE)
    flags_ok = (
        baseline.get("schema_version") == "iteration5-dual-mode-acceptance-baseline-v1"
        and baseline.get("aspect") == 8
        and baseline.get("manual_reviewed") is True
        and baseline.get("auto_accept_current_values") is False
        and baseline.get("removed_paths") == []
    )
    _add(report, "baseline.reviewed", flags_ok, "manual baseline and empty removed_paths")
    contract_hash = baseline.get("parent_contract_sha256")
    contract_path = _safe_path(root, CONTRACT_RELATIVE)
    hash_ok = (
        isinstance(contract_hash, str)
        and SHA256_RE.fullmatch(contract_hash) is not None
        and normalized_sha256(contract_path) == contract_hash.upper()
    )
    _add(report, "baseline.contract_hash", hash_ok, "contract parent hash")
    dataset = baseline.get("acceptance_dataset", {})
    contract_dataset = contract.get("acceptance_dataset", {})
    dataset_ok = (
        dataset.get("path") == contract_dataset.get("path")
        and dataset.get("normalized_sha256") == contract_dataset.get("normalized_sha256")
        and dataset.get("case_count") == 18
    )
    _add(report, "baseline.dataset_hash", dataset_ok, "immutable acceptance dataset")
    snapshot = baseline.get("public_contract_snapshot", {})
    snapshot_ok = snapshot.get("workflow_count") == 19 and snapshot.get("tool_count") == 22
    _add(report, "baseline.public_snapshot", snapshot_ok, "19 workflows and 22 tools")
    return baseline


def _check_migration(root: Path, report: dict[str, Any]) -> dict[str, Any]:
    migration = _read_json(root, MIGRATION_RELATIVE)
    ok = (
        migration.get("schema_version") == "iteration5-dual-mode-acceptance-migration-v1"
        and migration.get("aspect") == 8
        and migration.get("manual_reviewed") is True
        and migration.get("auto_accept_current_values") is False
        and migration.get("removed_paths") == []
        and isinstance(migration.get("batches"), list)
    )
    count = 0
    if ok:
        for batch in migration["batches"]:
            if not isinstance(batch, dict) or batch.get("manual_reviewed") is not True:
                ok = False
                continue
            records = batch.get("paths")
            if not isinstance(records, list):
                ok = False
                continue
            for record in records:
                count += 1
                if not isinstance(record, dict) or record.get("manual_review") is not True:
                    ok = False
                    continue
                post = record.get("post_normalized_sha256")
                if not isinstance(post, str) or not SHA256_RE.fullmatch(post):
                    ok = False
                    continue
                new_path = record.get("new_path")
                if isinstance(new_path, str):
                    try:
                        path = _safe_path(root, new_path)
                    except ContractError:
                        ok = False
                    else:
                        if not path.is_file() or normalized_sha256(path) != post.upper():
                            ok = False
    _add(report, "migration.reviewed_records", ok and count >= 2, f"reviewed records={count}")
    return migration


def _check_cumulative_overlay(root: Path, contract: dict[str, Any], report: dict[str, Any]) -> None:
    """Validate the narrow, manually reviewed escape hatch for prior checkers."""

    overlay = contract.get("cumulative_overlay")
    allowed = overlay.get("allowed_paths") if isinstance(overlay, dict) else None
    ok = (
        isinstance(overlay, dict)
        and overlay.get("manual_reviewed") is True
        and overlay.get("auto_accept_current_values") is False
        and isinstance(allowed, dict)
        and bool(allowed)
    )
    checked = 0
    if ok:
        for relative, evidence in allowed.items():
            checked += 1
            if not isinstance(relative, str) or not isinstance(evidence, dict):
                ok = False
                continue
            if relative in {
                CONTRACT_RELATIVE.as_posix(),
                BASELINE_RELATIVE.as_posix(),
                MIGRATION_RELATIVE.as_posix(),
            }:
                ok = False
            try:
                path = _safe_path(root, relative)
            except ContractError:
                ok = False
                continue
            fields_ok = (
                evidence.get("manual_review") is True
                and isinstance(evidence.get("reason"), str)
                and bool(evidence.get("reason"))
                and all(
                    isinstance(evidence.get(field), str)
                    and SHA256_RE.fullmatch(evidence[field]) is not None
                    for field in (
                        "raw_sha256",
                        "normalized_sha256",
                        "frontend_sha256",
                        "modular_sha256",
                        "backend_sha256",
                    )
                )
            )
            ok = ok and fields_ok and path.is_file()
            if path.is_file() and fields_ok:
                ok = ok and hashlib.sha256(path.read_bytes()).hexdigest().upper() == evidence["raw_sha256"].upper()
                ok = ok and normalized_sha256(path) == evidence["normalized_sha256"].upper()
    _add(report, "cumulative_overlay.reviewed", ok and checked > 0, f"reviewed later paths={checked}")


def _check_report_policy(contract: dict[str, Any], report: dict[str, Any]) -> None:
    policy = contract.get("report_policy")
    strings = _all_strings(policy)
    serialized = "\n".join(strings).casefold()
    required = all(
        token in serialized
        for token in ("dataset_id", "trajectory", "metrics", "hard_gate_failures", "blocked_or_unknown")
    )
    safe = not _contains_sensitive_value(serialized)
    _add(report, "report.policy", required and safe, "canonical safe normalization and forbidden-field policy")


def check_repository(repo_root: Path) -> dict[str, Any]:
    root = _safe_root(repo_root)
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "checks": [],
        "errors": [],
        "scope": {
            "repo_root": root.as_posix(),
            "reads_environment_files": False,
            "reads_user_projects": False,
            "contacts_external_services": False,
        },
    }
    contract = _read_json(root, CONTRACT_RELATIVE)
    contract_ok = (
        contract.get("schema_version") == "iteration5-dual-mode-acceptance-v1"
        and contract.get("aspect") == 8
        and contract.get("manual_reviewed") is True
        and contract.get("auto_accept_current_values") is False
        and contract.get("removed_paths") == []
    )
    _add(report, "contract.schema", contract_ok, "Aspect 8 reviewed contract")
    _check_parent_evidence(root, contract, report)
    _check_acceptance_dataset(root, contract, report)
    _check_topologies(root, contract, report)
    _check_runner_sources(root, report)
    _check_evaluation_paths(root, report)
    _check_report_policy(contract, report)
    _check_cumulative_overlay(root, contract, report)
    _check_baseline(root, contract, report)
    _check_migration(root, report)
    sensitive = json.dumps(report, ensure_ascii=False)
    _add(report, "report.self_safe", not _contains_sensitive_value(sensitive), "checker output contains no sensitive values")
    if report["errors"]:
        report["status"] = "fail"
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", required=True)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    output_format = "text"
    try:
        args = _parser().parse_args(argv)
        output_format = args.format
        if not args.repo_root.is_absolute():
            raise ContractError("repo-root must be absolute")
        report = check_repository(args.repo_root)
    except (ContractError, OSError, UnicodeError, ValueError) as exc:
        report = {
            "schema_version": SCHEMA_VERSION,
            "status": "error",
            "checks": [],
            "errors": [{"id": "checker.input", "status": "fail", "detail": str(exc)}],
        }
        exit_code = 2
    else:
        exit_code = 0 if report["status"] == "pass" else 1
    if output_format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"iteration5-closeout: {report['status']}")
        for item in report.get("checks", []):
            print(f"[{item['status']}] {item['id']}: {item['detail']}")
        for item in report.get("errors", []):
            if item not in report.get("checks", []):
                print(f"[fail] {item['id']}: {item['detail']}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
