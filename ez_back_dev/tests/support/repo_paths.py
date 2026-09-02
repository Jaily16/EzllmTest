"""Repository paths independent of the physical test package depth."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "ez_back_dev"
FRONTEND_ROOT = REPO_ROOT / "ez_front_dev"
FIXTURES_ROOT = BACKEND_ROOT / "tests" / "fixtures"


_FRONTEND_SOURCE_PREFIXES = (
    ("src/components/AgentWorkbench.vue", "src/features/agent/AgentWorkbench.vue"),
    ("src/components/WorkflowStepper.vue", "src/features/workspace/components/WorkflowStepper.vue"),
    ("src/components/TestPlan.vue", "src/features/planning/views/TestPlan.vue"),
    ("src/components/TestMenu.vue", "src/features/planning/views/TestMenu.vue"),
    ("src/components/FounctionalTest.vue", "src/features/testing/pages/FunctionalTest.vue"),
    ("src/views/LoginView.vue", "src/features/onboarding/views/LoginView.vue"),
    ("src/views/CreateView.vue", "src/features/onboarding/views/CreateView.vue"),
    ("src/views/MainView.vue", "src/features/workspace/MainView.vue"),
    ("src/views/AboutView.vue", "src/features/about/AboutView.vue"),
    ("src/components/onboarding/", "src/features/onboarding/components/"),
    ("src/components/planning/", "src/features/planning/components/"),
    ("src/components/testing/", "src/features/testing/components/"),
    ("src/components/workspace/", "src/shared/components/"),
    ("src/components/", "src/features/testing/pages/"),
    ("src/views/", "src/features/"),
    ("src/config/testWorkspaces.ts", "src/features/testing/config/testWorkspaces.ts"),
    ("src/config/", "src/shared/config/"),
    ("src/state/projectSetup.ts", "src/features/onboarding/state/projectSetup.ts"),
    ("src/state/projectAnalysis.ts", "src/features/planning/state/projectAnalysis.ts"),
    ("src/state/agentWorkbench.ts", "src/features/agent/state/agentWorkbench.ts"),
    ("src/state/", "src/features/"),
    ("src/composables/useAgentEvents.ts", "src/features/agent/composables/useAgentEvents.ts"),
    ("src/composables/useTestWorkflow.ts", "src/features/testing/composables/useTestWorkflow.ts"),
    ("src/composables/", "src/shared/composables/"),
    ("src/styles/", "src/shared/styles/"),
    ("src/ui/", "src/shared/ui/"),
    ("src/plugins/", "src/shared/plugins/"),
    ("src/router/index.ts", "src/app/router/index.ts"),
)


_DOCUMENT_PREFIXES = (
    ("docs/iteration-1-", "docs/history/iteration-1/iteration-1-"),
    ("docs/iteration-2-", "docs/history/iteration-2/iteration-2-"),
    ("docs/iteration-3-", "docs/history/iteration-3/iteration-3-"),
    ("docs/iteration-4-", "docs/history/iteration-4/iteration-4-"),
)

_ITERATION_5_DOCUMENTS = {
    "docs/iteration-5-overview.md": "docs/development/iteration-5/overview.md",
    "docs/iteration-5-baseline.md": "docs/development/iteration-5/baseline.md",
    "docs/iteration-5-asset-inventory.md": "docs/development/iteration-5/asset-inventory.md",
    "docs/iteration-5-development-log.md": "docs/development/iteration-5/development-log.md",
    "docs/iteration-5-prompts.md": "docs/development/iteration-5/prompts.md",
    "docs/iteration-5-style-guide.md": "docs/development/iteration-5/style-guide.md",
    "docs/iteration-development-log.md": "docs/history/iteration-development-log.md",
    "docs/long-text-strategy-audit.md": "docs/architecture/long-text-strategy-audit.md",
}


def canonical_frontend_relative(relative: str) -> str:
    """将迁移前的前端测试路径解析到当前 canonical source。"""
    normalized = relative.replace("\\", "/")
    if normalized.startswith("ez_front_dev/"):
        prefix = "ez_front_dev/"
        source_relative = normalized[len(prefix) :]
    else:
        prefix = ""
        source_relative = normalized
    for old_prefix, new_prefix in _FRONTEND_SOURCE_PREFIXES:
        if source_relative.startswith(old_prefix):
            source_relative = new_prefix + source_relative[len(old_prefix) :]
            break
    return prefix + source_relative


def canonical_frontend_path(relative: str) -> Path:
    """返回不保留旧目录别名的前端源文件绝对路径。"""
    return REPO_ROOT / canonical_frontend_relative(relative)


def canonical_document_relative(relative: str) -> str:
    """将迁移前的文档路径解析到当前 canonical 文档路径。"""
    normalized = relative.replace("\\", "/")
    if normalized in _ITERATION_5_DOCUMENTS:
        return _ITERATION_5_DOCUMENTS[normalized]
    for old_prefix, new_prefix in _DOCUMENT_PREFIXES:
        if normalized.startswith(old_prefix):
            return new_prefix + normalized[len(old_prefix) :]
    return normalized


def canonical_document_path(relative: str) -> Path:
    """返回不保留旧根目录别名的文档绝对路径。"""
    return REPO_ROOT / canonical_document_relative(relative)


def repo_path(*parts: str) -> Path:
    return REPO_ROOT.joinpath(*parts)


def frontend_path(*parts: str) -> Path:
    return FRONTEND_ROOT.joinpath(*parts)


def fixture_path(*parts: str) -> Path:
    return FIXTURES_ROOT.joinpath(*parts)
