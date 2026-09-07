import os

from fastapi import UploadFile


def upload_file(file: UploadFile, path: str):
    """保存已通过类型与路径校验的项目上传文件。

    参数:
        `file`：沿用签名中 `UploadFile` 类型约束的输入。
        `path`：目标路径。"""
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
        with open(f"{filepath}", "wb") as f:
            f.write(filebytes)
        f.close()
        return {"filepath": filepath, "result": True}
    except Exception as e:
        print("encountered exception {}".format(e))
        return {"reason": str(e), "result": False}
