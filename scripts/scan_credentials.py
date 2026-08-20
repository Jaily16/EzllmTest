"""Scan Git-visible text for credential-like values without printing secrets."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAX_TEXT_BYTES = 2 * 1024 * 1024

TEXT_SUFFIXES = {
    ".bat",
    ".cfg",
    ".conf",
    ".css",
    ".env",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".properties",
    ".ps1",
    ".py",
    ".sh",
    ".sql",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".vue",
    ".xml",
    ".yaml",
    ".yml",
}
TEXT_FILENAMES = {
    "dockerfile",
    "gemfile",
    "makefile",
    "procfile",
    "readme",
    "requirements.txt",
}

PLACEHOLDER_MARKERS = (
    "replace_",
    "replace-with-",
    "placeholder",
    "example",
    "dummy",
    "fake",
    "invalid",
    "not_a_real",
    "not-a-real",
    "changeme",
    "your_",
    "your-",
    "<redacted>",
    "[redacted]",
    "xxxx",
)


@dataclass(frozen=True)
class Finding:
    scope: str
    path: str
    line: int
    rule: str


@dataclass(frozen=True)
class SourceText:
    scope: str
    path: str
    text: str


@dataclass(frozen=True)
class CredentialRule:
    name: str
    pattern: re.Pattern[str]
    value_group: int


class CredentialScanError(RuntimeError):
    """Raised for a safe-to-report scanner operational failure."""


RULES = (
    CredentialRule(
        "provider API key",
        re.compile(r"\b(sk-[A-Za-z0-9_-]{20,})\b"),
        1,
    ),
    CredentialRule(
        "LangSmith key",
        re.compile(r"\b(lsv2_[A-Za-z0-9_-]{20,})\b", re.IGNORECASE),
        1,
    ),
    CredentialRule(
        "database URL credential",
        re.compile(
            r"\bmysql(?:\+[A-Za-z0-9_]+)?://[^\s:/@]+:([^\s/@]+)@[^\s]+",
            re.IGNORECASE,
        ),
        1,
    ),
    CredentialRule(
        "sensitive assignment",
        re.compile(
            r"(?m)(?:^|[\s{,])['\"]?"
            r"(?:[A-Z][A-Z0-9_]*(?:API_KEY|SECRET|PASSWORD|PASSWD|PWD|DATABASE_URL)"
            r"|api[_-]?key|apiKey|secret(?:[_-]?key)?|secretKey"
            r"|password|passwd|pwd|db[_-]?password|dbPassword"
            r"|database[_-]?url|databaseUrl|langchain_api_key|langsmith_api_key)"
            r"['\"]?\s*[:=]\s*['\"]?([^\s'\"#,;]+)"
        ),
        1,
    ),
)


def _is_placeholder(value: str) -> bool:
    normalized = value.strip().strip("'\"").lower()
    if not normalized:
        return True
    if any(marker in normalized for marker in PLACEHOLDER_MARKERS):
        return True
    if normalized.startswith(("${", "$env:", "os.getenv", "settings.", "config.")):
        return True
    if any(character in normalized for character in "{}()+*"):
        return True
    return False


def _looks_sensitive(rule: CredentialRule, value: str) -> bool:
    if _is_placeholder(value):
        return False
    if rule.name in {"provider API key", "LangSmith key"}:
        return True
    if rule.name == "database URL credential":
        return len(value) >= 8
    return len(value) >= 12 and bool(re.search(r"[A-Za-z0-9]", value))


def scan_text(text: str, scope: str, path: str) -> list[Finding]:
    """Return metadata-only findings for one text source."""

    findings: list[Finding] = []
    seen: set[tuple[int, str]] = set()
    for rule in RULES:
        for match in rule.pattern.finditer(text):
            value = match.group(rule.value_group)
            if not _looks_sensitive(rule, value):
                continue
            line = text.count("\n", 0, match.start()) + 1
            finding_key = (line, rule.name)
            if finding_key in seen:
                continue
            seen.add(finding_key)
            findings.append(Finding(scope=scope, path=path, line=line, rule=rule.name))
    return findings


def _redact_path(path: str) -> str:
    redacted = path
    for rule in RULES[:2]:
        redacted = rule.pattern.sub("[REDACTED]", redacted)
    return redacted


def format_finding(finding: Finding) -> str:
    """Render a finding without including matched content or source text."""

    return (
        f"{finding.scope}:{_redact_path(finding.path)}:{finding.line}: "
        f"{finding.rule} [REDACTED]"
    )


def _git(root: Path, *args: str) -> bytes:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise CredentialScanError("Git metadata could not be read") from exc
    return result.stdout


def _git_paths(root: Path, *args: str) -> list[str]:
    output = _git(root, *args)
    return [
        item.decode("utf-8", errors="surrogateescape")
        for item in output.split(b"\0")
        if item
    ]


def _is_candidate_text(path: str) -> bool:
    candidate = Path(path)
    name = candidate.name.lower()
    return (
        name.startswith(".env")
        or name in TEXT_FILENAMES
        or candidate.suffix.lower() in TEXT_SUFFIXES
    )


def _decode_text(content: bytes) -> str | None:
    if not content or len(content) > MAX_TEXT_BYTES or b"\0" in content:
        return None
    return content.decode("utf-8", errors="replace")


def _read_worktree_text(root: Path, path: str) -> str | None:
    root_resolved = root.resolve()
    candidate = (root / path).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError:
        return None
    try:
        content = candidate.read_bytes()
    except (OSError, ValueError):
        return None
    return _decode_text(content)


def _read_staged_text(root: Path, path: str) -> str | None:
    try:
        content = _git(root, "show", f":{path}")
    except CredentialScanError:
        return None
    return _decode_text(content)


def collect_sources(root: Path) -> list[SourceText]:
    """Collect text from tracked worktree, staged index, and untracked scopes."""

    root = root.resolve()
    scope_paths = {
        "tracked": _git_paths(root, "ls-files", "-z"),
        "staged": _git_paths(
            root,
            "diff",
            "--cached",
            "--name-only",
            "--diff-filter=ACMR",
            "-z",
        ),
        "untracked": _git_paths(
            root,
            "ls-files",
            "--others",
            "--exclude-standard",
            "-z",
        ),
    }

    sources: list[SourceText] = []
    for scope, paths in scope_paths.items():
        for path in paths:
            if not _is_candidate_text(path):
                continue
            text = (
                _read_staged_text(root, path)
                if scope == "staged"
                else _read_worktree_text(root, path)
            )
            if text is not None:
                sources.append(SourceText(scope=scope, path=path, text=text))
    return sources


def scan_sources(sources: Iterable[SourceText]) -> list[Finding]:
    findings: list[Finding] = []
    for source in sources:
        findings.extend(scan_text(source.text, source.scope, source.path))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scan Git-visible text and redact every credential finding."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=PROJECT_ROOT,
        help="Git worktree root (defaults to this repository)",
    )
    args = parser.parse_args(argv)

    try:
        sources = collect_sources(args.root)
    except CredentialScanError:
        print("Credential scan failed: Git metadata could not be read", file=sys.stderr)
        return 2

    findings = scan_sources(sources)
    if findings:
        for finding in findings:
            print(format_finding(finding))
        print(
            f"Credential scan found {len(findings)} redacted finding(s) "
            f"across {len(sources)} candidate source(s)."
        )
        return 1

    counts = {
        scope: sum(source.scope == scope for source in sources)
        for scope in ("tracked", "staged", "untracked")
    }
    print(
        "Credential scan clean: "
        f"tracked={counts['tracked']}, staged={counts['staged']}, "
        f"untracked={counts['untracked']}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
