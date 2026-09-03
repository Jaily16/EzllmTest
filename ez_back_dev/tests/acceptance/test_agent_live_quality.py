import json
import asyncio

import pytest
from langchain_core.embeddings import Embeddings

from scripts import agent_live_quality
from service import agentRuntimeFactory
from llm.streaming import ModelStreamEvent


def test_live_quality_requires_explicit_cost_confirmation():
    with pytest.raises(SystemExit, match="--confirm-cost"):
        agent_live_quality.main([])


def test_live_quality_scope_and_call_limits_are_fixed():
    assert agent_live_quality.MAX_CHAT_CALLS == 6
    assert len(agent_live_quality.PLANNER_CASES) == 6
    assert agent_live_quality.MAX_EMBEDDING_CALLS == 4
    assert len(agent_live_quality.RAG_CASES) == 3
    assert all(case.goal for case in agent_live_quality.PLANNER_CASES)
    assert all(document.page_content for document in agent_live_quality.RAG_DOCUMENTS)
    assert agent_live_quality.PLANNER_RESPONSE_FORMAT == {"type": "json_object"}


def test_public_report_rejects_sensitive_fields_and_non_finite_numbers():
    for field in (
        "credential",
        "document_content",
        "goal",
        "project_id",
        "prompt",
        "reasoning",
        "response_content",
        "traceback",
    ):
        with pytest.raises(ValueError, match="unsafe_live_report_field"):
            agent_live_quality.validate_safe_report({field: "sentinel"})
    with pytest.raises(ValueError, match="unsafe_live_report_number"):
        agent_live_quality.validate_safe_report({"latency_ms": float("nan")})


def test_public_report_shape_is_json_safe():
    report = {
        "schema_version": 1,
        "provider": "zhipu",
        "planner": {"passed": 6, "total_tokens": 123},
        "rag": {"passed": 3, "top1_accuracy": 1.0},
        "gate": {"passed": True},
    }
    agent_live_quality.validate_safe_report(report)
    assert json.loads(json.dumps(report)) == report


class _FakeEmbeddings(Embeddings):
    def embed_documents(self, texts):
        return [[1.0] for _ in texts]

    def embed_query(self, text):
        return [1.0]


def test_counting_embeddings_enforces_the_paid_call_ceiling():
    embeddings = agent_live_quality.CountingEmbeddings(_FakeEmbeddings())
    embeddings.embed_documents(["one"])
    for _ in range(agent_live_quality.MAX_EMBEDDING_CALLS - 1):
        embeddings.embed_query("query")
    assert embeddings.calls == agent_live_quality.MAX_EMBEDDING_CALLS
    with pytest.raises(RuntimeError, match="live_embedding_call_budget_exhausted"):
        embeddings.embed_query("one-too-many")


def test_runtime_provider_uses_shared_json_mode_contract(monkeypatch):
    captured = {}

    async def fake_stream(name, prompt, max_tokens, **kwargs):
        captured.update(
            {
                "name": name,
                "prompt": prompt,
                "max_tokens": max_tokens,
                **kwargs,
            }
        )
        yield ModelStreamEvent(
            "content",
            text=(
                '{"schema_version":1,"steps":'
                '[{"tool_name":"workflow_ui_case","arguments":{}}]}'
            ),
        )

    monkeypatch.setattr(agentRuntimeFactory, "stream_chat_completion", fake_stream)
    result = asyncio.run(
        agentRuntimeFactory._provider_plan(
            {
                "schema_version": 1,
                "goal": "Generate UI tests",
                "observation": {},
                "tools": [],
                "max_steps": 1,
            }
        )
    )

    assert result["steps"][0]["tool_name"] == "workflow_ui_case"
    assert "Return exactly one JSON object" in captured["prompt"]
    assert captured["request_options"]["response_format"] == {
        "type": "json_object"
    }
