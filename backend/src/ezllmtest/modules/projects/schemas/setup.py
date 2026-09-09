"""项目准备状态与可公开错误，不执行文件或存储操作。"""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field
SetupStage = Literal[
    "project_created",
    "knowledge_uploaded",
    "requirements_uploaded",
    "design_uploaded",
    "documents_ready",
    "setup_complete",
]

DocumentGroup = Literal["knowledge", "requirements", "design"]

class ProjectSetupStatus(BaseModel):
    pid: str
    project_exists: bool = True
    stage: SetupStage
    document_counts: dict[DocumentGroup, int]
    document_files: dict[DocumentGroup, list[str]]
    allowed_actions: list[str]
    source_revision: str | None = None
    message: str = Field(max_length=120)

class ProjectSetupError(RuntimeError):
    status_code = 500

    def __init__(
        self,
        message: str,
        status: ProjectSetupStatus | None = None,
        *,
        pid: str | None = None,
    ):
        """携带可选准备状态与项目标识，让调用方在准备失败时仍能返回已知阶段信息。"""
        super().__init__(message)
        self.status = status
        self.pid = pid or (status.pid if status is not None else "")

class ProjectSetupNotFoundError(ProjectSetupError):
    status_code = 404

    def __init__(self, pid: str):
        """将不存在的项目标识保留在准备异常中，供统一错误响应定位请求对象。"""
        super().__init__("项目不存在", pid=pid)

class ProjectSetupValidationError(ProjectSetupError):
    status_code = 422

class ProjectSetupPersistenceError(ProjectSetupError):
    status_code = 500
