import os
from dataclasses import FrozenInstanceError

import pytest


os.environ["PYTHON_DOTENV_DISABLED"] = "1"
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
for provider_key in (
    "ZHIPU_API_KEY",
    "DASHSCOPE_API_KEY",
    "DEEPSEEK_API_KEY",
    "MOONSHOT_API_KEY",
):
    os.environ[provider_key] = ""

from service.llmWorkflowStreamService import SUPPORTED_WORKFLOW_OPERATIONS
from service.workflowCatalog import (
    WORKFLOW_DEFINITIONS,
    get_workflow_definition,
    list_workflow_definitions,
)


EXPECTED_OPERATIONS = {
    "project_analysis",
    "unit_menu",
    "unit_info",
    "unit_case",
    "integration_menu",
    "integration_info",
    "integration_case",
    "api_info",
    "api_case",
    "ui_info",
    "ui_case",
    "db_info",
    "db_case",
    "functional_info",
    "functional_case",
    "nonfunctional_info",
    "nonfunctional_case",
    "acceptance_info",
    "acceptance_case",
}

SESSION_ONLY_OPERATIONS = {
    "unit_case",
    "integration_case",
    "api_case",
    "functional_case",
    "nonfunctional_case",
}

EXPECTED_LEGACY_INFO_TYPES = {
    "project_analysis": (1, 22, 23),
    "unit_menu": (2,),
    "unit_info": (),
    "unit_case": (3, 4, 5),
    "integration_menu": (2,),
    "integration_info": (),
    "integration_case": (6, 4, 7, 8, 9, 10),
    "api_info": (11,),
    "api_case": (12,),
    "ui_info": (13,),
    "ui_case": (14,),
    "db_info": (15,),
    "db_case": (16,),
    "functional_info": (17,),
    "functional_case": (18,),
    "nonfunctional_info": (19,),
    "nonfunctional_case": (),
    "acceptance_info": (20,),
    "acceptance_case": (21,),
}

EXPECTED_SELECTION_FIELDS = {
    "project_analysis": (),
    "unit_menu": (),
    "unit_info": ("unit_type", "unit"),
    "unit_case": ("method_type", "static_method", "unit_type", "unit", "output_type"),
    "integration_menu": (),
    "integration_info": ("integration_type", "name"),
    "integration_case": (
        "strategy_type",
        "strategy",
        "integration_object",
        "output_type",
    ),
    "api_info": (),
    "api_case": ("test_type", "output_type", "api_name"),
    "ui_info": (),
    "ui_case": (),
    "db_info": (),
    "db_case": (),
    "functional_info": (),
    "functional_case": ("test_type", "output_type", "use_case_name"),
    "nonfunctional_info": (),
    "nonfunctional_case": ("method_name",),
    "acceptance_info": (),
    "acceptance_case": (),
}

EXPECTED_PREREQUISITE_PAYLOAD_FIELDS = {
    "project_analysis": (),
    "unit_menu": (),
    "unit_info": ("unit",),
    "unit_case": ("unit_info",),
    "integration_menu": (),
    "integration_info": ("integration_type",),
    "integration_case": ("integration_object_info",),
    "api_info": (),
    "api_case": ("info",),
    "ui_info": (),
    "ui_case": ("info",),
    "db_info": (),
    "db_case": ("info",),
    "functional_info": (),
    "functional_case": ("info",),
    "nonfunctional_info": (),
    "nonfunctional_case": ("info",),
    "acceptance_info": (),
    "acceptance_case": ("info",),
}


def test_workflow_catalog_is_complete_and_unique():
    definitions = list_workflow_definitions()

    assert definitions == WORKFLOW_DEFINITIONS
    assert {item.operation for item in definitions} == EXPECTED_OPERATIONS
    assert len({item.operation for item in definitions}) == len(definitions)
    assert len({item.result_artifact for item in definitions}) == len(definitions)


def test_workflow_catalog_carries_task_5_persistence_metadata():
    definitions = list_workflow_definitions()

    assert {
        item.operation: item.legacy_info_types for item in definitions
    } == EXPECTED_LEGACY_INFO_TYPES
    assert {
        item.operation: item.selection_fields for item in definitions
    } == EXPECTED_SELECTION_FIELDS
    assert {
        item.operation: item.prerequisite_payload_fields for item in definitions
    } == EXPECTED_PREREQUISITE_PAYLOAD_FIELDS
    assert all(
        item.prompt_version
        == (
            "project-analysis-v2"
            if item.operation == "project_analysis"
            else "unit-menu-v2"
            if item.operation == "unit_menu"
            else "unit-info-v2"
            if item.operation == "unit_info"
            else f"{item.operation.replace('_', '-')}-v1"
        )
        for item in definitions
    )
    assert all(
        len(item.prompt_version) <= 32 and item.prompt_version.strip()
        for item in definitions
    )
    assert {
        item.operation for item in definitions if item.persistence == "session"
    } == SESSION_ONLY_OPERATIONS
    assert {
        item.operation for item in definitions if item.persistence == "artifact"
    } == EXPECTED_OPERATIONS - SESSION_ONLY_OPERATIONS


def test_workflow_catalog_matches_the_existing_generic_dispatcher():
    catalog_operations = EXPECTED_OPERATIONS - {"project_analysis"}

    assert catalog_operations == SUPPORTED_WORKFLOW_OPERATIONS


def test_workflow_definitions_are_immutable_and_addressable():
    definition = get_workflow_definition("project_analysis")

    assert definition.phase == "project"
    with pytest.raises(FrozenInstanceError):
        definition.operation = "changed"  # type: ignore[misc]


def test_unknown_workflow_definition_is_rejected():
    with pytest.raises(KeyError, match="unknown_operation"):
        get_workflow_definition("unknown_operation")
