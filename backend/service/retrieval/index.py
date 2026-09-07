"""Bounded in-process vector index reuse for revision-scoped projects."""

from __future__ import annotations

import asyncio
import threading
import time
from collections import OrderedDict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import InMemoryVectorStore
from service.retrieval.splitters import (
    design_child_text_splitter,
    knowledge_text_splitter,
    require_child_text_splitter,
)

IndexCorpus = Literal["design", "requirements", "knowledge"]
IndexKey = tuple[str, str, str, str]
INDEX_CAPACITY = 16
INDEX_IDLE_TTL_SECONDS = 30 * 60


@dataclass(frozen=True)
class ProjectIndex:
    key: IndexKey
    vectorstore: InMemoryVectorStore | None
    document_count: int
    documents: tuple[Document, ...] = ()

    def similarity_search_with_score(self, query: str, k: int) -> list[tuple[Document, float]]:
        """执行项目索引相似度检索并返回文档及其分数。"""
        if self.vectorstore is None or self.document_count == 0:
            return []
        return self.vectorstore.similarity_search_with_score(
            query,
            k=min(k, self.document_count),
        )


@dataclass
class _RegistryEntry:
    index: ProjectIndex
    last_access: float


_INDEXES: OrderedDict[IndexKey, _RegistryEntry] = OrderedDict()
_BUILD_LOCKS: dict[IndexKey, asyncio.Lock] = {}
_PROJECT_GENERATIONS: dict[str, int] = {}
_STATE_LOCK = threading.RLock()
_clock = time.monotonic


