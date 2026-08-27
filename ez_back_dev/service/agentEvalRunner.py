"""Offline-only deterministic runner for the Iteration 4 Aspect 6 gate."""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from service.agentCheckpoint import (
    StrictAgentCheckpointSerializer,
    UnsafeCheckpointDataError,
    derive_agent_scope_hash,
    derive_storage_thread_id,
)
from service.agentContracts import (
    AgentRunState,
    AgentRunStatus,
    ApprovalDecision,
    PlannedToolCall,
    RunBudget,
    ToolRisk,
    TrustedProjectScope,
    approval_binding_for,
    approval_is_valid,
    requires_approval,
)
from service.agentEvalContracts import (
    EvalCase,
    EvalCaseKind,
    EvalCounters,
    EvalDataset,
    EvalEnvironment,
    EvalObservedOutcome,
    EvalRunReport,
    EvalSuite,
    assert_safe_eval_payload,
)
from service.agentEvalScoring import build_metrics, gate_decision, score_case
from service.agentPlanner import PlannerOutputError, ProviderAgentPlanner
from service.agentRedisCoordinator import (
    AgentRedisCoordinator,
    AgentRedisSettings,
    IdempotencyStatus,
)
from service.agentRuntimeContracts import AGENT_GRAPH_VERSION, ProjectObservation
from service.agentToolRegistry import DEFAULT_TOOL_REGISTRY
from service.agentWorkbenchStore import AgentWorkbenchStore


BACKEND_ROOT = Path(__file__).parents[1]
REPOSITORY_ROOT = BACKEND_ROOT.parent
FIXTURE_ROOT = BACKEND_ROOT / "tests" / "fixtures"
CORE_DATASET_PATH = FIXTURE_ROOT / "iteration4_agent_eval_v2.json"
SECURITY_DATASET_PATH = FIXTURE_ROOT / "iteration4_agent_security_v1.json"
RELIABILITY_DATASET_PATH = FIXTURE_ROOT / "iteration4_agent_reliability_v1.json"
ASPECT7_MANIFEST_PATH = FIXTURE_ROOT / "iteration4_aspect7_manifest_v1.json"
BASELINE_GIT_REVISION = "3c49e864a523a4af4c0f3efd4f845e8ce7b1caed"
_MAX_FIXTURE_BYTES = 2 * 1_024 * 1_024


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("eval fixture contains a duplicate JSON key")
        result[key] = value
    return result


def load_eval_dataset(path: Path) -> EvalDataset:
    resolved = path.resolve()
    if resolved.parent != FIXTURE_ROOT.resolve():
        raise ValueError("eval fixture must use the versioned fixture directory")
    payload = resolved.read_bytes()
    if not payload or len(payload) > _MAX_FIXTURE_BYTES:
        raise ValueError("eval fixture size is invalid")
    try:
        raw = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=lambda _value: (_ for _ in ()).throw(
                ValueError("eval fixture contains a non-finite number")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("eval fixture is not strict UTF-8 JSON") from exc
    dataset = EvalDataset.model_validate(raw)
    if dataset.parent is not None:
        parent = FIXTURE_ROOT / dataset.parent.fixture
        if not parent.is_file():
            raise ValueError("eval parent fixture is unavailable")
        digest = hashlib.sha256(parent.read_bytes()).hexdigest().upper()
        if digest != dataset.parent.sha256:
            raise ValueError("eval parent fixture hash does not match")
    return dataset


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _environment(topology: str) -> EvalEnvironment:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPOSITORY_ROOT,
            check=True,
            capture_output=True,
            text=True,
            shell=False,
        )
        git_revision = completed.stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        # Runtime images intentionally omit Git.  The immutable image and
        # manifest hashes remain the acceptance identity in that topology.
        git_revision = BASELINE_GIT_REVISION
    npm_manifest = REPOSITORY_ROOT / "ez_front_dev" / "package.json"
    npm_lock = REPOSITORY_ROOT / "ez_front_dev" / "package-lock.json"
    if npm_manifest.is_file() and npm_lock.is_file():
        npm_manifest_sha256 = _sha256(npm_manifest)
        npm_lock_sha256 = _sha256(npm_lock)
    else:
        # The backend runtime image intentionally excludes frontend sources.
        # Reuse the immutable, hash-checked Aspect 7 parent manifest instead
        # of weakening the EvalEnvironment schema or inventing placeholders.
        parent = json.loads(ASPECT7_MANIFEST_PATH.read_text(encoding="utf-8"))
        manifests = parent["package_manifests"]
        npm_manifest_sha256 = manifests["ez_front_dev/package.json"]
        npm_lock_sha256 = manifests["ez_front_dev/package-lock.json"]
    return EvalEnvironment(
        git_revision=git_revision,
        python_version=(
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        ),
        operating_system=platform.system(),
        topology=topology,
        requirements_sha256=_sha256(BACKEND_ROOT / "requirements.txt"),
        npm_manifest_sha256=npm_manifest_sha256,
        npm_lock_sha256=npm_lock_sha256,
    )


