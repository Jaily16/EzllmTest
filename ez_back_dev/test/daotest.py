import pytest
from toollib.guid import SnowFlake
from sqlalchemy.orm import sessionmaker
from app.config import get_settings
from sqlalchemy import create_engine
from dao import testProjectDao
from tools import documentTools
from vectorstore.loader import load_document


def test_snowflake():
    snow = SnowFlake()
    uid = snow.gen_uid()
    print(uid)
    print(type(uid))


def test_db_connect():
    engine = create_engine(get_settings().database_url)
    session = sessionmaker(bind=engine)
    print(engine)
    print(session)


def test_add_project():
    testProjectDao.add_project("测试项目3")


def test_add_knowledge():
    pid = "Ez1788637745694900224"
    path = "static/projects/Ez1788637745694900224/knowledge/2023SEE_ch05_lecture-software-cost-metrics-&-control.pdf"
    testProjectDao.add_project_knowledge(pid, path)


def test_find_knowledges():
    pid = "Ez1788815504316563456"
    result = testProjectDao.find_project_knowledge_list(pid)
    print(len(result))


def test_find_docs():
    pid = "Ez1788815504316563456"
    result = testProjectDao.find_project_testdoc_list(pid)
    print(result[0].path)


def test_add_type():
    pid = "Ez1789225848298012672"
    testProjectDao.add_project_type(pid, True)


def test_count_tokens():
    pid = "Ez1789225848298012672"
    test_paths = testProjectDao.find_project_testdoc_list(pid)
    if test_paths:
        total_tokens = 0
        for testdoc in test_paths:
            doc = load_document(testdoc.path)
            doc_str = documentTools.docs_to_string(doc)
        # 知识库token值过多采用refine方式分析业务文档, 若不多则可以一次性全输入给llm模型
        print(total_tokens)


def test_find_name():
    pid = "Ez1789257412218191871"
    result = testProjectDao.find_project(pid)
    print(result)


def test_get_type():
    pid = "Ez1789569184871481344"
    result = testProjectDao.get_project_type(pid)
    print(result.overflow)


def test_project_info():
    pid = "Ez1790301634060877824"
    info = "1. 项目的单元构成：本项目的单元构成包括用户界面层(UI Layer)、应用逻辑层(Application Layer)、数据访问层(Data Access Layer)、第三方服务集成层(Third-party Service Integration Layer)、安全和性能优化层(Security and Performance Optimization Layer)、数据库层(Database Layer)和通用服务层(Common Service Layer)。其中，用户界面层提供用户界面，实现用户注册、登录、航班查询、预订机票、订单管理等功能；应用逻辑层处理用户请求和业务逻辑；数据访问层负责与数据库交互；第三方服务集成层集成第三方支付服务、短信、邮件服务等；安全和性能优化层实现用户身份认证、权限控制、系统性能优化等；数据库层存储系统的持久化数据；通用服务层提供日志记录、缓存管理、异常处理等通用服务组件。"
    info_type = 1
    print(testProjectDao.get_project_info(pid, info_type))


def test_delete():
    pid = "Ez1797579189918892032"
    testProjectDao.delete_project_all_info(pid)
    testProjectDao.delete_project_design_testdoc_list(pid)
    testProjectDao.delete_project_requirement_testdoc_list(pid)
    testProjectDao.delete_project_knowledge(pid)
    testProjectDao.delete_project_type(pid)
    testProjectDao.delete_project(pid)
