# 注册生成相关 REST 与 SSE 路由，保持接口契约并把生成过程交给应用服务。
import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
import ezllmtest.modules.projects.public as testProjectDao
from ezllmtest.modules.generation.application.operations.acceptance import find_out_requirement_info, generate_acceptance_test_cases
from ezllmtest.modules.generation.application.operations.api import find_out_apis_info, generate_api_test_cases
from ezllmtest.modules.generation.application.operations.database import find_out_database_info, generate_db_test_cases
from ezllmtest.modules.generation.application.operations.functional import find_out_use_cases_info, generate_functional_test_cases
from ezllmtest.modules.generation.application.operations.nonfunctional import find_out_nonfunctional_info, generate_nonfunctional_test_cases
from ezllmtest.modules.generation.application.test_plan import generate_test_plan, generate_test_plan_again
from ezllmtest.modules.generation.application.test_plan_stream import TestPlanStreamError, get_project_analysis_status, stream_test_plan
from ezllmtest.modules.generation.application.stream_core import WorkflowStreamError
from ezllmtest.modules.generation.application.stream import stream_llm_workflow
from ezllmtest.modules.generation.application.operations.ui import find_out_ui_info, generate_ui_test_cases
from ezllmtest.shared.status import Status
from ezllmtest.platform.ai.gateway import LLMConfigurationError, LLMEmptyResponseError, LLMProviderError, LLMRateLimitError, LLMTimeoutError, ensure_supported_model
from ezllmtest.modules.generation.schemas.requests import MenuModel, UnitTestInvokeModel, IntegrationTestInvokeModel, ApiTestInvokeModel, UITestInvokeModel, DBTestInvokeModel, FunctionalTestInvokeModel, NFunctionalTestInvokeModel, AcceptanceTestInvokeModel, PlanStreamRequest, WorkflowStreamRequest
from ezllmtest.modules.generation.application.operations.summarize import start_test_summarize_analyze, get_test_menu, restart_test_summarize_analyze
from ezllmtest.modules.generation.application.operations.unit import summarize_unit_info, find_out_test_unit_info, find_unit_test_knowledge, generate_test_cases, summarize_unit_info_again
from ezllmtest.modules.generation.application.operations.integration import get_integration_test_info, get_integration_description, find_integration_test_knowledge, generate_integration_test_cases

router = APIRouter()



def _validate_llm_name(llm_name: str) -> None:
    """HTTP 边界先核验注册模型标签，错误保持稳定响应，不转发未知模型到 provider。"""
    ensure_supported_model(llm_name)


# legacy SSE 事件格式是公共 wire contract；这里只序列化安全 payload，不改变事件名和字段。
def _sse_message(event: str, data: dict) -> str:
    """编码符合 legacy 流协议的 SSE 消息。"""
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"


def _stream_error(exc: Exception) -> dict:
    """将生成异常映射为安全 SSE 错误，不能把底层秘密或原始响应放入事件。"""
    if isinstance(exc, (TestPlanStreamError, WorkflowStreamError)):
        return {
            "code": exc.code,
            "message": str(exc),
            "status": exc.status,
            "retryable": exc.retryable,
        }
    if isinstance(exc, LLMConfigurationError):
        return {
            "code": "configuration_error",
            "message": str(exc),
            "status": 503,
            "retryable": False,
        }
    if isinstance(exc, LLMTimeoutError):
        return {
            "code": "timeout",
            "message": str(exc),
            "status": 504,
            "retryable": True,
        }
    if isinstance(exc, LLMRateLimitError):
        return {
            "code": "rate_limit",
            "message": str(exc),
            "status": 429,
            "retryable": True,
        }
    if isinstance(exc, LLMProviderError):
        return {
            "code": exc.code,
            "message": str(exc),
            "status": 502,
            "retryable": exc.retryable,
        }
    if isinstance(exc, LLMEmptyResponseError):
        return {
            "code": "empty_response",
            "message": str(exc),
            "status": 502,
            "retryable": True,
        }
    return {
        "code": "internal_error",
        "message": "大模型任务执行失败，请稍后重试",
        "status": 500,
        "retryable": True,
    }