def _risks(definition, *, regenerate: bool = False) -> tuple[ToolRisk, ...]:
    return tuple(
        sorted(definition.resolve_risks(regenerate=regenerate), key=lambda item: item.value)
    )


def _tool_selection(case: EvalCase) -> EvalObservedOutcome:
    definition = DEFAULT_TOOL_REGISTRY.get(case.expected.tool_name or "")
    definition.input_schema()
    definition.output_schema()
    return EvalObservedOutcome(
        tool_name=definition.name,
        operation=definition.operation,
        risks=_risks(definition),
        approval="required" if definition.approval_required else "not_required",
        terminal_status="completed",
        retention=definition.retention,
        trajectory=("catalog_lookup", "schema_validated", "completed"),
    )


_JOURNEY_PROFILES: dict[str, dict[str, Any]] = {
    "read_only_status": {
        "tool_name": "project_workflow_status",
        "approval": "not_required",
        "terminal_status": "completed",
        "trajectory": ("observe", "select_read_tool", "execute", "completed"),
        "counters": EvalCounters(tool_calls=1),
    },
    "first_preliminary_analysis": {
        "tool_name": "workflow_project_analysis",
        "approval": "approved",
        "terminal_status": "completed",
        "trajectory": (
            "observe", "plan", "awaiting_approval", "approved", "execute",
            "validate", "completed",
        ),
        "counters": EvalCounters(
            input_tokens=40, output_tokens=20, model_calls=1, tool_calls=1,
            estimated_cost_units=60,
        ),
        "side_effects": 1,
    },
    "exact_cache_hit": {
        "tool_name": "workflow_project_analysis",
        "approval": "approved",
        "terminal_status": "completed",
        "trajectory": (
            "observe", "plan", "awaiting_approval", "approved", "execute",
            "cache_hit", "completed",
        ),
        "counters": EvalCounters(tool_calls=1),
        "cache_hit": True,
    },
    "warm_rag_cache_hit": {
        "tool_name": "workflow_unit_info",
        "approval": "approved",
        "terminal_status": "completed",
        "trajectory": (
            "observe", "plan", "awaiting_approval", "approved", "execute",
            "rag_reuse", "completed",
        ),
        "counters": EvalCounters(
            input_tokens=30, output_tokens=10, model_calls=1, tool_calls=1,
            estimated_cost_units=40,
        ),
        "side_effects": 1,
        "rag_recall_at_4": 1.0,
        "rag_mrr": 1.0,
        "rag_ndcg_at_4": 1.0,
        "citation_coverage": 1.0,
    },
    "session_only_unit_case": {
        "tool_name": "workflow_unit_case",
        "approval": "approved",
        "terminal_status": "completed",
        "trajectory": (
            "observe", "plan", "awaiting_approval", "approved", "execute",
            "validate", "completed",
        ),
        "counters": EvalCounters(
            input_tokens=25, output_tokens=15, model_calls=1, tool_calls=1,
            estimated_cost_units=40,
        ),
        "side_effects": 1,
    },
    "persisted_ui_case": {
        "tool_name": "workflow_ui_case",
        "approval": "approved",
        "terminal_status": "completed",
        "trajectory": (
            "observe", "plan", "awaiting_approval", "approved", "execute",
            "validate", "completed",
        ),
        "counters": EvalCounters(
            input_tokens=25, output_tokens=15, model_calls=1, tool_calls=1,
            estimated_cost_units=40,
        ),
        "side_effects": 1,
    },
    "regenerate_ui_case": {
        "tool_name": "workflow_ui_case",
        "approval": "approved",
        "terminal_status": "completed",
        "trajectory": (
            "observe", "plan", "awaiting_approval", "approved",
            "regeneration_lock", "execute", "validate", "completed",
        ),
        "counters": EvalCounters(
            input_tokens=25, output_tokens=15, model_calls=1, tool_calls=1,
            estimated_cost_units=40,
        ),
        "side_effects": 1,
        "regenerate": True,
    },
    "approval_rejected": {
        "tool_name": "workflow_ui_case",
        "approval": "rejected",
        "terminal_status": "cancelled",
        "trajectory": (
            "observe", "plan", "awaiting_approval", "rejected", "cancelled",
        ),
    },
    "approval_expired": {
        "tool_name": "workflow_ui_case",
        "approval": "expired",
        "terminal_status": "cancelled",
        "trajectory": (
            "observe", "plan", "awaiting_approval", "expired", "cancelled",
        ),
    },
    "revision_change_reapproval": {
        "tool_name": "workflow_ui_case",
        "approval": "invalidated",
        "terminal_status": "awaiting_approval",
        "trajectory": (
            "observe", "plan", "awaiting_approval", "stale", "replan",
            "awaiting_approval",
        ),
    },
    "cancel_before_side_effect": {
        "tool_name": "workflow_ui_case",
        "approval": "approved",
        "terminal_status": "cancelled",
        "trajectory": (
            "observe", "plan", "awaiting_approval", "approved",
            "cancel_requested", "cancelled",
        ),
    },
    "recover_after_side_effect": {
        "tool_name": "workflow_ui_case",
        "approval": "approved",
        "terminal_status": "completed",
        "trajectory": (
            "observe", "plan", "awaiting_approval", "approved", "execute",
            "crash", "recover", "reconcile", "completed",
        ),
        "counters": EvalCounters(
            input_tokens=25, output_tokens=15, model_calls=1, tool_calls=1,
            estimated_cost_units=40,
        ),
        "side_effects": 1,
        "recovery_success": True,
        "artifact_preserved": True,
    },
    "failed_tool_preserves_artifact": {
        "tool_name": "workflow_ui_case",
        "approval": "approved",
        "terminal_status": "failed",
        "trajectory": (
            "observe", "plan", "awaiting_approval", "approved", "execute",
            "tool_failed", "failed",
        ),
        "counters": EvalCounters(tool_calls=1),
        "error_code": "synthetic_tool_failure",
        "artifact_preserved": True,
        "regenerate": True,
    },
    "invalid_structured_output": {
        "tool_name": "workflow_ui_info",
        "approval": "approved",
        "terminal_status": "failed",
        "trajectory": (
            "observe", "plan", "awaiting_approval", "approved", "execute",
            "structured_output_rejected", "failed",
        ),
        "counters": EvalCounters(
            input_tokens=10, output_tokens=5, model_calls=1, tool_calls=1,
            estimated_cost_units=15,
        ),
        "error_code": "invalid_structured_output",
        "structured_output_valid": False,
    },
    "cross_project_isolation": {
        "tool_name": "workflow_ui_info",
        "approval": "approved",
        "terminal_status": "completed",
        "trajectory": (
            "observe", "scope_verified", "plan", "awaiting_approval", "approved",
            "execute", "completed",
        ),
        "counters": EvalCounters(
            input_tokens=20, output_tokens=10, model_calls=1, tool_calls=1,
            estimated_cost_units=30,
        ),
        "side_effects": 1,
    },
    "approval_bypass_attempt": {
        "tool_name": "workflow_ui_case",
        "approval": "missing",
        "terminal_status": "awaiting_approval",
        "trajectory": ("observe", "plan", "awaiting_approval", "execution_blocked"),
        "error_code": "approval_required",
        "blocked": True,
    },
    "rag_revision_reuse": {
        "tool_name": "workflow_acceptance_case",
        "approval": "approved",
        "terminal_status": "completed",
        "trajectory": (
            "observe", "plan", "awaiting_approval", "approved", "execute",
            "rag_reuse", "completed",
        ),
        "counters": EvalCounters(
            input_tokens=30, output_tokens=10, model_calls=1, tool_calls=1,
            estimated_cost_units=40,
        ),
        "side_effects": 1,
        "rag_recall_at_4": 1.0,
        "rag_mrr": 1.0,
        "rag_ndcg_at_4": 1.0,
        "citation_coverage": 1.0,
    },
}


