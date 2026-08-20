from __future__ import annotations

from collections.abc import Sequence
from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore

from llm.provider import get_lazy_embeddings
from vectorstore.splitter import (
    design_child_text_splitter,
    design_parent_text_splitter,
    knowledge_text_splitter,
    require_child_text_splitter,
    require_parent_text_splitter,
    testdoc_text_splitter_for_api,
    testdoc_text_splitter_for_nfunctional,
)

_PARENT_ID_KEY = "_ezllm_parent_id"


class EmptyRetriever:
    def invoke(self, _query: str, config=None, **_kwargs) -> list[Document]:
        return []


class ProjectScopedParentRetriever:
    def __init__(self, parents: dict[str, Document], child_retriever):
        self._parents = parents
        self._child_retriever = child_retriever

    def invoke(self, query: str, config=None, **kwargs) -> list[Document]:
        children = self._child_retriever.invoke(query, config=config, **kwargs)
        result: list[Document] = []
        seen: set[str] = set()
        for child in children:
            parent_id = child.metadata.get(_PARENT_ID_KEY)
            if parent_id is not None and parent_id not in seen:
                seen.add(parent_id)
                result.append(self._parents[parent_id])
        return result


def _vector_retriever(
    documents: Sequence[Document], *, embedding_model=None, k: int = 4
):
    if not documents:
        return EmptyRetriever()
    vectorstore = InMemoryVectorStore(
        embedding=embedding_model or get_lazy_embeddings()
    )
    vectorstore.add_documents(documents=list(documents))
    return vectorstore.as_retriever(
        search_kwargs={"k": min(k, len(documents))}
    )


def _parent_retriever(
    documents: Sequence[Document],
    *,
    parent_splitter,
    child_splitter,
    embedding_model=None,
    k: int = 6,
):
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

    child_retriever = _vector_retriever(
        children, embedding_model=embedding_model, k=k
    )
    return ProjectScopedParentRetriever(parents, child_retriever)


def design_retriever(documents, *, embedding_model=None):
    return _parent_retriever(
        documents,
        parent_splitter=design_parent_text_splitter,
        child_splitter=design_child_text_splitter,
        embedding_model=embedding_model,
    )


def require_retriever(documents, *, embedding_model=None):
    return _parent_retriever(
        documents,
        parent_splitter=require_parent_text_splitter,
        child_splitter=require_child_text_splitter,
        embedding_model=embedding_model,
    )


def knowledge_retriever(documents, *, embedding_model=None):
    texts = knowledge_text_splitter.split_documents(list(documents))
    return _vector_retriever(texts, embedding_model=embedding_model)


def api_retriever(documents, *, embedding_model=None):
    texts = testdoc_text_splitter_for_api.split_documents(list(documents))
    return _vector_retriever(texts, embedding_model=embedding_model)


def nfunctional_retriever(documents, *, embedding_model=None):
    texts = testdoc_text_splitter_for_nfunctional.split_documents(list(documents))
    return _vector_retriever(texts, embedding_model=embedding_model)
