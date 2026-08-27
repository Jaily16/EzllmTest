from service.agentRagMeasurement import (
    RagCandidateMetrics,
    select_agent_rag_strategy,
)


def _metrics(**changes):
    values = {
        "strategy": "dense_v1",
        "slice_scores": {"p/design": (0.75, 0.70, 0.68)},
        "overall_ndcg_at_4": 0.68,
        "citation_coverage": 1.0,
        "invalid_citations": 0,
        "project_leaks": 0,
        "context_tokens": 1000,
        "model_calls": 1,
        "embedding_builds": 1,
        "cold_index_p95_ms": 10.0,
        "warm_query_p95_ms": 2.0,
    }
    values.update(changes)
    return RagCandidateMetrics(**values)


def test_hybrid_adoption_requires_all_relative_and_safety_gates():
    dense = _metrics()
    hybrid = _metrics(
        strategy="hybrid_rrf_v1",
        slice_scores={"p/design": (0.80, 0.76, 0.74)},
        overall_ndcg_at_4=0.74,
        cold_index_p95_ms=12.0,
        warm_query_p95_ms=2.3,
    )
    decision = select_agent_rag_strategy(dense, hybrid)
    assert decision.strategy == "hybrid_rrf_v1"
    assert decision.passed

    leaking = hybrid.model_copy(update={"project_leaks": 1})
    decision = select_agent_rag_strategy(dense, leaking)
    assert decision.strategy == "dense_v1"
    assert not decision.passed


def test_missing_timing_is_na_and_keeps_dense():
    dense = _metrics()
    hybrid = _metrics(
        strategy="hybrid_rrf_v1",
        slice_scores={"p/design": (0.80, 0.76, 0.74)},
        overall_ndcg_at_4=0.74,
        cold_index_p95_ms=None,
    )
    decision = select_agent_rag_strategy(dense, hybrid)
    assert decision.strategy == "dense_v1"
    assert decision.reason == "timing_not_comparable"


def test_rerank_needs_incremental_gain_and_relative_latency():
    dense = _metrics()
    hybrid = _metrics(
        strategy="hybrid_rrf_v1",
        slice_scores={"p/design": (0.80, 0.76, 0.74)},
        overall_ndcg_at_4=0.74,
        cold_index_p95_ms=12.0,
        warm_query_p95_ms=2.3,
    )
    rerank = hybrid.model_copy(
        update={
            "strategy": "hybrid_rerank_v1",
            "slice_scores": {"p/design": (0.84, 0.80, 0.78)},
            "overall_ndcg_at_4": 0.78,
            "warm_query_p95_ms": 2.5,
        }
    )
    decision = select_agent_rag_strategy(dense, hybrid, rerank)
    assert decision.strategy == "hybrid_rerank_v1"
