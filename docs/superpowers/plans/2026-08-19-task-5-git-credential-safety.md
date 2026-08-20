# Task 5 Git and Credential Safety Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent local credentials and generated artifacts from entering Git, and provide a repository scanner that reports secret-like values only as redacted findings.

**Architecture:** Keep ignore policy in the root `.gitignore`, implement a standard-library-only scanner in `scripts/scan_credentials.py`, and test scanner behavior with synthetic values assembled at runtime. The scanner treats tracked working-tree files, staged index blobs, and non-ignored untracked text files as distinct scopes and never prints matched values or source lines.

**Tech Stack:** Git, Python 3.11 standard library, pytest.

## Global Constraints

- Preserve all current uncommitted work as user-owned assets.
- Never read or print the real `.env` contents or any credential value.
- Do not delete local caches or IDE files; remove generated files from the Git index only.
- Do not install dependencies, call model APIs, commit, or push.
- Use visibly invalid placeholders in examples and tests.

---

### Task 1: Expand repository ignore policy

**Files:**
- Modify: `.gitignore`
- Test: `ez_back_dev/tests/test_credential_scan.py`

**Interfaces:**
- Consumes: Git ignore pattern semantics.
- Produces: Explicit exceptions for root and nested `.env.example` files while ignoring all other environment files, caches, build output, IDE metadata, and local vector indexes.

- [x] **Step 1: Add an ignore-policy test**

```python
def test_gitignore_keeps_examples_and_ignores_local_artifacts():
    source = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "!.env.example" in source
    assert "!**/.env.example" in source
    assert "**/__pycache__/" in source
    assert "ez_front_dev/dist/" in source
```

- [x] **Step 2: Run the focused test and confirm it fails before implementation**

Run: `python -m pytest tests/test_credential_scan.py -q`

Expected: failure because the new explicit exceptions and complete ignore policy are not present.

- [x] **Step 3: Add the minimal ignore rules**

```gitignore
.env
.env.*
**/.env
**/.env.*
!.env.example
!**/.env.example
**/__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/
ez_front_dev/node_modules/
ez_front_dev/dist/
.idea/
.vscode/
*.iml
.DS_Store
Thumbs.db
*.faiss
**/index.pkl
```

- [x] **Step 4: Run the focused test**

Run: `python -m pytest tests/test_credential_scan.py -q`

Expected: ignore-policy test passes.

### Task 2: Implement redacted multi-scope credential scanning

**Files:**
- Create: `scripts/scan_credentials.py`
- Create: `ez_back_dev/tests/test_credential_scan.py`

**Interfaces:**
- Consumes: `git ls-files -z`, `git diff --cached --name-only -z`, and `git show :path`.
- Produces: `scan_text(text: str, source: str, path: str) -> list[Finding]`, `collect_sources(root: Path) -> list[SourceText]`, and CLI exit codes 0 for clean, 1 for findings, 2 for operational failure.

- [x] **Step 1: Add scanner unit tests**

```python
def test_secret_like_value_is_redacted():
    secret = "sk-" + "a" * 40
    findings = scan_text(f"API_KEY={secret}", "untracked", "fixture.env")
    rendered = format_finding(findings[0])
    assert "[REDACTED]" in rendered
    assert secret not in rendered


def test_visible_placeholders_are_allowed():
    assert scan_text("API_KEY=replace_with_your_api_key", "tracked", ".env.example") == []
```

- [x] **Step 2: Run the scanner tests and confirm they fail before implementation**

Run: `python -m pytest tests/test_credential_scan.py -q`

Expected: import failure because the scanner module does not yet exist.

- [x] **Step 3: Implement scanner rules and source collection**

Implement named rules for provider-style `sk-` tokens, LangSmith `lsv2_` tokens, sensitive assignments such as `API_KEY`, `PASSWORD`, `DB_PASSWORD`, and `DATABASE_URL`, and credential-bearing MySQL URLs. Skip binary/oversized files and visibly invalid placeholder values. Render every result as `scope:path:line: rule [REDACTED]` without source excerpts, hashes, or matched values.

- [x] **Step 4: Run the focused scanner tests**

Run: `python -m pytest tests/test_credential_scan.py -q`

Expected: all scanner tests pass.

### Task 3: Stop tracking generated artifacts without deleting working copies

**Files:**
- Update: Git index entries matching `__pycache__/`, `*.pyc`, `.DS_Store`, `.idea/`, `.vscode/`, and `*.iml`.

**Interfaces:**
- Consumes: exact paths returned by `git ls-files`.
- Produces: staged index deletions while every local working-tree file remains present.

- [x] **Step 1: Capture the exact generated paths currently tracked**

Run: `git ls-files | rg "(^|/)(__pycache__/|.*\\.pyc$|\\.DS_Store$|\\.idea/|\\.vscode/|.*\\.iml$)"`

Expected: only generated cache, OS, and IDE metadata paths.

- [x] **Step 2: Remove only those exact paths from the index**

Run `git rm --cached --ignore-unmatch` with the verified literal paths. Do not use recursive filesystem deletion and do not remove source directories.

- [x] **Step 3: Verify local copies still exist and Git stages only index deletions**

Run: `git status --short`

Expected: generated entries are staged as deleted; unrelated user changes remain unchanged; local files are still present but ignored.

### Task 4: Run repository safety verification and record completion

**Files:**
- Modify: `docs/iteration-1-tasks.md`
- Modify: `docs/iteration-development-log.md`

**Interfaces:**
- Consumes: scanner CLI and pytest suite.
- Produces: evidence for all Task 5 acceptance conditions.

- [x] **Step 1: Run focused tests**

Run: `python -m pytest tests/test_credential_scan.py -q`

Expected: all tests pass.

- [x] **Step 2: Run the scanner across tracked, staged, and untracked candidate files**

Run: `python scripts/scan_credentials.py`

Expected: exit 0 and a count-only clean summary, or exit 1 with redacted findings only. Never print a source line or secret value.

- [x] **Step 3: Verify ignore behavior and tracked generated-file count**

Run: `git check-ignore -v .env ez_back_dev/.env ez_front_dev/.env`

Run: `git check-ignore .env.example ez_front_dev/.env.example`

Run: `git ls-files | rg "(^|/)(__pycache__/|.*\\.pyc$|\\.DS_Store$|\\.idea/|\\.vscode/|.*\\.iml$)"`

Expected: real environment files are ignored, example files are not ignored, and no generated paths remain tracked.

- [x] **Step 4: Update Task 5 checklist and development log**

Record exact commands and result counts without recording credentials, source excerpts, or secret fingerprints.

- [x] **Step 5: Do not commit**

Leave all Task 5 changes in the existing user-owned working tree for review.
