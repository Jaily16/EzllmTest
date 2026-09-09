"""仓储返回的只读项目快照；不携带 SQLAlchemy 会话或延迟加载状态。"""
from dataclasses import dataclass

@dataclass(frozen=True)
class ProjectRecord:
    id: str
    name: str

@dataclass(frozen=True)
class DocumentRecord:
    id: str
    path: str

@dataclass(frozen=True)
class ProjectTypeRecord:
    id: str
    overflow: int | None
