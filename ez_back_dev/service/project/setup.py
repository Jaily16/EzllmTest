"""Recoverable, revision-aware project setup without model calls."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from infrastructure.persistence import project_repository as testProjectDao
from infrastructure.persistence.artifact_repository import (
    WorkflowArtifactRecord,
    get_fresh_artifact,
    invalidate_project_artifacts,
    save_artifact,
)
from service.project.revision import (
    artifact_input_hash,
    compute_project_source_revision,
)
from service.project import documents as documentTools
from service.retrieval.loaders import load_document
from service.retrieval.index import invalidate_project_indexes


SetupStage = Literal[
    "project_created",
    "knowledge_uploaded",
    "requirements_uploaded",
    "design_uploaded",
    "documents_ready",
    "setup_complete",
]
DocumentGroup = Literal["knowledge", "requirements", "design"]

SETUP_ARTIFACT_KEY = "project_setup"
SETUP_PROMPT_VERSION = "project-setup-v1"
SETUP_MODEL_LABEL = "system"
SETUP_INPUT_HASH = artifact_input_hash(SETUP_ARTIFACT_KEY, {})
TOKEN_OVERFLOW_THRESHOLD = 14_500


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
        super().__init__(message)
        self.status = status
        self.pid = pid or (status.pid if status is not None else "")


class ProjectSetupNotFoundError(ProjectSetupError):
    status_code = 404

    def __init__(self, pid: str):
        super().__init__("项目不存在", pid=pid)


class ProjectSetupValidationError(ProjectSetupError):
    status_code = 422


class ProjectSetupPersistenceError(ProjectSetupError):
    status_code = 500


def _document_counts(snapshot: dict[str, list[str]]) -> dict[DocumentGroup, int]:
    return {
        "knowledge": len(snapshot.get("knowledge", [])),
        "requirements": len(snapshot.get("requirements", [])),
        "design": len(snapshot.get("design", [])),
    }


def _document_files(
    snapshot: dict[str, list[str]],
) -> dict[DocumentGroup, list[str]]:
    return {
        group: [Path(path).name for path in snapshot.get(group, [])]
        for group in ("knowledge", "requirements", "design")
    }


def _stage_for_counts(counts: dict[DocumentGroup, int]) -> SetupStage:
    if all(counts[group] > 0 for group in counts):
        return "documents_ready"
    if counts["design"] > 0:
        return "design_uploaded"
    if counts["requirements"] > 0:
        return "requirements_uploaded"
    if counts["knowledge"] > 0:
        return "knowledge_uploaded"
    return "project_created"


def _allowed_actions(
    counts: dict[DocumentGroup, int], stage: SetupStage
) -> list[str]:
    if stage == "setup_complete":
        return ["continue_to_plan"]
    missing = [
        f"upload_{group}"
        for group in ("knowledge", "requirements", "design")
        if counts[group] == 0
    ]
    return missing or ["finalize"]


def _status_message(
    counts: dict[DocumentGroup, int], stage: SetupStage
) -> str:
    if stage == "setup_complete":
        return "项目资料已确认"
    if stage == "documents_ready":
        return "项目资料已齐全，可以确认创建"
    missing_labels = [
        label
        for group, label in (
            ("knowledge", "测试知识库"),
            ("requirements", "业务需求文档"),
            ("design", "开发设计文档"),
        )
        if counts[group] == 0
    ]
    return "请补充" + "、".join(missing_labels)


def _load_snapshot(pid: str) -> dict[str, list[str]]:
    snapshot = testProjectDao.get_project_setup_documents(pid)
    if snapshot is None:
        raise ProjectSetupNotFoundError(pid)
    if snapshot is False:
        raise ProjectSetupPersistenceError("项目资料状态读取失败", pid=pid)
    return snapshot


def _setup_artifact(pid: str, source_revision: str):
    return get_fresh_artifact(
        pid,
        SETUP_ARTIFACT_KEY,
        source_revision,
        SETUP_INPUT_HASH,
        SETUP_PROMPT_VERSION,
        SETUP_MODEL_LABEL,
    )


def get_status(pid: str) -> ProjectSetupStatus:
    snapshot = _load_snapshot(pid)
    counts = _document_counts(snapshot)
    stage = _stage_for_counts(counts)
    source_revision = None
    if stage == "documents_ready":
        try:
            source_revision = compute_project_source_revision(pid)
        except ProjectSetupError:
            raise
        except Exception:
            raise ProjectSetupPersistenceError(
                "项目文档校验失败", pid=pid
            ) from None
        if _setup_artifact(pid, source_revision) is not None:
            stage = "setup_complete"
    return ProjectSetupStatus(
        pid=pid,
        stage=stage,
        document_counts=counts,
        document_files=_document_files(snapshot),
        allowed_actions=_allowed_actions(counts, stage),
        source_revision=source_revision,
        message=_status_message(counts, stage),
    )


def _count_document_tokens(paths: list[str]) -> int:
    total = 0
    for path in paths:
        documents = load_document(path)
        total += documentTools.num_tokens_from_string(
            documentTools.docs_to_string(documents)
        )
        if total > TOKEN_OVERFLOW_THRESHOLD:
            break
    return total


def analyze_project_type(pid: str) -> int:
    snapshot = _load_snapshot(pid)
    if not snapshot["requirements"] or not snapshot["design"]:
        status = get_status(pid)
        raise ProjectSetupValidationError(status.message, status)

    try:
        requirement_tokens = _count_document_tokens(snapshot["requirements"])
        design_tokens = _count_document_tokens(snapshot["design"])
    except Exception:
        raise ProjectSetupPersistenceError("项目文档读取失败", pid=pid) from None
    requirement_overflow = requirement_tokens > TOKEN_OVERFLOW_THRESHOLD
    design_overflow = design_tokens > TOKEN_OVERFLOW_THRESHOLD
    if requirement_overflow and design_overflow:
        overflow = 4
    elif design_overflow:
        overflow = 3
    elif requirement_overflow:
        overflow = 2
    elif requirement_tokens + design_tokens > TOKEN_OVERFLOW_THRESHOLD:
        overflow = 1
    else:
        overflow = 0

    if not testProjectDao.add_project_type(pid, overflow):
        raise ProjectSetupPersistenceError("项目类型保存失败", pid=pid)
    return overflow


def finalize(pid: str) -> ProjectSetupStatus:
    status = get_status(pid)
    if status.stage == "setup_complete":
        return status
    if status.stage != "documents_ready" or status.source_revision is None:
        raise ProjectSetupValidationError(status.message, status)

    overflow = analyze_project_type(pid)
    if not invalidate_project_artifacts(pid, status.source_revision):
        raise ProjectSetupPersistenceError("项目历史状态更新失败", status)
    invalidate_project_indexes(pid)

    record = WorkflowArtifactRecord(
        project_id=pid,
        artifact_key=SETUP_ARTIFACT_KEY,
        input_hash=SETUP_INPUT_HASH,
        source_revision=status.source_revision,
        prompt_version=SETUP_PROMPT_VERSION,
        model_label=SETUP_MODEL_LABEL,
        content=json.dumps(
            {"stage": "setup_complete"},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
        metadata={
            "document_counts": status.document_counts,
            "overflow": overflow,
        },
    )
    if not save_artifact(record):
        raise ProjectSetupPersistenceError("项目资料确认状态保存失败", status)
    return get_status(pid)
