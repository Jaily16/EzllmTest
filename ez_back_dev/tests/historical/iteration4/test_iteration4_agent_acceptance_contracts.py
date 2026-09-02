import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from service.agentAcceptanceContracts import (
    ACCEPTANCE_SEED,
    AcceptanceDataset,
    AcceptanceRunReport,
    AcceptanceSuite,
)
from service.agentAcceptanceRunner import load_acceptance_dataset
from repo_paths import fixture_path


FIXTURE = fixture_path("historical", "iteration4", "iteration4_agent_acceptance_v1.json")


def test_acceptance_dataset_is_strict_versioned_and_complete():
    dataset = load_acceptance_dataset(FIXTURE)
    assert dataset.seed == ACCEPTANCE_SEED
    assert dataset.provider == "deterministic_fake"
    assert dataset.projects == ("alpha", "alpine")
    assert len(dataset.cases) == 18
    assert {case.suite for case in dataset.cases} == {
        AcceptanceSuite.JOURNEY,
        AcceptanceSuite.RELIABILITY,
        AcceptanceSuite.PROTOCOL,
    }
    assert len({case.id for case in dataset.cases}) == len(dataset.cases)


def test_acceptance_contracts_forbid_unknown_and_sensitive_report_fields():
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    raw["unexpected"] = True
    with pytest.raises(ValidationError):
        AcceptanceDataset.model_validate(raw)

    assert "goal" not in AcceptanceRunReport.model_fields
    assert "prompt" not in AcceptanceRunReport.model_fields
    assert "reasoning" not in AcceptanceRunReport.model_fields
    assert "project_id" not in AcceptanceRunReport.model_fields
    assert "trace_id" not in AcceptanceRunReport.model_fields


def test_duplicate_json_keys_are_rejected(tmp_path):
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"schema_version":1,"schema_version":1}', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        load_acceptance_dataset(duplicate)
