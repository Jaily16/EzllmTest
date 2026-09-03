import asyncio

import pytest

from service.agentContracts import AgentRunState, RunBudget, ToolRisk, TrustedProjectScope
from service.agentPlanner import (
    PlannerOutputError,
    ProviderAgentPlanner,
    build_planner_provider_prompt,
    compile_planned_calls,
)
from service.agentRuntimeContracts import ProjectObservation


def _state() -> AgentRunState:
    return AgentRunState(
        run_id="run-1",
        thread_id="thread-1",
        project_scope=TrustedProjectScope(
            project_id="project-a", actor_id="actor-a", scope_version="1"
        ),
        source_revision="revision-1",
        goal="Generate UI test cases",
        budget=RunBudget(
            max_steps=3,
            max_elapsed_ms=60_000,
            max_input_tokens=2_000,
            max_output_tokens=2_000,
            max_model_calls=3,
            max_embedding_calls=1,
            max_tool_calls=3,
            max_estimated_cost_units=10_000,
        ),
    )


def test_provider_planner_receives_only_safe_summary_and_registry_metadata():
    captured = {}

    async def provider(request):
        captured.update(request)
        return {
            "steps": [
                {
                    "tool_name": "workflow_ui_case",
                    "arguments": {},
                }
            ]
        }

    planner = ProviderAgentPlanner(provider)
    observation = ProjectObservation(
        setup_stage="setup_complete",
        analysis_ready=True,
        workflow_stage="analysis_ready",
        source_revision="revision-1",
    )
    proposal = asyncio.run(
        planner.plan(goal="Generate UI tests", observation=observation, max_steps=3)
    )

    assert proposal.steps[0].tool_name == "workflow_ui_case"
    assert set(captured) == {"schema_version", "goal", "observation", "tools", "max_steps"}
    serialized = str(captured).lower()
    assert "project-a" not in serialized
    assert "document_body" not in serialized
    assert "reasoning" not in serialized
    ui_case = next(
        tool for tool in captured["tools"] if tool["operation"] == "ui_case"
    )
    assert "info" not in ui_case["input_schema"]["properties"]


def test_planner_provider_prompt_freezes_json_only_output_contract():
    request = {
        "schema_version": 1,
        "goal": "Generate UI tests",
        "observation": {"workflow_stage": "analysis_ready"},
        "tools": [
            {
                "name": "workflow_ui_case",
                "operation": "ui_case",
                "input_schema": {
                    "type": "object",
                    "properties": {"regenerate": {"type": "boolean"}},
                },
            }
        ],
        "max_steps": 1,
    }

    prompt = build_planner_provider_prompt(request)

    assert "Return exactly one JSON object" in prompt
    assert '"schema_version":1' in prompt
    assert '"steps"' in prompt
    assert '"tool_name"' in prompt
    assert '"arguments"' in prompt
    assert "No Markdown" in prompt
    assert "untrusted data" in prompt
    assert '"goal":"Generate UI tests"' in prompt
    assert "project_id" not in prompt


@pytest.mark.parametrize(
    "response",
    [
        {"steps": [{"tool_name": "project_setup_status", "arguments": {}}]},
        {"steps": [{"tool_name": "workflow_unknown", "arguments": {}}]},
        {
            "steps": [
                {
                    "tool_name": "workflow_ui_case",
                    "arguments": {"project_id": "project-b"},
                }
            ]
        },
        {
            "steps": [
                {
                    "tool_name": "workflow_ui_case",
                    "arguments": {"model_label": "model-choice"},
                }
            ]
        },
        {
            "steps": [
                {
                    "tool_name": "workflow_ui_case",
                    "arguments": {"info": "model-supplied artifact body"},
                }
            ]
        },
        {"steps": []},
        {"steps": "not-a-list"},
    ],
)
def test_provider_planner_rejects_non_catalog_or_runtime_owned_fields(response):
    async def provider(_request):
        return response

    planner = ProviderAgentPlanner(provider)
    with pytest.raises(PlannerOutputError):
        asyncio.run(
            planner.plan(
                goal="Generate tests",
                observation=ProjectObservation(
                    setup_stage="setup_complete",
                    analysis_ready=True,
                    workflow_stage="analysis_ready",
                    source_revision="revision-1",
                ),
                max_steps=3,
            )
        )


def test_runtime_compiles_model_proposal_with_derived_risk_model_and_idempotency():
    async def provider(_request):
        return {
            "steps": [
                {
                    "tool_name": "workflow_ui_case",
                    "arguments": {"regenerate": True},
                }
            ]
        }

    proposal = asyncio.run(
        ProviderAgentPlanner(provider).plan(
            goal="Generate tests",
            observation=ProjectObservation(
                setup_stage="setup_complete",
                analysis_ready=True,
                workflow_stage="analysis_ready",
                source_revision="revision-1",
            ),
            max_steps=3,
        )
    )
    calls = compile_planned_calls(
        _state(), proposal, execution_model="runtime-selected-model"
    )

    assert len(calls) == 1
    call = calls[0]
    assert call.operation == "ui_case"
    assert call.model_label == "runtime-selected-model"
    assert call.arguments == {"regenerate": True}
    assert call.risks == frozenset(
        {ToolRisk.PAID, ToolRisk.PERSISTENT, ToolRisk.REGENERATE}
    )
    assert call.idempotency_key.startswith("run-1:")
    replanned = compile_planned_calls(
        _state().model_copy(update={"plan_version": 1}),
        proposal,
        execution_model="runtime-selected-model",
    )
    assert replanned[0].idempotency_key != call.idempotency_key
