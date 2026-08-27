import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from service.agentContext import (
    AgentContextAssembler,
    ContextArtifact,
    ContextAssemblyError,
    context_payload_fields,
)
from service.agentContracts import (
    AgentRunState,
    ApprovalDecision,
    PlannedToolCall,
    RunBudget,
    ToolRisk,
    TrustedProjectScope,
    approval_binding_for,
    approval_is_valid,
)
from service.agentGraph import build_agent_graph
from service.agentPlanner import DeterministicAgentPlanner, PlannerProposal
from service.agentRuntimeContracts import AgentGraphEnvelope, ApprovalResume, ProjectObservation
from service.agentToolSchemas import ToolExecutionResult, ToolExecutionStatus


def _state(call: PlannedToolCall) -> AgentRunState:
    return AgentRunState(
        run_id="run-context",
        thread_id="thread-context",
        project_scope=TrustedProjectScope(
            project_id="project-a",
            actor_id="local-workbench",
            scope_version="iteration4-aspect4-v1",
        ),
        source_revision="revision-1",
        goal="Generate UI cases",
        plan_version=1,
        plan=(call,),
        budget=RunBudget(
            max_steps=3,
            max_elapsed_ms=60_000,
            max_input_tokens=10_000,
            max_output_tokens=5_000,
            max_model_calls=3,
            max_embedding_calls=2,
            max_tool_calls=3,
            max_estimated_cost_units=15_000,
        ),
    )


def _call(operation: str = "ui_case", arguments=None) -> PlannedToolCall:
    return PlannedToolCall(
        step_id="step-1",
        operation=operation,
        arguments=arguments or {"regenerate": False},
        risks=frozenset({ToolRisk.PAID, ToolRisk.PERSISTENT}),
        idempotency_key="run-context:unbound",
        model_label="deterministic-fake",
    )


def _artifact(**changes) -> ContextArtifact:
    values = {
        "operation": "ui_info",
        "artifact_key": "ui_info",
        "source_revision": "revision-1",
        "input_hash": "a" * 64,
        "prompt_version": "ui-info-v1",
        "model_label": "deterministic-fake",
        "selection": {},
        "result": "UNIQUE_CONTEXT_SENTINEL",
        "content_sha256": "b" * 64,
    }
    values.update(changes)
    return ContextArtifact(**values)


def test_case_context_fields_are_runtime_owned_and_never_checkpointed():
    assert context_payload_fields("ui_case") == ("info",)
    assert context_payload_fields("unit_case") == ("unit_info",)
    assert context_payload_fields("integration_case") == (
        "integration_object_info",
    )

    assembler = AgentContextAssembler(
        artifact_loader=lambda *_args: (_artifact(),)
    )
    state = _state(_call())
    bound = assembler.bind_call(state, state.plan[0])
    checkpoint = state.model_copy(update={"plan": (bound,)}).model_dump_json()

    assert bound.arguments == {"regenerate": False}
    assert len(bound.context_bindings) == 1
    assert bound.context_bindings[0].payload_field == "info"
    assert "UNIQUE_CONTEXT_SENTINEL" not in checkpoint
    assert "project-a" in checkpoint  # trusted scope remains part of runtime state

    hydrated = assembler.hydrate_call(
        state.model_copy(update={"plan": (bound,)}), bound
    )
    assert hydrated == {
        "regenerate": False,
        "info": "UNIQUE_CONTEXT_SENTINEL",
    }


def test_context_binding_is_part_of_the_approval_identity():
    first_artifact = _artifact()
    assembler = AgentContextAssembler(
        artifact_loader=lambda *_args: (first_artifact,)
    )
    state = _state(_call())
    bound = assembler.bind_call(state, state.plan[0])
    state = state.model_copy(update={"plan": (bound,)})
    now = datetime(2026, 8, 27, tzinfo=UTC)
    approval = approval_binding_for(
        state,
        bound,
        decision=ApprovalDecision.APPROVED,
        decided_at=now,
        expires_at=now + timedelta(minutes=5),
        nonce="context-approval",
    )
    changed = bound.model_copy(
        update={
            "context_bindings": (
                bound.context_bindings[0].model_copy(
                    update={"content_sha256": "c" * 64}
                ),
            )
        }
    )

    assert approval_is_valid(state, bound, approval, now=now)
    assert not approval_is_valid(
        state.model_copy(update={"plan": (changed,)}),
        changed,
        approval,
        now=now,
    )


