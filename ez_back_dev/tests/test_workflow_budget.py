import json
from dataclasses import fields

import pytest

from llm.provider import provider_options
from model.ChainJsonModel import QualifiedUnitTestMenu
from prompt.templates import (
    COMMON_GROUNDED_RULES,
    build_grounded_prompt,
    build_structured_output_prompt,
)
from service.workflowBudget import (
    WorkflowBudgetProfile,
    bound_prompt_context,
    profile_for,
    select_within_token_budget,
)
from service.workflowCatalog import list_workflow_definitions
from tools.documentTools import num_tokens_from_string


def _word_tokens(text: str) -> int:
    return len(text.split())


def test_profiles_cover_every_workflow_with_stage_specific_hard_caps():
    operations = {item.operation for item in list_workflow_definitions()}

    for operation in operations:
        map_profile = profile_for(operation, "map")
        structured = profile_for(operation, "structured")
        final = profile_for(operation, "final")

        assert isinstance(final, WorkflowBudgetProfile)
        assert map_profile.reasoning_mode == "off"
        assert structured.reasoning_mode == "off"
        assert final.reasoning_mode == "balanced"
        assert map_profile.output_token_limit <= 1_024
        structured_cap = 12_288 if operation == "unit_menu" else 2_048
        assert structured.output_token_limit <= structured_cap
        if operation != "unit_menu":
            assert final.output_token_limit > structured.output_token_limit
        assert final.output_token_limit <= 12_288
        assert 0 < final.max_context_tokens <= 64_000

    assert {item.name for item in fields(WorkflowBudgetProfile)} >= {
        "map_output_tokens",
        "structured_output_tokens",
        "final_output_tokens",
        "max_context_tokens",
        "reasoning_mode",
        "reasoning_budget",
    }


def test_provider_options_disable_mechanical_reasoning_and_bound_qwen():
    structured = profile_for("api_info", "structured")
    final = profile_for("api_case", "final")

    qwen_structured = provider_options(structured, "通义千问")
    qwen_final = provider_options(final, "通义千问")
    deepseek = provider_options(structured, "DeepSeek")
    glm = provider_options(structured, "GLM-4.7")
    kimi = provider_options(structured, "Moonshot Kimi")

    assert qwen_structured["max_tokens"] <= 2_048
    assert qwen_structured["enable_thinking"] is False
    assert qwen_structured["extra_body"] == {"enable_thinking": False}
    assert qwen_final["extra_body"]["enable_thinking"] is True
    assert qwen_final["enable_thinking"] is True
    assert 0 < qwen_final["extra_body"]["thinking_budget"] <= 4_096
    assert qwen_final["extra_body"]["thinking_budget"] <= qwen_final["max_tokens"]
    assert "reasoning_effort" not in deepseek
    assert deepseek["extra_body"] == {"thinking": {"type": "disabled"}}
    assert glm["extra_body"] == {"thinking": {"type": "disabled"}}
    assert kimi["extra_body"] == {"thinking": {"type": "disabled"}}


def test_exhaustive_qualified_unit_menu_has_a_non_truncating_output_budget():
    structured = profile_for("unit_menu", "structured")

    def reference(kind, index):
        return {
            "display_name": f"{kind}{index}方法",
            "qualified_name": (
                f"课程子系统/业务模块/ExampleService{index // 10}."
                f"{kind}{index}(Long userId, String value)"
            ),
            "source_hint": f"详细设计规约 第4.{index // 20 + 1}.{index % 20 + 1}节",
        }
    large_menu = QualifiedUnitTestMenu.model_validate(
        {
            "subsystem_menu": {
                "subsystem_test": True,
                "subsystem_list": [reference("子系统", index) for index in range(5)],
            },
            "module_menu": {
                "module_test": True,
                "module_list": [reference("模块", index) for index in range(10)],
            },
            "class_menu": {
                "class_test": True,
                "class_list": [reference("类", index) for index in range(30)],
            },
            "function_menu": {
                "function_test": True,
                "function_list": [reference("函数", index) for index in range(100)],
            },
        }
    )
    output_tokens = num_tokens_from_string(
        json.dumps(large_menu.model_dump(), ensure_ascii=False)
    )

    assert output_tokens > 8_192
    assert structured.output_token_limit >= output_tokens
    assert structured.reasoning_mode == "off"


def test_context_selection_is_deterministic_and_never_exceeds_budget():
    chunks = ["one two", "three four", "five"]

    selected = select_within_token_budget(
        chunks,
        4,
        token_counter=_word_tokens,
    )
    bounded = bound_prompt_context(
        "instruction",
        "one two three four five six",
        4,
        token_counter=_word_tokens,
    )

    assert selected == ["one two", "three four"]
    assert sum(_word_tokens(item) for item in selected) <= 4
    assert bounded.reduced is True
    assert bounded.input_context_tokens == 6
    assert bounded.selected_context_tokens <= 4


def test_prompt_preflight_preserves_instruction_head_and_business_tail():
    bounded = bound_prompt_context(
        "",
        "instruction-head middle-one middle-two business-tail",
        3,
        token_counter=_word_tokens,
    )

    assert bounded.selected_context_tokens <= 3
    assert "instruction-head" in bounded.prompt
    assert "business-tail" in bounded.prompt


def test_prompt_preflight_never_spends_document_budget_on_instructions():
    bounded = bound_prompt_context(
        "REQUIRED_SCHEMA must remain intact",
        "one two three four five six",
        3,
        token_counter=_word_tokens,
    )

    assert bounded.prompt.startswith("REQUIRED_SCHEMA must remain intact\n\n")
    assert bounded.selected_context_tokens <= 3


def test_shared_prompt_builders_include_context_and_schema_once():
    context = "UNIQUE_RAG_CONTEXT"
    schema = '{"type":"object"}'

    grounded = build_grounded_prompt(
        "回答接口测试问题",
        context,
        context_label="检索上下文",
    )
    structured = build_structured_output_prompt(
        f"从 {context} 提取接口",
        schema,
    )

    assert grounded.count(context) == 1
    assert grounded.count(COMMON_GROUNDED_RULES) == 1
    assert structured.count(context) == 1
    assert structured.count(schema) == 1
    assert structured.index(schema) < structured.index(context)


@pytest.mark.parametrize("stage", ["map", "structured", "final"])
def test_public_budget_metadata_contains_no_content(stage):
    metadata = profile_for("unit_info", stage).public_metadata()

    assert set(metadata) == {
        "stage",
        "map_output_tokens",
        "structured_output_tokens",
        "final_output_tokens",
        "max_context_tokens",
        "reasoning_mode",
        "reasoning_budget",
    }
    assert all(
        forbidden not in str(metadata).lower()
        for forbidden in ("prompt", "document", "reasoning_content", "api_key")
    )
