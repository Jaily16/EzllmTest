"""Immutable metadata for the Iteration 1 streamed workflow inventory.

Task 0 deliberately leaves the existing dispatchers unchanged.  Later
Iteration 2 tasks may consume this catalog after their compatibility tests
are in place.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tools.InfoType import InfoType


WorkflowPhase = Literal["project", "analysis", "case"]
SourceCorpus = Literal["all", "requirements", "design", "knowledge", "mixed"]
WorkflowPersistence = Literal["artifact", "session"]


@dataclass(frozen=True)
class WorkflowDefinition:
    operation: str
    phase: WorkflowPhase
    prerequisites: tuple[str, ...]
    result_artifact: str
    cache_artifacts: tuple[str, ...]
    source_corpus: SourceCorpus
    supports_regenerate: bool = True
    prompt_version: str = ""
    selection_fields: tuple[str, ...] = ()
    prerequisite_payload_fields: tuple[str, ...] = ()
    persistence: WorkflowPersistence = "artifact"

    def __post_init__(self) -> None:
        """在数据类初始化后校验并规范化实例状态。"""
        if not self.prompt_version:
            object.__setattr__(
                self,
                "prompt_version",
                f"{self.operation.replace('_', '-')}-v1",
            )

    @property
    def legacy_info_types(self) -> tuple[int, ...]:
        """返回当前legacy信息types。"""
        return tuple(
            _LEGACY_INFO_TYPE_BY_ARTIFACT[artifact]
            for artifact in self.cache_artifacts
        )


_LEGACY_INFO_TYPE_BY_ARTIFACT = {
    "project_summary": InfoType.PROJECT_INITIAL_SUMMARY.value,
    "project_units_summary": InfoType.PROJECT_UNITS_SUMMARY.value,
    "unit_test_knowledge": InfoType.PROJECT_UNIT_TEST_KNOWLEDGE.value,
    "static_blackbox_knowledge": InfoType.PROJECT_STATIC_BLACKBOX_KNOWLEDGE.value,
    "static_whitebox_knowledge": InfoType.PROJECT_STATIC_WHITEBOX_KNOWLEDGE.value,
    "integration_test_knowledge": InfoType.PROJECT_INTEGRATION_TEST_KNOWLEDGE.value,
    "integration_bigbang_knowledge": InfoType.PROJECT_INTEGRATION_BIGBANG_KNOWLEDGE.value,
    "integration_top_down_knowledge": InfoType.PROJECT_INTEGRATION_TOP_DOWN_KNOWLEDGE.value,
    "integration_bottom_up_knowledge": InfoType.PROJECT_INTEGRATION_BOTTOM_UP_KNOWLEDGE.value,
    "integration_sandwich_knowledge": InfoType.PROJECT_INTEGRATION_SANDWICH_KNOWLEDGE.value,
    "project_apis_summary": InfoType.PROJECT_APIS_SUMMARY.value,
    "api_test_knowledge": InfoType.PROJECT_API_TEST_KNOWLEDGE.value,
    "project_ui_summary": InfoType.PROJECT_UI_SUMMARY.value,
    "ui_test_knowledge": InfoType.PROJECT_UI_TEST_KNOWLEDGE.value,
    "project_db_summary": InfoType.PROJECT_DB_SUMMARY.value,
    "db_test_knowledge": InfoType.PROJECT_DB_TEST_KNOWLEDGE.value,
    "project_functional_summary": InfoType.PROJECT_FUNCTIONAL_SUMMARY.value,
    "functional_test_knowledge": InfoType.PROJECT_FUNCTION_TEST_KNOWLEDGE.value,
    "project_nonfunctional_summary": InfoType.PROJECT_NONFUNCTIONAL_SUMMARY.value,
    "project_acceptance_summary": InfoType.PROJECT_ACCEPTANCE_SUMMARY.value,
    "acceptance_test_knowledge": InfoType.PROJECT_ACCEPTANCE_TEST_KNOWLEDGE.value,
    "test_plan": InfoType.PROJECT_TEST_PLAN.value,
    "test_menu": InfoType.PROJECT_TEST_MENU.value,
}


WORKFLOW_DEFINITIONS: tuple[WorkflowDefinition, ...] = (
    WorkflowDefinition(
        operation="project_analysis",
        phase="project",
        prerequisites=("project_setup",),
        result_artifact="project_analysis_bundle",
        cache_artifacts=("project_summary", "test_plan", "test_menu"),
        source_corpus="all",
        prompt_version="project-analysis-v2",
    ),
    WorkflowDefinition(
        operation="unit_menu",
        phase="analysis",
        prerequisites=("project_analysis",),
        result_artifact="unit_menu",
        cache_artifacts=("project_units_summary",),
        source_corpus="design",
        prompt_version="unit-menu-v2",
    ),
    WorkflowDefinition(
        operation="unit_info",
        phase="analysis",
        prerequisites=("unit_menu",),
        result_artifact="unit_info",
        cache_artifacts=(),
        source_corpus="design",
        selection_fields=("unit_type", "unit"),
        prerequisite_payload_fields=("unit",),
        prompt_version="unit-info-v2",
    ),
    WorkflowDefinition(
        operation="unit_case",
        phase="case",
        prerequisites=("unit_info",),
        result_artifact="unit_case",
        cache_artifacts=(
            "unit_test_knowledge",
            "static_blackbox_knowledge",
            "static_whitebox_knowledge",
        ),
        source_corpus="knowledge",
        selection_fields=(
            "method_type",
            "static_method",
            "unit_type",
            "unit",
            "output_type",
        ),
        prerequisite_payload_fields=("unit_info",),
        persistence="session",
    ),
    WorkflowDefinition(
        operation="integration_menu",
        phase="analysis",
        prerequisites=("project_analysis",),
        result_artifact="integration_menu",
        cache_artifacts=("project_units_summary",),
        source_corpus="design",
    ),
    WorkflowDefinition(
        operation="integration_info",
        phase="analysis",
        prerequisites=("integration_menu",),
        result_artifact="integration_info",
        cache_artifacts=(),
        source_corpus="design",
        selection_fields=("integration_type", "name"),
        prerequisite_payload_fields=("integration_type",),
    ),
    WorkflowDefinition(
        operation="integration_case",
        phase="case",
        prerequisites=("integration_info",),
        result_artifact="integration_case",
        cache_artifacts=(
            "integration_test_knowledge",
            "static_blackbox_knowledge",
            "integration_bigbang_knowledge",
            "integration_top_down_knowledge",
            "integration_bottom_up_knowledge",
            "integration_sandwich_knowledge",
        ),
        source_corpus="knowledge",
        selection_fields=(
            "strategy_type",
            "strategy",
            "integration_object",
            "output_type",
        ),
        prerequisite_payload_fields=("integration_object_info",),
        persistence="session",
    ),
    WorkflowDefinition(
        operation="api_info",
        phase="analysis",
        prerequisites=("project_analysis",),
        result_artifact="api_info",
        cache_artifacts=("project_apis_summary",),
        source_corpus="design",
    ),
    WorkflowDefinition(
        operation="api_case",
        phase="case",
        prerequisites=("api_info",),
        result_artifact="api_case",
        cache_artifacts=("api_test_knowledge",),
        source_corpus="mixed",
        selection_fields=("test_type", "output_type", "api_name"),
        prerequisite_payload_fields=("info",),
        persistence="session",
    ),
    WorkflowDefinition(
        operation="ui_info",
        phase="analysis",
        prerequisites=("project_analysis",),
        result_artifact="ui_info",
        cache_artifacts=("project_ui_summary",),
        source_corpus="design",
    ),
    WorkflowDefinition(
        operation="ui_case",
        phase="case",
        prerequisites=("ui_info",),
        result_artifact="ui_case",
        cache_artifacts=("ui_test_knowledge",),
        source_corpus="knowledge",
        prerequisite_payload_fields=("info",),
    ),
    WorkflowDefinition(
        operation="db_info",
        phase="analysis",
        prerequisites=("project_analysis",),
        result_artifact="db_info",
        cache_artifacts=("project_db_summary",),
        source_corpus="design",
    ),
    WorkflowDefinition(
        operation="db_case",
        phase="case",
        prerequisites=("db_info",),
        result_artifact="db_case",
        cache_artifacts=("db_test_knowledge",),
        source_corpus="knowledge",
        prerequisite_payload_fields=("info",),
    ),
    WorkflowDefinition(
        operation="functional_info",
        phase="analysis",
        prerequisites=("project_analysis",),
        result_artifact="functional_info",
        cache_artifacts=("project_functional_summary",),
        source_corpus="requirements",
    ),
    WorkflowDefinition(
        operation="functional_case",
        phase="case",
        prerequisites=("functional_info",),
        result_artifact="functional_case",
        cache_artifacts=("functional_test_knowledge",),
        source_corpus="mixed",
        selection_fields=("test_type", "output_type", "use_case_name"),
        prerequisite_payload_fields=("info",),
        persistence="session",
    ),
    WorkflowDefinition(
        operation="nonfunctional_info",
        phase="analysis",
        prerequisites=("project_analysis",),
        result_artifact="nonfunctional_info",
        cache_artifacts=("project_nonfunctional_summary",),
        source_corpus="requirements",
    ),
    WorkflowDefinition(
        operation="nonfunctional_case",
        phase="case",
        prerequisites=("nonfunctional_info",),
        result_artifact="nonfunctional_case",
        cache_artifacts=(),
        source_corpus="knowledge",
        selection_fields=("method_name",),
        prerequisite_payload_fields=("info",),
        persistence="session",
    ),
    WorkflowDefinition(
        operation="acceptance_info",
        phase="analysis",
        prerequisites=("project_analysis",),
        result_artifact="acceptance_info",
        cache_artifacts=("project_acceptance_summary",),
        source_corpus="requirements",
    ),
    WorkflowDefinition(
        operation="acceptance_case",
        phase="case",
        prerequisites=("acceptance_info",),
        result_artifact="acceptance_case",
        cache_artifacts=("acceptance_test_knowledge",),
        source_corpus="knowledge",
        prerequisite_payload_fields=("info",),
    ),
)

_WORKFLOW_BY_OPERATION = {
    definition.operation: definition for definition in WORKFLOW_DEFINITIONS
}


# catalog 是 19 个 workflow 的唯一定义源，REST、Agent 和 MCP 都从这里读取顺序与 retention。
def get_workflow_definition(operation: str) -> WorkflowDefinition:
    """获取工作流定义，并遵循现有调用契约。"""
    return _WORKFLOW_BY_OPERATION[operation]


# 列表顺序属于公共能力清单，改变它会影响工具注册、审批计划和历史 evidence 对齐。
def list_workflow_definitions() -> tuple[WorkflowDefinition, ...]:
    """返回当前LIST工作流定义。"""
    return WORKFLOW_DEFINITIONS
