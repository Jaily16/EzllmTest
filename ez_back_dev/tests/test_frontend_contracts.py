import re
from pathlib import Path

from llm.provider import list_model_labels


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_ROOT = PROJECT_ROOT / "ez_front_dev"


def test_frontend_model_labels_match_backend_registry_in_order():
    source = (FRONTEND_ROOT / "src/config/models.ts").read_text(encoding="utf-8")
    array_body = re.search(r"MODEL_LABELS\s*=\s*\[(.*?)\]\s*as const", source, re.S)

    assert array_body is not None
    frontend_labels = re.findall(r'"([^"]+)"', array_body.group(1))
    assert frontend_labels == list_model_labels()


def test_frontend_model_options_show_concrete_model_names():
    source = (FRONTEND_ROOT / "src/config/models.ts").read_text(encoding="utf-8")

    expected_display_names = {
        '"GLM-4.7": "glm-4.7"',
        '"通义千问": "qwen3.5-plus"',
        'DeepSeek: "deepseek-v4-flash"',
        '"Moonshot Kimi": "kimi-k2.5"',
    }
    for display_mapping in expected_display_names:
        assert display_mapping in source

    assert "label: MODEL_DISPLAY_NAMES[value]" in source
    assert "value," in source


def test_integration_analysis_uses_the_generic_stream_and_backend_fallback():
    source = (FRONTEND_ROOT / "src/components/IntegrationTest.vue").read_text(
        encoding="utf-8"
    )

    assert 'runWorkflow("integration_menu"' in source
    assert 'runWorkflow("integration_info"' in source
    assert 'runWorkflow("integration_case"' in source
    assert "/project/llm/unit/menu/" not in source


def test_frontend_resolves_typed_http_errors_through_legacy_envelopes():
    source = (FRONTEND_ROOT / "src/main.ts").read_text(encoding="utf-8")

    assert "axios.defaults.validateStatus" in source
    assert "status >= 200 && status < 600" in source


def test_all_model_selectors_use_the_shared_registry_options():
    for relative_path in [
        "src/components/TestPlan.vue",
        "src/components/UnitTest.vue",
        "src/components/IntegrationTest.vue",
        "src/components/ApiTest.vue",
        "src/components/UITest.vue",
        "src/components/DatabaseTest.vue",
        "src/components/FounctionalTest.vue",
        "src/components/NonfunctionalTest.vue",
        "src/components/AcceptanceTest.vue",
    ]:
        source = (FRONTEND_ROOT / relative_path).read_text(encoding="utf-8")
        assert 'from "@/config/models"' in source
        assert "MODEL_OPTIONS" in source


def test_test_plan_uses_cancellable_post_sse_stream():
    component = (FRONTEND_ROOT / "src/components/TestPlan.vue").read_text(
        encoding="utf-8"
    )
    composable = (FRONTEND_ROOT / "src/composables/useLlmStream.ts").read_text(
        encoding="utf-8"
    )

    assert 'start("/project/llm/plan/stream"' in component
    assert "AbortController" in composable
    assert "response.body.getReader()" in composable
    assert 'case "reasoning_delta"' in composable
    assert 'case "answer_delta"' in composable
    assert 'case "summary_delta"' in composable
    assert 'case "menu"' in composable


def test_test_plan_refreshes_derived_workflow_status_after_bundle_save():
    component = (FRONTEND_ROOT / "src/components/TestPlan.vue").read_text(
        encoding="utf-8"
    )

    assert "loadProjectWorkflowStatus" in component
    assert "await loadProjectWorkflowStatus(requestUrl, projectId)" in component
    assert "setProjectAnalysisReady(menu.value)" in component


