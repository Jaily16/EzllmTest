from __future__ import annotations

import hashlib
import json
from pathlib import Path


from repo_paths import canonical_document_relative
from repo_paths import REPO_ROOT as ROOT


_FIXTURE_PATH_REWRITES = {
    "ez_back_dev/tests/fixtures/iteration3_contract_baseline_v1.json":
        "ez_back_dev/tests/fixtures/historical/iteration3/iteration3_contract_baseline_v1.json",
    "ez_back_dev/tests/fixtures/iteration4_release_manifest_v1.json":
        "ez_back_dev/tests/fixtures/historical/iteration4/iteration4_release_manifest_v1.json",
}

_TEST_PATH_REWRITES = {
    "ez_back_dev/tests/test_iteration4_release_contracts.py":
        "ez_back_dev/tests/historical/iteration4/test_iteration4_release_contracts.py",
    "ez_back_dev/tests/test_iteration5_planning_contracts.py":
        "ez_back_dev/tests/contract/iteration5/test_iteration5_planning_contracts.py",
}


def _repo_path(relative: str) -> Path:
    if relative.startswith("ez_back_dev/tests/fixtures/iteration5_"):
        relative = relative.replace(
            "ez_back_dev/tests/fixtures/", "ez_back_dev/tests/fixtures/current/iteration5/", 1
        )
    else:
        relative = _FIXTURE_PATH_REWRITES.get(relative, relative)
        relative = _TEST_PATH_REWRITES.get(relative, relative)
    relative = canonical_document_relative(relative)
    return ROOT / relative


def _load(relative: str) -> dict:
    return json.loads(_repo_path(relative).read_text(encoding="utf-8"))


