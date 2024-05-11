import os.path

from fastapi import APIRouter, UploadFile
from dao import testProjectDao
from tools.status import Status
from tools import fileTools

router = APIRouter()


@router.post("/project/add/{name}")
async def add_project(name: str):
    pid = testProjectDao.add_project(name)
    if pid:
        return {"status": Status.SUCCESS.value, "reason": "成功建立新项目", "data": pid}
    else:
        return {"status": Status.PROJECT_ADD_FAILURE.value,
                "reason": "项目建立失败",
                "data": False}


@router.post("/uploadFile/{pid}/{doctype}")
async def upload_file(file: UploadFile, pid: str, doctype: int):
    # 上传的是知识库
    filepath = ""
    if doctype == 1:
        filepath = "static/projects/" + pid + "/knowledge"
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
    # 上传的是业务文档
    if doctype == 2:
        filepath = "static/projects/" + pid + "/testdoc"
        if not os.path.isdir(filepath):
            os.makedirs(filepath)
        file_save = fileTools.upload_file(file, filepath)
        if file_save["result"]:
            file_path_save = testProjectDao.add_project_testdoc(pid, file_save["filepath"])
            if file_path_save:
                return {"status": Status.SUCCESS.value, "reason": "上传文档成功", "data": True}
            else:
                return {"status": Status.FILE_PATH_SAVE_FAILURE.value, "reason": "上传文档出现问题", "data": False}
        else:
            return {"status": Status.FILE_UPLOAD_FAILURE.value, "reason": "上传文档失败", "data": False}
