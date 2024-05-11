from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, ForeignKey

# 创建数据库表对应的映射类
Base = declarative_base()


class TestProject(Base):
    __tablename__ = 'tb_test_project'
    id = Column(String(21), primary_key=True)
    name = Column(String(100), nullable=False)


class TestProjectKnowledge(Base):
    __tablename__ = 'tb_project_knowledge'
    id = Column(String(21), ForeignKey("tb_test_project.id"), primary_key=True)
    path = Column(String(500), primary_key=True)


class TestProjectTestdoc(Base):
    __tablename__ = 'tb_project_testdoc'
    id = Column(String(21), ForeignKey("tb_test_project.id"), primary_key=True)
    path = Column(String(500), primary_key=True)
