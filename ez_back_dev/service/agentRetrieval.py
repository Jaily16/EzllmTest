"""Agent-only retrieval policy and metadata-only citation collection."""

from __future__ import annotations

import hashlib
import math
import re
import time
import unicodedata
from collections import Counter
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any, Iterator, Literal, Sequence

from langchain_core.documents import Document

from service.agentContracts import TrustedProjectScope
from service.agentToolSchemas import (
    RetrievalCitation,
    RetrievalQueryEvidence,
    ToolRetrievalEvidence,
)
from service.agentTelemetry import agent_span, get_agent_telemetry


AgentRagStrategy = Literal[
    "dense_v1", "hybrid_rrf_v1", "hybrid_rerank_v1"
]
AGENT_RAG_POLICY_VERSION = "iteration4-aspect5-v1"
# The versioned adoption decision keeps dense until comparable wall-clock
# measurements satisfy every gate.  Hybrid candidates remain benchmarkable.
ACTIVE_AGENT_RAG_STRATEGY: AgentRagStrategy = "dense_v1"
_CITATION_KEY = "_ezllm_citation_id"
_ENGLISH_OR_CJK = re.compile(r"[a-z0-9_]+|[\u3400-\u9fff]+")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def _normalized_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split())


def bm25_tokens(value: str) -> tuple[str, ...]:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    result: list[str] = []
    for token in _ENGLISH_OR_CJK.findall(normalized):
        if all("\u3400" <= char <= "\u9fff" for char in token):
            result.extend(token)
            result.extend(token[index : index + 2] for index in range(len(token) - 1))
        else:
            result.append(token)
    return tuple(result)


def _document_id(document: Document) -> str:
    return hashlib.sha256(
        _normalized_text(document.page_content).encode("utf-8")
    ).hexdigest()


def _bm25_scores(query: str, documents: Sequence[Document]) -> dict[str, float]:
    query_terms = bm25_tokens(query)
    if not query_terms or not documents:
        return {}
    tokenized = [bm25_tokens(item.page_content) for item in documents]
    lengths = [len(items) for items in tokenized]
    average_length = sum(lengths) / max(1, len(lengths))
    document_frequency = Counter(
        token for tokens in tokenized for token in set(tokens)
    )
    scores: dict[str, float] = {}
    for document, tokens, length in zip(documents, tokenized, lengths, strict=True):
        frequency = Counter(tokens)
        score = 0.0
        for term in query_terms:
            count = frequency.get(term, 0)
            if not count:
                continue
            frequency_count = document_frequency[term]
            inverse = math.log(
                1.0 + (len(documents) - frequency_count + 0.5) / (frequency_count + 0.5)
            )
            denominator = count + 1.5 * (
                1.0 - 0.75 + 0.75 * length / max(1.0, average_length)
            )
            score += inverse * count * 2.5 / denominator
        scores[_document_id(document)] = score
    maximum = max(scores.values(), default=0.0)
    if maximum <= 0:
        return {key: 0.0 for key in scores}
    return {key: value / maximum for key, value in scores.items()}


def _safe_source_label(metadata: dict[str, Any]) -> str:
    raw = str(metadata.get("source") or "document")
    label = PurePosixPath(raw.replace("\\", "/")).name
    label = _CONTROL.sub("", label).strip()
    return (label or "document")[:128]


def _page_number(metadata: dict[str, Any]) -> int:
    raw = metadata.get("page")
    return raw + 1 if isinstance(raw, int) and raw >= 0 else 1


@dataclass
class AgentRetrievalSession:
    project_id: str
    scope_hash: str
    strategy: AgentRagStrategy
    queries: list[RetrievalQueryEvidence] = field(default_factory=list)

    def assert_project(self, project_id: str) -> None:
        if project_id != self.project_id:
            raise ValueError("agent_retrieval_project_mismatch")

    def record(self, evidence: RetrievalQueryEvidence) -> None:
        self.queries.append(evidence)

    def snapshot(self) -> ToolRetrievalEvidence | None:
        if not self.queries:
            return None
        return ToolRetrievalEvidence(
            strategy=self.strategy,
            queries=tuple(self.queries),
            context_tokens=sum(item.context_tokens for item in self.queries),
            index_builds=sum(item.index_status == "build" for item in self.queries),
            index_reuses=sum(item.index_status == "reuse" for item in self.queries),
        )


_ACTIVE_SESSION: ContextVar[AgentRetrievalSession | None] = ContextVar(
    "ezllm_agent_retrieval_session", default=None
)


def _scope_hash(scope: TrustedProjectScope) -> str:
    value = "\x00".join(
        (scope.project_id, scope.actor_id, scope.scope_version)
    )
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@contextmanager
def use_agent_retrieval(
    scope: TrustedProjectScope,
    *,
    strategy: AgentRagStrategy = ACTIVE_AGENT_RAG_STRATEGY,
) -> Iterator[AgentRetrievalSession]:
    session = AgentRetrievalSession(
        project_id=scope.project_id,
        scope_hash=_scope_hash(scope),
        strategy=strategy,
    )
    token = _ACTIVE_SESSION.set(session)
    try:
        yield session
    finally:
        _ACTIVE_SESSION.reset(token)


def active_agent_retrieval(project_id: str) -> AgentRetrievalSession | None:
    session = _ACTIVE_SESSION.get()
    if session is not None:
        session.assert_project(project_id)
    return session


