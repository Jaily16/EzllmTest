# 声明生成请求字段及校验，公开描述与默认值保持协议兼容。
from typing import Any

from pydantic import BaseModel, Field


class InfoModel(BaseModel):
    pid: str
    info_type: int
    info: str


class MenuModel(BaseModel):
    summary: str


class PlanStreamRequest(BaseModel):
    pid: str
    llm_name: str
    regenerate: bool = False


class WorkflowStreamRequest(BaseModel):
    operation: str
    pid: str
    llm_name: str
    regenerate: bool = False
    payload: dict[str, Any] = Field(default_factory=dict)


class UnitTestInvokeModel(BaseModel):
    unit_test_knowledge: str
    static_method: str
    unit_test_method_knowledge: str
    unit: str
    unit_info: str
    output_type: int
    llm_name: str


class IntegrationTestInvokeModel(BaseModel):
    integration_test_knowledge: str
    strategy: str
    strategy_knowledge: str
    blackbox_method_knowledge: str
    integration_object: str
    integration_object_info: str
    output_type: int


class ApiTestInvokeModel(BaseModel):
    pid: str
    info: str
    test_type: int
    output_type: int
    api_name: str


class UITestInvokeModel(BaseModel):
    pid: str
    info: str


class DBTestInvokeModel(BaseModel):
    pid: str
    info: str


class FunctionalTestInvokeModel(BaseModel):
    pid: str
    info: str
    test_type: int
    output_type: int
    use_case_name: str


class NFunctionalTestInvokeModel(BaseModel):
    pid: str
    info: str
    method_name: str


class AcceptanceTestInvokeModel(BaseModel):
    pid: str
    info: str
