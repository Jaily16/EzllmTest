import json
import re
from datetime import datetime, timezone

from toollib.guid import SnowFlake
from sqlalchemy import create_engine, and_
from sqlalchemy.orm import sessionmaker
from infrastructure.config import get_settings
from model.TestProject import (TestProject, TestProjectKnowledge, TestProjectRequirementTestdoc,
                               TestProjectDesignTestdoc, TestProjectType, TestProjectInfo,
                               TestProjectWorkflowArtifact)
from tools.InfoType import InfoType

engine = create_engine(get_settings().database_url, pool_pre_ping=True)
Session = sessionmaker(bind=engine)


# 添加新项目
def add_project(name):
    """新增项目，并遵循现有调用契约。

    参数:
        `name`：目标名称。

    副作用:
        可能按照既有事务边界更新 MySQL 持久化状态。"""
    session = Session()
    snow = SnowFlake()
    uid = snow.gen_uid()
    pid = "Ez" + str(uid)
    new_project = TestProject(id=pid, name=name)
    try:  # 写一个 try 把可能出错的代码放进去。
        session.add(new_project)
        session.commit()
        return new_project.id
    except Exception as e:  # 写一个except
        print("encountered exception {}".format(e))
        return False


# 查找项目
def find_project(pid):
    """查找项目，并遵循现有调用契约。

    参数:
        `pid`：项目 ID。

    副作用:
        可能按照既有仓储契约读取 MySQL 持久化状态。"""
    session = Session()
    try:
        result = session.query(TestProject).filter(TestProject.id == pid).first()
        return result
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


# 删除项目
def delete_project(pid):
    """删除项目，并遵循现有调用契约。

    参数:
        `pid`：项目 ID。

    副作用:
        可能按照既有事务边界更新 MySQL 持久化状态。"""
    session = Session()
    try:
        result = session.query(TestProject).filter(TestProject.id == pid).first()
        session.delete(result)
        session.commit()
        return True
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


def _add_project_document_path(model, pid, path):
    """新增项目文档路径，并遵循现有调用契约。

    参数:
        `model`：调用方传入的现有参数。
        `pid`：项目 ID。
        `path`：目标路径。

    副作用:
        可能按照既有事务边界更新 MySQL 持久化状态。"""
    session = Session()
    try:
        existing = session.query(model).filter_by(id=pid, path=path).first()
        if existing is None:
            session.add(model(id=pid, path=path))
        session.commit()
        return True
    except Exception:
        session.rollback()
        return False
    finally:
        session.close()


# 添加知识库路径
def add_project_knowledge(pid, path):
    """新增项目知识库，并遵循现有调用契约。"""
    return _add_project_document_path(TestProjectKnowledge, pid, path)


# 查找所有知识库路径
def find_project_knowledge_list(pid):
    """查找项目知识库LIST，并遵循现有调用契约。

    参数:
        `pid`：项目 ID。

    副作用:
        可能按照既有仓储契约读取 MySQL 持久化状态。"""
    session = Session()
    try:
        knowledge_paths = session.query(TestProjectKnowledge).filter_by(id=pid).all()
        return knowledge_paths
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


# 删除所有知识库路径
def delete_project_knowledge(pid):
    """删除项目知识库，并遵循现有调用契约。

    参数:
        `pid`：项目 ID。

    副作用:
        可能按照既有事务边界更新 MySQL 持久化状态。"""
    session = Session()
    try:
        session.query(TestProjectKnowledge).filter_by(id=pid).delete()
        session.commit()
        return True
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


# 添加项目文档路径
def add_project_requirement_testdoc(pid, path):
    """新增项目需求testdoc，并遵循现有调用契约。"""
    return _add_project_document_path(TestProjectRequirementTestdoc, pid, path)


