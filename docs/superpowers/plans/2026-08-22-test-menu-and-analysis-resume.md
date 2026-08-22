# Test Menu Availability and Analysis Artifact Reuse Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Keep every unlocked test type visibly enterable in the test menu and make all saved preliminary-analysis steps resumable without another model call, while preserving explicit user-triggered regeneration.

**Architecture:** Treat route availability—not internal case completion—as the test-menu card status. Keep the existing revision/input/prompt/model artifact primary key, but let a normal analysis-step resume select the newest fresh compatible artifact across model labels when the exact currently selected model has no row. Explicit `regenerate=true` continues to bypass all cached results and saves under the selected model.

**Tech Stack:** Vue 3, TypeScript, Element Plus, FastAPI service layer, SQLAlchemy, pytest, in-memory SQLite.

**Constraints:** Preserve the dirty worktree and existing REST/SSE/database schemas. Do not call real chat models, embeddings, MySQL, or external network services. Do not install dependencies, commit, push, or modify `.env`.

---

### Task 1: Make test-menu cards express navigation availability

**Files:**
- Modify: `ez_back_dev/tests/test_frontend_contracts.py`
- Modify: `ez_front_dev/src/components/TestMenu.vue`

**Step 1: Add the failing contract test**

Assert that `TestMenu.vue` no longer consumes `completedOperations`, does not expose `completed/current` card states, and labels every allowed non-stale card `可进入`.

**Step 2: Run the focused test and verify it fails**

Run the new frontend contract only. The old `已完成`/`可继续` implementation must fail the assertion.

**Step 3: Implement the minimum Vue change**

Replace the completion-derived card state with `available | locked | stale`. Retain stale-family detection and route gating; remove completion-based labels and imports.

**Step 4: Run the focused contract**

Confirm the new contract passes.

### Task 2: Resume persisted preliminary analyses across model-selection resets

**Files:**
- Modify: `ez_back_dev/tests/test_workflow_resume.py`
- Modify: `ez_back_dev/service/workflowArtifactService.py`
- Modify: `ez_back_dev/service/llmWorkflowStreamService.py`

**Step 1: Add failing persistence/resume tests**

For every generic analysis operation, save a result under one model, revisit it with another selected model, and assert the saved database result is returned with zero additional provider calls. Assert the returned artifact metadata identifies the model that actually produced the saved row. Add a separate assertion that `regenerate=true` still calls the provider and writes under the newly selected model.

**Step 2: Run the focused tests and verify failure**

The current exact-model-only lookup must cause an extra provider call.

**Step 3: Implement compatible analysis fallback**

After an exact fresh-key miss, query only analysis artifacts matching project, artifact name, input hash, source revision, and prompt version, reject stale metadata, and choose the newest row deterministically. Reconstruct the returned key from that row. Do not apply this fallback to case artifacts.

**Step 4: Preserve explicit regeneration identity**

When regeneration is requested, generate and persist with the originally requested model key even if a compatible prior analysis artifact exists. Keep normal SSE event names and payload fields unchanged.

**Step 5: Run focused artifact/dispatcher tests**

Confirm all analysis operations resume from SQLite, model switching does not spend tokens on “继续”, and explicit regeneration still invokes the mock provider.

### Task 3: Validate and document the correction

**Files:**
- Modify: `docs/iteration-2-development-log.md`

**Step 1: Run offline regression checks**

Run the focused backend workflow tests, frontend contracts, frontend lint/build, and `git diff --check`. Use only mock/in-memory infrastructure and cleared provider keys.

**Step 2: Record behavior and boundaries**

Document that all preliminary analyses are stored in `tb_project_workflow_artifact`; compatible “继续” resumes without a model call, while explicit “重新生成” remains the only replacement path. Note that no schema, REST route, or SSE event changed.

**Step 3: Report without committing**

Summarize modified files, test results, database behavior, and remaining risks. Stop for the user's next instruction.
