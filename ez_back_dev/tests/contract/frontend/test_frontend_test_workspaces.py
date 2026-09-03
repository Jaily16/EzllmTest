import importlib.util
import re
from pathlib import Path


from repo_paths import canonical_document_path
from repo_paths import canonical_frontend_path
from repo_paths import REPO_ROOT as PROJECT_ROOT
FRONTEND_ROOT = PROJECT_ROOT / "ez_front_dev"
TESTING_COMPONENTS = FRONTEND_ROOT / "src" / "features" / "testing" / "components"
TEST_PAGES = {
    "UnitTest.vue": ("unit_menu", "unit_info", "unit_case", "session-only"),
    "IntegrationTest.vue": (
        "integration_menu",
        "integration_info",
        "integration_case",
        "session-only",
    ),
    "ApiTest.vue": ("api_info", "api_case", "session-only"),
    "UITest.vue": ("ui_info", "ui_case", "persistent"),
    "DatabaseTest.vue": ("db_info", "db_case", "persistent"),
    "FunctionalTest.vue": ("functional_info", "functional_case", "session-only"),
    "NonfunctionalTest.vue": (
        "nonfunctional_info",
        "nonfunctional_case",
        "session-only",
    ),
    "AcceptanceTest.vue": ("acceptance_info", "acceptance_case", "persistent"),
}


def read(relative_path: str) -> str:
    if relative_path.replace("\\", "/").startswith("docs/"):
        return canonical_document_path(relative_path).read_text(encoding="utf-8")
    return canonical_frontend_path(relative_path).read_text(encoding="utf-8")


def test_testing_primitives_publish_typed_semantic_contracts():
    expected = {
        "TestWorkspaceScaffold.vue": (
            "WorkspacePageHeader",
            "WorkflowStepper",
            "FeedbackState",
            "hydrationError",
            'name="hydration-actions"',
        ),
        "TestFieldGroup.vue": ("<fieldset", "<legend", "aria-describedby"),
        "TestTargetSelector.vue": (
            "TestTargetOption",
            "update:modelValue",
            "el-select",
            "overflow-wrap",
        ),
        "TestResultText.vue": ("white-space: pre-wrap", "overflow-wrap: anywhere"),
        "TestRetentionNotice.vue": ("persistent", "session-only", "已保存", "仅当前页面保留"),
    }
    for filename, fragments in expected.items():
        source = (TESTING_COMPONENTS / filename).read_text(encoding="utf-8")
        assert "defineProps" in source
        for fragment in fragments:
            assert fragment in source
        assert re.search(r"#[0-9a-fA-F]{3,8}\b", source) is None


def test_target_selector_keeps_long_selected_values_readable_without_focus_overlap():
    source = read(
        "ez_front_dev/src/features/testing/components/TestTargetSelector.vue"
    )

    assert 'popper-class="test-target-selector-popper"' in source
    assert "fit-input-width" in source
    assert 'class="test-target-selector__summary"' in source
    assert "selectedOption.label" in source
    assert "selectionDescriptionId" in source
    assert ':class="controlClasses"' in source
    assert '@visible-change="handleVisibleChange"' in source
    assert "const dropdownOpen = ref(false)" in source
    assert '"test-target-selector__control--selected"' in source
    assert '"test-target-selector__control--open"' in source
    assert ".test-target-selector__control--selected:not(" in source
    assert ":deep(.el-select__input)" in source
    assert "caret-color: transparent" in source
    assert ".test-target-selector__control--open" in source
    assert ":deep(.el-select__placeholder)" in source
    assert ".el-select__placeholder.is-transparent" not in source
    assert ".test-target-selector__control:focus-within" not in source
    assert "visibility: hidden" in source
    assert ":global(.test-target-selector-popper" in source
    assert "white-space: normal" in source
    assert "overflow-wrap: anywhere" in source


def test_all_eight_pages_share_anatomy_without_flattening_operations():
    for filename, contract in TEST_PAGES.items():
        source = read(f"ez_front_dev/src/features/testing/pages/{filename}")
        operations, retention = contract[:-1], contract[-1]
        for component in (
            "TestWorkspaceScaffold",
            "WorkspaceSection",
            "ModelSelector",
            "WorkflowActionBar",
            "ResultContainer",
            "TestResultText",
            "TestRetentionNotice",
        ):
            assert component in source, f"{filename} did not adopt {component}"
        for operation in operations:
            assert f'operation: "{operation}"' in source
            assert f"activeOperation === '{operation}'" in source
        assert f'retention="{retention}"' in source
        assert source.count("<LlmWorkflowExecution") == len(operations)


