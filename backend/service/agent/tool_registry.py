"""Immutable, catalog-derived tool registry shared by internal and MCP adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, JsonValue

from service.agent.contracts import (
    ToolRisk,
    TypedToolDefinition,
    typed_tool_definition_for,
)
from service.agent.tool_schemas import (
    EmptyToolInput,
    TOOL_INPUT_MODELS,
    ToolExecutionResult,
    WorkflowToolInput,
)
from service.workflow.budget import profile_for
from service.workflow.catalog import list_workflow_definitions


RAG_CAPABLE_OPERATIONS = frozenset(
    {
        "unit_info",
        "integration_info",
        "nonfunctional_info",
        "unit_case",
        "integration_case",
        "api_case",
        "ui_case",
        "db_case",
        "functional_case",
        "nonfunctional_case",
        "acceptance_case",
    }
)


class ToolBudgetMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    map: dict[str, JsonValue]
    structured: dict[str, JsonValue]
    final: dict[str, JsonValue]
    may_call_model: bool = True
    cache_may_skip_all_calls: bool = True


@dataclass(frozen=True)
class RegisteredToolDefinition:
    name: str
    title: str
    description: str
    input_model: type[BaseModel]
    catalog: TypedToolDefinition | None
    base_risks: frozenset[ToolRisk]
    budget: ToolBudgetMetadata | None
    rag_capable: bool
    idempotency_scope: Literal["none", "artifact_identity", "run_step"]
    cancellation: Literal["none", "cooperative"]
    retention: Literal["none", "artifact", "session"]

    @property
    def operation(self) -> str | None:
        """返回当前操作。"""
        return self.catalog.operation if self.catalog is not None else None

    @property
    def approval_required(self) -> bool:
        """返回当前审批必需状态。"""
        return bool(
            self.base_risks
            & {ToolRisk.PAID, ToolRisk.PERSISTENT, ToolRisk.REGENERATE}
        )

    def resolve_risks(self, *, regenerate: bool) -> frozenset[ToolRisk]:
        """解析风险，并遵循现有调用契约。"""
        if regenerate:
            return frozenset(
                {ToolRisk.PAID, ToolRisk.PERSISTENT, ToolRisk.REGENERATE}
            )
        return self.base_risks

    def input_schema(self) -> dict[str, JsonValue]:
        """处理输入schema，并保持 `RegisteredToolDefinition` 的现有状态约束。"""
        return self.input_model.model_json_schema(mode="validation")

    def output_schema(self) -> dict[str, JsonValue]:
        """处理输出schema，并保持 `RegisteredToolDefinition` 的现有状态约束。"""
        return ToolExecutionResult.model_json_schema(mode="serialization")

    def public_metadata(self) -> dict[str, JsonValue]:
        """返回当前公开元数据。"""
        return {
            "schema_version": 1,
            "operation": self.operation,
            "risks": sorted(risk.value for risk in self.base_risks),
            "approval_required": self.approval_required,
            "budget": (
                self.budget.model_dump(mode="json")
                if self.budget is not None
                else None
            ),
            "rag_capable": self.rag_capable,
            "idempotency_scope": self.idempotency_scope,
            "cancellation": self.cancellation,
            "retention": self.retention,
        }


class ToolRegistry:
    output_model = ToolExecutionResult

    def __init__(self, definitions: tuple[RegisteredToolDefinition, ...]):
        """初始化实例并保存后续操作所需的依赖与状态。

        参数:
            `definitions`：沿用签名中 `tuple[RegisteredToolDefinition, ...]` 类型约束的输入。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
        by_name = {item.name: item for item in definitions}
        if len(by_name) != len(definitions):
            raise ValueError("tool registry contains duplicate names")
        self._definitions = definitions
        self._by_name = by_name

    def definitions(self) -> tuple[RegisteredToolDefinition, ...]:
        """返回当前定义。"""
        return self._definitions

    def workflow_definitions(self) -> tuple[RegisteredToolDefinition, ...]:
        """返回当前工作流定义。"""
        return tuple(
            item for item in self._definitions if item.catalog is not None
        )

    def names(self) -> tuple[str, ...]:
        """返回当前名称。"""
        return tuple(item.name for item in self._definitions)

    def get(self, name: str) -> RegisteredToolDefinition:
        """获取内部逻辑，并遵循现有调用契约。

        参数:
            `name`：目标名称。

        返回:
            `RegisteredToolDefinition`，内容保持现有调用方契约。

        异常:
            `KeyError`：输入、状态或下游结果不满足现有约束时抛出。"""
        try:
            return self._by_name[name]
        except KeyError:
            raise KeyError(f"unknown tool: {name}") from None


def _read_tool(name: str, title: str, description: str):
    """读取工具，并遵循现有调用契约。"""
    return RegisteredToolDefinition(
        name=name,
        title=title,
        description=description,
        input_model=EmptyToolInput,
        catalog=None,
        base_risks=frozenset({ToolRisk.READ_ONLY}),
        budget=None,
        rag_capable=False,
        idempotency_scope="none",
        cancellation="none",
        retention="none",
    )


def _budget_for(operation: str) -> ToolBudgetMetadata:
    """为内部逻辑构造预算。"""
    return ToolBudgetMetadata(
        map=profile_for(operation, "map").public_metadata(),
        structured=profile_for(operation, "structured").public_metadata(),
        final=profile_for(operation, "final").public_metadata(),
    )


def build_default_tool_registry() -> ToolRegistry:
    """根据固定 workflow catalog 构建不可变的默认工具注册表。

    返回:
        `ToolRegistry`，内容保持现有调用方契约。"""
    reads = (
        _read_tool(
            "project_setup_status",
            "Project setup status",
            "Read the trusted project's document setup readiness.",
        ),
        _read_tool(
            "project_analysis_status",
            "Project analysis status",
            "Read persisted preliminary-analysis readiness.",
        ),
        _read_tool(
            "project_workflow_status",
            "Project workflow status",
            "Read the revision-aware workflow lifecycle.",
        ),
    )
    workflows = []
    for definition in list_workflow_definitions():
        persisted = definition.persistence == "artifact"
        base_risks = {ToolRisk.PAID}
        if persisted:
            base_risks.add(ToolRisk.PERSISTENT)
        workflows.append(
            RegisteredToolDefinition(
                name=f"workflow_{definition.operation}",
                title=f"Workflow: {definition.operation}",
                description=(
                    "Execute the existing project-scoped workflow through the "
                    "in-process application service layer."
                ),
                input_model=TOOL_INPUT_MODELS[definition.operation],
                catalog=typed_tool_definition_for(definition.operation),
                base_risks=frozenset(base_risks),
                budget=_budget_for(definition.operation),
                rag_capable=definition.operation in RAG_CAPABLE_OPERATIONS,
                idempotency_scope=(
                    "artifact_identity" if persisted else "run_step"
                ),
                cancellation="cooperative",
                retention="artifact" if persisted else "session",
            )
        )
    return ToolRegistry((*reads, *workflows))


DEFAULT_TOOL_REGISTRY = build_default_tool_registry()


def validate_workflow_input(
    operation: str, arguments: dict[str, JsonValue]
) -> WorkflowToolInput:
    """校验工作流输入，并保持现有契约。"""
    return TOOL_INPUT_MODELS[operation].model_validate(arguments)
