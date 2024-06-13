from toollib.guid import SnowFlake
from sqlalchemy import create_engine, and_
from sqlalchemy.orm import sessionmaker
from model.TestProject import (TestProject, TestProjectKnowledge, TestProjectRequirementTestdoc,
                               TestProjectDesignTestdoc, TestProjectType, TestProjectInfo)

engine = create_engine("mysql+pymysql://root:050598@localhost/ezllmtest_dev")
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


# 添加知识库路径
def add_project_knowledge(pid, path):
    session = Session()
    new_project_knowledge = TestProjectKnowledge(id=pid, path=path)
    try:
        session.add(new_project_knowledge)
        session.commit()
        return True
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


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
    session = Session()
    new_project_testdoc = TestProjectRequirementTestdoc(id=pid, path=path)
    try:
        session.add(new_project_testdoc)
        session.commit()
        return True
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


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
    session = Session()
    new_project_testdoc = TestProjectDesignTestdoc(id=pid, path=path)
    try:
        session.add(new_project_testdoc)
        session.commit()
        return True
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


# 查找所有业务开发文档路径
def find_project_design_testdoc_list(pid):
    session = Session()
    try:
        testdoc_paths = session.query(TestProjectDesignTestdoc).filter_by(id=pid).all()
        return testdoc_paths
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


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
    new_project_type = TestProjectType(id=pid, overflow=overflow)
    try:
        session.add(new_project_type)
        session.commit()
        return True
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


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
