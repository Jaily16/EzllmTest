"""MCP v2 adapter over the transport-neutral Aspect 2 tool registry."""

from __future__ import annotations

import inspect
import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import replace
from typing import Any

from mcp import MCPError
from mcp.server import Server, ServerRequestContext
from mcp.types import (
    INVALID_PARAMS,
    INVALID_REQUEST,
    CallToolRequestParams,
    CallToolResult,
    GetPromptRequestParams,
    GetPromptResult,
    ListPromptsResult,
    ListResourcesResult,
    ListToolsResult,
    PaginatedRequestParams,
    Prompt,
    PromptArgument,
    PromptMessage,
    ReadResourceRequestParams,
    ReadResourceResult,
    Resource,
    TextContent,
    TextResourceContents,
    Tool,
    ToolAnnotations,
)

from service.agentContracts import TrustedProjectScope
from service.agentToolExecutor import AgentToolExecutor, ToolInvocationContext
from service.agentToolRegistry import (
    DEFAULT_TOOL_REGISTRY,
    RegisteredToolDefinition,
    ToolRegistry,
)
from service.agentToolSchemas import (
    ToolExecutionResult,
    ToolExecutionStatus,
    ToolProgress,
)
from service.agentTelemetry import (
    agent_span,
    current_agent_trace_carrier,
    use_agent_trace,
)


TOOL_CATALOG_URI = "ezllm://tool-catalog/v1"
APPROVAL_POLICY_URI = "ezllm://approval-policy/v1"
MCP_SERVER_NAME = "ezllm-test-agent-tools"
MCP_SERVER_VERSION = "iteration4-aspect2"

ContextProvider = Callable[
    [str, ServerRequestContext[Any]],
    ToolInvocationContext | Awaitable[ToolInvocationContext],
]


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _tool_definition(
    definition: RegisteredToolDefinition,
) -> Tool:
    is_read = definition.catalog is None
    return Tool(
        name=definition.name,
        title=definition.title,
        description=definition.description,
        inputSchema=definition.input_schema(),
        outputSchema=definition.output_schema(),
        annotations=ToolAnnotations(
            readOnlyHint=is_read,
            destructiveHint=not is_read,
            idempotentHint=is_read,
            openWorldHint=False,
        ),
        _meta={"ezllm/tool": definition.public_metadata()},
    )


