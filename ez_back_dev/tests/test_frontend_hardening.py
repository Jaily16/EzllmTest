import importlib.util
import re
import struct
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_ROOT = PROJECT_ROOT / "ez_front_dev"


def read(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def png_dimensions(path: Path) -> tuple[int, int, int]:
    data = path.read_bytes()
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    width, height, bit_depth, colour_type = struct.unpack(">IIBB", data[16:26])
    return width, height, colour_type


def test_element_plus_is_explicitly_registered_without_full_runtime_or_css():
    main = read("ez_front_dev/src/main.ts")
    plugin = read("ez_front_dev/src/plugins/elementPlus.ts")

    assert "element-plus/dist/index.css" not in main
    assert "import ElementPlus from" not in main
    assert "ElementPlusIconsVue" not in main
    assert "installElementPlus(app)" in main

    components = {
        "ElAlert",
        "ElButton",
        "ElCollapse",
        "ElCollapseItem",
        "ElDialog",
        "ElIcon",
        "ElInput",
        "ElMenu",
        "ElMenuItem",
        "ElMenuItemGroup",
        "ElOption",
        "ElProgress",
        "ElRadioButton",
        "ElRadioGroup",
        "ElSegmented",
        "ElSelect",
        "ElStep",
        "ElSteps",
        "ElSubMenu",
        "ElTag",
        "ElUpload",
    }
    for component in components:
        assert component in plugin
    assert "ElImage" not in plugin
    assert "element-plus/es/components/message/style/css" in plugin
    assert "element-plus/es/components/message-box/style/css" in plugin
    assert "export { ElMessage, ElMessageBox }" in plugin

    icons = {
        "Box",
        "Close",
        "CollectionTag",
        "DataAnalysis",
        "Files",
        "HelpFilled",
        "HomeFilled",
        "Lock",
        "Magnet",
        "Menu",
        "MessageBox",
        "Monitor",
        "Notebook",
        "Orange",
        "Platform",
        "Reading",
    }
    for icon in icons:
        assert re.search(rf"\b{icon}\b", plugin)


def test_runtime_element_plus_services_use_the_internal_plugin():
    runtime_sources = [
        FRONTEND_ROOT / "src" / "views" / "MainView.vue",
        FRONTEND_ROOT / "src" / "views" / "CreateView.vue",
        FRONTEND_ROOT / "src" / "components" / "TestPlan.vue",
        *sorted((FRONTEND_ROOT / "src" / "components").glob("*Test.vue")),
        FRONTEND_ROOT / "src" / "ui" / "confirmations.ts",
    ]
    for source_path in runtime_sources:
        source = source_path.read_text(encoding="utf-8")
        assert not re.search(r'import\s+\{\s*El(?:Message|MessageBox).*?from\s+["\']element-plus["\']', source)


def test_accessibility_tokens_focus_motion_touch_and_import_order():
    main = read("ez_front_dev/src/main.ts")
    tokens = read("ez_front_dev/src/styles/tokens.css")
    accessibility = read("ez_front_dev/src/styles/accessibility.css")

    imports = (
        "./styles/tokens.css",
        "./styles/element-plus-theme.css",
        "./styles/base.css",
        "./styles/accessibility.css",
    )
    positions = [main.index(item) for item in imports]
    assert positions == sorted(positions)
    assert "--ez-focus-color: #2F7D4A;" in tokens
    assert "--ez-touch-target: 44px;" in tokens
    assert "outline: 3px solid var(--ez-focus-color);" in accessibility
    assert "outline-offset: var(--ez-focus-offset);" in accessibility
    assert ".el-input__wrapper" in accessibility
    assert ".el-select__wrapper" in accessibility
    assert ".el-segmented__item" in accessibility
    assert ".el-radio-button" in accessibility
    assert "input:focus-visible" in accessibility
    assert "outline: none;" in accessibility
    assert "@media (forced-colors: active)" in accessibility
    assert "@media (prefers-reduced-motion: reduce)" in accessibility
    assert "@media (max-width: 767px)" in accessibility
    assert "min-height: var(--ez-touch-target)" in accessibility
    assert "scroll-margin-top" in accessibility


def test_route_presentation_titles_and_focus_do_not_replace_guards():
    presentation = read("ez_front_dev/src/config/routePresentation.ts")
    router = read("ez_front_dev/src/router/index.ts")
    main_view = read("ez_front_dev/src/views/MainView.vue")
    onboarding = read("ez_front_dev/src/components/onboarding/OnboardingShell.vue")
    about = read("ez_front_dev/src/views/AboutView.vue")

    for path in (
        "/",
        "/create",
        "/about",
        "/plan",
        "/menu",
        "/unit",
        "/integration",
        "/api",
        "/ui",
        "/database",
        "/functional",
        "/nfunctional",
        "/acceptance",
    ):
        assert f'"{path}"' in presentation
    assert "routeTitleFor" in presentation
    assert "router.beforeEach" in router
    assert "isWorkflowRouteAllowed(to.path)" in router
    assert "router.afterEach" in router
    assert "document.title" in router
    assert "await nextTick()" in router
    assert "focus({ preventScroll: true })" in router
    assert "ROUTE_PRESENTATION" in main_view
    assert "const routeTitles" not in main_view
    assert 'tabindex="-1"' in onboarding
    assert '<main' in about and 'tabindex="-1"' in about


def test_form_controls_have_unique_ids_required_text_and_direct_names():
    model = read("ez_front_dev/src/components/workspace/ModelSelector.vue")
    group = read("ez_front_dev/src/components/testing/TestFieldGroup.vue")
    target = read("ez_front_dev/src/components/testing/TestTargetSelector.vue")

    assert "getCurrentInstance" in model
    assert "resolvedId" in model
    assert 'id: ""' in model
    assert ':id="resolvedId"' in model
    assert ':aria-label="label"' in model
    assert 'grid-template-columns: repeat(2, minmax(0, 1fr))' in model
    assert "@media (max-width: 320px)" in model
    assert "（必填）" in group
    assert "ez-sr-only" in group
    assert ':id="fieldId"' in target
    assert ':aria-label="label"' in target
    assert ':aria-required="required || undefined"' in target
    assert ':aria-describedby="describedBy"' in target
    assert 'ids.push(`${props.fieldId}-description`)' in target
    assert "ids.push(selectionDescriptionId.value)" in target


def test_loading_skeletons_are_typed_decorative_and_only_used_for_read_recovery():
    feedback = read("ez_front_dev/src/components/workspace/FeedbackState.vue")
    create = read("ez_front_dev/src/views/CreateView.vue")
    plan = read("ez_front_dev/src/components/TestPlan.vue")
    menu = read("ez_front_dev/src/components/TestMenu.vue")
    scaffold = read("ez_front_dev/src/components/testing/TestWorkspaceScaffold.vue")
    login = read("ez_front_dev/src/views/LoginView.vue")

    assert 'export type FeedbackSkeleton = "none" | "content" | "form" | "cards";' in feedback
    assert 'skeleton: "none"' in feedback
    assert 'class="feedback-state__skeleton"' in feedback
    assert 'aria-hidden="true"' in feedback
    assert 'skeleton="form"' in create
    assert 'skeleton="content"' in plan
    assert 'skeleton="cards"' in menu
    assert 'skeleton="content"' in scaffold
    assert "skeleton=" not in login
    assert re.search(r"setupRequestActive[\s\S]{0,300}kind=\"loading\"[\s\S]{0,300}(?!skeleton=)", create)


def test_status_announcements_are_atomic_and_not_attached_to_whole_grids():
    stepper = read("ez_front_dev/src/components/WorkflowStepper.vue")
    panel = read("ez_front_dev/src/components/LlmExecutionPanel.vue")
    menu = read("ez_front_dev/src/components/TestMenu.vue")

    assert "stepperAnnouncement" in stepper
    assert 'role="status"' in stepper
    assert 'aria-live="polite"' in stepper
    assert 'aria-atomic="true"' in stepper
    assert "executionAnnouncement" in panel
    assert 'aria-atomic="true"' in panel
    assert 'class="workspace-grid" aria-live="polite"' not in menu
    assert "menuStatusAnnouncement" in menu
    assert "共 8 类工作区" in menu


def test_user_facing_terminology_is_consistent_without_protocol_renames():
    main_view = read("ez_front_dev/src/views/MainView.vue")
    workspace_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((FRONTEND_ROOT / "src" / "components").glob("*Test.vue"))
    )

    assert "API 接口测试" in main_view
    assert "前端 UI 测试" in main_view
    assert "项目 ID ·" in main_view
    assert "api接口测试" not in main_view
    assert "前端UI测试" not in main_view
    assert "cache-aware SSE" not in workspace_sources
    assert "artifact cache" not in workspace_sources
    assert "按当前模型与输入" in workspace_sources
    assert "模型生成的" in workspace_sources


