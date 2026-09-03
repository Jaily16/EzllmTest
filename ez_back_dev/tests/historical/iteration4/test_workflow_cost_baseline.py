from __future__ import annotations

import asyncio
import json
import os
import socket
from dataclasses import dataclass, field, replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings


os.environ["PYTHON_DOTENV_DISABLED"] = "1"
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
for provider_key in (
    "ZHIPU_API_KEY",
    "DASHSCOPE_API_KEY",
    "DEEPSEEK_API_KEY",
    "MOONSHOT_API_KEY",
):
    os.environ[provider_key] = ""

from dao import testProjectDao
from dao.workflowArtifactDao import WorkflowArtifactRecord
from llm import provider
from llm import streaming as llm_streaming
from llm.streaming import ModelStreamEvent, TokenUsage
from service import llmTestPlanStreamService as plan_stream
from service import llmWorkflowAnalysisStreamService as workflow_analysis
from service import workflowArtifactService as workflow_artifacts
from service import llmWorkflowStreamCore as workflow_core
from service import llmWorkflowStreamService as workflow_stream
from service.projectRevisionService import artifact_input_hash
from service.workflowArtifactService import (
    WorkflowArtifactKey,
    WorkflowArtifactLookup,
    WorkflowArtifactSnapshot,
)
from service.workflowCatalog import get_workflow_definition, list_workflow_definitions
from service.workflowBudget import profile_for
from tools import documentTools
from tools.InfoType import InfoType
from vectorstore import indexRegistry, retrievers
from repo_paths import canonical_document_path


SMALL_TEXT = (
    "synthetic module interface requirement design test behavior.\n" * 40
).strip()
LARGE_TEXT = (
    "synthetic module interface requirement design test behavior.\n" * 1_900
).strip()


@dataclass(frozen=True)
class DocumentProfile:
    name: str
    text: str
    overflow: int


PROFILES = (
    DocumentProfile("small", SMALL_TEXT, 0),
    DocumentProfile("large", LARGE_TEXT, 4),
)

# Current Task 7 measurement. Each nested tuple is
# (chat calls, embedding builds, input-context tokens, summed output cap).
EXPECTED_BASELINE = {
    ("small", "project_analysis"): ((2, 0, 1633, 10240), (0, 0, 0, 0)),
    ("small", "unit_menu"): ((2, 0, 2157, 20480), (0, 0, 0, 0)),
    ("small", "unit_info"): ((2, 1, 964, 9728), (0, 0, 0, 0)),
    ("small", "unit_case"): ((3, 1, 1356, 15360), (3, 0, 1356, 15360)),
    ("small", "integration_menu"): ((2, 0, 1997, 9728), (0, 0, 0, 0)),
    ("small", "integration_info"): ((1, 1, 707, 8192), (0, 0, 0, 0)),
    ("small", "integration_case"): ((4, 1, 1988, 16896), (4, 0, 1988, 16896)),
    ("small", "api_info"): ((2, 0, 729, 9728), (0, 0, 0, 0)),
    ("small", "api_case"): ((3, 2, 1481, 15360), (3, 0, 1481, 15360)),
    ("small", "ui_info"): ((1, 0, 485, 8192), (0, 0, 0, 0)),
    ("small", "ui_case"): ((2, 1, 776, 13824), (0, 0, 0, 0)),
    ("small", "db_info"): ((1, 0, 486, 8192), (0, 0, 0, 0)),
    ("small", "db_case"): ((2, 1, 777, 13824), (0, 0, 0, 0)),
    ("small", "functional_info"): ((2, 0, 667, 9728), (0, 0, 0, 0)),
    ("small", "functional_case"): ((3, 2, 1304, 15360), (3, 0, 1304, 15360)),
    ("small", "nonfunctional_info"): ((2, 1, 895, 9728), (0, 0, 0, 0)),
    ("small", "nonfunctional_case"): ((2, 1, 609, 13824), (2, 0, 609, 13824)),
    ("small", "acceptance_info"): ((1, 0, 758, 8192), (0, 0, 0, 0)),
    ("small", "acceptance_case"): ((2, 1, 639, 13824), (0, 0, 0, 0)),
    ("large", "project_analysis"): ((2, 0, 35113, 10240), (0, 0, 0, 0)),
    ("large", "unit_menu"): ((2, 0, 18897, 20480), (0, 0, 0, 0)),
    ("large", "unit_info"): ((2, 1, 1923, 9728), (0, 0, 0, 0)),
    ("large", "unit_case"): ((3, 1, 10818, 15360), (3, 0, 10818, 15360)),
    ("large", "integration_menu"): ((2, 0, 18737, 9728), (0, 0, 0, 0)),
    ("large", "integration_info"): ((1, 1, 1666, 8192), (0, 0, 0, 0)),
    ("large", "integration_case"): ((4, 1, 16181, 16896), (4, 0, 16181, 16896)),
    ("large", "api_info"): ((2, 0, 17469, 9728), (0, 0, 0, 0)),
    ("large", "api_case"): ((3, 2, 7183, 15360), (3, 0, 7183, 15360)),
    ("large", "ui_info"): ((1, 0, 17225, 8192), (0, 0, 0, 0)),
    ("large", "ui_case"): ((2, 1, 5507, 13824), (0, 0, 0, 0)),
    ("large", "db_info"): ((1, 0, 17226, 8192), (0, 0, 0, 0)),
    ("large", "db_case"): ((2, 1, 5508, 13824), (0, 0, 0, 0)),
    ("large", "functional_info"): ((2, 0, 17407, 9728), (0, 0, 0, 0)),
    ("large", "functional_case"): ((3, 2, 6830, 15360), (3, 0, 6830, 15360)),
    ("large", "nonfunctional_info"): ((2, 1, 1690, 9728), (0, 0, 0, 0)),
    ("large", "nonfunctional_case"): ((2, 1, 5340, 13824), (2, 0, 5340, 13824)),
    ("large", "acceptance_info"): ((1, 0, 17498, 8192), (0, 0, 0, 0)),
    ("large", "acceptance_case"): ((2, 1, 5370, 13824), (0, 0, 0, 0)),
}

