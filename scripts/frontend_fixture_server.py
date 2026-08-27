"""Loopback-only offline REST/SSE fixture for frontend experience checks."""

from __future__ import annotations

import argparse
import json
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse


FIXTURE_HOST = "127.0.0.1"
DEFAULT_PORT = 18130
DEFAULT_ORIGIN_PORT = 18080
MAX_STATUS_DELAY_MS = 10000
MAX_PLAN_DELAY_MS = 10000
MAX_FIXTURE_UPLOAD_BYTES = 1024 * 1024
ANALYSIS_REQUIRED_PID = "Ez3000000000000000001"
READY_PID = "Ez3000000000000000002"
STALE_PID = "Ez3000000000000000003"
MIXED_MENU_PID = "Ez3000000000000000004"
PLAN_FAILURE_PID = "Ez3000000000000000005"
ANALYSIS_STALE_PID = "Ez3000000000000000006"
WORKSPACE_READY_PID = "Ez3000000000000000007"
PERSISTENCE_FAILURE_PID = "Ez3000000000000000008"
AGENT_FIXTURE_PID = WORKSPACE_READY_PID
RECOVERY_PID = "Ez4000000000000000001"
FIXTURE_IDS = {
    ANALYSIS_REQUIRED_PID,
    READY_PID,
    STALE_PID,
    MIXED_MENU_PID,
    PLAN_FAILURE_PID,
    ANALYSIS_STALE_PID,
    WORKSPACE_READY_PID,
    PERSISTENCE_FAILURE_PID,
}
ALLOWED_ORIGIN = f"http://{FIXTURE_HOST}:{DEFAULT_ORIGIN_PORT}"
SESSION_ONLY_OPERATIONS = {
    "unit_case",
    "integration_case",
    "api_case",
    "functional_case",
    "nonfunctional_case",
}


