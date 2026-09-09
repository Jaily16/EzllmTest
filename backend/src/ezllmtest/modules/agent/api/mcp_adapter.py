# 将共享工具定义与受控执行转换为 MCP tools/resources，不从参数中接受项目授权。
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

from ezllmtest.modules.agent.domain.contracts import TrustedProjectScope
from ezllmtest.modules.agent.runtime.execution.executor import AgentToolExecutor, ToolInvocationContext
from ezllmtest.modules.agent.runtime.tools.registry import DEFAULT_TOOL_REGISTRY, RegisteredToolDefinition, ToolRegistry
from ezllmtest.modules.agent.runtime.tools.schemas import ToolExecutionResult, ToolExecutionStatus, ToolProgress
from ezllmtest.platform.telemetry.agent_telemetry import agent_span, current_agent_trace_carrier, use_agent_trace


TOOL_CATALOG_URI = "ezllm://tool-catalog/v1"
APPROVAL_POLICY_URI = "ezllm://approval-policy/v1"
MCP_SERVER_NAME = "ezllm-test-agent-tools"
MCP_SERVER_VERSION = "iteration4-aspect2"

ContextProvider = Callable[
    [str, ServerRequestContext[Any]],
    ToolInvocationContext | Awaitable[ToolInvocationContext],
]


async def _maybe_await(value: Any) -> Any:
    """在结果可等待时执行 await，否则直接返回结果。"""
    if inspect.isawaitable(value):
        return await value
    return value


def _tool_definition(
    definition: RegisteredToolDefinition,
) -> Tool:
    """将固定注册表元数据映射为 MCP Tool，读写风险提示来自真实工具类型，描述与 schema 属于公开协议。"""
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
    """序列化固定工具目录及输入输出 schema，不根据资源请求动态增加能力。"""
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
    """公开可信 scope 和人工审批规则；资源说明不授予模型审批权。"""
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
    """仅允许长度受限的 Trace ID 字符集；非法标识不进入 MCP 公开响应。"""
    if value is None:
        return None
    return value if re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", value) else None


def _error_result(result: ToolExecutionResult) -> CallToolResult:
    """把安全工具错误映射为 MCP 错误结果，保留稳定错误码而不回传内部异常。"""
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
    """装配固定工具、资源和提示词协议，可信上下文由宿主注入；创建对象不启动网络服务。"""

    tool_executor = executor or AgentToolExecutor(registry=registry)

    async def provide_context(
        tool_name: str, request_context: ServerRequestContext[Any]
    ) -> ToolInvocationContext:
        """从宿主取得调用上下文，模型参数不能自行指定项目身份或批准状态。"""
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
        """从共享注册表返回 MCP 工具定义和公开缓存提示，列表请求不执行工具。"""
        return ListToolsResult(
            tools=[_tool_definition(item) for item in registry.definitions()],
            cacheScope="public",
            ttlMs=60_000,
        )

    async def call_tool(
        ctx: ServerRequestContext[Any], params: CallToolRequestParams
    ) -> CallToolResult:
        """核验工具名称和输入后交给共享执行器，MCP 路径不绕过预算、审批和项目隔离。"""
        try:
            registry.get(params.name)
        except KeyError:
            return CallToolResult(
                content=[TextContent(text="Unknown tool")],
                isError=True,
            )
        base_context = await provide_context(params.name, ctx)

        async def progress_sink(progress: ToolProgress) -> None:
            """把允许的工具进度转为 MCP 通知，不传播完整工具输入或模型正文。"""
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
        """返回已声明的 MCP 资源元数据，资源正文由读取接口按 URI 提供。"""
        return ListResourcesResult(
            resources=list(resources), cacheScope="public", ttlMs=60_000
        )

    async def read_resource(
        _ctx: ServerRequestContext[Any], params: ReadResourceRequestParams
    ) -> ReadResourceResult:
        """只提供已注册的静态目录与审批政策资源，未知 URI 明确拒绝。"""
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
        """列出预定义 MCP 提示入口，不在列表请求中调用模型。"""
        return ListPromptsResult(
            prompts=[prompt], cacheScope="public", ttlMs=60_000
        )

    async def get_prompt(
        _ctx: ServerRequestContext[Any], params: GetPromptRequestParams
    ) -> GetPromptResult:
        """从已注册提示词构造响应，参数与内容保持 MCP 既有协议边界。"""
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
