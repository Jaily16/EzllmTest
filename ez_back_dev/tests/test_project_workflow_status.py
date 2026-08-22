import os
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


os.environ["PYTHON_DOTENV_DISABLED"] = "1"
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["ZHIPU_API_KEY"] = ""
os.environ["DASHSCOPE_API_KEY"] = ""
os.environ["DEEPSEEK_API_KEY"] = ""
os.environ["MOONSHOT_API_KEY"] = ""

from service import projectWorkflowStatusService
from service.projectWorkflowStatusService import (
    ArtifactFact,
    ProjectStage,
    derive_project_stage,
)
from model.TestProject import (
    Base,
    TestProject as ProjectRow,
    TestProjectWorkflowArtifact as ArtifactRow,
)
from tools.InfoType import InfoType


TEST_MENU = {
    "test_plan": True,
    "unit_test": False,
    "integration_test": False,
    "api_test": False,
    "ui_test": True,
    "db_test": False,
    "functional_test": False,
    "nonfunctional_test": False,
    "acceptance_test": False,
}


@pytest.mark.parametrize(
    ("setup", "analysis", "artifact_count", "expected"),
    [
        (False, False, 0, ProjectStage.SETUP_REQUIRED),
        (True, False, 0, ProjectStage.ANALYSIS_REQUIRED),
        (True, True, 0, ProjectStage.ANALYSIS_READY),
        (True, True, 1, ProjectStage.TESTING_IN_PROGRESS),
    ],
)
def test_project_stage_is_derived(setup, analysis, artifact_count, expected):
    assert derive_project_stage(setup, analysis, artifact_count) is expected


def test_all_required_case_artifacts_make_testing_ready():
    assert (
        derive_project_stage(
            True,
            True,
            2,
            completed_operations={"ui_case", "api_case"},
            required_operations={"ui_case", "api_case"},
        )
        is ProjectStage.TESTING_READY
    )


def _install_persisted_facts(
    monkeypatch,
    *,
    setup_stage,
    summary=False,
    plan=False,
    menu=False,
    artifacts=(),
):
    revision = "rev-2" if setup_stage in {"documents_ready", "setup_complete"} else None
    monkeypatch.setattr(
        projectWorkflowStatusService.projectSetupService,
        "get_status",
        lambda _pid: SimpleNamespace(
            stage=setup_stage,
            source_revision=revision,
        ),
    )
    values = {
        InfoType.PROJECT_INITIAL_SUMMARY.value: summary,
        InfoType.PROJECT_TEST_PLAN.value: plan,
        InfoType.PROJECT_TEST_MENU.value: menu,
    }
    monkeypatch.setattr(
        projectWorkflowStatusService.testProjectDao,
        "get_project_info",
        lambda _pid, info_type: values[info_type],
    )
    monkeypatch.setattr(
        projectWorkflowStatusService,
        "_load_artifact_facts",
        lambda _pid, _revision: tuple(artifacts),
    )


@pytest.mark.parametrize(
    (
        "setup_stage",
        "summary",
        "plan",
        "menu",
        "artifacts",
        "expected_stage",
        "expected_routes",
    ),
    [
        (
            "project_created",
            False,
            False,
            False,
            (),
            ProjectStage.SETUP_REQUIRED,
            ["/create"],
        ),
        (
            "setup_complete",
            False,
            False,
            False,
            (),
            ProjectStage.ANALYSIS_REQUIRED,
            ["/plan"],
        ),
        (
            "setup_complete",
            "summary",
            False,
            TEST_MENU,
            (),
            ProjectStage.ANALYSIS_REQUIRED,
            ["/plan"],
        ),
        (
            "setup_complete",
            "summary",
            "plan",
            TEST_MENU,
            (),
            ProjectStage.ANALYSIS_READY,
            ["/plan", "/menu", "/ui"],
        ),
        (
            "setup_complete",
            "summary",
            "plan",
            TEST_MENU,
            (ArtifactFact("ui_info", "rev-2", False),),
            ProjectStage.TESTING_IN_PROGRESS,
            ["/plan", "/menu", "/ui"],
        ),
        (
            "setup_complete",
            "summary",
            "plan",
            TEST_MENU,
            (ArtifactFact("ui_case", "rev-2", False),),
            ProjectStage.TESTING_READY,
            ["/plan", "/menu", "/ui"],
        ),
    ],
)
def test_workflow_status_table_is_derived_from_persisted_facts(
    monkeypatch,
    setup_stage,
    summary,
    plan,
    menu,
    artifacts,
    expected_stage,
    expected_routes,
):
    _install_persisted_facts(
        monkeypatch,
        setup_stage=setup_stage,
        summary=summary,
        plan=plan,
        menu=menu,
        artifacts=artifacts,
    )

    status = projectWorkflowStatusService.get_project_workflow_status("Ez1")

    assert status.stage is expected_stage
    assert status.allowed_routes == expected_routes


