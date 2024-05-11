import pytest
from toollib.guid import SnowFlake
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dao import testProjectDao


def test_snowflake():
    snow = SnowFlake()
    uid = snow.gen_uid()
    print(uid)
    print(type(uid))


def test_db_connect():
    engine = create_engine("mysql+pymysql://root:050598@localhost/ezllmtest_dev")
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
    print(result[0].path)


def test_find_docs():
    pid = "Ez1788815504316563456"
    result = testProjectDao.find_project_testdoc_list(pid)
    print(result[0].path)
