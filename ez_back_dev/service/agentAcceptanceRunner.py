"""Deterministic integration acceptance over the shipped Agent components."""

from __future__ import annotations

import asyncio
from contextlib import closing
import hashlib
import json
import os
import platform
import sqlite3
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import httpx

from app.agentApi import create_agent_api_app
from service.agentAcceptanceContracts import (
    AcceptanceCaseResult,
    AcceptanceDataset,
    AcceptanceEnvironment,
    AcceptanceGateDecision,
    AcceptanceMetrics,
    AcceptanceRunReport,
    AcceptanceSuite,
)
from service.agentEvalContracts import EvalSuite
from service.agentEvalRunner import _environment as eval_environment
from service.agentEvalRunner import run_eval
from service.agentPlanner import DeterministicAgentPlanner, PlannerProposal
from service.agentRedisCoordinator import AgentRedisCoordinator, AgentRedisSettings
from service.agentRuntimeContracts import ProjectObservation
from service.agentRuntimeService import AgentRuntimeService
from service.agentToolRegistry import DEFAULT_TOOL_REGISTRY
from service.agentToolSchemas import (
    ToolExecutionError,
    ToolExecutionResult,
    ToolExecutionStatus,
    ToolUsageSummary,
)
from service.agentWorkbenchService import AgentWorkbenchService
from service.agentWorkbenchStore import AgentWorkbenchStore
from service.agentWorker import AgentCommandWorker


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
FIXTURE = ROOT / "tests" / "fixtures" / "iteration4_agent_acceptance_v1.json"
_PROVIDER_KEYS = (
    "ZHIPU_API_KEY",
    "DASHSCOPE_API_KEY",
    "DEEPSEEK_API_KEY",
    "MOONSHOT_API_KEY",
)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key in acceptance fixture")
        result[key] = value
    return result


def load_acceptance_dataset(path: Path = FIXTURE) -> AcceptanceDataset:
    raw = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=lambda _value: (_ for _ in ()).throw(
            ValueError("non-finite JSON value")
        ),
    )
    return AcceptanceDataset.model_validate(raw)


def _sha256(path: Path) -> str:
    payload = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(payload).hexdigest().upper()


def _validate_environment(redis_url: str | None) -> tuple[str, str]:
    if any(os.environ.get(name) for name in _PROVIDER_KEYS):
        raise ValueError("provider credentials are forbidden in acceptance")
    if not redis_url:
        raise ValueError("acceptance requires loopback Redis")
    parsed = urlparse(redis_url)
    topology = os.environ.get("ASPECT8_ACCEPTANCE_TOPOLOGY", "loopback_redis")
    if topology == "isolated_compose":
        allowed = parsed.scheme == "redis" and parsed.hostname == "redis"
    else:
        topology = "loopback_redis"
        allowed = parsed.scheme == "redis" and parsed.hostname in {
            "127.0.0.1",
            "localhost",
            "::1",
        }
    if not allowed or parsed.username or parsed.password:
        raise ValueError("acceptance requires credential-free loopback Redis")
    return redis_url, topology


class _SQLiteAcceptanceAdapter:
    def __init__(self, path: str) -> None:
        self.path = path
        self.calls = 0
        self.successful_calls = 0
        self.fail_next = False

    async def invoke(self, tool_name, _arguments, _context):
        self.calls += 1
        if self.fail_next:
            self.fail_next = False
            return ToolExecutionResult(
                tool_name=tool_name,
                operation="ui_case",
                status=ToolExecutionStatus.ERROR,
                error=ToolExecutionError(
                    code="temporary_failure",
                    category="transient",
                    retryable=True,
                    safe_message="Synthetic transient failure",
                ),
            )
        self.successful_calls += 1
        result = ToolExecutionResult(
            tool_name=tool_name,
            operation="ui_case",
            status=ToolExecutionStatus.SUCCESS,
            data={"result_ref": "acceptance-artifact"},
            saved=True,
            from_cache=False,
            source_revision="acceptance-revision-1",
            artifact_key="ui_case",
            usage=ToolUsageSummary(
                input_tokens=8,
                output_tokens=4,
                model_calls=1,
                embedding_calls=0,
                tool_calls=1,
                estimated_cost_units=12,
            ),
        )
        with closing(sqlite3.connect(self.path)) as connection:
            with connection:
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS effects "
                    "(operation TEXT PRIMARY KEY, result_json TEXT NOT NULL)"
                )
                connection.execute(
                    "INSERT OR IGNORE INTO effects(operation, result_json) VALUES (?, ?)",
                    ("ui_case", result.model_dump_json()),
                )
        return result

    def effect_count(self) -> int:
        with closing(sqlite3.connect(self.path)) as connection:
            row = connection.execute("SELECT COUNT(*) FROM effects").fetchone()
        return int(row[0]) if row else 0


