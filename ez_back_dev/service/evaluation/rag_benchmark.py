"""Offline synthetic RAG benchmark using deterministic fake dense scores."""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from langchain_core.documents import Document

from service.agent.contracts import TrustedProjectScope
from service.evaluation.rag_measurement import (
    RagCandidateMetrics,
    ndcg_at_k,
    recall_at_k,
    reciprocal_rank,
)
from service.retrieval.agent import AgentEvidenceRetriever, bm25_tokens, use_agent_retrieval
from service.retrieval.factory import RetrievalPolicy


class DeterministicFakeDenseIndex:
    """Stable token-hash vectors; never contacts an embedding provider."""

    def __init__(self, documents: list[Document], dimensions: int = 64) -> None:
        self.documents = documents
        self.dimensions = dimensions

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in bm25_tokens(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            vector[int.from_bytes(digest[:2], "big") % self.dimensions] += 1.0
        length = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / length for value in vector]

    def similarity_search_with_score(self, query: str, k: int):
        query_vector = self._vector(query)
        ranked = []
        for document in self.documents:
            document_vector = self._vector(document.page_content)
            score = sum(
                left * right
                for left, right in zip(query_vector, document_vector, strict=True)
            )
            ranked.append((document, score))
        return sorted(
            ranked,
            key=lambda item: (
                -item[1],
                str(item[0].metadata.get("document_id", "")),
            ),
        )[:k]


def load_rag_dataset(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if value.get("schema_version") != 1 or value.get("seed") != 20260827:
        raise ValueError("unsupported synthetic RAG dataset")
    if len(value.get("queries", [])) < 24:
        raise ValueError("synthetic RAG dataset is too small")
    return value


def benchmark_strategy(
    dataset: dict[str, Any], strategy: str
) -> RagCandidateMetrics:
    documents_by_slice: dict[tuple[str, str], list[Document]] = defaultdict(list)
    for project in dataset["projects"]:
        for item in project["documents"]:
            documents_by_slice[(project["id"], item["corpus"])].append(
                Document(
                    page_content=item["text"],
                    metadata={
                        "source": item["source"],
                        "page": item["page"] - 1,
                        "document_id": item["id"],
                    },
                )
            )
    scores: dict[str, list[tuple[float, float, float]]] = defaultdict(list)
    context_tokens = 0
    invalid_citations = 0
    citation_count = 0
    selected_count = 0
    for query in dataset["queries"]:
        key = (query["project_id"], query["corpus"])
        documents = documents_by_slice[key]
        index = DeterministicFakeDenseIndex(documents)
        scope = TrustedProjectScope(
            project_id=query["project_id"],
            actor_id="deterministic-benchmark",
            scope_version="iteration4-aspect5-v1",
        )
        with use_agent_retrieval(scope, strategy=strategy) as session:
            retriever = AgentEvidenceRetriever(
                index,
                RetrievalPolicy(4, 8, 6_000, 0.2),
                documents=documents,
                corpus=query["corpus"],
                source_revision="synthetic-revision-v1",
                index_status="build",
                session=session,
                token_counter=lambda text: len(bm25_tokens(text)),
            )
            ranked_documents = retriever.invoke(query["query"])
            evidence = session.snapshot()
        ranked = [item.metadata["document_id"] for item in ranked_documents]
        qrels = {key: int(value) for key, value in query["qrels"].items()}
        scores[f"{query['project_id']}/{query['corpus']}"] .append(
            (
                recall_at_k(ranked, qrels),
                reciprocal_rank(ranked, qrels),
                ndcg_at_k(ranked, qrels),
            )
        )
        if evidence is not None:
            context_tokens = max(context_tokens, evidence.context_tokens)
            citations = evidence.queries[0].citations
            citation_count += len(citations)
            selected_count += len(ranked)
            invalid_citations += sum(
                citation.citation_id != f"C{citation.rank}"
                for citation in citations
            )
    slice_scores = {
        key: tuple(
            sum(row[index] for row in rows) / len(rows)
            for index in range(3)
        )
        for key, rows in sorted(scores.items())
    }
    overall_ndcg = sum(value[2] for value in slice_scores.values()) / len(
        slice_scores
    )
    return RagCandidateMetrics(
        strategy=strategy,
        slice_scores=slice_scores,
        overall_ndcg_at_4=overall_ndcg,
        citation_coverage=(citation_count / selected_count if selected_count else 1.0),
        invalid_citations=invalid_citations,
        project_leaks=0,
        context_tokens=context_tokens,
        model_calls=0,
        embedding_builds=len(documents_by_slice),
        cold_index_p95_ms=None,
        warm_query_p95_ms=None,
    )
