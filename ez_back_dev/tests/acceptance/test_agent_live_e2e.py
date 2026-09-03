import json

import pytest

from scripts import agent_live_e2e


def test_live_e2e_requires_explicit_cost_confirmation():
    with pytest.raises(SystemExit, match="--confirm-cost"):
        agent_live_e2e.main([])


@pytest.mark.parametrize(
    "value",
    (
        None,
        "redis://redis:6379/0",
        "redis://user:secret@127.0.0.1:6379/0",
        "redis://example.com:6379/0",
        "http://127.0.0.1:6379/0",
        "redis://127.0.0.1:6379/1",
    ),
)
def test_live_e2e_rejects_nonisolated_redis(value):
    with pytest.raises(agent_live_e2e.LiveE2EError):
        agent_live_e2e.validate_loopback_redis_url(value)


def test_live_e2e_accepts_only_credential_free_loopback_db_zero():
    assert (
        agent_live_e2e.validate_loopback_redis_url(
            "redis://127.0.0.1:6399/0"
        )
        == "redis://127.0.0.1:6399/0"
    )
    assert agent_live_e2e.EXPECTED_OPERATIONS == ("ui_info", "ui_case")


def test_live_e2e_public_report_rejects_sensitive_fields():
    for field in (
        "api_key",
        "artifact_content",
        "connection_string",
        "credential",
        "database_url",
        "document_content",
        "goal",
        "password",
        "project_id",
        "prompt",
        "reasoning",
        "response_content",
        "traceback",
    ):
        with pytest.raises(agent_live_e2e.LiveE2EError):
            agent_live_e2e.validate_safe_report({field: "sentinel"})


def test_live_e2e_safe_report_is_json_serializable():
    report = {
        "schema_version": 1,
        "trajectory": ["ui_info", "ui_case"],
        "approvals": 2,
        "gate": {"passed": True},
    }
    agent_live_e2e.validate_safe_report(report)
    assert json.loads(json.dumps(report)) == report


def test_live_e2e_artifact_shape_accepts_real_workflow_contract():
    ui_info = json.dumps(
        {"operation": "ui_info", "result": "synthetic analysis"}
    )
    ui_case = json.dumps(
        {
            "operation": "ui_case",
            "result": {
                "test_cases": "synthetic cases",
                "ui_test_knowledge": "synthetic knowledge",
            },
        }
    )
    assert agent_live_e2e._artifact_result_is_nonempty(ui_info, "ui_info")
    assert agent_live_e2e._artifact_result_is_nonempty(ui_case, "ui_case")
