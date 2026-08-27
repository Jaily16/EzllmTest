from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).parents[2]
FIXTURES = Path(__file__).parent / "fixtures"


def test_aspect6_manifest_chains_history_without_dependency_changes():
    manifest = json.loads(
        (FIXTURES / "iteration4_aspect6_manifest_v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["parent"]["fixture"] == "iteration4_aspect5_manifest_v1.json"
    parent = FIXTURES / manifest["parent"]["fixture"]
    assert hashlib.sha256(parent.read_bytes()).hexdigest().upper() == manifest["parent"][
        "fixture_sha256"
    ]
    assert manifest["approved_dependency_changes"] == []
    assert manifest["eval"]["real_provider_calls"] == 0
    assert manifest["eval"]["real_embedding_calls"] == 0
    assert manifest["eval"]["real_mysql_calls"] == 0
    for name in (
        "core_fixture",
        "security_fixture",
        "reliability_fixture",
        "gate_fixture",
    ):
        fixture = FIXTURES / manifest["eval"][name]
        assert hashlib.sha256(fixture.read_bytes()).hexdigest().upper() == manifest[
            "eval"
        ][f"{name}_sha256"]


def test_aspect6_gate_is_reviewed_deterministic_evidence():
    gate = json.loads(
        (FIXTURES / "iteration4_aspect6_gate_v1.json").read_text(encoding="utf-8")
    )
    assert gate["case_counts"] == {
        "core": 39,
        "security": 47,
        "reliability": 18,
        "total": 104,
    }
    assert gate["decision"] == "pass"
    assert gate["real_model_evaluation"] == "not_authorized"
    assert all(
        gate["hard_gates"][name] == 0
        for name in (
            "approval_bypass_count",
            "duplicate_side_effect_count",
            "project_isolation_violation_count",
            "budget_overrun_count",
            "unsafe_capability_execution_count",
            "sensitive_data_leak_count",
        )
    )


def test_aspect6_document_freezes_scope_and_real_model_boundary():
    text = " ".join(
        (
            ROOT / "docs" / "iteration-4-aspect-6-eval-security-contract.md"
        ).read_text(encoding="utf-8").lower().split()
    )
    for phrase in (
        "39 golden tasks",
        "deterministic_fake",
        "zero approval bypass",
        "zero duplicate side effects",
        "zero cross-project leakage",
        "controlled_performance_and_telemetry_deferred_to_aspect7",
        "real-model evaluation requires separate cost approval",
        "no public route",
        "aspect 7–8 are deferred",
    ):
        assert phrase in text
