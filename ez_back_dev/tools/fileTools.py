import os

from fastapi import UploadFile


def upload_file(file: UploadFile, path: str):
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
