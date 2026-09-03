"""Read-only structural and reference checks for Iteration 5 Aspect 5.

This module intentionally has no migration or deletion API.  The baseline and
migration fixtures are reviewed records; this checker never rewrites them.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


SCHEMA_VERSION = "iteration5-frontend-structure-check-v1"
BASELINE_RELATIVE = Path(
    "ez_back_dev/tests/fixtures/current/iteration5/iteration5_frontend_structure_baseline_v1.json"
)
MIGRATION_RELATIVE = Path(
    "ez_back_dev/tests/fixtures/current/iteration5/iteration5_frontend_structure_migration_v1.json"
)
LATER_MIGRATION_RELATIVE = Path(
    "ez_back_dev/tests/fixtures/current/iteration5/iteration5_modular_runtime_migration_v1.json"
)
ASPECT8_CONTRACT_RELATIVE = Path("ops/iteration5-dual-mode-acceptance-contract.json")
FORBIDDEN_SWITCHES = {"--accept-current", "--update", "--write", "--delete"}
PROTECTED_SEGMENTS = {
    ".env",
    "example",
    "node_modules",
    "dist",
    "coverage",
    ".pytest_cache",
    ".ruff_cache",
    "uploads",
    "projects",
}
TEXT_SUFFIXES = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".mjs",
    ".md",
    ".py",
    ".ts",
    ".tsx",
    ".vue",
    ".yaml",
    ".yml",
}
SCAN_ROOTS = (
    "ez_front_dev/src",
    "ez_front_dev/public",
    "ez_back_dev/tests",
    "scripts",
    "docs",
    ".github/workflows",
)


@dataclass
class CheckReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    evidence: dict[str, object] = field(default_factory=dict)

    @property
    def exit_code(self) -> int:
        return 1 if self.errors else 0


def _relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load JSON fixture {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON fixture must be an object: {path}")
    return value


def normalized_sha256(path: Path) -> str:
    """Hash text with BOM/newline normalization; hash binary files as-is."""

    payload = path.read_bytes()
    if path.suffix.lower() in {".json", ".yaml", ".yml"}:
        try:
            value = json.loads(payload.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            value = None
        if value is not None:
            payload = (
                json.dumps(
                    value,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
                + b"\n"
            )
        else:
            payload = _normalized_text_bytes(payload)
    elif path.suffix.lower() in TEXT_SUFFIXES:
        payload = _normalized_text_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def _normalized_text_bytes(payload: bytes) -> bytes:
    text = payload.decode("utf-8-sig")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return (text.rstrip("\n") + "\n").encode("utf-8")


def validate_migration_path(
    repo_root: Path,
    candidate: str | Path,
    approved_roots: Iterable[str],
) -> tuple[bool, str]:
    """Validate one exact path without following an unsafe link target."""

    root = repo_root.resolve()
    raw = Path(candidate)
    path = raw if raw.is_absolute() else root / raw
    try:
        absolute = path.absolute()
        relative = absolute.relative_to(root)
    except ValueError:
        return False, "path_escapes_repository_root"

    parts = {part.casefold() for part in relative.parts}
    if parts & PROTECTED_SEGMENTS or any(
        part.casefold().startswith(".env") for part in relative.parts
    ):
        return False, "protected_path"

    approved = [Path(item).parts for item in approved_roots]
    if not any(tuple(relative.parts[: len(parts_)]) == parts_ for parts_ in approved):
        return False, "outside_approved_root"

    current = root
    for part in relative.parts:
        current = current / part
        if current.exists() and current.is_symlink():
            return False, "symlink_or_reparse_point"
        try:
            if current.exists() and current.stat().st_file_attributes & 0x400:
                return False, "symlink_or_reparse_point"
        except (AttributeError, OSError):
            pass
    return True, "ok"


def _iter_scan_files(root: Path) -> Iterable[Path]:
    for scan_root in SCAN_ROOTS:
        base = root / scan_root
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.is_symlink():
                continue
            if any(part.casefold() in PROTECTED_SEGMENTS for part in path.parts):
                continue
            if path.suffix.lower() in TEXT_SUFFIXES:
                yield path


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _validate_baseline(root: Path, baseline: dict, report: CheckReport) -> None:
    if baseline.get("schema_version") != "iteration5-frontend-structure-baseline-v1":
        report.errors.append("baseline schema_version is not iteration5 frontend v1")
    if baseline.get("aspect") != 5:
        report.errors.append("baseline aspect must be 5")
    if baseline.get("manual_reviewed") is not True:
        report.errors.append("baseline must be manually reviewed")
    if baseline.get("auto_accept_current_values") is not False:
        report.errors.append("baseline cannot auto-accept current values")
    parent = baseline.get("parent")
    if not isinstance(parent, dict) or not parent.get("fixture") or not parent.get(
        "fixture_sha256"
    ):
        report.errors.append("baseline parent fixture/hash is missing")
    else:
        parent_path = root / parent["fixture"]
        if not parent_path.is_file():
            report.errors.append(f"baseline parent fixture is missing: {parent['fixture']}")
        elif normalized_sha256(parent_path) != parent["fixture_sha256"]:
            report.errors.append(f"baseline parent hash drift: {parent['fixture']}")

    for field_name in (
        "route_snapshot",
        "source_path_map",
        "test_path_map",
        "fixture_path_map",
        "document_path_map",
        "asset_snapshot",
        "protected_paths",
        "removed_paths",
    ):
        if field_name not in baseline:
            report.errors.append(f"baseline field is missing: {field_name}")
    route_paths = baseline.get("route_snapshot", {}).get("paths", [])
    required_routes = {
        "/",
        "/about",
        "/create",
        "/menu",
        "/plan",
        "/unit",
        "/integration",
        "/api",
        "/ui",
        "/database",
        "/functional",
        "/nfunctional",
        "/acceptance",
        "/agent",
    }
    missing_routes = sorted(required_routes - set(route_paths))
    if missing_routes:
        report.errors.append(f"baseline route snapshot missing: {', '.join(missing_routes)}")


def _migration_records(migration: dict) -> list[dict]:
    batches = migration.get("batches")
    if not isinstance(batches, list):
        return []
    records: list[dict] = []
    for batch in batches:
        if not isinstance(batch, dict):
            continue
        records.extend(item for item in batch.get("paths", []) if isinstance(item, dict))
    return records


def _later_reviewed_hashes(root: Path) -> dict[str, str]:
    """Return explicitly reviewed post-hashes from later aspect overlays."""
    try:
        overlay = _load_json(root / LATER_MIGRATION_RELATIVE)
    except (OSError, UnicodeError, ValueError):
        return {}
    if overlay.get("manual_reviewed") is not True:
        return {}
    result: dict[str, str] = {}
    for record in _migration_records(overlay):
        new_path = record.get("new_path")
        post_hash = record.get("post_hash")
        if (
            isinstance(new_path, str)
            and isinstance(post_hash, str)
            and re.fullmatch(r"[0-9a-f]{64}", post_hash)
            and record.get("manual_review") is True
        ):
            result[new_path] = post_hash
    try:
        aspect8 = _load_json(root / ASPECT8_CONTRACT_RELATIVE)
        cumulative = aspect8.get("cumulative_overlay", {})
        allowed_paths = cumulative.get("allowed_paths", {})
    except (OSError, UnicodeError, ValueError):
        allowed_paths = {}
    if isinstance(allowed_paths, dict) and cumulative.get("manual_reviewed") is True:
        for new_path, evidence in allowed_paths.items():
            if not isinstance(new_path, str) or not isinstance(evidence, dict):
                continue
            post_hash = evidence.get("frontend_sha256")
            if (
                isinstance(post_hash, str)
                and re.fullmatch(r"[0-9a-f]{64}", post_hash, re.IGNORECASE)
                and evidence.get("manual_review") is True
            ):
                result[new_path] = post_hash
    return result


def _validate_migration(root: Path, migration: dict, report: CheckReport) -> None:
    if migration.get("schema_version") != "iteration5-frontend-structure-migration-v1":
        report.errors.append("migration schema_version is not iteration5 frontend v1")
    if migration.get("aspect") != 5:
        report.errors.append("migration aspect must be 5")
    if migration.get("manual_reviewed") is not True:
        report.errors.append("migration must be manually reviewed")
    if migration.get("auto_accept_current_values") is not False:
        report.errors.append("migration cannot auto-accept current values")
    parent = migration.get("parent_baseline")
    parent_hash = migration.get("parent_baseline_sha256")
    baseline_path = root / BASELINE_RELATIVE
    if parent != BASELINE_RELATIVE.as_posix():
        report.errors.append("migration parent baseline path is not canonical")
    if not isinstance(parent_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", parent_hash):
        report.errors.append("migration parent baseline hash is not a reviewed SHA-256")
    elif baseline_path.is_file() and normalized_sha256(baseline_path) != parent_hash:
        report.errors.append("migration parent baseline hash drift")
    if not isinstance(migration.get("removed_paths"), list):
        report.errors.append("migration removed_paths must be an explicit list")
    for removed in migration.get("removed_paths", []):
        if not isinstance(removed, str) or "*" in removed or "?" in removed:
            report.errors.append(f"removed path is not an exact path: {removed!r}")
    removal_records: dict[str, dict] = {}
    for batch in migration.get("batches", []):
        if not isinstance(batch, dict) or batch.get("id") != "legacy-test-image-precise-removal":
            continue
        for record in batch.get("paths", []):
            if isinstance(record, dict) and isinstance(record.get("old_path"), str):
                removal_records[record["old_path"]] = record
    removed_paths = {
        value for value in migration.get("removed_paths", []) if isinstance(value, str)
    }
    for removed in sorted(removed_paths):
        record = removal_records.get(removed)
        if record is None:
            report.errors.append(f"removed path lacks reviewed removal evidence: {removed}")
            continue
        for field_name in ("pre_hash", "post_hash"):
            value = record.get(field_name)
            if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
                report.errors.append(f"removed path has invalid {field_name}: {removed}")
        if record.get("manual_review") is not True or record.get("content_preserved") is not True:
            report.errors.append(f"removed path lacks manual preservation evidence: {removed}")
        recovery_path = record.get("new_path")
        if not isinstance(recovery_path, str) or not recovery_path:
            report.errors.append(f"removed path lacks exact recovery path: {removed}")
    for removed in sorted(set(removal_records) - removed_paths):
        report.errors.append(f"removal evidence is not listed in removed_paths: {removed}")
    for record in _migration_records(migration):
        for field_name in (
            "old_path",
            "new_path",
            "pre_hash",
            "post_hash",
            "content_preserved",
            "manual_review",
            "redirect_stub",
        ):
            if field_name not in record:
                report.errors.append(f"migration record missing {field_name}: {record}")

    redirects = migration.get("redirect_stubs")
    if not isinstance(redirects, list):
        report.errors.append("migration redirect_stubs must be an explicit list")
        redirects = []
    records_by_old: dict[str, list[dict]] = {}
    for record in _migration_records(migration):
        old_path = record.get("old_path")
        if isinstance(old_path, str):
            records_by_old.setdefault(old_path, []).append(record)
    later_hashes = _later_reviewed_hashes(root)
    seen_redirects: set[str] = set()
    for redirect in redirects:
        if not isinstance(redirect, dict):
            report.errors.append(f"redirect stub must be an object: {redirect!r}")
            continue
        old = redirect.get("old_path")
        new = redirect.get("new_path")
        if not isinstance(old, str) or not isinstance(new, str):
            report.errors.append(f"redirect stub paths must be strings: {redirect!r}")
            continue
        if old in seen_redirects:
            report.errors.append(f"redirect stub is duplicated: {old}")
        seen_redirects.add(old)
        allowed_old, old_reason = validate_migration_path(root, old, ["docs"])
        allowed_new, new_reason = validate_migration_path(root, new, ["docs"])
        if not allowed_old:
            report.errors.append(f"redirect source rejected: {old}: {old_reason}")
        if not allowed_new:
            report.errors.append(f"redirect target rejected: {new}: {new_reason}")
        old_path = root / old
        new_path = root / new
        if not old_path.is_file() or not new_path.is_file():
            report.errors.append(f"redirect source or target is missing: {old} -> {new}")
            continue
        try:
            stub_text = _read_text(old_path)
        except (OSError, UnicodeError) as exc:
            report.errors.append(f"redirect stub cannot be read: {old}: {exc}")
            continue
        if "frontend-structure.md" not in stub_text or old == new:
            report.errors.append(f"redirect stub is not a non-copying mapping: {old}")
        records = records_by_old.get(old, [])
        move_record = next(
            (
                item
                for item in reversed(records)
                if item.get("new_path") == new and item.get("content_preserved") is True
            ),
            None,
        )
        latest_record = next(
            (item for item in reversed(records) if item.get("new_path") == new),
            None,
        )
        if move_record is None:
            report.errors.append(f"redirect stub lacks matching document move record: {old}")
        elif move_record.get("manual_review") is not True:
            report.errors.append(f"redirect stub move record is not reviewed: {old}")
        elif latest_record is None or latest_record.get("manual_review") is not True:
            report.errors.append(f"redirect stub latest update is not reviewed: {old}")
        elif normalized_sha256(new_path).lower() != str(latest_record.get("post_hash", "")).lower() and (
            str(later_hashes.get(new, "")).lower() != normalized_sha256(new_path).lower()
        ):
            report.errors.append(f"redirect target hash drift: {new}")


def _validate_path_map(root: Path, baseline: dict, migration: dict, report: CheckReport) -> None:
    path_map = baseline.get("source_path_map", {})
    if not isinstance(path_map, dict) or not path_map:
        report.errors.append("source_path_map must be explicit and non-empty")
        return
    records = {item.get("old_path"): item for item in _migration_records(migration)}
    missing_destinations: list[str] = []
    for old_path, new_path in path_map.items():
        if not isinstance(old_path, str) or not isinstance(new_path, str):
            report.errors.append("source_path_map entries must be strings")
            continue
        allowed_old, old_reason = validate_migration_path(
            root, old_path, ["ez_front_dev/src"]
        )
        allowed_new, new_reason = validate_migration_path(
            root, new_path, ["ez_front_dev/src"]
        )
        if not allowed_old and old_path != "ez_front_dev/src/components/HelloWorld.vue":
            report.errors.append(f"old source path rejected: {old_path}: {old_reason}")
        if not allowed_new:
            report.errors.append(f"new source path rejected: {new_path}: {new_reason}")
        destination = root / new_path
        if not destination.is_file():
            missing_destinations.append(new_path)
        old_file = root / old_path
        if old_file.is_file() and old_path not in records:
            report.errors.append(f"old source path remains without migration record: {old_path}")
    if missing_destinations:
        report.errors.append(
            "canonical source paths are not present: " + ", ".join(sorted(missing_destinations))
        )


def _validate_active_frontend(root: Path, baseline: dict, report: CheckReport) -> None:
    router = root / "ez_front_dev/src/app/router/index.ts"
    if not router.is_file():
        report.errors.append("canonical router is missing")
        return
    source = _read_text(router)
    for path in baseline["route_snapshot"]["paths"]:
        if path not in source:
            report.errors.append(f"route is absent from canonical router: {path}")
    if "FounctionalTest.vue" in source:
        report.errors.append("old FounctionalTest.vue path remains in active router")
    if "FunctionalTest.vue" not in source:
        report.errors.append("canonical FunctionalTest.vue is absent from active router")
    for old_fragment in (
        "../views/",
        "../components/",
        "../composables/",
        "../state/",
        "../config/",
        "../styles/",
        "../ui/",
        "../plugins/",
    ):
        if old_fragment in source:
            report.errors.append(f"old router import prefix remains: {old_fragment}")

    for path in (root / "ez_front_dev/src").rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".vue", ".ts", ".css"}:
            continue
        if any(part.casefold() in PROTECTED_SEGMENTS for part in path.parts):
            continue
        text = _read_text(path)
        if "FounctionalTest.vue" in text:
            report.errors.append(f"old FunctionalTest spelling remains in active source: {_relative(path, root)}")
        for old_prefix in (
            "@/components/",
            "@/views/",
            "@/composables/",
            "@/state/",
            "@/config/",
            "@/styles/",
            "@/ui/",
            "@/plugins/",
        ):
            if old_prefix in text:
                report.errors.append(f"old alias remains in active source: {old_prefix} ({_relative(path, root)})")


def _python_imports(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeError, SyntaxError):
        return []
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append("." * node.level + (node.module or ""))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == "__import__":
                imports.append("dynamic:__import__")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in {"import_module", "find_spec"}:
                imports.append(f"dynamic:{node.func.attr}")
    return imports


def _validate_reference_audit(root: Path, baseline: dict, report: CheckReport) -> None:
    unresolved: list[str] = []
    for path in _iter_scan_files(root):
        try:
            text = _read_text(path)
        except (OSError, UnicodeError):
            continue
        relative = _relative(path, root)
        if "FounctionalTest.vue" in text and relative.startswith("ez_front_dev/src/"):
            unresolved.append(f"active:{relative}:FounctionalTest.vue")
        if relative.endswith(".py"):
            imports = _python_imports(path)
            if any(item.startswith("dynamic:") for item in imports):
                report.evidence.setdefault("dynamic_imports", {})
                report.evidence["dynamic_imports"][relative] = imports
    allowed_historical_tokens = {
        "iteration5_frontend_structure_baseline_v1.json",
        "iteration5_frontend_structure_migration_v1.json",
        "frontend-structure.md",
    }
    if unresolved:
        for item in unresolved:
            if not any(token in item for token in allowed_historical_tokens):
                report.errors.append(f"unresolved active reference: {item}")
    report.evidence["python_import_audit"] = "AST parsed repository test/scripts/docs scan"
    report.evidence["allowed_historical_tokens"] = sorted(allowed_historical_tokens)


def check_repository(repo_root: Path) -> CheckReport:
    report = CheckReport()
    root = repo_root.resolve()
    baseline_path = root / BASELINE_RELATIVE
    migration_path = root / MIGRATION_RELATIVE
    if not root.is_dir():
        report.errors.append(f"repository root is not a directory: {root}")
        return report
    if not baseline_path.is_file() or not migration_path.is_file():
        report.errors.append("Aspect 5 baseline or migration fixture is missing")
        return report
    try:
        baseline = _load_json(baseline_path)
        migration = _load_json(migration_path)
    except ValueError as exc:
        report.errors.append(str(exc))
        return report
    _validate_baseline(root, baseline, report)
    _validate_migration(root, migration, report)
    _validate_path_map(root, baseline, migration, report)
    _validate_active_frontend(root, baseline, report)
    _validate_reference_audit(root, baseline, report)

    for relative in baseline.get("protected_paths", []):
        if relative == ".env":
            # Existence is not read beyond the path boundary.
            report.evidence["protected_env"] = "existence_only"
    report.evidence["schema_version"] = SCHEMA_VERSION
    report.evidence["removed_paths"] = migration.get("removed_paths", [])
    return report


def _format_report(report: CheckReport, output_format: str) -> str:
    if output_format == "json":
        return json.dumps(
            {
                "exit_code": report.exit_code,
                "errors": report.errors,
                "warnings": report.warnings,
                "evidence": report.evidence,
            },
            ensure_ascii=False,
            indent=2,
        )
    lines = [f"frontend-structure-check: {'FAIL' if report.errors else 'PASS'}"]
    lines.extend(f"ERROR: {item}" for item in report.errors)
    lines.extend(f"WARNING: {item}" for item in report.warnings)
    if not report.errors:
        lines.append("No unresolved active frontend structure references.")
    return "\n".join(lines)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", required=True)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args, unknown = parser.parse_known_args(argv)
    if unknown or any(item in FORBIDDEN_SWITCHES for item in unknown):
        parser.error("only read-only --check options are supported")
    if not args.repo_root.is_absolute():
        parser.error("--repo-root must be an absolute path")
    return args


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parse_args(argv)
        report = check_repository(args.repo_root)
    except (OSError, ValueError) as exc:
        print(f"frontend-structure-check: configuration error: {exc}", file=sys.stderr)
        return 2
    print(_format_report(report, args.format))
    return report.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