def test_context_hydration_rejects_stale_missing_and_ambiguous_artifacts():
    state = _state(_call())

    with pytest.raises(ContextAssemblyError, match="context_binding_required"):
        AgentContextAssembler(
            artifact_loader=lambda *_args: (_artifact(),)
        ).hydrate_call(state, state.plan[0])

    missing = AgentContextAssembler(artifact_loader=lambda *_args: ())
    with pytest.raises(ContextAssemblyError, match="context_missing"):
        missing.bind_call(state, state.plan[0])

    ambiguous = AgentContextAssembler(
        artifact_loader=lambda *_args: (
            _artifact(),
            _artifact(content_sha256="c" * 64, result="other"),
        )
    )
    with pytest.raises(ContextAssemblyError, match="context_ambiguous"):
        ambiguous.bind_call(state, state.plan[0])

    stale = AgentContextAssembler(
        artifact_loader=lambda *_args: (
            _artifact(source_revision="revision-2"),
        )
    )
    with pytest.raises(ContextAssemblyError, match="context_stale"):
        stale.bind_call(state, state.plan[0])


def test_context_assembler_supports_async_graph_callers_without_io_in_state():
    assembler = AgentContextAssembler(
        artifact_loader=lambda *_args: (_artifact(),)
    )
    state = _state(_call())

    async def bind():
        return await asyncio.to_thread(assembler.bind_call, state, state.plan[0])

    bound = asyncio.run(bind())
    assert bound.context_bindings[0].source_operation == "ui_info"


def test_graph_hydrates_context_only_for_the_in_process_tool_invocation():
    now = datetime(2026, 8, 27, tzinfo=UTC)
    state = _state(_call()).model_copy(update={"plan_version": 0, "plan": ()})
    envelope = AgentGraphEnvelope(
        run_state=state,
        started_at=now,
        deadline_at=now + timedelta(minutes=5),
        planner_model="deterministic-fake",
        execution_model="deterministic-fake",
    )
    assembler = AgentContextAssembler(
        artifact_loader=lambda *_args: (_artifact(),)
    )

    class Adapter:
        arguments = None

        async def invoke(self, tool_name, arguments, context):
            self.arguments = arguments
            assert context.execution_arguments["info"] == "UNIQUE_CONTEXT_SENTINEL"
            return ToolExecutionResult(
                tool_name=tool_name,
                operation="ui_case",
                status=ToolExecutionStatus.SUCCESS,
                data={"cases": []},
            )

    adapter = Adapter()
    graph = build_agent_graph(
        observer=lambda _scope: ProjectObservation(
            setup_stage="ready",
            analysis_ready=True,
            workflow_stage="analysis_ready",
            source_revision="revision-1",
        ),
        planner=DeterministicAgentPlanner(
            PlannerProposal.model_validate(
                {"steps": [{"tool_name": "workflow_ui_case", "arguments": {}}]}
            )
        ),
        tool_adapter=adapter,
        checkpointer=InMemorySaver(),
        clock=lambda: now,
        context_assembler=assembler,
    )
    config = {"configurable": {"thread_id": "context-jit"}}
    paused_raw = asyncio.run(
        graph.ainvoke(
            {"envelope": envelope.model_dump(mode="json")}, config
        )
    )
    assert "UNIQUE_CONTEXT_SENTINEL" not in str(paused_raw)
    paused = AgentGraphEnvelope.model_validate(paused_raw["envelope"])
    call = paused.run_state.plan[0]
    approval = approval_binding_for(
        paused.run_state,
        call,
        decision=ApprovalDecision.APPROVED,
        decided_at=now,
        expires_at=now + timedelta(minutes=1),
        nonce="trusted-context",
    )
    resumed = asyncio.run(
        graph.ainvoke(
            Command(
                resume=ApprovalResume(
                    decision=ApprovalDecision.APPROVED,
                    expected_plan_hash=paused.approval_request.plan_hash,
                    binding=approval,
                ).model_dump(mode="json")
            ),
            config,
        )
    )
    assert adapter.arguments["info"] == "UNIQUE_CONTEXT_SENTINEL"
    assert "UNIQUE_CONTEXT_SENTINEL" not in str(resumed)