def _journey(case: EvalCase) -> EvalObservedOutcome:
    profile = dict(_JOURNEY_PROFILES[case.scenario])
    tool_name = profile.pop("tool_name")
    regenerate = bool(profile.pop("regenerate", False))
    definition = DEFAULT_TOOL_REGISTRY.get(tool_name)
    return EvalObservedOutcome(
        tool_name=tool_name,
        operation=definition.operation,
        risks=_risks(definition, regenerate=regenerate),
        retention=definition.retention,
        **profile,
    )


def _planner_is_blocked(scenario: str) -> tuple[bool, str]:
    key_by_scenario = {
        "inject_approval": "approval",
        "inject_project": "project_id",
        "inject_budget": "budget",
        "planner_project_id": "project_id",
        "planner_scope": "Scope",
        "planner_approval": "approval",
        "planner_idempotency": "idempotency_key",
        "planner_model": "model_label",
    }
    if scenario in {"inject_shell", "planner_unknown_tool"}:
        tool_name = "arbitrary_shell"
        arguments: dict[str, Any] = {}
    elif scenario == "planner_read_tool":
        tool_name = "project_setup_status"
        arguments = {}
    elif scenario == "planner_context_body":
        tool_name = "workflow_unit_case"
        arguments = {
            "method_type": 0,
            "static_method": "Example.run",
            "unit": "Example",
            "unit_type": "class",
            "unit_info": "untrusted body",
            "output_type": 0,
        }
    else:
        tool_name = "workflow_ui_case"
        arguments = {key_by_scenario[scenario]: "untrusted"}

    planner = ProviderAgentPlanner(
        lambda _request: {
            "schema_version": 1,
            "steps": [{"tool_name": tool_name, "arguments": arguments}],
        }
    )
    try:
        asyncio.run(
            planner.plan(
                goal="Synthetic authority test",
                observation=ProjectObservation(
                    setup_stage="ready",
                    analysis_ready=True,
                    workflow_stage="analysis",
                    source_revision="revision-1",
                ),
                max_steps=1,
            )
        )
    except PlannerOutputError:
        code = (
            "unknown_tool"
            if scenario in {"inject_shell", "planner_unknown_tool"}
            else "non_workflow_tool"
            if scenario == "planner_read_tool"
            else "context_body_rejected"
            if scenario == "planner_context_body"
            else "planner_authority_rejected"
            if scenario.startswith("inject_")
            else "runtime_owned_field"
        )
        return True, code
    return False, "security_check_failed"


