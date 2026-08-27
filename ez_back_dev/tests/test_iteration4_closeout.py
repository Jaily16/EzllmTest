from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_closeout_reports_all_aspects_evidence_limits_and_release_state():
    closeout = _read("docs/iteration-4-closeout.md")
    for required in (
        "Aspect 1–8",
        "19 个 workflow",
        "22 个类型化工具",
        "LangGraph",
        "Redis",
        "MCP",
        "OpenTelemetry",
        "104/104",
        "18/18",
        "session-only",
        "persisted",
        "approval bypass",
        "duplicate side effect",
        "project isolation",
        "awaiting_explicit_push",
        "未 stage、未 commit、未 fetch、未 pull、未 push",
        "真实模型 Agent 质量验收未执行",
    ):
        assert required in closeout
    assert "真实模型 Agent 验收通过" not in closeout
    assert "GitHub Actions 已通过" not in closeout


def test_readme_presents_iteration4_as_verified_without_erasing_limits():
    readme = _read("README.md")
    for required in (
        "Iteration 1–4",
        "LangGraph 单 Agent",
        "Agent API",
        "Redis",
        "MCP",
        "OpenTelemetry",
        "Docker Compose",
        "Vite",
        "docs/iteration-4-closeout.md",
        "agentAcceptance",
        "真实模型 Agent 质量验收未执行",
    ):
        assert required in readme
    assert "Iteration 4 路线图（规划完成，尚未启动）" not in readme
    assert "Vue CLI 生产构建仍可能" not in readme


def test_overview_and_prompt_are_archived_as_completed_history():
    overview = _read("docs/iteration-4-overview.md")
    prompts = _read("docs/iteration-4-prompts.md")
    assert "Aspect 1–8 已完成离线验收" in overview
    assert "docs/iteration-4-closeout.md" in overview
    assert "Iteration 4 已完成离线验收" in prompts
    assert "历史执行提示" in prompts
    assert "docs/iteration-4-closeout.md" in prompts
