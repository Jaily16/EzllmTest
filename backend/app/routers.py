import asyncio
import json
import os.path

from fastapi import APIRouter, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from infrastructure.persistence import project_repository as testProjectDao
from service.legacy.acceptance import find_out_requirement_info, generate_acceptance_test_cases
from service.legacy.api import find_out_apis_info, generate_api_test_cases
from service.legacy.database import find_out_database_info, generate_db_test_cases
from service.legacy.functional import find_out_use_cases_info, generate_functional_test_cases
from service.legacy.nonfunctional import find_out_nonfunctional_info, generate_nonfunctional_test_cases
from service.workflow.test_plan import generate_test_plan, generate_test_plan_again
from service.workflow.test_plan_stream import (
    TestPlanStreamError,
    get_project_analysis_status,
    stream_test_plan,
)
from service.workflow.stream_core import WorkflowStreamError
from service.workflow.stream import stream_llm_workflow
from service.project import setup as projectSetupService
from service.project import workflow_status as projectWorkflowStatusService
from service.project.setup import ProjectSetupError
from service.legacy.ui import find_out_ui_info, generate_ui_test_cases
from tools.status import Status
from infrastructure.llm.gateway import (
    LLMConfigurationError,
    LLMEmptyResponseError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
    ensure_supported_model,
)
from service.project import files as fileTools
from model.HttpModel import MenuModel, UnitTestInvokeModel, InfoModel, IntegrationTestInvokeModel, ApiTestInvokeModel, \
    UITestInvokeModel, DBTestInvokeModel, FunctionalTestInvokeModel, NFunctionalTestInvokeModel, \
    AcceptanceTestInvokeModel, PlanStreamRequest, WorkflowStreamRequest
from service.legacy.summarize import start_test_summarize_analyze, get_test_menu, restart_test_summarize_analyze
from service.legacy.unit import (summarize_unit_info, find_out_test_unit_info,
                                        find_unit_test_knowledge, generate_test_cases, summarize_unit_info_again)
from service.legacy.integration import (get_integration_test_info, get_integration_description,
                                               find_integration_test_knowledge, generate_integration_test_cases)

router = APIRouter()


def _validate_llm_name(llm_name: str) -> None:
    """校验LLM名称，并保持现有契约。"""
    ensure_supported_model(llm_name)


# legacy SSE 事件格式是公共 wire contract；这里只序列化安全 payload，不改变事件名和字段。
def _sse_message(event: str, data: dict) -> str:
    """编码符合 legacy 流协议的 SSE 消息。"""
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"


def _stream_error(exc: Exception) -> dict:
    """流式处理错误，并遵循现有调用契约。

    参数:
        `exc`：沿用签名中 `Exception` 类型约束的输入。

    返回:
        `dict`，内容保持现有调用方契约。"""
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


@router.post("/project/add/{name}", description="\f")
async def add_project(name: str):
    """\f
    处理 `POST /project/add/{name}` 请求，并沿用既有状态码、响应 schema 与安全边界。

    参数:
        `name`：目标名称。"""
    pid = testProjectDao.add_project(name)
    if pid:
        return {"status": Status.SUCCESS.value, "reason": "成功生成并保存项目id", "data": pid}
    else:
        return {"status": Status.PROJECT_ADD_FAILURE.value,
                "reason": "项目建立失败",
                "data": False}