def test_all_ten_feature_pages_retain_their_core_backend_flow():
    expected_fragments = {
        "TestMenu.vue": ["loadProjectWorkflowStatus"],
        "TestPlan.vue": ["/project/llm/plan/stream"],
        "UnitTest.vue": ["unit_menu", "unit_info", "unit_case"],
        "IntegrationTest.vue": [
            "integration_menu",
            "integration_info",
            "integration_case",
        ],
        "ApiTest.vue": ["api_info", "api_case"],
        "UITest.vue": ["ui_info", "ui_case"],
        "DatabaseTest.vue": ["db_info", "db_case"],
        "FounctionalTest.vue": ["functional_info", "functional_case"],
        "NonfunctionalTest.vue": ["nonfunctional_info", "nonfunctional_case"],
        "AcceptanceTest.vue": ["acceptance_info", "acceptance_case"],
    }

    for component, fragments in expected_fragments.items():
        source = (FRONTEND_ROOT / "src/components" / component).read_text(
            encoding="utf-8"
        )
        for fragment in fragments:
            assert fragment in source, f"{component} lost {fragment}"


def test_all_llm_test_pages_use_the_shared_streaming_panel_without_spinners():
    legacy_paths = (
        "/project/llm/unit/",
        "/project/llm/integration/",
        "/project/llm/api/",
        "/project/llm/ui/",
        "/project/llm/db/",
        "/project/llm/functional/",
        "/project/llm/nfunctional/",
        "/project/llm/acceptance/",
    )
    for component in [
        "UnitTest.vue",
        "IntegrationTest.vue",
        "ApiTest.vue",
        "UITest.vue",
        "DatabaseTest.vue",
        "FounctionalTest.vue",
        "NonfunctionalTest.vue",
        "AcceptanceTest.vue",
    ]:
        source = (FRONTEND_ROOT / "src/components" / component).read_text(
            encoding="utf-8"
        )
        assert "LlmWorkflowExecution" in source
        assert "useLlmWorkflow" in source
        assert "runWorkflow(" in source
        assert "v-loading" not in source
        for legacy_path in legacy_paths:
            assert legacy_path not in source


def test_each_streaming_panel_is_mounted_below_its_active_operation():
    expected_operations = {
        "UnitTest.vue": ("unit_menu", "unit_info", "unit_case"),
        "IntegrationTest.vue": (
            "integration_menu",
            "integration_info",
            "integration_case",
        ),
        "ApiTest.vue": ("api_info", "api_case"),
        "UITest.vue": ("ui_info", "ui_case"),
        "DatabaseTest.vue": ("db_info", "db_case"),
        "FounctionalTest.vue": ("functional_info", "functional_case"),
        "NonfunctionalTest.vue": (
            "nonfunctional_info",
            "nonfunctional_case",
        ),
        "AcceptanceTest.vue": ("acceptance_info", "acceptance_case"),
    }

    for component, operations in expected_operations.items():
        source = (FRONTEND_ROOT / "src/components" / component).read_text(
            encoding="utf-8"
        )
        assert "activeOperation" in source
        assert source.count("<LlmWorkflowExecution") == len(operations)
        for operation in operations:
            conditional_panel = re.compile(
                rf'<LlmWorkflowExecution[^>]*v-if="activeOperation === '
                rf"'{operation}'\"",
                re.S,
            )
            assert conditional_panel.search(source), (
                f"{component} does not mount the panel for {operation} "
                "at its contextual action location"
            )


def test_generic_frontend_stream_consumes_result_and_supports_cancellation():
    stream = (FRONTEND_ROOT / "src/composables/useLlmStream.ts").read_text(
        encoding="utf-8"
    )
    workflow = (FRONTEND_ROOT / "src/composables/useLlmWorkflow.ts").read_text(
        encoding="utf-8"
    )

    assert 'case "result"' in stream
    assert "data.result" in stream
    assert "AbortController" in stream
    assert 'start("/project/llm/workflow/stream"' in workflow
    assert "regenerate: options.regenerate === true" in workflow


