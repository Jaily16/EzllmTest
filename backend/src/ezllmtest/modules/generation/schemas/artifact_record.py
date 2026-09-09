# 定义产物记录的应用数据结构，避免跨层传递数据库会话。
from __future__ import annotations


from collections.abc import Mapping

from dataclasses import dataclass, field

from datetime import datetime

from typing import Any



@dataclass(frozen=True)
class WorkflowArtifactRecord:
    project_id: str
    artifact_key: str
    input_hash: str
    source_revision: str
    prompt_version: str
    model_label: str
    content: str
    metadata: Mapping[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None
