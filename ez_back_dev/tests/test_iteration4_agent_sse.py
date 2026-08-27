from __future__ import annotations

import asyncio

import httpx

from app.agentApi import create_agent_api_app
from service.agentContracts import ApprovalDecision, TrustedProjectScope
from tests.test_iteration4_agent_api import _service


async def _next_command(runtime, coordinator, owner="worker-api"):
    await coordinator.ensure_command_group("api-workers")
    commands = await coordinator.read_commands(
        "api-workers", owner, count=1, block_ms=50
    )
    assert len(commands) == 1
    result = await runtime.process_command(commands[0], owner=owner)
    await coordinator.ack_command("api-workers", commands[0].stream_id)
    return result


def _event_blocks(content: str) -> list[str]:
    return [block for block in content.split("\n\n") if block.startswith("id: ")]


def test_agent_sse_replay_is_monotonic_safe_and_closes_at_terminal():
    async def scenario():
        service, coordinator, _adapter = _service()
        app = create_agent_api_app(
            service,
            project_exists=lambda pid: pid == "project-a",
            allow_test_host=True,
            heartbeat_seconds=0.01,
            poll_seconds=0.005,
        )
        transport = httpx.ASGITransport(app=app)
        scope = TrustedProjectScope(
            project_id="project-a",
            actor_id="local-workbench",
            scope_version="iteration4-aspect4-v1",
        )
        try:
            async with httpx.AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as client:
                created = await client.post(
                    "/agent/v1/projects/project-a/runs",
                    json={
                        "goal": "Generate UI tests",
                        "model_label": "GLM-4.7",
                        "budget_preset": "focused",
                    },
                )
                thread_id = created.json()["data"]["thread_id"]
                await _next_command(service.runtime, coordinator)
                paused = await service.get_run(scope, thread_id)
                assert paused and paused.approval
                approved = await client.post(
                    f"/agent/v1/projects/project-a/runs/{thread_id}/approval",
                    json={
                        "decision": ApprovalDecision.APPROVED.value,
                        "expected_plan_hash": paused.approval.plan_hash,
                    },
                )
                assert approved.status_code == 200
                await _next_command(service.runtime, coordinator)

                response = await client.get(
                    f"/agent/v1/projects/project-a/runs/{thread_id}/events"
                )
                assert response.status_code == 200
                blocks = _event_blocks(response.text)
                identifiers = [
                    int(block.splitlines()[0].split(": ", 1)[1])
                    for block in blocks
                ]
                assert identifiers == sorted(set(identifiers))
                assert "event: agent_event" in response.text
                assert '"kind":"completed"' in response.text
                lowered = response.text.lower()
                for forbidden in (
                    "reasoning_delta",
                    "chain_of_thought",
                    "prompt",
                    "traceback",
                    "idempotency_key",
                    "nonce",
                ):
                    assert forbidden not in lowered

                last = identifiers[-2]
                replay = await client.get(
                    f"/agent/v1/projects/project-a/runs/{thread_id}/events",
                    headers={"Last-Event-ID": str(last)},
                )
                replay_ids = [
                    int(block.splitlines()[0].split(": ", 1)[1])
                    for block in _event_blocks(replay.text)
                ]
                assert replay_ids == [identifiers[-1]]
        finally:
            await coordinator.delete_test_namespace()
            await coordinator.aclose()

    asyncio.run(scenario())


def test_agent_sse_reports_retention_gap_with_replay_reset():
    async def scenario():
        service, coordinator, _adapter = _service()
        app = create_agent_api_app(
            service,
            project_exists=lambda _pid: True,
            allow_test_host=True,
        )
        transport = httpx.ASGITransport(app=app)
        scope = TrustedProjectScope(
            project_id="project-a",
            actor_id="local-workbench",
            scope_version="iteration4-aspect4-v1",
        )
        try:
            async with httpx.AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as client:
                created = await client.post(
                    "/agent/v1/projects/project-a/runs",
                    json={"goal": "UI", "model_label": "GLM-4.7"},
                )
                thread_id = created.json()["data"]["thread_id"]
                await _next_command(service.runtime, coordinator)
                view = await service.get_run(scope, thread_id)
                assert view and view.approval
                await service.decide_approval(
                    scope,
                    thread_id,
                    ApprovalDecision.APPROVED,
                    view.approval.plan_hash,
                )
                await _next_command(service.runtime, coordinator)

                scope_hash = service.scope_hash(scope)
                timeline = service.store._timeline_keys(
                    scope_hash, thread_id, "read"
                )[0]
                rows = await service.store.redis.xrange(
                    timeline, min="-", max="+", count=3
                )
                assert len(rows) == 3
                await service.store.redis.xdel(
                    timeline, *(row[0] for row in rows)
                )

                response = await client.get(
                    f"/agent/v1/projects/project-a/runs/{thread_id}/events",
                    params={"after_sequence": 1},
                )
                assert '"kind":"replay_reset"' in response.text
                assert '"reason":"retention_gap"' in response.text
        finally:
            await coordinator.delete_test_namespace()
            await coordinator.aclose()

    asyncio.run(scenario())