@router.get("/project/login/{pid}", description="\f")
async def login_project(pid: str):
    """\f
    处理 `GET /project/login/{pid}` 请求，并沿用既有状态码、响应 schema 与安全边界。

    参数:
        `pid`：项目 ID。"""
    result = testProjectDao.find_project(pid)
    if result is None:
        return {"status": Status.LOGIN_FAILURE.value, "reason": "请先创建项目", "data": False}
    elif not result:
        return {"status": Status.LOGIN_FAILURE.value, "reason": "登录失败", "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "登录成功", "data": result.name}


@router.post("/uploadFile/{pid}/{doctype}", description="\f")
async def upload_file(file: UploadFile, pid: str, doctype: int):
    # 上传的是知识库
    """\f
    处理 `POST /uploadFile/{pid}/{doctype}` 请求，并沿用既有状态码、响应 schema 与安全边界。

    参数:
        `file`：沿用签名中 `UploadFile` 类型约束的输入。
        `pid`：项目 ID。
        `doctype`：沿用签名中 `int` 类型约束的输入。"""
    if doctype == 1:
        filepath = "static/projects/" + pid + "/knowledge/"
        if not os.path.isdir(filepath):
            os.makedirs(filepath)
        file_save = fileTools.upload_file(file, filepath)
        if file_save["result"]:
            file_path_save = testProjectDao.add_project_knowledge(pid, file_save["filepath"])
            if file_path_save:
                return {"status": Status.SUCCESS.value, "reason": "上传文档成功", "data": True}
            else:
                return {"status": Status.FILE_PATH_SAVE_FAILURE.value, "reason": "上传文档出现问题", "data": False}
        else:
            return {"status": Status.FILE_UPLOAD_FAILURE.value, "reason": "上传文档失败", "data": False}
    # 上传的是业务需求文档
    if doctype == 2:
        filepath = "static/projects/" + pid + "/testdoc/"
        if not os.path.isdir(filepath):
            os.makedirs(filepath)
        file_save = fileTools.upload_file(file, filepath)
        if file_save["result"]:
            file_path_save = testProjectDao.add_project_requirement_testdoc(pid, file_save["filepath"])
            if file_path_save:
                return {"status": Status.SUCCESS.value, "reason": "上传文档成功", "data": True}
            else:
                return {"status": Status.FILE_PATH_SAVE_FAILURE.value, "reason": "上传文档出现问题", "data": False}
        else:
            return {"status": Status.FILE_UPLOAD_FAILURE.value, "reason": "上传文档失败", "data": False}
    if doctype == 3:
        filepath = "static/projects/" + pid + "/testdoc/"
        if not os.path.isdir(filepath):
            os.makedirs(filepath)
        file_save = fileTools.upload_file(file, filepath)
        if file_save["result"]:
            file_path_save = testProjectDao.add_project_design_testdoc(pid, file_save["filepath"])
            if file_path_save:
                return {"status": Status.SUCCESS.value, "reason": "上传文档成功", "data": True}
            else:
                return {"status": Status.FILE_PATH_SAVE_FAILURE.value, "reason": "上传文档出现问题", "data": False}
        else:
            return {"status": Status.FILE_UPLOAD_FAILURE.value, "reason": "上传文档失败", "data": False}


@router.post("/project/info/add", description="\f")
async def add_project_info(item: InfoModel):
    """\f
    处理 `POST /project/info/add` 请求，并沿用既有状态码、响应 schema 与安全边界。

    参数:
        `item`：待处理的条目。"""
    item_dict = item.model_dump()
    pid = item_dict["pid"]
    info_type = item_dict["info_type"]
    info = item_dict["info"]
    result = testProjectDao.add_project_info(pid, info_type, info)
    if result:
        return {"status": Status.SUCCESS.value, "reason": "成功保存项目LLM分析的相关信息", "data": True}
    else:
        return {"status": Status.PROJECT_INFO_FAILURE.value,
                "reason": "项目LLM信息添加失败",
                "data": False}


@router.post("/project/info/update", description="\f")
async def update_project_info(item: InfoModel):
    """\f
    处理 `POST /project/info/update` 请求，并沿用既有状态码、响应 schema 与安全边界。

    参数:
        `item`：待处理的条目。"""
    item_dict = item.model_dump()
    pid = item_dict["pid"]
    info_type = item_dict["info_type"]
    info = item_dict["info"]
    result = testProjectDao.update_project_info(pid, info_type, info)
    if result:
        return {"status": Status.SUCCESS.value, "reason": "成功更新项目LLM分析的相关信息", "data": True}
    else:
        return {"status": Status.PROJECT_INFO_FAILURE.value,
                "reason": "项目LLM信息更新失败",
                "data": False}


@router.get("/project/info/{pid}/{info_type}", description="\f")
async def get_project_info(pid: str, info_type: int):
    """\f
    处理 `GET /project/info/{pid}/{info_type}` 请求，并沿用既有状态码、响应 schema 与安全边界。

    参数:
        `pid`：项目 ID。
        `info_type`：沿用签名中 `int` 类型约束的输入。"""
    result = testProjectDao.get_project_info(pid, info_type)
    if not result:
        return {"status": Status.PROJECT_INFO_FAILURE.value,
                "reason": "未获取到项目相关的LLM信息",
                "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "成功获取项目LLM分析的相关信息", "data": result}


@router.get("/project/type/{pid}", description="\f")
@router.get("/project/type/analyze/{pid}", description="\f")
async def type_project(pid: str):
    """\f
    处理 `GET /project/type/{pid}` 请求，并沿用既有状态码、响应 schema 与安全边界。

    参数:
        `pid`：项目 ID。"""
    try:
        overflow = await asyncio.to_thread(projectSetupService.analyze_project_type, pid)
    except ProjectSetupError:
        return {
            "status": Status.PROJECT_ADD_FAILURE.value,
            "reason": "项目分析失败",
            "data": False,
        }
    return {
        "status": Status.SUCCESS.value,
        "reason": "成功分析并建立项目",
        "data": -1 if overflow == 0 else overflow,
    }


def _project_setup_error_response(exc: ProjectSetupError) -> JSONResponse:
    """处理项目初始化错误响应并返回现有契约规定的结果。

    参数:
        `exc`：沿用签名中 `ProjectSetupError` 类型约束的输入。

    返回:
        `JSONResponse`，内容保持现有调用方契约。"""
    if exc.status is not None:
        data = exc.status.model_dump(mode="json")
    else:
        data = {
            "pid": exc.pid,
            "project_exists": False,
            "stage": None,
            "document_counts": {
                "knowledge": 0,
                "requirements": 0,
                "design": 0,
            },
            "document_files": {
                "knowledge": [],
                "requirements": [],
                "design": [],
            },
            "allowed_actions": ["create_project"],
            "source_revision": None,
            "message": str(exc),
        }
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": Status.PROJECT_ADD_FAILURE.value,
            "reason": str(exc),
            "data": data,
        },
    )


