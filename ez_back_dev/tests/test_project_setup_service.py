import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker


os.environ["PYTHON_DOTENV_DISABLED"] = "1"
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["ZHIPU_API_KEY"] = ""
os.environ["DASHSCOPE_API_KEY"] = ""
os.environ["DEEPSEEK_API_KEY"] = ""
os.environ["MOONSHOT_API_KEY"] = ""

from dao import testProjectDao
from model.TestProject import (
    Base,
    TestProject as ProjectRow,
    TestProjectDesignTestdoc as DesignRow,
    TestProjectKnowledge as KnowledgeRow,
    TestProjectRequirementTestdoc as RequirementRow,
    TestProjectType as ProjectTypeRow,
)
from service import projectSetupService
from service.projectSetupService import (
    ProjectSetupPersistenceError,
    ProjectSetupValidationError,
)


def _paths(tmp_path: Path, *, knowledge=1, requirements=1, design=1):
    result = {"knowledge": [], "requirements": [], "design": []}
    for group, count in {
        "knowledge": knowledge,
        "requirements": requirements,
        "design": design,
    }.items():
        for index in range(count):
            path = tmp_path / group / f"{group}-{index}.txt"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"fixed {group} {index}", encoding="utf-8")
            result[group].append(str(path))
    return result


@pytest.mark.parametrize(
    ("counts", "expected_stage"),
    [
        ((0, 0, 0), "project_created"),
        ((1, 0, 0), "knowledge_uploaded"),
        ((0, 1, 0), "requirements_uploaded"),
        ((0, 0, 1), "design_uploaded"),
    ],
)
def test_setup_status_uses_explicit_upload_stages(
    tmp_path, monkeypatch, counts, expected_stage
):
    snapshot = _paths(
        tmp_path,
        knowledge=counts[0],
        requirements=counts[1],
        design=counts[2],
    )
    monkeypatch.setattr(
        projectSetupService.testProjectDao,
        "get_project_setup_documents",
        lambda _pid: snapshot,
    )

    status = projectSetupService.get_status("Ez1")

    assert status.project_exists is True
    assert status.stage == expected_stage
    assert status.document_counts == {
        "knowledge": counts[0],
        "requirements": counts[1],
        "design": counts[2],
    }
    assert all(
        Path(name).name == name
        for names in status.document_files.values()
        for name in names
    )
    assert all(
        str(tmp_path) not in name
        for names in status.document_files.values()
        for name in names
    )


def test_ready_status_computes_revision_and_exposes_finalize(tmp_path, monkeypatch):
    snapshot = _paths(tmp_path)
    monkeypatch.setattr(
        projectSetupService.testProjectDao,
        "get_project_setup_documents",
        lambda _pid: snapshot,
    )
    monkeypatch.setattr(
        projectSetupService, "compute_project_source_revision", lambda _pid: "rev-1"
    )
    monkeypatch.setattr(
        projectSetupService, "get_fresh_artifact", lambda *_args: None
    )

    status = projectSetupService.get_status("Ez1")

    assert status.stage == "documents_ready"
    assert status.source_revision == "rev-1"
    assert status.allowed_actions == ["finalize"]
    assert status.message == "项目资料已齐全，可以确认创建"


def test_status_masks_document_revision_failure_details(tmp_path, monkeypatch):
    snapshot = _paths(tmp_path)
    monkeypatch.setattr(
        projectSetupService.testProjectDao,
        "get_project_setup_documents",
        lambda _pid: snapshot,
    )
    monkeypatch.setattr(
        projectSetupService,
        "compute_project_source_revision",
        lambda _pid: (_ for _ in ()).throw(RuntimeError("private-server-path")),
    )

    with pytest.raises(ProjectSetupPersistenceError) as caught:
        projectSetupService.get_status("Ez1")

    assert str(caught.value) == "项目文档校验失败"
    assert "private-server-path" not in str(caught.value)


