"""Revision-aware resume and atomic persistence for generic workflows."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_

from infrastructure.persistence import project_repository as testProjectDao
from model.TestProject import TestProjectInfo, TestProjectWorkflowArtifact
from service.workflow.stream_core import WorkflowStreamError
from service.project.revision import (
    artifact_input_hash,
    compute_project_source_revision,
)
from service.workflow.catalog import WorkflowDefinition, get_workflow_definition


Session = testProjectDao.Session
_ARTIFACT_FORMAT_VERSION = 1
_DISALLOWED_CONTENT_KEYS = frozenset(
    {
        "api_key",
        "credential",
        "credentials",
        "database_password",
        "document_body",
        "document_content",
        "prompt",
        "prompt_body",
        "prompt_text",
        "provider_exception",
        "raw_exception",
        "reasoning",
        "reasoning_content",
        "reasoning_trace",
        "source_document",
        "source_documents",
    }
)


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


def _utcnow() -> datetime:
    """返回带 UTC 时区信息的当前时间。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _normalized_key(value: str) -> str:
    """构造normalized键，并保持现有命名空间格式。"""
    return value.strip().replace("-", "_").lower()


def _contains_disallowed_content(value: Any) -> bool:
    """处理包含关系禁止的内容并返回现有契约规定的结果。"""
    if isinstance(value, Mapping):
        return any(
            not isinstance(key, str)
            or _normalized_key(key) in _DISALLOWED_CONTENT_KEYS
            or _contains_disallowed_content(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_disallowed_content(item) for item in value)
    return False


def _json_value(value: Any) -> Any:
    """将输入约束为安全的 JSON 值。

    参数:
        `value`：待处理的值。

    返回:
        `Any`，内容保持现有调用方契约。

    异常:
        `TypeError`：输入、状态或下游结果不满足现有约束时抛出。"""
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("workflow artifact object keys must be text")
        return {
            key: _json_value(value[key])
            for key in sorted(value)
        }
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError("workflow artifact values must be JSON serializable")


def normalized_selection(
    definition: WorkflowDefinition, payload: Mapping[str, Any]
) -> dict[str, Any]:
    """规范化选择条件，并遵循现有调用契约。"""
    return {
        field: _json_value(payload[field])
        for field in sorted(definition.selection_fields)
        if field in payload
    }


def _artifact_content(
    definition: WorkflowDefinition,
    payload: Mapping[str, Any],
    result: Any,
) -> str:
    """处理产物内容并返回现有契约规定的结果。

    参数:
        `definition`：沿用签名中 `WorkflowDefinition` 类型约束的输入。
        `payload`：符合现有契约的载荷。
        `result`：沿用签名中 `Any` 类型约束的输入。

    返回:
        `str`，内容保持现有调用方契约。

    异常:
        `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
    normalized_result = _json_value(result)
    value = {
        "version": _ARTIFACT_FORMAT_VERSION,
        "operation": definition.operation,
        "selection": normalized_selection(definition, payload),
        "result": normalized_result,
    }
    if _contains_disallowed_content(value):
        raise ValueError("workflow artifact contains a disallowed content field")
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _snapshot_from_row(
    definition: WorkflowDefinition,
    key: WorkflowArtifactKey,
    row: TestProjectWorkflowArtifact,
) -> WorkflowArtifactSnapshot:
    """从数据行解析快照，并校验现有数据约束。

    参数:
        `definition`：沿用签名中 `WorkflowDefinition` 类型约束的输入。
        `key`：沿用签名中 `WorkflowArtifactKey` 类型约束的输入。
        `row`：沿用签名中 `TestProjectWorkflowArtifact` 类型约束的输入。

    返回:
        `WorkflowArtifactSnapshot`，内容保持现有调用方契约。

    异常:
        `WorkflowStreamError`：输入、状态或下游结果不满足现有约束时抛出。"""
    try:
        value = json.loads(row.content)
    except (TypeError, json.JSONDecodeError) as exc:
        raise WorkflowStreamError(
            "artifact_content_error",
            "已保存的工作流结果格式无效，请重新生成",
            status=500,
            retryable=True,
        ) from exc
    if (
        not isinstance(value, dict)
        or value.get("version") != _ARTIFACT_FORMAT_VERSION
        or value.get("operation") != definition.operation
        or not isinstance(value.get("selection"), dict)
        or "result" not in value
    ):
        raise WorkflowStreamError(
            "artifact_content_error",
            "已保存的工作流结果格式无效，请重新生成",
            status=500,
            retryable=True,
        )
    return WorkflowArtifactSnapshot(
        key=key,
        result=value["result"],
        selection=value["selection"],
    )


def _key_from_row(
    definition: WorkflowDefinition,
    row: TestProjectWorkflowArtifact,
) -> WorkflowArtifactKey:
    """从数据行解析键，并校验现有数据约束。"""
    return WorkflowArtifactKey(
        operation=definition.operation,
        input_hash=row.input_hash,
        source_revision=row.source_revision,
        prompt_version=row.prompt_version,
        model_label=row.model_label,
    )


def _metadata_is_stale(metadata_json: str | None) -> bool:
    """判断元数据过期是否满足现有约束。"""
    try:
        metadata = json.loads(metadata_json or "{}")
    except (TypeError, json.JSONDecodeError):
        return False
    return isinstance(metadata, dict) and "stale_for_source_revision" in metadata


def build_workflow_artifact_key(
    pid: str,
    definition: WorkflowDefinition,
    payload: dict[str, Any],
    model_label: str,
) -> WorkflowArtifactKey:
    """构造build工作流产物键，并保持现有命名空间格式。

    参数:
        `pid`：项目 ID。
        `definition`：沿用签名中 `WorkflowDefinition` 类型约束的输入。
        `payload`：符合现有契约的载荷。
        `model_label`：可信模型标签。

    返回:
        `WorkflowArtifactKey`，内容保持现有调用方契约。

    异常:
        `WorkflowStreamError`：输入、状态或下游结果不满足现有约束时抛出。"""
    try:
        source_revision = compute_project_source_revision(pid)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise WorkflowStreamError(
            "source_revision_error",
            "无法确认项目文档版本，请先完成资料确认",
            status=422,
            retryable=False,
        ) from exc
    return WorkflowArtifactKey(
        operation=definition.operation,
        input_hash=artifact_input_hash(definition.operation, payload),
        source_revision=source_revision,
        prompt_version=definition.prompt_version,
        model_label=model_label,
    )


# 查询 artifact 必须按项目、operation、source revision 和输入摘要命中，旧结果只能标 stale。
def lookup_workflow_artifact(
    pid: str,
    definition: WorkflowDefinition,
    payload: dict[str, Any],
    model_label: str,
) -> WorkflowArtifactLookup:
    """按完整产物身份查找仍然有效的 workflow 结果。

    参数:
        `pid`：项目 ID。
        `definition`：沿用签名中 `WorkflowDefinition` 类型约束的输入。
        `payload`：符合现有契约的载荷。
        `model_label`：可信模型标签。

    返回:
        `WorkflowArtifactLookup`，内容保持现有调用方契约。

    异常:
        `WorkflowStreamError`：输入、状态或下游结果不满足现有约束时抛出。"""
    key = build_workflow_artifact_key(pid, definition, payload, model_label)
    session = Session()
    try:
        identity = (
            pid,
            definition.result_artifact,
            key.input_hash,
            key.source_revision,
            key.prompt_version,
            key.model_label,
        )
        row = session.get(TestProjectWorkflowArtifact, identity)
        row_is_stale = row is not None and _metadata_is_stale(row.metadata_json)
        artifact_row = row if row is not None and not row_is_stale else None
        if artifact_row is None and definition.phase == "analysis":
            compatible_rows = (
                session.query(TestProjectWorkflowArtifact)
                .filter(
                    TestProjectWorkflowArtifact.project_id == pid,
                    TestProjectWorkflowArtifact.artifact_key
                    == definition.result_artifact,
                    TestProjectWorkflowArtifact.input_hash == key.input_hash,
                    TestProjectWorkflowArtifact.source_revision
                    == key.source_revision,
                    TestProjectWorkflowArtifact.prompt_version
                    == key.prompt_version,
                )
                .order_by(
                    TestProjectWorkflowArtifact.updated_at.desc(),
                    TestProjectWorkflowArtifact.model_label.asc(),
                )
                .all()
            )
            artifact_row = next(
                (
                    candidate
                    for candidate in compatible_rows
                    if not _metadata_is_stale(candidate.metadata_json)
                ),
                None,
            )
        artifact = None
        if artifact_row is not None:
            artifact = _snapshot_from_row(
                definition,
                _key_from_row(definition, artifact_row),
                artifact_row,
            )
        history_rows = (
            session.query(TestProjectWorkflowArtifact)
            .filter(
                TestProjectWorkflowArtifact.project_id == pid,
                TestProjectWorkflowArtifact.artifact_key
                == definition.result_artifact,
            )
            .all()
        )
        stale_model_filter = (
            True
            if definition.phase == "analysis"
            else TestProjectWorkflowArtifact.model_label == key.model_label
        )
        stale = artifact is None and (row_is_stale or (
            session.query(TestProjectWorkflowArtifact)
            .filter(
                TestProjectWorkflowArtifact.project_id == pid,
                TestProjectWorkflowArtifact.artifact_key
                == definition.result_artifact,
                TestProjectWorkflowArtifact.input_hash == key.input_hash,
                TestProjectWorkflowArtifact.prompt_version == key.prompt_version,
                stale_model_filter,
                TestProjectWorkflowArtifact.source_revision != key.source_revision,
            )
            .first()
            is not None
        ))
        return WorkflowArtifactLookup(
            key=key,
            artifact=artifact,
            stale=stale,
            has_history=bool(history_rows),
        )
    except WorkflowStreamError:
        raise
    except Exception as exc:
        session.rollback()
        raise WorkflowStreamError(
            "artifact_lookup_error",
            "工作流历史结果读取失败，请稍后重试",
            status=500,
            retryable=True,
        ) from exc
    finally:
        session.close()


def _fresh_artifact_exists(
    session,
    pid: str,
    prerequisite: str,
    source_revision: str,
) -> bool:
    """判断有效产物存在是否满足现有约束。"""
    definition = get_workflow_definition(prerequisite)
    rows = (
        session.query(TestProjectWorkflowArtifact)
        .filter(
            TestProjectWorkflowArtifact.project_id == pid,
            TestProjectWorkflowArtifact.artifact_key == definition.result_artifact,
            TestProjectWorkflowArtifact.source_revision == source_revision,
        )
        .all()
    )
    return any(not _metadata_is_stale(row.metadata_json) for row in rows)


def _legacy_seed_exists(session, pid: str, prerequisite: str) -> bool:
    """判断legacy SEED存在是否满足现有约束。

    参数:
        `session`：调用方传入的现有参数。
        `pid`：项目 ID。
        `prerequisite`：沿用签名中 `str` 类型约束的输入。

    返回:
        `bool`，内容保持现有调用方契约。"""
    definition = get_workflow_definition(prerequisite)
    if not definition.legacy_info_types:
        return False
    revision_aware = (
        session.query(TestProjectWorkflowArtifact)
        .filter(
            TestProjectWorkflowArtifact.project_id == pid,
            TestProjectWorkflowArtifact.artifact_key == definition.result_artifact,
        )
        .first()
    )
    if revision_aware is not None:
        return False
    for info_type in definition.legacy_info_types:
        row = session.get(TestProjectInfo, (pid, info_type))
        if row is None or not row.info:
            return False
    return True


def validate_workflow_prerequisites(
    pid: str,
    definition: WorkflowDefinition,
    payload: Mapping[str, Any],
    source_revision: str,
) -> None:
    """校验工作流依赖、source revision 与持久化前置条件。

    参数:
        `pid`：项目 ID。
        `definition`：沿用签名中 `WorkflowDefinition` 类型约束的输入。
        `payload`：符合现有契约的载荷。
        `source_revision`：沿用签名中 `str` 类型约束的输入。

    异常:
        `WorkflowStreamError`：输入、状态或下游结果不满足现有约束时抛出。"""
    session = Session()
    try:
        for prerequisite in definition.prerequisites:
            if _fresh_artifact_exists(
                session, pid, prerequisite, source_revision
            ) or _legacy_seed_exists(session, pid, prerequisite):
                continue
            if definition.prerequisite_payload_fields and all(
                field in payload
                and payload[field] is not None
                and (not isinstance(payload[field], str) or payload[field].strip())
                for field in definition.prerequisite_payload_fields
            ):
                continue
            raise WorkflowStreamError(
                "workflow_prerequisite_missing",
                f"请先完成前置工作流：{prerequisite}",
                status=422,
                retryable=False,
            )
    except WorkflowStreamError:
        raise
    except Exception as exc:
        session.rollback()
        raise WorkflowStreamError(
            "artifact_lookup_error",
            "工作流前置状态读取失败，请稍后重试",
            status=500,
            retryable=True,
        ) from exc
    finally:
        session.close()


# 保存前再次校验 revision 与输入摘要，失败或取消不得把半成品提升为 persisted final。
def save_workflow_artifact(
    pid: str,
    definition: WorkflowDefinition,
    key: WorkflowArtifactKey,
    payload: Mapping[str, Any],
    result: Any,
    pending_info: Mapping[int, str],
    *,
    call_count: int,
) -> bool:
    """原子保存 workflow 产物，并避免失败结果覆盖当前有效版本。

    参数:
        `pid`：项目 ID。
        `definition`：沿用签名中 `WorkflowDefinition` 类型约束的输入。
        `key`：沿用签名中 `WorkflowArtifactKey` 类型约束的输入。
        `payload`：符合现有契约的载荷。
        `result`：沿用签名中 `Any` 类型约束的输入。
        `pending_info`：沿用签名中 `Mapping[int, str]` 类型约束的输入。
        `call_count`：沿用签名中 `int` 类型约束的输入。

    返回:
        `bool`，内容保持现有调用方契约。

    异常:
        `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
    if key.operation != definition.operation or call_count < 0:
        return False
    try:
        content = _artifact_content(definition, payload, result)
        metadata_json = json.dumps(
            {"call_count": call_count, "operation": definition.operation},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError):
        return False

    session = Session()
    try:
        identity = (
            pid,
            definition.result_artifact,
            key.input_hash,
            key.source_revision,
            key.prompt_version,
            key.model_label,
        )
        row = session.get(TestProjectWorkflowArtifact, identity)
        now = _utcnow()
        if row is None:
            row = TestProjectWorkflowArtifact(
                project_id=pid,
                artifact_key=definition.result_artifact,
                input_hash=key.input_hash,
                source_revision=key.source_revision,
                prompt_version=key.prompt_version,
                model_label=key.model_label,
                content=content,
                metadata_json=metadata_json,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
        else:
            row.content = content
            row.metadata_json = metadata_json
            row.updated_at = now

        for info_type, info in pending_info.items():
            if isinstance(info_type, bool) or not isinstance(info_type, int):
                raise ValueError("legacy info type must be an integer")
            if not isinstance(info, str):
                raise ValueError("legacy info value must be text")
            legacy = session.query(TestProjectInfo).filter(
                and_(
                    TestProjectInfo.id == pid,
                    TestProjectInfo.info_type == info_type,
                )
            ).first()
            if legacy is None:
                session.add(TestProjectInfo(id=pid, info_type=info_type, info=info))
            else:
                legacy.info = info
        session.commit()
        return True
    except Exception:
        session.rollback()
        return False
    finally:
        session.close()