class AgentFixtureState:
    """Process-local Agent API state; it never calls a provider or database."""

    def __init__(self):
        self._lock = threading.Lock()
        self.model_calls = 0
        self.embedding_calls = 0
        self.tool_calls = 0
        self._next_run = 1
        self.active_thread_id: str | None = "fixture-thread-active"
        self._runs = {
            "fixture-thread-active": self._run(
                "fixture-run-active", "fixture-thread-active", "awaiting_approval"
            ),
            "fixture-thread-session": self._run(
                "fixture-run-session", "fixture-thread-session", "completed",
                session=True,
            ),
            "fixture-thread-failed": self._run(
                "fixture-run-failed", "fixture-thread-failed", "failed"
            ),
        }
        self._events = {
            "fixture-thread-active": [
                self._event(1, "queued", "created"),
                self._event(2, "planning", "planning"),
                self._event(3, "approval_required", "awaiting_approval"),
            ],
            "fixture-thread-session": [
                self._event(1, "queued", "created"),
                self._event(2, "completed", "completed"),
            ],
            "fixture-thread-failed": [
                self._event(1, "queued", "created"),
                self._event(
                    2,
                    "failed",
                    "failed",
                    safe_message="离线夹具：可恢复的 worker 中断。",
                ),
            ],
        }

    @staticmethod
    def _event(sequence: int, kind: str, status: str, **extra):
        return {
            "schema_version": 1,
            "sequence": sequence,
            "kind": kind,
            "occurred_at": f"2026-08-27T10:00:{sequence:02d}+00:00",
            "status": status,
            **extra,
        }

    @staticmethod
    def _usage(tool_calls: int = 0):
        return {
            "steps": tool_calls,
            "elapsed_ms": tool_calls * 320,
            "input_tokens": tool_calls * 10,
            "output_tokens": tool_calls * 20,
            "model_calls": tool_calls,
            "embedding_calls": 0,
            "tool_calls": tool_calls,
            "estimated_cost_units": tool_calls * 30,
        }

    @classmethod
    def _budget(cls, tool_calls: int = 0):
        limits = {
            "max_steps": 3,
            "max_elapsed_ms": 1200000,
            "max_input_tokens": 768000,
            "max_output_tokens": 147456,
            "max_model_calls": 12,
            "max_embedding_calls": 6,
            "max_tool_calls": 3,
            "max_estimated_cost_units": 915456,
        }
        usage = cls._usage(tool_calls)
        return {
            "preset": "focused",
            "limits": limits,
            "usage": usage,
            "remaining": {
                key: max(0, value - usage.get(key.replace("max_", ""), 0))
                for key, value in limits.items()
            },
            "cost_unit": "synthetic_test_unit",
        }

    @classmethod
    def _run(
        cls,
        run_id: str,
        thread_id: str,
        status: str,
        *,
        session: bool = False,
    ):
        awaiting = status == "awaiting_approval"
        completed = status == "completed"
        failed = status == "failed"
        operation = "unit_case" if session else "ui_case"
        retention = "session" if session else "artifact"
        evidence = []
        if completed:
            evidence = [
                {
                    "schema_version": 1,
                    "step_id": "step-1",
                    "operation": operation,
                    "retention": retention,
                    "status": "success",
                    "saved": not session,
                    "from_cache": False,
                    "source_revision": "fixture-revision-2",
                    "artifact_key": None if session else "ui_case",
                    "workspace_route": "/unit" if session else "/ui",
                    "session_result": (
                        {"cases": [{"name": "离线线程临时用例"}]}
                        if session
                        else None
                    ),
                    "usage": cls._usage(1),
                    "error_code": None,
                    "safe_message": None,
                    "retrieval_evidence": {
                        "policy_version": "iteration4-aspect5-v1",
                        "strategy": "dense_v1",
                        "context_tokens": 42,
                        "index_builds": 1,
                        "index_reuses": 0,
                        "queries": [
                            {
                                "strategy": "dense_v1",
                                "policy_version": "iteration4-aspect5-v1",
                                "corpus": "knowledge",
                                "source_revision": "fixture-revision-2",
                                "query_hash": "b" * 64,
                                "index_status": "build",
                                "context_tokens": 42,
                                "citations": [
                                    {
                                        "citation_id": "C1",
                                        "corpus": "knowledge",
                                        "source_label": "fixture-knowledge.md",
                                        "page": 2,
                                        "rank": 1,
                                        "score": 0.912345,
                                        "score_kind": "dense",
                                        "chunk_hash": "c" * 64,
                                    }
                                ],
                            }
                        ],
                    },
                }
            ]
        return {
            "schema_version": 1,
            "run_id": run_id,
            "thread_id": thread_id,
            "goal": "验证离线 Agent 工作台的审批与恢复体验",
            "status": status,
            "source_revision": "fixture-revision-2",
            "created_at": "2026-08-27T10:00:00+00:00",
            "deadline_at": "2026-08-27T10:20:00+00:00",
            "expires_at": "2026-09-03T10:00:00+00:00",
            "model_label": "GLM-4.7",
            "budget": cls._budget(1 if completed else 0),
            "plan_version": 1,
            "current_step_index": 0,
            "plan": [
                {
                    "step_id": "step-1",
                    "operation": operation,
                    "arguments": {},
                    "risks": ["paid", "persistent"] if not session else ["paid"],
                    "model_label": "GLM-4.7",
                    "retention": retention,
                    "current": not completed,
                    "context_bindings": [
                        {
                            "payload_field": "info",
                            "source_operation": "ui_info" if not session else "unit_info",
                            "artifact_key": "ui_info" if not session else "unit_info",
                            "source_revision": "fixture-revision-2",
                            "result_path": [] if not session else ["unit_info"],
                            "content_sha256": "d" * 64,
                        }
                    ],
                }
            ],
            "approval": (
                {
                    "plan_hash": "a" * 64,
                    "plan_version": 1,
                    "step_id": "step-1",
                    "operation": operation,
                    "risks": ["paid", "persistent"] if not session else ["paid"],
                    "expires_at": "2026-08-28T10:00:00+00:00",
                    "expired": False,
                }
                if awaiting
                else None
            ),
            "evidence": evidence,
            "last_error": (
                {
                    "code": "fixture_worker_interrupted",
                    "category": "transient",
                    "retryable": True,
                    "safe_message": "离线夹具：worker 中断，可安全恢复。",
                }
                if failed
                else None
            ),
            "last_event_sequence": 3 if awaiting else 2,
            "worker_available": thread_id != "fixture-thread-failed",
            "active": awaiting,
            "can_approve": awaiting,
            "can_edit": awaiting,
            "can_cancel": awaiting,
            "can_recover": failed,
            "trace_id": "0123456789abcdef0123456789abcdef" if completed else None,
            "trace_status": "instrumented" if completed else "not_instrumented",
            "retrieval": {
                "strategy": "dense_v1",
                "policy_version": "iteration4-aspect5-v1",
                "citation_mode": "metadata_only",
                "rerank_enabled": False,
                "agent_only": True,
            },
        }

    @staticmethod
    def capabilities():
        return {
            "schema_version": 1,
            "graph_version": "iteration4-aspect3-v1",
            "scope_version": "iteration4-aspect4-v1",
            "models": ["GLM-4.7", "通义千问", "DeepSeek", "Moonshot Kimi"],
            "budget_presets": [
                {"name": "focused", "budget": AgentFixtureState._budget()["limits"], "cost_unit": "synthetic_test_unit"},
                {"name": "standard", "budget": {**AgentFixtureState._budget()["limits"], "max_steps": 8, "max_tool_calls": 8}, "cost_unit": "synthetic_test_unit"},
            ],
            "risks": ["read_only", "paid", "persistent", "regenerate"],
            "single_agent": True,
            "chain_of_thought": False,
            "trace_status": "not_instrumented",
        }

    def list_runs(self):
        with self._lock:
            runs = [
                {
                    key: run[key]
                    for key in (
                        "run_id", "thread_id", "goal", "status", "model_label", "created_at", "active"
                    )
                }
                | {"budget_preset": run["budget"]["preset"]}
                for run in self._runs.values()
            ]
            return {
                "runs": runs,
                "active_thread_id": self.active_thread_id,
                "next_cursor": None,
            }

    def get_run(self, thread_id: str):
        with self._lock:
            value = self._runs.get(thread_id)
            return json.loads(json.dumps(value, ensure_ascii=False)) if value else None

    def create(self, goal: str):
        with self._lock:
            if self.active_thread_id:
                return None
            thread_id = f"fixture-thread-created-{self._next_run}"
            run_id = f"fixture-run-created-{self._next_run}"
            self._next_run += 1
            run = self._run(run_id, thread_id, "awaiting_approval")
            run["goal"] = goal
            self._runs[thread_id] = run
            self._events[thread_id] = [
                self._event(1, "queued", "created"),
                self._event(2, "planning", "planning"),
                self._event(3, "approval_required", "awaiting_approval"),
            ]
            self.active_thread_id = thread_id
            return {
                "run_id": run_id,
                "thread_id": thread_id,
                "command_id": "fixture-command-create",
            }

    def events(self, thread_id: str, after_sequence: int):
        with self._lock:
            return [
                dict(event)
                for event in self._events.get(thread_id, [])
                if event["sequence"] > after_sequence
            ]

    def decide(self, thread_id: str, decision: str, plan_hash: str):
        with self._lock:
            run = self._runs.get(thread_id)
            if not run or not run["approval"] or plan_hash != "a" * 64:
                return None
            if decision == "approved":
                completed = self._run(run["run_id"], thread_id, "completed")
                self._runs[thread_id] = completed
                self.model_calls += 1
                self.tool_calls += 1
                self._events[thread_id].extend(
                    [
                        self._event(4, "approval_submitted", "awaiting_approval"),
                        self._event(5, "executing", "executing"),
                        self._event(6, "progress", "executing", percent=50, label="离线安全进度"),
                        self._event(7, "tool_succeeded", "executing"),
                        self._event(8, "completed", "completed"),
                    ]
                )
            else:
                run["status"] = "cancelled"
                run["active"] = False
                run["can_approve"] = run["can_edit"] = run["can_cancel"] = False
                run["approval"] = None
                self._events[thread_id].append(
                    self._event(4, "cancelled", "cancelled")
                )
            self.active_thread_id = None
            return {"command_id": "fixture-command-decision"}

    def cancel(self, thread_id: str):
        return self.decide(thread_id, "rejected", "a" * 64)

    def edit(self, thread_id: str, goal: str, plan_hash: str):
        with self._lock:
            run = self._runs.get(thread_id)
            if not run or not run["approval"] or plan_hash != "a" * 64:
                return None
            run["goal"] = goal
            run["status"] = "planning"
            run["approval"] = None
            run["can_approve"] = False
            run["can_edit"] = False
            self._events[thread_id].append(
                self._event(4, "replanning", "planning")
            )
            return {"command_id": "fixture-command-edit"}

    def recover(self, thread_id: str):
        with self._lock:
            run = self._runs.get(thread_id)
            if not run or not run.get("can_recover") or self.active_thread_id:
                return None
            run["status"] = "recovering"
            run["active"] = True
            run["can_recover"] = False
            self.active_thread_id = thread_id
            self._events[thread_id].append(
                self._event(3, "recovering", "recovering")
            )
            return {"command_id": "fixture-command-recover"}

