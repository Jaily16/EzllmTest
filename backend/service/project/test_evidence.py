"""Deterministic document-structure evidence for project test-menu guards."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from model.ChainJsonModel import ProjectTestEvidence, TestMenu


_UNIT_PATTERNS: dict[str, re.Pattern[str]] = {
    "subsystem": re.compile(r"子系统|subsystem", re.I),
    "module_component": re.compile(r"模块|组件|\bmodule\b|\bcomponent\b", re.I),
    "code_unit": re.compile(
        r"类图|类名|类结构|函数|方法|\bclass\b|"
        r"[A-Za-z][A-Za-z0-9_]*(?:Service|Controller|Repository|Mapper|DAO)\b",
        re.I,
    ),
    "layer": re.compile(
        r"分层|控制层|服务层|业务层|数据访问层|表现层|持久层|\blayer(?:ed)?\b",
        re.I,
    ),
}

_INTEGRATION_PATTERNS: dict[str, re.Pattern[str]] = {
    "architecture": re.compile(
        r"架构|分层|微服务|前端|后端|客户端|服务端|\barchitecture\b",
        re.I,
    ),
    "boundary": re.compile(
        r"接口|\bAPI\b|\bREST(?:ful)?\b|\bRPC\b|消息队列|数据库|事件总线",
        re.I,
    ),
    "relationship": re.compile(
        r"调用|依赖|交互|协作|连接|通信|数据流|传递|集成|订阅|发布|"
        r"\bcall(?:s|ed|ing)?\b|\bdepend(?:s|ed|ency|encies)?\b",
        re.I,
    ),
    "multiple_units": re.compile(
        r"子系统|模块|组件|服务|控制层|服务层|数据访问层|"
        r"\bservice\b|\bmodule\b|\bcomponent\b",
        re.I,
    ),
}


def _document_texts(documents: Iterable[Any]) -> list[str]:
    """处理文档texts并返回现有契约规定的结果。"""
    values: list[str] = []
    for document in documents:
        content = getattr(document, "page_content", document)
        if isinstance(content, str) and content.strip():
            values.append(content)
    return values


def collect_project_test_evidence(
    documents: Iterable[Any],
) -> ProjectTestEvidence:
    """收集项目测试证据，并遵循现有调用契约。"""
    text = "\n".join(_document_texts(documents))
    unit_signals = tuple(
        name for name, pattern in _UNIT_PATTERNS.items() if pattern.search(text)
    )
    integration_signals = tuple(
        name
        for name, pattern in _INTEGRATION_PATTERNS.items()
        if pattern.search(text)
    )
    return ProjectTestEvidence(
        unit_signals=unit_signals,
        integration_signals=integration_signals,
        has_integration_relationship="relationship" in integration_signals,
    )


def reconcile_test_menu(
    candidate: TestMenu,
    evidence: ProjectTestEvidence,
) -> TestMenu:
    """协调并修正测试测试菜单，并遵循现有调用契约。"""

    values = candidate.model_dump()
    if evidence.unit_signal_categories >= 2:
        values["unit_test"] = True
    if (
        evidence.integration_signal_categories >= 3
        and evidence.has_integration_relationship
    ):
        values["integration_test"] = True
    return TestMenu.model_validate(values)
