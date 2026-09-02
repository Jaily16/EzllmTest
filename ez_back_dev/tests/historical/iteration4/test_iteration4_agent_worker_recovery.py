from __future__ import annotations

import asyncio
import multiprocessing
import os
import sqlite3
import time
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from service.agentContracts import (
    AgentRunStatus,
    ApprovalDecision,
    RunBudget,
    TrustedProjectScope,
)
from service.agentPlanner import DeterministicAgentPlanner, PlannerProposal
from service.agentRedisCoordinator import AgentRedisCoordinator, AgentRedisSettings
from service.agentRedisCoordinator import AgentCommand
from service.agentRuntimeContracts import ProjectObservation
from service.agentRuntimeService import AgentRuntimeService
from service.agentToolSchemas import (
    ToolExecutionResult,
    ToolExecutionStatus,
    ToolUsageSummary,
)
from service.agentWorker import AgentCommandWorker, build_parser


REDIS_URL = os.getenv("EZLLM_TEST_REDIS_URL")


class _SQLiteArtifactAdapter:
    def __init__(self, database_path: str):
        self.database_path = database_path

    async def invoke(self, tool_name, _arguments, _context):
        result = ToolExecutionResult(
            tool_name=tool_name,
            operation="ui_case",
            status=ToolExecutionStatus.SUCCESS,
            data={"result_ref": "sqlite-artifact"},
            saved=True,
            source_revision="revision-1",
            artifact_key="ui_case",
            usage=ToolUsageSummary(
                input_tokens=5,
                output_tokens=10,
                model_calls=1,
                embedding_calls=0,
                tool_calls=1,
                estimated_cost_units=2,
            ),
        )
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS effects "
                "(id INTEGER PRIMARY KEY AUTOINCREMENT, payload TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS artifact "
                "(artifact_key TEXT PRIMARY KEY, payload TEXT NOT NULL)"
            )
            connection.execute(
                "INSERT INTO effects(payload) VALUES (?)", ("ui_case",)
            )
            connection.execute(
                "INSERT OR REPLACE INTO artifact(artifact_key, payload) VALUES (?, ?)",
                ("ui_case", result.model_dump_json()),
            )
        return result


def _multiprocess_service(
    redis_url: str,
    prefix: str,
    database_path: str,
    *,
    crash_after_artifact: bool,
):
    coordinator = AgentRedisCoordinator(
        AgentRedisSettings(
            url=redis_url,
            prefix=prefix,
            lease_ttl_seconds=2,
            lease_renew_seconds=1,
            event_ttl_seconds=60,
            state_ttl_seconds=60,
        )
    )
    adapter = _SQLiteArtifactAdapter(database_path)

    async def reconcile(_call, _context):
        with sqlite3.connect(database_path) as connection:
            row = connection.execute(
                "SELECT payload FROM artifact WHERE artifact_key = ?",
                ("ui_case",),
            ).fetchone()
        return ToolExecutionResult.model_validate_json(row[0]) if row else None

    def crash(_call, _result):
        os._exit(23)

    service = AgentRuntimeService(
        coordinator=coordinator,
        planner=DeterministicAgentPlanner(
            PlannerProposal.model_validate(
                {
                    "steps": [
                        {
                            "tool_name": "workflow_ui_case",
                            "arguments": {"info": "synthetic ui"},
                        }
                    ]
                }
            )
        ),
        observer=lambda _scope: ProjectObservation(
            setup_stage="ready",
            analysis_ready=True,
            workflow_stage="analysis",
            source_revision="revision-1",
        ),
        tool_adapter=adapter,
        artifact_reconciler=reconcile,
        after_tool_hook=crash if crash_after_artifact else None,
        clock=lambda: datetime.now(UTC),
    )
    return service, coordinator