def test_page_migration_removes_legacy_layout_and_readonly_textareas():
    forbidden = (
        "<el-row",
        'type="textarea"',
        'style="width:',
        "width: 99%",
        "width: 190px",
        "min-width: 190px",
        'font-family: "Ali"',
        "#06b009",
    )
    for filename in TEST_PAGES:
        source = read(f"ez_front_dev/src/features/testing/pages/{filename}")
        for fragment in forbidden:
            assert fragment not in source, f"{filename} retains {fragment}"

    execution = read("ez_front_dev/src/features/testing/components/LlmWorkflowExecution.vue")
    assert 'type="textarea"' not in execution
    assert "white-space: pre-wrap" in execution


def test_workflow_controller_exposes_hydration_recovery_and_selection_stale_state():
    source = read("ez_front_dev/src/features/testing/composables/useTestWorkflow.ts")
    for fragment in (
        "const hydrating = ref(true)",
        "hasVisibleResult",
        "needsResultRecovery",
        "markStepStale",
        "finally",
        "hydrating.value = false",
    ):
        assert fragment in source
    assert "/project/llm/" not in source
    assert "fetch(" not in source


def test_results_are_visible_only_for_the_selection_that_generated_them():
    workflow = read("ez_front_dev/src/features/testing/composables/useTestWorkflow.ts")
    for fragment in (
        "selectionMatches",
        "selectionsMatch",
        "reconcileStepSelection",
        "hasVisibleResultFor",
        "step.selectionFields",
        "normalizeSelections",
    ):
        assert fragment in workflow

    page_contracts = {
        "UnitTest.vue": (
            "currentUnitInfoSelection",
            "visibleUnitInfoResult",
            "unitInfoExecutionVisible",
            "currentUnitCaseSelection",
            "visibleCaseResult",
            "caseExecutionVisible",
        ),
        "IntegrationTest.vue": (
            "currentIntegrationInfoSelection",
            "visibleIntegrationInfo",
            "integrationInfoExecutionVisible",
            "currentIntegrationCaseSelection",
            "visibleCaseResult",
            "caseExecutionVisible",
        ),
        "ApiTest.vue": ("currentApiCaseSelection", "caseResultVisible", "caseExecutionVisible"),
        "FunctionalTest.vue": ("currentFunctionalCaseSelection", "caseResultVisible", "caseExecutionVisible"),
        "NonfunctionalTest.vue": ("currentNonfunctionalCaseSelection", "caseResultVisible", "caseExecutionVisible"),
    }
    for filename, fragments in page_contracts.items():
        source = read(f"ez_front_dev/src/features/testing/pages/{filename}")
        assert "hasVisibleResultFor" in source
        for fragment in fragments:
            assert fragment in source

    unit = read("ez_front_dev/src/features/testing/pages/UnitTest.vue")
    integration = read("ez_front_dev/src/features/testing/pages/IntegrationTest.vue")
    assert 'v-if="visibleUnitInfoResult"' in unit
    assert 'v-if="visibleCaseResult && !menuRegenerating"' in unit
    assert 'v-if="visibleIntegrationInfo"' in integration
    assert 'v-if="visibleCaseResult && !menuRegenerating"' in integration
    assert "!staleWithoutContent('unit_info')" not in unit
    assert "!staleWithoutContent('integration_info')" not in integration

    # Selection changes only mark the retained result stale. They must not erase it,
    # so switching back to the generating selection reveals it without another SSE.
    assert 'reconcileStepSelection("unit_info", currentUnitInfoSelection.value)' in unit
    assert 'reconcileStepSelection("integration_info", currentIntegrationInfoSelection.value)' in integration

    llm_workflow = read("ez_front_dev/src/shared/composables/useLlmWorkflow.ts")
    assert "activeSelection" in llm_workflow