# 查找所有业务需求文档路径
def find_project_requirement_testdoc_list(pid):
    """查找项目需求testdoc LIST，并遵循现有调用契约。

    参数:
        `pid`：项目 ID。

    副作用:
        可能按照既有仓储契约读取 MySQL 持久化状态。"""
    session = Session()
    try:
        testdoc_paths = session.query(TestProjectRequirementTestdoc).filter_by(id=pid).all()
        return testdoc_paths
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


# 删除所有业务需求文档路径
def delete_project_requirement_testdoc_list(pid):
    """删除项目需求testdoc LIST，并遵循现有调用契约。

    参数:
        `pid`：项目 ID。

    副作用:
        可能按照既有事务边界更新 MySQL 持久化状态。"""
    session = Session()
    try:
        session.query(TestProjectRequirementTestdoc).filter_by(id=pid).delete()
        session.commit()
        return True
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


def add_project_design_testdoc(pid, path):
    """新增项目设计testdoc，并遵循现有调用契约。"""
    return _add_project_document_path(TestProjectDesignTestdoc, pid, path)


# 查找所有业务开发文档路径
def find_project_design_testdoc_list(pid):
    """查找项目设计testdoc LIST，并遵循现有调用契约。

    参数:
        `pid`：项目 ID。

    副作用:
        可能按照既有仓储契约读取 MySQL 持久化状态。"""
    session = Session()
    try:
        testdoc_paths = session.query(TestProjectDesignTestdoc).filter_by(id=pid).all()
        return testdoc_paths
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


def get_project_setup_documents(pid):
    """获取项目初始化文档，并遵循现有调用契约。

    参数:
        `pid`：项目 ID。

    副作用:
        可能按照既有仓储契约读取 MySQL 持久化状态。"""
    session = Session()
    try:
        project = session.query(TestProject).filter(TestProject.id == pid).first()
        if project is None:
            return None
        return {
            "knowledge": [
                row.path
                for row in session.query(TestProjectKnowledge).filter_by(id=pid).all()
            ],
            "requirements": [
                row.path
                for row in session.query(TestProjectRequirementTestdoc)
                .filter_by(id=pid)
                .all()
            ],
            "design": [
                row.path
                for row in session.query(TestProjectDesignTestdoc)
                .filter_by(id=pid)
                .all()
            ],
        }
    except Exception:
        session.rollback()
        return False
    finally:
        session.close()


# 删除所有业务开发文档路径
def delete_project_design_testdoc_list(pid):
    """删除项目设计testdoc LIST，并遵循现有调用契约。

    参数:
        `pid`：项目 ID。

    副作用:
        可能按照既有事务边界更新 MySQL 持久化状态。"""
    session = Session()
    try:
        session.query(TestProjectDesignTestdoc).filter_by(id=pid).delete()
        session.commit()
        return True
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


# 添加项目类型
def add_project_type(pid, overflow):
    """新增项目类型，并遵循现有调用契约。

    参数:
        `pid`：项目 ID。
        `overflow`：调用方传入的现有参数。

    副作用:
        可能按照既有事务边界更新 MySQL 持久化状态。"""
    session = Session()
    try:
        project_type = session.query(TestProjectType).filter(
            TestProjectType.id == pid
        ).first()
        if project_type is None:
            session.add(TestProjectType(id=pid, overflow=overflow))
        else:
            project_type.overflow = overflow
        session.commit()
        return True
    except Exception:
        session.rollback()
        return False
    finally:
        session.close()


# 获取项目类型信息
def get_project_type(pid):
    """获取项目类型，并遵循现有调用契约。

    参数:
        `pid`：项目 ID。

    副作用:
        可能按照既有仓储契约读取 MySQL 持久化状态。"""
    session = Session()
    try:
        result = session.query(TestProjectType).filter(TestProjectType.id == pid).first()
        return result
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