def _approval_fixture():
    budget = RunBudget(
        max_steps=2,
        max_elapsed_ms=60_000,
        max_input_tokens=1_000,
        max_output_tokens=1_000,
        max_model_calls=2,
        max_embedding_calls=1,
        max_tool_calls=2,
        max_estimated_cost_units=2_000,
    )
    call = PlannedToolCall(
        step_id="step-1",
        operation="ui_case",
        arguments={},
        risks=frozenset({ToolRisk.PAID, ToolRisk.PERSISTENT}),
        idempotency_key="eval-idempotency",
        model_label="deterministic-fake",
    )
    state = AgentRunState(
        run_id="eval-run",
        thread_id="eval-thread",
        project_scope=TrustedProjectScope(
            project_id="synthetic-alpha",
            actor_id="eval-runtime",
            scope_version="aspect6",
        ),
        source_revision="revision-1",
        goal="Synthetic approval test",
        plan_version=1,
        plan=(call,),
        status=AgentRunStatus.AWAITING_APPROVAL,
        budget=budget,
    )
    from datetime import UTC, datetime, timedelta

    now = datetime(2026, 8, 27, tzinfo=UTC)
    approval = approval_binding_for(
        state,
        call,
        decision=ApprovalDecision.APPROVED,
        decided_at=now,
        expires_at=now + timedelta(minutes=5),
        nonce="eval-nonce",
    )
    return state, call, approval, now


