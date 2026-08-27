import importlib.util
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_ROOT = PROJECT_ROOT / "ez_front_dev"
STYLES_ROOT = FRONTEND_ROOT / "src" / "styles"


def read(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def _hex_to_rgb(value: str) -> tuple[float, float, float]:
    channels = tuple(int(value[index : index + 2], 16) / 255 for index in (1, 3, 5))
    return channels


def _relative_luminance(value: str) -> float:
    def linear(channel: float) -> float:
        if channel <= 0.04045:
            return channel / 12.92
        return ((channel + 0.055) / 1.055) ** 2.4

    red, green, blue = (linear(channel) for channel in _hex_to_rgb(value))
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _contrast(foreground: str, background: str) -> float:
    lighter, darker = sorted(
        (_relative_luminance(foreground), _relative_luminance(background)),
        reverse=True,
    )
    return (lighter + 0.05) / (darker + 0.05)


def test_foundation_styles_are_imported_in_locked_order():
    source = read("ez_front_dev/src/main.ts")
    imports = (
        "./styles/tokens.css",
        "./styles/element-plus-theme.css",
        "./styles/base.css",
        "./styles/accessibility.css",
    )

    positions = [source.index(item) for item in imports]
    assert positions == sorted(positions)
    assert source.index("./plugins/elementPlus") < positions[0]
    assert "element-plus/dist/index.css" not in source


def test_document_language_viewport_and_app_scope_are_valid():
    document = read("ez_front_dev/index.html")
    app = read("ez_front_dev/src/App.vue")

    assert '<html lang="zh-CN">' in document
    assert re.search(
        r'<meta\s+name="viewport"\s+content="width=device-width,\s*initial-scale=1(?:\.0)?">',
        document,
    )
    assert document.rstrip().endswith("</html>")
    assert "@font-face" not in app
    assert "<router-view" in app


def test_tokens_cover_the_locked_design_system_contract():
    tokens = (STYLES_ROOT / "tokens.css").read_text(encoding="utf-8")
    required = {
        "--ez-color-brand-50": "#F1F7F3",
        "--ez-color-brand-500": "#2F7D4A",
        "--ez-color-brand-700": "#1E5232",
        "--ez-color-canvas": "#F5F7F6",
        "--ez-color-surface": "#FFFFFF",
        "--ez-color-text-primary": "#17211B",
        "--ez-color-text-secondary": "#4B5B51",
        "--ez-color-border": "#D9E2DC",
        "--ez-color-info": "#2563EB",
        "--ez-color-success": "#237A45",
        "--ez-color-warning": "#9A6700",
        "--ez-color-danger": "#B42318",
        "--ez-color-locked": "#5F6F65",
        "--ez-content-compact": "720px",
        "--ez-content-default": "960px",
        "--ez-content-wide": "1200px",
        "--ez-z-sticky": "100",
        "--ez-z-overlay": "2000",
        "--ez-motion-easing": "cubic-bezier(.2, 0, 0, 1)",
    }
    for name, value in required.items():
        assert re.search(rf"{re.escape(name)}:\s*{re.escape(value)};", tokens)


def test_system_fonts_focus_motion_and_content_utilities_are_global():
    base = (STYLES_ROOT / "base.css").read_text(encoding="utf-8")
    accessibility = (STYLES_ROOT / "accessibility.css").read_text(encoding="utf-8")

    assert 'font-family: "Quantify"' in base
    assert 'font-family: "Gjhn"' in base
    assert "font-display: swap" in base
    assert "AlimamaFangYuan.ttf" not in base
    for local_font in (
        'local("Microsoft YaHei UI")',
        'local("Microsoft YaHei")',
        'local("PingFang SC")',
    ):
        assert local_font in base
    assert ":focus-visible" in accessibility
    assert "prefers-reduced-motion: reduce" in accessibility
    assert "scroll-behavior: auto" in accessibility
    assert ".ez-page" in base
    assert ".ez-content" in base
    assert ".ez-sr-only" in base
    for breakpoint in ("768px", "1024px", "1440px", "1920px"):
        assert breakpoint in base


def test_semantic_color_pairs_meet_wcag_aa_for_normal_text():
    pairs = (
        ("#2F7D4A", "#FFFFFF"),
        ("#2563EB", "#EFF6FF"),
        ("#237A45", "#ECF7F0"),
        ("#9A6700", "#FFF7E6"),
        ("#B42318", "#FFF1F0"),
        ("#5F6F65", "#F3F4F6"),
    )
    for foreground, background in pairs:
        assert _contrast(foreground, background) >= 4.5


def test_element_plus_bridge_maps_variables_without_component_overrides():
    bridge = (STYLES_ROOT / "element-plus-theme.css").read_text(encoding="utf-8")

    for variable in (
        "--el-color-primary",
        "--el-color-primary-light-3",
        "--el-color-primary-light-5",
        "--el-color-primary-light-7",
        "--el-color-primary-light-8",
        "--el-color-primary-light-9",
        "--el-color-primary-dark-2",
        "--el-color-success",
        "--el-color-warning",
        "--el-color-danger",
        "--el-color-info",
        "--el-font-family",
        "--el-border-radius-base",
        "--el-box-shadow",
    ):
        assert variable in bridge
    assert re.search(r"\.el-[\w-]+", bridge) is None


def test_workflow_stepper_preserves_props_and_exposes_state_semantics():
    source = read("ez_front_dev/src/components/WorkflowStepper.vue")

    assert "defineProps" in source
    assert "steps:" in source
    assert "activeOperation:" in source
    assert ':data-state="step.state"' in source
    assert ':aria-current="activeOperation === step.operation ? \'step\' : undefined"' in source
    assert 'aria-hidden="true"' in source
    assert "repeat(auto-fit, minmax(min(100%, 180px), 1fr))" in source
    assert "@media (prefers-reduced-motion: reduce)" in source
    for state in ("locked", "ready", "running", "completed", "stale", "failed"):
        assert state in source
    for label in ("已锁定", "可开始", "进行中", "已完成", "已过期", "失败"):
        assert label in source


def test_offline_fixture_is_loopback_only_safe_and_deterministic():
    fixture_path = PROJECT_ROOT / "scripts" / "frontend_fixture_server.py"
    source = fixture_path.read_text(encoding="utf-8")
    forbidden = ("dotenv", "mysql", "sqlalchemy", "ez_back_dev", "os.getenv", "0.0.0.0")
    for fragment in forbidden:
        assert fragment not in source.lower()

    spec = importlib.util.spec_from_file_location("frontend_fixture_server", fixture_path)
    assert spec is not None and spec.loader is not None
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)

    assert fixture.FIXTURE_HOST == "127.0.0.1"
    required_id = "Ez3000000000000000001"
    ready_id = "Ez3000000000000000002"
    stale_id = "Ez3000000000000000003"
    assert fixture.workflow_status_for(required_id)["stage"] == "analysis_required"
    assert "/unit" in fixture.workflow_status_for(ready_id)["allowed_routes"]
    assert fixture.workflow_status_for(stale_id)["stale_operations"]

    events = list(fixture.sse_events_for(ready_id, "ui_info", False))
    event_names = [name for name, _data, _delay_ms in events]
    assert event_names[0] == "meta"
    assert "progress" in event_names
    assert "reasoning_delta" in event_names
    assert "answer_delta" in event_names
    assert "usage" in event_names
    assert "artifact" in event_names
    assert event_names[-1] == "completed"
    assert events == list(fixture.sse_events_for(ready_id, "ui_info", False))


def test_foundation_docs_publish_matrix_tokens_and_aspect_boundary():
    baseline = read("docs/iteration-3-experience-baseline.md")
    design_system = read("docs/iteration-3-design-system.md")

    for viewport in (
        "360×800",
        "768×1024",
        "1024×768",
        "1440×900",
        "1920×1080",
    ):
        assert viewport in baseline
    for surface in (
        "登录",
        "创建",
        "主框架",
        "测试计划",
        "测试菜单",
        "单元测试",
        "UI 测试",
        "LLM 执行面板",
    ):
        assert surface in baseline
    assert "Aspect 1" in baseline
    assert "Aspect 2–8" in baseline
    assert "#2F7D4A" in design_system
    assert "--ez-" in design_system
    assert "Element Plus" in design_system
    assert "WorkflowStepper" in design_system
    assert "不得" in design_system
