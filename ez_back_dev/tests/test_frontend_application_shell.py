import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_ROOT = PROJECT_ROOT / "ez_front_dev"


def read(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def test_shell_uses_semantic_landmarks_and_one_navigation_tree():
    source = read("ez_front_dev/src/views/MainView.vue")

    assert 'class="skip-link" href="#workspace-main"' in source
    assert '<header class="workspace-header">' in source
    assert 'id="workspace-navigation"' in source
    assert '<nav aria-label="项目工作区导航">' in source
    assert 'id="workspace-main"' in source
    assert 'class="workspace-content ez-content ez-content--wide"' in source
    assert len(re.findall(r"<el-menu(?:\s|>)", source)) == 1
    assert source.count("<router-view") == 1


def test_shell_preserves_routes_guards_and_navigation_state_semantics():
    source = read("ez_front_dev/src/views/MainView.vue")
    guarded_routes = (
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
    )

    for route in guarded_routes:
        assert f'index="{route}" :disabled="!isWorkflowRouteAllowed(\'{route}\')"' in source
    assert source.count(':disabled="!isWorkflowRouteAllowed(') == 10
    assert (
        'type NavigationState =\n  | "loading"\n  | "completed"\n  | "current"\n'
        in source
    )
    for state, label in (
        ("loading", "加载中"),
        ("completed", "已完成"),
        ("current", "当前"),
        ("locked", "已锁定"),
        ("stale", "已过期"),
        ("available", "可进入"),
        ("regenerating", "分析中"),
    ):
        assert f'{state}: "{label}"' in source
    assert 'if (!workflowStatusLoaded.value) return "loading";' in source
    assert 'if (projectAnalysisRegenerating.value && path !== "/plan") return "regenerating";' in source
    available = 'if (testRoutes.includes(path)) return "available";'
    completed = 'if (completedOperations.value.includes(operation)) return "completed";'
    assert source.index(available) < source.index(completed)
    assert "/project/llm/" not in source


def test_mobile_drawer_has_keyboard_focus_and_cleanup_contracts():
    source = read("ez_front_dev/src/views/MainView.vue")

    assert 'window.matchMedia("(min-width: 1024px)")' in source
    assert 'aria-controls="workspace-navigation"' in source
    assert ':aria-expanded="mobileNavigationOpen"' in source
    assert ':aria-hidden="!isDesktop && !mobileNavigationOpen"' in source
    assert ':inert="!isDesktop && !mobileNavigationOpen ? \'\' : undefined"' in source
    assert 'ref="navigationToggleRef"' in source
    assert 'ref="navigationCloseRef"' in source
    assert 'ref="navigationPanelRef"' in source
    assert 'ref="workspaceMainRef"' in source
    assert "openMobileNavigation" in source
    assert "closeMobileNavigation" in source
    assert "handleNavigationKeydown" in source
    assert 'event.key === "Escape"' in source
    assert 'event.key !== "Tab"' in source
    assert "document.body.classList.toggle(" in source
    assert '"ez-navigation-open"' in source
    assert "watch(() => route.path" in source
    assert "workspaceMainRef.value?.focus()" in source
    assert "onBeforeUnmount" in source


def test_shell_tokens_breakpoint_width_and_overflow_guards_are_published():
    tokens = read("ez_front_dev/src/styles/tokens.css")
    source = read("ez_front_dev/src/views/MainView.vue")

    assert "--ez-shell-header-height: 64px;" in tokens
    assert "--ez-shell-sidebar-width: 272px;" in tokens
    assert "--ez-shell-drawer-width: 320px;" in tokens
    assert "width: min(var(--ez-shell-drawer-width), calc(100vw - 48px));" in source
    assert "max-width: var(--ez-content-wide);" in source
    assert "@media (min-width: 1024px)" in source
    assert "@media (max-width: 1023px)" in source
    assert "@media (prefers-reduced-motion: reduce)" in source
    assert "overflow-x: clip" in source
    assert "100dvh" in source
    assert "#d1ffd3" not in source.lower()
    assert '<el-aside width="280px">' not in source


def test_fixture_status_delay_is_loopback_only_bounded_and_read_only():
    source = read("scripts/frontend_fixture_server.py")

    assert 'parser.add_argument("--status-delay-ms"' in source
    assert "0 <= args.status_delay_ms <= MAX_STATUS_DELAY_MS" in source
    assert "MAX_STATUS_DELAY_MS = 10000" in source
    assert "server.status_delay_ms = args.status_delay_ms" in source
    status_branch = source.index('if path.startswith("/project/workflow/status/"):')
    delay = source.index("time.sleep(self.server.status_delay_ms / 1000)")
    post = source.index("def do_POST")
    assert status_branch < delay < post
    assert 'FIXTURE_HOST = "127.0.0.1"' in source
    assert "0.0.0.0" not in source


def test_application_shell_document_records_information_architecture_and_matrix():
    document = read("docs/iteration-3-application-shell.md")

    for viewport in (
        "360×800",
        "768×1024",
        "1024×768",
        "1440×900",
        "1920×1080",
    ):
        assert viewport in document
    for topic in (
        "信息架构",
        "状态来源",
        "键盘",
        "焦点",
        "reduced-motion",
        "Aspect 2",
        "Aspect 3–8",
    ):
        assert topic in document
    assert "1024px" in document
    assert "1200px" in document
    assert "Iteration 2" in document