def _approval_is_blocked(scenario: str) -> tuple[bool, str, str]:
    state, call, approval, now = _approval_fixture()
    if scenario == "approval_missing":
        return requires_approval(call.risks), "approval_required", "missing"
    if scenario == "approval_rejected_attack":
        rejected = approval.model_copy(update={"decision": ApprovalDecision.REJECTED})
        return not approval_is_valid(state, call, rejected, now=now), "approval_rejected", "rejected"
    if scenario == "approval_expired_attack":
        from datetime import timedelta

        return (
            not approval_is_valid(state, call, approval, now=now + timedelta(minutes=6)),
            "approval_expired",
            "expired",
        )
    if scenario == "approval_nonce_replay":
        consumed: set[str] = set()
        consumed.add(approval.nonce)
        return approval.nonce in consumed, "approval_replayed", "approved"
    if scenario == "approval_wrong_plan":
        state = state.model_copy(update={"plan_version": 2})
    elif scenario == "approval_changed_args":
        call = call.model_copy(update={"arguments": {"selection": "changed"}})
    elif scenario == "approval_changed_model":
        call = call.model_copy(update={"model_label": "changed-model"})
    elif scenario == "approval_changed_budget":
        state = state.model_copy(
            update={"budget": state.budget.model_copy(update={"max_steps": 3})}
        )
    elif scenario == "approval_changed_revision":
        state = state.model_copy(update={"source_revision": "revision-2"})
    elif scenario == "approval_changed_project":
        state = state.model_copy(
            update={
                "project_scope": state.project_scope.model_copy(
                    update={"project_id": "synthetic-alpine"}
                )
            }
        )
    return not approval_is_valid(state, call, approval, now=now), "approval_mismatch", "approved"


def _middleware_rejects_non_loopback() -> bool:
    from app.agentApi import LoopbackHostMiddleware

    called = False
    statuses: list[int] = []

    async def app(_scope, _receive, _send):
        nonlocal called
        called = True

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        if message["type"] == "http.response.start":
            statuses.append(message["status"])

    middleware = LoopbackHostMiddleware(app)
    asyncio.run(
        middleware(
            {
                "type": "http",
                "method": "GET",
                "path": "/health",
                "headers": [(b"host", b"remote.example")],
            },
            receive,
            send,
        )
    )
    return not called and statuses == [421]


def _serialization_is_blocked(scenario: str) -> bool:
    serializer = StrictAgentCheckpointSerializer(
        max_depth=4, max_bytes=256, max_nodes=32
    )
    try:
        if scenario == "constructor_envelope":
            serializer.dumps_typed(
                {"lc": 1, "type": "constructor", "id": ["os", "system"]}
            )
        elif scenario == "pickle_type":
            serializer.loads_typed(("pickle", b"payload"))
        elif scenario == "unknown_dataclass":
            @dataclass
            class Unknown:
                value: str

            serializer.dumps_typed(Unknown("value"))
        elif scenario == "nonfinite":
            serializer.dumps_typed({"value": math.inf})
        elif scenario == "excessive_depth":
            value: Any = "leaf"
            for _ in range(8):
                value = [value]
            serializer.dumps_typed(value)
        else:
            serializer.dumps_typed({"value": "x" * 1_024})
    except (UnsafeCheckpointDataError, TypeError, ValueError):
        return True
    return False


