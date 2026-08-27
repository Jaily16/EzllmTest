"""Pure relative adoption gates for deterministic Agent RAG candidates."""

from __future__ import annotations

from typing import Literal
import math

from pydantic import BaseModel, ConfigDict, Field


class RagCandidateMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    strategy: Literal["dense_v1", "hybrid_rrf_v1", "hybrid_rerank_v1"]
    # recall@4, MRR, nDCG@4 by project/corpus slice.
    slice_scores: dict[str, tuple[float, float, float]]
    overall_ndcg_at_4: float = Field(ge=0, le=1)
    citation_coverage: float = Field(ge=0, le=1)
    invalid_citations: int = Field(ge=0)
    project_leaks: int = Field(ge=0)
    context_tokens: int = Field(ge=0, le=6_000)
    model_calls: int = Field(ge=0)
    embedding_builds: int = Field(ge=0)
    cold_index_p95_ms: float | None = Field(default=None, gt=0)
    warm_query_p95_ms: float | None = Field(default=None, gt=0)


class RagAdoptionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    strategy: Literal["dense_v1", "hybrid_rrf_v1", "hybrid_rerank_v1"]
    passed: bool
    reason: str


RAG_BENCHMARK_PROTOCOL = {
    "seed": 20260827,
    "warmup_runs": 5,
    "measurement_runs": 30,
    "concurrency": (1, 4),
    "scales": ("small", "large"),
    "modes": ("cold", "warm"),
    "discard_outliers": False,
}


def recall_at_k(ranked: list[str], qrels: dict[str, int], k: int = 4) -> float:
    relevant = {key for key, grade in qrels.items() if grade > 0}
    if not relevant:
        return 1.0
    return len(relevant & set(ranked[:k])) / len(relevant)


def reciprocal_rank(ranked: list[str], qrels: dict[str, int]) -> float:
    for index, key in enumerate(ranked, start=1):
        if qrels.get(key, 0) > 0:
            return 1.0 / index
    return 0.0


def ndcg_at_k(ranked: list[str], qrels: dict[str, int], k: int = 4) -> float:
    def discounted(grades: list[int]) -> float:
        return sum(
            (2**grade - 1) / math.log2(index + 2)
            for index, grade in enumerate(grades)
        )

    actual = discounted([qrels.get(key, 0) for key in ranked[:k]])
    ideal = discounted(sorted(qrels.values(), reverse=True)[:k])
    return actual / ideal if ideal else 1.0


def _correctness_and_safety_pass(
    dense: RagCandidateMetrics, candidate: RagCandidateMetrics
) -> bool:
    if set(candidate.slice_scores) != set(dense.slice_scores):
        return False
    if any(
        candidate.slice_scores[key][metric] + 1e-12
        < dense.slice_scores[key][metric]
        for key in dense.slice_scores
        for metric in range(3)
    ):
        return False
    return (
        candidate.citation_coverage == 1.0
        and candidate.invalid_citations == 0
        and candidate.project_leaks == 0
        and candidate.context_tokens <= 6_000
        and candidate.context_tokens <= dense.context_tokens * 1.05
        and candidate.model_calls <= dense.model_calls
        and candidate.embedding_builds <= dense.embedding_builds
    )


def select_agent_rag_strategy(
    dense: RagCandidateMetrics,
    hybrid: RagCandidateMetrics,
    rerank: RagCandidateMetrics | None = None,
) -> RagAdoptionDecision:
    if (
        not _correctness_and_safety_pass(dense, hybrid)
        or hybrid.overall_ndcg_at_4 < dense.overall_ndcg_at_4 + 0.05
    ):
        return RagAdoptionDecision(
            strategy="dense_v1", passed=False, reason="hybrid_gate_failed"
        )
    if any(
        value is None
        for value in (
            dense.cold_index_p95_ms,
            dense.warm_query_p95_ms,
            hybrid.cold_index_p95_ms,
            hybrid.warm_query_p95_ms,
        )
    ):
        return RagAdoptionDecision(
            strategy="dense_v1", passed=False, reason="timing_not_comparable"
        )
    hybrid_passes = (
        hybrid.cold_index_p95_ms <= dense.cold_index_p95_ms * 1.25
        and hybrid.warm_query_p95_ms <= dense.warm_query_p95_ms * 1.20
    )
    if not hybrid_passes:
        return RagAdoptionDecision(
            strategy="dense_v1", passed=False, reason="hybrid_gate_failed"
        )
    if rerank is not None:
        rerank_comparable = (
            rerank.cold_index_p95_ms is not None
            and rerank.warm_query_p95_ms is not None
        )
        if (
            rerank_comparable
            and _correctness_and_safety_pass(hybrid, rerank)
            and rerank.overall_ndcg_at_4 >= hybrid.overall_ndcg_at_4 + 0.03
            and rerank.warm_query_p95_ms <= hybrid.warm_query_p95_ms * 1.10
        ):
            return RagAdoptionDecision(
                strategy="hybrid_rerank_v1", passed=True, reason="rerank_gate_passed"
            )
    return RagAdoptionDecision(
        strategy="hybrid_rrf_v1", passed=True, reason="hybrid_gate_passed"
    )
