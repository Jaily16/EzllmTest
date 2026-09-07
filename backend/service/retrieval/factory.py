from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from infrastructure.llm.gateway import get_lazy_embeddings
from service.project.documents import num_tokens_from_string
from service.retrieval.index import IndexCorpus, get_project_index
from service.retrieval.splitters import (
    design_child_text_splitter,
    design_parent_text_splitter,
    knowledge_text_splitter,
    require_child_text_splitter,
    require_parent_text_splitter,
    testdoc_text_splitter_for_api,
    testdoc_text_splitter_for_nfunctional,
)

_PARENT_ID_KEY = "_ezllm_parent_id"


@dataclass(frozen=True)
class RetrievalPolicy:
    top_k: int
    fetch_k: int
    max_context_tokens: int
    min_score: float

    def __post_init__(self) -> None:
        """在数据类初始化后校验并规范化实例状态。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
        if self.top_k <= 0:
            raise ValueError("top_k must be positive")
        if self.fetch_k < self.top_k:
            raise ValueError("fetch_k must be at least top_k")
        if self.max_context_tokens <= 0:
            raise ValueError("max_context_tokens must be positive")
        if not -1.0 <= self.min_score <= 1.0:
            raise ValueError("min_score must be between -1 and 1")


DESIGN_RETRIEVAL_POLICY = RetrievalPolicy(4, 8, 6_000, 0.20)
REQUIREMENTS_RETRIEVAL_POLICY = RetrievalPolicy(4, 8, 6_000, 0.20)
KNOWLEDGE_RETRIEVAL_POLICY = RetrievalPolicy(4, 8, 6_000, 0.20)


class BoundedRetriever:
    def __init__(
        self,
        index: Any,
        policy: RetrievalPolicy,
        *,
        token_counter: Callable[[str], int] = num_tokens_from_string,
    ) -> None:
        """初始化实例并保存后续操作所需的依赖与状态。"""
        self._index = index
        self._policy = policy
        self._token_counter = token_counter
        self.last_context_tokens = 0

    def invoke(self, query: str, config=None, **_kwargs) -> list[Document]:
        """调用当前适配器封装的下游能力，并返回既有契约规定的结果。

        参数:
            `query`：沿用签名中 `str` 类型约束的输入。
            `config`：显式运行配置。
            `_kwargs`：调用方传入的现有参数。

        返回:
            `list[Document]`，内容保持现有调用方契约。"""
        del config
        scored = self._index.similarity_search_with_score(
            query,
            k=self._policy.fetch_k,
        )
        result: list[Document] = []
        seen: set[str] = set()
        total_tokens = 0
        for document, score in scored:
            if score < self._policy.min_score:
                continue
            content = " ".join(document.page_content.split())
            if not content:
                continue
            content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            if content_hash in seen:
                continue
            tokens = self._token_counter(content)
            if total_tokens + tokens > self._policy.max_context_tokens:
                break
            seen.add(content_hash)
            result.append(Document(page_content=content, metadata=dict(document.metadata)))
            total_tokens += tokens
            if len(result) >= self._policy.top_k:
                break
        self.last_context_tokens = total_tokens
        return result


async def get_project_retriever(
    pid: str,
    corpus: IndexCorpus,
    source_revision: str,
    documents: Sequence[Document],
    *,
    embedding_model=None,
    policy: RetrievalPolicy | None = None,
) -> BoundedRetriever:
    """获取项目检索器，并遵循现有调用契约。

    参数:
        `pid`：项目 ID。
        `corpus`：沿用签名中 `IndexCorpus` 类型约束的输入。
        `source_revision`：沿用签名中 `str` 类型约束的输入。
        `documents`：沿用签名中 `Sequence[Document]` 类型约束的输入。
        `embedding_model`：调用方传入的现有参数。
        `policy`：沿用签名中 `RetrievalPolicy | None` 类型约束的输入。

    返回:
        `BoundedRetriever`，内容保持现有调用方契约。"""
    from service.retrieval.agent import active_agent_retrieval

    agent_session = active_agent_retrieval(pid)
    embeddings = embedding_model or get_lazy_embeddings()
    index_result = await get_project_index(
        pid,
        corpus,
        source_revision,
        documents,
        embeddings,
        return_status=agent_session is not None,
    )
    if agent_session is not None:
        index, index_status = index_result
    else:
        index = index_result
    selected_policy = (
        policy
        or {
            "design": DESIGN_RETRIEVAL_POLICY,
            "requirements": REQUIREMENTS_RETRIEVAL_POLICY,
            "knowledge": KNOWLEDGE_RETRIEVAL_POLICY,
        }[corpus]
    )
    if agent_session is None:
        return BoundedRetriever(index, selected_policy)
    from service.retrieval.agent import AgentEvidenceRetriever

    return AgentEvidenceRetriever(
        index,
        selected_policy,
        documents=index.documents,
        corpus=corpus,
        source_revision=source_revision,
        index_status=index_status,
        session=agent_session,
        token_counter=num_tokens_from_string,
    )


class EmptyRetriever:
    def invoke(self, _query: str, config=None, **_kwargs) -> list[Document]:
        """调用当前适配器封装的下游能力，并返回既有契约规定的结果。"""
        return []


class ProjectScopedParentRetriever:
    def __init__(self, parents: dict[str, Document], child_retriever):
        """初始化实例并保存后续操作所需的依赖与状态。"""
        self._parents = parents
        self._child_retriever = child_retriever

    def invoke(self, query: str, config=None, **kwargs) -> list[Document]:
        """调用当前适配器封装的下游能力，并返回既有契约规定的结果。"""
        children = self._child_retriever.invoke(query, config=config, **kwargs)
        result: list[Document] = []
        seen: set[str] = set()
        for child in children:
            parent_id = child.metadata.get(_PARENT_ID_KEY)
            if parent_id is not None and parent_id not in seen:
                seen.add(parent_id)
                result.append(self._parents[parent_id])
        return result


def _vector_retriever(documents: Sequence[Document], *, embedding_model=None, k: int = 4):
    """处理向量检索器并返回现有契约规定的结果。"""
    if not documents:
        return EmptyRetriever()
    vectorstore = InMemoryVectorStore(embedding=embedding_model or get_lazy_embeddings())
    vectorstore.add_documents(documents=list(documents))
    return vectorstore.as_retriever(search_kwargs={"k": min(k, len(documents))})


def _parent_retriever(
    documents: Sequence[Document],
    *,
    parent_splitter,
    child_splitter,
    embedding_model=None,
    k: int = 6,
):
    """处理父级检索器并返回现有契约规定的结果。

    参数:
        `documents`：沿用签名中 `Sequence[Document]` 类型约束的输入。
        `parent_splitter`：调用方传入的现有参数。
        `child_splitter`：调用方传入的现有参数。
        `embedding_model`：调用方传入的现有参数。
        `k`：沿用签名中 `int` 类型约束的输入。"""
    if not documents:
        return EmptyRetriever()

    parent_documents = parent_splitter.split_documents(list(documents))
    parents: dict[str, Document] = {}
    children: list[Document] = []
    for index, parent in enumerate(parent_documents):
        parent_id = str(index)
        parents[parent_id] = Document(
            page_content=parent.page_content,
            metadata=dict(parent.metadata),
        )
        marked_parent = Document(
            page_content=parent.page_content,
            metadata={**parent.metadata, _PARENT_ID_KEY: parent_id},
        )
        children.extend(child_splitter.split_documents([marked_parent]))

    child_retriever = _vector_retriever(children, embedding_model=embedding_model, k=k)
    return ProjectScopedParentRetriever(parents, child_retriever)


def design_retriever(documents, *, embedding_model=None):
    """处理设计检索器并返回现有契约规定的结果。"""
    return _parent_retriever(
        documents,
        parent_splitter=design_parent_text_splitter,
        child_splitter=design_child_text_splitter,
        embedding_model=embedding_model,
    )


def require_retriever(documents, *, embedding_model=None):
    """读取并校验检索器，并保持现有契约。"""
    return _parent_retriever(
        documents,
        parent_splitter=require_parent_text_splitter,
        child_splitter=require_child_text_splitter,
        embedding_model=embedding_model,
    )


def knowledge_retriever(documents, *, embedding_model=None):
    """处理知识库检索器并返回现有契约规定的结果。"""
    texts = knowledge_text_splitter.split_documents(list(documents))
    return _vector_retriever(texts, embedding_model=embedding_model)


def api_retriever(documents, *, embedding_model=None):
    """处理API检索器并返回现有契约规定的结果。"""
    texts = testdoc_text_splitter_for_api.split_documents(list(documents))
    return _vector_retriever(texts, embedding_model=embedding_model)


def nfunctional_retriever(documents, *, embedding_model=None):
    """处理非功能测试检索器并返回现有契约规定的结果。"""
    texts = testdoc_text_splitter_for_nfunctional.split_documents(list(documents))
    return _vector_retriever(texts, embedding_model=embedding_model)