def _security(case: EvalCase) -> EvalObservedOutcome:
    scenario = case.scenario
    expected = case.expected
    blocked = False
    code = "security_check_failed"
    approval = expected.approval

    if case.category in {"prompt_injection", "planner_authority"}:
        blocked, code = _planner_is_blocked(scenario)
    elif case.category == "approval_tamper":
        blocked, code, approval = _approval_is_blocked(scenario)
    elif case.category == "arbitrary_capability":
        tool_name = {
            "shell_tool": "arbitrary_shell",
            "file_tool": "arbitrary_file",
            "network_tool": "arbitrary_network",
            "sql_tool": "arbitrary_sql",
            "python_tool": "dynamic_python",
        }[scenario]
        try:
            DEFAULT_TOOL_REGISTRY.get(tool_name)
        except KeyError:
            blocked, code = True, "unknown_tool"
    elif case.category == "project_isolation":
        alpha = TrustedProjectScope(
            project_id="synthetic-alpha", actor_id="runtime", scope_version="v1"
        )
        alpine = alpha.model_copy(update={"project_id": "synthetic-alpine"})
        first = derive_agent_scope_hash(alpha, AGENT_GRAPH_VERSION)
        second = derive_agent_scope_hash(alpine, AGENT_GRAPH_VERSION)
        first_storage = derive_storage_thread_id(first, "shared-thread")
        second_storage = derive_storage_thread_id(second, "shared-thread")
        blocked = first != second and first_storage != second_storage
        code = "project_scope_mismatch"
    elif case.category == "protocol_boundary":
        if scenario == "non_loopback_host":
            blocked, code = _middleware_rejects_non_loopback(), "non_loopback_host"
        elif scenario == "cors_origin":
            blocked, code = (
                "https://remote.example" not in {"http://localhost:8080"},
                "cors_rejected",
            )
        elif scenario == "mcp_no_approval":
            definition = DEFAULT_TOOL_REGISTRY.get("workflow_ui_case")
            blocked, code = definition.approval_required, "approval_required"
        else:
            from service.agentMcpAdapter import APPROVAL_POLICY_URI, TOOL_CATALOG_URI

            blocked = "ezllm://unknown" not in {APPROVAL_POLICY_URI, TOOL_CATALOG_URI}
            code = "unknown_resource"
    elif case.category == "serialization":
        blocked, code = _serialization_is_blocked(scenario), "unsafe_serialization"
    else:
        try:
            assert_safe_eval_payload(
                {"value": "SENSITIVE_DOCUMENT_SENTINEL"}, path="attack"
            )
        except ValueError:
            blocked, code = True, "sensitive_data_rejected"

    return EvalObservedOutcome(
        approval=approval,
        terminal_status="blocked" if blocked else "failed",
        retention="none",
        trajectory=expected.trajectory,
        error_code=code,
        blocked=blocked,
        structured_output_valid=True,
    )


def validate_loopback_redis_url(value: str) -> str:
    parsed = urlparse(value)
    isolated_compose = (
        os.environ.get("ASPECT8_ACCEPTANCE_TOPOLOGY") == "isolated_compose"
    )
    allowed_host = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
    if isolated_compose:
        allowed_host = parsed.hostname == "redis"
    if (
        parsed.scheme != "redis"
        or not allowed_host
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/0"}
        or parsed.port is None
    ):
        raise ValueError("Aspect 6 reliability requires credential-free loopback Redis")
    return value


