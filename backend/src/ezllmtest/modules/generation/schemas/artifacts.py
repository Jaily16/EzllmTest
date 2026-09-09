"""有效产物身份和恢复结果，不暴露 ORM 对象。"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
@dataclass(frozen=True)
class WorkflowArtifactKey:
    operation: str
    input_hash: str
    source_revision: str
    prompt_version: str
    model_label: str

@dataclass(frozen=True)
class WorkflowArtifactSnapshot:
    key: WorkflowArtifactKey
    result: Any
    selection: dict[str, Any]

@dataclass(frozen=True)
class WorkflowArtifactLookup:
    key: WorkflowArtifactKey
    artifact: WorkflowArtifactSnapshot | None
    stale: bool
    has_history: bool = False