@router.get("/project/setup/status/{pid}", description="\f")
async def project_setup_status(pid: str):
    """\f
    处理 `GET /project/setup/status/{pid}` 请求，并沿用既有状态码、响应 schema 与安全边界。

    参数:
        `pid`：项目 ID。"""
    try:
        status = await asyncio.to_thread(projectSetupService.get_status, pid)
    except ProjectSetupError as exc:
        return _project_setup_error_response(exc)
    return {
        "status": Status.SUCCESS.value,
        "reason": "项目资料状态获取成功",
        "data": status.model_dump(mode="json"),
    }


@router.post("/project/setup/finalize/{pid}", description="\f")
async def finalize_project_setup(pid: str):
    """\f
    处理 `POST /project/setup/finalize/{pid}` 请求，并沿用既有状态码、响应 schema 与安全边界。

    参数:
        `pid`：项目 ID。"""
    try:
        status = await asyncio.to_thread(projectSetupService.finalize, pid)
    except ProjectSetupError as exc:
        return _project_setup_error_response(exc)
    return {
        "status": Status.SUCCESS.value,
        "reason": "项目资料已确认",
        "data": status.model_dump(mode="json"),
    }


@router.get("/project/workflow/status/{pid}", description="\f")
async def project_workflow_status(pid: str):
    """\f
    处理 `GET /project/workflow/status/{pid}` 请求，并沿用既有状态码、响应 schema 与安全边界。

    参数:
        `pid`：项目 ID。"""
    try:
        status = await asyncio.to_thread(
            projectWorkflowStatusService.get_project_workflow_status, pid
        )
    except ProjectSetupError as exc:
        return _project_setup_error_response(exc)
    return {
        "status": Status.SUCCESS.value,
        "reason": "项目工作流状态获取成功",
        "data": status.model_dump(mode="json"),
    }


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
        """将现有工作流事件异步转换为 SSE 输出流。"""
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
        """将现有工作流事件异步转换为 SSE 输出流。"""
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