TASK0_PROJECT_ANALYSIS_BASELINE = {
    "small": (3, 0, 2560, 73728),
    "large": (9, 0, 60399, 122880),
}
TASK6_ISOLATED_TOTALS = {
    "small": {"input_tokens": 20_106, "output_cap": 1_105_920},
    "large": {"input_tokens": 260_009, "output_cap": 1_343_488},
}
QUALIFIED_REFERENCE_INPUT_OVERHEAD = 400
TASK0_GENERIC_REPEAT_TOTALS = {
    "small": {"chat_calls": 19, "embedding_builds": 5},
    "large": {"chat_calls": 19, "embedding_builds": 5},
}


WORKFLOW_PAYLOADS: dict[str, dict[str, Any]] = {
    "unit_menu": {},
    "unit_info": {"unit": "synthetic-unit"},
    "unit_case": {
        "method_type": 1,
        "static_method": "synthetic-blackbox",
        "unit": "synthetic-unit",
        "unit_info": "synthetic-unit-info",
        "output_type": 0,
    },
    "integration_menu": {},
    "integration_info": {
        "integration_type": 2,
        "name": "synthetic-module",
    },
    "integration_case": {
        "strategy_type": 0,
        "strategy": "synthetic-strategy",
        "integration_object": "synthetic-module",
        "integration_object_info": "synthetic-integration-info",
        "output_type": 0,
    },
    "api_info": {},
    "api_case": {
        "info": "synthetic-api-summary",
        "test_type": 1,
        "output_type": 0,
        "api_name": "synthetic-api",
    },
    "ui_info": {},
    "ui_case": {"info": "synthetic-ui-info"},
    "db_info": {},
    "db_case": {"info": "synthetic-database-info"},
    "functional_info": {},
    "functional_case": {
        "info": "synthetic-use-case-summary",
        "test_type": 1,
        "output_type": 0,
        "use_case_name": "synthetic-use-case",
    },
    "nonfunctional_info": {},
    "nonfunctional_case": {
        "info": "synthetic-nonfunctional-info",
        "method_name": "synthetic-performance-test",
    },
    "acceptance_info": {},
    "acceptance_case": {"info": "synthetic-acceptance-info"},
}


@dataclass(frozen=True)
class CostSnapshot:
    chat_calls: int
    embedding_builds: int
    input_context_tokens: int
    output_token_cap: int
    call_output_caps: tuple[int, ...]
    call_input_tokens: tuple[int, ...]
    mechanical_high_reasoning_calls: int
    selected_context_tokens: int


@dataclass
class MutableCost:
    chat_calls: int = 0
    embedding_builds: int = 0
    input_context_tokens: int = 0
    call_output_caps: list[int] = field(default_factory=list)
    call_input_tokens: list[int] = field(default_factory=list)
    mechanical_high_reasoning_calls: int = 0
    max_context_tokens: int = 0
    selected_context_tokens: int = 0

    def freeze(self) -> CostSnapshot:
        return CostSnapshot(
            chat_calls=self.chat_calls,
            embedding_builds=self.embedding_builds,
            input_context_tokens=self.input_context_tokens,
            output_token_cap=sum(self.call_output_caps),
            call_output_caps=tuple(self.call_output_caps),
            call_input_tokens=tuple(self.call_input_tokens),
            mechanical_high_reasoning_calls=self.mechanical_high_reasoning_calls,
            selected_context_tokens=self.selected_context_tokens,
        )


