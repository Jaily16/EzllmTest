from pathlib import Path
import importlib.util
import re


from repo_paths import canonical_frontend_path
from repo_paths import REPO_ROOT as PROJECT_ROOT
FRONTEND = PROJECT_ROOT / "ez_front_dev" / "src"


def test_agent_route_is_lazy_and_does_not_change_ten_workflow_guards():
    source = canonical_frontend_path("ez_front_dev/src/router/index.ts").read_text(encoding="utf-8")
    assert source.count("requiresWorkflow: true") == 10
    assert re.search(r"path:\s*[\"']/agent[\"']", source)
    assert "requiresAgent: true" in source
    assert re.search(
        r"import\(\s*[\"']../../features/agent/AgentWorkbench\.vue[\"']\s*\)",
        source,
    )
    assert "allowed_routes" not in source


def test_workbench_load_path_is_read_only_and_create_is_explicit():
    component = canonical_frontend_path("ez_front_dev/src/components/AgentWorkbench.vue").read_text(
        encoding="utf-8"
    )
    initialize = component.split("const initialize = async", 1)[1].split(
        "const createRun = async", 1
    )[0]
    assert "loadAgentCapabilities" in initialize
    assert "refreshHistory" in initialize
    assert "selectRun" in initialize
    assert "createAgentRun" not in initialize
    assert '@submit.prevent="createRun"' in component
    assert "只有点击此按钮才会创建运行" in component


def test_workbench_exposes_required_safety_retention_trace_and_a11y_copy():
    component = canonical_frontend_path("ez_front_dev/src/components/AgentWorkbench.vue").read_text(
        encoding="utf-8"
    )
    for term in (
        "不会展示或保存思维链",
        "paid",
        "persistent",
        "regenerate",
        "仅 Agent thread 保留 7 天，不写入项目 artifact",
        "Trace ID",
        "未启用",
        'aria-live="polite"',
        'aria-atomic="true"',
        "prefers-reduced-motion",
        "forced-colors",
        "--ez-touch-target",
    ):
        assert term in component
    assert "copyTraceId" in component
    assert "grafanaTraceUrl" in component
    assert "v-html" not in component


def test_frontend_fixture_covers_honest_disabled_and_instrumented_trace_states():
    fixture = (PROJECT_ROOT / "scripts" / "frontend_fixture_server.py").read_text(
        encoding="utf-8"
    )
    assert '"trace_id": "0123456789abcdef0123456789abcdef" if completed else None' in fixture
    assert '"trace_status": "instrumented" if completed else "not_instrumented"' in fixture


def test_event_composable_aborts_on_scope_dispose_and_bounds_reconnects():
    source = canonical_frontend_path("ez_front_dev/src/composables/useAgentEvents.ts").read_text(
        encoding="utf-8"
    )
    assert "onScopeDispose(stop)" in source
    assert "AbortController" in source
    assert "attempt < 6" in source
    assert "after_sequence" in source
    assert "replay_reset" in source


def test_loopback_fixture_models_agent_approval_session_recovery_and_zero_load_calls():
    fixture_path = PROJECT_ROOT / "scripts" / "frontend_fixture_server.py"
    spec = importlib.util.spec_from_file_location(
        "frontend_fixture_aspect4", fixture_path
    )
    assert spec and spec.loader
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    state = fixture.AgentFixtureState()
    assert state.model_calls == state.embedding_calls == state.tool_calls == 0
    listed = state.list_runs()
    assert listed["active_thread_id"] == "fixture-thread-active"
    session = state.get_run("fixture-thread-session")
    assert session["evidence"][0]["retention"] == "session"
    assert session["evidence"][0]["session_result"]
    failed = state.get_run("fixture-thread-failed")
    assert failed["can_recover"] is True
    assert state.decide("fixture-thread-active", "approved", "a" * 64)
    assert state.model_calls == state.tool_calls == 1
    completed = state.get_run("fixture-thread-active")
    assert completed["status"] == "completed"
    assert completed["evidence"][0]["session_result"] is None
