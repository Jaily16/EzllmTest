"""Read-only asset inventory and dry-run safety primitives for Iteration 5.

This module intentionally has no deletion API.  It can enumerate Git-visible
paths, classify them, collect bounded textual reference evidence, and emit a
deterministic dry-run report.  Real ``.env`` files, uploaded projects, and
service data are metadata-only boundaries and are never opened or hashed.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import stat
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence


SCHEMA_VERSION = "iteration5-asset-inventory-v1"
DRY_RUN_SCHEMA_VERSION = "iteration5-cleanup-dry-run-v1"
HASH_POLICY = "sha256_canonical_lf_v1"

CLASSIFICATIONS = (
    "Protected user data",
    "Protected product asset",
    "Historical evidence",
    "Generated disposable",
    "Duplicate candidate",
    "Legacy candidate",
    "Unknown",
)

PROTECTED_USER_PREFIXES = (
    "example",
    "ez_back_dev/static/projects",
)
PROTECTED_USER_FILENAMES = {".env"}
PROTECTED_USER_DIRNAMES = {".idea", ".vscode"}

HISTORICAL_PREFIXES = (
    "docs/iteration-1-",
    "docs/iteration-2-",
    "docs/iteration-3-",
    "docs/iteration-4-",
    "docs/history/iteration-1/",
    "docs/history/iteration-2/",
    "docs/history/iteration-3/",
    "docs/history/iteration-4/",
    "docs/history/iteration-development-log.md",
    "docs/superpowers/plans/",
    "ez_back_dev/tests/fixtures/iteration3_",
    "ez_back_dev/tests/fixtures/iteration4_",
    "ez_back_dev/tests/test_iteration4_",
)

GENERATED_DIRNAMES = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    "dist",
    "coverage",
    "htmlcov",
}
GENERATED_FILENAMES = {".coverage"}
GENERATED_SUFFIXES = {".pyc", ".pyo"}

DUPLICATE_ASSET_NAMES = {
    "ezlogo-workbench.png",
    "ezlogo.png",
    "logo.png",
    "uitest.png",
    "acceptancetest.png",
    "apitest.png",
    "databasetest.png",
    "functionaltest.png",
    "integrationtest.png",
    "nonfunctionaltest.png",
    "testplan.png",
    "unittest.png",
}

LEGACY_BASENAMES = {
    "helloworld.vue",
    "homeview.vue",
    "founctionaltest.vue",
    "legacylongtextservice.py",
}

SAFE_TEXT_SUFFIXES = {
    ".c",
    ".cfg",
    ".css",
    ".dockerfile",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".py",
    ".sql",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".vue",
    ".yml",
    ".yaml",
}

REQUIRED_HASH_PATHS = (
    "README.md",
    ".env.example",
    "ez_front_dev/.env.example",
    "ops/compose/.env.example",
    "ez_back_dev/requirements.txt",
    "ez_front_dev/package.json",
    "ez_front_dev/package-lock.json",
    "ez_back_dev/Dockerfile",
    "ez_front_dev/Dockerfile",
    "compose.yaml",
    ".github/workflows/iteration4-offline.yml",
    "ezllmtest.sql",
    "ez_back_dev/serve.py",
    "ez_back_dev/app/main.py",
    "ez_back_dev/app/routers.py",
    "ez_back_dev/app/agentApi.py",
    "ez_back_dev/app/agentWorker.py",
    "ez_back_dev/app/mcpServer.py",
    "ez_back_dev/app/agentEval.py",
    "ez_back_dev/app/agentAcceptance.py",
    "ez_back_dev/app/agentBenchmark.py",
    "ez_front_dev/src/main.ts",
    "ez_front_dev/src/app/router/index.ts",
    "ez_front_dev/src/features/agent/state/agentWorkbench.ts",
    "ez_front_dev/src/features/agent/composables/useAgentEvents.ts",
    "ez_front_dev/src/features/agent/AgentWorkbench.vue",
    "ez_front_dev/src/features/testing/config/testWorkspaces.ts",
    "ez_front_dev/src/shared/config/models.ts",
    "ez_back_dev/service/workflowCatalog.py",
    "ez_back_dev/service/workflowBudget.py",
    "ez_back_dev/service/agentToolSchemas.py",
    "ez_back_dev/service/agentToolRegistry.py",
    "ez_back_dev/service/agentContracts.py",
    "ez_back_dev/service/agentRuntimeContracts.py",
    "ez_back_dev/service/agentWorkbenchContracts.py",
    "ez_back_dev/service/agentMcpAdapter.py",
    "ez_back_dev/service/agentContext.py",
    "ez_back_dev/service/agentRetrieval.py",
    "ez_back_dev/service/agentCheckpoint.py",
    "ez_back_dev/service/agentRedisCoordinator.py",
    "ez_back_dev/service/agentGraph.py",
    "ez_back_dev/service/agentRuntimeService.py",
    "ez_back_dev/service/agentRuntimeFactory.py",
    "ez_back_dev/service/agentToolExecutor.py",
    "ez_back_dev/service/agentTelemetry.py",
    "ez_back_dev/service/projectRevisionService.py",
    "ez_back_dev/service/projectSetupService.py",
    "ez_back_dev/service/projectWorkflowStatusService.py",
    "ez_back_dev/service/workflowArtifactService.py",
    "ez_back_dev/service/llmWorkflowStreamCore.py",
    "ez_back_dev/dao/workflowArtifactDao.py",
    "ez_back_dev/model/TestProject.py",
    "ez_back_dev/tools/InfoType.py",
    "ez_back_dev/llm/provider.py",
    "ez_back_dev/llm/streaming.py",
    "scripts/scan_credentials.py",
    "scripts/check_frontend_bundle.py",
    "scripts/frontend_fixture_server.py",
    "ez_back_dev/tests/fixtures/historical/iteration3/iteration3_contract_baseline_v1.json",
    "ez_back_dev/tests/fixtures/historical/iteration4/iteration4_release_manifest_v1.json",
    "docs/iteration-4-overview.md",
    "docs/iteration-4-closeout.md",
    "docs/iteration-4-prompts.md",
    "docs/iteration-4-live-model-acceptance.md",
    "docs/iteration-4-development-log.md",
    # Existing Iteration 5 planning assets are user-owned inputs to this
    # baseline. They are hashed as ordinary files, never auto-accepted as
    # cleanup candidates.
    "docs/iteration-5-overview.md",
    "docs/iteration-5-prompts.md",
    "ez_back_dev/tests/contract/iteration5/test_iteration5_planning_contracts.py",
    "ez_back_dev/tests/historical/iteration4/test_iteration4_release_contracts.py",
)

# These are explicit compatibility names retained as redirect stubs after the
# Aspect 5 document move.  Inventory and baseline hashing must inspect the
# canonical document, not hash the stub merely because the old name remains
# present for link compatibility.
DOCUMENT_CANONICAL_PREFIXES = (
    ("docs/iteration-1-", "docs/history/iteration-1/iteration-1-"),
    ("docs/iteration-2-", "docs/history/iteration-2/iteration-2-"),
    ("docs/iteration-3-", "docs/history/iteration-3/iteration-3-"),
    ("docs/iteration-4-", "docs/history/iteration-4/iteration-4-"),
)
DOCUMENT_CANONICAL_PATHS = {
    "docs/iteration-5-overview.md": "docs/development/iteration-5/overview.md",
    "docs/iteration-5-baseline.md": "docs/development/iteration-5/baseline.md",
    "docs/iteration-5-asset-inventory.md": "docs/development/iteration-5/asset-inventory.md",
    "docs/iteration-5-development-log.md": "docs/development/iteration-5/development-log.md",
    "docs/iteration-5-prompts.md": "docs/development/iteration-5/prompts.md",
    "docs/iteration-5-style-guide.md": "docs/development/iteration-5/style-guide.md",
    "docs/iteration-development-log.md": "docs/history/iteration-development-log.md",
    "docs/long-text-strategy-audit.md": "docs/architecture/long-text-strategy-audit.md",
}



def normalize_relative(value: str | Path) -> str:
    """Return a stable repository-relative path representation."""

    text = str(value).replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text.strip("/")


def canonical_inventory_relative(relative: str | Path) -> str:
    """Resolve an explicitly mapped legacy document name for read-only hashing."""

    normalized = normalize_relative(relative)
    exact = DOCUMENT_CANONICAL_PATHS.get(normalized)
    if exact is not None:
        return exact
    for old_prefix, new_prefix in DOCUMENT_CANONICAL_PREFIXES:
        if normalized.startswith(old_prefix):
            return new_prefix + normalized[len(old_prefix) :]
    return normalized


def _parts(relative: str | Path) -> tuple[str, ...]:
    return PurePosixPath(normalize_relative(relative)).parts


def is_protected_user_data(relative: str | Path) -> bool:
    """Detect paths whose content, size, and hash must not be inspected."""

    normalized = normalize_relative(relative)
    parts = _parts(normalized)
    if not parts:
        return False
    if any(
        normalized == prefix or normalized.startswith(f"{prefix}/")
        for prefix in PROTECTED_USER_PREFIXES
    ):
        return True
    if any(part in PROTECTED_USER_DIRNAMES for part in parts):
        return True
    for part in parts:
        if part in PROTECTED_USER_FILENAMES:
            return True
        if part.startswith(".env.") and part != ".env.example":
            return True
    return False


def protected_status_boundary(relative: str | Path) -> str | None:
    """Collapse protected Git paths to a metadata-only boundary label.

    Git status can enumerate every child of an ignored directory.  The
    inventory must not echo those child names for user-owned projects or IDE
    state, so status output is reduced to the smallest safe boundary.
    """

    normalized = normalize_relative(relative)
    for prefix in PROTECTED_USER_PREFIXES:
        if normalized == prefix or normalized.startswith(f"{prefix}/"):
            return f"{prefix}/"
    parts = _parts(normalized)
    for index, part in enumerate(parts):
        if part in PROTECTED_USER_DIRNAMES:
            return "/".join(parts[: index + 1]) + "/"
    for index, part in enumerate(parts):
        if part == ".env":
            return "/".join(parts[: index + 1])
        if part.startswith(".env.") and part != ".env.example":
            return "/".join(parts[:index] + (".env",))
    return None


def redact_protected_statuses(records: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
    """Keep protected status existence while suppressing child path names."""

    redacted: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for record in records:
        boundary = protected_status_boundary(record["path"])
        if boundary is None:
            redacted.append(dict(record))
            continue
        key = (record["scope"], boundary)
        if key in seen:
            continue
        seen.add(key)
        redacted.append(
            {
                "status": record["status"],
                "path": boundary,
                "scope": record["scope"],
                "protection": "metadata_only_no_child_paths",
            }
        )
    return redacted


def is_historical_evidence(relative: str | Path) -> bool:
    normalized = normalize_relative(relative)
    return normalized.startswith(HISTORICAL_PREFIXES)


def is_generated_disposable(relative: str | Path) -> bool:
    normalized = normalize_relative(relative)
    path = PurePosixPath(normalized)
    if any(part in GENERATED_DIRNAMES for part in path.parts):
        return True
    if path.name in GENERATED_FILENAMES:
        return True
    return path.suffix.lower() in GENERATED_SUFFIXES


def classify_path(
    relative: str | Path,
    *,
    tracked: bool = True,
    ignored: bool = False,
) -> str:
    """Classify without reading the path's contents."""

    normalized = normalize_relative(relative)
    name = PurePosixPath(normalized).name.lower()

    if is_protected_user_data(normalized):
        return "Protected user data"
    if is_historical_evidence(normalized):
        return "Historical evidence"
    if is_generated_disposable(normalized):
        return "Generated disposable"
    if name in DUPLICATE_ASSET_NAMES:
        return "Duplicate candidate"
    if name in LEGACY_BASENAMES or normalized.startswith("ez_back_dev/test/"):
        return "Legacy candidate"
    if not tracked and not ignored:
        return "Unknown"
    return "Protected product asset"