def test_restore_and_reset_copy_matches_persistence_boundaries():
    confirmations = read("ez_front_dev/src/shared/ui/confirmations.ts")
    assert "confirmSessionOnlyResultReset" in confirmations
    assert "无法从项目中恢复" in confirmations

    for filename, contract in TEST_PAGES.items():
        source = read(f"ez_front_dev/src/features/testing/pages/{filename}")
        retention = contract[-1]
        assert "needsResultRecovery" in source
        assert "恢复匹配的已保存结果" in source
        if retention == "session-only":
            assert "confirmSessionOnlyResultReset" in source
            assert "resetStep(" in source
        else:
            assert "finalResultHidden" in source
            assert "重新显示" in source


def test_unit_qualified_references_keep_raw_values_and_duplicate_labels_distinct():
    helper = read("ez_front_dev/src/shared/ui/qualifiedReferences.ts")
    unit = read("ez_front_dev/src/features/testing/pages/UnitTest.vue")
    assert 'QUALIFIED_REFERENCE_SEPARATOR = " ｜ "' in helper
    assert "parseQualifiedReference" in helper
    assert "value: rawValue" in helper
    assert "parseQualifiedReference" in unit
    assert "selectedUnitLabel" in unit
    assert "unit: unit.value" in unit
    assert "reconcileStepSelection" in unit


def test_model_scope_and_session_persistence_contracts_remain_unchanged():
    unit = read("ez_front_dev/src/features/testing/pages/UnitTest.vue")
    assert "menuModel" in unit and "analysisModel" in unit and "caseModel" in unit
    for filename in set(TEST_PAGES) - {"UnitTest.vue"}:
        source = read(f"ez_front_dev/src/features/testing/pages/{filename}")
        assert "const llm = ref(DEFAULT_MODEL)" in source

    for filename in (
        "UnitTest.vue",
        "IntegrationTest.vue",
        "ApiTest.vue",
        "FunctionalTest.vue",
        "NonfunctionalTest.vue",
    ):
        source = read(f"ez_front_dev/src/features/testing/pages/{filename}")
        assert "persistResult: false" in source
    for filename in ("UITest.vue", "DatabaseTest.vue", "AcceptanceTest.vue"):
        assert "persistResult: false" not in read(f"ez_front_dev/src/features/testing/pages/{filename}")


def test_fixture_has_complete_structured_workspace_results():
    fixture_path = PROJECT_ROOT / "scripts" / "frontend_fixture_server.py"
    spec = importlib.util.spec_from_file_location("frontend_fixture_aspect6", fixture_path)
    assert spec is not None and spec.loader is not None
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)

    assert fixture.WORKSPACE_READY_PID == "Ez3000000000000000007"
    status = fixture.workflow_status_for(fixture.WORKSPACE_READY_PID)
    expected_persisted = {
        "unit_menu", "unit_info", "integration_menu", "integration_info",
        "api_info", "ui_info", "ui_case", "db_info", "db_case",
        "functional_info", "nonfunctional_info", "acceptance_info",
        "acceptance_case",
    }
    assert expected_persisted <= set(status["completed_operations"])

    for operation in (
        "unit_menu", "unit_info", "unit_case", "integration_menu",
        "integration_info", "integration_case", "api_info", "api_case",
        "ui_info", "ui_case", "db_info", "db_case", "functional_info",
        "functional_case", "nonfunctional_info", "nonfunctional_case",
        "acceptance_info", "acceptance_case",
    ):
        events = fixture.sse_events_for(fixture.WORKSPACE_READY_PID, operation, False)
        result = next(data["result"] for name, data, _delay in events if name == "result")
        assert result

    unit_menu = fixture._result_for("unit_menu")
    function_refs = unit_menu["list_info"]["function_menu"]["function_list"]
    assert len(function_refs) == 2
    assert function_refs[0].split(" ｜ ")[0] == function_refs[1].split(" ｜ ")[0]
    assert function_refs[0] != function_refs[1]


def test_aspect6_documentation_records_matrix_and_protection_boundaries():
    document = read("docs/iteration-3-test-workspaces.md")
    design = read("docs/iteration-3-design-system.md")
    for fragment in (
        "Aspect 6", "单元测试", "集成测试", "API", "UI", "数据库",
        "功能性", "非功能性", "验收", "qualified", "session-only",
        "persistent", "360×800", "1920×1080", "不自动发起",
    ):
        assert fragment in document
    assert "Aspect 6 八类测试工作区" in design
