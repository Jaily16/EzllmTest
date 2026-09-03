import importlib.util
import re
from pathlib import Path


from repo_paths import canonical_document_path
from repo_paths import canonical_frontend_path
from repo_paths import REPO_ROOT as PROJECT_ROOT
FRONTEND_ROOT = PROJECT_ROOT / "ez_front_dev"


def read(relative_path: str) -> str:
    if relative_path.startswith("ez_front_dev/"):
        return canonical_frontend_path(relative_path).read_text(encoding="utf-8")
    if relative_path.replace("\\", "/").startswith("docs/"):
        return canonical_document_path(relative_path).read_text(encoding="utf-8")
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def load_fixture():
    fixture_path = PROJECT_ROOT / "scripts" / "frontend_fixture_server.py"
    spec = importlib.util.spec_from_file_location("frontend_fixture_aspect8", fixture_path)
    assert spec is not None and spec.loader is not None
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    return fixture


def event_names(events) -> list[str]:
    return [name for name, _data, _delay in events]


def test_dynamic_onboarding_project_advances_only_after_saved_plan_completion():
    fixture = load_fixture()
    onboarding = fixture.OnboardingFixtureState()
    planning = fixture.PlanningFixtureState()
    pid = onboarding.create_project("Aspect 8 离线旅程")

    for group, filename in (
        ("knowledge", "knowledge.md"),
        ("requirements", "requirements.md"),
        ("design", "design.md"),
    ):
        assert onboarding.upload(pid, group, filename) is True
    assert onboarding.finalize(pid)["stage"] == "setup_complete"

    before = fixture.workflow_status_for_request(pid, planning, onboarding)
    assert before is not None
    assert before["stage"] == "analysis_required"
    assert before["allowed_routes"] == ["/plan"]
    assert planning.has_generated(pid) is False

    events = fixture.successful_plan_events_for(pid, False)
    planning.complete(pid, events)

    after = fixture.workflow_status_for_request(pid, planning, onboarding)
    assert planning.has_generated(pid) is True
    assert after is not None
    assert after["stage"] == "analysis_ready"
    assert after["completed_operations"] == ["project_analysis"]
    assert after["allowed_routes"] == ["/plan", "/menu", *fixture.TEST_ROUTES]
    assert planning.project_info(pid, 1)
    assert planning.project_info(pid, 22)
    assert planning.project_info(pid, 23)


def test_persistence_failure_keeps_cached_artifact_and_never_reports_completion():
    fixture = load_fixture()
    pid = fixture.PERSISTENCE_FAILURE_PID
    assert pid == "Ez3000000000000000008"

    status = fixture.workflow_status_for(pid)
    assert {"project_analysis", "ui_info", "ui_case"} <= set(
        status["completed_operations"]
    )

    cached_events = fixture.sse_events_for(pid, "ui_case", False)
    assert "artifact" in event_names(cached_events)
    cached_completed = next(
        data for name, data, _delay in cached_events if name == "completed"
    )
    assert cached_completed == {"saved": True, "from_cache": True, "ready": True}

    failed_events = fixture.sse_events_for(pid, "ui_case", True)
    assert event_names(failed_events) == [
        "meta",
        "progress",
        "answer_delta",
        "result",
        "error",
    ]
    assert "artifact" not in event_names(failed_events)
    assert "completed" not in event_names(failed_events)
    error = failed_events[-1][1]
    assert error["retryable"] is True
    assert "保存失败，上一份有效结果仍保留" in error["message"]
    assert "数据库" not in error["message"]
    assert "provider" not in error["message"].casefold()


def test_closeout_fixture_remains_loopback_only_and_process_local():
    source = read("scripts/frontend_fixture_server.py")
    assert 'FIXTURE_HOST = "127.0.0.1"' in source
    assert "0.0.0.0" not in source
    assert "dotenv" not in source.casefold()
    assert "sqlalchemy" not in source.casefold()
    assert "pymysql" not in source.casefold()
    assert "open(" not in source
    assert "Path(" not in source


def test_mobile_model_selector_disables_the_inline_segmented_indicator():
    source = read("ez_front_dev/src/components/workspace/ModelSelector.vue")
    assert ".el-segmented__item-selected" in source
    assert "display: none !important;" in source
    assert ".el-segmented__item.is-selected" in source
    assert "background: var(--ez-color-brand-500);" in source


def test_iteration3_protection_contracts_remain_explicit_and_complete():
    from service.workflowCatalog import WORKFLOW_DEFINITIONS

    assert len(WORKFLOW_DEFINITIONS) == 19
    assert {
        item.operation for item in WORKFLOW_DEFINITIONS if item.persistence == "session"
    } == {
        "unit_case",
        "integration_case",
        "api_case",
        "functional_case",
        "nonfunctional_case",
    }
    assert {
        item.operation for item in WORKFLOW_DEFINITIONS if item.persistence == "artifact"
    } >= {"ui_case", "db_case", "acceptance_case"}

    router = read("ez_front_dev/src/router/index.ts")
    expected_paths = (
        "/",
        "/about",
        "/create",
        "/test",
        "/menu",
        "/plan",
        "/unit",
        "/integration",
        "/api",
        "/ui",
        "/database",
        "/functional",
        "/nfunctional",
        "/acceptance",
    )
    for path in expected_paths:
        assert re.search(rf"path:\s*['\"]{re.escape(path)}['\"]", router)
    assert "router.beforeEach" in router
    assert "isWorkflowRouteAllowed(to.path)" in router


def test_closeout_documents_publish_matrix_evidence_limits_and_release_state():
    closeout = read("docs/iteration-3-closeout.md")
    for fragment in (
        "Aspect 1–8",
        "新项目",
        "部分上传",
        "analysis_required",
        "analysis_ready",
        "cached",
        "stale",
        "regeneration",
        "cancelled",
        "structured-output error",
        "persistence error",
        "session-only",
        "320",
        "360",
        "768",
        "1024",
        "1440",
        "1920",
        "200%",
        "Narrator",
        "未提交、未推送、未发布",
    ):
        assert fragment in closeout

    hardening = read("docs/iteration-3-hardening.md")
    log = read("docs/iteration-3-development-log.md")
    assert "Aspect 8 人工项处置" in hardening
    assert "Aspect 8：集成体验验收与迭代收口" in log


def test_readme_links_iteration3_closeout_and_development_log():
    readme = read("README.md")
    assert "docs/history/iteration-3/iteration-3-closeout.md" in readme
    assert "docs/history/iteration-3/iteration-3-development-log.md" in readme


def test_package_manifests_remain_dependency_stable():
    package = read("ez_front_dev/package.json")
    lock = read("ez_front_dev/package-lock.json")
    assert '"playwright"' not in package.casefold()
    assert '"vitest"' not in package.casefold()
    assert '"playwright"' not in lock.casefold()
    assert '"vitest"' not in lock.casefold()
