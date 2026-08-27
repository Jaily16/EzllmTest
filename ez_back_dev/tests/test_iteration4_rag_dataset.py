import json
from pathlib import Path

from service.agentRagBenchmark import benchmark_strategy, load_rag_dataset
from service.agentRagMeasurement import RAG_BENCHMARK_PROTOCOL, select_agent_rag_strategy


FIXTURES = Path(__file__).parent / "fixtures"


def test_dataset_is_versioned_synthetic_isolated_and_covers_the_matrix():
    dataset = load_rag_dataset(FIXTURES / "iteration4_rag_eval_v1.json")
    assert len(dataset["projects"]) == 2
    assert len(dataset["queries"]) >= 24
    assert {item["corpus"] for item in dataset["queries"]} == {
        "requirements", "design", "knowledge"
    }
    assert {item["scale"] for project in dataset["projects"] for item in project["documents"]} == {"small", "large"}
    project_documents = {
        project["id"]: {item["id"] for item in project["documents"]}
        for project in dataset["projects"]
    }
    for query in dataset["queries"]:
        assert set(query["qrels"]) <= project_documents[query["project_id"]]


def test_fake_provider_benchmark_is_repeatable_and_keeps_dense_when_timing_is_na():
    dataset = load_rag_dataset(FIXTURES / "iteration4_rag_eval_v1.json")
    dense = benchmark_strategy(dataset, "dense_v1")
    hybrid = benchmark_strategy(dataset, "hybrid_rrf_v1")
    rerank = benchmark_strategy(dataset, "hybrid_rerank_v1")
    assert dense == benchmark_strategy(dataset, "dense_v1")
    assert dense.project_leaks == hybrid.project_leaks == rerank.project_leaks == 0
    assert dense.invalid_citations == hybrid.invalid_citations == rerank.invalid_citations == 0
    assert dense.citation_coverage == hybrid.citation_coverage == rerank.citation_coverage == 1.0
    decision = select_agent_rag_strategy(dense, hybrid, rerank)
    assert decision.strategy == "dense_v1"
    assert decision.reason == "hybrid_gate_failed"


def test_benchmark_protocol_freezes_warmup_samples_and_matrix():
    assert RAG_BENCHMARK_PROTOCOL == {
        "seed": 20260827,
        "warmup_runs": 5,
        "measurement_runs": 30,
        "concurrency": (1, 4),
        "scales": ("small", "large"),
        "modes": ("cold", "warm"),
        "discard_outliers": False,
    }


def test_versioned_decision_does_not_claim_wall_clock_or_provider_results():
    decision = json.loads(
        (FIXTURES / "iteration4_aspect5_rag_decision_v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert decision["active_strategy"] == "dense_v1"
    assert decision["wall_clock_gate"] == "N/A"
    assert decision["model_provider_calls"] == 0
    assert decision["real_embedding_calls"] == 0
