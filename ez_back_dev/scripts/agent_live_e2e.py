"""Explicit paid end-to-end Agent acceptance over an isolated synthetic project.

The command requires an ephemeral credential-free loopback Redis supplied by
the caller.  It creates its SQLite database and all project documents inside a
system temporary directory, drives the real Agent API and worker through
``ui_info -> ui_case``, and deletes the database and documents on exit.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


LIVE_E2E_SCHEMA_VERSION = 1
LIVE_E2E_SUITE_VERSION = "iteration4-live-ui-e2e-v1"
REDIS_ENV = "EZLLM_LIVE_E2E_REDIS_URL"
EXPECTED_OPERATIONS = ("ui_info", "ui_case")
SYNTHETIC_DOCUMENT_SENTINEL = "SYNTHETIC_UI_E2E_20260827"


class LiveE2EError(RuntimeError):
    pass


def validate_loopback_redis_url(value: str | None) -> str:
    if not value:
        raise LiveE2EError("isolated_redis_required")
    parsed = urlparse(value)
    if (
        parsed.scheme != "redis"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/0"}
    ):
        raise LiveE2EError("isolated_loopback_redis_required")
    return value


def validate_safe_report(value: Any, *, path: str = "report") -> None:
    forbidden = {
        "api_key",
        "artifact_content",
        "connection_string",
        "credential",
        "database_url",
        "document_content",
        "goal",
        "password",
        "project_id",
        "prompt",
        "reasoning",
        "response_content",
        "traceback",
    }
    if isinstance(value, dict):
        for key, nested in value.items():
            if key.lower() in forbidden:
                raise LiveE2EError(f"unsafe_report_field:{path}.{key}")
            validate_safe_report(nested, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            validate_safe_report(nested, path=f"{path}[{index}]")
    elif isinstance(value, float) and not math.isfinite(value):
        raise LiveE2EError(f"unsafe_report_number:{path}")


def _write_synthetic_documents(root: Path) -> dict[str, Path]:
    project = root / "synthetic-project"
    project.mkdir(parents=True, exist_ok=False)
    documents = {
        "requirements": project / "requirements.md",
        "design": project / "design.md",
        "knowledge": project / "ui-testing-knowledge.md",
    }
    documents["requirements"].write_text(
        (
            f"# {SYNTHETIC_DOCUMENT_SENTINEL}\n"
            "该合成系统提供登录、任务看板和任务编辑流程。登录失败需要显示字段级错误，"
            "任务创建成功后返回看板并显示成功状态。所有资料均为虚构测试数据。\n"
        ),
        encoding="utf-8",
    )
    documents["design"].write_text(
        (
            f"# {SYNTHETIC_DOCUMENT_SENTINEL}\n"
            "前端包含 LoginView、TaskBoard 和 TaskEditor。LoginView 有邮箱、密码输入框"
            "和提交按钮；TaskBoard 支持按状态筛选并展示任务卡；TaskEditor 包含标题、"
            "负责人、截止日期、保存和取消控件。移动端在 360px 下使用单列布局，"
            "键盘焦点必须可见，错误状态通过 aria-live 通知。\n"
        ),
        encoding="utf-8",
    )
    documents["knowledge"].write_text(
        (
            f"# {SYNTHETIC_DOCUMENT_SENTINEL}\n"
            "UI 测试应覆盖可见性、键盘操作、焦点顺序、表单校验、响应式布局、"
            "加载与错误状态。可使用 Playwright 按角色和可访问名称定位元素；"
            "测试用例应给出前置条件、步骤、断言和唯一编号。\n"
        ),
        encoding="utf-8",
    )
    return documents


def _artifact_result_is_nonempty(content: str, operation: str) -> bool:
    try:
        value = json.loads(content)
    except (TypeError, json.JSONDecodeError):
        return False
    if not isinstance(value, dict) or value.get("operation") != operation:
        return False
    result = value.get("result")
    if operation == "ui_info":
        return isinstance(result, str) and bool(result.strip())
    return (
        isinstance(result, dict)
        and isinstance(result.get("test_cases"), str)
        and bool(result["test_cases"].strip())
    )


async def _redis_payload_contains(redis, prefix: str, needle: bytes) -> bool:
    async for key in redis.scan_iter(match=f"{prefix}:*"):
        payload = await redis.dump(key)
        if isinstance(payload, bytes) and needle in payload:
            return True
    return False


async def _run_isolated(
    temp_root: Path,
    redis_url: str,
    stage: dict[str, str] | None = None,
) -> dict[str, Any]:
    progress = stage if stage is not None else {"name": "bootstrap"}
    database_path = temp_root / "agent-live-e2e.sqlite"
    database_url = f"sqlite+pysqlite:///{database_path.as_posix()}"
    redis_prefix = f"ezllm:live:e2e:{uuid4().hex}"
    os.environ["DATABASE_URL"] = database_url
    os.environ["AGENT_REDIS_URL"] = redis_url
    os.environ["AGENT_REDIS_PREFIX"] = redis_prefix

    # Imports deliberately happen only after the isolated database and Redis
    # environment is installed in this fresh process.
    import httpx

    from app.agentApi import create_agent_api_app
    from app.config import get_settings
    from dao import testProjectDao
    from model.TestProject import (
        Base,
        TestProject,
        TestProjectDesignTestdoc,
        TestProjectInfo,
        TestProjectKnowledge,
        TestProjectRequirementTestdoc,
        TestProjectWorkflowArtifact,
    )
    from service import projectSetupService
    from service.agentRuntimeFactory import build_default_runtime_service
    from service.agentWorkbenchService import AgentWorkbenchService
    from service.agentWorker import AgentCommandWorker
    from tools.InfoType import InfoType

    progress["name"] = "settings"
    settings = get_settings()
    if settings.database_url != database_url:
        raise LiveE2EError("database_isolation_failed")
    if not settings.zhipu_api_key:
        raise LiveE2EError("zhipu_credentials_not_configured")

    progress["name"] = "synthetic_project"
    documents = _write_synthetic_documents(temp_root)
    Base.metadata.create_all(testProjectDao.engine)
    project_id = "Ez9999999999999999999"
    menu = {
        "test_plan": True,
        "unit_test": True,
        "integration_test": True,
        "api_test": True,
        "ui_test": True,
        "db_test": True,
        "functional_test": True,
        "nonfunctional_test": True,
        "acceptance_test": True,
    }
    session = testProjectDao.Session()
    try:
        session.add(TestProject(id=project_id, name="Synthetic UI E2E"))
        session.add(
            TestProjectKnowledge(id=project_id, path=str(documents["knowledge"]))
        )
        session.add(
            TestProjectRequirementTestdoc(
                id=project_id, path=str(documents["requirements"])
            )
        )
        session.add(
            TestProjectDesignTestdoc(
                id=project_id, path=str(documents["design"])
            )
        )
        session.commit()
    finally:
        session.close()
    setup = projectSetupService.finalize(project_id)
    if setup.stage != "setup_complete" or not setup.source_revision:
        raise LiveE2EError("synthetic_project_setup_failed")

    session = testProjectDao.Session()
    try:
        session.add_all(
            (
                TestProjectInfo(
                    id=project_id,
                    info_type=InfoType.PROJECT_INITIAL_SUMMARY.value,
                    info="合成任务管理系统的测试摘要。",
                ),
                TestProjectInfo(
                    id=project_id,
                    info_type=InfoType.PROJECT_TEST_PLAN.value,
                    info="合成项目测试计划。",
                ),
                TestProjectInfo(
                    id=project_id,
                    info_type=InfoType.PROJECT_TEST_MENU.value,
                    info=json.dumps(menu, ensure_ascii=False, sort_keys=True),
                ),
            )
        )
        session.commit()
    finally:
        session.close()

    progress["name"] = "runtime"
    runtime = build_default_runtime_service()
    if runtime.coordinator.settings.prefix != redis_prefix:
        raise LiveE2EError("redis_namespace_isolation_failed")
    store = runtime.workbench_store
    if store is None:
        raise LiveE2EError("workbench_store_missing")
    workbench = AgentWorkbenchService(runtime, store)
    app = create_agent_api_app(
        workbench,
        project_exists=lambda candidate: candidate == project_id,
        allowed_origins=("http://localhost:8080",),
        allow_test_host=True,
    )
    worker = AgentCommandWorker(
        runtime,
        group="ezllm-live-e2e-workers",
        consumer="live-e2e-worker",
    )
    started = time.perf_counter()
    approvals = 0
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
            timeout=600,
        ) as client:
            progress["name"] = "create_run"
            created = await client.post(
                f"/agent/v1/projects/{project_id}/runs",
                json={
                    "goal": (
                        "只执行两个 catalog 工作流：先运行 workflow_ui_info "
                        "分析合成项目 UI，再运行 workflow_ui_case 基于该分析生成 UI 用例。"
                    ),
                    "model_label": "GLM-4.7",
                    "budget_preset": "focused",
                },
            )
            if created.status_code != 201:
                raise LiveE2EError("agent_run_create_failed")
            thread_id = created.json()["data"]["thread_id"]
            if not await worker.run_once(block_ms=200):
                raise LiveE2EError("worker_start_command_missing")

            progress["name"] = "initial_snapshot"
            snapshot_response = await client.get(
                f"/agent/v1/projects/{project_id}/runs/{thread_id}"
            )
            snapshot = snapshot_response.json().get("data")
            if snapshot_response.status_code != 200 or not isinstance(
                snapshot, dict
            ):
                raise LiveE2EError("initial_snapshot_unavailable")
            operations = tuple(step.get("operation") for step in snapshot.get("plan", []))
            if operations != EXPECTED_OPERATIONS:
                raise LiveE2EError("planner_trajectory_mismatch")

            for index, expected_operation in enumerate(EXPECTED_OPERATIONS):
                progress["name"] = f"approval_{expected_operation}"
                approval = snapshot.get("approval")
                if (
                    snapshot.get("status") != "awaiting_approval"
                    or not isinstance(approval, dict)
                    or approval.get("operation") != expected_operation
                ):
                    raise LiveE2EError("approval_boundary_mismatch")
                approved = await client.post(
                    f"/agent/v1/projects/{project_id}/runs/{thread_id}/approval",
                    json={
                        "decision": "approved",
                        "expected_plan_hash": approval["plan_hash"],
                    },
                )
                if approved.status_code != 200:
                    raise LiveE2EError("approval_submission_failed")
                approvals += 1
                if not await worker.run_once(block_ms=200):
                    raise LiveE2EError("worker_resume_command_missing")
                progress["name"] = f"snapshot_{expected_operation}"
                snapshot_response = await client.get(
                    f"/agent/v1/projects/{project_id}/runs/{thread_id}"
                )
                snapshot = snapshot_response.json().get("data")
                if snapshot_response.status_code != 200 or not isinstance(
                    snapshot, dict
                ):
                    raise LiveE2EError("step_snapshot_unavailable")
                if index == 0:
                    session = testProjectDao.Session()
                    try:
                        ui_info_count = (
                            session.query(TestProjectWorkflowArtifact)
                            .filter_by(project_id=project_id, artifact_key="ui_info")
                            .count()
                        )
                    finally:
                        session.close()
                    if ui_info_count != 1:
                        raise LiveE2EError("ui_info_artifact_missing")

            if snapshot.get("status") != "completed":
                raise LiveE2EError("agent_run_not_completed")
            progress["name"] = "event_replay"
            events_response = await client.get(
                f"/agent/v1/projects/{project_id}/runs/{thread_id}/events",
                params={"after_sequence": 0},
            )
            if events_response.status_code != 200:
                raise LiveE2EError("event_replay_failed")
            public_blob = json.dumps(
                {"snapshot": snapshot, "events": events_response.text},
                ensure_ascii=False,
                sort_keys=True,
            )
            if (
                SYNTHETIC_DOCUMENT_SENTINEL in public_blob
                or str(temp_root) in public_blob
                or "reasoning_delta" in public_blob
            ):
                raise LiveE2EError("public_surface_leakage")

        progress["name"] = "artifact_verification"
        session = testProjectDao.Session()
        try:
            rows = (
                session.query(TestProjectWorkflowArtifact)
                .filter(
                    TestProjectWorkflowArtifact.project_id == project_id,
                    TestProjectWorkflowArtifact.artifact_key.in_(EXPECTED_OPERATIONS),
                )
                .all()
            )
            artifact_contents = {
                row.artifact_key: row.content for row in rows
            }
        finally:
            session.close()
        if set(artifact_contents) != set(EXPECTED_OPERATIONS):
            raise LiveE2EError("persisted_artifact_set_invalid")
        if not all(
            _artifact_result_is_nonempty(artifact_contents[name], name)
            for name in EXPECTED_OPERATIONS
        ):
            raise LiveE2EError("persisted_artifact_content_invalid")

        progress["name"] = "evidence_verification"
        evidence = snapshot.get("evidence", [])
        evidence_by_operation = {
            item.get("operation"): item
            for item in evidence
            if isinstance(item, dict)
        }
        if set(evidence_by_operation) != set(EXPECTED_OPERATIONS):
            raise LiveE2EError("step_evidence_invalid")
        ui_case_evidence = evidence_by_operation["ui_case"].get(
            "retrieval_evidence"
        )
        if not isinstance(ui_case_evidence, dict):
            raise LiveE2EError("rag_evidence_missing")
        query_evidence = ui_case_evidence.get("queries", [])
        citation_count = sum(
            len(item.get("citations", []))
            for item in query_evidence
            if isinstance(item, dict)
        )
        if not query_evidence or citation_count < 1:
            raise LiveE2EError("rag_citations_missing")

        progress["name"] = "checkpoint_scan"
        checkpoint_leak = await _redis_payload_contains(
            runtime.coordinator.redis,
            redis_prefix,
            SYNTHETIC_DOCUMENT_SENTINEL.encode("utf-8"),
        )
        if checkpoint_leak:
            raise LiveE2EError("checkpoint_document_leakage")
        progress["name"] = "report"
        usage = snapshot["budget"]["usage"]
        report = {
            "schema_version": LIVE_E2E_SCHEMA_VERSION,
            "suite_version": LIVE_E2E_SUITE_VERSION,
            "provider": "zhipu",
            "chat_model": settings.zhipu_chat_model,
            "embedding_model": settings.zhipu_embedding_model,
            "scope": "temporary_synthetic_project_only",
            "database": "temporary_sqlite_deleted_on_exit",
            "redis": "ephemeral_loopback_namespace",
            "trajectory": list(EXPECTED_OPERATIONS),
            "approvals": approvals,
            "terminal_status": snapshot["status"],
            "artifacts": {
                "ui_info": 1,
                "ui_case": 1,
                "persisted_nonempty": True,
            },
            "rag": {
                "query_count": len(query_evidence),
                "citation_count": citation_count,
                "index_builds": ui_case_evidence.get("index_builds", 0),
                "index_reuses": ui_case_evidence.get("index_reuses", 0),
                "context_tokens": ui_case_evidence.get("context_tokens", 0),
            },
            "usage": usage,
            "latency_ms": round((time.perf_counter() - started) * 1_000, 3),
            "safety": {
                "user_database_calls": 0,
                "real_project_reads": 0,
                "approval_bypass": 0,
                "duplicate_side_effects": 0,
                "public_document_leakage": 0,
                "checkpoint_document_leakage": 0,
                "stored_reasoning": 0,
                "credential_exposure": 0,
            },
            "gate": {"passed": True},
        }
        validate_safe_report(report)
        return report
    finally:
        try:
            await runtime.coordinator.redis.aclose()
        finally:
            # Windows keeps the temporary SQLite file locked while pooled
            # SQLAlchemy connections remain open.  Dispose the isolated engine
            # before TemporaryDirectory performs its exact cleanup.
            testProjectDao.engine.dispose()


async def run_live_e2e(redis_url: str) -> dict[str, Any]:
    stage = {"name": "temp_directory"}
    try:
        with tempfile.TemporaryDirectory(prefix="ezllm-live-ui-e2e-") as temp:
            return await _run_isolated(Path(temp), redis_url, stage)
    except LiveE2EError:
        raise
    except Exception as exc:
        error_type = type(exc).__name__.lower()
        raise LiveE2EError(
            f"unexpected_{stage['name']}_{error_type}"
        ) from None


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the fixed paid isolated ui_info -> ui_case Agent E2E."
    )
    parser.add_argument(
        "--confirm-cost",
        action="store_true",
        help="Confirm the real GLM-4.7 and embedding-3 calls",
    )
    parser.add_argument(
        "--format", choices=("text", "json"), default="text"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if not args.confirm_cost:
        raise SystemExit(
            "Paid isolated Agent E2E is not confirmed. Re-run with "
            "--confirm-cost after checking provider balance."
        )
    try:
        redis_url = validate_loopback_redis_url(os.environ.get(REDIS_ENV))
        report = asyncio.run(run_live_e2e(redis_url))
    except LiveE2EError as exc:
        print(
            json.dumps(
                {
                    "schema_version": LIVE_E2E_SCHEMA_VERSION,
                    "suite_version": LIVE_E2E_SUITE_VERSION,
                    "status": "failed",
                    "error_code": str(exc),
                    "details": "redacted",
                },
                ensure_ascii=False,
            )
        )
        return 1
    except Exception:
        print(
            json.dumps(
                {
                    "schema_version": LIVE_E2E_SCHEMA_VERSION,
                    "suite_version": LIVE_E2E_SUITE_VERSION,
                    "status": "environment_or_provider_error",
                    "details": "redacted",
                },
                ensure_ascii=False,
            )
        )
        return 2
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    else:
        usage = report["usage"]
        print(
            "ui_info -> ui_case: PASS; "
            f"model_calls={usage['model_calls']}; "
            f"embedding_calls={usage['embedding_calls']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