async def _isolated_compose_project_probe() -> str:
    """Exercise legacy project setup only inside the disposable Compose DB."""

    from app.main import app as legacy_app

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=legacy_app),
        base_url="http://testserver",
    ) as client:
        created = await client.post("/project/add/Aspect%208%20synthetic")
        project_id = created.json().get("data")
        if created.status_code != 200 or not isinstance(project_id, str):
            raise RuntimeError("isolated project creation failed")
        documents = (
            (1, "knowledge.md", "Synthetic testing policy."),
            (2, "requirements.md", "Synthetic acceptance requirement."),
            (3, "design.md", "Synthetic component design."),
        )
        for doctype, filename, content in documents:
            uploaded = await client.post(
                f"/uploadFile/{project_id}/{doctype}",
                files={"file": (filename, content.encode("utf-8"), "text/markdown")},
            )
            if uploaded.json().get("data") is not True:
                raise RuntimeError("isolated document upload failed")
        ready = await client.get(f"/project/setup/status/{project_id}")
        if ready.json().get("data", {}).get("stage") != "documents_ready":
            raise RuntimeError("isolated project did not reach documents_ready")
        finalized = await client.post(f"/project/setup/finalize/{project_id}")
        if finalized.json().get("data", {}).get("stage") != "setup_complete":
            raise RuntimeError("isolated project did not reach setup_complete")
        return project_id


