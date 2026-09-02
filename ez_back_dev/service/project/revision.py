"""Canonical project-source and workflow-input revisions.

Only file metadata and SHA-256 digests enter a source revision. Document
contents are read in bounded binary chunks and are never returned or logged.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from infrastructure.persistence import project_repository as testProjectDao


BACKEND_ROOT = Path(__file__).resolve().parents[1]
_READ_CHUNK_SIZE = 1024 * 1024
_VOLATILE_INPUT_KEYS = frozenset(
    {
        "request_id",
        "requestid",
        "timestamp",
        "created_at",
        "updated_at",
        "started_at",
        "completed_at",
        "ui_label",
        "uilabel",
        "display_label",
        "displaylabel",
    }
)


@dataclass(frozen=True)
class SourceRevisionEntry:
    relative_path: str
    document_kind: str
    size: int
    file_sha256: str

    @classmethod
    def from_file(
        cls,
        file_path: str | Path,
        *,
        document_kind: str,
        relative_path: str | None = None,
    ) -> "SourceRevisionEntry":
        path = Path(file_path)
        stat = path.stat()
        return cls(
            relative_path=_normalize_relative_path(relative_path or path.name),
            document_kind=_normalize_document_kind(document_kind),
            size=stat.st_size,
            file_sha256=_file_sha256(path),
        )


def _normalize_relative_path(value: str) -> str:
    normalized = PurePosixPath(str(value).replace("\\", "/")).as_posix()
    path = PurePosixPath(normalized)
    if not normalized or path.is_absolute() or ".." in path.parts:
        raise ValueError("source entry relative_path must be a safe relative path")
    return normalized


def _normalize_document_kind(value: str) -> str:
    normalized = str(value).strip().lower()
    if not normalized:
        raise ValueError("source entry document_kind is required")
    return normalized


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(_READ_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _coerce_source_entry(
    entry: SourceRevisionEntry | Mapping[str, Any],
) -> SourceRevisionEntry:
    if isinstance(entry, SourceRevisionEntry):
        candidate = entry
    elif isinstance(entry, Mapping):
        candidate = SourceRevisionEntry(
            relative_path=str(entry["relative_path"]),
            document_kind=str(entry["document_kind"]),
            size=int(entry["size"]),
            file_sha256=str(entry["file_sha256"]),
        )
    else:
        candidate = SourceRevisionEntry(
            relative_path=str(getattr(entry, "relative_path")),
            document_kind=str(getattr(entry, "document_kind")),
            size=int(getattr(entry, "size")),
            file_sha256=str(getattr(entry, "file_sha256")),
        )

    sha256 = candidate.file_sha256.strip().lower()
    if candidate.size < 0:
        raise ValueError("source entry size must be non-negative")
    if len(sha256) != 64 or any(character not in "0123456789abcdef" for character in sha256):
        raise ValueError("source entry file_sha256 must be a SHA-256 hex digest")
    return SourceRevisionEntry(
        relative_path=_normalize_relative_path(candidate.relative_path),
        document_kind=_normalize_document_kind(candidate.document_kind),
        size=candidate.size,
        file_sha256=sha256,
    )


# revision 由规范化的项目源条目决定，是 artifact/cache/RAG 复用与 stale 判断的共同身份。
def compute_source_revision(
    entries: Iterable[SourceRevisionEntry | Mapping[str, Any]],
) -> str:
    canonical_entries = [
        {
            "relative_path": entry.relative_path,
            "document_kind": entry.document_kind,
            "size": entry.size,
            "file_sha256": entry.file_sha256,
        }
        for entry in (_coerce_source_entry(item) for item in entries)
    ]
    canonical_entries.sort(
        key=lambda item: (
            item["relative_path"],
            item["document_kind"],
            item["size"],
            item["file_sha256"],
        )
    )
    canonical = json.dumps(
        canonical_entries,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _stored_path_and_relative_path(stored_path: str) -> tuple[Path, str]:
    original = Path(stored_path)
    resolved = (BACKEND_ROOT / original).resolve() if not original.is_absolute() else original.resolve()
    try:
        relative = resolved.relative_to(BACKEND_ROOT.resolve()).as_posix()
    except ValueError:
        relative = resolved.name
    return resolved, _normalize_relative_path(relative)


def _rows_for_project(pid: str, finder) -> list[Any]:
    rows = finder(pid)
    if rows is False or rows is None:
        raise RuntimeError("project document metadata is unavailable")
    return list(rows)


def compute_project_source_revision(pid: str) -> str:
    if not pid:
        raise ValueError("pid is required")

    groups = (
        ("knowledge", testProjectDao.find_project_knowledge_list),
        ("requirements", testProjectDao.find_project_requirement_testdoc_list),
        ("design", testProjectDao.find_project_design_testdoc_list),
    )
    entries: list[SourceRevisionEntry] = []
    for document_kind, finder in groups:
        for row in _rows_for_project(pid, finder):
            stored_path = row if isinstance(row, (str, Path)) else row.path
            path, relative_path = _stored_path_and_relative_path(str(stored_path))
            entries.append(
                SourceRevisionEntry.from_file(
                    path,
                    document_kind=document_kind,
                    relative_path=relative_path,
                )
            )
    return compute_source_revision(entries)


def _normalized_input_key(value: str) -> str:
    return value.strip().replace("-", "_").lower()


def _without_transport_metadata(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            key: _without_transport_metadata(item)
            for key, item in value.items()
            if isinstance(key, str)
            and _normalized_input_key(key) not in _VOLATILE_INPUT_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_without_transport_metadata(item) for item in value]
    return value


# 输入摘要只绑定可持久化业务字段，不把密钥或不可复现的运行时对象写入 artifact identity。
def artifact_input_hash(operation: str, payload: dict[str, Any]) -> str:
    if not operation:
        raise ValueError("operation is required")
    if not isinstance(payload, dict):
        raise TypeError("payload must be a dictionary")
    canonical = json.dumps(
        {
            "operation": operation,
            "payload": _without_transport_metadata(payload),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
