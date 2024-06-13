import os.path

from fastapi import APIRouter, UploadFile
from dao import testProjectDao
from service.llmAcceptanceTestService import find_out_requirement_info, generate_acceptance_test_cases
from service.llmApiTestService import find_out_apis_info, generate_api_test_cases
from service.llmDatabaseTestService import find_out_database_info, generate_db_test_cases
from service.llmFunctionalTestService import find_out_use_cases_info, generate_functional_test_cases
from service.llmNonfunctionalTestService import find_out_nonfunctional_info, generate_nonfunctional_test_cases
from service.llmTestPlanService import generate_test_plan, generate_test_plan_again
from service.llmUITestService import find_out_ui_info, generate_ui_test_cases
from tools.status import Status
from tools import fileTools, documentTools
from vectorstore.loader import load_document
from model.HttpModel import MenuModel, UnitTestInvokeModel, InfoModel, IntegrationTestInvokeModel, ApiTestInvokeModel, \
    UITestInvokeModel, DBTestInvokeModel, FunctionalTestInvokeModel, NFunctionalTestInvokeModel, \
    AcceptanceTestInvokeModel
from service.llmSummarizeService import start_test_summarize_analyze, get_test_menu, restart_test_summarize_analyze
from service.llmUnitTestService import (summarize_unit_info, find_out_test_unit_info,
                                        find_unit_test_knowledge, generate_test_cases, summarize_unit_info_again)
from service.llmIntegrationTestService import (get_integration_test_info, get_integration_description,
                                               find_integration_test_knowledge, generate_integration_test_cases)

router = APIRouter()


@router.post("/project/add/{name}")
async def add_project(name: str):
    pid = testProjectDao.add_project(name)
    if pid:
        return {"status": Status.SUCCESS.value, "reason": "成功生成并保存项目id", "data": pid}
    else:
        return {"status": Status.PROJECT_ADD_FAILURE.value,
                "reason": "项目建立失败",
                "data": False}


@router.get("/project/login/{pid}")
async def login_project(pid: str):
    result = testProjectDao.find_project(pid)
    if result is None:
        return {"status": Status.LOGIN_FAILURE, "reason": "请先创建项目", "data": False}
    elif not result:
        return {"status": Status.LOGIN_FAILURE, "reason": "登录失败", "data": False}
    else:
        return {"status": Status.LOGIN_FAILURE, "reason": "登录成功", "data": result.name}


@router.post("/uploadFile/{pid}/{doctype}")
async def upload_file(file: UploadFile, pid: str, doctype: int):
    # 上传的是知识库
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


@router.post("/project/info/add")
async def add_project_info(item: InfoModel):
    item_dict = item.dict()
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


@router.post("/project/info/update")
async def update_project_info(item: InfoModel):
    item_dict = item.dict()
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


