# 从有效产物与来源 revision 推导唯一项目阶段和允许路由。
"""Derive one project lifecycle from persisted, revision-aware facts."""

from __future__ import annotations

import json
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

import ezllmtest.modules.projects.ports.repository as testProjectDao
from ezllmtest.modules.generation.public import list_artifact_history
from ezllmtest.modules.generation.public import TestMenu
import ezllmtest.modules.projects.application.setup as projectSetupService
from ezllmtest.modules.projects.application.test_evidence import collect_project_test_evidence, reconcile_test_menu
import ezllmtest.modules.projects.application.documents as documentTools
from ezllmtest.modules.projects.application.setup import ProjectSetupPersistenceError
from ezllmtest.modules.generation.public import list_workflow_definitions
from ezllmtest.modules.projects.domain.info_type import InfoType


class ProjectStage(str, Enum):
    SETUP_REQUIRED = "setup_required"
    ANALYSIS_REQUIRED = "analysis_required"
    ANALYSIS_READY = "analysis_ready"
    TESTING_IN_PROGRESS = "testing_in_progress"
    TESTING_READY = "testing_ready"


class ProjectWorkflowStatus(BaseModel):
    pid: str
    stage: ProjectStage
    allowed_routes: list[str]
    completed_operations: list[str]
    stale_operations: list[str]
    menu: dict[str, bool] | None = None
    source_revision: str | None = None
    message: str = Field(max_length=120)


@dataclass(frozen=True)
class ArtifactFact:
    operation: str
    source_revision: str
    stale: bool


_MENU_ROUTES: tuple[tuple[str, str], ...] = (
    ("unit_test", "/unit"),
    ("integration_test", "/integration"),
    ("api_test", "/api"),
    ("ui_test", "/ui"),
    ("db_test", "/database"),
    ("functional_test", "/functional"),
    ("nonfunctional_test", "/nfunctional"),
    ("acceptance_test", "/acceptance"),
)

_TERMINAL_OPERATION_BY_MENU_KEY = {
    "unit_test": "unit_case",
    "integration_test": "integration_case",
    "api_test": "api_case",
    "ui_test": "ui_case",
    "db_test": "db_case",
    "functional_test": "functional_case",
    "nonfunctional_test": "nonfunctional_case",
    "acceptance_test": "acceptance_case",
}

_DEFINITIONS = list_workflow_definitions()
_OPERATION_BY_ARTIFACT_KEY = {
    definition.result_artifact: definition.operation
    for definition in _DEFINITIONS
    if definition.persistence == "artifact"
}
_OPERATION_ORDER = {
    definition.operation: index for index, definition in enumerate(_DEFINITIONS)
}


def derive_project_stage(
    setup: bool,
    analysis: bool,
    artifact_count: int,
    *,
    completed_operations: Collection[str] = (),
    required_operations: Collection[str] = (),
) -> ProjectStage:
    """从持久化事实推导项目阶段，不把前端临时状态视为准备或生成已完成。"""

    if not setup:
        return ProjectStage.SETUP_REQUIRED
    if not analysis:
        return ProjectStage.ANALYSIS_REQUIRED
    required = set(required_operations)
    if required and required.issubset(set(completed_operations)):
        return ProjectStage.TESTING_READY
    if artifact_count > 0:
        return ProjectStage.TESTING_IN_PROGRESS
    return ProjectStage.ANALYSIS_READY


def _parse_menu(value: Any) -> dict[str, bool] | None:
    """兼容菜单对象及历史代码围栏文本，提取 JSON 并校验布尔菜单字段。"""
    if isinstance(value, Mapping):
        candidate: Any = dict(value)
    elif isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            stripped = "\n".join(lines).strip()
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start < 0 or end < start:
            return None
        try:
            candidate = json.loads(stripped[start : end + 1])
        except (TypeError, json.JSONDecodeError):
            return None
    else:
        return None
    try:
        return TestMenu.model_validate(candidate).model_dump()
    except (TypeError, ValueError):
        return None


def _metadata_is_stale(metadata_json: str | None) -> bool:
    """读取产物元数据中的过期状态，存在旧结果不等于匹配当前资料。"""
    try:
        metadata = json.loads(metadata_json or "{}")
    except (TypeError, json.JSONDecodeError):
        return False
    return isinstance(metadata, dict) and "stale_for_source_revision" in metadata


def _load_artifact_facts(
    pid: str, current_source_revision: str | None
) -> tuple[ArtifactFact, ...]:
    """收集当前项目的产物存在性和 revision 事实，供统一生命周期判断。"""
    try:
        rows = list_artifact_history(pid)
        facts = []
        for row in rows:
            operation = _OPERATION_BY_ARTIFACT_KEY.get(row.artifact_key)
            if operation is None:
                continue
            facts.append(
                ArtifactFact(
                    operation=operation,
                    source_revision=row.source_revision,
                    stale=(
                        current_source_revision is None
                        or row.source_revision != current_source_revision
                        or _metadata_is_stale(row.metadata_json)
                    ),
                )
            )
        return tuple(facts)
    except Exception:
        raise ProjectSetupPersistenceError(
            "项目工作流状态读取失败", pid=pid
        ) from None


