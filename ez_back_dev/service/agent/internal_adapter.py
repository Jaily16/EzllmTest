"""Thin internal adapter for the future single-Agent runtime."""

from __future__ import annotations

from pydantic import JsonValue

from service.agent.executor import AgentToolExecutor, ToolInvocationContext
from service.agent.tool_registry import (
    DEFAULT_TOOL_REGISTRY,
    RegisteredToolDefinition,
    ToolRegistry,
)
from service.agent.tool_schemas import ToolExecutionResult


class InternalAgentToolAdapter:
    def __init__(
        self,
        *,
        executor: AgentToolExecutor | None = None,
        registry: ToolRegistry = DEFAULT_TOOL_REGISTRY,
    ) -> None:
        self.registry = registry
        self.executor = executor or AgentToolExecutor(registry=registry)

    def definitions(self) -> tuple[RegisteredToolDefinition, ...]:
        return self.registry.definitions()

    async def invoke(
        self,
        tool_name: str,
        arguments: dict[str, JsonValue],
        context: ToolInvocationContext,
    ) -> ToolExecutionResult:
        return await self.executor.execute(tool_name, arguments, context)