# 删除项目类型信息
def delete_project_type(pid):
    """删除项目类型，并遵循现有调用契约。

    参数:
        `pid`：项目 ID。

    副作用:
        可能按照既有事务边界更新 MySQL 持久化状态。"""
    session = Session()
    try:
        result = session.query(TestProjectType).filter(TestProjectType.id == pid).first()
        session.delete(result)
        session.commit()
        return True
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


# 添加项目LLM的分析信息
def add_project_info(pid, info_type, info):
    """新增项目信息，并遵循现有调用契约。

    参数:
        `pid`：项目 ID。
        `info_type`：调用方传入的现有参数。
        `info`：调用方传入的现有参数。

    副作用:
        可能按照既有事务边界更新 MySQL 持久化状态。"""
    session = Session()
    new_project_info = TestProjectInfo(id=pid, info_type=info_type, info=info)
    try:
        session.add(new_project_info)
        session.commit()
        return True
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


# 更新项目的LLM分析信息
def update_project_info(pid, info_type, info):
    """更新项目信息，并遵循现有调用契约。

    参数:
        `pid`：项目 ID。
        `info_type`：调用方传入的现有参数。
        `info`：调用方传入的现有参数。

    副作用:
        可能按照既有事务边界更新 MySQL 持久化状态。"""
    session = Session()
    try:
        p_info = session.query(TestProjectInfo).filter(
            and_(TestProjectInfo.id == pid, TestProjectInfo.info_type == info_type)).first()
        p_info.info = info
        session.commit()
        return True
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


# 获取项目的LLM分析信息
def get_project_info(pid, info_type):
    """获取项目信息，并遵循现有调用契约。

    参数:
        `pid`：项目 ID。
        `info_type`：调用方传入的现有参数。

    副作用:
        可能按照既有仓储契约读取 MySQL 持久化状态。"""
    session = Session()
    try:
        result = session.query(TestProjectInfo).filter(
            and_(TestProjectInfo.id == pid, TestProjectInfo.info_type == info_type)).first()
        if result is None:
            return False
        else:
            return result.info
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


def save_project_analysis_bundle(pid, summary, plan, menu_json):
    """保存项目分析数据包，并遵循现有调用契约。

    参数:
        `pid`：项目 ID。
        `summary`：调用方传入的现有参数。
        `plan`：调用方传入的现有参数。
        `menu_json`：调用方传入的现有参数。

    副作用:
        可能按照既有事务边界更新 MySQL 持久化状态。"""
    session = Session()
    try:
        values = (
            (InfoType.PROJECT_INITIAL_SUMMARY.value, summary),
            (InfoType.PROJECT_TEST_PLAN.value, plan),
            (InfoType.PROJECT_TEST_MENU.value, menu_json),
        )
        for info_type, info in values:
            project_info = session.query(TestProjectInfo).filter(
                and_(
                    TestProjectInfo.id == pid,
                    TestProjectInfo.info_type == info_type,
                )
            ).first()
            if project_info is None:
                session.add(
                    TestProjectInfo(id=pid, info_type=info_type, info=info)
                )
            else:
                project_info.info = info
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        print("encountered exception {}".format(e))
        return False
    finally:
        session.close()


def _valid_project_analysis_metadata(metadata):
    """返回当前valid项目分析元数据。"""
    if not isinstance(metadata, dict) or set(metadata) - {
        "budget_profile", "call_count", "operation", "model", "generation_policy"
    }:
        return False
    # Old callers remain valid; the extended identity is an all-or-nothing pair.
    if "model" not in metadata and "generation_policy" not in metadata:
        return True
    model = metadata.get("model")
    return (
        isinstance(model, str)
        and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}", model) is not None
        and metadata.get("generation_policy") in (
            "bounded-thinking-v1", "bounded-thinking-high-v2", "bounded-thinking-ds16k-v3"
        )
    )