def proposed_action(classification: str) -> str:
    return {
        "Protected user data": "retain_and_protect",
        "Protected product asset": "retain",
        "Historical evidence": "retain_and_hash",
        "Generated disposable": "candidate_allowlist",
        "Duplicate candidate": "retain_until_reference_audit",
        "Legacy candidate": "retain_until_reference_audit",
        "Unknown": "retain_and_report",
    }[classification]


def recovery_method(classification: str) -> str:
    return {
        "Protected user data": "No operation performed; protect the original user-owned location.",
        "Protected product asset": "Restore from the preserved worktree or the reviewed patch; do not reset the worktree.",
        "Historical evidence": "Restore from Git/history using the recorded evidence hash and link mapping.",
        "Generated disposable": "Regenerate from the existing source, lockfile, or deterministic fixture; quarantine before removal.",
        "Duplicate candidate": "Keep the original until the reference map and rollback mapping are complete.",
        "Legacy candidate": "Keep the original until a compatibility shim or explicit migration mapping is verified.",
        "Unknown": "No operation; retain and request owner/evidence clarification.",
    }[classification]


def _canonical_text_bytes(path: Path) -> bytes:
    payload = path.read_bytes()
    if payload.startswith(b"\xef\xbb\xbf"):
        payload = payload[3:]
    text = payload.decode("utf-8")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.rstrip("\n") + "\n"
    return text.encode("utf-8")


