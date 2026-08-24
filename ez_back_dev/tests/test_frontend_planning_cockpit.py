import importlib.util
import json
import struct
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_ROOT = PROJECT_ROOT / "ez_front_dev"
PLANNING_ASSETS = (
    FRONTEND_ROOT / "src" / "assets" / "static" / "image" / "test-types-v2"
)


def read(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def test_project_analysis_bundle_uses_read_only_rest_without_implicit_stream():
    state = read("ez_front_dev/src/state/projectAnalysis.ts")
    plan = read("ez_front_dev/src/components/TestPlan.vue")

    assert "export interface ProjectAnalysisBundle" in state
    assert "export const fetchProjectAnalysisBundle" in state
    for info_type in (1, 22, 23):
        assert f"/project/info/${{pid}}/{info_type}" in state
    assert "Promise.all" in state
    assert "signal" in state
    assert "parseProjectAnalysisMenu" in state
    assert "throw new Error" in state
    assert "/project/llm/" not in state

    assert "fetchProjectAnalysisBundle" in plan
    assert "AbortController" in plan
    assert "onBeforeUnmount" in plan
    assert "loadSavedBundle" in plan
    assert "await runTestPlan(false)" not in plan
    assert 'start("/project/llm/plan/stream"' in plan


def test_test_plan_is_a_shared_component_cockpit_with_saved_and_draft_layers():
    plan = read("ez_front_dev/src/components/TestPlan.vue")

    for component in (
        "WorkspacePageHeader",
        "WorkspaceSection",
        "ModelSelector",
        "WorkflowActionBar",
        "FeedbackState",
        "ResultContainer",
    ):
        assert component in plan
    for copy in (
        "业务文档的初步分析与总结",
        "建议测试计划",
        "推荐测试类型",
        "本次未保存草稿",
        "正在读取已保存计划",
        "未提供版本标识",
        "不会自动调用模型",
    ):
        assert copy in plan
    assert "savedBundle" in plan
    assert "draftVisible" in plan
    assert "bundleIsStale" in plan
    assert 'status="stale"' in plan or ':status="bundleStatus"' in plan
    assert "planning-prose" in plan
    assert "white-space: pre-wrap" in plan
    assert "width: 99%" not in plan
    assert "#06b009" not in plan.lower()
    assert "type=\"textarea\"" not in plan


def test_regeneration_confirmation_precedes_lock_and_preserves_previous_bundle():
    plan = read("ez_front_dev/src/components/TestPlan.vue")
    confirmations = read("ez_front_dev/src/ui/confirmations.ts")

    assert "export const confirmProjectAnalysisRegeneration" in confirmations
    for copy in (
        "确认重新生成测试计划",
        "测试菜单和八类测试工作区会临时锁定",
        "失败或取消会继续保留当前有效版本",
        "保留当前计划",
    ):
        assert copy in confirmations
    assert "return false" in confirmations

    confirmation = plan.index("await confirmProjectAnalysisRegeneration()")
    begin = plan.index("beginProjectAnalysisRegeneration()")
    assert confirmation < begin
    assert "previousBundle" in plan
    assert "saved.value && ready.value" in plan
    assert "finishProjectAnalysisRegeneration()" in plan
    assert "finally" in plan
    assert "setProjectAnalysisReady(menu.value)" in plan
    assert "await loadProjectWorkflowStatus(requestUrl, projectId)" in plan


def test_workspace_registry_and_card_publish_eight_typed_accessible_entries():
    registry = read("ez_front_dev/src/config/testWorkspaces.ts")
    card = read("ez_front_dev/src/components/planning/TestWorkspaceCard.vue")

    assert "export type TestWorkspaceKey" in registry
    assert "export type TestWorkspaceStatus" in registry
    assert "export interface TestWorkspaceDefinition" in registry
    assert "export const TEST_WORKSPACES" in registry
    for key in (
        "unit_test",
        "integration_test",
        "api_test",
        "ui_test",
        "db_test",
        "functional_test",
        "nonfunctional_test",
        "acceptance_test",
    ):
        assert f'key: "{key}"' in registry
    assert registry.count('terminalOperation: "') == 8
    assert "testPlan.png" not in registry
    assert "@/assets/static/image/test-types-v2/" in registry

    assert "<article" in card
    assert ':data-state="item.status"' in card
    assert "<RouterLink" in card
    assert "<el-button" not in card
    assert 'alt=""' in card
    assert 'width="256"' in card
    assert 'height="256"' in card
    assert 'loading="lazy"' in card
    assert "aria-describedby" in card
    assert "var(--ez-" in card
    assert "#" not in card


def test_test_menu_shows_all_eight_and_keeps_availability_separate_from_progress():
    menu = read("ez_front_dev/src/components/TestMenu.vue")

    assert "TEST_WORKSPACES" in menu
    assert 'v-for="item in dashboardItems"' in menu
    assert "TestWorkspaceCard" in menu
    assert "dashboardItems" in menu
    assert "projectAnalysisRegenerating" in menu
    for state, label in (
        ("regenerating", "分析中"),
        ("not-recommended", "未推荐"),
        ("stale", "已过期"),
        ("locked", "已锁定"),
        ("available", "可进入"),
    ):
        assert f'status: "{state}"' in menu
        assert label in menu
    regenerating = menu.index('status: "regenerating"')
    not_recommended = menu.index('status: "not-recommended"')
    stale = menu.index('status: "stale"')
    locked = menu.index('status: "locked"')
    available = menu.index('status: "available"')
    assert regenerating < not_recommended < stale < locked < available
    assert "已有可恢复结果" in menu
    assert "推荐状态不代表测试已完成" in menu
    assert "repeat(auto-fit, minmax(min(100%, 260px), 1fr))" in menu
    assert "min-width: 800px" not in menu
    assert "position: absolute" not in menu
    assert "testPlan.png" not in menu
    assert "loadProjectWorkflowStatus" in menu


def test_generated_workspace_images_are_small_transparent_pngs():
    filenames = (
        "unit-testing.png",
        "integration-testing.png",
        "api-testing.png",
        "ui-testing.png",
        "database-testing.png",
        "functional-testing.png",
        "nonfunctional-testing.png",
        "acceptance-testing.png",
    )
    total_size = 0
    for filename in filenames:
        path = PLANNING_ASSETS / filename
        data = path.read_bytes()
        assert data[:8] == b"\x89PNG\r\n\x1a\n"
        width, height, bit_depth, color_type = struct.unpack(">IIBB", data[16:26])
        assert (width, height) == (256, 256)
        assert bit_depth == 8
        assert color_type in {4, 6}, f"{filename} must retain alpha"
        assert path.stat().st_size <= 160 * 1024
        total_size += path.stat().st_size
    assert total_size <= 1024 * 1024


def test_fixture_supports_bundle_restore_mixed_stale_failure_and_plan_delay():
    fixture_path = PROJECT_ROOT / "scripts" / "frontend_fixture_server.py"
    source = fixture_path.read_text(encoding="utf-8")

    for pid in (
        "Ez3000000000000000004",
        "Ez3000000000000000005",
        "Ez3000000000000000006",
    ):
        assert pid in source
    assert 'parser.add_argument("--plan-delay-ms"' in source
    assert "MAX_PLAN_DELAY_MS = 10000" in source
    assert "0 <= args.plan_delay_ms <= MAX_PLAN_DELAY_MS" in source
    assert 'path.startswith("/project/info/")' in source
    assert "PlanningFixtureState" in source
    assert '"project_analysis"' in source
    assert '"retryable": True' in source
    assert 'FIXTURE_HOST = "127.0.0.1"' in source
    assert "0.0.0.0" not in source

    spec = importlib.util.spec_from_file_location("frontend_fixture_aspect5", fixture_path)
    assert spec is not None and spec.loader is not None
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)

    planning = fixture.PlanningFixtureState()
    mixed = planning.workflow_status(fixture.MIXED_MENU_PID)
    assert mixed["menu"]["db_test"] is False
    assert mixed["menu"]["nonfunctional_test"] is False
    assert len(mixed["allowed_routes"]) == 8

    stale = planning.workflow_status(fixture.ANALYSIS_STALE_PID)
    assert stale["stage"] == "analysis_required"
    assert stale["stale_operations"] == ["project_analysis"]
    assert planning.project_info(fixture.ANALYSIS_STALE_PID, 1)
    assert planning.project_info(fixture.ANALYSIS_STALE_PID, 22)
    assert isinstance(json.loads(planning.project_info(fixture.ANALYSIS_STALE_PID, 23)), dict)

    failure_events = fixture.plan_events_for(fixture.PLAN_FAILURE_PID, False)
    assert failure_events[-1][0] == "error"
    assert failure_events[-1][1]["retryable"] is True
    assert any(name == "answer_delta" for name, _data, _delay in failure_events)


def test_planning_documentation_records_contracts_images_matrix_and_boundaries():
    document = read("docs/iteration-3-planning-cockpit.md")
    design_system = read("docs/iteration-3-design-system.md")

    for topic in (
        "Aspect 5",
        "只读恢复",
        "不会自动调用模型",
        "未推荐",
        "可进入",
        "本次未保存草稿",
        "重新生成",
        "256×256",
        "image_gen",
        "360×800",
        "768×1024",
        "1024×768",
        "1440×900",
        "1920×1080",
        "Aspect 6–8",
    ):
        assert topic in document
    assert "TestWorkspaceCard" in design_system
    assert "测试计划与测试菜单" in design_system
