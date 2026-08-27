import asyncio
import json

import pytest
from mcp import Client, MCPError
from starlette.testclient import TestClient

from service.agentContracts import TrustedProjectScope
from service.agentMcpAdapter import (
    APPROVAL_POLICY_URI,
    TOOL_CATALOG_URI,
    create_mcp_server,
)
from service.agentToolExecutor import ToolInvocationContext
from service.agentToolRegistry import build_default_tool_registry
from service.agentToolSchemas import (
    ToolExecutionError,
    ToolExecutionResult,
    ToolExecutionStatus,
    ToolProgress,
)
from app.mcpServer import LOOPBACK_HOST, create_loopback_app


def _scope():
    return TrustedProjectScope(
        project_id="project-a",
        actor_id="trusted-user",
        scope_version="v1",
    )


class _FakeExecutor:
    def __init__(self, result=None, *, emit_progress=False, block=False):
        self.registry = build_default_tool_registry()
        self.result = result
        self.emit_progress = emit_progress
        self.block = block
        self.cancelled = False
        self.contexts = []

    async def execute(self, tool_name, arguments, context):
        self.contexts.append(context)
        if self.emit_progress:
            await context.progress_sink(
                ToolProgress(stage="one", label="One", progress=10)
            )
            await context.progress_sink(
                ToolProgress(stage="two", label="Two", progress=80)
            )
        if self.block:
            try:
                await asyncio.Future()
            except asyncio.CancelledError:
                self.cancelled = True
                raise
        return self.result or ToolExecutionResult(
            tool_name=tool_name,
            status=ToolExecutionStatus.SUCCESS,
            data={"ok": True},
        )


def test_mcp_lists_exact_registry_schemas_and_conservative_annotations():
    async def scenario():
        registry = build_default_tool_registry()
        server = create_mcp_server(project_scope=_scope(), registry=registry)
        async with Client(server) as client:
            listed = await client.list_tools()
        assert [tool.name for tool in listed.tools] == list(registry.names())
        by_name = {tool.name: tool for tool in listed.tools}
        for definition in registry.definitions():
            tool = by_name[definition.name]
            assert tool.input_schema == definition.input_schema()
            assert tool.output_schema == definition.output_schema()
            assert tool.annotations.open_world_hint is False
            if definition.catalog is None:
                assert tool.annotations.read_only_hint is True
                assert tool.annotations.idempotent_hint is True
                assert tool.annotations.destructive_hint is False
            else:
                assert tool.annotations.read_only_hint is False
                assert tool.annotations.idempotent_hint is False
                assert tool.annotations.destructive_hint is True

    asyncio.run(scenario())


def test_mcp_exposes_only_static_catalog_policy_resources_and_safe_prompt():
    async def scenario():
        server = create_mcp_server(project_scope=_scope())
        async with Client(server) as client:
            resources = await client.list_resources()
            prompts = await client.list_prompts()
            catalog = await client.read_resource(TOOL_CATALOG_URI)
            policy = await client.read_resource(APPROVAL_POLICY_URI)
            rendered = await client.get_prompt(
                "plan_test_workflow", {"goal": "Create UI tests"}
            )

        assert {str(item.uri) for item in resources.resources} == {
            TOOL_CATALOG_URI,
            APPROVAL_POLICY_URI,
        }
        assert [item.name for item in prompts.prompts] == [
            "plan_test_workflow"
        ]
        catalog_data = json.loads(catalog.contents[0].text)
        policy_data = json.loads(policy.contents[0].text)
        assert len(catalog_data["tools"]) == 22
        assert policy_data["workflow_requires_approval"] is True
        prompt_text = rendered.messages[0].content.text
        assert "Create UI tests" in prompt_text
        assert "project-a" not in prompt_text
        assert "chain-of-thought" not in prompt_text.lower()

    asyncio.run(scenario())


def test_mcp_success_is_structured_and_progress_is_monotonic():
    async def scenario():
        executor = _FakeExecutor(emit_progress=True)
        server = create_mcp_server(
            project_scope=_scope(), executor=executor
        )
        progress = []

        async def on_progress(value, total, message):
            progress.append((value, total, message))

        async with Client(server) as client:
            result = await client.call_tool(
                "project_setup_status", {}, progress_callback=on_progress
            )
        assert result.is_error is False
        assert result.structured_content["status"] == "success"
        assert result.structured_content["data"] == {"ok": True}
        assert [item[0] for item in progress] == [10, 80]
        assert executor.contexts[0].project_scope == _scope()

    asyncio.run(scenario())


def test_mcp_approval_required_is_a_host_visible_protocol_error():
    async def scenario():
        blocked = ToolExecutionResult(
            tool_name="workflow_ui_case",
            operation="ui_case",
            status=ToolExecutionStatus.APPROVAL_REQUIRED,
            error=ToolExecutionError(
                code="approval_required",
                category="approval",
                safe_message="A matching human approval is required",
            ),
        )
        server = create_mcp_server(
            project_scope=_scope(), executor=_FakeExecutor(blocked)
        )
        async with Client(server) as client:
            with pytest.raises(MCPError, match="approval"):
                await client.call_tool(
                    "workflow_ui_case",
                    {"model_label": "DeepSeek", "info": "ui"},
                )

    asyncio.run(scenario())


def test_mcp_model_correctable_failure_uses_is_error_without_details():
    async def scenario():
        failed = ToolExecutionResult(
            tool_name="project_setup_status",
            status=ToolExecutionStatus.ERROR,
            error=ToolExecutionError(
                code="invalid_arguments",
                category="validation",
                safe_message="Arguments are invalid",
            ),
        )
        server = create_mcp_server(
            project_scope=_scope(), executor=_FakeExecutor(failed)
        )
        async with Client(server) as client:
            result = await client.call_tool("project_setup_status", {})
        assert result.is_error is True
        assert result.structured_content is None
        assert "Arguments are invalid" in result.content[0].text

    asyncio.run(scenario())


def test_mcp_cancellation_reaches_the_executor():
    async def scenario():
        executor = _FakeExecutor(block=True)
        server = create_mcp_server(
            project_scope=_scope(), executor=executor
        )
        async with Client(server) as client:
            task = asyncio.create_task(
                client.call_tool("project_setup_status", {})
            )
            await asyncio.sleep(0)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        assert executor.cancelled is True

    asyncio.run(scenario())


def test_loopback_app_has_only_mcp_route_and_rejects_nonlocal_host():
    app = create_loopback_app(project_scope=_scope())
    paths = {route.path for route in app.routes}
    assert paths == {"/mcp"}
    assert LOOPBACK_HOST == "127.0.0.1"
    with TestClient(app) as client:
        response = client.post(
            "/mcp", headers={"host": "evil.example"}, json={}
        )
    assert response.status_code == 421


def test_context_provider_cannot_change_the_server_project_scope():
    async def scenario():
        async def wrong_scope(_tool_name, _request_context):
            return ToolInvocationContext(
                project_scope=TrustedProjectScope(
                    project_id="project-b",
                    actor_id="trusted-user",
                    scope_version="v1",
                )
            )

        server = create_mcp_server(
            project_scope=_scope(),
            executor=_FakeExecutor(),
            context_provider=wrong_scope,
        )
        async with Client(server) as client:
            with pytest.raises(MCPError, match="scope"):
                await client.call_tool("project_setup_status", {})

    asyncio.run(scenario())