def normalized_bytes(path: Path) -> bytes:
    """Return the Aspect 1 canonical hash payload."""

    if path.suffix.lower() == ".json":
        payload = path.read_bytes()
        if payload.startswith(b"\xef\xbb\xbf"):
            payload = payload[3:]
        value = json.loads(payload.decode("utf-8"))
        return (
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            + b"\n"
        )
    return _canonical_text_bytes(path)


def normalized_sha256(path: Path) -> str:
    return hashlib.sha256(normalized_bytes(path)).hexdigest()


def _is_reparse_point(path: Path) -> bool:
    if path.is_symlink():
        return True
    if os.name != "nt":
        return False
    try:
        attributes = os.stat(path, follow_symlinks=False).st_file_attributes
    except (AttributeError, FileNotFoundError, OSError):
        return False
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & reparse)


def validate_candidate_path(
    repo_root: Path,
    candidate: str | Path,
    *,
    approved_roots: Sequence[str | Path],
) -> dict[str, Any]:
    """Validate a candidate without opening it or deleting it."""

    root = repo_root.resolve(strict=True)
    raw = Path(candidate)
    absolute = raw if raw.is_absolute() else root / raw
    unresolved = absolute
    probe = unresolved
    while probe != root and probe != probe.parent:
        if _is_reparse_point(probe):
            return {"allowed": False, "reason": "symlink_or_reparse_point"}
        probe = probe.parent
    resolved = absolute.resolve(strict=False)
    normalized = normalize_relative(resolved.relative_to(root)) if resolved != root and resolved.is_relative_to(root) else None

    if resolved == root:
        return {"allowed": False, "reason": "repository_root_is_never_a_candidate"}
    if not resolved.is_relative_to(root):
        return {"allowed": False, "reason": "path_escapes_repository_root"}
    if normalized is None or is_protected_user_data(normalized):
        return {"allowed": False, "reason": "protected_path"}

    approved = []
    for item in approved_roots:
        approved_path = (root / item).resolve(strict=False)
        if resolved != approved_path and resolved.is_relative_to(approved_path):
            approved.append(normalize_relative(approved_path.relative_to(root)))
    if not approved:
        return {"allowed": False, "reason": "outside_approved_root"}

    current = resolved
    while current != root and current != current.parent:
        if _is_reparse_point(current):
            return {"allowed": False, "reason": "symlink_or_reparse_point"}
        current = current.parent

    if resolved == root:
        return {"allowed": False, "reason": "repository_root_is_never_a_candidate"}
    return {
        "allowed": True,
        "relative_path": normalized,
        "resolved_path": str(resolved),
        "approved_roots": sorted(approved),
    }