TEST_ROUTES = [
    "/unit",
    "/integration",
    "/api",
    "/ui",
    "/database",
    "/functional",
    "/nfunctional",
    "/acceptance",
]

SETUP_GROUPS = ("knowledge", "requirements", "design")
DOCTYPE_GROUPS = {1: "knowledge", 2: "requirements", 3: "design"}


def normalize_uploaded_filename(filename: str) -> str:
    safe_name = re.split(r"[\\/]", filename.strip())[-1]
    if "." in safe_name:
        stem, extension = safe_name.rsplit(".", 1)
        suffix = f".{extension}"
    else:
        stem, suffix = safe_name, ""
    return stem.replace(" ", "-").replace(".", "_") + suffix


class OnboardingFixtureState:
    """Process-local synthetic setup state; file bytes are never retained."""

    def __init__(self, fail_upload_once: str | None = None):
        self.fail_upload_once = fail_upload_once
        self.failure_used = False
        self._next_project = 2
        self._lock = threading.Lock()
        self._projects: dict[str, dict[str, Any]] = {
            RECOVERY_PID: {
                "name": "离线待恢复项目",
                "documents": {
                    "knowledge": ["existing-knowledge.md"],
                    "requirements": [],
                    "design": ["existing-design.md"],
                },
                "complete": False,
            }
        }

    def has_project(self, pid: str) -> bool:
        with self._lock:
            return pid in self._projects

    def login(self, pid: str) -> str | None:
        with self._lock:
            project = self._projects.get(pid)
            return str(project["name"]) if project else None

    def create_project(self, name: str) -> str:
        with self._lock:
            pid = f"Ez{4_000_000_000_000_000_000 + self._next_project}"
            self._next_project += 1
            self._projects[pid] = {
                "name": name,
                "documents": {group: [] for group in SETUP_GROUPS},
                "complete": False,
            }
            return pid

    def upload(self, pid: str, group: str, filename: str) -> bool:
        if group not in SETUP_GROUPS:
            raise ValueError("unknown setup group")
        normalized = normalize_uploaded_filename(filename)
        if not normalized:
            raise ValueError("filename is required")
        with self._lock:
            project = self._projects.get(pid)
            if project is None:
                raise KeyError(pid)
            documents: list[str] = project["documents"][group]
            if (
                self.fail_upload_once == group
                and len(documents) >= 1
                and not self.failure_used
            ):
                self.failure_used = True
                return False
            if normalized.casefold() not in {item.casefold() for item in documents}:
                documents.append(normalized)
            return True

    def status(self, pid: str) -> dict[str, Any]:
        with self._lock:
            project = self._projects.get(pid)
            if project is None:
                raise KeyError(pid)
            documents = {
                group: list(project["documents"][group]) for group in SETUP_GROUPS
            }
            complete = bool(project["complete"])
        counts = {group: len(documents[group]) for group in SETUP_GROUPS}
        if complete:
            stage = "setup_complete"
        elif all(counts[group] > 0 for group in SETUP_GROUPS):
            stage = "documents_ready"
        elif counts["design"] > 0:
            stage = "design_uploaded"
        elif counts["requirements"] > 0:
            stage = "requirements_uploaded"
        elif counts["knowledge"] > 0:
            stage = "knowledge_uploaded"
        else:
            stage = "project_created"
        allowed_actions = (
            ["continue_to_plan"]
            if complete
            else [
                f"upload_{group}" for group in SETUP_GROUPS if counts[group] == 0
            ]
            or ["finalize"]
        )
        missing_labels = [
            label
            for group, label in (
                ("knowledge", "测试知识库"),
                ("requirements", "业务需求文档"),
                ("design", "开发设计文档"),
            )
            if counts[group] == 0
        ]
        if complete:
            message = "项目资料已确认"
        elif not missing_labels:
            message = "项目资料已齐全，可以确认创建"
        else:
            message = "请补充" + "、".join(missing_labels)
        return {
            "pid": pid,
            "project_exists": True,
            "stage": stage,
            "document_counts": counts,
            "document_files": documents,
            "allowed_actions": allowed_actions,
            "source_revision": "fixture-setup-revision" if not missing_labels else None,
            "message": message,
        }

    def finalize(self, pid: str) -> dict[str, Any]:
        status = self.status(pid)
        if status["stage"] not in {"documents_ready", "setup_complete"}:
            raise ValueError(status["message"])
        with self._lock:
            self._projects[pid]["complete"] = True
        return self.status(pid)


def _menu_state(enabled: bool) -> dict[str, bool]:
    return {
        "test_plan": enabled,
        "unit_test": enabled,
        "integration_test": enabled,
        "api_test": enabled,
        "ui_test": enabled,
        "db_test": enabled,
        "functional_test": enabled,
        "nonfunctional_test": enabled,
        "acceptance_test": enabled,
    }


def _mixed_menu_state() -> dict[str, bool]:
    menu = _menu_state(True)
    menu["db_test"] = False
    menu["nonfunctional_test"] = False
    return menu


def allowed_origin_for(port: int) -> str:
    if not 1 <= port <= 65535:
        raise ValueError("origin port must be between 1 and 65535")
    return f"http://{FIXTURE_HOST}:{port}"


def workflow_status_for(pid: str) -> dict[str, Any]:
    """Return one of three deterministic project lifecycle snapshots."""
    if pid == ANALYSIS_REQUIRED_PID:
        return {
            "pid": pid,
            "stage": "analysis_required",
            "allowed_routes": ["/plan"],
            "completed_operations": [],
            "stale_operations": [],
            "menu": None,
            "source_revision": "fixture-revision-1",
            "message": "离线夹具：请先完成测试计划。",
        }
    if pid == STALE_PID:
        return {
            "pid": pid,
            "stage": "testing_in_progress",
            "allowed_routes": ["/plan", "/menu", *TEST_ROUTES],
            "completed_operations": ["project_analysis", "unit_menu", "ui_info"],
            "stale_operations": ["unit_info", "unit_case", "ui_info", "ui_case"],
            "menu": _menu_state(True),
            "source_revision": "fixture-revision-3",
            "message": "离线夹具：源资料已更新，部分结果需要重新生成。",
        }
    if pid == WORKSPACE_READY_PID:
        return {
            "pid": pid,
            "stage": "testing_ready",
            "allowed_routes": ["/plan", "/menu", *TEST_ROUTES],
            "completed_operations": [
                "project_analysis",
                "unit_menu",
                "unit_info",
                "integration_menu",
                "integration_info",
                "api_info",
                "ui_info",
                "ui_case",
                "db_info",
                "db_case",
                "functional_info",
                "nonfunctional_info",
                "acceptance_info",
                "acceptance_case",
            ],
            "stale_operations": [],
            "menu": _menu_state(True),
            "source_revision": "fixture-revision-7",
            "message": "离线夹具：八类测试工作区均可恢复。",
        }
    if pid == PERSISTENCE_FAILURE_PID:
        return {
            "pid": pid,
            "stage": "testing_ready",
            "allowed_routes": ["/plan", "/menu", *TEST_ROUTES],
            "completed_operations": ["project_analysis", "ui_info", "ui_case"],
            "stale_operations": [],
            "menu": _menu_state(True),
            "source_revision": "fixture-revision-8",
            "message": "离线夹具：已保留一份可恢复的前端 UI 测试结果。",
        }
    return {
        "pid": pid,
        "stage": "testing_in_progress",
        "allowed_routes": ["/plan", "/menu", *TEST_ROUTES],
        "completed_operations": ["project_analysis"],
        "stale_operations": [],
        "menu": _menu_state(True),
        "source_revision": "fixture-revision-2",
        "message": "离线夹具：项目已就绪。",
    }


