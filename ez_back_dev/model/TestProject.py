from sqlalchemy import Column, String, ForeignKey, INT, Text
from sqlalchemy.orm import DeclarativeBase

# 创建数据库表对应的映射类
class Base(DeclarativeBase):
    pass


class TestProject(Base):
    __tablename__ = 'tb_test_project'
    id = Column(String(21), primary_key=True)
    name = Column(String(100), nullable=False)


class TestProjectKnowledge(Base):
    __tablename__ = 'tb_project_knowledge'
    id = Column(String(21), ForeignKey("tb_test_project.id"), primary_key=True)
    path = Column(String(500), primary_key=True)


class TestProjectRequirementTestdoc(Base):
    __tablename__ = 'tb_project_requirement_testdoc'
    id = Column(String(21), ForeignKey("tb_test_project.id"), primary_key=True)
    path = Column(String(500), primary_key=True)


class TestProjectDesignTestdoc(Base):
    __tablename__ = 'tb_project_design_testdoc'
    id = Column(String(21), ForeignKey("tb_test_project.id"), primary_key=True)
    path = Column(String(500), primary_key=True)


class TestProjectType(Base):
    __tablename__ = 'tb_project_type'
    id = Column(String(21), ForeignKey("tb_test_project.id"), primary_key=True)
    overflow = Column(INT)


class TestProjectInfo(Base):
    __tablename__ = 'tb_project_info'
    id = Column(String(21), ForeignKey("tb_test_project.id"), primary_key=True)
    info_type = Column(INT, primary_key=True)
    info = Column(Text, nullable=False)