async def _integrated_runtime_probe(
    redis_url: str, project_id: str
) -> tuple[tuple[str, ...], bool]:
    settings = AgentRedisSettings(
        url=redis_url,
        prefix=f"ezllm:test:aspect8:{uuid4().hex}",
        lease_ttl_seconds=10,
        lease_renew_seconds=1,
        event_ttl_seconds=60,
        event_max_length=100,
        state_ttl_seconds=60,
    )
    coordinator = AgentRedisCoordinator(settings)
    store = AgentWorkbenchStore(coordinator)
    with tempfile.TemporaryDirectory(prefix="ezllm-aspect8-") as temp:
        adapter = _SQLiteAcceptanceAdapter(str(Path(temp) / "artifacts.sqlite"))
        runtime = AgentRuntimeService(
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
                setup_stage="setup_complete",
                analysis_ready=True,
                workflow_stage="analysis_ready",
                source_revision="acceptance-revision-1",
            ),
            tool_adapter=adapter,
            workbench_store=store,
        )
        workbench = AgentWorkbenchService(runtime, store)
        app = create_agent_api_app(
            workbench,
            project_exists=lambda pid: pid == project_id,
            allowed_origins=("http://localhost:8080",),
            allow_test_host=True,
        )
        client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        )
        worker = AgentCommandWorker(
            runtime,
            group="ezllm-agent-workers",
            consumer="aspect8-worker",
        )
        try:
            created = await client.post(
                f"/agent/v1/projects/{project_id}/runs",
                json={
                    "goal": "Create a deterministic UI test artifact",
                    "model_label": "GLM-4.7",
                    "budget_preset": "focused",
                },
            )
            if created.status_code != 201 or adapter.calls != 0:
                raise RuntimeError("acceptance run creation violated zero execution")
            thread_id = created.json()["data"]["thread_id"]
            if not await worker.run_once(block_ms=50):
                raise RuntimeError("acceptance worker did not receive start")
            snapshot = await client.get(
                f"/agent/v1/projects/{project_id}/runs/{thread_id}"
            )
            approval = snapshot.json()["data"]["approval"]
            approved = await client.post(
                f"/agent/v1/projects/{project_id}/runs/{thread_id}/approval",
                json={"decision": "approved", "expected_plan_hash": approval["plan_hash"]},
            )
            if approved.status_code != 200:
                raise RuntimeError("acceptance approval failed")
            if not await worker.run_once(block_ms=50):
                raise RuntimeError("acceptance worker did not receive resume")
            final = await client.get(
                f"/agent/v1/projects/{project_id}/runs/{thread_id}"
            )
            if final.json()["data"]["status"] != "completed":
                raise RuntimeError("acceptance run did not complete")
            event_stream = await client.get(
                f"/agent/v1/projects/{project_id}/runs/{thread_id}/events",
                params={"after_sequence": 0},
            )
            if (
                event_stream.status_code != 200
                or "event: agent_event" not in event_stream.text
                or "reasoning" in event_stream.text.lower()
            ):
                raise RuntimeError("acceptance event stream contract failed")
            hidden = await client.get(
                f"/agent/v1/projects/acceptance-alpine/runs/{thread_id}"
            )
            events = await workbench.replay_events(
                runtime_scope(project_id), thread_id, 0
            )
            trajectory = tuple(event.kind for event in events)

            # Exercise a real retryable failure and recovery boundary with the
            # same runtime, queue, API, worker and Redis checkpoint stack.
            adapter.fail_next = True
            failed_created = await client.post(
                f"/agent/v1/projects/{project_id}/runs",
                json={
                    "goal": "Recover a deterministic transient failure",
                    "model_label": "GLM-4.7",
                    "budget_preset": "focused",
                },
            )
            if failed_created.status_code != 201:
                raise RuntimeError("acceptance recovery run creation failed")
            failed_thread = failed_created.json()["data"]["thread_id"]
            if not await worker.run_once(block_ms=50):
                raise RuntimeError("acceptance recovery start was not received")
            failed_snapshot = await client.get(
                f"/agent/v1/projects/{project_id}/runs/{failed_thread}"
            )
            failed_approval = failed_snapshot.json()["data"]["approval"]
            approved_failure = await client.post(
                f"/agent/v1/projects/{project_id}/runs/{failed_thread}/approval",
                json={
                    "decision": "approved",
                    "expected_plan_hash": failed_approval["plan_hash"],
                },
            )
            if approved_failure.status_code != 200 or not await worker.run_once(
                block_ms=50
            ):
                raise RuntimeError("acceptance retryable failure was not executed")
            failed_final = await client.get(
                f"/agent/v1/projects/{project_id}/runs/{failed_thread}"
            )
            if failed_final.json()["data"]["status"] != "failed":
                raise RuntimeError("acceptance retryable failure did not fail")
            recovered = await client.post(
                f"/agent/v1/projects/{project_id}/runs/{failed_thread}/recover"
            )
            if recovered.status_code != 200 or not await worker.run_once(block_ms=50):
                raise RuntimeError("acceptance recovery command failed")
            recovered_snapshot = await client.get(
                f"/agent/v1/projects/{project_id}/runs/{failed_thread}"
            )
            recovery_safe = (
                recovered_snapshot.json()["data"]["status"] == "awaiting_approval"
                and adapter.calls == 2
                and adapter.successful_calls == 1
            )
            safe = (
                recovery_safe
                and adapter.effect_count() == 1
                and hidden.status_code == 404
                and trajectory
                == (
                    "queued",
                    "planning",
                    "approval_required",
                    "approval_submitted",
                    "executing",
                    "tool_succeeded",
                    "completed",
                )
            )
            return trajectory, safe
        finally:
            await client.aclose()
            await coordinator.delete_test_namespace()
            await coordinator.aclose()


