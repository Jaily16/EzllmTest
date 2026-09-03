"""Read-only boundary checker for the Aspect 4 backend migration."""

from __future__ import annotations

import argparse
import ast
from functools import lru_cache
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


FIXTURE = Path(
    "ez_back_dev/tests/fixtures/current/iteration5/"
    "iteration5_backend_architecture_baseline_v1.json"
)
MIGRATION = Path(
    "ez_back_dev/tests/fixtures/current/iteration5/iteration5_backend_migration_v1.json"
)
ASPECT5_STRUCTURE_MIGRATION = Path(
    "ez_back_dev/tests/fixtures/current/iteration5/"
    "iteration5_frontend_structure_migration_v1.json"
)
ASPECT8_CONTRACT = Path("ops/iteration5-dual-mode-acceptance-contract.json")
SCHEMA = "iteration5-backend-architecture-v1"
MIGRATION_SCHEMA = "iteration5-backend-migration-v1"
BACKEND_ROOT = Path("ez_back_dev")


class BoundaryError(ValueError):
    """Raised for an unsafe repository or malformed migration input."""


@lru_cache(maxsize=8)
def _aspect5_relocations(root: str) -> dict[str, str]:
    """Read only the reviewed Aspect 5 path map used by historical checks."""
    repository = Path(root)
    mapping: dict[str, str] = {
        "ez_back_dev/tests/fixtures/iteration3_contract_baseline_v1.json":
            "ez_back_dev/tests/fixtures/historical/iteration3/iteration3_contract_baseline_v1.json",
        "ez_back_dev/tests/fixtures/iteration4_release_manifest_v1.json":
            "ez_back_dev/tests/fixtures/historical/iteration4/iteration4_release_manifest_v1.json",
    }
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
        mapping.setdefault(
            f"ez_back_dev/tests/fixtures/{name}",
            f"ez_back_dev/tests/fixtures/historical/iteration4/{name}",
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
        mapping.setdefault(
            f"ez_back_dev/tests/fixtures/{name}",
            f"ez_back_dev/tests/fixtures/current/iteration5/{name}",
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
    mapping = _aspect5_relocations(str(root.resolve()))
    seen: set[str] = set()
    while normalized in mapping and normalized not in seen:
        seen.add(normalized)
        normalized = mapping[normalized]
    return normalized


@lru_cache(maxsize=8)
def _aspect5_post_hashes(root: str) -> dict[str, str]:
    """Return reviewed Aspect 5 post hashes for paths changed in this aspect."""
    repository = Path(root)
    migration_path = repository / ASPECT5_STRUCTURE_MIGRATION
    try:
        migration = json.loads(migration_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    post_hashes: dict[str, str] = {}
    for batch in migration.get("batches", []) if isinstance(migration, dict) else []:
        if not isinstance(batch, dict):
            continue
        for record in batch.get("paths", []):
            if not isinstance(record, dict):
                continue
            new = record.get("new_path")
            post = record.get("post_hash")
            if isinstance(new, str) and isinstance(post, str):
                post_hashes[new.replace("\\", "/")] = post
    return post_hashes


@lru_cache(maxsize=8)
def _aspect8_post_hashes(root: str) -> dict[str, str]:
    """Return only manually reviewed Aspect 8 canonical hashes."""

    repository = Path(root)
    try:
        contract = json.loads((repository / ASPECT8_CONTRACT).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    overlay = contract.get("cumulative_overlay") if isinstance(contract, dict) else None
    allowed = overlay.get("allowed_paths") if isinstance(overlay, dict) else None
    if not isinstance(overlay, dict) or overlay.get("manual_reviewed") is not True:
        return {}
    result: dict[str, str] = {}
    for path, evidence in allowed.items() if isinstance(allowed, dict) else []:
        if not isinstance(path, str) or not isinstance(evidence, dict):
            continue
        value = evidence.get("backend_sha256")
        if (
            isinstance(value, str)
            and re.fullmatch(r"[0-9a-f]{64}", value, re.IGNORECASE)
            and evidence.get("manual_review") is True
        ):
            result[path.replace("\\", "/")] = value.lower()
    return result


def _reviewed_post_hash(root: Path, relative: str, fallback: str) -> str:
    """Use Aspect 5 evidence only for an explicitly recorded relocated path."""
    normalized = relative.replace("\\", "/")
    target = _relocated_relative(root, normalized)
    return _aspect8_post_hashes(str(root.resolve())).get(
        target,
        _aspect5_post_hashes(str(root.resolve())).get(target, fallback),
    )


def _safe_path(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative:
        raise BoundaryError("relative path required")
    root = root.resolve()
    candidate = (root / _relocated_relative(root, relative)).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise BoundaryError(f"path escapes repository root: {relative}") from exc
    parts = {part.casefold() for part in Path(relative).parts}
    if ".env" in parts or any(part.startswith(".env.") and part != ".env.example" for part in parts):
        raise BoundaryError(f"refusing to inspect a real environment file: {relative}")
    if any(part.casefold() in {"example", "static", "uploads", "upload", "volumes", "volume"} for part in Path(relative).parts):
        if relative not in {"ez_back_dev/tests/fixtures/iteration3_contract_baseline_v1.json", "ez_back_dev/tests/fixtures/iteration4_release_manifest_v1.json"}:
            raise BoundaryError(f"protected data path is outside the checker scope: {relative}")
    return candidate


def _read_json(root: Path, relative: str) -> dict[str, Any]:
    value = json.loads(_safe_path(root, relative).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise BoundaryError(f"JSON object required: {relative}")
    return value


def _canonical_sha256(path: Path) -> str:
    payload = path.read_bytes()
    if path.suffix.casefold() == ".json":
        payload = json.dumps(
            json.loads(payload.decode("utf-8-sig")),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8") + b"\n"
    else:
        payload = (payload.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n").rstrip("\n") + "\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _module_name(path: Path, root: Path) -> str:
    relative = path.relative_to(root).with_suffix("")
    return ".".join(relative.parts)


def _module_path(root: Path, module: str) -> Path:
    """Resolve an importable backend module without widening the scan root."""

    relative = BACKEND_ROOT / Path(*module.split("."))
    file_path = _safe_path(root, str(relative.with_suffix(".py")))
    if file_path.is_file():
        return file_path
    return _safe_path(root, str(relative / "__init__.py"))


def _canonical_modules(root: Path, fixture: dict[str, Any]) -> dict[str, Path]:
    backend_root = _safe_path(root, str(BACKEND_ROOT))
    modules: dict[str, Path] = {}
    for relative_package in fixture.get("canonical_packages", []):
        package = _safe_path(root, relative_package)
        if not package.is_dir():
            continue
        for path in package.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            relative = path.relative_to(backend_root)
            parts = list(relative.with_suffix("").parts)
            if parts[-1] == "__init__":
                parts.pop()
            if parts:
                modules[".".join(parts)] = path
    return modules


def _relative_import_prefix(current_module: str, level: int, module: str | None) -> str:
    package = current_module.split(".")[:-1]
    if level > 1:
        package = package[: -(level - 1)]
    if module:
        package.extend(module.split("."))
    return ".".join(package)


def _imported_modules(
    tree: ast.AST,
    current_module: str,
    known_modules: set[str],
) -> set[str]:
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in known_modules:
                    imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            prefix = _relative_import_prefix(current_module, node.level, node.module)
            if prefix in known_modules:
                imports.add(prefix)
            for alias in node.names:
                candidate = f"{prefix}.{alias.name}" if prefix else alias.name
                if candidate in known_modules:
                    imports.add(candidate)
    return imports


def _is_shim(path: Path, target: str) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
    except (OSError, SyntaxError):
        return False
    has_target_import = any(
        isinstance(node, ast.ImportFrom) and node.module == target
        or isinstance(node, ast.Import) and any(alias.name == target for alias in node.names)
        for node in tree.body
    )
    has_target_loader = f'_import_module("{target}")' in text or f"_import_module('{target}')" in text
    has_business_definitions = any(
        isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        for node in tree.body
    )
    forbidden_calls = (
        "Session(",
        "create_engine(",
        "ChatOpenAI(",
        "OpenAIEmbeddings(",
    )
    return (
        (has_target_import or has_target_loader)
        and not has_business_definitions
        and not any(token in text for token in forbidden_calls)
    )


def _dynamic_imports(
    path: Path,
    tree: ast.AST,
    known_modules: set[str],
) -> list[str]:
    unresolved: list[str] = []
    known_prefixes = ("app", "service", "infrastructure", "llm", "dao", "tools", "vectorstore")
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function_name = ""
        if isinstance(node.func, ast.Name):
            function_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                function_name = f"{node.func.value.id}.{node.func.attr}"
        if function_name not in {"import_module", "importlib.import_module", "__import__", "find_spec"}:
            continue
        argument = node.args[0] if node.args else None
        if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
            value = argument.value
            if value.startswith(known_prefixes) and value not in known_modules:
                unresolved.append(f"{path.as_posix()}:{node.lineno}:{value}")
        else:
            unresolved.append(f"{path.as_posix()}:{node.lineno}:non_literal_dynamic_import")
    return unresolved


def _scan_reference_files(root: Path) -> list[Path]:
    """Scan repository-owned code/config/docs while pruning protected data roots."""

    candidates: list[Path] = []
    suffixes = {".py", ".md", ".json", ".toml", ".txt", ".yml", ".yaml", ".mjs", ".ts", ".vue"}
    roots = [
        _safe_path(root, "ez_back_dev"),
        _safe_path(root, "scripts"),
        _safe_path(root, ".github"),
        _safe_path(root, "docs"),
    ]
    for scan_root in roots:
        if not scan_root.is_dir():
            continue
        for current, directories, files in os.walk(scan_root):
            directories[:] = [
                name
                for name in directories
                if name.casefold()
                not in {
                    ".git",
                    ".pytest_cache",
                    "__pycache__",
                    "dist",
                    "node_modules",
                    "uploads",
                    "upload",
                    "projects",
                    "static",
                    "example",
                }
            ]
            current_path = Path(current)
            for name in files:
                path = current_path / name
                if path.suffix.casefold() in suffixes and not name.casefold().startswith(".env"):
                    candidates.append(path)
    for relative in ("README.md", "compose.yaml", "ez_back_dev/Dockerfile", "ez_back_dev/serve.py"):
        path = _safe_path(root, relative)
        if path.is_file() and path not in candidates:
            candidates.append(path)
    return candidates


def _reference_audit(
    root: Path,
    mapping: dict[str, str],
    canonical_modules: dict[str, Path],
    report: dict[str, Any],
) -> None:
    references: list[dict[str, str]] = []
    canonical_compatibility_imports: list[str] = []
    for path in _scan_reference_files(root):
        try:
            text = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):
            continue
        for old in mapping:
            if old not in text:
                continue
            relative = path.relative_to(root).as_posix()
            if relative.startswith("ez_back_dev/"):
                try:
                    module = ".".join(Path(relative).with_suffix("").parts[1:])
                except ValueError:
                    module = ""
                if module in canonical_modules:
                    canonical_compatibility_imports.append(f"{relative}:{old}")
                    continue
            references.append({"path": relative, "module": old})
    _add(
        report,
        "reference.audit",
        not canonical_compatibility_imports,
        f"compatibility-imports={canonical_compatibility_imports}; references={len(references)}",
    )
    report["reference_audit"] = {
        "scanned_files": len(_scan_reference_files(root)),
        "compatibility_references": references,
        "canonical_compatibility_imports": canonical_compatibility_imports,
    }


def _check_public_entrypoints(
    root: Path,
    entries: list[str],
    report: dict[str, Any],
) -> None:
    if not isinstance(entries, list):
        _add(report, "public.entrypoints", False, "public_entrypoints must be a list")
        return
    for entry in entries:
        if not isinstance(entry, str) or not entry:
            _add(report, "public.entrypoint", False, f"invalid entrypoint: {entry!r}")
            continue
        if entry.endswith(".py"):
            relative = f"ez_back_dev/{entry}"
            path = _safe_path(root, relative)
        else:
            module = entry.split(":", 1)[0]
            path = _module_path(root, module)
        _add(report, "public.entrypoint", path.is_file(), f"{entry} -> {path.relative_to(root).as_posix()}")


def _add(report: dict[str, Any], check_id: str, ok: bool, detail: str) -> None:
    item = {"id": check_id, "status": "pass" if ok else "fail", "detail": detail}
    report["checks"].append(item)
    if not ok:
        report["errors"].append(item)


def check_repository(root: Path) -> dict[str, Any]:
    report: dict[str, Any] = {"schema_version": SCHEMA, "status": "pass", "checks": [], "errors": []}
    migration: dict[str, Any] = {}
    try:
        fixture = _read_json(root, str(FIXTURE))
    except (BoundaryError, OSError, json.JSONDecodeError) as exc:
        report["status"] = "error"
        report["errors"].append({"id": "fixture.load", "status": "fail", "detail": str(exc)})
        return report
    _add(report, "fixture.schema", fixture.get("schema_version") == SCHEMA, str(fixture.get("schema_version")))
    _add(report, "fixture.manual_reviewed", fixture.get("manual_reviewed") is True, str(fixture.get("manual_reviewed")))
    _add(report, "fixture.auto_accept", fixture.get("auto_accept_current_values") is False, str(fixture.get("auto_accept_current_values")))
    parent = fixture.get("parent", {})
    try:
        parent_path = _safe_path(root, parent["fixture"])
        parent_ok = parent_path.is_file() and _canonical_sha256(parent_path) == parent["fixture_sha256"]
    except (KeyError, BoundaryError, OSError):
        parent_ok = False
    _add(report, "fixture.parent_hash", parent_ok, str(parent))

    package_ok = True
    for relative in fixture.get("canonical_packages", []):
        try:
            path = _safe_path(root, relative)
            ok = path.is_dir() and (path / "__init__.py").is_file()
        except BoundaryError:
            ok = False
        package_ok = package_ok and ok
        _add(report, "canonical.package", ok, relative)

    mapping = fixture.get("module_map", {})
    mapping_ok = isinstance(mapping, dict) and bool(mapping)
    for old, target in mapping.items():
        try:
            target_path = _module_path(root, target)
            old_path = _module_path(root, old)
            ok = target_path.is_file() and old_path.is_file() and _is_shim(old_path, target)
        except (BoundaryError, OSError):
            ok = False
        mapping_ok = mapping_ok and ok
        _add(report, "module.mapping", ok, f"{old} -> {target}")

    _check_public_entrypoints(root, fixture.get("public_entrypoints", []), report)

    canonical_modules = _canonical_modules(root, fixture)
    graph: dict[str, set[str]] = {}
    known_modules = set(canonical_modules) | set(mapping) | {
        "app",
        "dao",
        "llm",
        "tools",
        "vectorstore",
        "service",
    }
    dynamic_unknown: list[str] = []
    for module, path in canonical_modules.items():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError) as exc:
            _add(report, "canonical.parse", False, f"{module}: {exc}")
            continue
        imported_modules = _imported_modules(tree, module, known_modules)
        edges = {imported for imported in imported_modules if imported in canonical_modules}
        for imported in imported_modules:
            if imported in mapping:
                _add(
                    report,
                    "canonical.no_compat_import",
                    False,
                    f"{module} imports compatibility module {imported}",
                )
        dynamic_unknown.extend(_dynamic_imports(path, tree, known_modules))
        graph[module] = edges

    direction_rules = (
        ("infrastructure.", ("app.", "service."), "infrastructure cannot depend on delivery/service"),
        ("service.retrieval.", ("service.agent.",), "retrieval cannot depend on Agent"),
        ("service.workflow.", ("service.agent.",), "workflow cannot depend on Agent runtime"),
        ("service.project.", ("app.",), "project cannot depend on delivery"),
    )
    for module, edges in graph.items():
        for source_prefix, forbidden_prefixes, reason in direction_rules:
            if not module.startswith(source_prefix):
                continue
            for imported in edges:
                if imported.startswith(forbidden_prefixes):
                    _add(report, "dependency.direction", False, f"{module} -> {imported}: {reason}")

    visiting: set[str] = set()
    visited: set[str] = set()
    cycles: list[str] = []

    def visit(module: str, trail: tuple[str, ...] = ()) -> None:
        if module in visiting:
            cycles.append(" -> ".join((*trail, module)))
            return
        if module in visited:
            return
        visiting.add(module)
        for child in graph.get(module, set()):
            visit(child, (*trail, module))
        visiting.remove(module)
        visited.add(module)

    for module in graph:
        visit(module)
    _add(report, "canonical.no_cycles", not cycles, "; ".join(cycles) or "none")
    expected_dynamic = fixture.get("unresolved_dynamic_imports")
    _add(
        report,
        "dynamic.imports",
        isinstance(expected_dynamic, list) and expected_dynamic == dynamic_unknown,
        f"observed={dynamic_unknown}; recorded={expected_dynamic}",
    )

    historical_ok = True
    for relative, expected in fixture.get("historical_hashes", {}).items():
        try:
            path = _safe_path(root, relative)
            ok = path.is_file() and _canonical_sha256(path) == expected
        except (BoundaryError, OSError):
            ok = False
        historical_ok = historical_ok and ok
        _add(report, "historical.hash", ok, relative)

    migration_ok = True
    try:
        migration = _read_json(root, str(MIGRATION))
        migration_ok = (
            migration.get("schema_version") == MIGRATION_SCHEMA
            and migration.get("aspect") == 4
            and migration.get("manual_reviewed") is True
            and migration.get("auto_accept_current_values") is False
            and _relocated_relative(root, migration.get("parent", {}).get("fixture", ""))
            == str(FIXTURE).replace("\\", "/")
            and migration.get("removed_paths") == []
        )
        migration_parent = migration.get("parent", {})
        if isinstance(migration_parent, dict):
            parent_path = _safe_path(root, migration_parent.get("fixture", ""))
            migration_ok = migration_ok and (
                parent_path.is_file()
                and migration_parent.get("fixture_sha256") == _canonical_sha256(parent_path)
            )
        batches = migration.get("batches")
        batch_ids = {item.get("id") for item in batches} if isinstance(batches, list) else set()
        required_batch_ids = {"infrastructure", "retrieval-project-workflow", "agent-evaluation-legacy"}
        migration_ok = migration_ok and required_batch_ids <= batch_ids
        for batch in batches if isinstance(batches, list) else []:
            source_paths = batch.get("source_paths", [])
            canonical_paths = batch.get("canonical_paths", [])
            pre_hashes = batch.get("pre_change_sha256", {})
            post_hashes = batch.get("post_change_sha256", {})
            valid_pre = (
                isinstance(source_paths, list)
                and isinstance(pre_hashes, dict)
                and set(pre_hashes) == set(source_paths)
                and all(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) for value in pre_hashes.values())
            )
            valid_post = (
                isinstance(canonical_paths, list)
                and isinstance(post_hashes, dict)
                and set(post_hashes) == set(canonical_paths)
                and all(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) for value in post_hashes.values())
            )
            current_post = True
            for relative, expected in post_hashes.items():
                path = _safe_path(root, relative)
                reviewed_expected = _reviewed_post_hash(root, relative, expected)
                current_post = current_post and path.is_file() and _canonical_sha256(path) == reviewed_expected
            migration_ok = migration_ok and bool(batch.get("review")) and valid_pre and valid_post and current_post
        new_hashes = migration.get("new_path_post_change_sha256", {})
        valid_new = isinstance(new_hashes, dict) and bool(new_hashes)
        for relative, expected in new_hashes.items() if isinstance(new_hashes, dict) else []:
            try:
                path = _safe_path(root, relative)
                reviewed_expected = _reviewed_post_hash(root, relative, expected)
                valid_new = (
                    valid_new
                    and isinstance(reviewed_expected, str)
                    and re.fullmatch(r"[0-9a-f]{64}", reviewed_expected) is not None
                    and path.is_file()
                    and _canonical_sha256(path) == reviewed_expected
                )
            except (BoundaryError, OSError, TypeError):
                valid_new = False
        migration_ok = migration_ok and valid_new
        shims = migration.get("compatibility_shims")
        migration_ok = migration_ok and isinstance(shims, list)
        if isinstance(shims, list):
            observed_shims = {item.get("old") for item in shims if isinstance(item, dict)}
            migration_ok = migration_ok and observed_shims == set(mapping)
    except (BoundaryError, OSError, KeyError, TypeError, json.JSONDecodeError):
        migration_ok = False
    _add(report, "migration.fixture", migration_ok, str(MIGRATION))
    snapshot = migration.get("public_contract_snapshot", {}) if isinstance(migration, dict) else {}
    try:
        parent_contract = _read_json(root, snapshot.get("fixture", ""))
        snapshot_ok = (
            snapshot.get("workflow_count") == 19
            and len(parent_contract.get("workflows", [])) == 19
            and snapshot.get("tool_count") == 22
            and snapshot.get("rest_sse_mcp_unchanged") is True
        )
    except (BoundaryError, OSError, KeyError, TypeError, json.JSONDecodeError):
        snapshot_ok = False
    _add(report, "public.contract_snapshot", snapshot_ok, str(snapshot))
    _reference_audit(root, mapping, canonical_modules, report)
    recorded_audit = migration.get("reference_audit", {}) if isinstance(migration, dict) else {}
    computed_audit = report.get("reference_audit", {})
    _add(
        report,
        "reference.audit_fixture",
        isinstance(recorded_audit, dict)
        and recorded_audit.get("manual_reviewed") is True
        and recorded_audit.get("canonical_compatibility_imports") == computed_audit.get("canonical_compatibility_imports")
        and recorded_audit.get("unknown_dynamic_imports") == dynamic_unknown,
        f"recorded={recorded_audit}; computed={computed_audit}",
    )
    _add(report, "fixture.dynamic_unknown", fixture.get("unresolved_dynamic_imports") == [], str(fixture.get("unresolved_dynamic_imports")))
    if package_ok and mapping_ok and historical_ok and migration_ok and not report["errors"]:
        report["status"] = "pass"
    else:
        report["status"] = "fail"
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", required=True)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    try:
        root = args.repo_root.resolve()
        report = check_repository(root)
    except (BoundaryError, OSError) as exc:
        report = {"schema_version": SCHEMA, "status": "error", "checks": [], "errors": [{"id": "arguments", "status": "fail", "detail": str(exc)}]}
        if args.format == "json":
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(f"ERROR: {exc}")
        return 2
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for item in report["checks"]:
            print(f"{item['status'].upper()} {item['id']}: {item['detail']}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
