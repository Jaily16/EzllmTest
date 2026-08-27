from service.agentContracts import ToolRisk
from service.agentToolRegistry import (
    RAG_CAPABLE_OPERATIONS,
    build_default_tool_registry,
)
from service.workflowBudget import profile_for
from service.workflowCatalog import list_workflow_definitions


READ_TOOLS = (
    "project_setup_status",
    "project_analysis_status",
    "project_workflow_status",
)


def test_registry_has_three_reads_and_all_catalog_workflows_in_order():
    registry = build_default_tool_registry()
    definitions = list_workflow_definitions()

    assert registry.names()[:3] == READ_TOOLS
    assert registry.names()[3:] == tuple(
        f"workflow_{item.operation}" for item in definitions
    )
    assert len(registry.names()) == 22
    assert tuple(
        item.operation for item in registry.workflow_definitions()
    ) == tuple(item.operation for item in definitions)


def test_registry_derives_catalog_budget_risk_retention_and_idempotency():
    registry = build_default_tool_registry()
    for catalog_item in list_workflow_definitions():
        item = registry.get(f"workflow_{catalog_item.operation}")
        assert item.catalog is not None
        assert item.catalog.operation == catalog_item.operation
        assert item.catalog.persistence == catalog_item.persistence
        assert item.budget is not None
        assert item.budget.final == profile_for(
            catalog_item.operation, "final"
        ).public_metadata()
        assert ToolRisk.PAID in item.base_risks
        if catalog_item.persistence == "artifact":
            assert ToolRisk.PERSISTENT in item.base_risks
            assert item.retention == "artifact"
            assert item.idempotency_scope == "artifact_identity"
        else:
            assert ToolRisk.PERSISTENT not in item.base_risks
            assert item.retention == "session"
            assert item.idempotency_scope == "run_step"

        normal = item.resolve_risks(regenerate=False)
        regenerate = item.resolve_risks(regenerate=True)
        assert normal == item.base_risks
        assert regenerate == frozenset(
            {ToolRisk.PAID, ToolRisk.PERSISTENT, ToolRisk.REGENERATE}
        )


def test_read_tools_have_no_model_embedding_approval_or_retention():
    registry = build_default_tool_registry()
    for name in READ_TOOLS:
        item = registry.get(name)
        assert item.base_risks == frozenset({ToolRisk.READ_ONLY})
        assert item.budget is None
        assert item.rag_capable is False
        assert item.retention == "none"
        assert item.idempotency_scope == "none"
        assert item.cancellation == "none"


def test_rag_capability_is_explicit_and_does_not_expand_to_all_workflows():
    expected = {
        "unit_info",
        "integration_info",
        "nonfunctional_info",
        "unit_case",
        "integration_case",
        "api_case",
        "ui_case",
        "db_case",
        "functional_case",
        "nonfunctional_case",
        "acceptance_case",
    }
    assert RAG_CAPABLE_OPERATIONS == frozenset(expected)
    registry = build_default_tool_registry()
    actual = {
        item.operation
        for item in registry.workflow_definitions()
        if item.rag_capable
    }
    assert actual == expected


def test_public_tool_schemas_never_expose_trusted_runtime_fields():
    forbidden = {
        "pid",
        "project_id",
        "actor_id",
        "scope",
        "approval",
        "idempotency_key",
        "api_key",
        "prompt",
        "reasoning",
    }
    registry = build_default_tool_registry()
    for item in registry.definitions():
        schema = item.input_schema()
        assert forbidden.isdisjoint(schema.get("properties", {}))
        assert item.output_schema() == registry.output_model.model_json_schema()