def _embedding_model_identity(embeddings: Embeddings) -> str:
    """处理embedding模型身份并返回现有契约规定的结果。"""
    for attribute in ("model", "model_name", "deployment"):
        value = getattr(embeddings, attribute, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    cls = type(embeddings)
    return f"{cls.__module__}.{cls.__qualname__}"


def _split_documents(corpus: IndexCorpus, documents: Sequence[Document]) -> list[Document]:
    """拆分文档，并遵循现有调用契约。"""
    splitters = {
        "design": design_child_text_splitter,
        "requirements": require_child_text_splitter,
        "knowledge": knowledge_text_splitter,
    }
    return splitters[corpus].split_documents(list(documents))


def _build_index(
    key: IndexKey,
    corpus: IndexCorpus,
    documents: Sequence[Document],
    embeddings: Embeddings,
) -> ProjectIndex:
    """构建索引，并遵循现有调用契约。

    参数:
        `key`：沿用签名中 `IndexKey` 类型约束的输入。
        `corpus`：沿用签名中 `IndexCorpus` 类型约束的输入。
        `documents`：沿用签名中 `Sequence[Document]` 类型约束的输入。
        `embeddings`：沿用签名中 `Embeddings` 类型约束的输入。

    返回:
        `ProjectIndex`，内容保持现有调用方契约。"""
    if not documents:
        return ProjectIndex(key=key, vectorstore=None, document_count=0)
    chunks = _split_documents(corpus, documents)
    if not chunks:
        return ProjectIndex(key=key, vectorstore=None, document_count=0)
    vectorstore = InMemoryVectorStore(embedding=embeddings)
    vectorstore.add_documents(documents=chunks)
    return ProjectIndex(
        key=key,
        vectorstore=vectorstore,
        document_count=len(chunks),
        documents=tuple(chunks),
    )


def _prune_expired(now: float) -> None:
    """清理expired，并保持现有契约。"""
    expired = [
        key for key, entry in _INDEXES.items() if now - entry.last_access > INDEX_IDLE_TTL_SECONDS
    ]
    for key in expired:
        _INDEXES.pop(key, None)


def _cached_index(key: IndexKey, now: float) -> ProjectIndex | None:
    """处理缓存索引并返回现有契约规定的结果。"""
    with _STATE_LOCK:
        _prune_expired(now)
        entry = _INDEXES.pop(key, None)
        if entry is None:
            return None
        entry.last_access = now
        _INDEXES[key] = entry
        return entry.index


async def get_project_index(
    pid: str,
    corpus: IndexCorpus,
    source_revision: str,
    documents: Sequence[Document],
    embeddings: Embeddings,
    *,
    return_status: bool = False,
) -> ProjectIndex | tuple[ProjectIndex, Literal["build", "reuse"]]:
    """获取项目索引，并遵循现有调用契约。

    参数:
        `pid`：项目 ID。
        `corpus`：沿用签名中 `IndexCorpus` 类型约束的输入。
        `source_revision`：沿用签名中 `str` 类型约束的输入。
        `documents`：沿用签名中 `Sequence[Document]` 类型约束的输入。
        `embeddings`：沿用签名中 `Embeddings` 类型约束的输入。
        `return_status`：沿用签名中 `bool` 类型约束的输入。

    返回:
        `ProjectIndex | tuple[ProjectIndex, Literal['build', 'reuse']]`，内容保持现有调用方契约。

    异常:
        `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
    if not isinstance(pid, str) or not pid.strip():
        raise ValueError("pid is required")
    if corpus not in {"design", "requirements", "knowledge"}:
        raise ValueError("unsupported index corpus")
    if not isinstance(source_revision, str) or not source_revision.strip():
        raise ValueError("source_revision is required")
    if embeddings is None:
        raise ValueError("embeddings are required")

    key: IndexKey = (
        pid,
        corpus,
        source_revision,
        _embedding_model_identity(embeddings),
    )
    now = _clock()
    cached = _cached_index(key, now)
    if cached is not None:
        return (cached, "reuse") if return_status else cached

    with _STATE_LOCK:
        request_generation = _PROJECT_GENERATIONS.get(pid, 0)
        build_lock = _BUILD_LOCKS.get(key)
        if build_lock is None:
            build_lock = asyncio.Lock()
            _BUILD_LOCKS[key] = build_lock

    try:
        async with build_lock:
            now = _clock()
            cached = _cached_index(key, now)
            if cached is not None:
                return (cached, "reuse") if return_status else cached
            index = await asyncio.to_thread(
                _build_index,
                key,
                corpus,
                list(documents),
                embeddings,
            )
            with _STATE_LOCK:
                if _PROJECT_GENERATIONS.get(pid, 0) == request_generation:
                    _INDEXES[key] = _RegistryEntry(index=index, last_access=now)
                    _INDEXES.move_to_end(key)
                    while len(_INDEXES) > INDEX_CAPACITY:
                        _INDEXES.popitem(last=False)
            return (index, "build") if return_status else index
    finally:
        with _STATE_LOCK:
            if _BUILD_LOCKS.get(key) is build_lock:
                _BUILD_LOCKS.pop(key, None)


def invalidate_project_indexes(pid: str) -> int:
    """使失效项目indexes，并遵循现有调用契约。

    参数:
        `pid`：项目 ID。

    返回:
        `int`，内容保持现有调用方契约。

    异常:
        `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
    if not isinstance(pid, str) or not pid.strip():
        raise ValueError("pid is required")
    with _STATE_LOCK:
        keys = [key for key in _INDEXES if key[0] == pid]
        for key in keys:
            _INDEXES.pop(key, None)
        _PROJECT_GENERATIONS[pid] = _PROJECT_GENERATIONS.get(pid, 0) + 1
        return len(keys)


def index_registry_size() -> int:
    """返回当前索引注册表大小。"""
    with _STATE_LOCK:
        _prune_expired(_clock())
        return len(_INDEXES)


def _reset_index_registry_for_tests() -> None:
    """重置索引注册表面向测试，并保持现有契约。"""
    with _STATE_LOCK:
        _INDEXES.clear()
        _BUILD_LOCKS.clear()
        _PROJECT_GENERATIONS.clear()
