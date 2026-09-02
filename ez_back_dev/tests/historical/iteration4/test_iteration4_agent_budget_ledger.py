from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from service.agentBudgetLedger import (
    AgentBudgetExceeded,
    RedisAgentBudgetLedger,
    current_agent_budget,
    reserve_embedding_budget,
    reserve_model_budget,
    reserve_tool_budget,
    use_agent_budget,
)
from service.agentContracts import RunBudget, UsageCounters
from service.agentRedisCoordinator import AgentRedisCoordinator, AgentRedisSettings


REDIS_URL = os.getenv("EZLLM_TEST_REDIS_URL")


def _settings() -> AgentRedisSettings:
    if not REDIS_URL:
        pytest.skip("EZLLM_TEST_REDIS_URL is not configured")
    return AgentRedisSettings(
        url=REDIS_URL,
        prefix=f"ezllm:test:aspect3:budget:{uuid4().hex}",
        lease_ttl_seconds=5,
        lease_renew_seconds=1,
        state_ttl_seconds=60,
    )


def _budget(**changes) -> RunBudget:
    values = {
        "max_steps": 3,
        "max_elapsed_ms": 60_000,
        "max_input_tokens": 100,
        "max_output_tokens": 80,
        "max_model_calls": 2,
        "max_embedding_calls": 1,
        "max_tool_calls": 2,
        "max_estimated_cost_units": 20,
    }
    values.update(changes)
    return RunBudget(**values)


def test_budget_is_atomic_monotonic_and_cannot_expand_on_recovery():
    async def scenario():
        settings = _settings()
        coordinator = AgentRedisCoordinator(settings)
        ledger = RedisAgentBudgetLedger(coordinator)
        now = datetime.now(UTC)
        try:
            lease = await coordinator.acquire_lease(
                "scope", "iteration4-aspect3-v1", "budget-thread", "worker-a"
            )
            assert lease is not None
            await ledger.initialize(
                lease, _budget(), started_at=now, deadline_at=now + timedelta(seconds=60)
            )
            first = await ledger.reserve(
                lease,
                "model-1",
                UsageCounters(
                    input_tokens=20,
                    output_tokens=30,
                    model_calls=1,
                    estimated_cost_units=5,
                ),
                now=now,
            )
            assert first.model_calls == 1
            duplicate = await ledger.reserve(
                lease,
                "model-1",
                UsageCounters(
                    input_tokens=20,
                    output_tokens=30,
                    model_calls=1,
                    estimated_cost_units=5,
                ),
                now=now,
            )
            assert duplicate == first
            with pytest.raises(ValueError, match="immutable"):
                await ledger.initialize(
                    lease,
                    _budget(max_model_calls=3),
                    started_at=now,
                    deadline_at=now + timedelta(seconds=60),
                )
            await ledger.reserve(
                lease,
                "model-2",
                UsageCounters(model_calls=1, output_tokens=20),
                now=now,
            )
            with pytest.raises(AgentBudgetExceeded, match="model_calls"):
                await ledger.reserve(
                    lease,
                    "model-3",
                    UsageCounters(model_calls=1),
                    now=now,
                )
            snapshot = await ledger.snapshot(lease)
            assert snapshot.model_calls == 2
            assert snapshot.output_tokens == 50
        finally:
            await coordinator.delete_test_namespace()
            await coordinator.aclose()

    asyncio.run(scenario())


def test_budget_rejects_expired_deadline_and_stale_fence():
    async def scenario():
        settings = _settings()
        coordinator = AgentRedisCoordinator(settings)
        ledger = RedisAgentBudgetLedger(coordinator)
        now = datetime.now(UTC)
        try:
            lease = await coordinator.acquire_lease(
                "scope", "iteration4-aspect3-v1", "deadline", "worker-a"
            )
            assert lease is not None
            await ledger.initialize(
                lease,
                _budget(),
                started_at=now - timedelta(seconds=2),
                deadline_at=now - timedelta(seconds=1),
            )
            with pytest.raises(AgentBudgetExceeded, match="deadline"):
                await ledger.reserve(
                    lease, "late", UsageCounters(tool_calls=1), now=now
                )
            await coordinator.release_lease(lease)
            with pytest.raises(Exception, match="lease"):
                await ledger.snapshot(lease)
        finally:
            await coordinator.delete_test_namespace()
            await coordinator.aclose()

    asyncio.run(scenario())


def test_context_guard_is_agent_only_and_reserves_model_embedding_and_tool_calls():
    async def scenario():
        settings = _settings()
        coordinator = AgentRedisCoordinator(settings)
        ledger = RedisAgentBudgetLedger(coordinator)
        now = datetime.now(UTC)
        try:
            lease = await coordinator.acquire_lease(
                "scope", "iteration4-aspect3-v1", "guard", "worker-a"
            )
            assert lease is not None
            await ledger.initialize(
                lease, _budget(), started_at=now, deadline_at=now + timedelta(seconds=60)
            )
            assert current_agent_budget() is None
            guard = ledger.sync_guard(
                lease,
                model_max_output_tokens=10,
                model_cost_units=2,
                embedding_cost_units=1,
            )
            with use_agent_budget(guard):
                assert current_agent_budget() is guard
                reserve_model_budget("abcd" * 4)
                reserve_embedding_budget(["synthetic text"])
                reserve_tool_budget()
            assert current_agent_budget() is None
            snapshot = await ledger.snapshot(lease)
            assert snapshot.model_calls == 1
            assert snapshot.embedding_calls == 1
            assert snapshot.tool_calls == 1
            assert snapshot.output_tokens == 10
            assert snapshot.estimated_cost_units == 3
        finally:
            await coordinator.delete_test_namespace()
            await coordinator.aclose()

    asyncio.run(scenario())


def test_legacy_no_context_hooks_are_no_ops():
    assert current_agent_budget() is None
    assert reserve_model_budget("legacy") is None
    assert reserve_embedding_budget(["legacy"]) is None
    assert reserve_tool_budget() is None


def test_provider_and_embedding_hooks_run_only_inside_agent_context(monkeypatch):
    from llm import provider

    calls: list[tuple[str, object]] = []

    class Guard:
        def reserve_model(self, value):
            calls.append(("model", value))

        def reserve_embedding(self, texts):
            calls.append(("embedding", tuple(texts)))

        def reserve_tool(self):
            calls.append(("tool", None))

    class ChatClient:
        def invoke(self, value):
            return type("Result", (), {"content": "safe result"})()

    class Embeddings:
        def embed_query(self, _text):
            return [0.0]

        def embed_documents(self, texts):
            return [[0.0] for _ in texts]

    monkeypatch.setattr(provider, "get_chat_client", lambda *_args: ChatClient())
    monkeypatch.setattr(provider, "get_embeddings", lambda: Embeddings())

    provider.invoke_chat_model("DeepSeek", "legacy")
    provider.LazyZhipuEmbeddings().embed_query("legacy")
    assert calls == []

    with use_agent_budget(Guard()):
        provider.invoke_chat_model("DeepSeek", "agent input")
        provider.LazyZhipuEmbeddings().embed_documents(["one", "two"])
    assert calls == [
        ("model", "agent input"),
        ("embedding", ("one", "two")),
    ]
