# 在事务中保存按 revision 标识的有效产物，失败不覆盖既有成功版本。
"""Atomic persistence for revision-scoped workflow artifacts."""

from __future__ import annotations
from ezllmtest.modules.generation.schemas.artifact_record import WorkflowArtifactRecord

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, overload

from ezllmtest.platform.database.connection import Session

_MAX_METADATA_BYTES = 16 * 1024
_SENSITIVE_METADATA_KEYS = frozenset(
    {
        "api_key",
        "database_password",
        "document",
        "document_content",
        "documents",
        "prompt",
        "prompt_body",
        "prompt_text",
        "provider_exception",
        "raw_exception",
        "reasoning",
        "reasoning_content",
        "reasoning_trace",
        "source_text",
    }
)




def _utcnow() -> datetime:
    """读取 UTC 当前时间后移除 tzinfo，以匹配现有数据库列的无时区时间表示。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _normalized_metadata_key(value: str) -> str:
    """去除两端空白、把连字符转为下划线并小写，用于稳定的字段匹配。"""
    return value.strip().replace("-", "_").lower()


def _contains_sensitive_metadata(value: Any) -> bool:
    """递归检查元数据字段名，阻止秘密或提示词类内容进入有效产物的描述字段。"""
    if isinstance(value, Mapping):
        return any(
            not isinstance(key, str)
            or _normalized_metadata_key(key) in _SENSITIVE_METADATA_KEYS
            or _contains_sensitive_metadata(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_sensitive_metadata(item) for item in value)
    return False


def _metadata_json(metadata: Mapping[str, Any]) -> str:
    """序列化前检查敏感字段和体积边界；异常在创建数据库会话前抛出，避免无效写入。"""
    if not isinstance(metadata, Mapping) or _contains_sensitive_metadata(metadata):
        raise ValueError("artifact metadata contains a disallowed metadata field")
    try:
        serialized = json.dumps(
            dict(metadata),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("artifact metadata must be JSON serializable") from exc
    if len(serialized.encode("utf-8")) > _MAX_METADATA_BYTES:
        raise ValueError("artifact metadata exceeds the size limit")
    return serialized


def _record_from_row(row: TestProjectWorkflowArtifact) -> WorkflowArtifactRecord:
    """将 ORM 行转换为脱离会话的产物记录，调用方不持有延迟加载对象。"""
    try:
        metadata = json.loads(row.metadata_json)
    except (TypeError, json.JSONDecodeError):
        metadata = {}
    if not isinstance(metadata, dict):
        metadata = {}
    return WorkflowArtifactRecord(
        project_id=row.project_id,
        artifact_key=row.artifact_key,
        input_hash=row.input_hash,
        source_revision=row.source_revision,
        prompt_version=row.prompt_version,
        model_label=row.model_label,
        content=row.content,
        metadata=metadata,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@overload
def save_artifact(record: WorkflowArtifactRecord) -> bool:
    """保存产物，并遵循现有调用契约。"""
    ...


@overload
def save_artifact(
    record: str,
    artifact_key: str,
    source_revision: str,
    input_hash: str,
    prompt_version: str,
    model_label: str,
    content: str,
    metadata: Mapping[str, Any],
) -> bool:
    """保存产物，并遵循现有调用契约。"""
    ...


def save_artifact(
    record: WorkflowArtifactRecord | str,
    artifact_key: str | None = None,
    source_revision: str | None = None,
    input_hash: str | None = None,
    prompt_version: str | None = None,
    model_label: str | None = None,
    content: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> bool:
    """校验类型与元数据后在独立会话内新增或替换有效产物，提交失败回滚并关闭会话。"""
    if isinstance(record, WorkflowArtifactRecord):
        artifact = record
    else:
        values = (
            artifact_key,
            source_revision,
            input_hash,
            prompt_version,
            model_label,
            content,
        )
        if any(value is None for value in values):
            raise TypeError("all workflow artifact fields are required")
        artifact = WorkflowArtifactRecord(
            project_id=record,
            artifact_key=artifact_key,
            input_hash=input_hash,
            source_revision=source_revision,
            prompt_version=prompt_version,
            model_label=model_label,
            content=content,
            metadata=metadata or {},
        )

    serialized_metadata = _metadata_json(artifact.metadata)
    identity = (
        artifact.project_id,
        artifact.artifact_key,
        artifact.input_hash,
        artifact.source_revision,
        artifact.prompt_version,
        artifact.model_label,
    )
    session = Session()
    try:
        row = session.get(TestProjectWorkflowArtifact, identity)
        now = _utcnow()
        if row is None:
            row = TestProjectWorkflowArtifact(
                project_id=artifact.project_id,
                artifact_key=artifact.artifact_key,
                input_hash=artifact.input_hash,
                source_revision=artifact.source_revision,
                prompt_version=artifact.prompt_version,
                model_label=artifact.model_label,
                content=artifact.content,
                metadata_json=serialized_metadata,
                created_at=artifact.created_at or now,
                updated_at=now,
            )
            session.add(row)
        else:
            row.content = artifact.content
            row.metadata_json = serialized_metadata
            row.updated_at = now
        session.commit()
        return True
    except Exception:
        session.rollback()
        return False
    finally:
        session.close()


def get_fresh_artifact(
    project_id: str,
    artifact_key: str,
    source_revision: str,
    input_hash: str,
    prompt_version: str,
    model_label: str,
) -> WorkflowArtifactRecord | None:
    """按产物身份读取有效记录并转换为快照；无论成功或异常均关闭本次会话。"""
    session = Session()
    try:
        row = session.get(
            TestProjectWorkflowArtifact,
            (
                project_id,
                artifact_key,
                input_hash,
                source_revision,
                prompt_version,
                model_label,
            ),
        )
        if row is None:
            return None
        record = _record_from_row(row)
        if "stale_for_source_revision" in record.metadata:
            return None
        return record
    except Exception:
        session.rollback()
        return None
    finally:
        session.close()


def invalidate_project_artifacts(project_id: str, source_revision: str) -> bool:
    """仅将指定项目产物标记为过期并维护元数据，不把来源变化解释为删除历史有效结果。"""
    session = Session()
    try:
        rows = (
            session.query(TestProjectWorkflowArtifact)
            .filter(TestProjectWorkflowArtifact.project_id == project_id)
            .all()
        )
        now = _utcnow()
        for row in rows:
            try:
                metadata = json.loads(row.metadata_json)
            except (TypeError, json.JSONDecodeError):
                metadata = {}
            if not isinstance(metadata, dict):
                metadata = {}
            if row.source_revision == source_revision:
                metadata.pop("stale_for_source_revision", None)
            else:
                metadata["stale_for_source_revision"] = source_revision
            row.metadata_json = _metadata_json(metadata)
            row.updated_at = now
        session.commit()
        return True
    except Exception:
        session.rollback()
        return False
    finally:
        session.close()


def bind_model(model):
    """由 bootstrap 绑定本域 ORM 实现，导入仓储不自行创建数据库模型或连接。"""
    global TestProjectWorkflowArtifact
    TestProjectWorkflowArtifact = model
