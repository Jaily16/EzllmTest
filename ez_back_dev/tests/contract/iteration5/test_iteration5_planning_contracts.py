from pathlib import Path


from repo_paths import canonical_document_path
from repo_paths import REPO_ROOT as ROOT


def _read(relative: str) -> str:
    if relative.replace("\\", "/").startswith("docs/"):
        return canonical_document_path(relative).read_text(encoding="utf-8")
    return (ROOT / relative).read_text(encoding="utf-8")


def test_iteration5_overview_is_aspect_level_and_not_marked_complete():
    overview = _read("docs/iteration-5-overview.md")
    assert (
        "状态：Aspect 8 已执行但未完成（Blocked）" in overview
        or "Iteration 5 已完成（Aspect 8 双模式验收通过）" in overview
    )
    assert "不细分 task" in overview
    assert overview.count("### Aspect ") == 8
    for aspect in range(1, 9):
        assert f"### Aspect {aspect} " in overview
    for required in (
        "安全清理",
        "单一版本契约",
        "中文注释",
        "后端领域化重组",
        "前端、测试、资产与文档结构收敛",
        "分步骤、分模块运行",
        "Docker 容器交付",
        "双模式集成验收",
    ):
        assert required in overview
    assert "不在 Aspect 8 之前宣称 Iteration 5 完成" in overview


def test_iteration5_prompts_enforce_read_only_then_aspect1_plan():
    prompts = _read("docs/iteration-5-prompts.md")
    assert prompts.count("## 第一条提示词") == 1
    assert prompts.count("## 第二条提示词") == 1
    assert "完成只读接手报告后立即停止" in prompts
    assert "只为 Iteration 5 Aspect 1" in prompts
    assert "不要规划或实施 Aspect 2–8" in prompts
    assert "不得读取、计算内容哈希或输出大小" in prompts
    assert "不要直接编辑、清理或运行任何命令" in prompts


def test_readme_links_iteration5_without_overstating_delivery():
    readme = _read("README.md")
    assert (
        "Aspect 8 已执行但未完成（Blocked）" in readme
        or "Iteration 5 已完成（Aspect 8 双模式验收通过）" in readme
    )
    assert "docs/development/iteration-5/overview.md" in readme
    assert "docs/development/iteration-5/prompts.md" in readme