def _normalized_sha256(path: Path) -> str:
    payload = path.read_bytes()
    if path.suffix.lower() == ".json":
        if payload.startswith(b"\xef\xbb\xbf"):
            payload = payload[3:]
        payload = (
            json.dumps(
                json.loads(payload.decode("utf-8")),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            + b"\n"
        )
    else:
        if payload.startswith(b"\xef\xbb\xbf"):
            payload = payload[3:]
        payload = payload.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
        payload = (payload.rstrip("\n") + "\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _normalized_size(path: Path) -> int:
    payload = path.read_bytes()
    if path.suffix.lower() == ".json":
        if payload.startswith(b"\xef\xbb\xbf"):
            payload = payload[3:]
        payload = (
            json.dumps(
                json.loads(payload.decode("utf-8")),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            + b"\n"
        )
    else:
        if payload.startswith(b"\xef\xbb\xbf"):
            payload = payload[3:]
        text = payload.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
        payload = (text.rstrip("\n") + "\n").encode("utf-8")
    return len(payload)


def _platform_size_variants(path: Path) -> set[int]:
    """Accept only canonical LF and its exact CRLF representation."""
    payload = path.read_bytes()
    variants = {len(payload)}
    if path.suffix.lower() == ".json":
        return variants | {_normalized_size(path)}
    if payload.startswith(b"\xef\xbb\xbf"):
        payload = payload[3:]
    text = payload.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    canonical = (text.rstrip("\n") + "\n").encode("utf-8")
    variants.add(len(canonical))
    variants.add(len(canonical.replace(b"\n", b"\r\n")))
    return variants


def _aspect3_style_changed_paths() -> set[str]:
    migration = _load(
        "ez_back_dev/tests/fixtures/iteration5_style_migration_v1.json"
    )
    return {
        relative
        for batch in migration["batches"]
        for relative in batch["paths"]
    }


def _aspect4_backend_changed_paths() -> set[str]:
    migration = _load(
        "ez_back_dev/tests/fixtures/iteration5_backend_migration_v1.json"
    )
    return {
        relative
        for batch in migration["batches"]
        for relative in batch["source_paths"]
    }


def _aspect5_structure_changed_paths() -> set[str]:
    migration = _load(
        "ez_back_dev/tests/fixtures/current/iteration5/"
        "iteration5_frontend_structure_migration_v1.json"
    )
    return {
        record["old_path"]
        for batch in migration["batches"]
        for record in batch.get("paths", [])
        if isinstance(record, dict) and isinstance(record.get("old_path"), str)
    }


def _later_reviewed_paths() -> set[str]:
    contract = _load("ops/iteration5-dual-mode-acceptance-contract.json")
    overlay = contract.get("cumulative_overlay", {})
    allowed_paths = overlay.get("allowed_paths", {})
    return set(allowed_paths) if isinstance(allowed_paths, dict) else set()


def test_baseline_freezes_the_current_git_identity_without_network_assumptions():
    baseline = _load("ez_back_dev/tests/fixtures/iteration5_baseline_manifest_v1.json")
    assert baseline["schema_version"] == "iteration5-baseline-manifest-v1"
    assert baseline["hash_policy"] == "sha256_canonical_lf_v1"
    assert baseline["git"] == {
        "branch": "main",
        "head": "8812be4fa73ab6274ec642fd5099be060aafb5d6",
        "origin_main": "8812be4fa73ab6274ec642fd5099be060aafb5d6",
        "ahead_behind": ["0", "0"],
        "staged": [],
        "dirty_tracked": [
            "README.md",
            "ez_back_dev/tests/test_iteration4_release_contracts.py",
        ],
        "untracked": [
            "docs/iteration-5-overview.md",
            "docs/iteration-5-prompts.md",
            "ez_back_dev/tests/test_iteration5_planning_contracts.py",
        ],
    }


def test_key_manifest_entry_hashes_are_explicit_not_runtime_generated():
    baseline = _load("ez_back_dev/tests/fixtures/iteration5_baseline_manifest_v1.json")
    migration = _load(
        "ez_back_dev/tests/fixtures/iteration5_version_migration_v1.json"
    )
    mutable = (
        set(migration["mutable_active_paths"])
        | _aspect3_style_changed_paths()
        | _aspect4_backend_changed_paths()
        | _aspect5_structure_changed_paths()
        | _later_reviewed_paths()
    )
    assert baseline["auto_accept_current_values"] is False
    assert baseline["files"]
    for relative, entry in baseline["files"].items():
        if relative in mutable:
            continue
        path = _repo_path(relative)
        assert path.is_file(), relative
        assert entry["sha256"] == _normalized_sha256(path), relative
        # The baseline was captured on Windows; accept only its raw size or
        # the exact canonical LF/CRLF representation of the same bytes.
        assert entry["size_bytes"] in _platform_size_variants(path), relative


def test_version_migration_fixture_records_manual_post_change_hashes():
    baseline = _load("ez_back_dev/tests/fixtures/iteration5_baseline_manifest_v1.json")
    migration = _load(
        "ez_back_dev/tests/fixtures/iteration5_version_migration_v1.json"
    )
    assert migration["schema_version"] == "iteration5-version-migration-v1"
    assert migration["aspect"] == 2
    assert migration["hash_policy"] == "sha256_canonical_lf_v1"
    assert migration["manual_reviewed"] is True
    assert migration["auto_accept_current_values"] is False
    assert migration["parent"]["fixture"] == (
        "ez_back_dev/tests/fixtures/iteration5_baseline_manifest_v1.json"
    )
    assert migration["parent"]["fixture_sha256"] == _normalized_sha256(
        _repo_path(migration["parent"]["fixture"])
    )
    mutable = set(migration["mutable_active_paths"])
    style_changed = _aspect3_style_changed_paths()
    backend_changed = _aspect4_backend_changed_paths()
    structure_changed = _aspect5_structure_changed_paths()
    later_changed = _later_reviewed_paths()
    immutable = set(migration["immutable_paths"])
    assert mutable.isdisjoint(immutable)
    assert mutable
    assert immutable
    assert set(migration["post_change_sha256"]) == mutable
    for relative, expected in migration["post_change_sha256"].items():
        if (
            relative in style_changed
            or relative in backend_changed
            or relative in structure_changed
            or relative in later_changed
        ):
            continue
        assert expected == _normalized_sha256(_repo_path(relative)), relative
    for relative in immutable - style_changed - backend_changed - later_changed:
        assert relative in baseline["files"], relative
        assert baseline["files"][relative]["sha256"] == _normalized_sha256(
            _repo_path(relative)
        ), relative


def test_historical_evidence_hashes_are_separately_identified():
    baseline = _load("ez_back_dev/tests/fixtures/iteration5_baseline_manifest_v1.json")
    historical = {
        path: entry
        for path, entry in baseline["files"].items()
        if entry["classification"] == "Historical evidence"
    }
    assert {
        "docs/iteration-4-overview.md",
        "docs/iteration-4-closeout.md",
        "docs/iteration-4-live-model-acceptance.md",
        "docs/iteration-4-development-log.md",
        "ez_back_dev/tests/fixtures/iteration3_contract_baseline_v1.json",
        "ez_back_dev/tests/fixtures/iteration4_release_manifest_v1.json",
    } <= set(historical)


def test_iteration4_contracts_are_protected_by_static_baseline_expectations():
    contract = _load("ez_back_dev/tests/fixtures/iteration3_contract_baseline_v1.json")
    assert contract["workflow_count"] == 19
    assert len(contract["workflows"]) == 19
    assert contract["retention"]["preliminary_analysis"] == "persisted"
    assert set(contract["retention"]["session_only_case_operations"]) == {
        "api_case",
        "functional_case",
        "integration_case",
        "nonfunctional_case",
        "unit_case",
    }
    assert set(contract["retention"]["persisted_case_operations"]) == {
        "acceptance_case",
        "db_case",
        "ui_case",
    }
    assert "reasoning_delta" in contract["sse_events"]

    catalog = (ROOT / "ez_back_dev/service/workflow/catalog.py").read_text(encoding="utf-8")
    registry = (ROOT / "ez_back_dev/service/agent/tool_registry.py").read_text(encoding="utf-8")
    router = (ROOT / "ez_back_dev/app/routers.py").read_text(encoding="utf-8")
    mcp = (ROOT / "ez_back_dev/service/agent/mcp_adapter.py").read_text(encoding="utf-8")
    checkpoint = (ROOT / "ez_back_dev/service/agent/checkpoint.py").read_text(encoding="utf-8")
    stream_core = (ROOT / "ez_back_dev/service/workflow/stream_core.py").read_text(encoding="utf-8")
    assert catalog.count("operation=") == 19
    assert "ToolRegistry((*reads, *workflows))" in registry
    assert "TOOL_CATALOG_URI" in mcp
    assert "APPROVAL_POLICY_URI" in mcp
    assert "/project/llm/workflow/stream" in router
    assert "reasoning_delta" in stream_core
    assert "JsonPlusSerializer" in checkpoint
    assert "no pickle or msgpack" in checkpoint


def test_protected_boundaries_are_not_in_the_cleanup_allowlist():
    allowlist = _load(
        "ez_back_dev/tests/fixtures/iteration5_cleanup_allowlist_v1.json"
    )
    assert allowlist["schema_version"] == "iteration5-cleanup-allowlist-v1"
    assert allowlist["apply_enabled"] is False
    assert allowlist["matching_policy"] == "enumerate_then_review_exact_paths"
    assert set(allowlist["protected_prefixes"]) >= {
        ".env",
        "example/",
        "ez_back_dev/static/projects/",
        "declared_compose_volumes",
        "external_service_data",
    }
    forbidden = tuple(allowlist["protected_prefixes"])
    for item in allowlist["exact_paths"]:
        assert not item.startswith(forbidden)
        assert "*" not in item
        assert "?" not in item


def test_inventory_and_development_log_keep_aspect_boundaries_explicitly():
    inventory = _load("ez_back_dev/tests/fixtures/iteration5_asset_inventory_v1.json")
    log = _repo_path("docs/iteration-5-development-log.md").read_text(encoding="utf-8")
    assert inventory["aspect"] == 1
    assert inventory["auto_accept_current_values"] is False
    assert "## Aspect 1" in log
    assert "## Aspect 2" in log
    assert "Aspect 3" in log
    assert "## Aspect 4" in log
    assert "## Aspect 5" in log
    assert "\n## Aspect 6" in log
    assert "\n## Aspect 7" in log
    assert "\n## Aspect 8" in log


def test_aspect3_style_baseline_and_migration_are_reviewed():
    baseline = _load("ez_back_dev/tests/fixtures/iteration5_style_baseline_v1.json")
    migration = _load("ez_back_dev/tests/fixtures/iteration5_style_migration_v1.json")
    assert baseline["schema_version"] == "iteration5-style-baseline-v1"
    assert baseline["aspect"] == 3
    assert baseline["manual_reviewed"] is True
    assert baseline["auto_accept_current_values"] is False
    assert baseline["parent"]["fixture"] == "ez_back_dev/tests/fixtures/iteration5_version_migration_v1.json"
    assert baseline["parent"]["fixture_sha256"] == _normalized_sha256(
        _repo_path(baseline["parent"]["fixture"])
    )
    assert set(baseline["files"]) == set(baseline["format_scope"])
    assert migration["schema_version"] == "iteration5-style-migration-v1"
    assert migration["aspect"] == 3
    assert migration["manual_reviewed"] is True
    assert migration["auto_accept_current_values"] is False
    assert migration["parent"]["fixture"] == "ez_back_dev/tests/fixtures/iteration5_style_baseline_v1.json"
    assert migration["parent"]["fixture_sha256"] == _normalized_sha256(
        _repo_path(migration["parent"]["fixture"])
    )
    assert len(migration["batches"]) >= 3
    assert all(batch["manual_reviewed"] is True for batch in migration["batches"])
