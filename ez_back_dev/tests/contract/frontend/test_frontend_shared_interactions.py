import importlib.util
import re
from pathlib import Path

import pytest


from repo_paths import canonical_document_path
from repo_paths import canonical_frontend_path
from repo_paths import REPO_ROOT as PROJECT_ROOT
FRONTEND_ROOT = PROJECT_ROOT / "ez_front_dev"
WORKSPACE_COMPONENTS = FRONTEND_ROOT / "src" / "shared" / "components"


def read(relative_path: str) -> str:
    if relative_path.replace("\\", "/").startswith("docs/"):
        return canonical_document_path(relative_path).read_text(encoding="utf-8")
    return canonical_frontend_path(relative_path).read_text(encoding="utf-8")


def test_shared_workspace_components_publish_explicit_semantic_contracts():
    expected = {
        "WorkspacePageHeader.vue": ("<h2", 'name="actions"', "description"),
        "WorkspaceSection.vue": ("<section", "aria-busy", 'name="actions"'),
        "ModelSelector.vue": ("<fieldset", "<legend", "update:modelValue"),
        "WorkflowActionBar.vue": ('role="group"', "ariaLabel", "<slot"),
        "FeedbackState.vue": ("loading", "empty", "error"),
        "ResultContainer.vue": ("persistent", "session-only", "<section"),
    }

    for filename, fragments in expected.items():
        source = (WORKSPACE_COMPONENTS / filename).read_text(encoding="utf-8")
        assert "defineProps" in source
        for fragment in fragments:
            assert fragment in source
        assert re.search(r"#[0-9a-fA-F]{3,8}\b", source) is None

    model_selector = (WORKSPACE_COMPONENTS / "ModelSelector.vue").read_text(
        encoding="utf-8"
    )
    assert "ModelLabel" in model_selector
    assert "el-segmented" in model_selector
    assert "overflow-x: auto" not in model_selector
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in model_selector
    assert "@media (max-width: 320px)" in model_selector

    action_bar = (WORKSPACE_COMPONENTS / "WorkflowActionBar.vue").read_text(
        encoding="utf-8"
    )
    assert "flex-wrap: wrap" in action_bar
    assert "@media (max-width: 480px)" in action_bar


def test_design_tokens_cover_shared_control_and_reading_measure():
    tokens = read("ez_front_dev/src/shared/styles/tokens.css")

    assert "--ez-control-height: 40px;" in tokens
    assert "--ez-reading-measure: 72ch;" in tokens


def test_llm_stream_tracks_existing_persistence_meta_without_transport_changes():
    stream = read("ez_front_dev/src/shared/composables/useLlmStream.ts")

    assert 'export type LlmPersistence = "" | "artifact" | "session";' in stream
    assert "export interface LlmExecutionMeta" in stream
    assert "persistence: LlmPersistence" in stream
    assert 'meta.persistence = "";' in stream
    assert re.search(r'meta\.persistence\s*=\s*\n?\s*data\.persistence === "artifact"', stream)
    assert 'start("/project/llm/workflow/stream"' not in stream
    assert 'case "reasoning_delta"' in stream
    assert 'case "completed"' in stream
    assert "controller.abort()" in stream


def test_llm_feedback_hierarchy_exposes_all_user_facing_states():
    panel = read("ez_front_dev/src/features/testing/components/LlmExecutionPanel.vue")
    execution = read("ez_front_dev/src/features/testing/components/LlmWorkflowExecution.vue")

    for label in (
        "进行中",
        "已从缓存恢复",
        "已保存",
        "已完成",
        "仅当前页面保留",
        "已取消",
        "本次未保存",
        "失败",
        "可安全重试",
        "模型推理 · 仅本次会话",
    ):
        assert label in panel
    for token_label in ("输入 Token", "思考 Token", "正文 Token", "总 Token"):
        assert token_label in panel
    assert 'const openSections = ref<string[]>([]);' in panel
    assert 'aria-live="polite"' in panel
    assert "LlmExecutionMeta" in panel
    assert "#06b009" not in panel.lower()
    assert "width: 99%" not in panel

    assert "ResultContainer" in execution
    assert "answer && (!completed || error || cancelled)" in execution
    assert "LlmExecutionMeta" in execution
    assert "width: 99%" not in execution
    assert "#06b009" not in execution.lower()


def test_result_replacement_confirmation_preserves_existing_copy_and_behavior():
    helper = read("ez_front_dev/src/shared/ui/confirmations.ts")
    workflow = read("ez_front_dev/src/features/testing/composables/useTestWorkflow.ts")

    assert "export const confirmResultReplacement" in helper
    assert "ElMessageBox.confirm" in helper
    for label in (
        "将替换已保存的有效结果，是否继续？",
        "确认重新生成",
        "重新生成",
        "保留原结果",
    ):
        assert label in helper
    assert "return false" in helper
    assert "confirmResultReplacement(step.label)" in workflow
    assert "ElMessageBox" not in workflow
    assert "/project/llm/" not in workflow
    assert "fetch(" not in workflow


