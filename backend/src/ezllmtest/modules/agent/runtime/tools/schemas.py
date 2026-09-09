# 定义严格的工具输入，项目授权、审批和幂等信息只能来自可信上下文。
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

from ezllmtest.modules.knowledge.public import RetrievalCitation, RetrievalQueryEvidence, ToolRetrievalEvidence
from ezllmtest.modules.agent.domain.contracts import redact_sensitive_text


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
        """导出业务 payload 时排除控制字段，防止把授权或调度字段混入工作流输入。"""
        return self.model_dump(
            mode="json", exclude=self._CONTROL_FIELDS
        )

    def planned_arguments(self) -> dict[str, JsonValue]:
        """提取可进入计划的业务参数，运行身份与授权仍由可信上下文提供。"""
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
        """选择具名单元的集成分析时必须提供目标名称，避免扩大为整个项目。"""
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
        """单接口生成必须带接口名称，不能把空目标解释为全部接口。"""
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
        """单用例生成必须带用例名称，保持用户选择范围。"""
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
        """校验工具执行错误时脱敏敏感赋值，公开错误不携带原始秘密。"""
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
        """校验安全进度标签时脱敏敏感赋值，不直接公开任意执行文本。"""
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
    """递归检查工具结果中的禁止字段，运行秘密和隐藏推理不得进入公开结果。"""
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
        """结果构造时校验 data 的公开安全边界，避免内部载荷通过工具信封泄露。"""
        if value is not None:
            _validate_safe_result(value)
        return value

    @model_validator(mode="after")
    def _status_matches_error(self):
        """校验成功/失败状态与 error 对象一致，消费者不必猜测矛盾结果。"""
        if self.status is ToolExecutionStatus.SUCCESS and self.error is not None:
            raise ValueError("successful tool results cannot contain an error")
        if self.status is not ToolExecutionStatus.SUCCESS and self.error is None:
            raise ValueError("non-success tool results require a safe error")
        return self
