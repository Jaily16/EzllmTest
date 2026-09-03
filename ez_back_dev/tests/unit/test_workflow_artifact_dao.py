import json
import os
import re
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session as SqlAlchemySession
from sqlalchemy.orm import sessionmaker


os.environ["PYTHON_DOTENV_DISABLED"] = "1"
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"

from dao import workflowArtifactDao
from dao.workflowArtifactDao import (
    WorkflowArtifactRecord,
    get_fresh_artifact,
    invalidate_project_artifacts,
    save_artifact,
)
from model.TestProject import (
    Base,
    TestProject as ProjectRow,
    TestProjectWorkflowArtifact as ArtifactRow,
)


from repo_paths import REPO_ROOT as PROJECT_ROOT
SQL_PATH = PROJECT_ROOT / "ezllmtest.sql"


def _session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as session:
        session.add(ProjectRow(id="Ez1", name="project"))
        session.commit()
    return engine, factory


def _record(
    *,
    source_revision: str = "rev-1",
    content: str = "final result",
    metadata: dict | None = None,
) -> WorkflowArtifactRecord:
    return WorkflowArtifactRecord(
        project_id="Ez1",
        artifact_key="api_info",
        input_hash="input-1",
        source_revision=source_revision,
        prompt_version="prompt-v1",
        model_label="DeepSeek",
        content=content,
        metadata=metadata or {"budget_profile": "analysis"},
    )


def test_changed_document_revision_makes_artifact_stale(monkeypatch):
    _engine, factory = _session_factory()
    monkeypatch.setattr(workflowArtifactDao, "Session", factory)

    assert save_artifact(_record())
    assert get_fresh_artifact(
        "Ez1", "api_info", "rev-2", "input-1", "prompt-v1", "DeepSeek"
    ) is None

    result = get_fresh_artifact(
        "Ez1", "api_info", "rev-1", "input-1", "prompt-v1", "DeepSeek"
    )
    assert result is not None
    assert result.content == "final result"
    assert result.metadata == {"budget_profile": "analysis"}


def test_save_artifact_upserts_same_composite_key_atomically(monkeypatch):
    engine, factory = _session_factory()
    monkeypatch.setattr(workflowArtifactDao, "Session", factory)

    assert save_artifact(_record(content="first"))
    assert save_artifact(_record(content="second", metadata={"call_count": 2}))

    with factory() as session:
        rows = session.scalars(select(ArtifactRow)).all()
    assert len(rows) == 1
    assert rows[0].content == "second"
    assert json.loads(rows[0].metadata_json) == {"call_count": 2}

    class FailingCommitSession(SqlAlchemySession):
        def commit(self):
            raise RuntimeError("sanitized persistence failure")

    failing_factory = sessionmaker(bind=engine, class_=FailingCommitSession)
    monkeypatch.setattr(workflowArtifactDao, "Session", failing_factory)
    assert not save_artifact(_record(content="must not replace second"))

    with factory() as session:
        row = session.scalar(select(ArtifactRow))
    assert row.content == "second"


def test_save_artifact_supports_planned_positional_interface(monkeypatch):
    _engine, factory = _session_factory()
    monkeypatch.setattr(workflowArtifactDao, "Session", factory)

    assert save_artifact(
        "Ez1",
        "api_info",
        "rev-1",
        "input-1",
        "prompt-v1",
        "DeepSeek",
        "value",
        {"call_count": 1},
    )
    result = get_fresh_artifact(
        "Ez1", "api_info", "rev-1", "input-1", "prompt-v1", "DeepSeek"
    )
    assert result is not None
    assert result.content == "value"


@pytest.mark.parametrize(
    "metadata",
    [
        {"reasoning": "private trace"},
        {"nested": {"prompt_body": "private prompt"}},
        {"provider_exception": "raw upstream response"},
    ],
)
def test_save_artifact_rejects_sensitive_metadata(monkeypatch, metadata):
    _engine, factory = _session_factory()
    monkeypatch.setattr(workflowArtifactDao, "Session", factory)

    with pytest.raises(ValueError, match="metadata"):
        save_artifact(_record(metadata=metadata))

    with factory() as session:
        assert session.scalar(select(ArtifactRow)) is None


def test_invalidate_project_artifacts_marks_only_other_revisions_stale(monkeypatch):
    _engine, factory = _session_factory()
    monkeypatch.setattr(workflowArtifactDao, "Session", factory)
    assert save_artifact(_record(source_revision="rev-old"))
    assert save_artifact(_record(source_revision="rev-current"))

    assert invalidate_project_artifacts("Ez1", "rev-current")
    with factory() as session:
        old_row = session.scalar(
            select(ArtifactRow).where(ArtifactRow.source_revision == "rev-old")
        )
    assert old_row is not None
    assert json.loads(old_row.metadata_json)["stale_for_source_revision"] == (
        "rev-current"
    )
    assert get_fresh_artifact(
        "Ez1", "api_info", "rev-old", "input-1", "prompt-v1", "DeepSeek"
    ) is None
    current = get_fresh_artifact(
        "Ez1", "api_info", "rev-current", "input-1", "prompt-v1", "DeepSeek"
    )
    assert current is not None
    assert "stale_for_source_revision" not in current.metadata


def test_base_schema_contains_workflow_artifact_table_and_index():
    sql = SQL_PATH.read_text(encoding="utf-8")

    assert "CREATE TABLE `tb_project_workflow_artifact`" in sql
    assert re.search(r"INDEX\s+`?idx_workflow_artifact_project_key`?", sql, re.I)
