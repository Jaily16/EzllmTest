from langchain_core.documents import Document

from service.agentContracts import TrustedProjectScope
from service.agentRetrieval import (
    AgentEvidenceRetriever,
    bm25_tokens,
    use_agent_retrieval,
)
from vectorstore.retrievers import RetrievalPolicy


class _Index:
    def __init__(self, scored):
        self.scored = scored

    def similarity_search_with_score(self, _query, k):
        return self.scored[:k]


def test_unicode_tokenizer_is_reproducible_for_identifiers_and_chinese():
    assert bm25_tokens("Order_ID订单状态") == (
        "order_id",
        "订",
        "单",
        "状",
        "态",
        "订单",
        "单状",
        "状态",
    )


def test_agent_retrieval_emits_only_selected_metadata_citations():
    documents = [
        Document(
            page_content="Order_ID 支付确认 order identifier",
            metadata={"source": r"C:\private\design.md", "page": 2},
        ),
        Document(
            page_content="unrelated reservation route",
            metadata={"source": "/private/other.md", "page": 0},
        ),
    ]
    index = _Index([(documents[0], 0.9), (documents[1], 0.3)])
    scope = TrustedProjectScope(
        project_id="project-a", actor_id="workbench", scope_version="v1"
    )
    with use_agent_retrieval(scope, strategy="hybrid_rrf_v1") as session:
        retriever = AgentEvidenceRetriever(
            index,
            RetrievalPolicy(4, 8, 6_000, 0.2),
            documents=documents,
            corpus="design",
            source_revision="revision-1",
            index_status="build",
            session=session,
            token_counter=lambda text: len(text.split()),
        )
        selected = retriever.invoke("Order_ID 支付确认")
        evidence = session.snapshot()

    assert selected[0].metadata["_ezllm_citation_id"] == "C1"
    assert evidence is not None
    citation = evidence.queries[0].citations[0]
    assert citation.source_label == "design.md"
    assert citation.page == 3
    assert citation.rank == 1
    assert len(citation.chunk_hash) == 64
    serialized = evidence.model_dump_json()
    assert "Order_ID" not in serialized
    assert "C:\\private" not in serialized
    assert "/private" not in serialized


def test_citations_exclude_deduplicated_and_token_truncated_chunks():
    documents = [
        Document(page_content="same content", metadata={"source": "a.md"}),
        Document(page_content=" same  content ", metadata={"source": "b.md"}),
        Document(page_content="too many tokens here", metadata={"source": "c.md"}),
    ]
    index = _Index([(doc, 0.9 - index * 0.1) for index, doc in enumerate(documents)])
    scope = TrustedProjectScope(
        project_id="project-a", actor_id="workbench", scope_version="v1"
    )
    with use_agent_retrieval(scope) as session:
        retriever = AgentEvidenceRetriever(
            index,
            RetrievalPolicy(4, 8, 2, 0.2),
            documents=documents,
            corpus="knowledge",
            source_revision="revision-1",
            index_status="reuse",
            session=session,
            token_counter=lambda text: len(text.split()),
        )
        selected = retriever.invoke("same")
        evidence = session.snapshot()

    assert len(selected) == 1
    assert len(evidence.queries[0].citations) == 1
    assert evidence.context_tokens == 2


def test_project_scope_isolation_blocks_mismatched_retriever():
    scope = TrustedProjectScope(
        project_id="project-a", actor_id="workbench", scope_version="v1"
    )
    with use_agent_retrieval(scope) as session:
        try:
            session.assert_project("project-b")
        except ValueError as exc:
            assert str(exc) == "agent_retrieval_project_mismatch"
        else:
            raise AssertionError("cross-project retrieval was not rejected")
