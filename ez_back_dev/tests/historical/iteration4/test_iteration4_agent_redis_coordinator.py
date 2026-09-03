from __future__ import annotations

import asyncio
import os
from uuid import uuid4

import pytest

from service.agentRedisCoordinator import (
    AgentRedisCoordinator,
    AgentRedisSettings,
    IdempotencyStatus,
    LeaseLostError,
    agent_redis_settings_from_environment,
)


REDIS_URL = os.getenv("EZLLM_TEST_REDIS_URL")


def test_environment_settings_honor_separate_checkpoint_idempotency_and_cancel_ttls(
    monkeypatch,
):
    monkeypatch.setenv("AGENT_CHECKPOINT_TTL_SECONDS", "701")
    monkeypatch.setenv("AGENT_IDEMPOTENCY_TTL_SECONDS", "702")
    monkeypatch.setenv("AGENT_CANCEL_TTL_SECONDS", "703")
    settings = agent_redis_settings_from_environment()
    assert settings.state_ttl_seconds == 701
    assert settings.idempotency_ttl == 702
    assert settings.cancel_ttl == 703


def _coordinator() -> AgentRedisCoordinator:
    if not REDIS_URL:
        pytest.skip("EZLLM_TEST_REDIS_URL is not configured")
    suffix = uuid4().hex
    return AgentRedisCoordinator(
        AgentRedisSettings(
            url=REDIS_URL,
            prefix=f"ezllm:test:aspect3:{suffix}",
            lease_ttl_seconds=2,
            lease_renew_seconds=1,
            command_claim_seconds=1,
            event_ttl_seconds=60,
            event_max_length=5,
            state_ttl_seconds=60,
        )
    )


def test_lease_fencing_rejects_stale_owner_and_is_project_scoped():
    async def scenario():
        coordinator = _coordinator()
        try:
            first = await coordinator.acquire_lease(
                "scope-a", "iteration4-aspect3-v1", "thread-1", "worker-a"
            )
            assert first is not None
            assert await coordinator.acquire_lease(
                "scope-a", "iteration4-aspect3-v1", "thread-1", "worker-b"
            ) is None
            other_scope = await coordinator.acquire_lease(
                "scope-b", "iteration4-aspect3-v1", "thread-1", "worker-b"
            )
            assert other_scope is not None
            assert await coordinator.renew_lease(first)
            assert await coordinator.release_lease(first)
            second = await coordinator.acquire_lease(
                "scope-a", "iteration4-aspect3-v1", "thread-1", "worker-b"
            )
            assert second is not None
            assert second.fence > first.fence
            assert not await coordinator.renew_lease(first)
        finally:
            await coordinator.delete_test_namespace()
            await coordinator.aclose()

    asyncio.run(scenario())


def test_idempotency_state_machine_prevents_duplicate_or_stale_completion():
    async def scenario():
        coordinator = _coordinator()
        try:
            lease = await coordinator.acquire_lease(
                "scope-a", "iteration4-aspect3-v1", "thread-2", "worker-a"
            )
            assert lease is not None
            reserved = await coordinator.reserve_idempotency(
                lease,
                idempotency_key="idem-1",
                operation="ui_case",
                persisted=True,
            )
            assert reserved.status is IdempotencyStatus.RESERVED
            duplicate = await coordinator.reserve_idempotency(
                lease,
                idempotency_key="idem-1",
                operation="ui_case",
                persisted=True,
            )
            assert duplicate.status is IdempotencyStatus.RESERVED
            started = await coordinator.mark_idempotency_started(lease, "idem-1")
            assert started.status is IdempotencyStatus.STARTED
            completed = await coordinator.complete_idempotency(
                lease, "idem-1", {"artifact_key": "ui_case", "saved": True}
            )
            assert completed.status is IdempotencyStatus.COMPLETED
            assert completed.result == {"artifact_key": "ui_case", "saved": True}
            again = await coordinator.complete_idempotency(
                lease, "idem-1", {"artifact_key": "ui_case", "saved": True}
            )
            assert again == completed
            await coordinator.release_lease(lease)
            replacement = await coordinator.acquire_lease(
                "scope-a", "iteration4-aspect3-v1", "thread-2", "worker-b"
            )
            assert replacement is not None
            with pytest.raises(LeaseLostError):
                await coordinator.mark_idempotency_started(lease, "idem-1")
        finally:
            await coordinator.delete_test_namespace()
            await coordinator.aclose()

    asyncio.run(scenario())