class CostRecorder:
    def __init__(self) -> None:
        self.current = MutableCost()

    def reset(self) -> None:
        self.current = MutableCost()

    def snapshot(self) -> CostSnapshot:
        return self.current.freeze()


_ACTIVE_RECORDER: CostRecorder | None = None


def _install_retrieval_counter(monkeypatch: pytest.MonkeyPatch) -> None:
    original_invoke = retrievers.BoundedRetriever.invoke

    def measured_invoke(self, query: str, config=None, **kwargs):
        result = original_invoke(self, query, config=config, **kwargs)
        if _ACTIVE_RECORDER is not None:
            _ACTIVE_RECORDER.current.selected_context_tokens += (
                self.last_context_tokens
            )
        return result

    monkeypatch.setattr(
        retrievers.BoundedRetriever, "invoke", measured_invoke
    )


class CountingEmbeddings(Embeddings):
    def __init__(self, recorder: CostRecorder) -> None:
        self._recorder = recorder

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self._recorder.current.embedding_builds += 1
        return [[1.0, 0.0, 0.0] for _text in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0]


class OfflineProjectState:
    def __init__(self, overflow: int) -> None:
        self.overflow = overflow
        self.info: dict[int, str] = {}
        self.analysis_artifact: WorkflowArtifactRecord | None = None
        self.workflow_artifacts: dict[
            tuple[str, str, str, str, str], WorkflowArtifactSnapshot
        ] = {}

    def get_info(self, _pid: str, info_type: int) -> str | bool:
        return self.info.get(info_type, False)

    def save_values(self, _pid: str, values: dict[int, str]) -> bool:
        self.info.update(values)
        return True

    def save_analysis_bundle(
        self,
        _pid: str,
        summary: str,
        plan: str,
        menu_json: str,
    ) -> bool:
        self.info.update(
            {
                InfoType.PROJECT_INITIAL_SUMMARY.value: summary,
                InfoType.PROJECT_TEST_PLAN.value: plan,
                InfoType.PROJECT_TEST_MENU.value: menu_json,
            }
        )
        return True

    def get_analysis_artifact(self, *_args) -> WorkflowArtifactRecord | None:
        return self.analysis_artifact

    def save_analysis_artifact_bundle(
        self,
        pid: str,
        summary: str,
        plan: str,
        menu_json: str,
        **artifact,
    ) -> bool:
        self.save_analysis_bundle(pid, summary, plan, menu_json)
        self.analysis_artifact = WorkflowArtifactRecord(
            project_id=pid,
            artifact_key=artifact["artifact_key"],
            input_hash=artifact["input_hash"],
            source_revision=artifact["source_revision"],
            prompt_version=artifact["prompt_version"],
            model_label=artifact["model_label"],
            content=artifact["artifact_content"],
            metadata=json.loads(artifact["metadata_json"]),
        )
        return True

    def lookup_workflow_artifact(
        self,
        _pid: str,
        definition,
        payload: dict[str, Any],
        model_label: str,
    ) -> WorkflowArtifactLookup:
        key = WorkflowArtifactKey(
            operation=definition.operation,
            input_hash=artifact_input_hash(definition.operation, payload),
            source_revision="offline-revision",
            prompt_version=definition.prompt_version,
            model_label=model_label,
        )
        identity = (
            definition.result_artifact,
            key.input_hash,
            key.source_revision,
            key.prompt_version,
            key.model_label,
        )
        return WorkflowArtifactLookup(
            key=key,
            artifact=self.workflow_artifacts.get(identity),
            stale=False,
        )

    def save_workflow_artifact(
        self,
        _pid: str,
        definition,
        key: WorkflowArtifactKey,
        payload: dict[str, Any],
        result: Any,
        pending_info: dict[int, str],
        *,
        call_count: int,
    ) -> bool:
        del call_count
        self.info.update(pending_info)
        identity = (
            definition.result_artifact,
            key.input_hash,
            key.source_revision,
            key.prompt_version,
            key.model_label,
        )
        self.workflow_artifacts[identity] = WorkflowArtifactSnapshot(
            key=key,
            result=result,
            selection={
                field: payload[field]
                for field in definition.selection_fields
                if field in payload
            },
        )
        return True