class PlanningFixtureState:
    """Process-local synthetic planning bundles; nothing is written to disk."""

    def __init__(self):
        self._lock = threading.Lock()
        self._failure_used = False
        self._generated: set[str] = set()
        self._bundles: dict[str, dict[str, Any]] = {
            READY_PID: self._bundle("离线就绪项目", _menu_state(True)),
            STALE_PID: self._bundle("离线部分过期项目", _menu_state(True)),
            MIXED_MENU_PID: self._bundle("离线混合推荐项目", _mixed_menu_state()),
            ANALYSIS_STALE_PID: self._bundle("离线上一版计划", _menu_state(True)),
            PERSISTENCE_FAILURE_PID: self._bundle(
                "离线持久化失败回滚项目", _menu_state(True)
            ),
        }

    @staticmethod
    def _bundle(label: str, menu: dict[str, bool]) -> dict[str, Any]:
        return {
            "summary": (
                f"{label}业务摘要：系统包含项目入口、规划工作台和八类测试空间。"
                "本段仅为离线合成文本，用于验证长文本换行与只读恢复。"
            ),
            "plan": (
                f"{label}建议计划：先确认业务边界和资料版本，再按推荐类型开展测试，"
                "并在每一步明确保存、过期、取消和失败反馈。"
            ),
            "menu": dict(menu),
        }

    def project_info(self, pid: str, info_type: int) -> str | None:
        with self._lock:
            bundle = self._bundles.get(pid)
            if bundle is None:
                return None
            if info_type == 1:
                return str(bundle["summary"])
            if info_type == 22:
                return str(bundle["plan"])
            if info_type == 23:
                return json.dumps(bundle["menu"], ensure_ascii=False)
        return None

    def workflow_status(self, pid: str) -> dict[str, Any]:
        if pid == ANALYSIS_STALE_PID and pid not in self._generated:
            return {
                "pid": pid,
                "stage": "analysis_required",
                "allowed_routes": ["/plan"],
                "completed_operations": [],
                "stale_operations": ["project_analysis"],
                "menu": None,
                "source_revision": "fixture-revision-6",
                "message": "离线夹具：资料已更新，上一版计划需要重新生成。",
            }
        if pid == MIXED_MENU_PID and pid not in self._generated:
            menu = _mixed_menu_state()
            routes = [
                route
                for route, key in zip(
                    TEST_ROUTES,
                    (
                        "unit_test",
                        "integration_test",
                        "api_test",
                        "ui_test",
                        "db_test",
                        "functional_test",
                        "nonfunctional_test",
                        "acceptance_test",
                    ),
                )
                if menu[key]
            ]
            return {
                "pid": pid,
                "stage": "testing_in_progress",
                "allowed_routes": ["/plan", "/menu", *routes],
                "completed_operations": ["project_analysis", "ui_case"],
                "stale_operations": [],
                "menu": menu,
                "source_revision": "fixture-revision-4",
                "message": "离线夹具：六类测试可进入，两类未推荐。",
            }
        if pid == PLAN_FAILURE_PID and pid not in self._generated:
            return {
                "pid": pid,
                "stage": "analysis_required",
                "allowed_routes": ["/plan"],
                "completed_operations": [],
                "stale_operations": [],
                "menu": None,
                "source_revision": "fixture-revision-5",
                "message": "离线夹具：等待显式生成测试计划。",
            }
        if pid in self._generated:
            with self._lock:
                menu = dict(self._bundles[pid]["menu"])
            routes = [
                route
                for route, key in zip(
                    TEST_ROUTES,
                    (
                        "unit_test", "integration_test", "api_test", "ui_test",
                        "db_test", "functional_test", "nonfunctional_test",
                        "acceptance_test",
                    ),
                )
                if menu[key]
            ]
            return {
                "pid": pid,
                "stage": "analysis_ready",
                "allowed_routes": ["/plan", "/menu", *routes],
                "completed_operations": ["project_analysis"],
                "stale_operations": [],
                "menu": menu,
                "source_revision": f"fixture-generated-{pid[-1:]}",
                "message": "离线夹具：新计划已保存。",
            }
        return workflow_status_for(pid)

    def has_generated(self, pid: str) -> bool:
        with self._lock:
            return pid in self._generated

    def plan_events(
        self, pid: str, regenerate: bool
    ) -> list[tuple[str, dict[str, Any], int]]:
        with self._lock:
            should_fail = pid == PLAN_FAILURE_PID and not self._failure_used
            if should_fail:
                self._failure_used = True
        if should_fail:
            return plan_events_for(pid, regenerate)
        return successful_plan_events_for(pid, regenerate)

    def complete(self, pid: str, events: list[tuple[str, dict[str, Any], int]]) -> None:
        summary = "".join(
            str(data.get("text") or "") for name, data, _delay in events
            if name == "summary_delta"
        ).strip()
        plan = "".join(
            str(data.get("text") or "") for name, data, _delay in events
            if name == "answer_delta"
        ).strip()
        menu_event = next((data for name, data, _delay in events if name == "menu"), {})
        menu = menu_event.get("menu")
        if not summary or not plan or not isinstance(menu, dict):
            return
        with self._lock:
            self._bundles[pid] = {"summary": summary, "plan": plan, "menu": dict(menu)}
            self._generated.add(pid)


def workflow_status_for_request(
    pid: str,
    planning_state: PlanningFixtureState,
    onboarding_state: OnboardingFixtureState | None,
) -> dict[str, Any] | None:
    """Resolve fixed and process-local projects without persisting fixture state."""
    if pid in FIXTURE_IDS:
        return planning_state.workflow_status(pid)
    if onboarding_state is None or not onboarding_state.has_project(pid):
        return None
    if planning_state.has_generated(pid):
        return planning_state.workflow_status(pid)
    return {
        "pid": pid,
        "stage": "analysis_required",
        "allowed_routes": ["/plan"],
        "completed_operations": [],
        "stale_operations": [],
        "menu": None,
        "source_revision": "fixture-setup-revision",
        "message": "离线夹具：项目资料已确认，请显式生成测试计划。",
    }