def _legacy_analysis_bundle(pid: str) -> tuple[bool, dict[str, bool] | None]:
    """将旧项目分析记录映射为兼容事实，不虚构新的 revision 缓存命中。"""
    summary = testProjectDao.get_project_info(
        pid, InfoType.PROJECT_INITIAL_SUMMARY.value
    )
    plan = testProjectDao.get_project_info(pid, InfoType.PROJECT_TEST_PLAN.value)
    menu = _parse_menu(
        testProjectDao.get_project_info(pid, InfoType.PROJECT_TEST_MENU.value)
    )
    if menu is not None and (
        not menu.get("unit_test", False)
        or not menu.get("integration_test", False)
    ):
        try:
            candidate = TestMenu.model_validate(menu)
            evidence = collect_project_test_evidence(
                documentTools.generate_all_testdocs_docs(pid)
            )
            menu = reconcile_test_menu(candidate, evidence).model_dump()
        except Exception:
            pass
    return bool(summary) and bool(plan) and menu is not None, menu


def _sorted_operations(operations: Collection[str]) -> list[str]:
    """按 catalog 顺序返回稳定的 workflow 操作列表。"""
    return sorted(
        set(operations),
        key=lambda operation: (_OPERATION_ORDER.get(operation, 10_000), operation),
    )


def _allowed_routes(
    stage: ProjectStage, menu: dict[str, bool] | None
) -> list[str]:
    """资料未齐全只允许创建页，分析未就绪只允许计划页，之后依据菜单逐项开放测试路由。"""
    if stage is ProjectStage.SETUP_REQUIRED:
        return ["/create"]
    if stage is ProjectStage.ANALYSIS_REQUIRED or menu is None:
        return ["/plan"]
    return [
        "/plan",
        "/menu",
        *[route for key, route in _MENU_ROUTES if menu.get(key) is True],
    ]


def _status_message(stage: ProjectStage, has_stale: bool) -> str:
    """为已推导阶段选择展示文本，状态转换仍由事实规则决定。"""
    if stage is ProjectStage.SETUP_REQUIRED:
        return "项目资料已变化，请先完成资料确认" if has_stale else "请先完成项目资料上传与确认"
    if stage is ProjectStage.ANALYSIS_REQUIRED:
        return "项目分析已过期，请重新生成测试计划" if has_stale else "请先生成测试计划和测试菜单"
    if stage is ProjectStage.ANALYSIS_READY:
        return "项目分析已就绪，可以开始测试"
    if stage is ProjectStage.TESTING_IN_PROGRESS:
        return "测试工作进行中，可继续未完成步骤"
    return "已完成当前测试菜单启用的测试类型"


def get_project_workflow_status(pid: str) -> ProjectWorkflowStatus:
    """把准备状态、当前 revision 和有效产物合成统一阶段；旧产物失效与已完成清单分别返回。"""

    setup_status = projectSetupService.get_status(pid)
    setup_ready = setup_status.stage == "setup_complete"
    current_revision = setup_status.source_revision
    legacy_ready, legacy_menu = _legacy_analysis_bundle(pid)
    facts = _load_artifact_facts(pid, current_revision)

    fresh_operations = {fact.operation for fact in facts if not fact.stale}
    stale_operations = {fact.operation for fact in facts if fact.stale}

    analysis_artifact_facts = [
        fact for fact in facts if fact.operation == "project_analysis"
    ]
    has_analysis_artifact = bool(analysis_artifact_facts)
    has_fresh_analysis_artifact = any(
        not fact.stale for fact in analysis_artifact_facts
    )
    analysis_ready = (
        setup_ready
        and legacy_ready
        and (not has_analysis_artifact or has_fresh_analysis_artifact)
    )
    if analysis_ready:
        fresh_operations.add("project_analysis")
    elif legacy_ready or has_analysis_artifact:
        fresh_operations.discard("project_analysis")
        stale_operations.add("project_analysis")

    if not setup_ready:
        stale_operations.update(fresh_operations)
        fresh_operations.clear()

    menu = legacy_menu if analysis_ready else None
    required_operations = {
        operation
        for key, operation in _TERMINAL_OPERATION_BY_MENU_KEY.items()
        if menu is not None and menu.get(key) is True
    }
    test_operations = fresh_operations - {"project_analysis"}
    stage = derive_project_stage(
        setup_ready,
        analysis_ready,
        len(test_operations),
        completed_operations=test_operations,
        required_operations=required_operations,
    )
    completed = _sorted_operations(fresh_operations)
    stale = _sorted_operations(stale_operations - fresh_operations)
    return ProjectWorkflowStatus(
        pid=pid,
        stage=stage,
        allowed_routes=_allowed_routes(stage, menu),
        completed_operations=completed,
        stale_operations=stale,
        menu=menu,
        source_revision=current_revision,
        message=_status_message(stage, bool(stale)),
    )