class AgentEvidenceRetriever:
    def __init__(
        self,
        index: Any,
        policy: Any,
        *,
        documents: Sequence[Document],
        corpus: Literal["design", "requirements", "knowledge"],
        source_revision: str,
        index_status: Literal["build", "reuse"],
        session: AgentRetrievalSession,
        token_counter,
    ) -> None:
        self._index = index
        self._policy = policy
        self._documents = tuple(documents)
        self._corpus = corpus
        self._source_revision = source_revision
        self._index_status = index_status
        self._session = session
        self._token_counter = token_counter
        self.last_context_tokens = 0

    def _ranked(self, query: str) -> list[tuple[Document, float, str]]:
        dense_pairs = self._index.similarity_search_with_score(
            query, k=self._policy.fetch_k
        )
        dense = [
            (document, float(score))
            for document, score in dense_pairs
            if math.isfinite(float(score)) and score >= self._policy.min_score
        ]
        if self._session.strategy == "dense_v1":
            return [(document, score, "dense") for document, score in dense]

        bm25 = _bm25_scores(query, self._documents)
        by_id = {_document_id(item): item for item in self._documents}
        dense_rank = {
            _document_id(document): rank
            for rank, (document, _score) in enumerate(dense, start=1)
        }
        lexical_rank = {
            key: rank
            for rank, (key, score) in enumerate(
                sorted(bm25.items(), key=lambda item: (-item[1], item[0])),
                start=1,
            )
            if score >= self._policy.min_score
        }
        keys = set(dense_rank) | set(lexical_rank)
        fused = {
            key: (1 / (60 + dense_rank[key]) if key in dense_rank else 0)
            + (1 / (60 + lexical_rank[key]) if key in lexical_rank else 0)
            for key in keys
        }
        ranked = sorted(fused, key=lambda key: (-fused[key], key))
        if self._session.strategy == "hybrid_rerank_v1":
            query_terms = set(bm25_tokens(query))

            def rerank_key(key: str):
                terms = set(bm25_tokens(by_id[key].page_content))
                coverage = len(query_terms & terms) / max(1, len(query_terms))
                identifier = sum(
                    1 for term in query_terms if "_" in term and term in terms
                )
                return (-identifier, -coverage, -fused[key], key)

            ranked.sort(key=rerank_key)
            return [
                (
                    by_id[key],
                    len(query_terms & set(bm25_tokens(by_id[key].page_content)))
                    / max(1, len(query_terms)),
                    "term_coverage",
                )
                for key in ranked[: self._policy.fetch_k]
            ]
        return [
            (by_id[key], fused[key], "rrf")
            for key in ranked[: self._policy.fetch_k]
        ]

    def _invoke(self, query: str, config=None, **_kwargs) -> list[Document]:
        del config
        ranked = self._ranked(query)
        selected: list[Document] = []
        citations: list[RetrievalCitation] = []
        seen: set[str] = set()
        total_tokens = 0
        for document, score, score_kind in ranked:
            content = _normalized_text(document.page_content)
            if not content:
                continue
            content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            if content_hash in seen:
                continue
            tokens = self._token_counter(content)
            if total_tokens + tokens > self._policy.max_context_tokens:
                break
            seen.add(content_hash)
            total_tokens += tokens
            rank = len(selected) + 1
            citation_id = f"C{rank}"
            metadata = dict(document.metadata)
            source_label = _safe_source_label(metadata)
            page = _page_number(metadata)
            chunk_binding = "\x00".join(
                (
                    self._session.scope_hash,
                    self._source_revision,
                    self._corpus,
                    source_label,
                    str(page),
                    content,
                )
            )
            chunk_hash = hashlib.sha256(chunk_binding.encode("utf-8")).hexdigest()
            metadata[_CITATION_KEY] = citation_id
            selected.append(Document(page_content=content, metadata=metadata))
            citations.append(
                RetrievalCitation(
                    citation_id=citation_id,
                    corpus=self._corpus,
                    source_label=source_label,
                    page=page,
                    rank=rank,
                    score=score,
                    score_kind=score_kind,
                    chunk_hash=chunk_hash,
                )
            )
            if len(selected) >= self._policy.top_k:
                break
        self.last_context_tokens = total_tokens
        self._session.record(
            RetrievalQueryEvidence(
                strategy=self._session.strategy,
                corpus=self._corpus,
                source_revision=self._source_revision,
                query_hash=hashlib.sha256(
                    _normalized_text(query).encode("utf-8")
                ).hexdigest(),
                index_status=self._index_status,
                context_tokens=total_tokens,
                citations=tuple(citations),
            )
        )
        return selected

    def invoke(self, query: str, config=None, **kwargs) -> list[Document]:
        started = time.perf_counter()
        status = "error"
        telemetry = get_agent_telemetry()
        try:
            with agent_span(
                "agent.retrieval",
                {
                    "retrieval.corpus": self._corpus,
                    "retrieval.strategy": self._session.strategy,
                    "retrieval.index.action": self._index_status,
                },
            ):
                result = self._invoke(query, config=config, **kwargs)
            status = "success"
            return result
        finally:
            telemetry.counter(
                "ezllm.agent.retrieval.queries",
                labels={
                    "corpus": self._corpus,
                    "strategy": self._session.strategy,
                    "status": status,
                },
            )
            telemetry.histogram(
                "ezllm.agent.retrieval.duration",
                (time.perf_counter() - started) * 1_000,
                {
                    "corpus": self._corpus,
                    "strategy": self._session.strategy,
                    "status": status,
                },
            )