def _run_git(root: Path, *arguments: str) -> bytes:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout


def _run_git_text(root: Path, *arguments: str) -> str:
    return _run_git(root, *arguments).decode("utf-8", errors="replace").strip()


def _parse_porcelain_z(payload: bytes) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for token in payload.split(b"\0"):
        if len(token) < 4:
            continue
        decoded = os.fsdecode(token)
        status = decoded[:2]
        path = normalize_relative(decoded[3:])
        if not path:
            continue
        scope = (
            "ignored"
            if status == "!!"
            else "untracked"
            if status == "??"
            else "tracked"
        )
        records.append({"status": status, "path": path, "scope": scope})
    return records


def git_status_records(root: Path, *, matching: bool = False) -> list[dict[str, str]]:
    ignored_mode = "matching" if matching else "traditional"
    payload = _run_git(
        root,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
        f"--ignored={ignored_mode}",
    )
    return _parse_porcelain_z(payload)


def git_snapshot(root: Path) -> dict[str, Any]:
    """Collect Git metadata; no network or worktree mutation is used."""

    all_status = git_status_records(root, matching=False)
    matching_status = git_status_records(root, matching=True)
    safe_all_status = redact_protected_statuses(all_status)
    safe_matching_status = redact_protected_statuses(matching_status)
    ahead_behind = _run_git_text(root, "rev-list", "--left-right", "--count", "HEAD...origin/main")
    return {
        "branch": _run_git_text(root, "branch", "--show-current"),
        "head": _run_git_text(root, "rev-parse", "HEAD"),
        "origin_main": _run_git_text(root, "rev-parse", "--verify", "origin/main"),
        "ahead_behind": ahead_behind.split(),
        "status": safe_all_status,
        "status_matching": safe_matching_status,
        "diff_stat": _run_git_text(root, "diff", "--stat"),
        "diff_name_status": _run_git_text(root, "diff", "--name-status").splitlines(),
        "cached_name_status": _run_git_text(root, "diff", "--cached", "--name-status").splitlines(),
        "ignored_full_count": sum(item["scope"] == "ignored" for item in all_status),
    }


