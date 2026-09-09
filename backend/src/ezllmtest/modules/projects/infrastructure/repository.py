# 通过装配的数据库会话访问项目记录，向外返回应用层快照。
from ezllmtest.modules.projects.schemas.records import ProjectRecord, DocumentRecord, ProjectTypeRecord
import json
import re
from datetime import datetime, timezone

from toollib.guid import SnowFlake
from sqlalchemy import and_
from ezllmtest.platform.database.connection import Session
from ezllmtest.platform.settings import get_settings
from ezllmtest.modules.projects.infrastructure.models import TestProject, TestProjectKnowledge, TestProjectRequirementTestdoc, TestProjectDesignTestdoc, TestProjectType, TestProjectInfo
from ezllmtest.modules.projects.domain.info_type import InfoType



# 添加新项目
def add_project(name):
    """生成 Snowflake 项目 ID 后在独立数据库会话中插入项目，提交成功才返回 ID，结束时关闭会话。"""
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

    finally:
        session.close()


# 查找项目
def find_project(pid):
    """按项目 ID 查询并返回不带 ORM 会话的只读快照；不存在与查询失败分别返回 None 和 False。"""
    session = Session()
    try:
        result = session.query(TestProject).filter(TestProject.id == pid).first()
        return None if result is None else ProjectRecord(result.id, result.name)
    except Exception as e:
        print("encountered exception {}".format(e))
        return False

    finally:
        session.close()


# 删除项目
def delete_project(pid):
    """删除指定项目记录并提交，始终关闭会话；不会由源码清理流程调用。"""
    session = Session()
    try:
        result = session.query(TestProject).filter(TestProject.id == pid).first()
        session.delete(result)
        session.commit()
        return True
    except Exception as e:
        print("encountered exception {}".format(e))
        return False

    finally:
        session.close()


def _add_project_document_path(model, pid, path):
    """在项目资料表登记受控路径，事务失败回滚，不能让部分登记冒充上传完成。"""
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
    """通过统一登记函数添加知识文档路径，不在仓储内读取文件正文。"""
    return _add_project_document_path(TestProjectKnowledge, pid, path)


# 查找所有知识库路径
def find_project_knowledge_list(pid):
    """查询项目知识文档路径并转换为 DocumentRecord，离开函数前关闭数据库会话。"""
    session = Session()
    try:
        knowledge_paths = session.query(TestProjectKnowledge).filter_by(id=pid).all()
        return [DocumentRecord(row.id, row.path) for row in knowledge_paths]
    except Exception as e:
        print("encountered exception {}".format(e))
        return False

    finally:
        session.close()


# 删除所有知识库路径
def delete_project_knowledge(pid):
    """仅删除指定项目的知识文档登记记录并提交，不负责磁盘文件删除。"""
    session = Session()
    try:
        session.query(TestProjectKnowledge).filter_by(id=pid).delete()
        session.commit()
        return True
    except Exception as e:
        print("encountered exception {}".format(e))
        return False

    finally:
        session.close()


# 添加项目文档路径
def add_project_requirement_testdoc(pid, path):
    """通过统一登记函数添加需求资料路径，文件上传由应用层负责。"""
    return _add_project_document_path(TestProjectRequirementTestdoc, pid, path)


# 查找所有业务需求文档路径
def find_project_requirement_testdoc_list(pid):
    """查询项目需求资料路径并返回会话外可用的文档快照。"""
    session = Session()
    try:
        testdoc_paths = session.query(TestProjectRequirementTestdoc).filter_by(id=pid).all()
        return [DocumentRecord(row.id, row.path) for row in testdoc_paths]
    except Exception as e:
        print("encountered exception {}".format(e))
        return False

    finally:
        session.close()


# 删除所有业务需求文档路径
def delete_project_requirement_testdoc_list(pid):
    """删除指定项目的需求文档登记并提交，结束时关闭会话。"""
    session = Session()
    try:
        session.query(TestProjectRequirementTestdoc).filter_by(id=pid).delete()
        session.commit()
        return True
    except Exception as e:
        print("encountered exception {}".format(e))
        return False

    finally:
        session.close()