def save_project_analysis_artifact_bundle(
    pid,
    summary,
    plan,
    menu_json,
    *,
    artifact_key,
    input_hash,
    source_revision,
    prompt_version,
    model_label,
    artifact_content,
    metadata_json,
):
    """保存项目分析产物数据包，并遵循现有调用契约。

    参数:
        `pid`：项目 ID。
        `summary`：调用方传入的现有参数。
        `plan`：调用方传入的现有参数。
        `menu_json`：调用方传入的现有参数。
        `artifact_key`：调用方传入的现有参数。
        `input_hash`：调用方传入的现有参数。
        `source_revision`：调用方传入的现有参数。
        `prompt_version`：调用方传入的现有参数。
        `model_label`：可信模型标签。
        `artifact_content`：调用方传入的现有参数。
        `metadata_json`：调用方传入的现有参数。

    副作用:
        可能按照既有事务边界更新 MySQL 持久化状态。"""
    try:
        menu = json.loads(menu_json)
        artifact_value = json.loads(artifact_content)
        metadata = json.loads(metadata_json)
    except (TypeError, json.JSONDecodeError):
        return False
    if (
        not isinstance(menu, dict)
        or not isinstance(artifact_value, dict)
        or artifact_value.get("summary") != summary
        or artifact_value.get("plan") != plan
        or artifact_value.get("menu") != menu
        or not _valid_project_analysis_metadata(metadata)
    ):
        return False

    session = Session()
    try:
        identity = (
            pid,
            artifact_key,
            input_hash,
            source_revision,
            prompt_version,
            model_label,
        )
        artifact = session.get(TestProjectWorkflowArtifact, identity)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if artifact is None:
            artifact = TestProjectWorkflowArtifact(
                project_id=pid,
                artifact_key=artifact_key,
                input_hash=input_hash,
                source_revision=source_revision,
                prompt_version=prompt_version,
                model_label=model_label,
                content=artifact_content,
                metadata_json=metadata_json,
                created_at=now,
                updated_at=now,
            )
            session.add(artifact)
        else:
            artifact.content = artifact_content
            artifact.metadata_json = metadata_json
            artifact.updated_at = now

        values = (
            (InfoType.PROJECT_INITIAL_SUMMARY.value, summary),
            (InfoType.PROJECT_TEST_PLAN.value, plan),
            (InfoType.PROJECT_TEST_MENU.value, menu_json),
        )
        for info_type, info in values:
            project_info = session.query(TestProjectInfo).filter(
                and_(
                    TestProjectInfo.id == pid,
                    TestProjectInfo.info_type == info_type,
                )
            ).first()
            if project_info is None:
                session.add(
                    TestProjectInfo(id=pid, info_type=info_type, info=info)
                )
            else:
                project_info.info = info
        session.commit()
        return True
    except Exception:
        session.rollback()
        return False
    finally:
        session.close()


def save_project_info_values(pid, values):
    """保存项目信息值，并遵循现有调用契约。

    参数:
        `pid`：项目 ID。
        `values`：调用方传入的现有参数。

    副作用:
        可能按照既有事务边界更新 MySQL 持久化状态。"""
    session = Session()
    try:
        for info_type, info in values.items():
            project_info = session.query(TestProjectInfo).filter(
                and_(
                    TestProjectInfo.id == pid,
                    TestProjectInfo.info_type == info_type,
                )
            ).first()
            if project_info is None:
                session.add(
                    TestProjectInfo(id=pid, info_type=info_type, info=info)
                )
            else:
                project_info.info = info
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        print("encountered exception {}".format(e))
        return False
    finally:
        session.close()


# 删除项目的所有LLM分析信息
def delete_project_all_info(pid):
    """删除项目ALL信息，并遵循现有调用契约。

    参数:
        `pid`：项目 ID。

    副作用:
        可能按照既有事务边界更新 MySQL 持久化状态。"""
    session = Session()
    try:
        session.query(TestProjectInfo).filter_by(id=pid).delete()
        session.commit()
        return True
    except Exception as e:
        print("encountered exception {}".format(e))
        return False