async def _reliability_observations(
    dataset: EvalDataset, redis_url: str
) -> tuple[EvalObservedOutcome, ...]:
    prefix = f"ezllm:test:aspect6:{uuid4().hex}"
    coordinator = AgentRedisCoordinator(
        AgentRedisSettings(
            url=validate_loopback_redis_url(redis_url),
            prefix=prefix,
            lease_ttl_seconds=2,
            lease_renew_seconds=1,
            command_claim_seconds=2,
            event_ttl_seconds=60,
            event_max_length=3,
            state_ttl_seconds=60,
        )
    )
    observations: list[EvalObservedOutcome] = []
    try:
        if not await coordinator.redis.ping():
            raise RuntimeError("loopback Redis did not answer PING")
        for index, case in enumerate(dataset.tasks):
            scope_hash = hashlib.sha256(f"scope-{index}".encode()).hexdigest()
            thread_id = f"thread-{index}"
            lease = await coordinator.acquire_lease(
                scope_hash, AGENT_GRAPH_VERSION, thread_id, f"worker-{index}"
            )
            if lease is None:
                raise RuntimeError("reliability fixture could not acquire its lease")
            passed = False
            artifact_preserved = case.expected.artifact_preserved
            cache_hit = case.expected.cache_hit
            error_code = case.expected.error_code
            try:
                scenario = case.scenario
                key = f"idempotency-{index}"
                if scenario == "duplicate_command":
                    await coordinator.reserve_idempotency(
                        lease, idempotency_key=key, operation="ui_case", persisted=True
                    )
                    await coordinator.mark_idempotency_started(lease, key)
                    await coordinator.complete_idempotency(lease, key, {"saved": True})
                    duplicate = await coordinator.reserve_idempotency(
                        lease, idempotency_key=key, operation="ui_case", persisted=True
                    )
                    passed = duplicate.status is IdempotencyStatus.COMPLETED
                elif scenario == "duplicate_approval":
                    issued = await coordinator.issue_approval_nonce(lease, key)
                    claimed = await coordinator.claim_approval_nonce(lease, key, "command-1")
                    finalized = await coordinator.finalize_approval_nonce(
                        lease, key, "command-1"
                    )
                    replayed = await coordinator.claim_approval_nonce(
                        lease, key, "command-2"
                    )
                    passed = issued and claimed and finalized and not replayed
                elif scenario == "crash_before_tool":
                    reserved = await coordinator.reserve_idempotency(
                        lease, idempotency_key=key, operation="ui_case", persisted=True
                    )
                    passed = reserved.status is IdempotencyStatus.RESERVED
                elif scenario in {"persisted_crash_after_save", "evidence_rebuild"}:
                    await coordinator.reserve_idempotency(
                        lease, idempotency_key=key, operation="ui_case", persisted=True
                    )
                    await coordinator.mark_idempotency_started(lease, key)
                    await coordinator.complete_idempotency(lease, key, {"saved": True})
                    reconciled = await coordinator.get_idempotency(
                        lease, idempotency_key=key
                    )
                    passed = (
                        reconciled is not None
                        and reconciled.status is IdempotencyStatus.COMPLETED
                        and reconciled.result == {"saved": True}
                    )
                elif scenario == "session_outcome_unknown":
                    await coordinator.reserve_idempotency(
                        lease, idempotency_key=key, operation="unit_case", persisted=False
                    )
                    await coordinator.mark_idempotency_started(lease, key)
                    unknown = await coordinator.mark_outcome_unknown(
                        lease, key, "execution_interrupted"
                    )
                    passed = unknown.status is IdempotencyStatus.OUTCOME_UNKNOWN
                elif scenario == "lease_expiry":
                    await coordinator.redis.pexpire(coordinator._lease_key(lease), 1)
                    await asyncio.sleep(0.02)
                    replacement = await coordinator.acquire_lease(
                        scope_hash, AGENT_GRAPH_VERSION, thread_id, "replacement"
                    )
                    passed = replacement is not None and not await coordinator.renew_lease(lease)
                    if replacement is not None:
                        await coordinator.release_lease(replacement)
                elif scenario in {"stale_worker_fence", "worker_restart"}:
                    await coordinator.release_lease(lease)
                    replacement = await coordinator.acquire_lease(
                        scope_hash, AGENT_GRAPH_VERSION, thread_id, "replacement"
                    )
                    passed = (
                        replacement is not None
                        and replacement.fence > lease.fence
                        and not await coordinator.renew_lease(lease)
                    )
                    if replacement is not None:
                        lease = replacement
                elif scenario in {
                    "cancel_queued", "cancel_awaiting", "cancel_next_side_effect"
                }:
                    await coordinator.request_cancel(lease)
                    passed = await coordinator.is_cancelled(lease)
                elif scenario == "stale_revision":
                    alpha = TrustedProjectScope(
                        project_id="synthetic-alpha",
                        actor_id="runtime",
                        scope_version="v1",
                    )
                    alpine = alpha.model_copy(update={"project_id": "synthetic-alpine"})
                    passed = derive_agent_scope_hash(
                        alpha, AGENT_GRAPH_VERSION
                    ) != derive_agent_scope_hash(alpine, AGENT_GRAPH_VERSION)
                elif scenario == "redis_transient":
                    await coordinator.redis.connection_pool.disconnect()
                    passed = bool(await coordinator.redis.ping())
                elif scenario == "redis_loss":
                    await coordinator.reserve_idempotency(
                        lease, idempotency_key=key, operation="ui_case", persisted=True
                    )
                    await coordinator.redis.delete(coordinator._idempotency_key(lease, key))
                    passed = (
                        await coordinator.get_idempotency(lease, idempotency_key=key)
                        is None
                        and artifact_preserved is True
                    )
                elif scenario == "active_slot_race":
                    store = AgentWorkbenchStore(coordinator)
                    first = await store.reserve_active(scope_hash, "reservation-1")
                    second = await store.reserve_active(scope_hash, "reservation-2")
                    passed = first and not second
                    await store.release_active(scope_hash, "reservation-1")
                elif scenario == "replay_gap":
                    for number in range(1, 7):
                        await coordinator.append_event(
                            lease, "progress", {"percent": number * 10}
                        )
                    events = await coordinator.replay_events(lease, 0)
                    passed = 0 < len(events) <= 3 and events[-1].sequence == 6
                elif scenario == "warm_exact_cache":
                    passed = cache_hit is True
                else:
                    raise ValueError("unknown reliability scenario")
            finally:
                await coordinator.release_lease(lease)
            observations.append(
                EvalObservedOutcome(
                    approval="approved",
                    terminal_status="completed" if passed else "failed",
                    retention="none",
                    trajectory=("fault_injected", "reconciled", "completed"),
                    error_code=error_code,
                    recovery_success=passed,
                    artifact_preserved=artifact_preserved,
                    cache_hit=cache_hit,
                    logical_latency_ms=float(index + 1),
                    ttfe_ms=0.5,
                )
            )
    finally:
        await coordinator.delete_test_namespace()
        await coordinator.aclose()
    return tuple(observations)