@router.get("/project/info/{pid}/{info_type}")
async def get_project_info(pid: str, info_type: int):
    result = testProjectDao.get_project_info(pid, info_type)
    if not result:
        return {"status": Status.PROJECT_INFO_FAILURE.value,
                "reason": "未获取到项目相关的LLM信息",
                "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "成功获取项目LLM分析的相关信息", "data": result}


@router.get("/project/type/{pid}")
async def type_project(pid: str):
    total_requirement_tokens = 0
    total_design_tokens = 0
    requirement_overflow = False
    design_overflow = False
    requirement_test_paths = testProjectDao.find_project_requirement_testdoc_list(pid)
    design_test_paths = testProjectDao.find_project_design_testdoc_list(pid)
    if requirement_test_paths:
        for path in requirement_test_paths:
            doc = load_document(path.path)
            doc_str = documentTools.docs_to_string(doc)
            total_requirement_tokens += documentTools.num_tokens_from_string(doc_str)
            if total_requirement_tokens > 14500:
                requirement_overflow = True
                break
    else:
        return {"status": Status.PROJECT_ADD_FAILURE.value,
                "reason": "项目建立失败",
                "data": False}
    if design_test_paths:
        for path in design_test_paths:
            doc = load_document(path.path)
            doc_str = documentTools.docs_to_string(doc)
            total_design_tokens += documentTools.num_tokens_from_string(doc_str)
            if total_design_tokens > 14500:
                design_overflow = True
                break
    else:
        return {"status": Status.PROJECT_ADD_FAILURE.value,
                "reason": "项目建立失败",
                "data": False}
    # 知识库token值过多采用map-reduce方式分析业务文档, 若不多则可以一次性全输入给llm模型
    # 需求文档和设计文档都超token-4
    if requirement_overflow and design_overflow:
        if testProjectDao.add_project_type(pid, 4):
            return {"status": Status.SUCCESS.value, "reason": "成功分析并建立项目", "data": 4}
        else:
            return {"status": Status.PROJECT_ADD_FAILURE.value,
                    "reason": "项目分析失败",
                    "data": False}
    # 只是开发设计文档超token-3
    if design_overflow:
        if testProjectDao.add_project_type(pid, 3):
            return {"status": Status.SUCCESS.value, "reason": "成功分析并建立项目", "data": 3}
        else:
            return {"status": Status.PROJECT_ADD_FAILURE.value,
                    "reason": "项目分析失败",
                    "data": False}
    # 只是需求文档超token-2
    if requirement_overflow:
        if testProjectDao.add_project_type(pid, 2):
            return {"status": Status.SUCCESS.value, "reason": "成功分析并建立项目", "data": 2}
        else:
            return {"status": Status.PROJECT_ADD_FAILURE.value,
                    "reason": "项目分析失败",
                    "data": False}
    total_tokens = total_requirement_tokens + total_design_tokens
    # 两者都没超token，但加起来超了
    if total_tokens > 14500:
        if testProjectDao.add_project_type(pid, 1):
            return {"status": Status.SUCCESS.value, "reason": "成功分析并建立项目", "data": 1}
        else:
            return {"status": Status.PROJECT_ADD_FAILURE.value,
                    "reason": "项目分析失败",
                    "data": False}
    # 两者都没超token，加起来也没超
    else:
        if testProjectDao.add_project_type(pid, 0):
            return {"status": Status.SUCCESS.value, "reason": "成功分析并建立项目", "data": -1}
        else:
            return {"status": Status.PROJECT_ADD_FAILURE.value,
                    "reason": "项目分析失败",
                    "data": False}


@router.get("/project/llm/menu/analyze/{pid}")
async def analyze_testdoc_for_menu(pid: str):
    result = start_test_summarize_analyze(pid)
    if not result:
        return {"status": Status.LLM_MENU_ANALYSIS_FAILURE.value, "reason": "业务文档分析失败", "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "业务文档分析完成", "data": result}


@router.get("/project/llm/menu/analyze/update/{pid}/{llm_name}")
async def reanalyze_testdoc(pid: str, llm_name: str):
    result = restart_test_summarize_analyze(pid, llm_name)
    if not result:
        return {"status": Status.LLM_MENU_ANALYSIS_FAILURE.value, "reason": "业务文档重新分析失败", "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "业务文档重新分析完成", "data": result}


@router.post("/project/llm/menu/acquire")
async def acquire_menu(item: MenuModel):
    item_dict = item.dict()
    summary = item_dict["summary"]
    result = get_test_menu(summary)
    return {"status": Status.SUCCESS.value, "reason": "测试类型分析完成", "data": result}


@router.get("/project/llm/unit/menu/{pid}/{llm_name}")
async def unit_test_menu(pid: str, llm_name: str):
    result = summarize_unit_info(pid, llm_name)
    if not result:
        return {"status": Status.LLM_MENU_ANALYSIS_FAILURE.value, "reason": "单元测试分析失败", "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "单元测试类型分析完成", "data": result}


@router.get("/project/llm/unit/menu/update/{pid}/{llm_name}")
async def unit_test_menu_again(pid: str, llm_name: str):
    result = summarize_unit_info_again(pid, llm_name)
    if not result:
        return {"status": Status.LLM_MENU_ANALYSIS_FAILURE.value, "reason": "单元测试重新分析失败", "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "单元测试类型重新分析完成", "data": result}


@router.get("/project/llm/unit/info/{pid}/{name}/{llm_name}")
async def unit_test_info(pid: str, name: str, llm_name: str):
    result = find_out_test_unit_info(pid, name, llm_name)
    if not result:
        return {"status": Status.LLM_MENU_ANALYSIS_FAILURE.value, "reason": "单元信息获取失败", "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "单元信息获取成功", "data": result}


@router.get("/project/llm/unit/knowledge/{pid}/{method_type}")
async def unit_test_knowledge(pid: str, method_type: int):
    result = find_unit_test_knowledge(pid, method_type)
    if not result:
        return {"status": Status.LLM_MENU_ANALYSIS_FAILURE.value, "reason": "单元测试知识库信息获取失败", "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "单元测试知识库信息获取成功", "data": result}


@router.post("/project/llm/unit/case")
async def unit_test_case(item: UnitTestInvokeModel):
    item_dict = item.dict()
    test_knowledge = item_dict["unit_test_knowledge"]
    static_method = item_dict["static_method"]
    unit_test_method_knowledge = item_dict["unit_test_method_knowledge"]
    unit = item_dict["unit"]
    unit_info = item_dict["unit_info"]
    output_type = item_dict["output_type"]
    llm_name = item_dict["llm_name"]
    result = generate_test_cases(test_knowledge, static_method, unit_test_method_knowledge,
                                 unit, unit_info, output_type, llm_name)
    if not result:
        return {"status": Status.LLM_MENU_ANALYSIS_FAILURE.value, "reason": "单元测试用例生成失败", "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "单元测试用例生成成功", "data": result}


@router.post("/project/llm/integration/menu")
async def acquire_integration_menu(item: MenuModel):
    item_dict = item.dict()
    summary = item_dict["summary"]
    result = get_integration_test_info(summary)
    if not result:
        return {"status": Status.LLM_MENU_ANALYSIS_FAILURE.value, "reason": "集成测试类型分析失败", "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "集成测试类型分析成功", "data": result}


@router.get("/project/llm/integration/info/{pid}/{integration_type}/{name}")
async def find_out_integration_test_info(pid: str, integration_type: int, name: str):
    if integration_type <= 1:
        result = get_integration_description(pid, integration_type)
    else:
        result = get_integration_description(pid, integration_type, name)
    if not result:
        return {"status": Status.INTEGRATION_INFO_GET_FAILURE.value, "reason": "集成测试信息分析失败", "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "集成测试信息分析成功", "data": result}


@router.get("/project/llm/integration/knowledge/{pid}/{strategy_type}")
async def integration_test_knowledge(pid: str, strategy_type: int):
    result = find_integration_test_knowledge(pid, strategy_type)
    if not result:
        return {"status": Status.LLM_MENU_ANALYSIS_FAILURE.value, "reason": "集成测试知识库信息获取失败", "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "集成测试知识库信息获取成功", "data": result}


@router.post("/project/llm/integration/case")
async def integration_test_case(item: IntegrationTestInvokeModel):
    item_dict = item.dict()
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
        return {"status": Status.LLM_MENU_ANALYSIS_FAILURE.value, "reason": "单元测试用例生成失败", "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "单元测试用例生成成功", "data": result}


@router.get("/project/llm/api/info/{pid}")
async def get_apis_info(pid: str):
    result = find_out_apis_info(pid)
    if not result:
        return {"status": Status.LLM_APIS_ANALYSIS_FAILURE.value, "reason": "项目api接口信息获取失败", "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "项目api接口信息获取成功", "data": result}


@router.post("/project/llm/api/case")
async def api_test_case(item: ApiTestInvokeModel):
    item_dict = item.dict()
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


@router.get("/project/llm/ui/info/{pid}")
async def get_ui_info(pid: str):
    result = find_out_ui_info(pid)
    if not result:
        return {"status": Status.LLM_APIS_ANALYSIS_FAILURE.value, "reason": "项目前端UI设计信息获取失败", "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "项目前端UI设计信息获取成功", "data": result}


@router.post("/project/llm/ui/case")
async def ui_test_case(item: UITestInvokeModel):
    item_dict = item.dict()
    pid = item_dict["pid"]
    info = item_dict["info"]
    result = generate_ui_test_cases(pid, info)
    if not result:
        return {"status": Status.LLM_APIS_ANALYSIS_FAILURE.value, "reason": "项目前端UI测试用例生成失败", "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "项目前端UI测试用例生成成功", "data": result}


@router.get("/project/llm/db/info/{pid}")
async def get_db_info(pid: str):
    result = find_out_database_info(pid)
    if not result:
        return {"status": Status.LLM_APIS_ANALYSIS_FAILURE.value, "reason": "项目数据库设计信息获取失败", "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "项目数据库设计信息获取成功", "data": result}


@router.post("/project/llm/db/case")
async def db_test_case(item: DBTestInvokeModel):
    item_dict = item.dict()
    pid = item_dict["pid"]
    info = item_dict["info"]
    result = generate_db_test_cases(pid, info)
    if not result:
        return {"status": Status.LLM_APIS_ANALYSIS_FAILURE.value, "reason": "项目数据库测试用例生成失败", "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "项目数据库测试用例生成成功", "data": result}


@router.get("/project/llm/functional/info/{pid}")
async def get_use_cases_info(pid: str):
    result = find_out_use_cases_info(pid)
    if not result:
        return {"status": Status.LLM_APIS_ANALYSIS_FAILURE.value, "reason": "项目用例相关信息获取失败", "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "项目用例相关信息获取成功", "data": result}


@router.post("/project/llm/functional/case")
async def functional_test_case(item: FunctionalTestInvokeModel):
    item_dict = item.dict()
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


@router.get("/project/llm/nfunctional/info/{pid}")
async def get_nfunctional_info(pid: str):
    result = find_out_nonfunctional_info(pid)
    if not result:
        return {"status": Status.LLM_APIS_ANALYSIS_FAILURE.value, "reason": "项目非功能性需求信息获取失败",
                "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "项目非功能性需求信息获取成功", "data": result}


@router.post("/project/llm/nfunctional/case")
async def nfunctional_test_case(item: NFunctionalTestInvokeModel):
    item_dict = item.dict()
    pid = item_dict["pid"]
    info = item_dict["info"]
    method_name = item_dict["method_name"]
    result = generate_nonfunctional_test_cases(pid, info, method_name)
    if not result:
        return {"status": Status.LLM_APIS_ANALYSIS_FAILURE.value, "reason": "项目系统非功能性测试用例生成失败",
                "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "项目系统非功能性测试用例生成成功", "data": result}


@router.get("/project/llm/acceptance/info/{pid}")
async def get_acceptance_info(pid: str):
    result = find_out_requirement_info(pid)
    if not result:
        return {"status": Status.LLM_APIS_ANALYSIS_FAILURE.value, "reason": "项目信息获取失败", "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "项目信息获取成功", "data": result}


@router.post("/project/llm/acceptance/case")
async def acceptance_test_case(item: AcceptanceTestInvokeModel):
    item_dict = item.dict()
    pid = item_dict["pid"]
    info = item_dict["info"]
    result = generate_acceptance_test_cases(pid, info)
    if not result:
        return {"status": Status.LLM_APIS_ANALYSIS_FAILURE.value, "reason": "验收测试用例生成失败", "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "验收测试用例生成成功", "data": result}


@router.get("/project/llm/plan/{pid}/{llm_name}")
async def test_plan(pid: str, llm_name: str):
    result = generate_test_plan(pid, llm_name)
    if not result:
        return {"status": Status.LLM_APIS_ANALYSIS_FAILURE.value, "reason": "测试计划生成失败", "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "测试计划生成成功", "data": result}


@router.put("/project/llm/plan/update/{pid}/{llm_name}")
async def test_plan_again(pid: str, llm_name: str):
    result = generate_test_plan_again(pid, llm_name)
    if not result:
        return {"status": Status.LLM_APIS_ANALYSIS_FAILURE.value, "reason": "测试计划生成失败", "data": False}
    else:
        return {"status": Status.SUCCESS.value, "reason": "测试计划生成成功", "data": result}