def fixed_setup_status_for(pid: str) -> dict[str, Any]:
    documents = {
        "knowledge": ["fixture-knowledge.md"],
        "requirements": ["fixture-requirements.md"],
        "design": ["fixture-design.md"],
    }
    return {
        "pid": pid,
        "project_exists": True,
        "stage": "setup_complete",
        "document_counts": {group: 1 for group in SETUP_GROUPS},
        "document_files": documents,
        "allowed_actions": ["continue_to_plan"],
        "source_revision": "fixture-setup-revision",
        "message": "项目资料已确认",
    }


def persistence_for(operation: str) -> str:
    return "session" if operation in SESSION_ONLY_OPERATIONS else "artifact"


def _meta(operation: str) -> tuple[str, dict[str, Any], int]:
    return (
        "meta",
        {
            "request_id": f"fixture-{operation}",
            "label": "离线体验验证",
            "provider": "offline-fixture",
            "model": "fixed-response",
            "operation": operation,
            "persistence": persistence_for(operation),
            "artifact_key": operation,
            "source_revision": "fixture-revision-2",
            "prompt_version": "fixture-v1",
        },
        180,
    )


def _artifact(operation: str) -> tuple[str, dict[str, Any], int]:
    return (
        "artifact",
        {
            "artifact_key": operation,
            "source_revision": "fixture-revision-2",
            "prompt_version": "fixture-v1",
            "model_label": "离线固定响应",
            "status": "completed",
        },
        80,
    )


def _result_for(operation: str) -> Any:
    if operation == "unit_menu":
        return {
            "text_info": "离线夹具识别到一个可验证的模块单元。",
            "list_info": {
                "subsystem_menu": {"subsystem_test": False, "subsystem_list": []},
                "module_menu": {
                    "module_test": True,
                    "module_list": ["认证模块 ｜ fixture.auth ｜ offline-design.md"],
                },
                "class_menu": {"class_test": False, "class_list": []},
                "function_menu": {
                    "function_test": True,
                    "function_list": [
                        "创建 ｜ fixture.auth.create(request) ｜ auth-service.py",
                        "创建 ｜ fixture.billing.create(request) ｜ billing-service.py",
                    ],
                },
            },
        }
    if operation == "unit_info":
        return {
            "unit_info": "离线固定单元分析：验证输入、输出与异常分支。",
            "test_type": {"black_box": True, "white_box": True},
        }
    if operation == "unit_case":
        return {
            "unit_test_knowledge": "离线固定单元测试知识。",
            "unit_method_knowledge": "离线固定黑盒与白盒方法知识。",
            "test_cases": "UNIT-FIXTURE-001：验证 session-only 完成反馈。",
        }
    if operation == "integration_menu":
        return {
            "subsystem_integration_test": True,
            "subsystem_integration_menu": {
                "subsystem_test": True,
                "subsystem_list": ["认证子系统与计费子系统的身份同步链路"],
            },
            "module_integration_menu": {
                "module_test": True,
                "module_list": ["认证模块—会话模块"],
            },
            "class_integration_menu": {
                "class_test": True,
                "class_list": ["fixture.auth.AuthService 与 SessionRepository"],
            },
        }
    if operation == "integration_info":
        return "离线固定集成对象分析：验证调用顺序、数据边界和失败回滚。"
    if operation == "integration_case":
        return {
            "integration_test_knowledge": "离线固定集成测试知识。",
            "static_blackbox_knowledge": "离线固定静态黑盒知识。",
            "integration_strategy_knowledge": "离线固定集成策略知识。",
            "test_cases": "INTEGRATION-FIXTURE-001：验证 session-only 集成结果。",
        }
    if operation == "api_info":
        return {
            "apis_info": "离线固定 API 内容：POST /sessions 与 GET /sessions/{id}。",
            "list": {"api_list": ["POST /sessions", "GET /sessions/{id}"]},
        }
    if operation == "api_case":
        return {
            "api_test_knowledge": "离线固定 API 测试知识。",
            "test_cases": "API-FIXTURE-001：验证接口输入与错误信封。",
        }
    if operation == "ui_info":
        return "离线固定 UI 分析结果，不包含任何项目资料。"
    if operation == "ui_case":
        return {
            "ui_test_knowledge": "离线固定 UI 测试知识。",
            "test_cases": "UI-FIXTURE-001：验证响应式状态展示。",
        }
    if operation == "db_info":
        return "离线固定数据库设计：用户、会话与审计记录及其约束。"
    if operation == "db_case":
        return {
            "db_test_knowledge": "离线固定数据库测试知识。",
            "test_cases": "DB-FIXTURE-001：验证唯一约束与事务回滚。",
        }
    if operation == "functional_info":
        return {
            "text_info": "离线固定功能需求：用户登录、会话恢复和安全退出。",
            "list_info": {"use_case_list": ["用户登录", "恢复已有会话"]},
        }
    if operation == "functional_case":
        return {
            "functional_test_knowledge": "离线固定功能性测试知识。",
            "test_cases": "FUNCTIONAL-FIXTURE-001：验证登录主成功路径。",
        }
    if operation == "nonfunctional_info":
        return {
            "nonfunctional_info": "离线固定非功能需求：响应时间、可靠性与安全性。",
            "list": {"method_list": ["性能测试", "可靠性测试", "安全测试"]},
        }
    if operation == "nonfunctional_case":
        return {
            "nonfunctional_test_knowledge": "离线固定非功能测试知识。",
            "test_cases": "NONFUNCTIONAL-FIXTURE-001：验证响应时间阈值。",
        }
    if operation == "acceptance_info":
        return "离线固定验收需求：关键业务路径可完成且反馈清晰。"
    if operation == "acceptance_case":
        return {
            "acceptance_test_knowledge": "离线固定验收测试知识。",
            "test_cases": "ACCEPTANCE-FIXTURE-001：验证最终验收条件。",
        }
    return f"离线固定结果：{operation}。"


