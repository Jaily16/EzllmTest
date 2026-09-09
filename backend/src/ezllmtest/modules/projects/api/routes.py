# 提供项目、资料和状态接口，调用项目应用服务并保留稳定响应格式。
import asyncio

from fastapi import APIRouter, UploadFile
from fastapi.responses import JSONResponse
import ezllmtest.modules.projects.ports.repository as testProjectDao
import ezllmtest.modules.projects.application.setup as projectSetupService
import ezllmtest.modules.projects.application.workflow_status as projectWorkflowStatusService
from ezllmtest.modules.projects.application.setup import ProjectSetupError
from ezllmtest.shared.status import Status
import ezllmtest.modules.projects.application.files as fileTools
from ezllmtest.modules.generation.public import InfoModel

router = APIRouter()



# 创建并保存项目 ID，明确属于业务写入接口。
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


# 按项目 ID 查询已有项目名称；不因此创建运行或消费任务。
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


# 将上传绑定到明确项目和资料类别，交给资料登记流程处理，不能按客户端路径写任意位置。
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
        file_save = fileTools.upload_file(file, filepath)
        if file_save["result"]:
            file_path_save = testProjectDao.add_project_design_testdoc(pid, file_save["filepath"])
            if file_path_save:
                return {"status": Status.SUCCESS.value, "reason": "上传文档成功", "data": True}
            else:
                return {"status": Status.FILE_PATH_SAVE_FAILURE.value, "reason": "上传文档出现问题", "data": False}
        else:
            return {"status": Status.FILE_UPLOAD_FAILURE.value, "reason": "上传文档失败", "data": False}


# 把指定类型的项目分析内容交给项目公开接口保存。
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


# 更新指定项目信息类型的内容，保持现有失败响应语义。
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


# 按项目和信息类型返回已有记录，不通过读取接口隐式生成内容。
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


# 这两个历史 GET 路径可能分析并登记项目类型，不能直接作为无副作用只读查询。
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
    """把准备状态异常转换为稳定响应，只公开允许的错误类别和消息。"""
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


# 读取并返回项目资料准备状态，准备异常转换为统一安全响应。
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


# 显式确认资料完整性并持久化准备状态，不在此调用模型。
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


# 从准备状态及有效产物推导工作流阶段和允许路由，不启动生成。
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
