"""Validate the active cross-toolchain version contract without writing files."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


CONTRACT_RELATIVE = Path("ops/version-contract.json")
SCHEMA_VERSION = "iteration5-version-contract-v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)
FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)
EXACT_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
PYTHON_FROM_RE = re.compile(
    r"^FROM\s+python:(?P<version>\d+\.\d+\.\d+)-slim@sha256:(?P<digest>[0-9a-f]{64})",
    re.IGNORECASE,
)
NODE_FROM_RE = re.compile(
    r"^FROM\s+node:(?P<version>\d+\.\d+\.\d+)-alpine@sha256:(?P<digest>[0-9a-f]{64})",
    re.IGNORECASE,
)
IMAGE_RE = re.compile(
    r"^\s*image:\s*[\"']?(?P<image>[^\"'\s]+)[\"']?\s*$",
    re.IGNORECASE,
)
USES_RE = re.compile(
    r"^\s*-?\s*uses:\s*(?P<action>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)@(?P<ref>[^\s#]+)\s*(?:#\s*(?P<comment>.*))?$"
)
VERSION_LINE_RE = re.compile(r"^\s*(?:python-version|node-version):\s*[\"']?([^\"'\s]+)")
REQUIREMENT_RE = re.compile(
    r"^\s*(?P<name>[A-Za-z0-9_.-]+)(?:\[[^]]+\])?==(?P<version>[^\s;\\]+)"
)
HASH_TOKEN_RE = re.compile(r"--hash=(?P<algorithm>[A-Za-z0-9-]+):(?P<digest>[0-9a-fA-F]+)")


class ContractError(ValueError):
    """Raised when the repository root or contract is unsafe to inspect."""


def _safe_path(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    root_resolved = root.resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise ContractError(f"path escapes repository root: {relative}") from exc
    parts = {part.casefold() for part in Path(relative).parts}
    if ".env" in parts or any(
        part.startswith(".env.") and part.casefold() != ".env.example"
        for part in parts
    ):
        raise ContractError(f"refusing to read a real environment file: {relative}")
    return candidate


def _read_text(root: Path, relative: str) -> str:
    path = _safe_path(root, relative)
    if not path.is_file():
        raise ContractError(f"missing contract input: {relative}")
    return path.read_text(encoding="utf-8")


def _read_json(root: Path, relative: str) -> dict[str, Any]:
    try:
        value = json.loads(_read_text(root, relative))
    except json.JSONDecodeError as exc:
        raise ContractError(f"invalid JSON: {relative}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"JSON object required: {relative}")
    return value


def load_contract(root: Path) -> dict[str, Any]:
    contract = _read_json(root, str(CONTRACT_RELATIVE))
    if contract.get("schema_version") != SCHEMA_VERSION:
        raise ContractError("unsupported version contract schema")
    return contract


def _add(report: dict[str, Any], check_id: str, ok: bool, detail: str) -> None:
    report["checks"].append(
        {"id": check_id, "status": "pass" if ok else "fail", "detail": detail}
    )
    if not ok:
        report["errors"].append({"id": check_id, "detail": detail})


def _version_minor(version: str) -> tuple[int, int]:
    parts = version.split(".")
    return int(parts[0]), int(parts[1])


def _logical_requirement_lines(text: str) -> list[str]:
    logical: list[str] = []
    current = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.endswith("\\"):
            current += line[:-1].rstrip() + " "
            continue
        logical.append((current + line).strip())
        current = ""
    if current:
        logical.append(current.strip())
    return logical


def _direct_requirement_names(text: str) -> set[str]:
    return set(_direct_requirement_versions(text))


def _direct_requirement_versions(text: str) -> dict[str, str]:
    names: set[str] = set()
    versions: dict[str, str] = {}
    for line in _logical_requirement_lines(text):
        match = REQUIREMENT_RE.match(line)
        if match:
            name = match.group("name").casefold().replace("-", "_")
            names.add(name)
            versions[name] = match.group("version")
    return versions


def _all_hashes_are_sha256(line: str) -> bool:
    hashes = HASH_TOKEN_RE.findall(line)
    return bool(hashes) and all(
        algorithm.casefold() == "sha256" and bool(SHA256_RE.fullmatch(digest))
        for algorithm, digest in hashes
    )


def check_contract(root: Path) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "checks": [],
        "errors": [],
    }
    try:
        contract = load_contract(root)
    except ContractError as exc:
        report["status"] = "error"
        report["errors"].append({"id": "contract.load", "detail": str(exc)})
        return report

    _add(
        report,
        "contract.product_release",
        contract.get("product_release") == "0.1.0",
        f"product_release={contract.get('product_release')!r}",
    )

    runtime = contract.get("runtime")
    python_runtime = runtime.get("python") if isinstance(runtime, dict) else None
    node_runtime = runtime.get("node") if isinstance(runtime, dict) else None
    if not isinstance(python_runtime, dict) or not isinstance(node_runtime, dict):
        _add(report, "contract.runtime.shape", False, "runtime.python and runtime.node are required")
        return report

    _add(report, "runtime.python.line", python_runtime.get("line") == "3.11", str(python_runtime.get("line")))
    _add(report, "runtime.node.line", node_runtime.get("line") == "24", str(node_runtime.get("line")))
    _add(report, "runtime.node.npm_major", node_runtime.get("npm_major") == 11, str(node_runtime.get("npm_major")))

    backend_dockerfile = python_runtime.get("dockerfile")
    frontend_dockerfile = node_runtime.get("dockerfile")
    workflow = python_runtime.get("ci_workflow")
    for check_id, relative in (
        ("runtime.python.dockerfile_path", backend_dockerfile),
        ("runtime.node.dockerfile_path", frontend_dockerfile),
        ("runtime.ci.workflow_path", workflow),
        ("contract.human_doc_path", contract.get("human_doc")),
    ):
        ok = isinstance(relative, str)
        if ok:
            try:
                _safe_path(root, relative)
                ok = _safe_path(root, relative).is_file()
            except ContractError:
                ok = False
        _add(report, check_id, ok, str(relative))

    if isinstance(backend_dockerfile, str):
        backend_text = _read_text(root, backend_dockerfile)
        backend_from = next(
            (PYTHON_FROM_RE.match(line.strip()) for line in backend_text.splitlines() if line.strip().upper().startswith("FROM ")),
            None,
        )
        expected = python_runtime.get("exact")
        exact_ok = bool(backend_from and backend_from.group("version") == expected)
        digest_ok = bool(backend_from and SHA256_RE.fullmatch(backend_from.group("digest")))
        _add(report, "runtime.python.docker_exact", exact_ok, f"observed={backend_from.group('version') if backend_from else None}; expected={expected}")
        _add(report, "runtime.python.docker_digest", digest_ok, "backend FROM digest is sha256-pinned")
        expected_ref = contract.get("dockerfiles", {}).get("backend_base")
        observed_ref = (
            f"python:{backend_from.group('version')}-slim@sha256:{backend_from.group('digest')}"
            if backend_from
            else ""
        )
        _add(report, "runtime.python.docker_ref_contract", observed_ref == expected_ref, f"observed={observed_ref}; expected={expected_ref}")

    if isinstance(frontend_dockerfile, str):
        frontend_text = _read_text(root, frontend_dockerfile)
        node_from = next(
            (NODE_FROM_RE.match(line.strip()) for line in frontend_text.splitlines() if line.strip().upper().startswith("FROM NODE:")),
            None,
        )
        expected = node_runtime.get("exact")
        exact_ok = bool(node_from and node_from.group("version") == expected)
        digest_ok = bool(node_from and SHA256_RE.fullmatch(node_from.group("digest")))
        _add(report, "runtime.node.docker_exact", exact_ok, f"observed={node_from.group('version') if node_from else None}; expected={expected}")
        _add(report, "runtime.node.docker_digest", digest_ok, "node FROM digest is sha256-pinned")
        _add(report, "runtime.nginx.digest", "nginx:" in frontend_text and "@sha256:" in frontend_text, "nginx runtime image is digest-pinned")
        expected_ref = contract.get("dockerfiles", {}).get("frontend_build_base")
        observed_ref = (
            f"node:{node_from.group('version')}-alpine@sha256:{node_from.group('digest')}"
            if node_from
            else ""
        )
        _add(report, "runtime.node.docker_ref_contract", observed_ref == expected_ref, f"observed={observed_ref}; expected={expected_ref}")
        nginx_ref_match = re.search(r"^FROM\s+(?P<ref>nginx:[^\s]+)", frontend_text, re.IGNORECASE | re.MULTILINE)
        expected_nginx = contract.get("dockerfiles", {}).get("frontend_runtime_base")
        _add(report, "runtime.nginx.ref_contract", bool(nginx_ref_match) and nginx_ref_match.group("ref") == expected_nginx, f"observed={nginx_ref_match.group('ref') if nginx_ref_match else None}; expected={expected_nginx}")

    if isinstance(workflow, str):
        workflow_text = _read_text(root, workflow)
        versions = [
            ("python", python_runtime.get("exact")),
            ("node", node_runtime.get("exact")),
        ]
        for name, expected in versions:
            observed = [
                match.group(1)
                for line in workflow_text.splitlines()
                if (match := VERSION_LINE_RE.match(line))
                and name in line
            ]
            _add(report, f"runtime.ci.{name}", bool(observed) and all(item == expected for item in observed), f"observed={observed}; expected={expected}")

    python_policy = contract.get("python_lock")
    if not isinstance(python_policy, dict):
        _add(report, "python_lock.shape", False, "python_lock is required")
    else:
        input_path = python_policy.get("input")
        locks = python_policy.get("locks")
        generator = python_policy.get("generator")
        _add(report, "python_lock.generator", generator == {"name": "pip-tools", "version": "7.6.1"}, str(generator))
        input_text = _read_text(root, input_path) if isinstance(input_path, str) else ""
        direct_versions = _direct_requirement_versions(input_text)
        direct_names = set(direct_versions)
        _add(report, "python_lock.direct_input_pinned", bool(direct_names) and len(direct_names) >= 20, f"direct_packages={len(direct_names)}")
        expected_direct = python_policy.get("direct_versions")
        expected_normalized = {
            str(name).casefold().replace("-", "_"): str(version)
            for name, version in expected_direct.items()
        } if isinstance(expected_direct, dict) else {}
        _add(
            report,
            "python_lock.direct_contract_alignment",
            bool(expected_normalized)
            and direct_versions == expected_normalized,
            "requirements.in exact pins match the version contract",
        )
        if isinstance(locks, dict):
            for platform in ("linux", "windows"):
                relative = locks.get(platform)
                ok = isinstance(relative, str)
                if ok:
                    try:
                        lock_text = _read_text(root, relative)
                    except ContractError as exc:
                        _add(report, f"python_lock.{platform}", False, str(exc))
                        continue
                    logical = _logical_requirement_lines(lock_text)
                    package_lines = [line for line in logical if not line.startswith(("-", "--"))]
                    pinned = [REQUIREMENT_RE.match(line) for line in package_lines]
                    ok = bool(package_lines) and all(
                        match and _all_hashes_are_sha256(line)
                        for match, line in zip(pinned, package_lines)
                    )
                    names = {match.group("name").casefold().replace("-", "_") for match in pinned if match}
                    ok = ok and direct_names <= names
                    _add(report, f"python_lock.{platform}", ok, f"path={relative}; packages={len(names)}")
                else:
                    _add(report, f"python_lock.{platform}", False, str(relative))

    node_policy = contract.get("node_lock")
    if not isinstance(node_policy, dict):
        _add(report, "node_lock.shape", False, "node_lock is required")
    else:
        manifest_path = node_policy.get("manifest")
        lock_path = node_policy.get("lock")
        manifest = _read_json(root, manifest_path) if isinstance(manifest_path, str) else {}
        lock = _read_json(root, lock_path) if isinstance(lock_path, str) else {}
        _add(report, "node_lock.version", lock.get("lockfileVersion") == 3, str(lock.get("lockfileVersion")))
        _add(report, "node_lock.product_version", manifest.get("version") == contract.get("product_release"), str(manifest.get("version")))
        root_lock = lock.get("packages", {}).get("") if isinstance(lock.get("packages"), dict) else None
        _add(report, "node_lock.root_alignment", isinstance(root_lock, dict) and root_lock.get("dependencies") == manifest.get("dependencies") and root_lock.get("devDependencies") == manifest.get("devDependencies"), "package.json root specs match lock root")
        _add(
            report,
            "node_lock.contract_alignment",
            manifest.get("dependencies") == node_policy.get("direct_dependencies")
            and manifest.get("devDependencies") == node_policy.get("direct_dev_dependencies"),
            "package.json exact specs match the version contract",
        )
        all_specs = dict(manifest.get("dependencies", {}))
        all_specs.update(manifest.get("devDependencies", {}))
        exact = all(
            isinstance(value, str) and bool(EXACT_VERSION_RE.fullmatch(value))
            for value in all_specs.values()
        )
        _add(report, "node_lock.direct_exact", exact, f"direct_specs={len(all_specs)}")
        vue_version = all_specs.get("vue")
        compiler_version = all_specs.get("@vue/compiler-sfc")
        aligned = bool(vue_version and compiler_version) and _version_minor(vue_version) == _version_minor(compiler_version)
        _add(report, "node_lock.vue_compiler_minor", aligned, f"vue={vue_version}; compiler={compiler_version}")

    quality = contract.get("quality_tools")
    if not isinstance(quality, dict):
        _add(report, "quality_tools.shape", False, "quality_tools is required")
    else:
        ruff = quality.get("ruff")
        prettier = quality.get("prettier")
        _add(
            report,
            "quality_tools.ruff",
            isinstance(ruff, dict) and ruff.get("name") == "ruff" and ruff.get("version") == "0.16.5",
            str(ruff),
        )
        _add(
            report,
            "quality_tools.prettier",
            isinstance(prettier, dict) and prettier.get("name") == "prettier" and prettier.get("version") == "3.9.6",
            str(prettier),
        )
        dev_locks = quality.get("python_dev_locks")
        _add(
            report,
            "quality_tools.python_dev_locks",
            dev_locks == {
                "input": "ez_back_dev/requirements-dev.in",
                "linux": "ez_back_dev/requirements-dev.txt",
                "windows": "ez_back_dev/requirements-dev-windows.txt",
                "generator": {"name": "pip-tools", "version": "7.6.1"},
            },
            str(dev_locks),
        )
        paths = quality.get("paths")
        expected_paths = {
            "style_checker": "scripts/check_style_contract.py",
            "style_baseline": "ez_back_dev/tests/fixtures/iteration5_style_baseline_v1.json",
            "style_migration": "ez_back_dev/tests/fixtures/iteration5_style_migration_v1.json",
            "ruff_config": "ruff.toml",
            "prettier_config": ".prettierrc.json",
        }
        _add(
            report,
            "quality_tools.paths",
            isinstance(paths, dict) and all(paths.get(key) == value for key, value in expected_paths.items()),
            str(paths),
        )

    images = contract.get("images")
    compose_path = images.get("compose") if isinstance(images, dict) else None
    if isinstance(compose_path, str):
        compose_text = _read_text(root, compose_path)
        external = images.get("external_services", [])
        image_lines = {}
        current_service = None
        for line in compose_text.splitlines():
            service_match = re.match(r"^\s{2}([A-Za-z0-9_-]+):\s*$", line)
            if service_match:
                current_service = service_match.group(1)
            image_match = IMAGE_RE.match(line)
            if image_match and current_service:
                image_lines[current_service] = image_match.group("image")
        for service in external:
            image = image_lines.get(service, "")
            digest = image.rsplit("@sha256:", 1)[-1] if "@sha256:" in image else ""
            _add(report, f"compose.{service}.digest", bool(SHA256_RE.fullmatch(digest)), image or "missing")
            expected = images.get("refs", {}).get(service) if isinstance(images, dict) else None
            _add(report, f"compose.{service}.ref_contract", image == expected, f"observed={image}; expected={expected}")
        app_tags = images.get("application_tags", {})
        app_images_present = all(
            isinstance(image, str) and image in compose_text
            for image in app_tags.values()
        ) if isinstance(app_tags, dict) else False
        _add(
            report,
            "compose.app_tags",
            app_images_present
            and not any("iteration" in image.casefold() for image in app_tags.values()),
            str(app_tags),
        )

    actions = contract.get("actions")
    if isinstance(actions, dict) and isinstance(actions.get("workflow"), str):
        action_text = _read_text(root, actions["workflow"])
        action_lines = [USES_RE.match(line) for line in action_text.splitlines() if "uses:" in line]
        valid = bool(action_lines) and all(
            match and FULL_SHA_RE.fullmatch(match.group("ref")) and bool(match.group("comment"))
            for match in action_lines
        )
        _add(report, "actions.full_sha_with_comment", valid, f"action_lines={len(action_lines)}")
        expected_refs = actions.get("refs", {})
        observed_refs = {
            match.group("action"): match.group("ref")
            for match in action_lines
            if match
        }
        _add(report, "actions.contract_alignment", all(
            observed_refs.get(action) == ref
            for action, ref in expected_refs.items()
        ), "workflow action refs match the version contract")

    human_doc = contract.get("human_doc")
    if isinstance(human_doc, str):
        versions_text = _read_text(root, human_doc)
        readme = _read_text(root, "README.md")
        _add(report, "docs.readme_links_versions", "docs/versions.md" in readme, "README links docs/versions.md")
        _add(report, "docs.human_version_doc_marker", "version-contract.json" in versions_text, "human version doc identifies machine contract")
        forbidden = (
            "Element Plus 2.7",
            "Node.js 24、npm 11",
            "langchain-core==1.5.6",
            "langchain-openai==1.5.2",
            "openai==3.3.0",
            "Python 3.11 runtime baseline verified",
        )
        _add(report, "docs.readme_no_duplicate_versions", not any(token in readme for token in forbidden), "active README has no known duplicate version text")

    report["status"] = "pass" if not report["errors"] else "fail"
    return report


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--check", action="store_true", help="validate without writing files")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if not args.check:
        print("refusing to run without explicit --check", file=sys.stderr)
        return 2
    report = check_contract(args.repo_root.resolve())
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"version-contract: {report['status']}")
        for item in report["checks"]:
            print(f"[{item['status']}] {item['id']}: {item['detail']}")
        for item in report["errors"]:
            print(f"[error] {item['id']}: {item['detail']}", file=sys.stderr)
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
