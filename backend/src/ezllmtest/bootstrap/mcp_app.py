# 装配本机 MCP 服务并绑定显式项目 scope，协议入口不猜测用户项目。
"""Standalone loopback-only MCP entry point for Iteration 4 Aspect 2."""

from __future__ import annotations


from starlette.applications import Starlette

from ezllmtest.modules.agent.domain.contracts import TrustedProjectScope
from ezllmtest.modules.agent.api.mcp_adapter import ContextProvider, create_mcp_server
from ezllmtest.modules.agent.runtime.execution.executor import AgentToolExecutor
from ezllmtest.modules.agent.runtime.tools.registry import DEFAULT_TOOL_REGISTRY, ToolRegistry


LOOPBACK_HOST = "127.0.0.1"
DEFAULT_MCP_PORT = 8011


# MCP 仅绑定 loopback，并复用 Agent registry/context，不能成为审批或项目隔离的旁路。
def create_loopback_app(
    *,
    project_scope: TrustedProjectScope,
    registry: ToolRegistry = DEFAULT_TOOL_REGISTRY,
    executor: AgentToolExecutor | None = None,
    context_provider: ContextProvider | None = None,
) -> Starlette:
    """以宿主明确提供的 project scope 装配回环 MCP 应用，不猜测或自动选择已有项目。"""
    server = create_mcp_server(
        project_scope=project_scope,
        registry=registry,
        executor=executor,
        context_provider=context_provider,
    )
    return server.streamable_http_app(
        streamable_http_path="/mcp",
        json_response=False,
        stateless_http=True,
        host=LOOPBACK_HOST,
    )