def test_ui_test_pilot_contract_graduates_to_all_test_workspaces():
    source = read("ez_front_dev/src/features/testing/pages/UITest.vue")

    for component in (
        "WorkspacePageHeader",
        "WorkspaceSection",
        "ModelSelector",
        "WorkflowActionBar",
        "FeedbackState",
        "ResultContainer",
    ):
        assert component in source
    assert ':options="MODEL_OPTIONS"' in source
    assert source.count("<LlmWorkflowExecution") == 2
    assert "activeOperation === 'ui_info'" in source
    assert "activeOperation === 'ui_case'" in source
    assert re.search(r'runWorkflow\(\s*"ui_info"', source)
    assert re.search(r'runWorkflow\(\s*"ui_case"', source)
    assert "keepPreviousOnFailure: true" in source
    assert "hydrateWorkflow" in source
    assert "hydrationError" in source
    assert 'retention="persistent"' in source
    assert "width: 190px" not in source
    assert "width: 99%" not in source
    assert "#06b009" not in source.lower()

    for filename in (
        "UnitTest.vue",
        "IntegrationTest.vue",
        "ApiTest.vue",
        "UITest.vue",
        "DatabaseTest.vue",
        "FunctionalTest.vue",
        "NonfunctionalTest.vue",
        "AcceptanceTest.vue",
    ):
        workspace = read(f"ez_front_dev/src/features/testing/pages/{filename}")
        assert "TestWorkspaceScaffold" in workspace
        assert "WorkspaceSection" in workspace
        assert "ModelSelector" in workspace
        assert "WorkflowActionBar" in workspace
        assert "ResultContainer" in workspace


def test_fixture_models_artifact_and_session_only_completion_truthfully():
    fixture_path = PROJECT_ROOT / "scripts" / "frontend_fixture_server.py"
    source = fixture_path.read_text(encoding="utf-8")
    assert "SESSION_ONLY_OPERATIONS" in source
    assert '"unit_case"' in source
    assert '"nonfunctional_case"' in source
    assert '"persistence": persistence_for(operation)' in source

    spec = importlib.util.spec_from_file_location("frontend_fixture_aspect3", fixture_path)
    assert spec is not None and spec.loader is not None
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)

    assert fixture.allowed_origin_for(18080) == "http://127.0.0.1:18080"
    assert fixture.allowed_origin_for(18082) == "http://127.0.0.1:18082"
    with pytest.raises(ValueError):
        fixture.allowed_origin_for(0)

    session_events = fixture.sse_events_for(fixture.READY_PID, "unit_case", False)
    session_meta = session_events[0][1]
    session_names = [event for event, _data, _delay in session_events]
    session_completed = session_events[-1][1]
    assert session_meta["persistence"] == "session"
    assert "artifact" not in session_names
    assert session_completed["saved"] is False
    assert session_completed["from_cache"] is False

    artifact_events = fixture.sse_events_for(fixture.READY_PID, "ui_case", False)
    artifact_meta = artifact_events[0][1]
    artifact_names = [event for event, _data, _delay in artifact_events]
    artifact_completed = artifact_events[-1][1]
    assert artifact_meta["persistence"] == "artifact"
    assert "artifact" in artifact_names
    assert artifact_completed["saved"] is True
    assert artifact_completed["from_cache"] is True

    unit_menu_events = fixture.sse_events_for(fixture.READY_PID, "unit_menu", False)
    unit_info_events = fixture.sse_events_for(fixture.READY_PID, "unit_info", False)
    unit_case_events = fixture.sse_events_for(fixture.READY_PID, "unit_case", False)
    unit_menu = next(data["result"] for name, data, _delay in unit_menu_events if name == "result")
    unit_info = next(data["result"] for name, data, _delay in unit_info_events if name == "result")
    unit_case = next(data["result"] for name, data, _delay in unit_case_events if name == "result")
    assert unit_menu["list_info"]["module_menu"]["module_list"]
    assert unit_info["test_type"] == {"black_box": True, "white_box": True}
    assert unit_case["unit_test_knowledge"]
    assert unit_case["unit_method_knowledge"]
    assert unit_case["test_cases"]


def test_shared_interaction_documentation_records_contracts_and_boundaries():
    document = read("docs/iteration-3-shared-interactions.md")
    design_system = read("docs/iteration-3-design-system.md")

    for topic in (
        "Aspect 3",
        "组件契约",
        "reasoning",
        "Token",
        "仅当前页面保留",
        "已从缓存恢复",
        "360×800",
        "1920×1080",
        "Aspect 4–8",
    ):
        assert topic in document
    assert "共享交互" in design_system
    assert "WorkspaceSection" in design_system
    assert "LlmExecutionPanel" in design_system
