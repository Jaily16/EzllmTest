import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.scan_credentials import collect_sources, format_finding, scan_text


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )


def test_gitignore_keeps_examples_and_ignores_local_artifacts():
    source = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")

    for expected_rule in [
        ".env.*",
        "**/.env.*",
        "!.env.example",
        "!**/.env.example",
        "**/__pycache__/",
        "*.py[cod]",
        ".pytest_cache/",
        ".mypy_cache/",
        ".ruff_cache/",
        "ez_front_dev/dist/",
        ".idea/",
        ".vscode/",
        "*.faiss",
        "**/index.pkl",
    ]:
        assert expected_rule in source


@pytest.mark.parametrize(
    ("text_factory", "expected_rule"),
    [
        (lambda: "API_KEY=" + "sk-" + "a" * 40, "provider API key"),
        (lambda: "LANGSMITH_API_KEY=" + "lsv2_" + "b" * 40, "LangSmith key"),
        (lambda: "DB_PASSWORD=" + "c" * 24, "sensitive assignment"),
        (
            lambda: "DATABASE_URL=mysql+pymysql://app:" + "d" * 24 + "@db.local/app",
            "database URL credential",
        ),
    ],
)
def test_secret_like_values_are_detected_and_redacted(text_factory, expected_rule):
    text = text_factory()
    findings = scan_text(text, "untracked", "fixture.env")

    assert any(finding.rule == expected_rule for finding in findings)
    rendered = "\n".join(format_finding(finding) for finding in findings)
    assert "[REDACTED]" in rendered
    assert text.split("=", 1)[1] not in rendered


@pytest.mark.parametrize(
    "text",
    [
        "API_KEY=replace_with_your_api_key",
        "PASSWORD=invalid_example_password",
        "LANGSMITH_API_KEY=lsv2_test_placeholder_not_a_real_key",
        "DATABASE_URL=mysql+pymysql://user:example_password@127.0.0.1/db",
    ],
)
def test_visible_placeholders_are_allowed(text):
    assert scan_text(text, "tracked", ".env.example") == []


def test_collect_sources_covers_git_scopes_and_skips_ignored_files(tmp_path):
    _git(tmp_path, "init")
    (tmp_path / ".gitignore").write_text(".env\n", encoding="utf-8")
    (tmp_path / "tracked.txt").write_text("safe\n", encoding="utf-8")
    _git(tmp_path, "add", ".gitignore", "tracked.txt")

    worktree_secret = "sk-" + "w" * 40
    staged_secret = "lsv2_" + "s" * 40
    untracked_secret = "sk-" + "u" * 40
    ignored_secret = "sk-" + "i" * 40

    (tmp_path / "tracked.txt").write_text(worktree_secret, encoding="utf-8")
    (tmp_path / "staged.txt").write_text(staged_secret, encoding="utf-8")
    _git(tmp_path, "add", "staged.txt")
    (tmp_path / "untracked.txt").write_text(untracked_secret, encoding="utf-8")
    (tmp_path / ".env").write_text(ignored_secret, encoding="utf-8")

    sources = collect_sources(tmp_path)
    scopes_and_paths = {(source.scope, source.path) for source in sources}

    assert ("tracked", "tracked.txt") in scopes_and_paths
    assert ("staged", "staged.txt") in scopes_and_paths
    assert ("untracked", "untracked.txt") in scopes_and_paths
    assert not any(source.path == ".env" for source in sources)

    all_text = "\n".join(source.text for source in sources)
    assert worktree_secret in all_text
    assert staged_secret in all_text
    assert untracked_secret in all_text
    assert ignored_secret not in all_text