def test_optimized_logo_and_build_configuration_are_bounded():
    logo = (
        FRONTEND_ROOT
        / "src"
        / "assets"
        / "static"
        / "image"
        / "ezlogo-workbench-v2.png"
    )
    width, height, colour_type = png_dimensions(logo)
    assert (width, height) == (192, 192)
    assert colour_type in {4, 6}
    assert logo.stat().st_size <= 96 * 1024

    main_view = read("ez_front_dev/src/views/MainView.vue")
    onboarding = read("ez_front_dev/src/components/onboarding/OnboardingShell.vue")
    config = read("ez_front_dev/vue.config.js")
    assert "ezlogo-workbench-v2.png" in main_view
    assert "ezlogo-workbench-v2.png" in onboarding
    assert 'width="38"' in main_view and 'height="38"' in main_view
    assert 'width="52"' in onboarding and 'height="52"' in onboarding
    assert "productionSourceMap: false" in config
    assert "__VUE_PROD_HYDRATION_MISMATCH_DETAILS__" in config


def test_bundle_checker_exposes_locked_zero_dependency_budgets():
    path = PROJECT_ROOT / "scripts" / "check_frontend_bundle.py"
    spec = importlib.util.spec_from_file_location("frontend_bundle_checker", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.MAX_LOGO_BYTES == 96 * 1024
    assert module.MAX_INITIAL_JS_BYTES == 900 * 1024
    assert module.MAX_INITIAL_JS_GZIP_BYTES == 285 * 1024
    assert module.MAX_INITIAL_CSS_BYTES == 220 * 1024
    assert module.MAX_INITIAL_CSS_GZIP_BYTES == 34 * 1024
    assert module.MAX_INITIAL_TOTAL_BYTES == int(1.20 * 1024 * 1024)
    assert module.MAX_BUILD_BYTES == 3 * 1024 * 1024


def test_hardening_document_records_wcag_viewports_and_measured_assets():
    document = read("docs/iteration-3-hardening.md")
    for term in (
        "WCAG 2.2 AA",
        "320",
        "360",
        "768",
        "1024",
        "1440",
        "1920",
        "200%",
        "Element Plus",
        "1.16 MiB",
        "311 KiB",
        "688,067",
        "Aspect 8",
    ):
        assert term in document
