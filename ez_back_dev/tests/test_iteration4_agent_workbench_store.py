from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from service.agentContracts import AgentRunStatus, UsageCounters
from service.agentRedisCoordinator import AgentRedisCoordinator, AgentRedisSettings
from service.agentWorkbenchContracts import AgentStepEvidence
from service.agentWorkbenchStore import AgentWorkbenchStore


REDIS_URL = os.getenv("EZLLM_TEST_REDIS_URL")


def _store():
    if not REDIS_URL:
        pytest.skip("EZLLM_TEST_REDIS_URL is not configured")
    coordinator = AgentRedisCoordinator(
        AgentRedisSettings(
            url=REDIS_URL,
            prefix=f"ezllm:test:aspect4:store:{uuid4().hex}",
            event_ttl_seconds=60,
            state_ttl_seconds=60,
        )
    )
    return AgentWorkbenchStore(coordinator), coordinator


def test_active_slot_and_index_are_project_scoped_and_atomic():
    async def scenario():
        store, coordinator = _store()
        try:
            assert await store.reserve_active("scope-a", "reservation-a")
            assert not await store.reserve_active("scope-a", "reservation-b")
            assert await store.commit_active(
                "scope-a", "reservation-a", "thread-a"
            )
            assert await store.active_thread("scope-a") == "thread-a"
            assert await store.active_thread("scope-b") is None

            first = await store.register_run(
                "scope-a", "thread-a", "focused", datetime.now(UTC)
            )
            second = await store.register_run(
                "scope-a", "thread-b", "standard", datetime.now(UTC)
            )
            assert second > first
            page, cursor = await store.list_run_threads("scope-a", limit=1)
            assert page == ("thread-b",)
            assert cursor == second
            page, cursor = await store.list_run_threads(
                "scope-a", limit=2, before=cursor
            )
            assert page == ("thread-a",)
            assert cursor is None

            assert not await store.release_active("scope-a", "thread-b")
            assert await store.release_active("scope-a", "thread-a")
            assert await store.active_thread("scope-a") is None
        finally:
            await coordinator.delete_test_namespace()
            await coordinator.aclose()

    import asyncio

    asyncio.run(scenario())


def test_evidence_and_timeline_are_safe_bounded_and_idempotent():
    async def scenario():
        store, coordinator = _store()
        try:
            evidence = AgentStepEvidence(
                step_id="step-1",
                operation="unit_case",
                retention="session",
                status="success",
                session_result={"cases": [{"name": "synthetic"}]},
                usage=UsageCounters(tool_calls=1),
            )
            await store.put_evidence("scope-a", "thread-a", evidence)
            assert await store.get_evidence("scope-a", "thread-a") == (
                evidence,
            )
            assert await store.get_evidence("scope-b", "thread-a") == ()

            payload = {
                "kind": "queued",
                "occurred_at": datetime.now(UTC).isoformat(),
                "status": AgentRunStatus.CREATED.value,
            }
            sequence = await store.append_timeline_event(
                "scope-a", "thread-a", "queued", payload
            )
            duplicate = await store.append_timeline_event(
                "scope-a", "thread-a", "queued", payload
            )
            assert duplicate == sequence
            events = await store.replay_timeline("scope-a", "thread-a", 0)
            assert len(events) == 1
            assert events[0].sequence == sequence
            assert events[0].kind == "queued"
            assert await store.timeline_bounds("scope-a", "thread-a") == (
                sequence,
                sequence,
            )
        finally:
            await coordinator.delete_test_namespace()
            await coordinator.aclose()

    import asyncio

    asyncio.run(scenario())


def test_worker_heartbeat_expires_without_refreshing_run_state():
    async def scenario():
        store, coordinator = _store()
        try:
            assert not await store.worker_available()
            await store.heartbeat_worker("worker-a", ttl_seconds=2)
            assert await store.worker_available()
        finally:
            await coordinator.delete_test_namespace()
            await coordinator.aclose()

    import asyncio

    asyncio.run(scenario())


def test_progress_buckets_are_monotonic_per_step_and_stage():
    async def scenario():
        store, coordinator = _store()
        try:
            assert await store.accept_progress(
                "scope-a", "thread-a", "step:run", 20
            )
            assert not await store.accept_progress(
                "scope-a", "thread-a", "step:run", 10
            )
            assert not await store.accept_progress(
                "scope-a", "thread-a", "step:run", 20
            )
            assert await store.accept_progress(
                "scope-a", "thread-a", "step:run", 25
            )
            assert await store.accept_progress(
                "scope-a", "thread-a", "step:save", 5
            )
        finally:
            await coordinator.delete_test_namespace()
            await coordinator.aclose()

    import asyncio

    asyncio.run(scenario())
