import json
from datetime import datetime, timezone

from toollib.guid import SnowFlake
from sqlalchemy import create_engine, and_
from sqlalchemy.orm import sessionmaker
from app.config import get_settings
from model.TestProject import (TestProject, TestProjectKnowledge, TestProjectRequirementTestdoc,
                               TestProjectDesignTestdoc, TestProjectType, TestProjectInfo,
                               TestProjectWorkflowArtifact)
from tools.InfoType import InfoType

engine = create_engine(get_settings().database_url, pool_pre_ping=True)
Session = sessionmaker(bind=engine)


# 添加新项目
def add_project(name):
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
    session = Session()
    try:
        result = session.query(TestProject).filter(TestProject.id == pid).first()
        return result
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


# 删除项目
def delete_project(pid):
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
    return _add_project_document_path(TestProjectKnowledge, pid, path)


# 查找所有知识库路径
def find_project_knowledge_list(pid):
    session = Session()
    try:
        knowledge_paths = session.query(TestProjectKnowledge).filter_by(id=pid).all()
        return knowledge_paths
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


# 删除所有知识库路径
def delete_project_knowledge(pid):
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
    return _add_project_document_path(TestProjectRequirementTestdoc, pid, path)


# 查找所有业务需求文档路径
def find_project_requirement_testdoc_list(pid):
    session = Session()
    try:
        testdoc_paths = session.query(TestProjectRequirementTestdoc).filter_by(id=pid).all()
        return testdoc_paths
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


# 删除所有业务需求文档路径
def delete_project_requirement_testdoc_list(pid):
    session = Session()
    try:
        session.query(TestProjectRequirementTestdoc).filter_by(id=pid).delete()
        session.commit()
        return True
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


def add_project_design_testdoc(pid, path):
    return _add_project_document_path(TestProjectDesignTestdoc, pid, path)


# 查找所有业务开发文档路径
def find_project_design_testdoc_list(pid):
    session = Session()
    try:
        testdoc_paths = session.query(TestProjectDesignTestdoc).filter_by(id=pid).all()
        return testdoc_paths
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


def get_project_setup_documents(pid):
    """Return one-session document paths for setup status and finalization."""
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
    session = Session()
    try:
        result = session.query(TestProjectType).filter(TestProjectType.id == pid).first()
        return result
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


# 删除项目类型信息
def delete_project_type(pid):
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
    """Atomically upsert the initial summary, test plan, and test menu."""
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
    """Atomically replace the revision artifact and all legacy bundle rows."""
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
        or not isinstance(metadata, dict)
        or set(metadata) - {"budget_profile", "call_count", "operation"}
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
    """Atomically upsert an arbitrary group of project analysis values."""
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
    session = Session()
    try:
        session.query(TestProjectInfo).filter_by(id=pid).delete()
        session.commit()
        return True
    except Exception as e:
        print("encountered exception {}".format(e))
        return False
