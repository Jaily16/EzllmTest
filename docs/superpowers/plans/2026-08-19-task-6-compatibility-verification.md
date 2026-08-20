# Task 6 Compatibility Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove the upgraded backend, sample data, Git safety controls, and Vue frontend remain compatible without network, paid-model, or database writes.

**Architecture:** Add only the two missing offline contracts to the existing repository-data tests, then run the backend suite with deprecations promoted to errors. Independently verify credential/Git safety and frontend lint/build, while auditing the optional live database verifier with a fake engine so no MySQL connection is required.

**Tech Stack:** Python 3.11, pytest, SQLAlchemy test doubles, Git, Vue CLI, npm.

## Global Constraints

- Preserve the existing dirty worktree and 50 staged index-only generated-file deletions.
- Do not read `.env`, expose credentials, call a model/embedding API, or incur external cost.
- Do not execute database mutations; Task 6 uses static SQL checks and a fake database engine.
- Do not install/upgrade dependencies, start services, commit, or push.
- Treat every `DeprecationWarning` as a backend test failure.

---

### Task 1: Close sample-data and read-only verifier coverage gaps

**Files:**
- Modify: `ez_back_dev/tests/test_repository_data.py`
- Read only: `ez_back_dev/scripts/verify_database.py`

**Interfaces:**
- Consumes: `ezllmtest.sql`, `verify_database.EXPECTED_TABLES`, and `verify_database.main()`.
- Produces: Offline proof of six SQL tables and proof that the verifier executes only `SELECT COUNT(*) FROM tb_test_project` after metadata inspection.

- [x] **Step 1: Add the SQL table-count test**

```python
def test_sample_database_declares_expected_six_tables():
    sql = SQL_PATH.read_text(encoding="utf-8")
    tables = set(re.findall(r"CREATE TABLE `([^`]+)`", sql))
    assert tables == verify_database.EXPECTED_TABLES
```

- [x] **Step 2: Add the fake-engine read-only verifier test**

```python
def test_live_database_verifier_is_metadata_and_select_only(monkeypatch, capsys):
    engine = _RecordingEngine(project_count=7)
    monkeypatch.setattr(verify_database, "engine", engine)
    monkeypatch.setattr(
        verify_database,
        "inspect",
        lambda _engine: _Inspector(verify_database.EXPECTED_TABLES),
    )
    verify_database.main()
    assert engine.statements == ["SELECT COUNT(*) FROM tb_test_project"]
    assert "Database OK" in capsys.readouterr().out
```

- [x] **Step 3: Run the focused tests**

Run: `python -W error::DeprecationWarning -m pytest tests/test_repository_data.py -q`

Expected: four tests pass with no database or network access.

### Task 2: Run complete backend compatibility verification

**Files:**
- Test: `ez_back_dev/tests/`

**Interfaces:**
- Consumes: configuration, registry, provider mocks, LCEL chains, loaders, import-safety subprocess, API contracts, static sample data, and credential scanner.
- Produces: One full-suite pass under Python 3.11 with deprecation warnings treated as errors.

- [x] **Step 1: Run the entire backend suite**

Run: `python -W error::DeprecationWarning -m pytest tests -q`

Expected: all tests pass; the import-safety test fails if any application import opens a socket.

- [x] **Step 2: Confirm dependency consistency**

Run: `python -m pip check`

Expected: `No broken requirements found.`

### Task 3: Re-run credential and tracked-file gates

**Files:**
- Read only: `.gitignore`
- Read only: `scripts/scan_credentials.py`

**Interfaces:**
- Consumes: current Git tracked, staged, and non-ignored untracked candidate text.
- Produces: Clean redacted scanner result, zero generated artifacts still tracked, and exactly 50 authorized staged index-only deletions.

- [x] **Step 1: Run credential scanning**

Run: `python scripts/scan_credentials.py`

Expected: exit 0 with a count-only clean summary.

- [x] **Step 2: Verify Git safety counts**

Run read-only Git queries to assert generated tracked artifacts equal 0 and staged deletion paths equal 50.

### Task 4: Run frontend compatibility gates

**Files:**
- Read only: `ez_front_dev/`

**Interfaces:**
- Consumes: existing Vue 3 source, shared model option mapping, lockfile, and Vue CLI configuration.
- Produces: lint and production-build exit code 0 without new errors.

- [x] **Step 1: Run lint**

Run: `npm run lint`

Expected: exit 0; existing warnings may remain, but there are no errors.

- [x] **Step 2: Run production build**

Run: `npm run build`

Expected: exit 0; known Browserslist, Vue CLI/Node, lint, and asset-size warnings may remain.

### Task 5: Record Task 6 evidence and the optional live command

**Files:**
- Modify: `docs/iteration-1-tasks.md`
- Modify: `docs/iteration-development-log.md`

**Interfaces:**
- Consumes: exact verification command outputs.
- Produces: Completed Task 6 checklist and a user-runnable live verifier command.

- [x] **Step 1: Record offline verification counts**

Record test totals, scanner scope counts, Git safety counts, lint/build exit results, and known warnings without copying credential-like content.

- [x] **Step 2: Record the optional live read-only database command**

```powershell
Set-Location D:\codex\EzllmTest_v2\ez_back_dev
& 'D:\tool\anaconda3\envs\ezllmtest\python.exe' .\scripts\verify_database.py
```

The command performs SQLAlchemy table metadata inspection and one `SELECT COUNT(*)`; it performs no INSERT, UPDATE, DELETE, DDL, commit, or schema migration.

- [x] **Step 3: Do not commit**

Leave all verification work and pre-existing user changes in the current worktree.
