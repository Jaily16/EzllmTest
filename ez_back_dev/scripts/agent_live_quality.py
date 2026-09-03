"""Explicitly gated live-model quality check for the Iteration 4 Agent.

The check uses only versioned synthetic inputs.  It never prints prompts, model
content, document content, credentials, project identifiers, or provider error
details.  Unlike the offline acceptance suite, this command makes billable
external calls and therefore requires ``--confirm-cost``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from infrastructure.config import get_settings
from infrastructure.llm.gateway import (
    LLMError,
    SUPPORTED_MODEL_LABEL,
    get_lazy_embeddings,
)
from infrastructure.llm.stream import ModelStreamEvent, TokenUsage, stream_chat_completion
from service.agent.contracts import TrustedProjectScope
from service.agent.planner import (
    PLANNER_RESPONSE_FORMAT,
    ProviderAgentPlanner,
    build_planner_provider_prompt,
)
from service.retrieval.agent import use_agent_retrieval
from service.agent.runtime_contracts import ProjectObservation
from service.retrieval.index import _reset_index_registry_for_tests
from service.retrieval.factory import RetrievalPolicy, get_project_retriever


LIVE_SCHEMA_VERSION = 1
LIVE_SUITE_VERSION = "iteration4-live-quality-v1"
MAX_CHAT_CALLS = 6
MAX_EMBEDDING_CALLS = 4
PLANNER_MAX_OUTPUT_TOKENS = 4_096


@dataclass(frozen=True)
class PlannerCase:
    case_id: str
    goal: str
    expected_tool: str
    require_regenerate: bool = False


@dataclass(frozen=True)
class RagCase:
    case_id: str
    query: str
    expected_source: str


PLANNER_CASES = (
    PlannerCase(
        "project-analysis",
        "请为这个刚完成资料上传的测试项目生成项目分析。",
        "workflow_project_analysis",
    ),
    PlannerCase(
        "api-analysis",
        "项目分析已完成，请分析项目中可测试的 API 接口。",
        "workflow_api_info",
    ),
    PlannerCase(
        "ui-case",
        "UI 分析已存在，请生成前端 UI 测试用例。",
        "workflow_ui_case",
    ),
    PlannerCase(
        "functional-case",
        "功能分析已存在，请生成完整功能测试用例，test_type 使用 0，output_type 使用 0。",
        "workflow_functional_case",
    ),
    PlannerCase(
        "nonfunctional-case",
        "非功能分析已存在，请使用边界值法生成非功能测试用例。",
        "workflow_nonfunctional_case",
    ),
    PlannerCase(
        "ui-regenerate",
        "请重新生成已经存在的前端 UI 测试用例。",
        "workflow_ui_case",
        require_regenerate=True,
    ),
)


RAG_DOCUMENTS = (
    Document(
        page_content="退款申请在交易完成七天内自动批准，超过七天必须由财务人员人工复核。",
        metadata={"source": "refund-policy.md", "page": 0},
    ),
    Document(
        page_content="POST /payments/{id}/confirm 使用 Idempotency-Key 确保支付确认接口幂等。",
        metadata={"source": "payment-api.md", "page": 0},
    ),
    Document(
        page_content="通知服务采用指数退避重试，最大三次，随后进入死信队列。",
        metadata={"source": "reliability.md", "page": 0},
    ),
    Document(
        page_content="库存预占在十五分钟后释放，并通过 reservation_id 追踪。",
        metadata={"source": "inventory.md", "page": 0},
    ),
)


RAG_CASES = (
    RagCase("refund-policy", "超过七天的退款申请由谁审核？", "refund-policy.md"),
    RagCase(
        "payment-idempotency",
        "哪个接口使用 Idempotency-Key 保证支付确认幂等？",
        "payment-api.md",
    ),
    RagCase(
        "notification-retry",
        "通知失败后采用什么重试策略？",
        "reliability.md",
    ),
)


def _usage_dict(usage: TokenUsage | None) -> dict[str, int | None]:
    if usage is None:
        return {
            "input_tokens": None,
            "reasoning_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
        }
    return usage.as_dict()


class LivePlannerProvider:
    """Runtime-equivalent provider edge with usage-only evidence."""

    def __init__(self) -> None:
        self.usages: list[TokenUsage | None] = []

    async def __call__(self, request: dict[str, Any]) -> dict[str, Any]:
        if len(self.usages) >= MAX_CHAT_CALLS:
            raise RuntimeError("live_chat_call_budget_exhausted")
        prompt = build_planner_provider_prompt(request)
        content: list[str] = []
        usage: TokenUsage | None = None
        try:
            async for event in stream_chat_completion(
                SUPPORTED_MODEL_LABEL,
                prompt,
                PLANNER_MAX_OUTPUT_TOKENS,
                request_options={
                    "max_tokens": PLANNER_MAX_OUTPUT_TOKENS,
                    "temperature": 0,
                    "extra_body": {"thinking": {"type": "disabled"}},
                    "response_format": PLANNER_RESPONSE_FORMAT,
                },
            ):
                if not isinstance(event, ModelStreamEvent):
                    continue
                if event.kind == "content":
                    content.append(event.text)
                elif event.kind == "usage":
                    usage = event.usage
        finally:
            self.usages.append(usage)
        try:
            value = json.loads("".join(content))
        except json.JSONDecodeError as exc:
            raise ValueError("planner_invalid_json") from exc
        if not isinstance(value, dict):
            raise ValueError("planner_invalid_object")
        return value


class CountingEmbeddings(Embeddings):
    """Enforce and report the fixed live embedding call budget."""

    def __init__(self, delegate: Embeddings) -> None:
        self.delegate = delegate
        self.calls = 0

    @property
    def model_name(self) -> str:
        value = getattr(self.delegate, "model_name", None)
        return value if isinstance(value, str) and value else "embedding-3"

    def _reserve(self) -> None:
        if self.calls >= MAX_EMBEDDING_CALLS:
            raise RuntimeError("live_embedding_call_budget_exhausted")
        self.calls += 1

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self._reserve()
        return self.delegate.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        self._reserve()
        return self.delegate.embed_query(text)


def _observation() -> ProjectObservation:
    return ProjectObservation(
        setup_stage="complete",
        analysis_ready=True,
        workflow_stage="ready",
        completed_operations=(
            "project_analysis",
            "api_info",
            "ui_info",
            "functional_info",
            "nonfunctional_info",
            "ui_case",
        ),
        stale_operations=(),
        source_revision="synthetic-revision-v1",
    )


async def _planner_quality() -> dict[str, Any]:
    provider = LivePlannerProvider()
    planner = ProviderAgentPlanner(provider)
    case_results: list[dict[str, Any]] = []
    for case in PLANNER_CASES:
        started = time.perf_counter()
        status = "failed"
        actual_tool: str | None = None
        structured_valid = False
        regenerate_valid = False
        error_code: str | None = None
        try:
            proposal = await planner.plan(
                goal=case.goal,
                observation=_observation(),
                max_steps=1,
            )
            structured_valid = True
            step = proposal.steps[0]
            actual_tool = step.tool_name
            regenerate_valid = (
                not case.require_regenerate
                or step.arguments.get("regenerate") is True
            )
            if actual_tool == case.expected_tool and regenerate_valid:
                status = "passed"
            else:
                error_code = "quality_expectation_mismatch"
        except LLMError:
            error_code = "provider_call_failed"
        except (TypeError, ValueError):
            error_code = "structured_output_invalid"
        except Exception:
            error_code = "planner_internal_error"
        usage = provider.usages[-1] if provider.usages else None
        case_results.append(
            {
                "case_id": case.case_id,
                "status": status,
                "expected_tool": case.expected_tool,
                "actual_tool": actual_tool,
                "structured_output_valid": structured_valid,
                "regenerate_valid": regenerate_valid,
                "latency_ms": round((time.perf_counter() - started) * 1_000, 3),
                "usage": _usage_dict(usage),
                "error_code": error_code,
            }
        )
    numeric_usage = [usage for usage in provider.usages if usage is not None]
    return {
        "calls": len(provider.usages),
        "passed": sum(item["status"] == "passed" for item in case_results),
        "structured_valid": sum(
            item["structured_output_valid"] for item in case_results
        ),
        "input_tokens": sum(item.input_tokens or 0 for item in numeric_usage),
        "reasoning_tokens": sum(item.reasoning_tokens or 0 for item in numeric_usage),
        "output_tokens": sum(item.output_tokens or 0 for item in numeric_usage),
        "total_tokens": sum(item.total_tokens or 0 for item in numeric_usage),
        "completion_tokens_observed": sum(
            max((item.total_tokens or 0) - (item.input_tokens or 0), 0)
            for item in numeric_usage
            if item.total_tokens is not None and item.input_tokens is not None
        ),
        "cases": case_results,
    }


async def _rag_quality() -> dict[str, Any]:
    _reset_index_registry_for_tests()
    scope = TrustedProjectScope(
        project_id="iteration4-live-synthetic-project",
        actor_id="live-quality-gate",
        scope_version=LIVE_SUITE_VERSION,
    )
    embeddings = CountingEmbeddings(get_lazy_embeddings())
    cases: list[dict[str, Any]] = []
    with use_agent_retrieval(scope, strategy="dense_v1") as session:
        for case in RAG_CASES:
            started = time.perf_counter()
            status = "failed"
            actual_source: str | None = None
            error_code: str | None = None
            try:
                retriever = await get_project_retriever(
                    scope.project_id,
                    "knowledge",
                    "synthetic-revision-v1",
                    RAG_DOCUMENTS,
                    embedding_model=embeddings,
                    policy=RetrievalPolicy(1, 4, 6_000, -1.0),
                )
                selected = await asyncio.to_thread(retriever.invoke, case.query)
                if selected:
                    raw_source = selected[0].metadata.get("source")
                    if isinstance(raw_source, str):
                        actual_source = Path(raw_source).name
                if actual_source == case.expected_source:
                    status = "passed"
                else:
                    error_code = "retrieval_expectation_mismatch"
            except LLMError:
                error_code = "embedding_call_failed"
            except Exception:
                error_code = "retrieval_internal_error"
            cases.append(
                {
                    "case_id": case.case_id,
                    "status": status,
                    "expected_source": case.expected_source,
                    "actual_source": actual_source,
                    "latency_ms": round(
                        (time.perf_counter() - started) * 1_000, 3
                    ),
                    "error_code": error_code,
                }
            )
        evidence = session.snapshot()
    index_builds = evidence.index_builds if evidence is not None else 0
    index_reuses = evidence.index_reuses if evidence is not None else 0
    citation_count = (
        sum(len(query.citations) for query in evidence.queries)
        if evidence is not None
        else 0
    )
    context_tokens = evidence.context_tokens if evidence is not None else 0
    return {
        "embedding_calls": embeddings.calls,
        "queries": len(cases),
        "passed": sum(item["status"] == "passed" for item in cases),
        "top1_accuracy": round(
            sum(item["status"] == "passed" for item in cases) / len(cases), 6
        ),
        "citation_coverage": round(citation_count / len(cases), 6),
        "index_builds": index_builds,
        "index_reuses": index_reuses,
        "context_tokens": context_tokens,
        "cases": cases,
    }


def _safe_number(value: Any) -> bool:
    return not isinstance(value, float) or math.isfinite(value)


def validate_safe_report(value: Any, *, path: str = "report") -> None:
    forbidden_keys = {
        "credential",
        "document_content",
        "goal",
        "project_id",
        "prompt",
        "reasoning",
        "response_content",
        "traceback",
    }
    if isinstance(value, dict):
        for key, nested in value.items():
            if key.lower() in forbidden_keys:
                raise ValueError(f"unsafe_live_report_field:{path}.{key}")
            validate_safe_report(nested, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            validate_safe_report(nested, path=f"{path}[{index}]")
    elif not _safe_number(value):
        raise ValueError(f"unsafe_live_report_number:{path}")


async def run_live_quality() -> dict[str, Any]:
    settings = get_settings()
    if not settings.zhipu_api_key:
        raise RuntimeError("zhipu_credentials_not_configured")
    planner = await _planner_quality()
    rag = await _rag_quality()
    report = {
        "schema_version": LIVE_SCHEMA_VERSION,
        "suite_version": LIVE_SUITE_VERSION,
        "provider": "zhipu",
        "chat_model": settings.zhipu_chat_model,
        "embedding_model": settings.zhipu_embedding_model,
        "scope": "versioned_synthetic_only",
        "limits": {
            "max_chat_calls": MAX_CHAT_CALLS,
            "max_embedding_calls": MAX_EMBEDDING_CALLS,
            "max_output_tokens_per_chat_call": PLANNER_MAX_OUTPUT_TOKENS,
        },
        "planner": planner,
        "rag": rag,
        "safety": {
            "real_project_reads": 0,
            "mysql_calls": 0,
            "tool_side_effects": 0,
            "stored_model_content": 0,
            "stored_reasoning": 0,
            "credential_exposure": 0,
        },
        "gate": {
            "planner_pass": planner["passed"] == len(PLANNER_CASES),
            "structured_output_pass": planner["structured_valid"]
            == len(PLANNER_CASES),
            "rag_pass": rag["passed"] == len(RAG_CASES),
            "citation_pass": rag["citation_coverage"] == 1.0,
            "index_reuse_pass": rag["index_builds"] == 1
            and rag["index_reuses"] == len(RAG_CASES) - 1,
        },
    }
    report["gate"]["passed"] = all(report["gate"].values())
    validate_safe_report(report)
    return report


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the fixed paid live-model Agent quality gate."
    )
    parser.add_argument(
        "--confirm-cost",
        action="store_true",
        help="Confirm up to 6 chat and 4 embedding API calls",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if not args.confirm_cost:
        raise SystemExit(
            "Paid live Agent quality calls are not confirmed. Re-run with "
            "--confirm-cost after checking provider balance."
        )
    try:
        report = asyncio.run(run_live_quality())
    except Exception:
        print(
            json.dumps(
                {
                    "schema_version": LIVE_SCHEMA_VERSION,
                    "suite_version": LIVE_SUITE_VERSION,
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
        print(
            f"Planner: {report['planner']['passed']}/{len(PLANNER_CASES)}; "
            f"RAG: {report['rag']['passed']}/{len(RAG_CASES)}; "
            f"gate={'PASS' if report['gate']['passed'] else 'FAIL'}"
        )
    return 0 if report["gate"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