def tracked_paths(root: Path) -> list[str]:
    payload = _run_git(root, "ls-files", "-z")
    return sorted(normalize_relative(os.fsdecode(item)) for item in payload.split(b"\0") if item)


def _safe_text_paths(root: Path) -> Iterable[Path]:
    excluded_dirs = {
        ".git",
        "node_modules",
        "dist",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "example",
        "projects",
    }
    for current, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        current_relative = normalize_relative(current_path.relative_to(root))
        dirnames[:] = [
            directory
            for directory in dirnames
            if directory not in excluded_dirs
            and not is_protected_user_data(
                normalize_relative(Path(current_relative) / directory)
            )
        ]
        for filename in filenames:
            path = current_path / filename
            relative = normalize_relative(path.relative_to(root))
            if is_protected_user_data(relative):
                continue
            if _is_reparse_point(path):
                continue
            if path.suffix.lower() not in SAFE_TEXT_SUFFIXES and path.name not in {"Dockerfile", ".gitignore"}:
                continue
            yield path


def _reference_channel(source: str) -> str:
    normalized = normalize_relative(source)
    if "/tests/" in f"/{normalized}" or "/test/" in f"/{normalized}":
        return "test_or_fixture"
    if normalized.endswith(".py"):
        return "python_import_or_runtime"
    if normalized.endswith((".vue", ".ts", ".tsx", ".css")):
        return "vue_router_template_css"
    if normalized.startswith("docs/") or normalized.endswith(".md"):
        return "documentation"
    if normalized.startswith(".github/") or normalized in {"compose.yaml", "Dockerfile"} or normalized.endswith("Dockerfile"):
        return "docker_ci"
    if normalized.startswith("scripts/"):
        return "script_cli"
    return "source_text"