def test_finalize_is_idempotent_and_writes_setup_artifact_once(
    tmp_path, monkeypatch
):
    snapshot = _paths(tmp_path)
    stored = {}
    writes = []
    invalidations = []
    index_invalidations = []
    type_analyses = []
    monkeypatch.setattr(
        projectSetupService.testProjectDao,
        "get_project_setup_documents",
        lambda _pid: snapshot,
    )
    monkeypatch.setattr(
        projectSetupService, "compute_project_source_revision", lambda _pid: "rev-1"
    )
    monkeypatch.setattr(
        projectSetupService,
        "get_fresh_artifact",
        lambda *_args: stored.get("artifact"),
    )

    def fake_save(record):
        writes.append(record)
        stored["artifact"] = record
        return True

    monkeypatch.setattr(projectSetupService, "save_artifact", fake_save)
    monkeypatch.setattr(
        projectSetupService,
        "invalidate_project_artifacts",
        lambda pid, revision: invalidations.append((pid, revision)) or True,
    )
    monkeypatch.setattr(
        projectSetupService,
        "invalidate_project_indexes",
        lambda pid: index_invalidations.append(pid),
        raising=False,
    )
    monkeypatch.setattr(
        projectSetupService,
        "analyze_project_type",
        lambda pid: type_analyses.append(pid) or 0,
    )

    first = projectSetupService.finalize("Ez1")
    second = projectSetupService.finalize("Ez1")

    assert first.stage == second.stage == "setup_complete"
    assert first.source_revision == second.source_revision == "rev-1"
    assert len(writes) == 1
    assert invalidations == [("Ez1", "rev-1")]
    assert index_invalidations == ["Ez1"]
    assert type_analyses == ["Ez1"]


def test_finalize_missing_documents_returns_422_without_deleting_uploads(
    tmp_path, monkeypatch
):
    snapshot = _paths(tmp_path, design=0)
    deleted = []
    monkeypatch.setattr(
        projectSetupService.testProjectDao,
        "get_project_setup_documents",
        lambda _pid: snapshot,
    )
    monkeypatch.setattr(
        testProjectDao,
        "delete_project_knowledge",
        lambda _pid: deleted.append("knowledge"),
    )
    monkeypatch.setattr(
        testProjectDao,
        "delete_project_requirement_testdoc_list",
        lambda _pid: deleted.append("requirements"),
    )
    monkeypatch.setattr(
        testProjectDao,
        "delete_project_design_testdoc_list",
        lambda _pid: deleted.append("design"),
    )

    with pytest.raises(ProjectSetupValidationError) as caught:
        projectSetupService.finalize("Ez1")

    assert caught.value.status_code == 422
    assert caught.value.status.document_counts["knowledge"] == 1
    assert caught.value.status.document_counts["requirements"] == 1
    assert caught.value.status.document_counts["design"] == 0
    assert deleted == []


def test_add_project_type_is_an_idempotent_upsert(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as session:
        session.add(ProjectRow(id="Ez1", name="project"))
        session.commit()
    monkeypatch.setattr(testProjectDao, "Session", factory)

    assert testProjectDao.add_project_type("Ez1", 1)
    assert testProjectDao.add_project_type("Ez1", 4)

    with factory() as session:
        rows = session.scalars(select(ProjectTypeRow)).all()
    assert len(rows) == 1
    assert rows[0].overflow == 4


def test_document_path_saves_are_idempotent_for_group_retry(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as session:
        session.add(ProjectRow(id="Ez1", name="project"))
        session.commit()
    monkeypatch.setattr(testProjectDao, "Session", factory)

    saves = (
        (testProjectDao.add_project_knowledge, KnowledgeRow, "knowledge.txt"),
        (
            testProjectDao.add_project_requirement_testdoc,
            RequirementRow,
            "requirements.txt",
        ),
        (testProjectDao.add_project_design_testdoc, DesignRow, "design.txt"),
    )
    for save, model, path in saves:
        assert save("Ez1", path)
        assert save("Ez1", path)
        with factory() as session:
            assert len(session.scalars(select(model)).all()) == 1