def test_project_lifecycle_enters_first_allowed_step_and_locks_routes():
    router = (FRONTEND_ROOT / "src/router/index.ts").read_text(encoding="utf-8")
    login = (FRONTEND_ROOT / "src/views/LoginView.vue").read_text(encoding="utf-8")
    main = (FRONTEND_ROOT / "src/views/MainView.vue").read_text(encoding="utf-8")
    plan = (FRONTEND_ROOT / "src/components/TestPlan.vue").read_text(encoding="utf-8")
    menu = (FRONTEND_ROOT / "src/components/TestMenu.vue").read_text(encoding="utf-8")

    assert "redirect: '/plan'" in router
    assert router.count("meta: { requiresWorkflow: true }") == 10
    assert "workflowStatusLoaded.value" in router
    assert "isWorkflowRouteAllowed(to.path)" in router
    assert "getWorkflowRedirectPath()" in router
    assert "开始分析业务和生成测试计划" in login
    assert '<span>测试计划</span>' in main
    assert "loadProjectWorkflowStatus" in main
    assert 'index="/menu" :disabled="!isWorkflowRouteAllowed(\'/menu\')"' in main
    assert main.count(":disabled=\"!isWorkflowRouteAllowed(") == 10
    assert "navigationState" in main
    for state in ("已完成", "当前", "已锁定", "已过期"):
        assert state in main
    assert "业务文档的初步分析与总结" in plan
    assert "setProjectAnalysisReady(menu.value)" in plan
    assert "loadProjectWorkflowStatus" in menu
    assert "statusForTestType" in menu
    assert "/project/llm/menu/acquire" not in menu
    assert "/project/llm/menu/analyze/" not in menu


def test_project_workflow_state_has_one_typed_status_loader():
    source = (FRONTEND_ROOT / "src/state/projectAnalysis.ts").read_text(
        encoding="utf-8"
    )

    assert "export interface ProjectWorkflowStatus" in source
    for stage in (
        "setup_required",
        "analysis_required",
        "analysis_ready",
        "testing_in_progress",
        "testing_ready",
    ):
        assert f'"{stage}"' in source
    assert "allowed_routes: string[]" in source
    assert "completed_operations: string[]" in source
    assert "stale_operations: string[]" in source
    assert "loadProjectWorkflowStatus" in source
    assert '"/project/workflow/status/"' in source
    assert "isWorkflowRouteAllowed" in source
    assert "getWorkflowRedirectPath" in source


def test_unlocked_test_routes_stay_enterable_in_sidebar():
    source = (FRONTEND_ROOT / "src/views/MainView.vue").read_text(
        encoding="utf-8"
    )

    test_route_state = 'if (testRoutes.includes(path)) return "available";'
    completed_state = 'if (completedOperations.value.includes(operation)) return "completed";'
    assert test_route_state in source
    assert source.index(test_route_state) < source.index(completed_state)
    assert 'available: "可进入"' in source


def test_unlocked_test_types_stay_enterable_in_test_menu():
    source = (FRONTEND_ROOT / "src/components/TestMenu.vue").read_text(
        encoding="utf-8"
    )

    assert 'type TestTypeStatus = "available" | "locked" | "stale";' in source
    assert 'available: "可进入"' in source
    assert 'if (!isWorkflowRouteAllowed(type.link)) return "locked";' in source
    assert 'return "available";' in source
    assert "completedOperations" not in source
    assert 'completed: "已完成"' not in source
    assert 'current: "可继续"' not in source


def test_project_analysis_regeneration_temporarily_locks_menu_and_test_routes():
    state = (FRONTEND_ROOT / "src/state/projectAnalysis.ts").read_text(
        encoding="utf-8"
    )
    plan = (FRONTEND_ROOT / "src/components/TestPlan.vue").read_text(
        encoding="utf-8"
    )
    router = (FRONTEND_ROOT / "src/router/index.ts").read_text(
        encoding="utf-8"
    )

    assert "export const projectAnalysisRegenerating = ref(false)" in state
    assert "beginProjectAnalysisRegeneration" in state
    assert "finishProjectAnalysisRegeneration" in state
    assert 'return path === "/plan"' in state
    assert "if (regenerate) beginProjectAnalysisRegeneration()" in plan
    assert "finally" in plan
    assert "if (regenerate) finishProjectAnalysisRegeneration()" in plan
    assert "isWorkflowRouteAllowed(to.path)" in router


def test_workflow_status_loading_does_not_start_an_llm_request():
    state = (FRONTEND_ROOT / "src/state/projectAnalysis.ts").read_text(
        encoding="utf-8"
    )
    main = (FRONTEND_ROOT / "src/views/MainView.vue").read_text(encoding="utf-8")
    menu = (FRONTEND_ROOT / "src/components/TestMenu.vue").read_text(
        encoding="utf-8"
    )
    combined = state + main + menu

    assert "/project/workflow/status/" in combined
    assert "/project/llm/plan/stream" not in combined
    assert "/project/llm/workflow/stream" not in combined


