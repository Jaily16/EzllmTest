from service.longTextPolicy import (
    LONG_TEXT_POLICIES,
    LongTextStrategy,
    effective_context_budget,
    strategy_for,
)
from service.workflowCatalog import WORKFLOW_DEFINITIONS


def test_every_streamed_workflow_has_an_explicit_long_text_policy():
    assert set(LONG_TEXT_POLICIES) == {
        definition.operation for definition in WORKFLOW_DEFINITIONS
    }


def test_exhaustive_workflows_stuff_then_map_reduce():
    assert strategy_for("project_analysis", 63_999) is LongTextStrategy.STUFF
    assert (
        strategy_for("project_analysis", 64_001)
        is LongTextStrategy.MAP_REDUCE
    )
    for operation in (
        "unit_menu",
        "api_info",
        "ui_info",
        "db_info",
        "functional_info",
        "acceptance_info",
    ):
        assert strategy_for(operation, 31_999) is LongTextStrategy.STUFF
        assert (
            strategy_for(operation, 32_001)
            is LongTextStrategy.MAP_REDUCE
        )


def test_focused_and_artifact_workflows_never_refine_or_map_retrieved_context():
    for operation in (
        "unit_info",
        "integration_info",
        "nonfunctional_info",
    ):
        assert (
            strategy_for(operation, 200_000)
            is LongTextStrategy.RETRIEVAL_STUFF
        )
    for operation in (
        "unit_case",
        "integration_case",
        "api_case",
        "ui_case",
        "db_case",
        "functional_case",
        "nonfunctional_case",
        "acceptance_case",
    ):
        assert (
            strategy_for(operation, 200_000)
            is LongTextStrategy.ARTIFACT_STUFF
        )
    assert all(policy.overflow_strategy != "refine" for policy in LONG_TEXT_POLICIES.values())


def test_effective_budget_reserves_model_output_reasoning_and_safety_margin():
    assert effective_context_budget("project_analysis", "final", "GLM-4.7") >= 64_000
    assert effective_context_budget("project_analysis", "final", "通义千问") >= 64_000
    assert effective_context_budget("project_analysis", "final", "DeepSeek") >= 64_000
    assert effective_context_budget("project_analysis", "final", "Moonshot Kimi") >= 64_000