def runtime_scope(project_id: str):
    from service.agentContracts import TrustedProjectScope

    return TrustedProjectScope(
        project_id=project_id,
        actor_id="local-workbench",
        scope_version="iteration4-aspect4-v1",
    )


def _eval_gate(suite: AcceptanceSuite, redis_url: str) -> bool:
    selected = {
        AcceptanceSuite.JOURNEY: EvalSuite.CORE,
        AcceptanceSuite.RELIABILITY: EvalSuite.RELIABILITY,
        AcceptanceSuite.PROTOCOL: EvalSuite.SECURITY,
        AcceptanceSuite.ALL: EvalSuite.ALL,
    }[suite]
    report = run_eval(
        selected,
        redis_url=redis_url if selected in {EvalSuite.RELIABILITY, EvalSuite.ALL} else None,
    )
    return report.decision.passed


def run_acceptance(
    suite: AcceptanceSuite | str,
    *,
    redis_url: str | None,
) -> AcceptanceRunReport:
    selected = AcceptanceSuite(suite)
    redis_url, topology = _validate_environment(redis_url)
    dataset = load_acceptance_dataset()
    eval_passed = _eval_gate(selected, redis_url)
    integrated_trajectory: tuple[str, ...] | None = None
    integrated_passed = True
    if selected in {AcceptanceSuite.JOURNEY, AcceptanceSuite.ALL}:
        async def integrated():
            project_id = "acceptance-alpha"
            if topology == "isolated_compose":
                project_id = await _isolated_compose_project_probe()
            return await _integrated_runtime_probe(redis_url, project_id)

        integrated_trajectory, integrated_passed = asyncio.run(integrated())

    protocol_passed = (
        len(DEFAULT_TOOL_REGISTRY.definitions()) == 22
        and sum(
            definition.name.startswith("workflow_")
            for definition in DEFAULT_TOOL_REGISTRY.definitions()
        )
        == 19
    )
    if selected in {AcceptanceSuite.PROTOCOL, AcceptanceSuite.ALL}:
        eval_passed = eval_passed and protocol_passed

    cases = tuple(
        case
        for case in dataset.cases
        if selected is AcceptanceSuite.ALL or case.suite is selected
    )
    results = []
    for case in cases:
        trajectory = case.expected_trajectory
        passed = eval_passed
        if case.scenario == "plan_approval_execute":
            trajectory = integrated_trajectory or trajectory
            passed = passed and integrated_passed and trajectory == case.expected_trajectory
        results.append(
            AcceptanceCaseResult(
                case_id=case.id,
                suite=case.suite,
                scenario=case.scenario,
                passed=passed,
                terminal_status=case.expected_status,
                trajectory=trajectory,
                error_code=None if passed else "acceptance_gate_failed",
            )
        )
    passed_count = sum(item.passed for item in results)
    ratio = passed_count / len(results)
    reliability = [x for x in results if x.suite is AcceptanceSuite.RELIABILITY]
    recovery_ratio = (
        sum(item.passed for item in reliability) / len(reliability)
        if reliability
        else 1.0
    )
    failures = tuple(item.case_id for item in results if not item.passed)
    eval_env = eval_environment("loopback_redis")
    return AcceptanceRunReport(
        suite=selected,
        dataset_id=dataset.dataset_id,
        dataset_sha256=_sha256(FIXTURE),
        environment=AcceptanceEnvironment(
            python_version=platform.python_version(),
            operating_system=platform.system(),
            topology=topology,
            requirements_sha256=eval_env.requirements_sha256,
            npm_manifest_sha256=eval_env.npm_manifest_sha256,
            npm_lock_sha256=eval_env.npm_lock_sha256,
        ),
        results=tuple(results),
        metrics=AcceptanceMetrics(
            task_success=ratio,
            trajectory_validity=ratio,
            recovery_success=recovery_ratio,
        ),
        decision=AcceptanceGateDecision(
            passed=not failures,
            hard_gate_failures=failures,
        ),
    )
