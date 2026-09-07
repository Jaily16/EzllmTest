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
        """初始化实例并保存后续操作所需的依赖与状态。"""
        self.registry = registry
        self.executor = executor or AgentToolExecutor(registry=registry)

    def definitions(self) -> tuple[RegisteredToolDefinition, ...]:
        """返回当前定义。"""
        return self.registry.definitions()

    async def invoke(
        self,
        tool_name: str,
        arguments: dict[str, JsonValue],
        context: ToolInvocationContext,
    ) -> ToolExecutionResult:
        """调用当前适配器封装的下游能力，并返回既有契约规定的结果。"""
        return await self.executor.execute(tool_name, arguments, context)