def _worker_process(
    redis_url: str,
    prefix: str,
    database_path: str,
    command_payload: dict,
    owner: str,
    crash_after_artifact: bool,
    output_queue,
):
    async def run():
        service, coordinator = _multiprocess_service(
            redis_url,
            prefix,
            database_path,
            crash_after_artifact=crash_after_artifact,
        )
        try:
            result = await service.process_command(
                AgentCommand.model_validate(command_payload), owner=owner
            )
            output_queue.put(result.run_state.status.value)
        finally:
            await coordinator.aclose()

    asyncio.run(run())


def _budget() -> RunBudget:
    return RunBudget(
        max_steps=3,
        max_elapsed_ms=60_000,
        max_input_tokens=1_000,
        max_output_tokens=1_000,
        max_model_calls=3,
        max_embedding_calls=2,
        max_tool_calls=3,
        max_estimated_cost_units=1_000,
    )


class _Adapter:
    def __init__(self, operation: str, *, saved: bool):
        self.operation = operation
        self.saved = saved
        self.calls = 0
        self.result: ToolExecutionResult | None = None

    async def invoke(self, tool_name, _arguments, _context):
        self.calls += 1
        self.result = ToolExecutionResult(
            tool_name=tool_name,
            operation=self.operation,
            status=ToolExecutionStatus.SUCCESS,
            data={"result_ref": f"run-result-{self.operation}"},
            saved=self.saved,
            source_revision="revision-1",
            artifact_key=self.operation if self.saved else None,
            usage=ToolUsageSummary(
                input_tokens=5,
                output_tokens=10,
                model_calls=1,
                embedding_calls=0,
                tool_calls=1,
                estimated_cost_units=2,
            ),
        )
        return self.result


def _runtime(operation: str, arguments: dict, *, saved: bool):
    if not REDIS_URL:
        pytest.skip("EZLLM_TEST_REDIS_URL is not configured")
    settings = AgentRedisSettings(
        url=REDIS_URL,
        prefix=f"ezllm:test:aspect3:recovery:{uuid4().hex}",
        lease_ttl_seconds=10,
        lease_renew_seconds=1,
        event_ttl_seconds=60,
        state_ttl_seconds=60,
    )
    coordinator = AgentRedisCoordinator(settings)
    adapter = _Adapter(operation, saved=saved)
    service = AgentRuntimeService(
        coordinator=coordinator,
        planner=DeterministicAgentPlanner(
            PlannerProposal.model_validate(
                {
                    "steps": [
                        {
                            "tool_name": f"workflow_{operation}",
                            "arguments": arguments,
                        }
                    ]
                }
            )
        ),
        observer=lambda _scope: ProjectObservation(
            setup_stage="ready",
            analysis_ready=True,
            workflow_stage="analysis",
            source_revision="revision-1",
        ),
        tool_adapter=adapter,
        clock=lambda: datetime.now(UTC),
    )
    return service, coordinator, adapter


async def _start_and_approve(service, coordinator, scope):
    handle = await service.create_run(
        scope,
        "Synthetic recovery task",
        planner_model="deterministic",
        execution_model="fake-model",
        budget=_budget(),
    )
    await coordinator.ensure_command_group("workers")
    [start] = await coordinator.read_commands(
        "workers", "consumer-a", count=1, block_ms=10
    )
    paused = await service.process_command(start, owner="worker-a")
    await coordinator.ack_command("workers", start.stream_id)
    await service.approve_run(
        scope,
        handle.thread_id,
        ApprovalDecision.APPROVED,
        expected_plan_hash=paused.approval_request.plan_hash,
    )
    [resume] = await coordinator.read_commands(
        "workers", "consumer-a", count=1, block_ms=10
    )
    return handle, resume


