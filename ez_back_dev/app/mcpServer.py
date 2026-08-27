"""Standalone loopback-only MCP entry point for Iteration 4 Aspect 2."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

import uvicorn
from starlette.applications import Starlette

from service.agentContracts import TrustedProjectScope
from service.agentMcpAdapter import ContextProvider, create_mcp_server
from service.agentToolExecutor import AgentToolExecutor
from service.agentToolRegistry import DEFAULT_TOOL_REGISTRY, ToolRegistry


LOOPBACK_HOST = "127.0.0.1"
DEFAULT_MCP_PORT = 8011


def create_loopback_app(
    *,
    project_scope: TrustedProjectScope,
    registry: ToolRegistry = DEFAULT_TOOL_REGISTRY,
    executor: AgentToolExecutor | None = None,
    context_provider: ContextProvider | None = None,
) -> Starlette:
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


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the project-scoped EzLLM loopback MCP server."
    )
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--actor-id", default="loopback-operator")
    parser.add_argument("--scope-version", default="v1")
    parser.add_argument("--port", type=int, default=DEFAULT_MCP_PORT)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    scope = TrustedProjectScope(
        project_id=args.project_id,
        actor_id=args.actor_id,
        scope_version=args.scope_version,
    )
    app = create_loopback_app(project_scope=scope)
    uvicorn.run(app, host=LOOPBACK_HOST, port=args.port)


if __name__ == "__main__":
    main()
