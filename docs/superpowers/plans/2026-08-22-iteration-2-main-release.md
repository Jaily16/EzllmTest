# Iteration 2 Main Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish the completed Iteration 2 implementation to GitHub `main` with schema-only SQL and no local project documents, credentials, or runtime data.

**Architecture:** Convert the tracked base SQL dump from sample-data form to deterministic empty-table DDL while retaining the additive Iteration 2 migration. Enforce the release boundary with repository tests and ignore rules, run the complete offline gate, stage only Git-visible source/schema/docs changes, commit on local `main`, fetch/reconcile `origin/main`, and push only after the staged tree passes the same safety checks.

**Tech Stack:** Git, GitHub HTTPS remote, MySQL DDL, Python 3.11/pytest, Vue 3/npm.

## Global Constraints

- Upload and merge the completed iteration into `main`.
- Every uploaded SQL table must contain no data rows.
- Do not upload `.env`, API keys, passwords, `example/`, runtime project documents, frontend build output, caches, or local vector indexes.
- Preserve the user's local `example/` and current runtime project documents on disk.
- Do not call real chat models, embeddings, or MySQL while validating the release.
- Do not force-push or rewrite published history.

---

### Task 1: Enforce schema-only repository data

**Files:**
- Modify: `ezllmtest.sql`
- Modify: `README.md`
- Modify: `ez_back_dev/tests/test_repository_data.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: existing six-table base dump and additive `iteration_2_workflow_artifacts.sql` migration.
- Produces: base schema DDL with six empty tables plus a seventh-table additive schema-only migration.

- [ ] **Step 1: Change repository-data tests first**

Replace the seven-project/47-document assertions with checks that both SQL files contain `CREATE TABLE` statements and contain no `INSERT`, `REPLACE`, `LOAD DATA`, or executable MySQL dump data directives.

- [ ] **Step 2: Run the focused test and verify it fails**

Run `python -m pytest tests/test_repository_data.py -q`; expect the six existing `INSERT INTO` statements in `ezllmtest.sql` to fail.

- [ ] **Step 3: Remove only data statements from the base dump**

Mechanically remove all six single-line `INSERT INTO` statements, preserve all six DDL definitions, encoding, constraints, indexes, and session directives, and verify zero data-write statements remain.

- [ ] **Step 4: Exclude runtime project documents**

Add `/ez_back_dev/static/projects/` to `.gitignore`. Keep the existing `/example/` rule. Stage tracked historical project-document deletions, but never stage the current untracked runtime project directory.

- [ ] **Step 5: Correct setup documentation**

Describe `ezllmtest.sql` as six empty legacy tables and the Iteration 2 migration as the seventh empty table. Remove instructions that promise seven sample projects.

- [ ] **Step 6: Run the focused repository test**

Expect every schema-only and exclusion assertion to pass without reading `.env` or connecting to MySQL.

### Task 2: Run final offline release gates

**Files:**
- Verify: `ez_back_dev/tests/`
- Verify: `ez_front_dev/`
- Verify: `scripts/scan_credentials.py`

**Interfaces:**
- Consumes: the candidate release worktree.
- Produces: evidence that the exact release candidate is testable and free of detected credentials/data statements.

- [ ] **Step 1: Run the complete backend suite**

Use Python 3.11 with provider keys cleared and an in-memory SQLite URL; run `python -m pytest tests -q`. Expect every test to pass with no deselection after schema sanitization.

- [ ] **Step 2: Run frontend quality gates**

Run `npm run lint` and `npm run build`; expect lint success and a successful production build, allowing only the documented bundle-size and dependency deprecation warnings.

- [ ] **Step 3: Run release safety scans**

Run the credential scanner, schema-only SQL audit, generated/runtime asset tracking checks, and `git diff --check`. Fail the release if any credential-like value, SQL data write, unignored runtime document, or whitespace error is detected.

### Task 3: Commit and synchronize main safely

**Files:**
- Stage: all intended Iteration 2 source, tests, documentation, schema-only SQL, migration, and tracked project-document deletions.
- Exclude: ignored runtime/local files.

**Interfaces:**
- Consumes: a passing release candidate and local `main` currently based on `origin/main`.
- Produces: one Iteration 2 release commit on GitHub `main`.

- [ ] **Step 1: Fetch and verify remote ancestry**

Run `git fetch origin main`, then inspect `git rev-list --left-right --count origin/main...HEAD`. If the remote advanced, create the local commit first and rebase it non-interactively onto `origin/main`; do not force-push.

- [ ] **Step 2: Stage the explicit release tree**

Run `git add -A`, then prove `.env`, `example/`, `ez_front_dev/dist/`, runtime project files, caches, and local indexes are absent from `git diff --cached --name-only`.

- [ ] **Step 3: Re-run staged credential and SQL checks**

Scan the staged index and confirm both staged SQL files have zero data-write statements before committing.

- [ ] **Step 4: Create the release commit**

Commit with message `feat: complete iteration 2 workflow optimization`.

- [ ] **Step 5: Push main without rewriting history**

Push `HEAD:main` to `origin`. If rejected because the remote advanced, fetch, rebase, re-run the focused safety gate, and retry a normal push.

- [ ] **Step 6: Verify the remote result**

Confirm local `HEAD`, `origin/main`, and `git ls-remote origin refs/heads/main` resolve to the same commit; report commit ID, tests, schema-only status, and excluded local assets.
