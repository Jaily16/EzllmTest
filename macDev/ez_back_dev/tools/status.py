from enum import Enum


# 定义后端的状态码枚举(用4位数区分http状态码)
class Status(Enum):
    SUCCESS = 2001
    PROJECT_ADD_FAILURE = 5001
    FILE_UPLOAD_FAILURE = 5902
    FILE_PATH_SAVE_FAILURE = 5903