def test_unknown_session_outcome_is_fail_closed_and_not_replayed():
    async def scenario():
        coordinator = _coordinator()
        try:
            lease = await coordinator.acquire_lease(
                "scope-a", "iteration4-aspect3-v1", "thread-3", "worker-a"
            )
            assert lease is not None
            await coordinator.reserve_idempotency(
                lease,
                idempotency_key="idem-session",
                operation="unit_case",
                persisted=False,
            )
            await coordinator.mark_idempotency_started(lease, "idem-session")
            unknown = await coordinator.mark_outcome_unknown(
                lease, "idem-session", "session_result_not_recorded"
            )
            assert unknown.status is IdempotencyStatus.OUTCOME_UNKNOWN
            assert unknown.result is None
            with pytest.raises(ValueError, match="outcome_unknown"):
                await coordinator.mark_idempotency_started(
                    lease, "idem-session"
                )
        finally:
            await coordinator.delete_test_namespace()
            await coordinator.aclose()

    asyncio.run(scenario())


def test_cancel_nonce_events_and_command_delivery_are_bounded_and_one_time():
    async def scenario():
        coordinator = _coordinator()
        try:
            lease = await coordinator.acquire_lease(
                "scope-a", "iteration4-aspect3-v1", "thread-4", "worker-a"
            )
            assert lease is not None
            assert not await coordinator.is_cancelled(lease)
            await coordinator.request_cancel(lease)
            assert await coordinator.is_cancelled(lease)

            assert await coordinator.issue_approval_nonce(lease, "nonce-1")
            assert not await coordinator.issue_approval_nonce(lease, "nonce-1")
            assert await coordinator.consume_approval_nonce(lease, "nonce-1")
            assert not await coordinator.consume_approval_nonce(lease, "nonce-1")
            assert await coordinator.issue_approval_nonce(lease, "nonce-2")
            assert await coordinator.claim_approval_nonce(
                lease, "nonce-2", "command-a"
            )
            assert await coordinator.claim_approval_nonce(
                lease, "nonce-2", "command-a"
            )
            assert not await coordinator.claim_approval_nonce(
                lease, "nonce-2", "command-b"
            )
            assert await coordinator.finalize_approval_nonce(
                lease, "nonce-2", "command-a"
            )

            for index in range(7):
                sequence = await coordinator.append_event(
                    lease, "progress", {"index": index}
                )
                assert sequence == index + 1
            events = await coordinator.replay_events(lease, after_sequence=2)
            assert [event.sequence for event in events] == [3, 4, 5, 6, 7]
            assert all(event.kind == "progress" for event in events)

            await coordinator.ensure_command_group("workers")
            command_id = await coordinator.enqueue_command(
                scope_hash="scope-a",
                graph_version="iteration4-aspect3-v1",
                thread_id="thread-4",
                command_id="command-1",
                kind="resume",
            )
            commands = await coordinator.read_commands(
                "workers", "consumer-a", count=1, block_ms=10
            )
            assert len(commands) == 1
            assert commands[0].stream_id == command_id
            assert commands[0].command_id == "command-1"
            await asyncio.sleep(1.05)
            claimed = await coordinator.claim_commands(
                "workers", "consumer-b", count=1
            )
            assert [item.stream_id for item in claimed] == [command_id]
            assert await coordinator.ack_command("workers", command_id) == 1
        finally:
            await coordinator.delete_test_namespace()
            await coordinator.aclose()

    asyncio.run(scenario())