def test_project_setup_state_is_typed_persisted_and_restorable():
    source = (FRONTEND_ROOT / "src/state/projectSetup.ts").read_text(
        encoding="utf-8"
    )

    assert 'export type SetupStepState = "pending" | "running" | "completed" | "failed"' in source
    assert "export interface ProjectSetupState" in source
    assert 'Record<SetupGroup, SetupStepState>' in source
    assert "sourceRevision: string | null" in source
    assert "localStorage.setItem" in source
    assert "restoreProjectSetupState" in source
    assert "loadProjectSetupStatus" in source
    assert '"/project/setup/status/"' in source
    assert '"/project/setup/finalize/"' in source


def test_create_view_retries_only_incomplete_groups_and_restores_after_refresh():
    source = (FRONTEND_ROOT / "src/views/CreateView.vue").read_text(
        encoding="utf-8"
    )

    assert 'from "@/state/projectSetup"' in source
    assert "onMounted" in source
    assert "restoreProjectSetupState" in source
    assert "loadProjectSetupStatus" in source
    assert 'projectSetupState.groups[group] === "completed"' in source
    assert "markSetupGroup" in source
    assert "setupRequestActive.value" in source
    assert ':disabled="setupRequestActive"' in source
    assert "projectSetupState.stage === \"setup_complete\"" in source
    assert "finalizeProjectSetup" in source
    assert "<el-steps" in source
    assert "var knowledge_result" not in source
    assert "var testdoc_result_requirement" not in source
    assert "var testdoc_result_design" not in source


TEST_WORKFLOW_PAGES = {
    "UnitTest.vue": ("unit_menu", "unit_info", "unit_case"),
    "IntegrationTest.vue": (
        "integration_menu",
        "integration_info",
        "integration_case",
    ),
    "ApiTest.vue": ("api_info", "api_case"),
    "UITest.vue": ("ui_info", "ui_case"),
    "DatabaseTest.vue": ("db_info", "db_case"),
    "FounctionalTest.vue": ("functional_info", "functional_case"),
    "NonfunctionalTest.vue": ("nonfunctional_info", "nonfunctional_case"),
    "AcceptanceTest.vue": ("acceptance_info", "acceptance_case"),
}


def test_all_test_pages_share_saved_step_state_and_contextual_execution():
    for component, operations in TEST_WORKFLOW_PAGES.items():
        source = (FRONTEND_ROOT / "src/components" / component).read_text(
            encoding="utf-8"
        )

        assert "useTestWorkflow" in source
        assert "WorkflowStepper" in source
        assert "activeOperation" in source
        assert "hydrateWorkflow" in source
        assert "canRunStep" in source
        assert "regenerateStep" in source
        assert "staleWarning" in source
        assert "onMounted" in source
        assert "继续" in source
        assert "重新生成" in source
        assert source.count("<LlmWorkflowExecution") == len(operations)


def test_unit_page_uses_qualified_options_and_persists_unit_type():
    source = (FRONTEND_ROOT / "src/components/UnitTest.vue").read_text(
        encoding="utf-8"
    )

    assert "interface UnitOption" in source
    assert "parseUnitOption" in source
    assert ':key="item.value"' in source
    assert ':label="item.label"' in source
    assert ':value="item.value"' in source
    assert 'selectionFields: ["unit_type", "unit"]' in source
    assert "unit_type: unitType.value" in source
    assert "savedUnitType" in source


def test_unit_menu_regeneration_hides_previous_downstream_controls():
    source = (FRONTEND_ROOT / "src/components/UnitTest.vue").read_text(
        encoding="utf-8"
    )

    assert "const menuRegenerating = computed" in source
    assert 'v-if="menuRegenerating"' in source
    assert 'v-else-if="menuResult"' in source
    assert 'v-if="unitInfoResult && !menuRegenerating"' in source
    assert 'v-if="caseResult && !menuRegenerating"' in source
    assert "失败或取消后恢复原结果" in source
    assert "menuRegenerationRequested.value = true" in source
    assert "finally" in source
    assert "menuRegenerationRequested.value = false" in source


