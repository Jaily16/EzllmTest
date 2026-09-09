"""生成域拥有有效产物映射，表名和字段保持 V6 契约。"""
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text
from ezllmtest.platform.database.models import Base

def _utcnow():
    """读取 UTC 当前时间后移除 tzinfo，以匹配现有数据库列的无时区时间表示。"""
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
