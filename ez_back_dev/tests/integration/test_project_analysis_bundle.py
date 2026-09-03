import json

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from dao import testProjectDao
from model.TestProject import (
    Base,
    TestProject as ProjectRow,
    TestProjectInfo as ProjectInfoRow,
)
from tools.InfoType import InfoType


def make_session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def test_save_project_analysis_bundle_inserts_all_values_with_one_api(monkeypatch):
    session_factory = make_session_factory()
    with session_factory() as session:
        session.add(ProjectRow(id="Ez1", name="project"))
        session.commit()
    monkeypatch.setattr(testProjectDao, "Session", session_factory)

    menu_json = json.dumps({"test_plan": True})
    assert testProjectDao.save_project_analysis_bundle(
        "Ez1", "summary", "plan", menu_json
    )

    with session_factory() as session:
        rows = session.scalars(
            select(ProjectInfoRow).where(ProjectInfoRow.id == "Ez1")
        ).all()
    values = {row.info_type: row.info for row in rows}
    assert values == {
        InfoType.PROJECT_INITIAL_SUMMARY.value: "summary",
        InfoType.PROJECT_TEST_PLAN.value: "plan",
        InfoType.PROJECT_TEST_MENU.value: menu_json,
    }


def test_save_project_analysis_bundle_rolls_back_every_value_on_commit_error(
    monkeypatch,
):
    session_factory = make_session_factory()
    old_values = {
        InfoType.PROJECT_INITIAL_SUMMARY.value: "old summary",
        InfoType.PROJECT_TEST_PLAN.value: "old plan",
        InfoType.PROJECT_TEST_MENU.value: "old menu",
    }
    with session_factory() as session:
        session.add(ProjectRow(id="Ez1", name="project"))
        session.add_all(
            ProjectInfoRow(id="Ez1", info_type=key, info=value)
            for key, value in old_values.items()
        )
        session.commit()
    monkeypatch.setattr(testProjectDao, "Session", session_factory)

    assert not testProjectDao.save_project_analysis_bundle(
        "Ez1", "new summary", "new plan", None
    )

    with session_factory() as session:
        rows = session.scalars(
            select(ProjectInfoRow).where(ProjectInfoRow.id == "Ez1")
        ).all()
    assert {row.info_type: row.info for row in rows} == old_values


def test_save_project_info_values_atomically_upserts_arbitrary_types(monkeypatch):
    session_factory = make_session_factory()
    with session_factory() as session:
        session.add(ProjectRow(id="Ez1", name="project"))
        session.add(ProjectInfoRow(id="Ez1", info_type=11, info="old"))
        session.commit()
    monkeypatch.setattr(testProjectDao, "Session", session_factory)

    assert testProjectDao.save_project_info_values(
        "Ez1", {11: "new api summary", 12: "api knowledge"}
    )

    with session_factory() as session:
        rows = session.scalars(
            select(ProjectInfoRow).where(ProjectInfoRow.id == "Ez1")
        ).all()
    assert {row.info_type: row.info for row in rows} == {
        11: "new api summary",
        12: "api knowledge",
    }
