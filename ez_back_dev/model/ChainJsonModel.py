from langchain_core.pydantic_v1 import BaseModel, Field
from typing import List


# 1.用于测试菜单的生成
class TestMenu(BaseModel):
    test_plan: bool = Field(description="该业务能否制定测试计划")
    unit_test: bool = Field(description="该业务能否做单元测试")
    integration_test: bool = Field(description="该业务能否做集成测试")
    api_test: bool = Field(description="该业务能否api接口测试")
    ui_test: bool = Field(description="该业务能否做前端ui测试")
    db_test: bool = Field(description="该业务能否做数据库测试")
    functional_test: bool = Field(description="该业务能否做系统功能性测试")
    nonfunctional_test: bool = Field(description="该业务能否做系统非功能性测试")
    acceptance_test: bool = Field(description="该业务能否做验收测试")


# 2.用于单元测试的生成
class SubsystemMenu(BaseModel):
    subsystem_test: bool = Field(description="该业务能否做子系统测试")
    subsystem_list: List[str] = Field(description="业务的子系统划分")


class ModuleMenu(BaseModel):
    module_test: bool = Field(description="该业务是否能做模块测试")
    module_list: List[str] = Field(description="业务的模块划分")


class ClassMenu(BaseModel):
    class_test: bool = Field(description="该业务是否能做类(class)测试")
    class_list: List[str] = Field(description="业务的类(class)划分")


class FunctionMenu(BaseModel):
    function_test: bool = Field(description="该业务能否做函数测试")
    function_list: List[str] = Field(description="业务的函数划分")


class UnitTestMenu(BaseModel):
    subsystem_menu: SubsystemMenu = Field(description="该业务的子系统测试相关内容")
    module_menu: ModuleMenu = Field(description="该业务的模块测试相关内容")
    class_menu: ClassMenu = Field(description="该业务的类(class)测试相关内容")
    function_menu: FunctionMenu = Field(description="该业务的函数测试相关内容")


class UnitTestMethod(BaseModel):
    black_box: bool = Field(description="是否能进行静态黑盒测试")
    white_box: bool = Field(description="是否能进行静态白盒测试")


# 2.用于集成测试的生成
class ClassIntegrationMenu(BaseModel):
    class_test: bool = Field(description="该业务是否能做类(class)内的集成测试")
    class_list: List[str] = Field(description="业务的类(class)划分")


class ModuleIntegrationMenu(BaseModel):
    module_test: bool = Field(description="该业务是否能做模块内的集成测试")
    module_list: List[str] = Field(description="业务的模块划分")


class SubsystemIntegrationMenu(BaseModel):
    subsystem_test: bool = Field(description="该业务能否做子系统内的集成测试")
    subsystem_list: List[str] = Field(description="业务的子系统划分")


class IntegrationTestMenu(BaseModel):
    subsystem_integration_test: bool = Field(description="该业务能否做子系统间的集成测试")
    subsystem_integration_menu: SubsystemIntegrationMenu = Field(description="该业务的子系统内集成测试的相关内容")
    module_integration_menu: ModuleIntegrationMenu = Field(description="该业务的模块内集成测试的相关内容")
    class_integration_menu: ClassIntegrationMenu = Field(description="该业务的类(class)内集成测试的相关内容")


# 用于获取api接口的列表
class ApiList(BaseModel):
    api_list: List[str] = Field(description="业务的api接口列表")


# 用于获取所有用例的列表
class UseCaseList(BaseModel):
    use_case_list: List[str] = Field(description="业务的用例列表")


# 用于非功能性测试的列表
class NonfunctionalTestMethodList(BaseModel):
    method_list: List[str] = Field(description="业务需要进行的所有非功能性测试列表")
