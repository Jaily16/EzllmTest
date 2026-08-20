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


def test_all_ten_feature_pages_retain_their_core_backend_flow():
    expected_fragments = {
        "TestMenu.vue": ["loadProjectAnalysisStatus"],
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


def test_project_analysis_enters_plan_first_and_locks_downstream_routes():
    router = (FRONTEND_ROOT / "src/router/index.ts").read_text(encoding="utf-8")
    login = (FRONTEND_ROOT / "src/views/LoginView.vue").read_text(encoding="utf-8")
    main = (FRONTEND_ROOT / "src/views/MainView.vue").read_text(encoding="utf-8")
    plan = (FRONTEND_ROOT / "src/components/TestPlan.vue").read_text(encoding="utf-8")
    menu = (FRONTEND_ROOT / "src/components/TestMenu.vue").read_text(encoding="utf-8")

    assert "redirect: '/plan'" in router
    assert "meta: { requiresAnalysis: true }" in router
    assert "to.meta.requiresAnalysis && !analysisReady.value" in router
    assert "开始分析业务和生成测试计划" in login
    assert '<span>测试计划</span>' in main
    assert 'index="/menu" :disabled="!analysisReady"' in main
    assert main.count(':disabled="!analysisReady"') == 9
    assert "业务文档的初步分析与总结" in plan
    assert "setProjectAnalysisReady(menu.value)" in plan
    assert "/project/llm/menu/acquire" not in menu
    assert "/project/llm/menu/analyze/" not in menu