def test_changed_documents_lock_routes_and_report_stale_operations(monkeypatch):
    _install_persisted_facts(
        monkeypatch,
        setup_stage="documents_ready",
        summary="old summary",
        plan="old plan",
        menu=TEST_MENU,
        artifacts=(ArtifactFact("ui_case", "rev-1", True),),
    )

    status = projectWorkflowStatusService.get_project_workflow_status("Ez1")

    assert status.stage is ProjectStage.SETUP_REQUIRED
    assert status.allowed_routes == ["/create"]
    assert status.completed_operations == []
    assert status.stale_operations == ["project_analysis", "ui_case"]
    assert status.menu is None


def test_artifact_facts_are_revision_scoped_and_ignore_setup_artifact(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as session:
        session.add(ProjectRow(id="Ez1", name="project"))
        session.add_all(
            [
                ArtifactRow(
                    project_id="Ez1",
                    artifact_key="project_setup",
                    input_hash="setup",
                    source_revision="rev-2",
                    prompt_version="setup-v1",
                    model_label="system",
                    content="{}",
                    metadata_json="{}",
                ),
                ArtifactRow(
                    project_id="Ez1",
                    artifact_key="api_info",
                    input_hash="api",
                    source_revision="rev-2",
                    prompt_version="api-v1",
                    model_label="mock",
                    content="saved result",
                    metadata_json="{}",
                ),
                ArtifactRow(
                    project_id="Ez1",
                    artifact_key="ui_case",
                    input_hash="ui",
                    source_revision="rev-1",
                    prompt_version="ui-v1",
                    model_label="mock",
                    content="old result",
                    metadata_json='{"stale_for_source_revision":"rev-2"}',
                ),
            ]
        )
        session.commit()
    monkeypatch.setattr(projectWorkflowStatusService, "Session", factory)

    facts = projectWorkflowStatusService._load_artifact_facts("Ez1", "rev-2")

    assert facts == (
        ArtifactFact("api_info", "rev-2", False),
        ArtifactFact("ui_case", "rev-1", True),
    )


def test_artifact_facts_ignore_historical_session_only_case_rows(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as session:
        session.add(ProjectRow(id="Ez1", name="project"))
        session.add_all(
            [
                ArtifactRow(
                    project_id="Ez1",
                    artifact_key="nonfunctional_info",
                    input_hash="analysis",
                    source_revision="rev-2",
                    prompt_version="nonfunctional-info-v1",
                    model_label="mock",
                    content="saved analysis",
                    metadata_json="{}",
                ),
                ArtifactRow(
                    project_id="Ez1",
                    artifact_key="nonfunctional_case",
                    input_hash="performance",
                    source_revision="rev-2",
                    prompt_version="nonfunctional-case-v1",
                    model_label="mock",
                    content="historical selected case",
                    metadata_json="{}",
                ),
            ]
        )
        session.commit()
    monkeypatch.setattr(projectWorkflowStatusService, "Session", factory)

    facts = projectWorkflowStatusService._load_artifact_facts("Ez1", "rev-2")

    assert facts == (ArtifactFact("nonfunctional_info", "rev-2", False),)


def test_invalid_legacy_menu_does_not_unlock_analysis(monkeypatch):
    _install_persisted_facts(
        monkeypatch,
        setup_stage="setup_complete",
        summary="summary",
        plan="plan",
        menu="not valid json",
    )

    status = projectWorkflowStatusService.get_project_workflow_status("Ez1")

    assert status.stage is ProjectStage.ANALYSIS_REQUIRED
    assert status.allowed_routes == ["/plan"]
    assert status.completed_operations == []


def test_revision_aware_analysis_artifact_overrides_legacy_fallback(monkeypatch):
    _install_persisted_facts(
        monkeypatch,
        setup_stage="setup_complete",
        summary="old summary",
        plan="old plan",
        menu=TEST_MENU,
        artifacts=(ArtifactFact("project_analysis", "rev-1", True),),
    )

    status = projectWorkflowStatusService.get_project_workflow_status("Ez1")

    assert status.stage is ProjectStage.ANALYSIS_REQUIRED
    assert status.allowed_routes == ["/plan"]
    assert status.completed_operations == []
    assert status.stale_operations == ["project_analysis"]
    assert status.menu is None