def sse_events_for(
    pid: str, operation: str, regenerate: bool
) -> list[tuple[str, dict[str, Any], int]]:
    """Build deterministic synthetic events without importing production code."""
    if pid not in FIXTURE_IDS:
        return [
            (
                "error",
                {
                    "code": "fixture_project_not_found",
                    "message": "离线夹具未配置此项目。",
                    "status": 404,
                    "retryable": False,
                },
                0,
            )
        ]

    if pid == PERSISTENCE_FAILURE_PID and operation == "ui_case" and regenerate:
        return [
            _meta(operation),
            (
                "progress",
                {
                    "stage": "fixture_persist",
                    "label": "正在验证离线保存失败回滚",
                    "current": 1,
                    "total": 2,
                    "percent": 50,
                },
                240,
            ),
            (
                "answer_delta",
                {"text": "离线未保存草稿：用于验证旧结果在保存失败后仍然可读。"},
                140,
            ),
            ("result", {"result": _result_for(operation)}, 100),
            (
                "error",
                {
                    "code": "fixture_persistence_error",
                    "message": "离线夹具模拟：保存失败，上一份有效结果仍保留。",
                    "status": 500,
                    "retryable": True,
                },
                0,
            ),
        ]

    if operation == "db_info" and pid != WORKSPACE_READY_PID:
        return [
            _meta(operation),
            (
                "progress",
                {
                    "stage": "fixture_validation",
                    "label": "正在验证固定错误状态",
                    "current": 1,
                    "total": 2,
                    "percent": 45,
                },
                600,
            ),
            (
                "error",
                {
                    "code": "fixture_structured_error",
                    "message": "离线夹具模拟：本次结果未保存，可以安全重试。",
                    "status": 422,
                    "retryable": True,
                },
                0,
            ),
        ]

    if operation == "acceptance_info" and pid != WORKSPACE_READY_PID:
        return [
            _meta(operation),
            (
                "progress",
                {
                    "stage": "fixture_waiting",
                    "label": "离线慢流正在等待取消",
                    "current": 1,
                    "total": 4,
                    "percent": 25,
                },
                10000,
            ),
            (
                "answer_delta",
                {"text": "这是一段用于验证取消反馈的固定占位文本。"},
                10000,
            ),
            (
                "progress",
                {
                    "stage": "fixture_waiting",
                    "label": "离线慢流继续处理",
                    "current": 3,
                    "total": 4,
                    "percent": 75,
                },
                10000,
            ),
            ("result", {"result": "离线验收分析固定结果。"}, 120),
            _artifact(operation),
            (
                "completed",
                {"saved": True, "from_cache": False, "ready": True},
                0,
            ),
        ]

    if operation == "ui_info":
        return [
            _meta(operation),
            (
                "progress",
                {
                    "stage": "fixture_prepare",
                    "label": "正在整理离线状态数据",
                    "current": 1,
                    "total": 4,
                    "percent": 15,
                },
                700,
            ),
            (
                "reasoning_delta",
                {
                    "stage": "fixture_status",
                    "label": "离线状态说明",
                    "text": "固定夹具正在检查信息层级与长文本换行。",
                },
                900,
            ),
            (
                "progress",
                {
                    "stage": "fixture_compose",
                    "label": "正在组织固定展示内容",
                    "current": 2,
                    "total": 4,
                    "percent": 55,
                },
                900,
            ),
            (
                "answer_delta",
                {
                    "text": (
                        "离线示例正文：页面应清楚区分进度、状态说明、正文、"
                        "Token 用量与保存结果，并在窄视口完整换行。"
                    )
                },
                800,
            ),
            (
                "usage",
                {
                    "input_tokens": 120,
                    "reasoning_tokens": 32,
                    "output_tokens": 88,
                    "total_tokens": 240,
                },
                180,
            ),
            (
                "result",
                {"result": "离线固定 UI 分析结果，不包含任何项目资料。"},
                120,
            ),
            _artifact(operation),
            (
                "progress",
                {
                    "stage": "fixture_complete",
                    "label": "离线固定结果已保存",
                    "current": 4,
                    "total": 4,
                    "percent": 100,
                },
                120,
            ),
            (
                "completed",
                {"saved": True, "from_cache": False, "ready": True},
                0,
            ),
        ]

    session_only = operation in SESSION_ONLY_OPERATIONS
    cached = not regenerate and not session_only
    result = _result_for(operation)
    events = [
        _meta(operation),
        (
            "progress",
            {
                "stage": "fixture_cached" if cached else "fixture_generate",
                "label": "正在读取离线固定结果" if cached else "正在生成离线固定结果",
                "current": 1,
                "total": 1,
                "percent": 100,
            },
            220,
        ),
        ("answer_delta", {"text": f"离线固定展示：{operation}。"}, 120),
        (
            "usage",
            {
                "input_tokens": None if cached else 80,
                "reasoning_tokens": None if cached else 20,
                "output_tokens": None if cached else 40,
                "total_tokens": None if cached else 140,
            },
            80,
        ),
        ("result", {"result": result}, 80),
    ]
    if not session_only:
        events.append(_artifact(operation))
    events.append(
        (
            "completed",
            {
                "saved": not session_only,
                "from_cache": cached,
                "ready": True,
            },
            0,
        )
    )
    return events


def successful_plan_events_for(
    pid: str, regenerate: bool
) -> list[tuple[str, dict[str, Any], int]]:
    cached = not regenerate and pid != ANALYSIS_REQUIRED_PID
    menu = _mixed_menu_state() if pid == MIXED_MENU_PID else _menu_state(True)
    return [
        _meta("project_analysis"),
        (
            "progress",
            {
                "stage": "fixture_plan",
                "label": "正在读取离线测试计划" if cached else "正在生成离线测试计划",
                "current": 1,
                "total": 2,
                "percent": 50,
            },
            260,
        ),
        ("summary_delta", {"text": "离线业务摘要：仅用于体验基线。"}, 100),
        ("answer_delta", {"text": "离线测试计划：覆盖固定的功能与状态验证。"}, 100),
        ("menu", {"menu": menu}, 100),
        ("result", {"result": {"summary": "离线业务摘要", "plan": "离线测试计划"}}, 80),
        _artifact("project_analysis"),
        (
            "completed",
            {"saved": True, "from_cache": cached, "ready": True},
            0,
        ),
    ]


def plan_events_for(pid: str, regenerate: bool) -> list[tuple[str, dict[str, Any], int]]:
    """Return a deterministic failure once selected by the planning state."""
    if pid != PLAN_FAILURE_PID:
        return successful_plan_events_for(pid, regenerate)
    return [
        _meta("project_analysis"),
        (
            "progress",
            {
                "stage": "fixture_plan",
                "label": "正在生成离线测试计划",
                "current": 1,
                "total": 2,
                "percent": 50,
            },
            260,
        ),
        ("summary_delta", {"text": "离线失败草稿摘要：已收到部分内容。"}, 100),
        ("answer_delta", {"text": "离线失败草稿计划：用于验证旧版保留与安全重试。"}, 100),
        (
            "error",
            {
                "code": "fixture_retryable_plan_failure",
                "message": "离线夹具模拟：计划生成失败，本次未保存。",
                "status": 503,
                "retryable": True,
            },
            0,
        ),
    ]


