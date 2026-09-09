# 内部调用适配器连接共享注册表与执行器；自身不重新导出旧模块。
"""Thin internal adapter for the future single-Agent runtime."""

from __future__ import annotations

from pydantic import JsonValue

from ezllmtest.modules.agent.runtime.execution.executor import AgentToolExecutor, ToolInvocationContext
from ezllmtest.modules.agent.runtime.tools.registry import DEFAULT_TOOL_REGISTRY, RegisteredToolDefinition, ToolRegistry
from ezllmtest.modules.agent.runtime.tools.schemas import ToolExecutionResult


class InternalAgentToolAdapter:
    def __init__(
        self,
        *,
        executor: AgentToolExecutor | None = None,
        registry: ToolRegistry = DEFAULT_TOOL_REGISTRY,
    ) -> None:
        """让内部工具适配器与执行器共享同一注册表，避免解析和执行使用不同的工具定义。"""
        self.registry = registry
        self.executor = executor or AgentToolExecutor(registry=registry)

    def definitions(self) -> tuple[RegisteredToolDefinition, ...]:
        """读取共享工具注册表中的定义，内部适配器不维护第二份工具清单。"""
        return self.registry.definitions()

    async def invoke(
        self,
        tool_name: str,
        arguments: dict[str, JsonValue],
        context: ToolInvocationContext,
    ) -> ToolExecutionResult:
        """将调用和可信上下文交给受控执行器，不在适配层绕过审批、预算或项目检查。"""
        return await self.executor.execute(tool_name, arguments, context)
