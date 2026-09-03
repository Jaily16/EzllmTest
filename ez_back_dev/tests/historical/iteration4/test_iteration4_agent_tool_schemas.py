import pytest
from pydantic import ValidationError

from service.agentToolSchemas import (
    TOOL_INPUT_MODELS,
    ToolExecutionResult,
    ToolExecutionStatus,
)


EXPECTED_PAYLOAD_FIELDS = {
    "project_analysis": set(),
    "unit_menu": set(),
    "unit_info": {"unit", "unit_type"},
    "unit_case": {
        "method_type",
        "static_method",
        "unit",
        "unit_type",
        "unit_info",
        "output_type",
    },
    "integration_menu": {"units_info"},
    "integration_info": {"integration_type", "name"},
    "integration_case": {
        "strategy_type",
        "strategy",
        "integration_object",
        "integration_object_info",
        "output_type",
    },
    "api_info": set(),
    "api_case": {"info", "test_type", "output_type", "api_name"},
    "ui_info": set(),
    "ui_case": {"info"},
    "db_info": set(),
    "db_case": {"info"},
    "functional_info": set(),
    "functional_case": {
        "info",
        "test_type",
        "output_type",
        "use_case_name",
    },
    "nonfunctional_info": set(),
    "nonfunctional_case": {"info", "method_name"},
    "acceptance_info": set(),
    "acceptance_case": {"info"},
}


def test_workflow_input_models_preserve_payload_fields_and_common_controls():
    assert set(TOOL_INPUT_MODELS) == set(EXPECTED_PAYLOAD_FIELDS)
    for operation, payload_fields in EXPECTED_PAYLOAD_FIELDS.items():
        fields = set(TOOL_INPUT_MODELS[operation].model_fields)
        assert fields == payload_fields | {"model_label", "regenerate"}


@pytest.mark.parametrize("operation", EXPECTED_PAYLOAD_FIELDS)
def test_workflow_inputs_forbid_project_scope_and_unknown_fields(operation):
    model = TOOL_INPUT_MODELS[operation]
    assert model.model_config["extra"] == "forbid"
    with pytest.raises(ValidationError):
        model.model_validate(
            {
                "model_label": "DeepSeek",
                "project_id": "model-controlled-project",
            }
        )


def test_conditional_names_match_existing_workflow_validation():
    integration = TOOL_INPUT_MODELS["integration_info"]
    assert integration(
        model_label="DeepSeek", integration_type=0, name=""
    ).name == ""
    with pytest.raises(ValidationError):
        integration(model_label="DeepSeek", integration_type=2, name="")

    api = TOOL_INPUT_MODELS["api_case"]
    api(
        model_label="DeepSeek",
        info="all APIs",
        test_type=0,
        output_type=0,
        api_name="",
    )
    with pytest.raises(ValidationError):
        api(
            model_label="DeepSeek",
            info="one API",
            test_type=1,
            output_type=0,
            api_name="",
        )

    functional = TOOL_INPUT_MODELS["functional_case"]
    functional(
        model_label="DeepSeek",
        info="all use cases",
        test_type=0,
        output_type=0,
        use_case_name="",
    )
    with pytest.raises(ValidationError):
        functional(
            model_label="DeepSeek",
            info="one use case",
            test_type=1,
            output_type=0,
            use_case_name="",
        )


def test_tool_result_is_strict_json_and_rejects_reasoning_payloads():
    result = ToolExecutionResult(
        tool_name="project_setup_status",
        status=ToolExecutionStatus.SUCCESS,
        data={"stage": "setup_complete"},
    )
    assert ToolExecutionResult.model_validate_json(result.model_dump_json()) == result
    with pytest.raises(ValidationError):
        ToolExecutionResult(
            tool_name="workflow_ui_case",
            operation="ui_case",
            status=ToolExecutionStatus.SUCCESS,
            data={"reasoning": "hidden chain of thought"},
        )
    with pytest.raises(ValidationError):
        ToolExecutionResult(
            tool_name="project_setup_status",
            status=ToolExecutionStatus.SUCCESS,
            unexpected=True,
        )
