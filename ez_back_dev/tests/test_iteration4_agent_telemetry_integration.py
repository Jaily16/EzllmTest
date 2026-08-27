from __future__ import annotations

import asyncio
import json
import os
from uuid import uuid4

import httpx
import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.agentApi import create_agent_api_app
from service.agentPlanner import DeterministicAgentPlanner, PlannerProposal
from service.agentRedisCoordinator import AgentRedisCoordinator, AgentRedisSettings
from service.agentRuntimeContracts import ProjectObservation
from service.agentRuntimeService import AgentRuntimeService
from service.agentTelemetry import (
    AgentTelemetry,
    TelemetrySettings,
    replace_agent_telemetry_for_tests,
)
from service.agentToolSchemas import (
    ToolExecutionResult,
    ToolExecutionStatus,
    ToolUsageSummary,
)
from service.agentWorkbenchService import AgentWorkbenchService
from service.agentWorkbenchStore import AgentWorkbenchStore


REDIS_URL = os.getenv("EZLLM_TEST_REDIS_URL")


class _Adapter:
    async def invoke(self, tool_name, _arguments, _context):
        return ToolExecutionResult(
            tool_name=tool_name,
            operation="ui_case",
            status=ToolExecutionStatus.SUCCESS,
            data={"cases": [{"name": "synthetic"}]},
            saved=True,
            source_revision="revision-1",
            artifact_key="ui_case",
            usage=ToolUsageSummary(model_calls=1, tool_calls=1),
        )


def test_api_redis_worker_graph_share_one_redacted_run_trace():
    if not REDIS_URL:
        pytest.skip("EZLLM_TEST_REDIS_URL is not configured")

    async def scenario():
        exporter = InMemorySpanExporter()
        telemetry = AgentTelemetry(
            TelemetrySettings(
                enabled=True,
                endpoint="http://127.0.0.1:4317",
                service_name="ezllm-agent-test",
                export_timeout_ms=200,
                metric_interval_ms=1_000,
            ),
            span_exporter=exporter,
        )
        previous = replace_agent_telemetry_for_tests(telemetry)
        coordinator = AgentRedisCoordinator(
            AgentRedisSettings(
                url=REDIS_URL,
                prefix=f"ezllm:test:aspect7:trace:{uuid4().hex}",
                lease_ttl_seconds=10,
                lease_renew_seconds=1,
                event_ttl_seconds=60,
                state_ttl_seconds=60,
            )
        )
        store = AgentWorkbenchStore(coordinator)
        runtime = AgentRuntimeService(
            coordinator=coordinator,
            planner=DeterministicAgentPlanner(
                PlannerProposal.model_validate(
                    {
                        "steps": [
                            {
                                "tool_name": "workflow_ui_case",
                                "arguments": {"info": "synthetic ui"},
                            }
                        ]
                    }
                )
            ),
            observer=lambda _scope: ProjectObservation(
                setup_stage="ready",
                analysis_ready=True,
                workflow_stage="analysis",
                source_revision="revision-1",
            ),
            tool_adapter=_Adapter(),
            workbench_store=store,
        )
        workbench = AgentWorkbenchService(runtime, store)
        app = create_agent_api_app(
            workbench,
            project_exists=lambda pid: pid == "project-a",
            allow_test_host=True,
        )
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                created = await client.post(
                    "/agent/v1/projects/project-a/runs",
                    json={
                        "goal": "Generate UI cases",
                        "model_label": "GLM-4.7",
                        "budget_preset": "focused",
                    },
                )
                assert created.status_code == 201
                thread_id = created.json()["data"]["thread_id"]

                await coordinator.ensure_command_group("workers")
                [command] = await coordinator.read_commands(
                    "workers", "worker-a", block_ms=10
                )
                assert command.trace_carrier is not None
                paused = await runtime.process_command(command, owner="worker-a")
                assert paused.trace_carrier == command.trace_carrier

                snapshot = await client.get(
                    f"/agent/v1/projects/project-a/runs/{thread_id}"
                )
                public = snapshot.json()["data"]
                assert public["trace_status"] == "instrumented"
                assert public["trace_id"] == command.trace_carrier.trace_id

            telemetry.force_flush(1_000)
            spans = exporter.get_finished_spans()
            run_trace_id = int(command.trace_carrier.trace_id, 16)
            run_names = {
                span.name for span in spans if span.context.trace_id == run_trace_id
            }
            assert {
                "http.agent_api",
                "agent.command.enqueue",
                "agent.command.worker",
                "agent.run",
                "agent.graph.observe",
                "agent.graph.plan",
                "agent.plan",
                "agent.checkpoint",
            } <= run_names
            rendered = json.dumps(
                [dict(span.attributes or {}) for span in spans],
                sort_keys=True,
            ).lower()
            for forbidden in (
                "project-a",
                "generate ui cases",
                "synthetic ui",
                "redis://",
                "prompt",
                "reasoning",
            ):
                assert forbidden not in rendered
        finally:
            replace_agent_telemetry_for_tests(previous)
            await coordinator.delete_test_namespace()
            await coordinator.aclose()
            telemetry.shutdown(1_000)

    asyncio.run(scenario())
