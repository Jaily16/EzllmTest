from toollib.guid import SnowFlake
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from model.TestProject import TestProject, TestProjectKnowledge, TestProjectTestdoc

engine = create_engine("mysql+pymysql://root:lyl050598@localhost/ezllmtest_dev")
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


# 添加项目文档路径
def add_project_testdoc(pid, path):
    session = Session()
    new_project_testdoc = TestProjectTestdoc(id=pid, path=path)
    try:
        session.add(new_project_testdoc)
        session.commit()
        return True
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


# 查找所有业务文档路径
def find_project_testdoc_list(pid):
    session = Session()
    try:
        testdoc_paths = session.query(TestProjectTestdoc).filter_by(id=pid).all()
        return testdoc_paths
    except Exception as e:
        print("encountered exception {}".format(e))
        return False
