# 协调工作流产物恢复、失效核对及原子保存，将数据库记录转换为应用快照。
"""Revision-aware resume and atomic persistence for generic workflows."""

from __future__ import annotations
from ezllmtest.modules.generation.schemas.artifacts import WorkflowArtifactKey, WorkflowArtifactSnapshot, WorkflowArtifactLookup

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_

from ezllmtest.platform.database.connection import Session

from ezllmtest.modules.generation.application.stream_core import WorkflowStreamError
from ezllmtest.modules.projects.public import artifact_input_hash, compute_project_source_revision
from ezllmtest.modules.generation.domain.catalog import WorkflowDefinition, get_workflow_definition


TestProjectInfo = TestProjectWorkflowArtifact = None

def bind_models(info_model, artifact_model):
    """由 bootstrap 绑定生成与项目信息 ORM，保持模块导入和真实数据库连接分离。"""
    global TestProjectInfo, TestProjectWorkflowArtifact
    TestProjectInfo, TestProjectWorkflowArtifact = info_model, artifact_model
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








def _utcnow() -> datetime:
    """读取 UTC 当前时间后移除 tzinfo，以匹配现有数据库列的无时区时间表示。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _normalized_key(value: str) -> str:
    """去除两端空白、把连字符转为下划线并小写，用于稳定的字段匹配。"""
    return value.strip().replace("-", "_").lower()


def _contains_disallowed_content(value: Any) -> bool:
    """递归拒绝 checkpoint、reasoning、prompt 等不允许进入产物正文结构的字段。"""
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
    """把选择值限定为稳定 JSON 类型并规范化集合，不序列化任意运行对象。"""
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
    """按稳定键序规范化用户选择，保证相同选择产生相同输入身份。"""
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
    """构造可持久化的结果和选择对象，写库前验证 JSON 类型及禁止内容。"""
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
    """解码并验证产物行后返回稳定快照，损坏内容不能作为可恢复的有效结果。"""
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
    """从数据库行提取完整产物身份，使调用方无需依赖 ORM。"""
    return WorkflowArtifactKey(
        operation=definition.operation,
        input_hash=row.input_hash,
        source_revision=row.source_revision,
        prompt_version=row.prompt_version,
        model_label=row.model_label,
    )


def _metadata_is_stale(metadata_json: str | None) -> bool:
    """只解析过期标记，不因记录存在就认为其匹配当前来源版本。"""
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
    """结合项目来源 revision、操作、模型、提示词版本和选择输入建立缓存身份，避免跨版本复用。"""
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
    """先匹配完整产物身份，再区分精确缓存、其他模型和历史过期结果；返回查找状态而不自动生成。"""
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
    """在当前来源 revision 内检查前置产物，并排除已标记 stale 的记录。"""
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
    """检查历史兼容前置数据是否存在，仅用于旧项目准备判断，不把它升级为新 revision 的精确缓存。"""
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
    """按 workflow 定义验证选择字段与前置产物，失败时阻止下游调用并关闭只读会话。"""
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
    """将最终产物与关联 pending_info 放入同一事务；任何异常回滚，失败执行不能部分覆盖旧有效数据。"""
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


def list_artifact_history(project_id: str, artifact_key: str | None = None):
    """按项目和可选产物条件读取历史快照并按更新时间排序，关闭会话后返回不可变记录。"""
    from ezllmtest.modules.generation.schemas.history import ArtifactHistoryRow
    session = Session()
    try:
        query = session.query(TestProjectWorkflowArtifact).filter(
            TestProjectWorkflowArtifact.project_id == project_id)
        if artifact_key is not None:
            query = query.filter(TestProjectWorkflowArtifact.artifact_key == artifact_key)
        rows = query.order_by(TestProjectWorkflowArtifact.updated_at.desc()).all()
        return tuple(ArtifactHistoryRow(
            row.artifact_key, row.input_hash, row.source_revision, row.prompt_version,
            row.model_label, row.content, row.metadata_json, row.updated_at) for row in rows)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
