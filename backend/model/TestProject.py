from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Index, INT, String, Text
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


def _utcnow():
    """返回带 UTC 时区信息的当前时间。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TestProjectWorkflowArtifact(Base):
    __tablename__ = "tb_project_workflow_artifact"

    project_id = Column(
        String(21), ForeignKey("tb_test_project.id"), primary_key=True
    )
    artifact_key = Column(String(80), primary_key=True)
    input_hash = Column(String(64), primary_key=True)
    source_revision = Column(String(64), primary_key=True)
    prompt_version = Column(String(32), primary_key=True)
    model_label = Column(String(32), primary_key=True)
    content = Column(Text, nullable=False)
    metadata_json = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        Index(
            "idx_workflow_artifact_project_key",
            "project_id",
            "artifact_key",
        ),
    )


WorkflowArtifact = TestProjectWorkflowArtifact
