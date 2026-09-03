import importlib.util
import re
from pathlib import Path


from repo_paths import canonical_document_path
from repo_paths import canonical_frontend_path
from repo_paths import REPO_ROOT as PROJECT_ROOT
FRONTEND_ROOT = PROJECT_ROOT / "ez_front_dev"
ONBOARDING_COMPONENTS = (
    FRONTEND_ROOT / "src" / "features" / "onboarding" / "components"
)


def read(relative_path: str) -> str:
    if relative_path.replace("\\", "/").startswith("docs/"):
        return canonical_document_path(relative_path).read_text(encoding="utf-8")
    return canonical_frontend_path(relative_path).read_text(encoding="utf-8")


def test_onboarding_components_publish_semantic_token_only_contracts():
    expected = {
        "OnboardingShell.vue": ("<main", "<h1", "wide", '<slot name="secondary"'),
        "ProjectIdDisplay.vue": ("项目 ID", "aria-live", "useClipboard"),
        "DocumentUploadGroup.vue": (
            "update:modelValue",
            "已上传并将在重试时复用",
            "el-upload",
            "aria-live",
        ),
    }

    for filename, fragments in expected.items():
        source = (ONBOARDING_COMPONENTS / filename).read_text(encoding="utf-8")
        assert "defineProps" in source
        for fragment in fragments:
            assert fragment in source
        assert re.search(r"#[0-9a-fA-F]{3,8}\b", source) is None
        assert "min-width: 500px" not in source

    shell = (ONBOARDING_COMPONENTS / "OnboardingShell.vue").read_text(
        encoding="utf-8"
    )
    assert "var(--ez-color-canvas)" in shell
    assert "max-width: 1040px" in shell
    assert "var(--ez-content-wide)" in shell
    assert "@media (min-width: 1024px)" in shell


def test_document_upload_group_keeps_element_plus_file_list_reference_stable():
    source = (ONBOARDING_COMPONENTS / "DocumentUploadGroup.vue").read_text(
        encoding="utf-8"
    )

    # Passing a filtering computed through v-model creates a fresh array on every
    # render. Element Plus writes that value back, which can recursively retrigger
    # the parent render as soon as the first file is dropped.
    assert ':file-list="modelValue"' in source
    assert '@update:file-list="updateModelValue"' in source
    assert 'v-model:file-list="controlledFiles"' not in source
    assert "props.modelValue.filter" not in source


def test_login_separates_recovery_open_and_create_without_implicit_generation():
    source = read("ez_front_dev/src/features/onboarding/views/LoginView.vue")

    for label in (
        "继续上次项目",
        "打开已有项目",
        "创建新项目",
        "开始分析业务和生成测试计划",
    ):
        assert label in source
    assert "<form" in source
    assert '@submit.prevent="login"' in source
    assert "^Ez\\d{19}$" in source
    assert "loginPending" in source
    assert "AbortController" in source
    assert "FeedbackState" in source
    assert "fetchProjectSetupStatus" in source
    assert "applyProjectSetupStatus" in source
    assert 'status.stage === "setup_complete"' in source
    assert 'router.push({ name: "testMain" })' in source
    assert 'router.push("/create")' in source
    assert "confirmRecoverySwitch" in source
    assert "confirmRecoveryDiscard" in source
    assert "setTimeout" not in source
    assert "/project/llm/" not in source
    assert "project/setup/finalize" not in source
    assert "linear-gradient" not in source
    assert "position: absolute" not in source


def test_project_setup_state_tracks_remote_files_and_restores_old_snapshots_safely():
    source = read("ez_front_dev/src/features/onboarding/state/projectSetup.ts")

    for fragment in (
        "documentCounts: Record<SetupGroup, number>",
        "documentFiles: Record<SetupGroup, string[]>",
        "allowedActions: string[]",
        "export const fetchProjectSetupStatus",
        "export const recordUploadedDocument",
        "export const normalizeUploadedDocumentName",
        "export const isUploadedDocument",
        "status.document_counts",
        "status.document_files",
        "status.allowed_actions",
    ):
        assert fragment in source
    assert "SETUP_STATUS_PATH" in source
    assert "SETUP_FINALIZE_PATH" in source
    assert "loadProjectSetupStatus" in source
    assert "finalizeProjectSetup" in source
    assert re.search(r'state === "running"\s*\?\s*"pending"', source)
    assert "Object.assign(projectSetupState, emptyState(), restored)" not in source