def add_project_design_testdoc(pid, path):
    """通过统一登记函数添加设计资料路径，不执行文档解析或索引。"""
    return _add_project_document_path(TestProjectDesignTestdoc, pid, path)


# 查找所有业务开发文档路径
def find_project_design_testdoc_list(pid):
    """查询项目设计资料的路径快照，不把 ORM 对象传出仓储。"""
    session = Session()
    try:
        testdoc_paths = session.query(TestProjectDesignTestdoc).filter_by(id=pid).all()
        return [DocumentRecord(row.id, row.path) for row in testdoc_paths]
    except Exception as e:
        print("encountered exception {}".format(e))
        return False

    finally:
        session.close()


def get_project_setup_documents(pid):
    """项目存在时读取三组已登记路径，供准备服务核对资料完整性。"""
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
    """删除指定项目的设计文档登记并提交，不将此操作等同于源码清理。"""
    session = Session()
    try:
        session.query(TestProjectDesignTestdoc).filter_by(id=pid).delete()
        session.commit()
        return True
    except Exception as e:
        print("encountered exception {}".format(e))
        return False

    finally:
        session.close()


# 添加项目类型
def add_project_type(pid, overflow):
    """保存项目类型信息并提交本次事务，失败不留下半份类型判断。"""
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
    """读取项目类型并返回独立快照，缺失与存储异常使用不同返回值。"""
    session = Session()
    try:
        result = session.query(TestProjectType).filter(TestProjectType.id == pid).first()
        return None if result is None else ProjectTypeRecord(result.id, result.overflow)
    except Exception as e:
        print("encountered exception {}".format(e))
        return False

    finally:
        session.close()


# 删除项目类型信息
def delete_project_type(pid):
    """删除指定项目的类型记录并提交，保持会话关闭边界。"""
    session = Session()
    try:
        result = session.query(TestProjectType).filter(TestProjectType.id == pid).first()
        session.delete(result)
        session.commit()
        return True
    except Exception as e:
        print("encountered exception {}".format(e))
        return False

    finally:
        session.close()


# 添加项目LLM的分析信息
def add_project_info(pid, info_type, info):
    """新增指定项目信息记录，提交与回滚由本仓储会话负责。"""
    session = Session()
    new_project_info = TestProjectInfo(id=pid, info_type=info_type, info=info)
    try:
        session.add(new_project_info)
        session.commit()
        return True
    except Exception as e:
        print("encountered exception {}".format(e))
        return False

    finally:
        session.close()


# 更新项目的LLM分析信息
def update_project_info(pid, info_type, info):
    """更新当前项目对应类型的信息，异常回滚并关闭会话。"""
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

    finally:
        session.close()


# 获取项目的LLM分析信息
def get_project_info(pid, info_type):
    """读取指定项目和信息类型的记录，返回数据快照而非开放数据库会话。"""
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

    finally:
        session.close()


def save_project_analysis_bundle(pid, summary, plan, menu_json):
    """把摘要、菜单和计划作为同一次分析结果提交，失败不部分覆盖已有信息。"""
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
    """严格校验分析元数据允许的键与模型策略格式，非法字段不能随结果写入。"""
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
    """在同一事务保存分析信息和 revision 产物记录，使恢复身份与有效结果一致。"""
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
    """批量保存指定项目信息值，事务边界防止失败时留下部分新结果。"""
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
    """按项目 ID 删除历史信息记录并提交；这是业务删除能力，本轮注释核验不调用。"""
    session = Session()
    try:
        session.query(TestProjectInfo).filter_by(id=pid).delete()
        session.commit()
        return True
    except Exception as e:
        print("encountered exception {}".format(e))
        return False

    finally:
        session.close()


# 项目分析的原子提交跨项目说明与生成产物，由 bootstrap 显式提供产物映射。
TestProjectWorkflowArtifact = None
def bind_workflow_model(model):
    """由装配层注入产物 ORM 类型，使项目三件套与有效产物可在同一事务中保存。"""
    global TestProjectWorkflowArtifact
    TestProjectWorkflowArtifact = model
