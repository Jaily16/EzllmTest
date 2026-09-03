"""Atomic persistence for revision-scoped workflow artifacts."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, overload

from infrastructure.persistence.project_repository import Session
from model.TestProject import TestProjectWorkflowArtifact

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


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _normalized_metadata_key(value: str) -> str:
    return value.strip().replace("-", "_").lower()


def _contains_sensitive_metadata(value: Any) -> bool:
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
def save_artifact(record: WorkflowArtifactRecord) -> bool: ...


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
) -> bool: ...


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
