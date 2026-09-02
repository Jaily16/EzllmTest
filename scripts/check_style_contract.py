"""Validate the Aspect 3 style contract without writing repository files."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Any

STYLE_BASELINE = Path(
    "ez_back_dev/tests/fixtures/current/iteration5/iteration5_style_baseline_v1.json"
)
STYLE_MIGRATION = Path(
    "ez_back_dev/tests/fixtures/current/iteration5/iteration5_style_migration_v1.json"
)
ARCHITECTURE_BASELINE = Path(
    "ez_back_dev/tests/fixtures/current/iteration5/iteration5_backend_architecture_baseline_v1.json"
)
BACKEND_MIGRATION = Path(
    "ez_back_dev/tests/fixtures/current/iteration5/iteration5_backend_migration_v1.json"
)
ASPECT5_STRUCTURE_MIGRATION = Path(
    "ez_back_dev/tests/fixtures/current/iteration5/iteration5_frontend_structure_migration_v1.json"
)
ASPECT8_CONTRACT = Path("ops/iteration5-dual-mode-acceptance-contract.json")
VERSION_CONTRACT = Path("ops/version-contract.json")
STYLE_SCHEMA = "iteration5-style-baseline-v1"
MIGRATION_SCHEMA = "iteration5-style-migration-v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)
HASH_RE = re.compile(r"--hash=(?P<algorithm>[A-Za-z0-9-]+):(?P<digest>[0-9a-fA-F]+)")
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
SUPPRESSION_RE = re.compile(
    r"(?:fmt\s*:\s*(?:off|skip)|prettier-ignore|eslint-disable|noqa|type:\s*ignore)"
)

REQUIRED_CONFIGS = (
    ".editorconfig",
    ".gitattributes",
    "ruff.toml",
    ".prettierrc.json",
    ".prettierignore",
)

REQUIRED_COMMENT_SYMBOLS = (
    "service.agentContracts.transition",
    "service.agentContracts.approval_is_valid",
    "service.agentContracts.typed_tool_definitions",
    "service.agentCheckpoint.StrictAgentCheckpointSerializer",
    "service.agentCheckpoint.derive_storage_thread_id",
    "service.agentCheckpoint.AsyncAgentRedisCheckpointSaver",
    "service.agentRedisCoordinator.LeaseHandle",
    "service.agentRedisCoordinator.AgentRedisCoordinator",
    "service.agentRuntimeService._run_with_lease_heartbeat",
    "service.agentRuntimeService.AgentRuntimeService",
    "service.agentToolExecutor.AgentToolExecutor",
    "service.agentContext.AgentContextAssembler",
    "service.agentRetrieval.AgentEvidenceRetriever",
    "service.agentTelemetry._SafeSpanExporter",
    "service.agentTelemetry.telemetry_public_status",
    "service.workflowBudget.select_within_token_budget",
    "service.workflowBudget.bound_prompt_context",
    "service.workflowArtifactService.lookup_workflow_artifact",
    "service.workflowArtifactService.save_workflow_artifact",
    "service.projectRevisionService.compute_source_revision",
    "service.projectRevisionService.artifact_input_hash",
    "service.workflowCatalog.list_workflow_definitions",
    "app.routers._sse_message",
    "app.routers.test_plan_stream",
    "app.routers.llm_workflow_stream",
    "app.agentApi._sse_event",
    "app.agentApi.create_agent_api_app",
    "app.mcpServer.create_loopback_app",
    "frontend.AgentWorkbench.initialize",
    "frontend.AgentWorkbench.submitApproval",
    "frontend.AgentWorkbench.cancelCurrentRun",
    "frontend.AgentWorkbench.recoverCurrentRun",
    "frontend.useAgentEvents.parseBlock",
    "frontend.agentWorkbench.request",
    "frontend.router.routes",
)


class ContractError(ValueError):
    """Raised when a style-contract input is unsafe or malformed."""


@lru_cache(maxsize=8)
def _reviewed_relocations(root: str) -> dict[str, str]:
    """Resolve only paths recorded by the reviewed Aspect 5 migration map."""
    repository = Path(root)
    mapping: dict[str, str] = {}
    for name in (
        "iteration3_contract_baseline_v1.json",
        "iteration4_aspect2_manifest_v1.json",
        "iteration4_aspect3_manifest_v1.json",
        "iteration4_aspect4_manifest_v1.json",
        "iteration4_aspect5_manifest_v1.json",
        "iteration4_aspect6_manifest_v1.json",
        "iteration4_aspect7_manifest_v1.json",
        "iteration4_aspect8_manifest_v1.json",
        "iteration4_aspect7_prechange_performance_v1.json",
        "iteration4_aspect7_performance_gate_v1.json",
        "iteration4_aspect5_rag_decision_v1.json",
        "iteration4_rag_eval_v1.json",
        "iteration4_agent_eval_v1.json",
        "iteration4_agent_acceptance_v1.json",
        "iteration4_release_manifest_v1.json",
    ):
        mapping[f"ez_back_dev/tests/fixtures/{name}"] = (
            f"ez_back_dev/tests/fixtures/historical/iteration4/{name}"
        )
    mapping["ez_back_dev/tests/fixtures/iteration3_contract_baseline_v1.json"] = (
        "ez_back_dev/tests/fixtures/historical/iteration3/iteration3_contract_baseline_v1.json"
    )
    for name in (
        "iteration5_asset_inventory_v1.json",
        "iteration5_backend_architecture_baseline_v1.json",
        "iteration5_backend_migration_v1.json",
        "iteration5_baseline_manifest_v1.json",
        "iteration5_cleanup_allowlist_v1.json",
        "iteration5_style_baseline_v1.json",
        "iteration5_style_migration_v1.json",
        "iteration5_version_migration_v1.json",
    ):
        mapping[f"ez_back_dev/tests/fixtures/{name}"] = (
            f"ez_back_dev/tests/fixtures/current/iteration5/{name}"
        )
    migration_path = repository / ASPECT5_STRUCTURE_MIGRATION
    try:
        migration = json.loads(migration_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        migration = {}
    for batch in migration.get("batches", []) if isinstance(migration, dict) else []:
        if not isinstance(batch, dict):
            continue
        for record in batch.get("paths", []):
            if not isinstance(record, dict):
                continue
            old = record.get("old_path")
            new = record.get("new_path")
            if isinstance(old, str) and isinstance(new, str):
                mapping[old.replace("\\", "/")] = new.replace("\\", "/")
    return mapping


def _relocated_relative(root: Path, relative: str) -> str:
    normalized = relative.replace("\\", "/")
    mapping = _reviewed_relocations(str(root.resolve()))
    seen: set[str] = set()
    while normalized in mapping and normalized not in seen:
        seen.add(normalized)
        normalized = mapping[normalized]
    return normalized


def _safe_root(root: Path) -> Path:
    resolved = root.expanduser().resolve()
    if not resolved.is_dir():
        raise ContractError(f"repository root is not a directory: {root}")
    return resolved


def _safe_path(root: Path, relative: str) -> Path:
    relative_path = Path(relative)
    if relative_path.is_absolute():
        raise ContractError(f"absolute input path is not allowed: {relative}")
    parts = {part.casefold() for part in relative_path.parts}
    if ".env" in parts or any(
        part.startswith(".env.") and part.casefold() != ".env.example" for part in parts
    ):
        raise ContractError(f"refusing to inspect a real environment file: {relative}")
    candidate = (root / _relocated_relative(root, relative)).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ContractError(f"path escapes repository root: {relative}") from exc
    return candidate


def _read_bytes(root: Path, relative: str) -> bytes:
    path = _safe_path(root, relative)
    if not path.is_file():
        raise ContractError(f"missing style-contract input: {relative}")
    return path.read_bytes()


def _read_text(root: Path, relative: str) -> str:
    return _read_bytes(root, relative).decode("utf-8-sig")


def _read_json(root: Path, relative: str) -> dict[str, Any]:
    try:
        value = json.loads(_read_text(root, relative))
    except json.JSONDecodeError as exc:
        raise ContractError(f"invalid JSON: {relative}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"JSON object required: {relative}")
    return value


def _normalized_bytes(path: Path) -> bytes:
    payload = path.read_bytes()
    if payload.startswith(b"\xef\xbb\xbf"):
        payload = payload[3:]
    if path.suffix.casefold() == ".json":
        value = json.loads(payload.decode("utf-8"))
        return (
            json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
            + b"\n"
        )
    text = payload.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return (text.rstrip("\n") + "\n").encode("utf-8")


def _normalized_sha256(path: Path) -> str:
    return hashlib.sha256(_normalized_bytes(path)).hexdigest()


def _add(report: dict[str, Any], check_id: str, ok: bool, detail: str) -> None:
    item = {"id": check_id, "status": "pass" if ok else "fail", "detail": detail}
    report["checks"].append(item)
    if not ok:
        report["errors"].append(item)


def _check_required_files(root: Path, report: dict[str, Any]) -> None:
    for relative in REQUIRED_CONFIGS:
        try:
            path = _safe_path(root, relative)
            ok = path.is_file()
        except ContractError as exc:
            _add(report, f"config.{relative}", False, str(exc))
            continue
        _add(report, f"config.{relative}", ok, "present" if ok else "missing")

    required = (
        "ez_back_dev/requirements-dev.in",
        "ez_back_dev/requirements-dev.txt",
        "ez_back_dev/requirements-dev-windows.txt",
        "scripts/check_style_contract.py",
        str(STYLE_BASELINE),
        str(STYLE_MIGRATION),
        "docs/iteration-5-style-guide.md",
    )
    for relative in required:
        try:
            ok = _safe_path(root, relative).is_file()
        except ContractError as exc:
            _add(report, f"required.{relative}", False, str(exc))
            continue
        _add(report, f"required.{relative}", ok, "present" if ok else "missing")


def _check_dev_lock(
    root: Path, relative: str, expected_version: str, report: dict[str, Any]
) -> None:
    platform_name = "windows" if relative.endswith("-windows.txt") else "linux"
    check_id = f"dev_lock.{platform_name}"
    try:
        text = _read_text(root, relative)
    except ContractError as exc:
        _add(report, check_id, False, str(exc))
        return
    requirement_lines: list[str] = []
    current: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#") and "==" in line and not line.startswith("-"):
            if current:
                requirement_lines.append(" ".join(current))
            current = [line.rstrip("\\")]
        elif current and line.startswith("--hash="):
            current.append(line.rstrip("\\"))
        elif current and (not line or line.startswith("#")):
            continue
        elif current:
            requirement_lines.append(" ".join(current))
            current = []
    if current:
        requirement_lines.append(" ".join(current))
    valid = bool(requirement_lines)
    details: list[str] = []
    for line in requirement_lines:
        hashes = HASH_RE.findall(line)
        if not hashes or any(
            algorithm.casefold() != "sha256" or len(digest) != 64 for algorithm, digest in hashes
        ):
            valid = False
            details.append("every pinned requirement needs a 64-character sha256 hash")
        if f"=={expected_version}" not in line:
            valid = False
            details.append(f"expected ruff=={expected_version}")
    _add(
        report,
        check_id,
        valid,
        "; ".join(details) if details else f"{len(requirement_lines)} hashed requirement line(s)",
    )


def _check_quality_contract(root: Path, contract: dict[str, Any], report: dict[str, Any]) -> None:
    quality = contract.get("quality_tools")
    if not isinstance(quality, dict):
        _add(report, "quality_tools.present", False, "quality_tools object is missing")
        return
    ruff = quality.get("ruff", {})
    prettier = quality.get("prettier", {})
    _add(report, "quality_tools.ruff", ruff.get("version") == "0.16.5", str(ruff))
    _add(report, "quality_tools.prettier", prettier.get("version") == "3.9.6", str(prettier))
    paths = quality.get("paths", {})
    expected_paths = {
        # Version contract retains the Aspect 2 root-relative fixture names;
        # the reviewed relocation map resolves them to current storage.
        "style_baseline": "ez_back_dev/tests/fixtures/iteration5_style_baseline_v1.json",
        "style_migration": "ez_back_dev/tests/fixtures/iteration5_style_migration_v1.json",
        "style_checker": "scripts/check_style_contract.py",
        "ruff_config": "ruff.toml",
        "prettier_config": ".prettierrc.json",
    }
    _add(
        report,
        "quality_tools.paths",
        all(paths.get(key) == value for key, value in expected_paths.items()),
        f"observed={paths}",
    )
    python_locks = quality.get("python_dev_locks", {})
    _add(
        report,
        "quality_tools.python_dev_locks",
        python_locks
        == {
            "input": "ez_back_dev/requirements-dev.in",
            "linux": "ez_back_dev/requirements-dev.txt",
            "windows": "ez_back_dev/requirements-dev-windows.txt",
            "generator": {"name": "pip-tools", "version": "7.6.1"},
        },
        f"observed={python_locks}",
    )
    if isinstance(python_locks, dict):
        for platform_name in ("linux", "windows"):
            relative = python_locks.get(platform_name)
            if isinstance(relative, str):
                _check_dev_lock(root, relative, "0.16.5", report)


def _check_format_configs(root: Path, report: dict[str, Any]) -> None:
    try:
        ruff = tomllib.loads(_read_text(root, "ruff.toml"))
        prettier = _read_json(root, ".prettierrc.json")
        editorconfig = _read_text(root, ".editorconfig")
        attributes = _read_text(root, ".gitattributes")
    except (ContractError, tomllib.TOMLDecodeError) as exc:
        _add(report, "format.configs", False, str(exc))
        return
    _add(
        report,
        "format.ruff",
        ruff.get("target-version") == "py311"
        and ruff.get("line-length") == 100
        and ruff.get("format", {}).get("line-ending") == "lf"
        and ruff.get("lint", {}).get("select") == ["E4", "E7", "E9", "F", "I"],
        f"observed={ruff}",
    )
    _add(
        report,
        "format.prettier",
        prettier
        == {
            "printWidth": 100,
            "tabWidth": 2,
            "useTabs": False,
            "semi": True,
            "singleQuote": False,
            "trailingComma": "all",
            "bracketSpacing": True,
            "arrowParens": "always",
            "endOfLine": "lf",
            "proseWrap": "preserve",
        },
        f"observed={prettier}",
    )
    _add(
        report,
        "format.editorconfig",
        "end_of_line = lf" in editorconfig and "insert_final_newline = true" in editorconfig,
        "LF and final newline policy present",
    )
    _add(
        report,
        "format.attributes",
        "*.py text" in attributes
        and "*.vue text" in attributes
        and "*.png binary" in attributes
        and "*.pdf binary" in attributes,
        "source and binary policies present",
    )


def _check_frontend_manifest(root: Path, contract: dict[str, Any], report: dict[str, Any]) -> None:
    try:
        package = _read_json(root, "ez_front_dev/package.json")
        lock = _read_json(root, "ez_front_dev/package-lock.json")
    except ContractError as exc:
        _add(report, "frontend.manifest", False, str(exc))
        return
    dev = package.get("devDependencies", {})
    scripts = package.get("scripts", {})
    root_lock = lock.get("packages", {}).get("")
    _add(
        report,
        "frontend.prettier_version",
        dev.get("prettier") == "3.9.6",
        str(dev.get("prettier")),
    )
    _add(report, "frontend.lock_root", isinstance(root_lock, dict), "root package present")
    if isinstance(root_lock, dict):
        _add(
            report,
            "frontend.lock_prettier",
            root_lock.get("devDependencies", {}).get("prettier") == "3.9.6",
            str(root_lock.get("devDependencies", {}).get("prettier")),
        )
    prettier_package = lock.get("packages", {}).get("node_modules/prettier", {})
    _add(
        report,
        "frontend.lock_prettier_package",
        prettier_package.get("version") == "3.9.6",
        str(prettier_package.get("version")),
    )
    _add(
        report,
        "frontend.format_scripts",
        scripts.get("format") and scripts.get("format:check"),
        f"format={scripts.get('format')}; format:check={scripts.get('format:check')}",
    )
    _add(
        report,
        "frontend.package_contract",
        contract.get("node_lock", {}).get("manifest") == "ez_front_dev/package.json",
        "manifest path remains Aspect 2 source of truth",
    )


def _check_scope(root: Path, baseline: dict[str, Any], report: dict[str, Any]) -> None:
    scope = baseline.get("format_scope")
    manual = baseline.get("manual_review_scope")
    protected = baseline.get("protected_exclusions")
    if (
        not isinstance(scope, list)
        or not isinstance(manual, list)
        or not isinstance(protected, list)
    ):
        _add(report, "baseline.scope.shape", False, "scope/manual/protected arrays are required")
        return
    forbidden_fragments = (
        ".env",
        "static/projects/",
        "node_modules/",
        "dist/",
        "src/assets/",
        "iteration-4-",
        "iteration5_baseline_manifest",
        "iteration5_version_migration",
        "HelloWorld.vue",
        "FounctionalTest.vue",
    )
    unsafe = [
        path
        for path in scope
        if any(fragment.casefold() in path.casefold() for fragment in forbidden_fragments)
    ]
    _add(report, "baseline.scope.protected", not unsafe, f"unsafe={unsafe}")
    _add(
        report,
        "baseline.scope.disjoint",
        not set(scope) & set(manual),
        "scope and manual review are disjoint",
    )
    for relative in scope:
        try:
            path = _safe_path(root, relative)
            ok = path.is_file()
        except ContractError as exc:
            _add(report, f"baseline.scope.{relative}", False, str(exc))
            continue
        _add(report, f"baseline.scope.{relative}", ok, "explicit file" if ok else "missing")

    files = baseline.get("files", {})
    moved_paths, post_hashes = _aspect4_path_evidence(root)
    aspect8_hashes = _aspect8_reviewed_hashes(root)
    _add(
        report,
        "baseline.files.shape",
        isinstance(files, dict) and set(files) == set(scope),
        f"expected={len(scope)} observed={len(files) if isinstance(files, dict) else 0}",
    )
    if isinstance(files, dict):
        for relative in scope:
            entry = files.get(relative, {})
            expected = entry.get("sha256") if isinstance(entry, dict) else None
            valid = isinstance(expected, str) and bool(SHA256_RE.fullmatch(expected))
            detail = "valid sha256"
            try:
                path = _safe_path(root, relative)
                evidence_path = moved_paths.get(relative, relative)
                if evidence_path != relative:
                    post_expected = post_hashes.get(evidence_path)
                    evidence_file = _safe_path(root, evidence_path)
                    observed = _normalized_sha256(evidence_file)
                    valid = (
                        isinstance(post_expected, str)
                        and observed.casefold() == post_expected.casefold()
                    )
                    if not valid and evidence_path in aspect8_hashes:
                        valid = observed.casefold() == aspect8_hashes[evidence_path].casefold()
                        detail = (
                            f"moved={evidence_path}; observed={observed}; Aspect 8 reviewed overlay"
                        )
                    detail = (
                        detail
                        if valid and evidence_path in aspect8_hashes
                        else f"moved={evidence_path}; observed={observed}; parent hash retained"
                    )
                elif relative in post_hashes:
                    observed = _normalized_sha256(path)
                    valid = observed.casefold() == post_hashes[relative].casefold()
                    if not valid and relative in aspect8_hashes:
                        valid = observed.casefold() == aspect8_hashes[relative].casefold()
                        detail = f"Aspect 8 reviewed overlay observed={observed}"
                    else:
                        detail = f"Aspect 4 post-change observed={observed}"
                elif valid:
                    observed = _normalized_sha256(path)
                    valid = observed.casefold() == expected.casefold()
                    detail = f"observed={observed}"
            except (ContractError, ValueError) as exc:
                valid = False
                detail = str(exc)
            _add(report, f"baseline.file_hash.{relative}", valid, detail)


def _check_baseline(
    root: Path, baseline: dict[str, Any], migration: dict[str, Any], report: dict[str, Any]
) -> None:
    _add(
        report,
        "baseline.schema",
        baseline.get("schema_version") == STYLE_SCHEMA,
        str(baseline.get("schema_version")),
    )
    _add(report, "baseline.aspect", baseline.get("aspect") == 3, str(baseline.get("aspect")))
    _add(
        report,
        "baseline.manual_reviewed",
        baseline.get("manual_reviewed") is True,
        str(baseline.get("manual_reviewed")),
    )
    _add(
        report,
        "baseline.auto_accept",
        baseline.get("auto_accept_current_values") is False,
        str(baseline.get("auto_accept_current_values")),
    )
    _add(
        report,
        "baseline.parent",
        isinstance(baseline.get("parent"), dict),
        "parent fixture recorded",
    )
    _add(
        report,
        "migration.schema",
        migration.get("schema_version") == MIGRATION_SCHEMA,
        str(migration.get("schema_version")),
    )
    _add(
        report,
        "migration.manual_reviewed",
        migration.get("manual_reviewed") is True,
        str(migration.get("manual_reviewed")),
    )
    _add(
        report,
        "migration.auto_accept",
        migration.get("auto_accept_current_values") is False,
        str(migration.get("auto_accept_current_values")),
    )
    parent = baseline.get("parent", {})
    if isinstance(parent, dict):
        try:
            parent_path = _safe_path(root, parent["fixture"])
            parent_hash = _normalized_sha256(parent_path)
            _add(
                report,
                "baseline.parent_hash",
                parent.get("fixture_sha256") == parent_hash,
                f"observed={parent_hash}",
            )
        except (KeyError, ContractError, ValueError) as exc:
            _add(report, "baseline.parent_hash", False, str(exc))
    migration_parent = migration.get("parent", {})
    migration_batches = migration.get("batches", [])
    _add(
        report,
        "migration.batches",
        isinstance(migration_batches, list)
        and len(migration_batches) >= 3
        and all(
            isinstance(batch, dict) and batch.get("manual_reviewed") is True
            for batch in migration_batches
        ),
        f"batches={len(migration_batches) if isinstance(migration_batches, list) else 0}",
    )
    if isinstance(migration_parent, dict):
        try:
            migration_path = _safe_path(root, migration_parent["fixture"])
            migration_hash = _normalized_sha256(migration_path)
            _add(
                report,
                "migration.parent_hash",
                migration_parent.get("fixture_sha256") == migration_hash,
                f"observed={migration_hash}",
            )
        except (KeyError, ContractError, ValueError) as exc:
            _add(report, "migration.parent_hash", False, str(exc))
    _check_scope(root, baseline, report)


def _check_hashes(root: Path, baseline: dict[str, Any], report: dict[str, Any]) -> None:
    protected = baseline.get("protected_hashes", {})
    if not isinstance(protected, dict) or not protected:
        _add(report, "baseline.protected_hashes", False, "protected hash map is required")
        return
    for relative, expected in protected.items():
        valid = isinstance(expected, str) and bool(SHA256_RE.fullmatch(expected))
        detail = "valid sha256"
        try:
            path = _safe_path(root, relative)
            moved_paths, post_hashes = _aspect4_path_evidence(root)
            evidence_path = moved_paths.get(relative, relative)
            evidence_expected = post_hashes.get(evidence_path)
            if not path.is_file():
                valid = False
                detail = "protected file is missing"
            elif valid:
                observed = _normalized_sha256(path)
                valid = observed.casefold() == (evidence_expected or expected).casefold()
                detail = f"observed={observed}"
        except (ContractError, ValueError) as exc:
            valid = False
            detail = str(exc)
        _add(report, f"protected_hash.{relative}", valid, detail)


def _symbol_present(text: str, symbol: str) -> bool:
    name = symbol.rsplit(".", 1)[-1]
    pattern = re.compile(
        rf"(?:class|def|function|const|async function)\s+{re.escape(name)}\b|\b{re.escape(name)}\b"
    )
    return any(
        CJK_RE.search(text[max(0, match.start() - 900) : match.end() + 900])
        for match in pattern.finditer(text)
    )


def _aspect4_path_evidence(root: Path) -> tuple[dict[str, str], dict[str, str]]:
    """Resolve Aspect 3 entries to reviewed Aspect 4 post-change evidence."""

    moved: dict[str, str] = {}
    post_hashes: dict[str, str] = {}
    try:
        architecture = _read_json(root, str(ARCHITECTURE_BASELINE))
        migration = _read_json(root, str(BACKEND_MIGRATION))
    except (ContractError, json.JSONDecodeError):
        return moved, post_hashes
    for old, target in architecture.get("module_map", {}).items():
        old_path = (Path("ez_back_dev") / Path(*old.split("."))).with_suffix(".py").as_posix()
        target_path = (Path("ez_back_dev") / Path(*target.split("."))).with_suffix(".py").as_posix()
        moved[old_path] = target_path
    for batch in migration.get("batches", []):
        if not isinstance(batch, dict):
            continue
        hashes = batch.get("post_change_sha256", {})
        if isinstance(hashes, dict):
            post_hashes.update(
                {
                    relative: value
                    for relative, value in hashes.items()
                    if isinstance(relative, str) and isinstance(value, str)
                }
            )
        source_paths = batch.get("source_paths", [])
        canonical_paths = batch.get("canonical_paths", [])
        if isinstance(source_paths, list) and isinstance(canonical_paths, list):
            same_paths = set(source_paths) & set(canonical_paths)
            for relative in same_paths:
                if isinstance(relative, str):
                    moved.setdefault(relative, relative)
    new_hashes = migration.get("new_path_post_change_sha256", {})
    if isinstance(new_hashes, dict):
        for relative, value in new_hashes.items():
            if isinstance(relative, str) and isinstance(value, str):
                moved.setdefault(relative, relative)
                post_hashes[relative] = value

    # Aspect 5 records moved source, test, and fixture paths without rewriting
    # the historical Aspect 3 baseline. Their reviewed post hashes are current
    # evidence for the old baseline entries.
    try:
        structure_migration = _read_json(root, str(ASPECT5_STRUCTURE_MIGRATION))
    except (ContractError, json.JSONDecodeError):
        structure_migration = {}
    for batch in (
        structure_migration.get("batches", []) if isinstance(structure_migration, dict) else []
    ):
        if not isinstance(batch, dict):
            continue
        for record in batch.get("paths", []):
            if not isinstance(record, dict):
                continue
            old = record.get("old_path")
            new = record.get("new_path")
            post = record.get("post_hash")
            if not all(isinstance(value, str) for value in (old, new, post)):
                continue
            old = old.replace("\\", "/")
            new = new.replace("\\", "/")
            moved[old] = new
            post_hashes[new] = post
    return moved, post_hashes


def _aspect8_reviewed_hashes(root: Path) -> dict[str, str]:
    """Read only the explicit normalized hashes approved by Aspect 8."""

    try:
        contract = _read_json(root, str(ASPECT8_CONTRACT))
    except (ContractError, OSError, UnicodeError, ValueError):
        return {}
    overlay = contract.get("cumulative_overlay") if isinstance(contract, dict) else None
    allowed = overlay.get("allowed_paths") if isinstance(overlay, dict) else None
    if not isinstance(overlay, dict) or overlay.get("manual_reviewed") is not True:
        return {}
    result: dict[str, str] = {}
    for path, evidence in allowed.items() if isinstance(allowed, dict) else []:
        if not isinstance(path, str) or not isinstance(evidence, dict):
            continue
        value = evidence.get("normalized_sha256")
        if (
            isinstance(value, str)
            and re.fullmatch(r"[0-9a-f]{64}", value, re.IGNORECASE)
            and evidence.get("manual_review") is True
        ):
            result[path.replace("\\", "/")] = value
    return result


def _check_comments(
    root: Path,
    baseline: dict[str, Any],
    report: dict[str, Any],
) -> None:
    entries = baseline.get("comment_coverage", [])
    registered = {item.get("symbol") for item in entries if isinstance(item, dict)}
    _add(
        report,
        "comments.registry",
        set(REQUIRED_COMMENT_SYMBOLS) <= registered,
        f"required={len(REQUIRED_COMMENT_SYMBOLS)} registered={len(registered)}",
    )
    for item in entries:
        if not isinstance(item, dict):
            continue
        relative = item.get("path")
        symbol = item.get("symbol")
        if not isinstance(relative, str) or not isinstance(symbol, str):
            _add(report, "comments.entry", False, "path and symbol are required")
            continue
        try:
            moved_paths, _post_hashes = _aspect4_path_evidence(root)
            text = _read_text(root, moved_paths.get(relative, relative))
            ok = _symbol_present(text, symbol)
        except ContractError as exc:
            ok = False
            text = str(exc)
        _add(report, f"comments.{symbol}", ok, "CJK explanation anchor present" if ok else text)


def _check_suppressions(root: Path, baseline: dict[str, Any], report: dict[str, Any]) -> None:
    allowed = baseline.get("suppressions", {}).get("allowed", [])
    observed: list[dict[str, str]] = []
    for relative in baseline.get("format_scope", []):
        if relative == "scripts/check_style_contract.py":
            continue
        try:
            text = _read_text(root, relative)
        except ContractError:
            continue
        if SUPPRESSION_RE.search(text):
            observed.append({"path": relative, "token": "registered suppression"})
    allowed_pairs = {
        (item.get("path"), item.get("token")) for item in allowed if isinstance(item, dict)
    }
    unexpected = [item for item in observed if (item["path"], item["token"]) not in allowed_pairs]
    _add(report, "format.suppressions", not unexpected, f"unexpected={unexpected}")


def _check_line_endings(root: Path, baseline: dict[str, Any], report: dict[str, Any]) -> None:
    bad: list[str] = []
    for relative in baseline.get("format_scope", []):
        try:
            payload = _read_bytes(root, relative)
        except ContractError:
            continue
        if b"\r\n" in payload or b"\r" in payload or not payload.endswith(b"\n"):
            bad.append(relative)
    _add(report, "format.line_endings", not bad, f"non-LF-or-final-newline={bad}")


def _check_ci(root: Path, report: dict[str, Any]) -> None:
    try:
        text = _read_text(root, ".github/workflows/iteration4-offline.yml")
    except ContractError as exc:
        _add(report, "ci.style_gates", False, str(exc))
        return
    required = (
        "python scripts/check_style_contract.py --check --format text",
        "ruff check",
        "ruff format --check",
        "npm run format:check",
    )
    missing = [item for item in required if item not in text]
    forbidden_tokens = ("ruff format -" + "-write", "prettier -" + "-write")
    forbidden = [item for item in forbidden_tokens if item in text]
    _add(
        report,
        "ci.style_gates",
        not missing and not forbidden,
        f"missing={missing}; forbidden={forbidden}",
    )


def check_style_contract(root: Path) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema_version": STYLE_SCHEMA,
        "status": "pass",
        "checks": [],
        "errors": [],
    }
    try:
        safe_root = _safe_root(root)
        contract = _read_json(safe_root, str(VERSION_CONTRACT))
        baseline = _read_json(safe_root, str(STYLE_BASELINE))
        migration = _read_json(safe_root, str(STYLE_MIGRATION))
    except (ContractError, json.JSONDecodeError) as exc:
        report["status"] = "fail"
        report["errors"].append({"id": "inputs", "status": "fail", "detail": str(exc)})
        return report

    _check_required_files(safe_root, report)
    _check_quality_contract(safe_root, contract, report)
    _check_format_configs(safe_root, report)
    _check_frontend_manifest(safe_root, contract, report)
    _check_baseline(safe_root, baseline, migration, report)
    _check_hashes(safe_root, baseline, report)
    _check_comments(safe_root, baseline, report)
    _check_suppressions(safe_root, baseline, report)
    _check_line_endings(safe_root, baseline, report)
    _check_ci(safe_root, report)
    report["status"] = "pass" if not report["errors"] else "fail"
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate the repository contract")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.check:
        print("--check is required", file=sys.stderr)
        return 2
    try:
        report = check_style_contract(args.repo_root)
    except (ContractError, OSError, ValueError) as exc:
        print(f"style contract input error: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"style-contract: {report['status']}")
        for item in report["errors"]:
            print(f"FAIL {item['id']}: {item['detail']}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