def test_test_workflow_composable_has_six_states_and_no_automatic_llm_call():
    source = (
        FRONTEND_ROOT / "src/composables/useTestWorkflow.ts"
    ).read_text(encoding="utf-8")

    assert (
        'export type WorkflowStepState = "locked" | "ready" | "running" | '
        '"completed" | "stale" | "failed";'
    ) in source
    assert "export interface TestWorkflowStep" in source
    assert "loadProjectWorkflowStatus" in source
    assert "normalizeSelections" in source
    assert "selectionFields" in source
    assert "Object.prototype.hasOwnProperty.call(selection, field)" in source
    assert "allowedNextActions" in source
    assert "sessionStorage.setItem" in source
    assert "sessionStorage.getItem" in source
    assert "markDependentsStale" in source
    assert "confirmReplacement" in source
    assert "keepPreviousOnFailure" in source
    assert "/project/llm/" not in source
    assert "fetch(" not in source


def test_selected_target_cases_are_not_restored_from_browser_storage():
    composable = (
        FRONTEND_ROOT / "src/composables/useTestWorkflow.ts"
    ).read_text(encoding="utf-8")
    components = {
        "UnitTest.vue": "unit_case",
        "IntegrationTest.vue": "integration_case",
        "ApiTest.vue": "api_case",
        "FounctionalTest.vue": "functional_case",
        "NonfunctionalTest.vue": "nonfunctional_case",
    }

    assert "persistResult?: boolean" in composable
    assert "persistResult: definition.persistResult !== false" in composable
    assert ".filter((step) => step.persistResult)" in composable
    assert "if (!step.persistResult) return;" in composable
    assert "step.persistResult && status.completed_operations.includes(step.operation)" in composable
    for component, operation in components.items():
        source = (FRONTEND_ROOT / "src/components" / component).read_text(
            encoding="utf-8"
        )
        assert re.search(
            rf'operation: "{operation}"[\s\S]*?persistResult: false',
            source,
        )

    for component in ("UITest.vue", "DatabaseTest.vue", "AcceptanceTest.vue"):
        source = (FRONTEND_ROOT / "src/components" / component).read_text(
            encoding="utf-8"
        )
        assert "persistResult: false" not in source


def test_shared_stepper_renders_every_workflow_state():
    source = (FRONTEND_ROOT / "src/components/WorkflowStepper.vue").read_text(
        encoding="utf-8"
    )

    assert "TestWorkflowStep" in source
    assert "defineProps" in source
    for state in ("locked", "ready", "running", "completed", "stale", "failed"):
        assert state in source
    for label in ("已锁定", "可开始", "进行中", "已完成", "已过期", "失败"):
        assert label in source


def test_llm_workflow_records_artifact_metadata_without_changing_endpoint():
    stream = (FRONTEND_ROOT / "src/composables/useLlmStream.ts").read_text(
        encoding="utf-8"
    )
    workflow = (FRONTEND_ROOT / "src/composables/useLlmWorkflow.ts").read_text(
        encoding="utf-8"
    )

    assert 'case "artifact"' in stream
    assert "artifactKey" in stream
    assert "sourceRevision" in stream
    assert "TestWorkflowController" in workflow
    assert "completeStep" in workflow
    assert "failStep" in workflow
    assert 'start("/project/llm/workflow/stream"' in workflow


def test_iteration2_release_docs_cover_frontend_resume_and_build_gate():
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    closeout = (
        PROJECT_ROOT / "docs" / "iteration-2-closeout.md"
    ).read_text(encoding="utf-8")

    assert "Iteration 2 完成报告" in readme
    assert "workflow status" in closeout
    assert "sessionStorage" in closeout
    assert "不会自动发起 LLM" in closeout
    assert "275 passed" in closeout
    assert "1 deselected" in closeout
    assert "零错误、零警告" in closeout
    assert "asset size limit" in closeout
    assert "entrypoint size limit" in closeout