def _structured_response(prompt_text: str) -> str:
    if "[PROJECT_ANALYSIS_DIGEST_MAP_V2]" in prompt_text:
        return "offline-map-evidence"
    if "[PROJECT_ANALYSIS_DIGEST" in prompt_text:
        value: dict[str, Any] = {
            "summary": "offline-baseline-result",
            "menu": {
                "test_plan": True,
                "unit_test": True,
                "integration_test": True,
                "api_test": True,
                "ui_test": True,
                "db_test": True,
                "functional_test": True,
                "nonfunctional_test": True,
                "acceptance_test": True,
            },
        }
    elif "subsystem_integration_test" in prompt_text:
        value: dict[str, Any] = {
            "subsystem_integration_test": True,
            "subsystem_integration_menu": {
                "subsystem_test": True,
                "subsystem_list": ["synthetic-subsystem"],
            },
            "module_integration_menu": {
                "module_test": True,
                "module_list": ["synthetic-module"],
            },
            "class_integration_menu": {
                "class_test": True,
                "class_list": ["synthetic-class"],
            },
        }
    elif "subsystem_menu" in prompt_text and "function_menu" in prompt_text:
        value = {
            "subsystem_menu": {
                "subsystem_test": True,
                "subsystem_list": [{
                    "display_name": "synthetic-subsystem",
                    "qualified_name": "synthetic/system/subsystem",
                    "source_hint": "synthetic-section",
                }],
            },
            "module_menu": {
                "module_test": True,
                "module_list": [{
                    "display_name": "synthetic-module",
                    "qualified_name": "synthetic/system/module",
                    "source_hint": "synthetic-section",
                }],
            },
            "class_menu": {
                "class_test": True,
                "class_list": [{
                    "display_name": "synthetic-class",
                    "qualified_name": "synthetic.module.Class",
                    "source_hint": "synthetic-section",
                }],
            },
            "function_menu": {
                "function_test": True,
                "function_list": [{
                    "display_name": "synthetic-function",
                    "qualified_name": "synthetic.module.Class.function()",
                    "source_hint": "synthetic-section",
                }],
            },
        }
    elif "api_list" in prompt_text:
        value = {"api_list": ["synthetic-api"]}
    elif "use_case_list" in prompt_text:
        value = {"use_case_list": ["synthetic-use-case"]}
    elif "method_list" in prompt_text:
        value = {"method_list": ["synthetic-performance-test"]}
    elif "black_box" in prompt_text and "white_box" in prompt_text:
        value = {"black_box": True, "white_box": True}
    elif all(
        field_name in prompt_text
        for field_name in (
            "test_plan",
            "unit_test",
            "integration_test",
            "api_test",
            "ui_test",
            "db_test",
            "functional_test",
            "nonfunctional_test",
            "acceptance_test",
        )
    ):
        value = {
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
    else:
        return "offline-baseline-result"
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _documents(profile: DocumentProfile, source: str) -> list[Document]:
    return [
        Document(
            page_content=profile.text,
            metadata={"source": f"synthetic/{source}.txt"},
        )
    ]


def _install_safety_guards(monkeypatch: pytest.MonkeyPatch) -> None:
    def blocked_network(*_args, **_kwargs):
        raise AssertionError("offline baseline attempted network access")

    def blocked_provider(*_args, **_kwargs):
        raise AssertionError("offline baseline attempted provider client creation")

    monkeypatch.setattr(socket, "create_connection", blocked_network)
    monkeypatch.setattr(provider, "get_chat_client", blocked_provider)
    monkeypatch.setattr(provider, "get_embeddings", blocked_provider)
    monkeypatch.setattr(llm_streaming, "_create_stream_client", blocked_provider)


def _install_offline_harness(
    monkeypatch: pytest.MonkeyPatch,
    profile: DocumentProfile,
    state: OfflineProjectState,
    recorder: CostRecorder,
) -> None:
    monkeypatch.setattr(testProjectDao, "find_project", lambda _pid: object())
    monkeypatch.setattr(
        testProjectDao,
        "get_project_type",
        lambda _pid: SimpleNamespace(overflow=state.overflow),
    )
    monkeypatch.setattr(testProjectDao, "get_project_info", state.get_info)
    monkeypatch.setattr(
        testProjectDao, "save_project_info_values", state.save_values
    )
    monkeypatch.setattr(
        testProjectDao,
        "save_project_analysis_bundle",
        state.save_analysis_bundle,
    )
    monkeypatch.setattr(
        testProjectDao,
        "save_project_analysis_artifact_bundle",
        state.save_analysis_artifact_bundle,
    )
    monkeypatch.setattr(
        plan_stream,
        "compute_project_source_revision",
        lambda _pid: f"{profile.name}-revision",
    )
    monkeypatch.setattr(
        plan_stream,
        "get_fresh_artifact",
        state.get_analysis_artifact,
    )
    monkeypatch.setattr(
        workflow_artifacts,
        "lookup_workflow_artifact",
        state.lookup_workflow_artifact,
    )
    monkeypatch.setattr(
        workflow_artifacts,
        "build_workflow_artifact_key",
        lambda pid, definition, payload, model_label: state.lookup_workflow_artifact(
            pid, definition, payload, model_label
        ).key,
    )
    monkeypatch.setattr(
        workflow_artifacts,
        "validate_workflow_prerequisites",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        workflow_artifacts,
        "save_workflow_artifact",
        state.save_workflow_artifact,
    )

    monkeypatch.setattr(
        documentTools,
        "generate_all_testdocs_docs",
        lambda _pid: _documents(profile, "requirements")
        + _documents(profile, "design"),
    )
    monkeypatch.setattr(
        documentTools,
        "generate_require_testdocs_docs",
        lambda _pid: _documents(profile, "requirements"),
    )
    monkeypatch.setattr(
        documentTools,
        "generate_design_testdocs_docs",
        lambda _pid: _documents(profile, "design"),
    )
    monkeypatch.setattr(
        documentTools,
        "generate_knowledge_docs",
        lambda _pid: _documents(profile, "knowledge"),
    )
    monkeypatch.setattr(
        documentTools,
        "generate_all_testdocs_str",
        lambda _pid: f"{profile.text}\n{profile.text}",
    )
    monkeypatch.setattr(
        documentTools,
        "generate_require_testdocs_str",
        lambda _pid: profile.text,
    )
    monkeypatch.setattr(
        documentTools,
        "generate_design_testdocs_str",
        lambda _pid: profile.text,
    )

    design_operations = {"unit_menu", "api_info", "ui_info", "db_info"}
    offline_specs = {}
    for operation, spec in workflow_analysis.ANALYSIS_SPECS.items():
        if operation in design_operations:
            string_loader = lambda _pid: profile.text
            document_loader = lambda _pid: _documents(profile, "design")
        else:
            string_loader = lambda _pid: profile.text
            document_loader = lambda _pid: _documents(profile, "requirements")
        offline_specs[operation] = replace(
            spec,
            string_loader=string_loader,
            document_loader=document_loader,
        )
    monkeypatch.setattr(workflow_analysis, "ANALYSIS_SPECS", offline_specs)

    def unexpected_document_load(*_args, **_kwargs):
        raise AssertionError("offline baseline attempted filesystem document loading")

    monkeypatch.setattr(documentTools, "load_document", unexpected_document_load)
    monkeypatch.setattr(
        retrievers,
        "get_lazy_embeddings",
        lambda: CountingEmbeddings(recorder),
    )

    async def fake_stream_chat_completion(
        _name: str,
        prompt_text: str,
        max_tokens: int,
        minimum_timeout_seconds: float = 0.0,
        *,
        request_options: dict[str, Any] | None = None,
    ):
        del minimum_timeout_seconds
        assert request_options is not None
        assert request_options["max_tokens"] == max_tokens
        assert all(
            forbidden not in str(request_options).lower()
            for forbidden in ("prompt", "document", "api_key")
        )
        input_tokens = documentTools.num_tokens_from_string(prompt_text)
        is_mechanical = max_tokens <= 2_048
        options_text = str(request_options).lower()
        if is_mechanical and any(
            marker in options_text
            for marker in (
                "'reasoning_effort': 'high'",
                "'reasoning_effort': 'medium'",
                "'enable_thinking': true",
                "'type': 'enabled'",
            )
        ):
            recorder.current.mechanical_high_reasoning_calls += 1
        assert input_tokens <= recorder.current.max_context_tokens
        recorder.current.chat_calls += 1
        recorder.current.input_context_tokens += input_tokens
        recorder.current.call_output_caps.append(max_tokens)
        recorder.current.call_input_tokens.append(input_tokens)
        content = _structured_response(prompt_text)
        yield ModelStreamEvent("content", text=content)
        yield ModelStreamEvent(
            "usage",
            usage=TokenUsage(
                input_tokens=input_tokens,
                reasoning_tokens=0,
                output_tokens=1,
                total_tokens=input_tokens + 1,
            ),
        )

    monkeypatch.setattr(
        plan_stream, "stream_chat_completion", fake_stream_chat_completion
    )
    monkeypatch.setattr(
        workflow_core, "stream_chat_completion", fake_stream_chat_completion
    )
    metadata = {
        "label": "GLM-4.7",
        "provider": "offline",
        "model": "offline-mock",
    }
    monkeypatch.setattr(
        plan_stream, "get_stream_model_metadata", lambda _name: metadata
    )
    monkeypatch.setattr(
        workflow_stream, "get_stream_model_metadata", lambda _name: metadata
    )


async def _consume(stream) -> list[dict[str, Any]]:
    events = []
    async for item in stream:
        events.append(item)
    assert any(item["event"] == "completed" for item in events)
    return events


def _execute_operation(operation: str, *, regenerate: bool = False) -> None:
    if operation == "project_analysis":
        asyncio.run(
            _consume(
                plan_stream.stream_test_plan(
                    "EzOfflineBaseline000",
                    "GLM-4.7",
                    regenerate,
                )
            )
        )
        return
    asyncio.run(
        _consume(
            workflow_stream.stream_llm_workflow(
                operation,
                "EzOfflineBaseline000",
                "GLM-4.7",
                WORKFLOW_PAYLOADS[operation],
                regenerate=regenerate,
            )
        )
    )


def _measure_operation(
    monkeypatch: pytest.MonkeyPatch,
    profile: DocumentProfile,
    operation: str,
) -> tuple[CostSnapshot, CostSnapshot]:
    global _ACTIVE_RECORDER
    state = OfflineProjectState(profile.overflow)
    recorder = CostRecorder()
    indexRegistry._reset_index_registry_for_tests()
    _install_offline_harness(monkeypatch, profile, state, recorder)

    try:
        _ACTIVE_RECORDER = recorder
        recorder.reset()
        recorder.current.max_context_tokens = profile_for(
            operation, "final"
        ).max_context_tokens
        _execute_operation(operation)
        first = recorder.snapshot()

        recorder.reset()
        recorder.current.max_context_tokens = profile_for(
            operation, "final"
        ).max_context_tokens
        _execute_operation(operation)
        repeated = recorder.snapshot()
    finally:
        _ACTIVE_RECORDER = None
    return first, repeated


def collect_offline_baseline(
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, dict[str, tuple[CostSnapshot, CostSnapshot]]]:
    _install_safety_guards(monkeypatch)
    _install_retrieval_counter(monkeypatch)
    operations = [item.operation for item in list_workflow_definitions()]
    return {
        profile.name: {
            operation: _measure_operation(monkeypatch, profile, operation)
            for operation in operations
        }
        for profile in PROFILES
    }


RAG_REUSE_OPERATIONS = (
    "unit_info",
    "api_case",
    "functional_case",
    "nonfunctional_info",
)
RAG_CONTEXT_LIMITS = {
    "unit_info": 6_000,
    "api_case": 12_000,
    "functional_case": 12_000,
    "nonfunctional_info": 6_000,
}
TASK5_LARGE_RAG_INPUT_TOKENS = {
    "unit_info": 8_837,
    "api_case": 22_243,
    "functional_case": 19_356,
    "nonfunctional_info": 3_490,
}
RAG_REUSE_EXPECTED = {
    ("small", "unit_info"): (
        (2, 1, 964, 9728, 321),
        (2, 0, 964, 9728, 321),
    ),
    ("small", "api_case"): (
        (3, 2, 1481, 15360, 642),
        (3, 0, 1481, 15360, 642),
    ),
    ("small", "functional_case"): (
        (3, 2, 1304, 15360, 642),
        (3, 0, 1304, 15360, 642),
    ),
    ("small", "nonfunctional_info"): (
        (2, 1, 895, 9728, 321),
        (2, 0, 895, 9728, 321),
    ),
    ("large", "unit_info"): (
        (2, 1, 1923, 9728, 1282),
        (2, 0, 1923, 9728, 1282),
    ),
    ("large", "api_case"): (
        (3, 2, 7183, 15360, 6324),
        (3, 0, 7183, 15360, 6324),
    ),
    ("large", "functional_case"): (
        (3, 2, 6830, 15360, 6148),
        (3, 0, 6830, 15360, 6148),
    ),
    ("large", "nonfunctional_info"): (
        (2, 1, 1690, 9728, 1106),
        (2, 0, 1690, 9728, 1106),
    ),
}


def _measure_regenerated_retrieval(
    monkeypatch: pytest.MonkeyPatch,
    profile: DocumentProfile,
    operation: str,
) -> tuple[CostSnapshot, CostSnapshot]:
    global _ACTIVE_RECORDER
    state = OfflineProjectState(profile.overflow)
    recorder = CostRecorder()
    indexRegistry._reset_index_registry_for_tests()
    _install_offline_harness(monkeypatch, profile, state, recorder)

    try:
        _ACTIVE_RECORDER = recorder
        recorder.reset()
        recorder.current.max_context_tokens = profile_for(
            operation, "final"
        ).max_context_tokens
        _execute_operation(operation)
        first = recorder.snapshot()

        recorder.reset()
        recorder.current.max_context_tokens = profile_for(
            operation, "final"
        ).max_context_tokens
        _execute_operation(operation, regenerate=True)
        regenerated = recorder.snapshot()
    finally:
        _ACTIVE_RECORDER = None
    return first, regenerated


def collect_offline_retrieval_reuse(
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, dict[str, tuple[CostSnapshot, CostSnapshot]]]:
    _install_safety_guards(monkeypatch)
    _install_retrieval_counter(monkeypatch)
    return {
        profile.name: {
            operation: _measure_regenerated_retrieval(
                monkeypatch, profile, operation
            )
            for operation in RAG_REUSE_OPERATIONS
        }
        for profile in PROFILES
    }


def _metric_text(metric: CostSnapshot) -> str:
    return (
        f"{metric.chat_calls}/{metric.embedding_builds}/"
        f"{metric.input_context_tokens}/{metric.output_token_cap}"
    )


def _metric_tuple(metric: CostSnapshot) -> tuple[int, int, int, int]:
    return (
        metric.chat_calls,
        metric.embedding_builds,
        metric.input_context_tokens,
        metric.output_token_cap,
    )


def _rag_metric_tuple(
    metric: CostSnapshot,
) -> tuple[int, int, int, int, int]:
    return (*_metric_tuple(metric), metric.selected_context_tokens)


def test_offline_cost_baseline_covers_all_workflows_without_external_io(
    monkeypatch,
    capsys,
):
    baseline = collect_offline_baseline(monkeypatch)
    expected_operations = {
        item.operation for item in list_workflow_definitions()
    }

    assert set(baseline) == {"small", "large"}
    assert set(EXPECTED_BASELINE) == {
        (profile_name, operation)
        for profile_name in baseline
        for operation in expected_operations
    }
    for profile_name, operations in baseline.items():
        assert set(operations) == expected_operations
        for operation, (first, repeated) in operations.items():
            for metric in (first, repeated):
                assert metric.chat_calls == len(metric.call_output_caps)
                assert metric.input_context_tokens >= 0
                assert metric.embedding_builds >= 0
                assert all(
                    cap in {1_024, 1_536, 2_048, 8_192, 12_288}
                    for cap in metric.call_output_caps
                )
                assert (metric.chat_calls == 0) == (
                    metric.input_context_tokens == 0
                )
                assert (metric.chat_calls == 0) == (
                    metric.output_token_cap == 0
                )
            assert repeated.chat_calls <= first.chat_calls, (
                profile_name,
                operation,
            )
            assert repeated.embedding_builds <= first.embedding_builds, (
                profile_name,
                operation,
            )
            assert (
                _metric_tuple(first),
                _metric_tuple(repeated),
            ) == EXPECTED_BASELINE[(profile_name, operation)]

    for profile_name in baseline:
        project_first = baseline[profile_name]["project_analysis"][0]
        project_repeat = baseline[profile_name]["project_analysis"][1]
        expected_calls = 2
        assert project_first.chat_calls == expected_calls
        assert project_first.embedding_builds == 0
        assert project_first.input_context_tokens < TASK0_PROJECT_ANALYSIS_BASELINE[
            profile_name
        ][2]
        assert project_first.output_token_cap < TASK0_PROJECT_ANALYSIS_BASELINE[
            profile_name
        ][3]
        assert project_repeat.chat_calls == 0
        assert project_repeat.embedding_builds == 0

        for definition in list_workflow_definitions():
            if definition.operation == "project_analysis":
                continue
            repeated = baseline[profile_name][definition.operation][1]
            if definition.persistence == "artifact":
                assert _metric_tuple(repeated) == (0, 0, 0, 0)
            else:
                first = baseline[profile_name][definition.operation][0]
                assert repeated.chat_calls == first.chat_calls
                assert repeated.embedding_builds == 0

        first_metrics = [
            measurement[0] for measurement in baseline[profile_name].values()
        ]
        repeated_metrics = [
            measurement[1] for measurement in baseline[profile_name].values()
        ]
        assert sum(
            metric.input_context_tokens for metric in first_metrics
        ) <= (
            TASK6_ISOLATED_TOTALS[profile_name]["input_tokens"]
            + QUALIFIED_REFERENCE_INPUT_OVERHEAD
        )
        assert sum(
            metric.output_token_cap for metric in first_metrics
        ) < TASK6_ISOLATED_TOTALS[profile_name]["output_cap"]
        assert sum(metric.chat_calls for metric in repeated_metrics) < (
            TASK0_GENERIC_REPEAT_TOTALS[profile_name]["chat_calls"]
        )
        assert sum(metric.embedding_builds for metric in repeated_metrics) < (
            TASK0_GENERIC_REPEAT_TOTALS[profile_name]["embedding_builds"]
        )

    print("profile|operation|first C/E/I/O|repeat C/E/I/O")
    for profile in PROFILES:
        for definition in list_workflow_definitions():
            first, repeated = baseline[profile.name][definition.operation]
            print(
                f"{profile.name}|{definition.operation}|"
                f"{_metric_text(first)}|{_metric_text(repeated)}"
            )

    captured = capsys.readouterr()
    assert "offline-baseline-result" not in captured.out
    if os.getenv("EZLLMTEST_PRINT_BASELINE") == "1":
        with capsys.disabled():
            print(captured.out, end="")


def test_rag_regeneration_reuses_indexes_and_bounds_selected_context(
    monkeypatch,
    capsys,
):
    measurements = collect_offline_retrieval_reuse(monkeypatch)

    assert set(measurements) == {"small", "large"}
    for profile_name, operations in measurements.items():
        assert set(operations) == set(RAG_REUSE_OPERATIONS)
        for operation, (first, regenerated) in operations.items():
            assert first.embedding_builds >= 1
            assert regenerated.embedding_builds == 0
            assert 0 < first.selected_context_tokens <= RAG_CONTEXT_LIMITS[
                operation
            ]
            assert (
                regenerated.selected_context_tokens
                == first.selected_context_tokens
            )
            if profile_name == "large":
                assert (
                    first.input_context_tokens
                    < TASK5_LARGE_RAG_INPUT_TOKENS[operation]
                )
            assert (
                _rag_metric_tuple(first),
                _rag_metric_tuple(regenerated),
            ) == RAG_REUSE_EXPECTED[(profile_name, operation)]

    print("profile|operation|first C/E/I/O/R|regenerated C/E/I/O/R")
    for profile in PROFILES:
        for operation in RAG_REUSE_OPERATIONS:
            first, regenerated = measurements[profile.name][operation]
            first_metric = (
                f"{_metric_text(first)}/{first.selected_context_tokens}"
            )
            regenerated_metric = (
                f"{_metric_text(regenerated)}/"
                f"{regenerated.selected_context_tokens}"
            )
            print(
                f"{profile.name}|{operation}|{first_metric}|"
                f"{regenerated_metric}"
            )

    captured = capsys.readouterr()
    assert "offline-baseline-result" not in captured.out
    if os.getenv("EZLLMTEST_PRINT_BASELINE") == "1":
        with capsys.disabled():
            print(captured.out, end="")


def test_token_baseline_report_contains_only_the_recorded_safe_metrics():
    report = canonical_document_path("docs/iteration-2-token-baseline.md").read_text(
        encoding="utf-8"
    )

    for definition in list_workflow_definitions():
        small_first, small_repeat = EXPECTED_BASELINE[
            ("small", definition.operation)
        ]
        large_first, large_repeat = EXPECTED_BASELINE[
            ("large", definition.operation)
        ]
        expected_row = (
            f"| `{definition.operation}` | "
            f"{'/'.join(map(str, small_first))} | "
            f"{'/'.join(map(str, small_repeat))} | "
            f"{'/'.join(map(str, large_first))} | "
            f"{'/'.join(map(str, large_repeat))} |"
        )
        assert expected_row in report

    for profile_name in ("small", "large"):
        for operation in RAG_REUSE_OPERATIONS:
            first, regenerated = RAG_REUSE_EXPECTED[
                (profile_name, operation)
            ]
            expected_row = (
                f"| {profile_name.title()} | `{operation}` | "
                f"{'/'.join(map(str, first))} | "
                f"{'/'.join(map(str, regenerated))} |"
            )
            assert expected_row in report

    assert SMALL_TEXT not in report
    assert LARGE_TEXT not in report
    assert "offline-baseline-result" not in report


def test_iteration2_release_efficiency_thresholds(monkeypatch):
    baseline = collect_offline_baseline(monkeypatch)

    assert baseline["small"]["project_analysis"][0].chat_calls <= 2
    for operations in baseline.values():
        for operation, (first, repeated) in operations.items():
            if get_workflow_definition(operation).persistence == "artifact":
                assert _metric_tuple(repeated) == (0, 0, 0, 0)
            else:
                assert repeated.chat_calls == first.chat_calls
                assert repeated.embedding_builds == 0
            assert first.mechanical_high_reasoning_calls == 0
            assert repeated.mechanical_high_reasoning_calls == 0
            context_limit = profile_for(operation, "final").max_context_tokens
            assert all(
                input_tokens <= context_limit
                for input_tokens in first.call_input_tokens
            )