def test_persisted_artifact_is_reconciled_after_crash_without_duplicate_effect():
    async def scenario():
        service, coordinator, adapter = _runtime(
            "ui_case", {"info": "synthetic ui"}, saved=True
        )
        scope = TrustedProjectScope(
            project_id="project-a", actor_id="actor-a", scope_version="1"
        )

        async def crash_after_tool(_call, _result):
            raise RuntimeError("synthetic crash after artifact save")

        service.after_tool_hook = crash_after_tool
        try:
            _, resume = await _start_and_approve(service, coordinator, scope)
            with pytest.raises(RuntimeError, match="synthetic crash"):
                await service.process_command(resume, owner="worker-a")
            assert adapter.calls == 1

            service.after_tool_hook = None
            service.artifact_reconciler = lambda _call, _context: adapter.result
            recovered = await service.process_command(resume, owner="worker-b")
            assert recovered.run_state.status is AgentRunStatus.COMPLETED
            assert adapter.calls == 1
        finally:
            await coordinator.delete_test_namespace()
            await coordinator.aclose()

    asyncio.run(scenario())


def test_session_only_unknown_outcome_never_retries_the_paid_call():
    async def scenario():
        service, coordinator, adapter = _runtime(
            "unit_case",
            {
                "method_type": 0,
                "static_method": "Example.run",
                "unit": "Example",
                "unit_type": "class",
                "unit_info": "synthetic unit",
                "output_type": 0,
            },
            saved=False,
        )
        scope = TrustedProjectScope(
            project_id="project-a", actor_id="actor-a", scope_version="1"
        )

        async def crash_after_tool(_call, _result):
            raise RuntimeError("synthetic session crash")

        service.after_tool_hook = crash_after_tool
        try:
            _, resume = await _start_and_approve(service, coordinator, scope)
            with pytest.raises(RuntimeError, match="session crash"):
                await service.process_command(resume, owner="worker-a")
            service.after_tool_hook = None
            failed = await service.process_command(resume, owner="worker-b")
            assert failed.run_state.status is AgentRunStatus.FAILED
            assert failed.run_state.last_error.code == "outcome_unknown"
            assert adapter.calls == 1
        finally:
            await coordinator.delete_test_namespace()
            await coordinator.aclose()

    asyncio.run(scenario())


def test_worker_acknowledges_only_after_successful_processing():
    class Coordinator:
        def __init__(self):
            self.acked = []

        async def ensure_command_group(self, _group):
            return None

        async def claim_commands(self, _group, _consumer, count=1):
            return []

        async def read_commands(self, _group, _consumer, count=1, block_ms=1):
            return [type("Command", (), {"stream_id": "1-0"})()]

        async def ack_command(self, group, stream_id):
            self.acked.append((group, stream_id))

    class Service:
        def __init__(self, fail=False):
            self.coordinator = Coordinator()
            self.fail = fail

        async def process_command(self, _command, owner):
            if self.fail:
                raise RuntimeError("synthetic worker failure")
            assert owner == "consumer-a"

    async def scenario():
        success = Service()
        worker = AgentCommandWorker(success, consumer="consumer-a")
        assert await worker.run_once(block_ms=1)
        assert success.coordinator.acked == [("ezllm-agent-workers", "1-0")]

        failure = Service(fail=True)
        worker = AgentCommandWorker(failure, consumer="consumer-a")
        with pytest.raises(RuntimeError, match="synthetic worker failure"):
            await worker.run_once(block_ms=1)
        assert failure.coordinator.acked == []

    asyncio.run(scenario())


def test_worker_cli_has_no_redis_url_host_project_or_approval_arguments():
    parser = build_parser()
    parsed = parser.parse_args(["--once", "--consumer", "worker-1"])
    assert parsed.once is True
    assert parsed.consumer == "worker-1"
    option_strings = {
        option
        for action in parser._actions
        for option in action.option_strings
    }
    assert "--host" not in option_strings
    assert "--redis-url" not in option_strings
    assert "--project" not in option_strings
    assert "--approval" not in option_strings