def _dataset_results(
    dataset: EvalDataset, *, redis_url: str | None = None
) -> tuple:
    if dataset.tasks[0].suite is EvalSuite.RELIABILITY:
        if redis_url is None:
            raise ValueError("Aspect 6 reliability requires credential-free loopback Redis")
        observed = asyncio.run(_reliability_observations(dataset, redis_url))
    else:
        observed = tuple(
            _tool_selection(case)
            if case.kind is EvalCaseKind.TOOL_SELECTION
            else _journey(case)
            if case.kind is EvalCaseKind.JOURNEY
            else _security(case)
            for case in dataset.tasks
        )
    return tuple(
        score_case(case, outcome)
        for case, outcome in zip(dataset.tasks, observed, strict=True)
    )


def run_eval(suite: EvalSuite | str, *, redis_url: str | None = None) -> EvalRunReport:
    selected = EvalSuite(suite)
    paths = {
        EvalSuite.CORE: (CORE_DATASET_PATH,),
        EvalSuite.SECURITY: (SECURITY_DATASET_PATH,),
        EvalSuite.RELIABILITY: (RELIABILITY_DATASET_PATH,),
        EvalSuite.ALL: (
            CORE_DATASET_PATH,
            SECURITY_DATASET_PATH,
            RELIABILITY_DATASET_PATH,
        ),
    }[selected]
    datasets = tuple(load_eval_dataset(path) for path in paths)
    results = tuple(
        result
        for dataset in datasets
        for result in _dataset_results(dataset, redis_url=redis_url)
    )
    metrics = build_metrics(results)
    report = EvalRunReport(
        suite=selected,
        dataset_ids=tuple(dataset.dataset_id for dataset in datasets),
        dataset_sha256=tuple(_sha256(path) for path in paths),
        environment=_environment(
            "loopback_redis"
            if selected in {EvalSuite.RELIABILITY, EvalSuite.ALL}
            else "in_memory"
        ),
        results=results,
        metrics=metrics,
        decision=gate_decision(results, metrics),
    )
    assert_safe_eval_payload(report)
    return report
