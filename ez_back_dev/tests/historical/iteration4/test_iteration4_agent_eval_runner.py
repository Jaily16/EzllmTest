from __future__ import annotations

from service.agentEvalContracts import EvalSuite
from service.agentEvalRunner import run_eval


def test_core_eval_is_deterministic_and_all_hard_gates_pass():
    first = run_eval(EvalSuite.CORE)
    second = run_eval(EvalSuite.CORE)

    assert first == second
    assert len(first.results) == 39
    assert first.decision.passed
    metrics = {metric.name: metric for metric in first.metrics}
    for name in (
        "task_success",
        "trajectory_validity",
        "tool_selection_accuracy",
        "structured_output_validity",
    ):
        assert metrics[name].value == 1.0
    assert metrics["approval_bypass_count"].value == 0
    assert metrics["duplicate_side_effect_count"].value == 0
    assert metrics["project_isolation_violation_count"].value == 0
    assert metrics["otel_overhead_ratio"].value is None
    assert (
        metrics["otel_overhead_ratio"].reason
        == "controlled_performance_and_telemetry_deferred_to_aspect7"
    )


def test_report_contains_only_safe_case_level_evidence():
    report = run_eval(EvalSuite.CORE)
    serialized = report.model_dump_json().lower()
    for forbidden in (
        "prompt",
        "completion",
        "reasoning",
        "scratchpad",
        "traceback",
        "redis://",
        "document_sentinel",
    ):
        assert forbidden not in serialized


def test_core_and_security_do_not_reach_provider_embedding_mysql_or_network(
    monkeypatch,
):
    import socket

    from llm import provider
    from service import workflowArtifactService
    from vectorstore import retrievers

    def blocked(*_args, **_kwargs):
        raise AssertionError("offline Eval attempted a forbidden external path")

    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(provider, "get_chat_client", blocked)
    monkeypatch.setattr(provider, "get_embeddings", blocked)
    monkeypatch.setattr(workflowArtifactService, "lookup_workflow_artifact", blocked)
    monkeypatch.setattr(retrievers, "get_project_retriever", blocked)

    assert run_eval(EvalSuite.CORE).decision.passed
    assert run_eval(EvalSuite.SECURITY).decision.passed
