from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

import pytest

from vectorstore.retrievers import (
    BoundedRetriever,
    RetrievalPolicy,
    design_retriever,
)


class KeywordEmbeddings(Embeddings):
    def _vector(self, text: str) -> list[float]:
        lowered = text.lower()
        return [
            float("alpha" in lowered),
            float("beta" in lowered),
            float("shared" in lowered),
        ]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


def test_design_retrievers_are_project_scoped():
    project_a = design_retriever(
        [Document(page_content="alpha shared project A")],
        embedding_model=KeywordEmbeddings(),
    )
    project_b = design_retriever(
        [Document(page_content="beta shared project B")],
        embedding_model=KeywordEmbeddings(),
    )

    a_contents = [doc.page_content for doc in project_a.invoke("alpha")]
    b_contents = [doc.page_content for doc in project_b.invoke("beta")]

    assert a_contents == ["alpha shared project A"]
    assert b_contents == ["beta shared project B"]
    assert all("project B" not in content for content in a_contents)
    assert all("project A" not in content for content in b_contents)


def test_empty_project_does_not_require_embeddings():
    retriever = design_retriever([])

    assert retriever.invoke("anything") == []


class ScoredIndex:
    def __init__(self, values):
        self.values = values
        self.fetches = []
        self.document_count = len(values)

    def similarity_search_with_score(self, query: str, k: int):
        self.fetches.append((query, k))
        return self.values[:k]


def test_bounded_retrieval_deduplicates_normalized_content_and_keeps_metadata():
    index = ScoredIndex(
        [
            (
                Document(
                    page_content=" alpha   beta\nvalue ",
                    metadata={"source": "a.md", "page": 7},
                ),
                0.95,
            ),
            (
                Document(
                    page_content="alpha beta value",
                    metadata={"source": "duplicate.md", "page": 8},
                ),
                0.90,
            ),
            (
                Document(
                    page_content="low score content",
                    metadata={"source": "low.md", "page": 9},
                ),
                0.10,
            ),
        ]
    )
    policy = RetrievalPolicy(
        top_k=2,
        fetch_k=3,
        max_context_tokens=20,
        min_score=0.25,
    )
    retriever = BoundedRetriever(
        index,
        policy,
        token_counter=lambda text: len(text.split()),
    )

    result = retriever.invoke("alpha")

    assert [item.page_content for item in result] == ["alpha beta value"]
    assert result[0].metadata == {"source": "a.md", "page": 7}
    assert index.fetches == [("alpha", 3)]
    assert retriever.last_context_tokens == 3


def test_bounded_retrieval_stops_before_context_budget_is_exceeded():
    index = ScoredIndex(
        [
            (Document(page_content="one two three"), 0.9),
            (Document(page_content="four five six"), 0.8),
            (Document(page_content="seven"), 0.7),
        ]
    )
    retriever = BoundedRetriever(
        index,
        RetrievalPolicy(3, 3, 5, 0.2),
        token_counter=lambda text: len(text.split()),
    )

    result = retriever.invoke("query")

    assert [item.page_content for item in result] == ["one two three"]
    assert retriever.last_context_tokens == 3


@pytest.mark.parametrize(
    "values",
    [
        (0, 1, 10, 0.0),
        (2, 1, 10, 0.0),
        (1, 1, 0, 0.0),
        (1, 1, 10, 1.1),
    ],
)
def test_retrieval_policy_rejects_unbounded_or_inconsistent_values(values):
    with pytest.raises(ValueError):
        RetrievalPolicy(*values)