# 历史 GET 入口可能触发摘要分析及保存，不能仅因方法为 GET 就把它纳入只读验收。
@router.get("/project/llm/menu/analyze/{pid}", description="\f")
async def analyze_testdoc_for_menu(pid: str):
    """\f
    处理 `GET /project/llm/menu/analyze/{pid}` 请求，并沿用既有状态码、响应 schema 与安全边界。

    参数:
        `pid`：项目 ID。"""
    result = start_test_summarize_analyze(pid)
    if not result:
        return {"status": Status.LLM_MENU_ANALYSIS_FAILURE.value, "reason": "业务文档分析失败", "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "业务文档分析完成", "data": result}


# 校验显式模型后强制重新分析项目摘要，属于有模型和写入副作用的历史 GET 入口。
@router.get("/project/llm/menu/analyze/update/{pid}/{llm_name}", description="\f")
async def reanalyze_testdoc(pid: str, llm_name: str):
    """\f
    处理 `GET /project/llm/menu/analyze/update/{pid}/{llm_name}` 请求，并沿用既有状态码、响应 schema 与安全边界。

    参数:
        `pid`：项目 ID。
        `llm_name`：界面选择的模型标识。"""
    _validate_llm_name(llm_name)
    result = restart_test_summarize_analyze(pid, llm_name)
    if not result:
        return {"status": Status.LLM_MENU_ANALYSIS_FAILURE.value, "reason": "业务文档重新分析失败", "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "业务文档重新分析完成", "data": result}


# 根据提交的摘要调用结构化测试菜单生成，不把 POST 响应当作无模型静态计算。
@router.post("/project/llm/menu/acquire", description="\f")
async def acquire_menu(item: MenuModel):
    """\f
    处理 `POST /project/llm/menu/acquire` 请求，并沿用既有状态码、响应 schema 与安全边界。

    参数:
        `item`：待处理的条目。"""
    item_dict = item.model_dump()
    summary = item_dict["summary"]
    result = get_test_menu(summary)
    return {"status": Status.SUCCESS.value, "reason": "测试类型分析完成", "data": result}


# 读取或生成单元目录并返回分析结果，模型标签先经允许列表校验。
@router.get("/project/llm/unit/menu/{pid}/{llm_name}", description="\f")
async def unit_test_menu(pid: str, llm_name: str):
    """\f
    处理 `GET /project/llm/unit/menu/{pid}/{llm_name}` 请求，并沿用既有状态码、响应 schema 与安全边界。

    参数:
        `pid`：项目 ID。
        `llm_name`：界面选择的模型标识。"""
    _validate_llm_name(llm_name)
    result = summarize_unit_info(pid, llm_name)
    if not result:
        return {"status": Status.LLM_MENU_ANALYSIS_FAILURE.value, "reason": "单元测试分析失败", "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "单元测试类型分析完成", "data": result}


# 显式重生成单元目录，复用业务实现的保存与失效边界。
@router.get("/project/llm/unit/menu/update/{pid}/{llm_name}", description="\f")
async def unit_test_menu_again(pid: str, llm_name: str):
    """\f
    处理 `GET /project/llm/unit/menu/update/{pid}/{llm_name}` 请求，并沿用既有状态码、响应 schema 与安全边界。

    参数:
        `pid`：项目 ID。
        `llm_name`：界面选择的模型标识。"""
    _validate_llm_name(llm_name)
    result = summarize_unit_info_again(pid, llm_name)
    if not result:
        return {"status": Status.LLM_MENU_ANALYSIS_FAILURE.value, "reason": "单元测试重新分析失败", "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "单元测试类型重新分析完成", "data": result}


# 为指定单元检索设计文档并生成分析，路径参数不是只读查询保证。
@router.get("/project/llm/unit/info/{pid}/{name}/{llm_name}", description="\f")
async def unit_test_info(pid: str, name: str, llm_name: str):
    """\f
    处理 `GET /project/llm/unit/info/{pid}/{name}/{llm_name}` 请求，并沿用既有状态码、响应 schema 与安全边界。

    参数:
        `pid`：项目 ID。
        `name`：目标名称。
        `llm_name`：界面选择的模型标识。"""
    _validate_llm_name(llm_name)
    result = find_out_test_unit_info(pid, name, llm_name)
    if not result:
        return {"status": Status.LLM_MENU_ANALYSIS_FAILURE.value, "reason": "单元信息获取失败", "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "单元信息获取成功", "data": result}


# 按请求的单元测试方法调用知识流程，保持路径参数对应的项目和目标范围。
@router.get("/project/llm/unit/knowledge/{pid}/{method_type}", description="\f")
async def unit_test_knowledge(pid: str, method_type: int):
    """\f
    处理 `GET /project/llm/unit/knowledge/{pid}/{method_type}` 请求，并沿用既有状态码、响应 schema 与安全边界。

    参数:
        `pid`：项目 ID。
        `method_type`：沿用签名中 `int` 类型约束的输入。"""
    result = find_unit_test_knowledge(pid, method_type)
    if not result:
        return {"status": Status.LLM_MENU_ANALYSIS_FAILURE.value, "reason": "单元测试知识库信息获取失败", "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "单元测试知识库信息获取成功", "data": result}


# 从请求 DTO 提取单元测试知识与目标参数，交给生成服务并编码成功或失败信封。
@router.post("/project/llm/unit/case", description="\f")
async def unit_test_case(item: UnitTestInvokeModel):
    """\f
    处理 `POST /project/llm/unit/case` 请求，并沿用既有状态码、响应 schema 与安全边界。

    参数:
        `item`：待处理的条目。"""
    item_dict = item.model_dump()
    test_knowledge = item_dict["unit_test_knowledge"]
    static_method = item_dict["static_method"]
    unit_test_method_knowledge = item_dict["unit_test_method_knowledge"]
    unit = item_dict["unit"]
    unit_info = item_dict["unit_info"]
    output_type = item_dict["output_type"]
    llm_name = item_dict["llm_name"]
    _validate_llm_name(llm_name)
    result = generate_test_cases(test_knowledge, static_method, unit_test_method_knowledge,
                                 unit, unit_info, output_type, llm_name)
    if not result:
        return {"status": Status.LLM_MENU_ANALYSIS_FAILURE.value, "reason": "单元测试用例生成失败", "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "单元测试用例生成成功", "data": result}


# 由摘要生成集成测试类型菜单，结构化输出由业务链负责校验。
@router.post("/project/llm/integration/menu", description="\f")
async def acquire_integration_menu(item: MenuModel):
    """\f
    处理 `POST /project/llm/integration/menu` 请求，并沿用既有状态码、响应 schema 与安全边界。

    参数:
        `item`：待处理的条目。"""
    item_dict = item.model_dump()
    summary = item_dict["summary"]
    result = get_integration_test_info(summary)
    if not result:
        return {"status": Status.LLM_MENU_ANALYSIS_FAILURE.value, "reason": "集成测试类型分析失败", "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "集成测试类型分析成功", "data": result}


# 核验集成层级和具名目标后取得描述，不把未指定目标扩展为任意项目资料。
@router.get("/project/llm/integration/info/{pid}/{integration_type}/{name}", description="\f")
async def find_out_integration_test_info(pid: str, integration_type: int, name: str):
    """\f
    处理 `GET /project/llm/integration/info/{pid}/{integration_type}/{name}` 请求，并沿用既有状态码、响应 schema 与安全边界。

    参数:
        `pid`：项目 ID。
        `integration_type`：沿用签名中 `int` 类型约束的输入。
        `name`：目标名称。"""
    if integration_type <= 1:
        result = get_integration_description(pid, integration_type)
    else:
        result = get_integration_description(pid, integration_type, name)
    if not result:
        return {"status": Status.INTEGRATION_INFO_GET_FAILURE.value, "reason": "集成测试信息分析失败", "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "集成测试信息分析成功", "data": result}


# 为明确集成策略调用知识流程，HTTP 参数不能绕过已有策略校验。
@router.get("/project/llm/integration/knowledge/{pid}/{strategy_type}", description="\f")
async def integration_test_knowledge(pid: str, strategy_type: int):
    """\f
    处理 `GET /project/llm/integration/knowledge/{pid}/{strategy_type}` 请求，并沿用既有状态码、响应 schema 与安全边界。

    参数:
        `pid`：项目 ID。
        `strategy_type`：沿用签名中 `int` 类型约束的输入。"""
    result = find_integration_test_knowledge(pid, strategy_type)
    if not result:
        return {"status": Status.LLM_MENU_ANALYSIS_FAILURE.value, "reason": "集成测试知识库信息获取失败", "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "集成测试知识库信息获取成功", "data": result}


# 将集成对象、策略和知识输入交给用例生成服务，接口层不另写产物存储。
@router.post("/project/llm/integration/case", description="\f")
async def integration_test_case(item: IntegrationTestInvokeModel):
    """\f
    处理 `POST /project/llm/integration/case` 请求，并沿用既有状态码、响应 schema 与安全边界。

    参数:
        `item`：待处理的条目。"""
    item_dict = item.model_dump()
    test_knowledge = item_dict["integration_test_knowledge"]
    strategy = item_dict["strategy"]
    strategy_knowledge = item_dict["strategy_knowledge"]
    blackbox_method_knowledge = item_dict["blackbox_method_knowledge"]
    integration_object = item_dict["integration_object"]
    integration_object_info = item_dict["integration_object_info"]
    output_type = item_dict["output_type"]
    result = generate_integration_test_cases(test_knowledge, strategy, strategy_knowledge, blackbox_method_knowledge,
                                             integration_object, integration_object_info, output_type)
    if not result:
        return {"status": Status.LLM_MENU_ANALYSIS_FAILURE.value, "reason": "集成测试用例生成失败", "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "集成测试用例生成成功", "data": result}


# 返回或生成项目 API 分析；缓存未命中时可能调用模型。
@router.get("/project/llm/api/info/{pid}", description="\f")
async def get_apis_info(pid: str):
    """\f
    处理 `GET /project/llm/api/info/{pid}` 请求，并沿用既有状态码、响应 schema 与安全边界。

    参数:
        `pid`：项目 ID。"""
    result = find_out_apis_info(pid)
    if not result:
        return {"status": Status.LLM_APIS_ANALYSIS_FAILURE.value, "reason": "项目api接口信息获取失败", "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "项目api接口信息获取成功", "data": result}


# 将项目及 API 选择范围交给用例生成服务，保留失败返回格式。
@router.post("/project/llm/api/case", description="\f")
async def api_test_case(item: ApiTestInvokeModel):
    """\f
    处理 `POST /project/llm/api/case` 请求，并沿用既有状态码、响应 schema 与安全边界。

    参数:
        `item`：待处理的条目。"""
    item_dict = item.model_dump()
    pid = item_dict["pid"]
    info = item_dict["info"]
    test_type = item_dict["test_type"]
    output_type = item_dict["output_type"]
    api_name = item_dict["api_name"]
    result = generate_api_test_cases(pid, info, test_type, output_type, api_name)
    if not result:
        return {"status": Status.LLM_APIS_ANALYSIS_FAILURE.value, "reason": "项目api用例生成失败", "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "项目api用例生成成功", "data": result}


# 返回或生成界面分析，GET 路径不代表无生成副作用。
@router.get("/project/llm/ui/info/{pid}", description="\f")
async def get_ui_info(pid: str):
    """\f
    处理 `GET /project/llm/ui/info/{pid}` 请求，并沿用既有状态码、响应 schema 与安全边界。

    参数:
        `pid`：项目 ID。"""
    result = find_out_ui_info(pid)
    if not result:
        return {"status": Status.LLM_APIS_ANALYSIS_FAILURE.value, "reason": "项目前端UI设计信息获取失败", "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "项目前端UI设计信息获取成功", "data": result}


# 根据提交的界面信息与项目知识生成 UI 测试用例。
@router.post("/project/llm/ui/case", description="\f")
async def ui_test_case(item: UITestInvokeModel):
    """\f
    处理 `POST /project/llm/ui/case` 请求，并沿用既有状态码、响应 schema 与安全边界。

    参数:
        `item`：待处理的条目。"""
    item_dict = item.model_dump()
    pid = item_dict["pid"]
    info = item_dict["info"]
    result = generate_ui_test_cases(pid, info)
    if not result:
        return {"status": Status.LLM_APIS_ANALYSIS_FAILURE.value, "reason": "项目前端UI测试用例生成失败", "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "项目前端UI测试用例生成成功", "data": result}


# 返回或生成数据库设计摘要，缓存未命中时调用分析服务。
@router.get("/project/llm/db/info/{pid}", description="\f")
async def get_db_info(pid: str):
    """\f
    处理 `GET /project/llm/db/info/{pid}` 请求，并沿用既有状态码、响应 schema 与安全边界。

    参数:
        `pid`：项目 ID。"""
    result = find_out_database_info(pid)
    if not result:
        return {"status": Status.LLM_APIS_ANALYSIS_FAILURE.value, "reason": "项目数据库设计信息获取失败", "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "项目数据库设计信息获取成功", "data": result}


# 根据项目数据库信息与测试知识生成用例。
@router.post("/project/llm/db/case", description="\f")
async def db_test_case(item: DBTestInvokeModel):
    """\f
    处理 `POST /project/llm/db/case` 请求，并沿用既有状态码、响应 schema 与安全边界。

    参数:
        `item`：待处理的条目。"""
    item_dict = item.model_dump()
    pid = item_dict["pid"]
    info = item_dict["info"]
    result = generate_db_test_cases(pid, info)
    if not result:
        return {"status": Status.LLM_APIS_ANALYSIS_FAILURE.value, "reason": "项目数据库测试用例生成失败", "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "项目数据库测试用例生成成功", "data": result}


# 读取或生成需求用例分析，后续测试选择依赖返回的结构化结果。
@router.get("/project/llm/functional/info/{pid}", description="\f")
async def get_use_cases_info(pid: str):
    """\f
    处理 `GET /project/llm/functional/info/{pid}` 请求，并沿用既有状态码、响应 schema 与安全边界。

    参数:
        `pid`：项目 ID。"""
    result = find_out_use_cases_info(pid)
    if not result:
        return {"status": Status.LLM_APIS_ANALYSIS_FAILURE.value, "reason": "项目用例相关信息获取失败", "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "项目用例相关信息获取成功", "data": result}


# 按功能目标和输出格式生成测试用例，指定目标时由服务补充检索。
@router.post("/project/llm/functional/case", description="\f")
async def functional_test_case(item: FunctionalTestInvokeModel):
    """\f
    处理 `POST /project/llm/functional/case` 请求，并沿用既有状态码、响应 schema 与安全边界。

    参数:
        `item`：待处理的条目。"""
    item_dict = item.model_dump()
    pid = item_dict["pid"]
    info = item_dict["info"]
    test_type = item_dict["test_type"]
    output_type = item_dict["output_type"]
    use_case_name = item_dict["use_case_name"]
    result = generate_functional_test_cases(pid, info, test_type, output_type, use_case_name)
    if not result:
        return {"status": Status.LLM_APIS_ANALYSIS_FAILURE.value, "reason": "项目系统功能性测试用例生成失败",
                "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "项目系统功能性测试用例生成成功", "data": result}


# 读取或生成非功能性需求分析，保留历史错误信封。
@router.get("/project/llm/nfunctional/info/{pid}", description="\f")
async def get_nfunctional_info(pid: str):
    """\f
    处理 `GET /project/llm/nfunctional/info/{pid}` 请求，并沿用既有状态码、响应 schema 与安全边界。

    参数:
        `pid`：项目 ID。"""
    result = find_out_nonfunctional_info(pid)
    if not result:
        return {"status": Status.LLM_APIS_ANALYSIS_FAILURE.value, "reason": "项目非功能性需求信息获取失败",
                "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "项目非功能性需求信息获取成功", "data": result}


# 按方法名称检索测试知识并生成非功能用例。
@router.post("/project/llm/nfunctional/case", description="\f")
async def nfunctional_test_case(item: NFunctionalTestInvokeModel):
    """\f
    处理 `POST /project/llm/nfunctional/case` 请求，并沿用既有状态码、响应 schema 与安全边界。

    参数:
        `item`：待处理的条目。"""
    item_dict = item.model_dump()
    pid = item_dict["pid"]
    info = item_dict["info"]
    method_name = item_dict["method_name"]
    result = generate_nonfunctional_test_cases(pid, info, method_name)
    if not result:
        return {"status": Status.LLM_APIS_ANALYSIS_FAILURE.value, "reason": "项目系统非功能性测试用例生成失败",
                "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "项目系统非功能性测试用例生成成功", "data": result}


# 读取或生成验收需求分析，不能在只读验收中无条件调用此 GET。
@router.get("/project/llm/acceptance/info/{pid}", description="\f")
async def get_acceptance_info(pid: str):
    """\f
    处理 `GET /project/llm/acceptance/info/{pid}` 请求，并沿用既有状态码、响应 schema 与安全边界。

    参数:
        `pid`：项目 ID。"""
    result = find_out_requirement_info(pid)
    if not result:
        return {"status": Status.LLM_APIS_ANALYSIS_FAILURE.value, "reason": "项目信息获取失败", "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "项目信息获取成功", "data": result}


# 结合需求信息与验收测试知识生成用例，失败不编码为成功。
@router.post("/project/llm/acceptance/case", description="\f")
async def acceptance_test_case(item: AcceptanceTestInvokeModel):
    """\f
    处理 `POST /project/llm/acceptance/case` 请求，并沿用既有状态码、响应 schema 与安全边界。

    参数:
        `item`：待处理的条目。"""
    item_dict = item.model_dump()
    pid = item_dict["pid"]
    info = item_dict["info"]
    result = generate_acceptance_test_cases(pid, info)
    if not result:
        return {"status": Status.LLM_APIS_ANALYSIS_FAILURE.value, "reason": "验收测试用例生成失败", "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "验收测试用例生成成功", "data": result}


# 校验模型后读取或生成测试计划，缓存和保存由应用服务处理。
@router.get("/project/llm/plan/{pid}/{llm_name}", description="\f")
async def test_plan(pid: str, llm_name: str):
    """\f
    处理 `GET /project/llm/plan/{pid}/{llm_name}` 请求，并沿用既有状态码、响应 schema 与安全边界。

    参数:
        `pid`：项目 ID。
        `llm_name`：界面选择的模型标识。"""
    _validate_llm_name(llm_name)
    result = generate_test_plan(pid, llm_name)
    if not result:
        return {"status": Status.LLM_APIS_ANALYSIS_FAILURE.value, "reason": "测试计划生成失败", "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "测试计划生成成功", "data": result}


# 显式重新生成并更新测试计划，PUT 响应不改变历史错误格式。
@router.put("/project/llm/plan/update/{pid}/{llm_name}", description="\f")
async def test_plan_again(pid: str, llm_name: str):
    """\f
    处理 `PUT /project/llm/plan/update/{pid}/{llm_name}` 请求，并沿用既有状态码、响应 schema 与安全边界。

    参数:
        `pid`：项目 ID。
        `llm_name`：界面选择的模型标识。"""
    _validate_llm_name(llm_name)
    result = generate_test_plan_again(pid, llm_name)
    if not result:
        return {"status": Status.LLM_APIS_ANALYSIS_FAILURE.value, "reason": "测试计划生成失败", "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "测试计划生成成功", "data": result}


# 先确认项目存在，再查询摘要、计划和菜单的完整就绪状态。
@router.get("/project/analysis/status/{pid}", description="\f")
async def project_analysis_status(pid: str):
    """\f
    处理 `GET /project/analysis/status/{pid}` 请求，并沿用既有状态码、响应 schema 与安全边界。

    参数:
        `pid`：项目 ID。"""
    if not await asyncio.to_thread(testProjectDao.find_project, pid):
        return {
            "status": Status.LOGIN_FAILURE.value,
            "reason": "项目不存在",
            "data": False,
        }
    result = await get_project_analysis_status(pid)
    return {
        "status": Status.SUCCESS.value,
        "reason": "项目分析状态获取成功",
        "data": result,
    }


# 校验模型并包装计划 SSE；客户端断开会传入生成过程，取消异常继续向上传播。
@router.post("/project/llm/plan/stream", description="\f")
# 旧计划流保持延迟保存和取消语义，不能因 Agent 工作台接入而隐式触发额外模型调用。
async def test_plan_stream(item: PlanStreamRequest, request: Request):
    """\f
    处理 `POST /project/llm/plan/stream` 请求，并沿用既有状态码、响应 schema 与安全边界。

    参数:
        `item`：待处理的条目。
        `request`：当前请求对象。"""
    _validate_llm_name(item.llm_name)

    async def event_source():
        """把计划事件编码为 SSE；断连停止发送，普通异常只在连接仍存活时输出安全错误事件。"""
        try:
            async for message in stream_test_plan(
                item.pid,
                item.llm_name,
                item.regenerate,
                is_disconnected=request.is_disconnected,
            ):
                if await request.is_disconnected():
                    return
                yield _sse_message(message["event"], message["data"])
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if not await request.is_disconnected():
                yield _sse_message("error", _stream_error(exc))

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# 按 operation 包装统一工作流 SSE，并将客户端断连检查交给应用服务。
@router.post("/project/llm/workflow/stream", description="\f")
# workflow SSE 必须继续沿用 legacy 路由、事件顺序和安全错误信封。
async def llm_workflow_stream(item: WorkflowStreamRequest, request: Request):
    """\f
    处理 `POST /project/llm/workflow/stream` 请求，并沿用既有状态码、响应 schema 与安全边界。

    参数:
        `item`：待处理的条目。
        `request`：当前请求对象。"""
    _validate_llm_name(item.llm_name)

    async def event_source():
        """持续编码工作流事件；取消不吞掉，断连后不追加错误或成功帧。"""
        try:
            async for message in stream_llm_workflow(
                item.operation,
                item.pid,
                item.llm_name,
                item.payload,
                item.regenerate,
                is_disconnected=request.is_disconnected,
            ):
                if await request.is_disconnected():
                    return
                yield _sse_message(message["event"], message["data"])
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if not await request.is_disconnected():
                yield _sse_message("error", _stream_error(exc))

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