def _python_tokens(text: str) -> set[str]:
    tokens: set[str] = set()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return tokens
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            tokens.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            tokens.add(node.module)
        elif isinstance(node, ast.Call) and node.args:
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                tokens.add(first.value)
    return tokens


def _reference_documents(root: Path) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for source_path in _safe_text_paths(root):
        source = normalize_relative(source_path.relative_to(root))
        try:
            text = source_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        documents.append(
            {
                "source": source,
                "text": text,
                "channel": _reference_channel(source),
                "python_tokens": _python_tokens(text) if source.endswith(".py") else set(),
            }
        )
    return documents


def find_references(
    root: Path,
    target: str | Path,
    *,
    documents: Sequence[Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Collect bounded, non-executing evidence for a candidate path."""

    normalized = normalize_relative(target)
    basename = PurePosixPath(normalized).name
    dotted = normalized[:-3].replace("/", ".") if normalized.endswith(".py") else ""
    evidence: list[dict[str, Any]] = []
    for document in documents if documents is not None else _reference_documents(root):
        source = str(document["source"])
        if source == normalized:
            continue
        text = str(document["text"])
        matched: list[str] = []
        if normalized in text:
            matched.append(normalized)
        if basename and basename in text:
            matched.append(basename)
        if dotted and dotted in document["python_tokens"]:
            matched.append(dotted)
        if matched:
            evidence.append(
                {
                    "source": source,
                    "channel": document["channel"],
                    "tokens": sorted(set(matched)),
                }
            )
    return sorted(evidence, key=lambda item: (item["channel"], item["source"]))


def _status_for_path(path: str, statuses: Mapping[str, dict[str, str]]) -> dict[str, str]:
    return statuses.get(path, {"status": "  ", "path": path, "scope": "tracked"})


def build_asset_record(
    root: Path,
    relative: str,
    *,
    status: Mapping[str, str],
    hash_paths: set[str] | None = None,
    reference: bool = False,
    reference_documents: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    normalized = normalize_relative(relative)
    scope = status.get("scope", "tracked")
    tracked = scope == "tracked"
    ignored = scope == "ignored"
    classification = classify_path(normalized, tracked=tracked, ignored=ignored)
    path = root / Path(*_parts(normalized))
    protected = classification == "Protected user data"
    exists = path.exists() if not protected else path.exists()

    record: dict[str, Any] = {
        "asset_id": f"{scope}:{normalized}",
        "scope": scope,
        "path_or_resource": normalized,
        "exists": "present" if exists else "missing",
        "git_status": status.get("status", "  "),
        "classification": classification,
        "source": ["git_status" if scope != "tracked" else "git_tracked"],
        "size_bytes": None,
        "sha256": None,
        "reference_evidence": [],
        "proposed_action": proposed_action(classification),
        "recovery": recovery_method(classification),
        "review_state": "unreviewed",
    }

    if protected:
        record["protection"] = "existence_only_no_read_no_size_no_hash"
        return record

    if exists and path.is_file() and classification in {
        "Protected product asset",
        "Historical evidence",
        "Generated disposable",
        "Duplicate candidate",
        "Legacy candidate",
    }:
        if hash_paths is None or normalized in hash_paths:
            record["size_bytes"] = path.stat().st_size
            try:
                record["sha256"] = normalized_sha256(path)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                record["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()

    if reference and exists and not path.is_dir():
        record["reference_evidence"] = find_references(
            root, normalized, documents=reference_documents
        )
    return record


def build_inventory(root: Path) -> dict[str, Any]:
    root = root.resolve(strict=True)
    snapshot = git_snapshot(root)
    statuses: dict[str, dict[str, str]] = {}
    for item in snapshot["status_matching"]:
        statuses.setdefault(item["path"], item)

    tracked = set(tracked_paths(root))
    paths = set(tracked)
    paths.update(item["path"] for item in snapshot["status_matching"])
    key_paths = set(REQUIRED_HASH_PATHS)
    reference_documents = _reference_documents(root)
    candidate_paths = {
        path
        for path in paths
        if classify_path(path, tracked=path in tracked, ignored=statuses.get(path, {}).get("scope") == "ignored")
        in {"Duplicate candidate", "Legacy candidate"}
    }
    assets = [
        build_asset_record(
            root,
            path,
            status=_status_for_path(path, statuses),
            hash_paths=key_paths,
            reference=path in candidate_paths,
            reference_documents=reference_documents,
        )
        for path in sorted(paths)
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "hash_policy": HASH_POLICY,
        "mode": "read_only_inventory_and_dry_run",
        "repo_root": str(root),
        "git": snapshot,
        "protected_boundaries": {
            "paths": [
                ".env",
                "ez_front_dev/.env",
                "example/",
                "ez_back_dev/static/projects/",
                "declared_compose_volumes",
                "external_mysql_redis_observability_data",
                "global_system_temp",
            ],
            "policy": "existence_or_declaration_only; no content, size, or hash",
        },
        "assets": assets,
        "generated_candidate_policy": {
            "schema_version": DRY_RUN_SCHEMA_VERSION,
            "default_action": "report_only",
            "apply_requires_manual_allowlist": True,
            "allowed_matching": "enumerate_actual_paths_then_review_exact_paths",
            "candidate_kinds": [
                "__pycache__",
                ".pyc",
                ".pytest_cache",
                "coverage",
                "dist",
                "logs",
                "benchmark",
                "trace",
                "screenshot",
                "node_modules",
            ],
            "protected_prefixes": list(PROTECTED_USER_PREFIXES),
        },
        "reference_channels": [
            "python_import_or_runtime",
            "vue_router_template_css",
            "test_or_fixture",
            "documentation",
            "docker_ci",
            "script_cli",
            "source_text",
        ],
    }


def build_hash_manifest(root: Path, paths: Sequence[str] = REQUIRED_HASH_PATHS) -> dict[str, Any]:
    root = root.resolve(strict=True)
    files: dict[str, Any] = {}
    missing: list[str] = []
    for relative in paths:
        normalized = normalize_relative(relative)
        if is_protected_user_data(normalized):
            files[normalized] = {
                "classification": "Protected user data",
                "size_bytes": None,
                "sha256": None,
                "policy": "not_read",
            }
            continue
        resolved = canonical_inventory_relative(normalized)
        path = root / Path(*_parts(resolved))
        if not path.is_file():
            missing.append(normalized)
            continue
        files[normalized] = {
            "classification": classify_path(normalized),
            "resolved_path": resolved,
            "size_bytes": path.stat().st_size,
            "sha256": normalized_sha256(path),
            "policy": HASH_POLICY,
        }
    return {
        "schema_version": "iteration5-baseline-manifest-v1",
        "hash_policy": HASH_POLICY,
        "files": files,
        "missing": missing,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="emit a read-only JSON report; this is the only supported mode",
    )
    args = parser.parse_args(argv)
    if not args.dry_run:
        parser.error("Aspect 1 inventory requires explicit --dry-run; no apply mode exists")
    report = build_inventory(args.repo_root)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