def test_two_process_crash_restart_reconciles_sqlite_artifact_once(tmp_path):
    if not REDIS_URL:
        pytest.skip("EZLLM_TEST_REDIS_URL is not configured")

    async def prepare(prefix: str, database_path: str):
        service, coordinator = _multiprocess_service(
            REDIS_URL,
            prefix,
            database_path,
            crash_after_artifact=False,
        )
        scope = TrustedProjectScope(
            project_id="project-a", actor_id="actor-a", scope_version="1"
        )
        handle = await service.create_run(
            scope,
            "Persist then recover",
            planner_model="deterministic",
            execution_model="fake-model",
            budget=_budget(),
        )
        await coordinator.ensure_command_group("workers")
        [start] = await coordinator.read_commands(
            "workers", "preparer", count=1, block_ms=10
        )
        paused = await service.process_command(start, owner="preparer")
        await coordinator.ack_command("workers", start.stream_id)
        await service.approve_run(
            scope,
            handle.thread_id,
            ApprovalDecision.APPROVED,
            expected_plan_hash=paused.approval_request.plan_hash,
        )
        [resume] = await coordinator.read_commands(
            "workers", "preparer", count=1, block_ms=10
        )
        await coordinator.aclose()
        return resume.model_dump(mode="json")

    prefix = f"ezllm:test:aspect3:multiprocess:{uuid4().hex}"
    database_path = str(tmp_path / "artifact.sqlite3")
    command_payload = asyncio.run(prepare(prefix, database_path))
    context = multiprocessing.get_context("spawn")
    output_queue = context.Queue()

    first = context.Process(
        target=_worker_process,
        args=(
            REDIS_URL,
            prefix,
            database_path,
            command_payload,
            "worker-crash",
            True,
            output_queue,
        ),
    )
    first.start()
    first.join(timeout=20)
    assert first.exitcode == 23

    # The killed process cannot release its lease.  Poll only the bounded test
    # TTL rather than bypassing the fence or deleting the lease.
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        async def probe_lease():
            checker = AgentRedisCoordinator(
                AgentRedisSettings(
                    url=REDIS_URL,
                    prefix=prefix,
                    lease_ttl_seconds=2,
                    lease_renew_seconds=1,
                    state_ttl_seconds=60,
                )
            )
            try:
                lease = await checker.acquire_lease(
                    command_payload["scope_hash"],
                    command_payload["graph_version"],
                    command_payload["thread_id"],
                    "lease-probe",
                )
                if lease is not None:
                    await checker.release_lease(lease)
                    return True
                return False
            finally:
                await checker.aclose()

        if asyncio.run(probe_lease()):
            break
        time.sleep(0.1)
    else:
        pytest.fail("crashed worker lease did not expire")

    second = context.Process(
        target=_worker_process,
        args=(
            REDIS_URL,
            prefix,
            database_path,
            command_payload,
            "worker-restart",
            False,
            output_queue,
        ),
    )
    second.start()
    second.join(timeout=20)
    assert second.exitcode == 0
    assert output_queue.get(timeout=2) == AgentRunStatus.COMPLETED.value
    with sqlite3.connect(database_path) as connection:
        [effect_count] = connection.execute(
            "SELECT COUNT(*) FROM effects"
        ).fetchone()
    assert effect_count == 1

    async def cleanup():
        coordinator = AgentRedisCoordinator(
            AgentRedisSettings(
                url=REDIS_URL,
                prefix=prefix,
                lease_ttl_seconds=2,
                lease_renew_seconds=1,
                state_ttl_seconds=60,
            )
        )
        await coordinator.delete_test_namespace()
        storage_id = coordinator.storage_id(
            command_payload["scope_hash"],
            command_payload["graph_version"],
            command_payload["thread_id"],
        )
        assert not await coordinator.redis.exists(
            coordinator._key("run-view", storage_id)
        )
        await coordinator.aclose()

    asyncio.run(cleanup())
    # Redis loss makes the thread unrecoverable but never deletes the durable
    # artifact represented by the isolated SQLite store.
    with sqlite3.connect(database_path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM artifact"
        ).fetchone()[0] == 1
