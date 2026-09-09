# 只组装当前任务所需的可信产物元数据和前置条件，不把数据库正文整体塞入 Agent 上下文。
"""Trusted, metadata-only prerequisite context assembly for Agent runs."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from ezllmtest.modules.generation.public import ArtifactHistoryRow
import ezllmtest.modules.generation.public as workflowArtifactService
from ezllmtest.modules.agent.domain.contracts import AgentRunState, ContextBinding, PlannedToolCall
from ezllmtest.modules.generation.public import get_workflow_definition


class ContextAssemblyError(ValueError):
    """A safe, classified failure before any tool side effect."""


class ContextArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    operation: str = Field(min_length=1, max_length=64)
    artifact_key: str = Field(min_length=1, max_length=128)
    source_revision: str = Field(min_length=1, max_length=128)
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    prompt_version: str = Field(min_length=1, max_length=128)
    model_label: str = Field(min_length=1, max_length=128)
    selection: dict[str, JsonValue] = Field(default_factory=dict)
    result: JsonValue
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


_RESULT_PATHS: dict[str, tuple[str, ...]] = {
    "unit_case": ("unit_info",),
    "integration_case": (),
    "api_case": ("apis_info",),
    "ui_case": (),
    "db_case": (),
    "functional_case": ("text_info",),
    "nonfunctional_case": ("nonfunctional_info",),
    "acceptance_case": (),
}


def context_payload_fields(operation: str) -> tuple[str, ...]:
    """列出各工作流允许由可信上下文补齐的参数字段，模型参数不能取得存储权威。"""
    return get_workflow_definition(operation).prerequisite_payload_fields


def _canonical_json(value: JsonValue) -> bytes:
    """用稳定 JSON 键序表达上下文身份，避免字典插入顺序改变审批绑定。"""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _result_hash(result: JsonValue) -> str:
    """对产物结果计算稳定摘要，供前置上下文识别变化，不把全文放入状态身份。"""
    return hashlib.sha256(_canonical_json(result)).hexdigest()


def _parse_artifact_row(
    operation: str, row: ArtifactHistoryRow
) -> ContextArtifact | None:
    """将仓储快照解析为上下文候选，拒绝不符合有效产物结构的数据。"""
    try:
        value = json.loads(row.content)
        metadata = json.loads(row.metadata_json or "{}")
    except (TypeError, json.JSONDecodeError):
        return None
    if (
        not isinstance(value, dict)
        or value.get("version") != 1
        or value.get("operation") != operation
        or not isinstance(value.get("selection"), dict)
        or "result" not in value
        or (
            isinstance(metadata, dict)
            and "stale_for_source_revision" in metadata
        )
    ):
        return None
    result = value["result"]
    return ContextArtifact(
        operation=operation,
        artifact_key=row.artifact_key,
        source_revision=row.source_revision,
        input_hash=row.input_hash,
        prompt_version=row.prompt_version,
        model_label=row.model_label,
        selection=value["selection"],
        result=result,
        content_sha256=_result_hash(result),
    )


def _default_artifact_loader(project_id: str, source_operation: str) -> tuple[ContextArtifact, ...]:
    """通过 generation 的只读快照接口组装前置上下文，不接触 ORM 或会话。"""
    definition = get_workflow_definition(source_operation)
    rows = workflowArtifactService.list_artifact_history(project_id, definition.result_artifact)
    return tuple(artifact for row in rows
                 if (artifact := _parse_artifact_row(source_operation, row)) is not None)


ArtifactLoader = Callable[[str, str], Iterable[ContextArtifact]]


# context 只按可信 artifact identity 在内存中组装，不能把其他项目正文带入当前运行。
class AgentContextAssembler:
    """Bind trusted artifact identities and hydrate bodies only in memory."""

    def __init__(self, artifact_loader: ArtifactLoader | None = None) -> None:
        """允许注入产物读取接口；默认加载器只在组装上下文时按所需引用读取产物。"""
        self._artifact_loader = artifact_loader or _default_artifact_loader

    @staticmethod
    def _source_operation(call: PlannedToolCall) -> str:
        """从操作目录判断当前调用依赖的前置来源，不任意猜测其他工作流结果。"""
        definition = get_workflow_definition(call.operation)
        if len(definition.prerequisites) != 1:
            raise ContextAssemblyError("context_prerequisite_invalid")
        return definition.prerequisites[0]

    @staticmethod
    def _selection_matches(
        call: PlannedToolCall, artifact: ContextArtifact
    ) -> bool:
        """比较规范化选择条件与已保存产物输入，避免复用不匹配目标的上下文。"""
        if call.operation == "unit_case":
            return all(
                artifact.selection.get(key) == call.arguments.get(key)
                for key in ("unit", "unit_type")
                if key in call.arguments
            )
        if call.operation == "integration_case":
            target = call.arguments.get("integration_object")
            return not target or artifact.selection.get("name") == target
        return True

    def _candidates(
        self, state: AgentRunState, call: PlannedToolCall
    ) -> tuple[ContextArtifact, ...]:
        """在可信项目内选择满足前置条件的产物候选，不跨项目检索上下文。"""
        source = self._source_operation(call)
        loaded = tuple(
            ContextArtifact.model_validate(item)
            for item in self._artifact_loader(
                state.project_scope.project_id, source
            )
        )
        current = tuple(
            item
            for item in loaded
            if item.source_revision == state.source_revision
            and self._selection_matches(call, item)
        )
        if not current:
            if loaded:
                raise ContextAssemblyError("context_stale")
            raise ContextAssemblyError("context_missing")
        by_hash = {item.content_sha256: item for item in current}
        if len(by_hash) != 1:
            raise ContextAssemblyError("context_ambiguous")
        return tuple(by_hash.values())

    def bind_call(
        self, state: AgentRunState, call: PlannedToolCall
    ) -> PlannedToolCall:
        """为计划调用绑定前置产物元数据及上下文身份，让审批覆盖实际将使用的资料版本。"""
        fields = context_payload_fields(call.operation)
        if not fields:
            return call.model_copy(update={"context_bindings": ()})
        if any(field in call.arguments for field in fields):
            raise ContextAssemblyError("context_body_in_plan")
        artifact = self._candidates(state, call)[0]
        result_path = _RESULT_PATHS.get(call.operation, ())
        bindings = tuple(
            ContextBinding(
                payload_field=field,
                source_operation=artifact.operation,
                artifact_key=artifact.artifact_key,
                source_revision=artifact.source_revision,
                input_hash=artifact.input_hash,
                prompt_version=artifact.prompt_version,
                model_label=artifact.model_label,
                result_path=result_path,
                content_sha256=artifact.content_sha256,
            )
            for field in fields
        )
        return call.model_copy(update={"context_bindings": bindings})

    def hydrate_call(
        self, state: AgentRunState, call: PlannedToolCall
    ) -> dict[str, JsonValue]:
        """执行前按已绑定身份补齐所需参数，来源变化时不能静默换用另一份产物。"""
        fields = context_payload_fields(call.operation)
        if fields and not call.context_bindings:
            raise ContextAssemblyError("context_binding_required")
        if not call.context_bindings:
            return dict(call.arguments)
        hydrated: dict[str, JsonValue] = dict(call.arguments)
        for binding in call.context_bindings:
            if binding.source_revision != state.source_revision:
                raise ContextAssemblyError("context_stale")
            candidates = tuple(
                item
                for item in self._artifact_loader(
                    state.project_scope.project_id, binding.source_operation
                )
                if item.source_revision == state.source_revision
                and item.input_hash == binding.input_hash
                and item.prompt_version == binding.prompt_version
                and item.model_label == binding.model_label
                and item.artifact_key == binding.artifact_key
                and item.content_sha256 == binding.content_sha256
                and self._selection_matches(call, item)
            )
            if not candidates:
                raise ContextAssemblyError("context_stale")
            unique = {item.content_sha256: item for item in candidates}
            if len(unique) != 1:
                raise ContextAssemblyError("context_ambiguous")
            value: Any = next(iter(unique.values())).result
            for key in binding.result_path:
                if not isinstance(value, dict) or key not in value:
                    raise ContextAssemblyError("context_result_invalid")
                value = value[key]
            if not isinstance(value, str) or not value.strip():
                raise ContextAssemblyError("context_result_invalid")
            hydrated[binding.payload_field] = value
        return hydrated