class FrontendFixtureServer(ThreadingHTTPServer):
    """Threading fixture server with browser-test-only response controls."""

    status_delay_ms = 0
    plan_delay_ms = 0
    allowed_origin = ALLOWED_ORIGIN
    onboarding_enabled = False
    onboarding_state: OnboardingFixtureState | None = None
    planning_state: PlanningFixtureState
    agent_state: AgentFixtureState


class FixtureRequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "EzFrontendFixture/1"

    def log_message(self, format: str, *args: Any) -> None:
        print(f"fixture {self.address_string()} {format % args}")

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", self.server.allowed_origin)
        self.send_header(
            "Access-Control-Allow-Headers", "Content-Type, Accept, Last-Event-ID"
        )
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def _json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        try:
            value = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    def _read_upload_body(self) -> bytes | None:
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
        except ValueError:
            return None
        if length <= 0 or length > MAX_FIXTURE_UPLOAD_BYTES:
            return None
        return self.rfile.read(length)

    @staticmethod
    def _multipart_filename(body: bytes) -> str:
        match = re.search(br'filename="([^"]+)"', body[:16384])
        if match is None:
            return ""
        return match.group(1).decode("utf-8", errors="replace")

    def _onboarding_state(self) -> OnboardingFixtureState | None:
        if not self.server.onboarding_enabled:
            return None
        return self.server.onboarding_state

    def _sse(
        self,
        events: list[tuple[str, dict[str, Any], int]],
        extra_delay_ms: int = 0,
    ) -> bool:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("Connection", "close")
        self.send_header("X-Accel-Buffering", "no")
        self._cors()
        self.end_headers()
        completed_delivered = False
        try:
            for event, data, delay_ms in events:
                block = (
                    f"event: {event}\n"
                    f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                ).encode("utf-8")
                self.wfile.write(block)
                self.wfile.flush()
                if event == "completed":
                    completed_delivered = True
                if delay_ms:
                    time.sleep(delay_ms / 1000)
                if extra_delay_ms and event != "completed":
                    time.sleep(extra_delay_ms / 1000)
        except (BrokenPipeError, ConnectionResetError, OSError):
            completed_delivered = False
        finally:
            self.close_connection = True
        return completed_delivered

    def _agent_sse(self, events: list[dict[str, Any]]) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("Connection", "close")
        self._cors()
        self.end_headers()
        try:
            for event in events:
                block = (
                    f"id: {event['sequence']}\n"
                    "event: agent_event\n"
                    f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                ).encode("utf-8")
                self.wfile.write(block)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            self.close_connection = True

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        parts = path.strip("/").split("/")
        if path == "/agent/v1/capabilities":
            self._json(
                {
                    "status": "success",
                    "reason": "offline Agent capabilities",
                    "data": self.server.agent_state.capabilities(),
                }
            )
            return
        if len(parts) >= 5 and parts[:3] == ["agent", "v1", "projects"] and parts[4] == "runs":
            pid = unquote(parts[3])
            if pid != AGENT_FIXTURE_PID:
                self._json(
                    {
                        "status": "agent_project_not_found",
                        "reason": "离线 Agent 夹具未配置该项目",
                        "data": None,
                    },
                    404,
                )
                return
            if len(parts) == 5:
                self._json(
                    {
                        "status": "success",
                        "reason": "offline Agent runs",
                        "data": self.server.agent_state.list_runs(),
                    }
                )
                return
            thread_id = unquote(parts[5])
            run = self.server.agent_state.get_run(thread_id)
            if run is None:
                self._json(
                    {
                        "status": "agent_thread_not_found_or_expired",
                        "reason": "离线 Agent thread 已失效",
                        "data": None,
                    },
                    404,
                )
                return
            if len(parts) == 6:
                self._json(
                    {"status": "success", "reason": "offline Agent run", "data": run}
                )
                return
            if len(parts) == 7 and parts[6] == "events":
                values = parse_qs(parsed.query).get("after_sequence", ["0"])
                try:
                    after_sequence = max(
                        0,
                        int(self.headers.get("Last-Event-ID") or values[-1]),
                    )
                except ValueError:
                    after_sequence = 0
                self._agent_sse(
                    self.server.agent_state.events(thread_id, after_sequence)
                )
                return
        if path == "/health":
            self._json({"status": 200, "reason": "offline fixture", "data": True})
            return
        if path.startswith("/project/login/"):
            pid = unquote(path.rsplit("/", 1)[-1])
            state = self._onboarding_state()
            onboarding_name = state.login(pid) if state else None
            known = pid in FIXTURE_IDS or onboarding_name is not None
            self._json(
                {
                    "status": 200 if known else 404,
                    "reason": "离线夹具项目已载入" if known else "离线夹具未配置此项目",
                    "data": onboarding_name or (f"离线体验项目 {pid[-1:]}" if known else False),
                }
            )
            return
        if path.startswith("/project/setup/status/"):
            pid = unquote(path.rsplit("/", 1)[-1])
            if pid in FIXTURE_IDS:
                status = fixed_setup_status_for(pid)
            else:
                state = self._onboarding_state()
                try:
                    status = state.status(pid) if state else None
                except KeyError:
                    status = None
            if status is None:
                self._json(
                    {"status": 404, "reason": "离线夹具未配置此项目", "data": False},
                    404,
                )
                return
            self._json({"status": 2001, "reason": "项目资料状态获取成功", "data": status})
            return
        if path.startswith("/project/info/"):
            parts = path.strip("/").split("/")
            try:
                pid = unquote(parts[2])
                info_type = int(parts[3])
            except (IndexError, ValueError):
                self._json(
                    {"status": 422, "reason": "离线夹具读取路径无效", "data": False},
                    422,
                )
                return
            value = self.server.planning_state.project_info(pid, info_type)
            if value is None:
                self._json(
                    {"status": 404, "reason": "离线夹具未保存此规划数据", "data": False},
                    404,
                )
                return
            self._json({"status": 200, "reason": "离线规划数据读取成功", "data": value})
            return
        if path.startswith("/project/workflow/status/"):
            pid = path.rsplit("/", 1)[-1]
            state = self._onboarding_state()
            status = workflow_status_for_request(
                pid, self.server.planning_state, state
            )
            if status is None:
                self._json(
                    {"status": 404, "reason": "离线夹具未配置此项目", "data": False}
                )
                return
            if self.server.status_delay_ms:
                time.sleep(self.server.status_delay_ms / 1000)
            self._json({"status": 200, "reason": "离线工作流状态", "data": status})
            return
        self._json({"status": 404, "reason": "离线夹具未提供该读取路径", "data": False}, 404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        parts = path.strip("/").split("/")
        if len(parts) >= 5 and parts[:3] == ["agent", "v1", "projects"] and parts[4] == "runs":
            pid = unquote(parts[3])
            body = self._read_json()
            if pid != AGENT_FIXTURE_PID:
                self._json(
                    {"status": "agent_project_not_found", "reason": "离线 Agent 夹具未配置该项目", "data": None},
                    404,
                )
                return
            if len(parts) == 5:
                created = self.server.agent_state.create(str(body.get("goal") or "").strip())
                if created is None:
                    self._json(
                        {"status": "agent_run_conflict", "reason": "当前项目已有活跃运行", "data": None},
                        409,
                    )
                    return
                self._json({"status": "success", "reason": "offline Agent run queued", "data": created}, 201)
                return
            thread_id = unquote(parts[5])
            action = parts[6] if len(parts) == 7 else ""
            if action == "approval":
                result = self.server.agent_state.decide(
                    thread_id,
                    str(body.get("decision") or ""),
                    str(body.get("expected_plan_hash") or ""),
                )
            elif action == "edit":
                result = self.server.agent_state.edit(
                    thread_id,
                    str(body.get("goal") or ""),
                    str(body.get("expected_plan_hash") or ""),
                )
            elif action == "cancel":
                result = self.server.agent_state.cancel(thread_id)
                if result is not None:
                    result = self.server.agent_state.get_run(thread_id)
            elif action == "recover":
                result = self.server.agent_state.recover(thread_id)
            else:
                result = None
            if result is None:
                self._json(
                    {"status": "agent_control_conflict", "reason": "离线 Agent 控制请求已失效", "data": None},
                    409,
                )
                return
            self._json({"status": "success", "reason": "offline Agent control accepted", "data": result})
            return
        state = self._onboarding_state()
        if path.startswith("/project/add/"):
            if state is None:
                self._json(
                    {"status": 405, "reason": "离线夹具拒绝生产型写入路径", "data": False},
                    405,
                )
                return
            name = unquote(path[len("/project/add/") :]).strip()
            if not name:
                self._json({"status": 422, "reason": "项目名称不能为空", "data": False}, 422)
                return
            pid = state.create_project(name)
            self._json({"status": 2001, "reason": "成功生成并保存项目 ID", "data": pid})
            return
        if path.startswith("/uploadFile/"):
            if state is None:
                self._json(
                    {"status": 405, "reason": "离线夹具拒绝生产型写入路径", "data": False},
                    405,
                )
                return
            parts = path.strip("/").split("/")
            try:
                pid = unquote(parts[1])
                doctype = int(parts[2])
                group = DOCTYPE_GROUPS[doctype]
            except (IndexError, KeyError, ValueError):
                self._json({"status": 422, "reason": "无效的上传路径", "data": False}, 422)
                return
            upload_body = self._read_upload_body()
            if upload_body is None:
                self._json(
                    {"status": 413, "reason": "离线夹具只接受 1MB 内的合成文件", "data": False},
                    413,
                )
                return
            filename = self._multipart_filename(upload_body)
            try:
                uploaded = state.upload(pid, group, filename)
            except (KeyError, ValueError):
                self._json({"status": 422, "reason": "离线夹具上传参数无效", "data": False}, 422)
                return
            if not uploaded:
                self._json(
                    {"status": 503, "reason": f"离线夹具模拟：{group} 上传失败一次", "data": False},
                    503,
                )
                return
            self._json({"status": 2001, "reason": "上传文档成功", "data": True})
            return
        if path.startswith("/project/setup/finalize/"):
            if state is None:
                self._json(
                    {"status": 405, "reason": "离线夹具拒绝生产型写入路径", "data": False},
                    405,
                )
                return
            pid = unquote(path.rsplit("/", 1)[-1])
            try:
                status = state.finalize(pid)
            except KeyError:
                self._json({"status": 404, "reason": "项目不存在", "data": False}, 404)
                return
            except ValueError as caught:
                status = state.status(pid)
                self._json({"status": 422, "reason": str(caught), "data": status}, 422)
                return
            self._json({"status": 2001, "reason": "项目资料确认成功", "data": status})
            return

        body = self._read_json()
        pid = str(body.get("pid") or "")
        regenerate = body.get("regenerate") is True
        if path == "/project/llm/plan/stream":
            events = self.server.planning_state.plan_events(pid, regenerate)
            completed_delivered = self._sse(events, self.server.plan_delay_ms)
            if completed_delivered:
                self.server.planning_state.complete(pid, events)
            return
        if path == "/project/llm/workflow/stream":
            operation = str(body.get("operation") or "")
            self._sse(sse_events_for(pid, operation, regenerate))
            return
        self._json(
            {"status": 405, "reason": "离线夹具拒绝生产型写入路径", "data": False},
            405,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the loopback frontend fixture.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--origin-port", type=int, default=DEFAULT_ORIGIN_PORT)
    parser.add_argument("--status-delay-ms", type=int, default=0)
    parser.add_argument("--plan-delay-ms", type=int, default=0)
    parser.add_argument(
        "--enable-onboarding",
        action="store_true",
        help="Enable process-local synthetic project setup writes.",
    )
    parser.add_argument(
        "--fail-upload-once",
        choices=SETUP_GROUPS,
        default=None,
        help="After one success, fail the next upload in this group once.",
    )
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    if not 0 <= args.status_delay_ms <= MAX_STATUS_DELAY_MS:
        parser.error(
            f"status delay must be between 0 and {MAX_STATUS_DELAY_MS} milliseconds"
        )
    if not 0 <= args.plan_delay_ms <= MAX_PLAN_DELAY_MS:
        parser.error(
            f"plan delay must be between 0 and {MAX_PLAN_DELAY_MS} milliseconds"
        )
    try:
        allowed_origin = allowed_origin_for(args.origin_port)
    except ValueError as caught:
        parser.error(str(caught))

    server = FrontendFixtureServer((FIXTURE_HOST, args.port), FixtureRequestHandler)
    server.status_delay_ms = args.status_delay_ms
    server.plan_delay_ms = args.plan_delay_ms
    server.allowed_origin = allowed_origin
    server.onboarding_enabled = args.enable_onboarding
    server.onboarding_state = (
        OnboardingFixtureState(args.fail_upload_once)
        if args.enable_onboarding
        else None
    )
    server.planning_state = PlanningFixtureState()
    server.agent_state = AgentFixtureState()
    print(f"Offline frontend fixture listening on http://{FIXTURE_HOST}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
