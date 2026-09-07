"""Strict, transport-neutral schemas for Iteration 4 project tools.

Project authority, approvals, idempotency state, prompts, and model reasoning are
intentionally absent from every model-visible input.
"""

from __future__ import annotations

from enum import Enum
import math
from typing import ClassVar, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)

from service.retrieval.contracts import (
    RetrievalCitation,
    RetrievalQueryEvidence,
    ToolRetrievalEvidence,
)
from service.agent.contracts import redact_sensitive_text


class _StrictToolModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=False,
    )


class EmptyToolInput(_StrictToolModel):
    """A model-visible input with no arguments; scope is runtime-injected."""


class WorkflowToolInput(_StrictToolModel):
    model_label: StrictStr = Field(min_length=1, max_length=128)
    regenerate: bool = False

    _CONTROL_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {"model_label", "regenerate"}
    )

    def workflow_payload(self) -> dict[str, JsonValue]:
        """构造工作流载荷。"""
        return self.model_dump(
            mode="json", exclude=self._CONTROL_FIELDS
        )

    def planned_arguments(self) -> dict[str, JsonValue]:
        """处理已规划的参数，并保持 `WorkflowToolInput` 的现有状态约束。"""
        return {
            **self.workflow_payload(),
            "regenerate": self.regenerate,
        }


class ProjectAnalysisToolInput(WorkflowToolInput):
    pass


class UnitMenuToolInput(WorkflowToolInput):
    pass


class UnitInfoToolInput(WorkflowToolInput):
    unit: StrictStr = Field(min_length=1)
    unit_type: StrictStr = ""


class UnitCaseToolInput(WorkflowToolInput):
    method_type: StrictInt
    static_method: StrictStr = Field(min_length=1)
    unit: StrictStr = Field(min_length=1)
    unit_type: StrictStr = ""
    unit_info: StrictStr = Field(min_length=1)
    output_type: StrictInt


class IntegrationMenuToolInput(WorkflowToolInput):
    units_info: StrictStr | None = None


class IntegrationInfoToolInput(WorkflowToolInput):
    integration_type: StrictInt
    name: StrictStr = ""

    @model_validator(mode="after")
    def _named_targets_require_a_name(self):
        """返回当前命名目标require A名称。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
        if self.integration_type not in (0, 1) and not self.name.strip():
            raise ValueError("name is required for the selected integration type")
        return self


class IntegrationCaseToolInput(WorkflowToolInput):
    strategy_type: StrictInt
    strategy: StrictStr = Field(min_length=1)
    integration_object: StrictStr = Field(min_length=1)
    integration_object_info: StrictStr = Field(min_length=1)
    output_type: StrictInt


class ApiInfoToolInput(WorkflowToolInput):
    pass


class ApiCaseToolInput(WorkflowToolInput):
    info: StrictStr = Field(min_length=1)
    test_type: StrictInt
    output_type: StrictInt
    api_name: StrictStr = ""

    @model_validator(mode="after")
    def _single_api_requires_a_name(self):
        """返回当前单项API requiresA名称。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
        if self.test_type != 0 and not self.api_name.strip():
            raise ValueError("api_name is required for a named API")
        return self


class UiInfoToolInput(WorkflowToolInput):
    pass


class UiCaseToolInput(WorkflowToolInput):
    info: StrictStr = Field(min_length=1)


class DbInfoToolInput(WorkflowToolInput):
    pass


class DbCaseToolInput(WorkflowToolInput):
    info: StrictStr = Field(min_length=1)


class FunctionalInfoToolInput(WorkflowToolInput):
    pass


