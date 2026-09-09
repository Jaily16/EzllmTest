# 处理项目上传文件的路径与登记流程，受保护资料不随源码目录重组迁移。
import os

from typing import Protocol, BinaryIO
from ezllmtest.platform.files import document_path

class UploadFile(Protocol):
    """上传端口只要求文件对象和名称，不依赖 HTTP 框架。"""
    file: BinaryIO
    filename: str


def upload_file(file: UploadFile, path: str):
    """在项目数据边界内处理明确上传文件，不把用户资料迁入源码目录或其他项目位置。"""
    try:
        filebytes = file.file.read()
        filename = file.filename
        old_name = filename.rsplit('.', 1)[0]
        postfix = os.path.splitext(filename)[-1]
        # 对文档名称进行格式化
        old_name = old_name.replace(" ", "-")
        new_name = old_name.replace(".", "_")
        format_filename = new_name + postfix
        filepath = os.path.join(path, format_filename)
        target = document_path(filepath)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("wb") as f:
            f.write(filebytes)
        f.close()
        return {"filepath": filepath, "result": True}
    except Exception as e:
        print("encountered exception {}".format(e))
        return {"reason": str(e), "result": False}