def _catalog_resource(registry: ToolRegistry) -> str:
    return json.dumps(
        {
            "schema_version": 1,
            "tools": [
                {
                    "name": item.name,
                    "title": item.title,
                    "description": item.description,
                    "input_schema": item.input_schema(),
                    "output_schema": item.output_schema(),
                    "metadata": item.public_metadata(),
                }
                for item in registry.definitions()
            ],
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _approval_policy_resource() -> str:
    return json.dumps(
        {
            "schema_version": 1,
            "read_only_requires_approval": False,
            "workflow_requires_approval": True,
            "risk_labels": [
                "read_only",
                "paid",
                "persistent",
                "regenerate",
            ],
            "regenerate_requires": [
                "paid",
                "persistent",
                "regenerate",
            ],
            "project_scope_source": "trusted_runtime",
            "model_may_supply_scope": False,
            "model_may_supply_approval": False,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _safe_trace_id(value: str | None) -> str | None:
    if value is None:
        return None
    return value if re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", value) else None


def _error_result(result: ToolExecutionResult) -> CallToolResult:
    assert result.error is not None
    return CallToolResult(
        content=[TextContent(text=result.error.safe_message)],
        isError=True,
        _meta={
            "ezllm/schemaVersion": 1,
            "ezllm/tool": result.tool_name,
            "ezllm/errorCode": result.error.code,
        },
    )


def create_mcp_server(
    *,
    project_scope: TrustedProjectScope,
    registry: ToolRegistry = DEFAULT_TOOL_REGISTRY,
    executor: AgentToolExecutor | None = None,
    context_provider: ContextProvider | None = None,
) -> Server[Any]:
    """Create a project-bound server without adding routes to the public app."""

    tool_executor = executor or AgentToolExecutor(registry=registry)

    async def provide_context(
        tool_name: str, request_context: ServerRequestContext[Any]
    ) -> ToolInvocationContext:
        if context_provider is None:
            value = ToolInvocationContext(project_scope=project_scope)
        else:
            value = await _maybe_await(
                context_provider(tool_name, request_context)
            )
        if value.project_scope != project_scope:
            raise MCPError(
                code=INVALID_REQUEST,
                message="Trusted project scope mismatch",
                data={"code": "project_scope_mismatch", "tool": tool_name},
            )
        return value

    async def list_tools(
        _ctx: ServerRequestContext[Any],
        _params: PaginatedRequestParams | None,
    ) -> ListToolsResult:
        return ListToolsResult(
            tools=[_tool_definition(item) for item in registry.definitions()],
            cacheScope="public",
            ttlMs=60_000,
        )

    async def call_tool(
        ctx: ServerRequestContext[Any], params: CallToolRequestParams
    ) -> CallToolResult:
        try:
            registry.get(params.name)
        except KeyError:
            return CallToolResult(
                content=[TextContent(text="Unknown tool")],
                isError=True,
            )
        base_context = await provide_context(params.name, ctx)

        async def progress_sink(progress: ToolProgress) -> None:
            await ctx.session.report_progress(
                progress.progress,
                total=progress.total,
                message=progress.label,
            )
            if base_context.progress_sink is not None:
                await _maybe_await(base_context.progress_sink(progress))

        with use_agent_trace():
            with agent_span("mcp.request", always=True):
                carrier = current_agent_trace_carrier()
                invocation_context = replace(
                    base_context,
                    progress_sink=progress_sink,
                    trace_id=(carrier.trace_id if carrier else None),
                )
                result = await tool_executor.execute(
                    params.name,
                    params.arguments or {},
                    invocation_context,
                )
        if result.status is ToolExecutionStatus.APPROVAL_REQUIRED:
            raise MCPError(
                code=INVALID_REQUEST,
                message="Human approval is required",
                data={"code": "approval_required", "tool": params.name},
            )
        if (
            result.error is not None
            and result.error.code == "project_scope_mismatch"
        ):
            raise MCPError(
                code=INVALID_REQUEST,
                message="Trusted project scope mismatch",
                data={
                    "code": "project_scope_mismatch",
                    "tool": params.name,
                },
            )
        if result.status is not ToolExecutionStatus.SUCCESS:
            return _error_result(result)
        structured = result.model_dump(mode="json")
        text_value = result.data if result.data is not None else {"ok": True}
        meta: dict[str, Any] = {
            "ezllm/schemaVersion": 1,
            "ezllm/tool": result.tool_name,
        }
        trace_id = _safe_trace_id(invocation_context.trace_id)
        if trace_id is not None:
            meta["ezllm/traceId"] = trace_id
        return CallToolResult(
            content=[
                TextContent(
                    text=json.dumps(
                        text_value,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                )
            ],
            structuredContent=structured,
            isError=False,
            _meta=meta,
        )

    resources = (
        Resource(
            name="tool_catalog_v1",
            title="EzLLM typed tool catalog",
            uri=TOOL_CATALOG_URI,
            description="Static schemas and execution metadata for registered tools.",
            mimeType="application/json",
        ),
        Resource(
            name="approval_policy_v1",
            title="EzLLM approval policy",
            uri=APPROVAL_POLICY_URI,
            description="Static human-approval and trusted-scope policy.",
            mimeType="application/json",
        ),
    )

    async def list_resources(
        _ctx: ServerRequestContext[Any],
        _params: PaginatedRequestParams | None,
    ) -> ListResourcesResult:
        return ListResourcesResult(
            resources=list(resources), cacheScope="public", ttlMs=60_000
        )

    async def read_resource(
        _ctx: ServerRequestContext[Any], params: ReadResourceRequestParams
    ) -> ReadResourceResult:
        uri = str(params.uri)
        if uri == TOOL_CATALOG_URI:
            content = _catalog_resource(registry)
        elif uri == APPROVAL_POLICY_URI:
            content = _approval_policy_resource()
        else:
            raise MCPError(
                code=INVALID_PARAMS,
                message="Unknown resource",
                data={"uri": uri},
            )
        return ReadResourceResult(
            contents=[
                TextResourceContents(
                    uri=uri,
                    mimeType="application/json",
                    text=content,
                )
            ],
            cacheScope="public",
            ttlMs=60_000,
        )

    prompt = Prompt(
        name="plan_test_workflow",
        title="Plan a catalog-backed test workflow",
        description=(
            "Prepare a structured proposal using status reads and catalog "
            "operations; never self-approve paid or persistent work."
        ),
        arguments=[
            PromptArgument(
                name="goal",
                title="Testing goal",
                description="A concise testing objective.",
                required=True,
            )
        ],
    )

    async def list_prompts(
        _ctx: ServerRequestContext[Any],
        _params: PaginatedRequestParams | None,
    ) -> ListPromptsResult:
        return ListPromptsResult(
            prompts=[prompt], cacheScope="public", ttlMs=60_000
        )

    async def get_prompt(
        _ctx: ServerRequestContext[Any], params: GetPromptRequestParams
    ) -> GetPromptResult:
        if params.name != prompt.name:
            raise MCPError(
                code=INVALID_PARAMS,
                message="Unknown prompt",
                data={"name": params.name},
            )
        goal = (params.arguments or {}).get("goal", "").strip()
        if not goal or len(goal) > 4_000:
            raise MCPError(
                code=INVALID_PARAMS,
                message="A goal between 1 and 4000 characters is required",
            )
        instruction = (
            f"Testing goal: {goal}\n"
            "First use only the project status read tools. Then propose a "
            "structured sequence of workflow_<operation> tools from the "
            "registered catalog. Do not include project identifiers, secrets, "
            "raw document bodies, hidden reasoning, or approval tokens. Paid, "
            "persistent, and regenerate operations must wait for explicit "
            "human approval from the trusted host."
        )
        return GetPromptResult(
            description=prompt.description,
            messages=[
                PromptMessage(
                    role="user", content=TextContent(text=instruction)
                )
            ],
        )

    return Server(
        MCP_SERVER_NAME,
        version=MCP_SERVER_VERSION,
        title="EzLLM Test Agent Tools",
        description=(
            "Project-scoped typed tools backed by existing deterministic "
            "workflow services."
        ),
        on_list_tools=list_tools,
        on_call_tool=call_tool,
        on_list_resources=list_resources,
        on_read_resource=read_resource,
        on_list_prompts=list_prompts,
        on_get_prompt=get_prompt,
    )
