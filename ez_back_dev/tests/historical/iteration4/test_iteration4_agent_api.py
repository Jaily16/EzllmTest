from __future__ import annotations

import asyncio
import os
from uuid import uuid4

import httpx
import pytest

from app.agentApi import AGENT_API_HOST, build_parser, create_agent_api_app
from service.agentContracts import TrustedProjectScope
from service.agentPlanner import DeterministicAgentPlanner, PlannerProposal
from service.agentRedisCoordinator import AgentRedisCoordinator, AgentRedisSettings
from service.agentRuntimeContracts import ProjectObservation
from service.agentRuntimeService import AgentRuntimeService
from service.agentToolSchemas import (
    ToolExecutionResult,
    ToolExecutionStatus,
    ToolUsageSummary,
)
from service.agentWorkbenchService import AgentWorkbenchService
from service.agentWorkbenchStore import AgentWorkbenchStore


REDIS_URL = os.getenv("EZLLM_TEST_REDIS_URL")


class _Adapter:
    def __init__(self):
        self.calls = 0

    async def invoke(self, tool_name, arguments, context):
        self.calls += 1
        return ToolExecutionResult(
            tool_name=tool_name,
            operation="ui_case",
            status=ToolExecutionStatus.SUCCESS,
            data={"cases": [{"name": "synthetic UI"}]},
            saved=True,
            source_revision="revision-1",
            artifact_key="ui_case",
            usage=ToolUsageSummary(
                input_tokens=10,
                output_tokens=20,
                model_calls=1,
                embedding_calls=0,
                tool_calls=1,
                estimated_cost_units=5,
            ),
        )


def _service():
    if not REDIS_URL:
        pytest.skip("EZLLM_TEST_REDIS_URL is not configured")
    coordinator = AgentRedisCoordinator(
        AgentRedisSettings(
            url=REDIS_URL,
            prefix=f"ezllm:test:aspect4:api:{uuid4().hex}",
            lease_ttl_seconds=10,
            lease_renew_seconds=1,
            event_ttl_seconds=60,
            event_max_length=100,
            state_ttl_seconds=60,
        )
    )
    store = AgentWorkbenchStore(coordinator)
    adapter = _Adapter()
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
            setup_stage="setup_complete",
            analysis_ready=True,
            workflow_stage="analysis_ready",
            source_revision="revision-1",
        ),
        tool_adapter=adapter,
        workbench_store=store,
    )
    return AgentWorkbenchService(runtime, store), coordinator, adapter


def test_agent_api_contract_scope_envelopes_and_zero_implicit_execution():
    async def scenario():
        service, coordinator, adapter = _service()
        app = create_agent_api_app(
            service,
            project_exists=lambda pid: pid == "project-a",
            allowed_origins=("http://localhost:8080",),
            allow_test_host=True,
        )
        transport = httpx.ASGITransport(app=app)
        try:
            async with httpx.AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as client:
                capabilities = await client.get("/agent/v1/capabilities")
                assert capabilities.status_code == 200
                assert set(capabilities.json()) == {"status", "reason", "data"}
                assert capabilities.json()["data"]["trace_status"] == "not_instrumented"

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
                assert adapter.calls == 0

                snapshot = await client.get(
                    f"/agent/v1/projects/project-a/runs/{thread_id}"
                )
                assert snapshot.status_code == 200
                data = snapshot.json()["data"]
                assert data["trace_id"] is None
                assert data["trace_status"] == "not_instrumented"
                assert "actor_id" not in str(data)
                assert adapter.calls == 0

                history = await client.get("/agent/v1/projects/project-a/runs")
                assert history.status_code == 200
                assert len(history.json()["data"]["runs"]) == 1

                hidden = await client.get(
                    f"/agent/v1/projects/project-b/runs/{thread_id}"
                )
                assert hidden.status_code == 404
                assert hidden.json()["status"] == "agent_project_not_found"

                invalid = await client.post(
                    "/agent/v1/projects/project-a/runs",
                    json={
                        "goal": "x",
                        "model_label": "unknown",
                        "budget_preset": "focused",
                        "project_id": "project-b",
                    },
                )
                assert invalid.status_code == 422
                assert invalid.json() == {
                    "status": "agent_validation_error",
                    "reason": "Agent request validation failed",
                    "data": None,
                }
                assert adapter.calls == 0
        finally:
            await coordinator.delete_test_namespace()
            await coordinator.aclose()

    asyncio.run(scenario())


def test_agent_api_loopback_host_cors_health_and_cli_contract():
    async def scenario():
        service, coordinator, _adapter = _service()
        app = create_agent_api_app(
            service,
            project_exists=lambda _pid: True,
            allowed_origins=("http://localhost:8080",),
            allow_test_host=True,
        )
        try:
            okay_transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=okay_transport, base_url="http://testserver"
            ) as client:
                health = await client.get("/health")
                assert health.status_code == 200
                assert health.json()["data"]["redis"] == "ok"
                preflight = await client.options(
                    "/agent/v1/capabilities",
                    headers={
                        "Origin": "http://localhost:8080",
                        "Access-Control-Request-Method": "GET",
                    },
                )
                assert preflight.headers["access-control-allow-origin"] == (
                    "http://localhost:8080"
                )
                denied_origin = await client.get(
                    "/agent/v1/capabilities",
                    headers={"Origin": "https://example.invalid"},
                )
                assert "access-control-allow-origin" not in denied_origin.headers

            hostile_transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=hostile_transport,
                base_url="http://example.invalid",
            ) as client:
                denied = await client.get("/health")
                assert denied.status_code == 421
                assert denied.json()["status"] == "agent_host_rejected"
        finally:
            await coordinator.delete_test_namespace()
            await coordinator.aclose()

    asyncio.run(scenario())

    parser = build_parser()
    parsed = parser.parse_args(["--port", "8131"])
    assert parsed.port == 8131
    options = {
        option
        for action in parser._actions
        for option in action.option_strings
    }
    assert "--host" not in options
    assert AGENT_API_HOST == "127.0.0.1"


def test_agent_api_routes_are_isolated_from_main_fastapi():
    from app.agentApi import app as agent_app
    from app.main import app as main_app

    agent_paths = {
        route.path for route in agent_app.routes if hasattr(route, "path")
    }
    main_paths = {
        route.path for route in main_app.routes if hasattr(route, "path")
    }
    assert "/agent/v1/projects/{pid}/runs" in agent_paths
    assert not any(path.startswith("/agent/v1") for path in main_paths)