def test_create_view_reuses_successful_files_and_keeps_write_sequence_explicit():
    source = read("ez_front_dev/src/features/onboarding/views/CreateView.vue")

    for component in (
        "OnboardingShell",
        "ProjectIdDisplay",
        "DocumentUploadGroup",
        "FeedbackState",
        "WorkflowActionBar",
    ):
        assert component in source
    for fragment in (
        '[/\\\\]',
        "80",
        '"txt", "pdf", "md", "doc", "docx"',
        "normalizeUploadedDocumentName",
        "isUploadedDocument",
        "recordUploadedDocument",
        "activeUpload",
        "current: index + 1",
        "total: pendingFiles.length",
        "confirmProjectCreation",
        "confirmProjectSetupExit",
        "confirmRecoveryDiscard",
        "onBeforeRouteLeave",
        "beforeunload",
        "项目资料已确认，尚未开始模型分析",
    ):
        assert fragment in source
    assert source.index("/project/add/") < source.index("/uploadFile/")
    assert source.index("loadProjectSetupStatus") < source.index(
        "finalizeProjectSetup"
    )
    assert source.count("<DocumentUploadGroup") == 3
    assert "<el-steps" in source
    assert "min-width: 500px" not in source
    assert 'width="760"' not in source
    assert "width: 350px" not in source
    assert "width: 230px" not in source
    assert "#d1ffd3" not in source.lower()
    assert "/project/llm/" not in source


def test_confirmation_helpers_make_every_onboarding_mutation_explicit():
    source = read("ez_front_dev/src/shared/ui/confirmations.ts")

    for helper in (
        "confirmProjectCreation",
        "confirmRecoverySwitch",
        "confirmRecoveryDiscard",
        "confirmProjectSetupExit",
        "confirmPendingFileRemoval",
    ):
        assert f"export const {helper}" in source
    for label in (
        "不会自动启动模型分析",
        "不会删除服务器上的项目或文档",
        "保留恢复状态",
        "移除待上传文档",
    ):
        assert label in source
    assert source.count("return false") >= 6


def test_offline_fixture_requires_explicit_ephemeral_onboarding_mode():
    fixture_path = PROJECT_ROOT / "scripts" / "frontend_fixture_server.py"
    source = fixture_path.read_text(encoding="utf-8")

    for fragment in (
        "OnboardingFixtureState",
        "RECOVERY_PID",
        "--enable-onboarding",
        "--fail-upload-once",
        "MAX_FIXTURE_UPLOAD_BYTES",
        "/project/setup/status/",
        "/project/setup/finalize/",
        "/project/add/",
        "/uploadFile/",
    ):
        assert fragment in source
    assert "0.0.0.0" not in source
    assert "dotenv" not in source.lower()
    assert "sqlalchemy" not in source.lower()

    spec = importlib.util.spec_from_file_location(
        "frontend_fixture_onboarding", fixture_path
    )
    assert spec is not None and spec.loader is not None
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)

    state = fixture.OnboardingFixtureState(fail_upload_once="requirements")
    pid = state.create_project("合成项目")
    assert re.fullmatch(r"Ez\d{19}", pid)
    assert state.login(pid) == "合成项目"
    assert state.status(pid)["stage"] == "project_created"
    state.upload(pid, "knowledge", "knowledge.txt")
    state.upload(pid, "requirements", "first requirement.txt")
    failure = state.upload(pid, "requirements", "second.txt")
    assert failure is False
    assert state.status(pid)["document_files"]["requirements"] == [
        "first-requirement.txt"
    ]
    assert state.upload(pid, "requirements", "second.txt") is True
    state.upload(pid, "design", "design.v1.md")
    completed = state.finalize(pid)
    assert completed["stage"] == "setup_complete"
    assert completed["document_files"]["design"] == ["design_v1.md"]
    recovery = state.status(fixture.RECOVERY_PID)
    assert recovery["document_counts"] == {
        "knowledge": 1,
        "requirements": 0,
        "design": 1,
    }


def test_onboarding_documentation_records_behavior_and_aspect_boundary():
    document = read("docs/iteration-3-onboarding.md")
    design_system = read("docs/iteration-3-design-system.md")

    for topic in (
        "Aspect 4",
        "打开已有项目",
        "创建新项目",
        "部分上传",
        "项目 ID",
        "不会自动启动模型分析",
        "360×800",
        "1920×1080",
        "Aspect 5–8",
    ):
        assert topic in document
    assert "OnboardingShell" in design_system
    assert "DocumentUploadGroup" in design_system