class FunctionalCaseToolInput(WorkflowToolInput):
    info: StrictStr = Field(min_length=1)
    test_type: StrictInt
    output_type: StrictInt
    use_case_name: StrictStr = ""

    @model_validator(mode="after")
    def _single_use_case_requires_a_name(self):
        """返回当前单项USE用例requires A名称。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
        if self.test_type != 0 and not self.use_case_name.strip():
            raise ValueError("use_case_name is required for a named use case")
        return self


class NonfunctionalInfoToolInput(WorkflowToolInput):
    pass


class NonfunctionalCaseToolInput(WorkflowToolInput):
    info: StrictStr = Field(min_length=1)
    method_name: StrictStr = Field(min_length=1)


class AcceptanceInfoToolInput(WorkflowToolInput):
    pass


class AcceptanceCaseToolInput(WorkflowToolInput):
    info: StrictStr = Field(min_length=1)


TOOL_INPUT_MODELS: dict[str, type[WorkflowToolInput]] = {
    "project_analysis": ProjectAnalysisToolInput,
    "unit_menu": UnitMenuToolInput,
    "unit_info": UnitInfoToolInput,
    "unit_case": UnitCaseToolInput,
    "integration_menu": IntegrationMenuToolInput,
    "integration_info": IntegrationInfoToolInput,
    "integration_case": IntegrationCaseToolInput,
    "api_info": ApiInfoToolInput,
    "api_case": ApiCaseToolInput,
    "ui_info": UiInfoToolInput,
    "ui_case": UiCaseToolInput,
    "db_info": DbInfoToolInput,
    "db_case": DbCaseToolInput,
    "functional_info": FunctionalInfoToolInput,
    "functional_case": FunctionalCaseToolInput,
    "nonfunctional_info": NonfunctionalInfoToolInput,
    "nonfunctional_case": NonfunctionalCaseToolInput,
    "acceptance_info": AcceptanceInfoToolInput,
    "acceptance_case": AcceptanceCaseToolInput,
}


class ToolExecutionStatus(str, Enum):
    SUCCESS = "success"
    APPROVAL_REQUIRED = "approval_required"
    CANCELLED = "cancelled"
    STALE = "stale"
    ERROR = "error"


class ToolUsageSummary(_StrictToolModel):
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    model_calls: int = Field(default=0, ge=0)
    embedding_calls: int | None = Field(default=None, ge=0)
    tool_calls: int = Field(default=1, ge=0)
    estimated_cost_units: int | None = Field(default=None, ge=0)


class ToolExecutionError(_StrictToolModel):
    code: StrictStr = Field(min_length=1, max_length=128)
    category: str = Field(min_length=1, max_length=64)
    retryable: bool = False
    safe_message: StrictStr = Field(min_length=1, max_length=512)

    @field_validator("safe_message")
    @classmethod
    def _redact_message(cls, value: str) -> str:
        """脱敏消息，并遵循现有调用契约。"""
        return redact_sensitive_text(value)


class ToolProgress(_StrictToolModel):
    stage: StrictStr = Field(min_length=1, max_length=128)
    label: StrictStr = Field(min_length=1, max_length=512)
    progress: float = Field(ge=0)
    total: float | None = Field(default=100, gt=0)
    current: int | None = Field(default=None, ge=0)
    item_total: int | None = Field(default=None, ge=0)

    @field_validator("label")
    @classmethod
    def _redact_label(cls, value: str) -> str:
        """脱敏标签，并遵循现有调用契约。"""
        return redact_sensitive_text(value)


_FORBIDDEN_RESULT_KEYS = frozenset(
    {
        "api_key",
        "authorization",
        "completion",
        "cookie",
        "document_body",
        "password",
        "prompt",
        "raw_document",
        "reasoning",
        "scratchpad",
        "secret",
    }
)


def _validate_safe_result(value: JsonValue, path: str = "data") -> None:
    """校验安全结果，并保持现有契约。

    参数:
        `value`：待处理的值。
        `path`：目标路径。

    异常:
        `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
    if isinstance(value, dict):
        for key, nested in value.items():
            if key.strip().lower() in _FORBIDDEN_RESULT_KEYS:
                raise ValueError(f"forbidden tool result key: {path}.{key}")
            _validate_safe_result(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _validate_safe_result(nested, f"{path}[{index}]")


class ToolExecutionResult(_StrictToolModel):
    schema_version: int = Field(default=1, ge=1, le=1)
    tool_name: StrictStr = Field(min_length=1, max_length=128)
    operation: StrictStr | None = Field(default=None, max_length=64)
    status: ToolExecutionStatus
    data: JsonValue | None = None
    from_cache: bool = False
    saved: bool = False
    stale: bool = False
    source_revision: StrictStr | None = Field(default=None, max_length=128)
    artifact_key: StrictStr | None = Field(default=None, max_length=128)
    usage: ToolUsageSummary = Field(default_factory=ToolUsageSummary)
    error: ToolExecutionError | None = None
    retrieval_evidence: ToolRetrievalEvidence | None = None

    @field_validator("data")
    @classmethod
    def _data_is_safe(cls, value: JsonValue | None):
        """判断DATA安全是否满足现有约束。"""
        if value is not None:
            _validate_safe_result(value)
        return value

    @model_validator(mode="after")
    def _status_matches_error(self):
        """处理状态匹配关系错误，并保持 `ToolExecutionResult` 的现有状态约束。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
        if self.status is ToolExecutionStatus.SUCCESS and self.error is not None:
            raise ValueError("successful tool results cannot contain an error")
        if self.status is not ToolExecutionStatus.SUCCESS and self.error is None:
            raise ValueError("non-success tool results require a safe error")
        return self
