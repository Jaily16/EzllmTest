# Session-Only Selected Test Cases Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep final test cases that require a selected fine-grained target available only in the current page session, without saving or restoring them from the workflow artifact database.

**Architecture:** Add an explicit workflow-catalog persistence policy so the backend dispatcher can distinguish persisted analysis/results from session-only selected-target cases. Ignore historical rows for session-only operations, return their generated SSE result with `saved=false`, and keep only an in-memory Vue result until the page is left; do not restore those steps from `sessionStorage` or project workflow status.

**Tech Stack:** Python 3.11, FastAPI service layer, SQLAlchemy, pytest with in-memory SQLite, Vue 3 Composition API, TypeScript.

## Global Constraints

- Apply session-only behavior to `unit_case`, `integration_case`, `api_case`, `functional_case`, and `nonfunctional_case`.
- Continue persisting every preliminary analysis operation.
- Continue persisting `ui_case`, `db_case`, and `acceptance_case`, which do not select a fine-grained target.
- Do not delete historical MySQL rows; ignore them through catalog-aware reads and lifecycle derivation.
- Do not access real chat models, embeddings, MySQL, `.env`, or external networks.
- Do not install dependencies, stage, commit, or push.

---

### Task 1: Catalog the persistence boundary

**Files:**
- Modify: `ez_back_dev/service/workflowCatalog.py`
- Test: `ez_back_dev/tests/test_workflow_catalog.py`

**Interfaces:**
- Consumes: existing `WorkflowDefinition` inventory.
- Produces: `WorkflowDefinition.persistence: Literal["artifact", "session"]`.

- [ ] **Step 1: Write the failing catalog test**

```python
assert {
    item.operation for item in list_workflow_definitions()
    if item.persistence == "session"
} == {
    "unit_case", "integration_case", "api_case",
    "functional_case", "nonfunctional_case",
}
```

- [ ] **Step 2: Run the catalog test and verify it fails**

Run `python -m pytest tests/test_workflow_catalog.py -q`; expect the missing `persistence` field to fail.

- [ ] **Step 3: Add the immutable persistence field**

Define `WorkflowPersistence = Literal["artifact", "session"]`, default the field to `"artifact"`, and mark exactly the five selected-target final operations `"session"`.

- [ ] **Step 4: Run the catalog test and verify it passes**

Run `python -m pytest tests/test_workflow_catalog.py -q`; expect all catalog tests to pass.

### Task 2: Stop database save and restore for session-only cases

**Files:**
- Modify: `ez_back_dev/service/llmWorkflowStreamService.py`
- Modify: `ez_back_dev/service/projectWorkflowStatusService.py`
- Test: `ez_back_dev/tests/test_workflow_resume.py`
- Test: `ez_back_dev/tests/test_project_workflow_status.py`

**Interfaces:**
- Consumes: `WorkflowDefinition.persistence`.
- Produces: session-only SSE completion with `saved=false` and no artifact event/write.

- [ ] **Step 1: Write failing dispatcher tests**

For each of the five session-only operations, invoke the mock workflow twice and assert two provider executions, zero `TestProjectWorkflowArtifact` rows, no `artifact` event, and `completed.saved is False`. Keep persisted workflows' exact-repeat tests unchanged.

- [ ] **Step 2: Write the historical-row status test**

Insert a historical `nonfunctional_case` row into in-memory SQLite and assert `_load_artifact_facts()` ignores it while retaining a persisted `nonfunctional_info` fact.

- [ ] **Step 3: Run focused backend tests and verify failure**

Run the named workflow-resume and project-status tests; expect current save/resume behavior to fail.

- [ ] **Step 4: Implement catalog-aware dispatch**

For `persistence == "session"`, build the revision/input key without querying artifacts, run the existing prerequisite validation and workflow stream, skip `save_workflow_artifact`, skip the `artifact` SSE event, and emit `completed(saved=False, from_cache=False, ...)`. Persisted operations retain the existing path unchanged.

- [ ] **Step 5: Ignore historical session-only rows in status**

Build `_OPERATION_BY_ARTIFACT_KEY` only from definitions with `persistence == "artifact"`, so old rows cannot make a session-only case appear completed or stale.

- [ ] **Step 6: Run focused backend tests and verify they pass**

Run the workflow catalog, resume, stream-service, and project-status suites using cleared provider keys and in-memory SQLite.

### Task 3: Keep selected-target case results out of browser restoration

**Files:**
- Modify: `ez_front_dev/src/composables/useTestWorkflow.ts`
- Modify: `ez_front_dev/src/components/UnitTest.vue`
- Modify: `ez_front_dev/src/components/IntegrationTest.vue`
- Modify: `ez_front_dev/src/components/ApiTest.vue`
- Modify: `ez_front_dev/src/components/FounctionalTest.vue`
- Modify: `ez_front_dev/src/components/NonfunctionalTest.vue`
- Test: `ez_back_dev/tests/test_frontend_contracts.py`

**Interfaces:**
- Consumes: `TestWorkflowStepDefinition.persistResult?: boolean`.
- Produces: transient results that remain reactive on the current mounted page but are omitted from `sessionStorage` and ignored during restore/status hydration.

- [ ] **Step 1: Write the failing frontend contract**

Assert the five selected-target case definitions use `persistResult: false`, the other three case definitions do not, and the composable filters storage/restore/status completion for non-persisted steps.

- [ ] **Step 2: Run the focused contract and verify failure**

Run the new frontend contract; expect the missing field and filtering logic to fail.

- [ ] **Step 3: Implement transient Vue step state**

Add `persistResult` to runtime steps with a default of `true`. Keep `completeStep()` reactive for current-page rendering, but omit transient steps from `storedWorkflow()`, skip them in `restoreSession()`, and prevent old `completed_operations` values from marking them completed in `applyStatus()`.

- [ ] **Step 4: Mark the five page definitions**

Set `persistResult: false` only on `unit_case`, `integration_case`, `api_case`, `functional_case`, and `nonfunctional_case` definitions.

- [ ] **Step 5: Run frontend contracts, lint, and build**

Expect contracts and lint to pass; expect build success with only existing bundle-size warnings.

### Task 4: Reconcile offline baselines and document the override

**Files:**
- Modify if required: `ez_back_dev/tests/test_workflow_cost_baseline.py`
- Modify if required: `docs/iteration-2-token-baseline.md`
- Modify: `docs/iteration-2-development-log.md`

**Interfaces:**
- Consumes: session-only repeat semantics.
- Produces: an honest offline gate that no longer claims zero-call cross-page repeats for the five deliberately transient final operations.

- [ ] **Step 1: Run the cost baseline**

Run `python -m pytest tests/test_workflow_cost_baseline.py -q` with mock chat/embedding and fixed documents.

- [ ] **Step 2: Update only assertions affected by the policy**

Keep zero-call repeat requirements for all persisted analyses and persisted final results. Record that the five session-only case operations intentionally rerun after leaving the page and therefore have first-run-equivalent offline repeat cost.

- [ ] **Step 3: Run the complete offline gate**

Run the backend suite with the known user-owned repository-data assertion deselected, then credential scan and `git diff --check`.

- [ ] **Step 4: Record the compatibility boundary**

Document the five-operation policy, current-page-only result lifetime, ignored historical rows, unchanged analysis persistence, and the absence of real provider/database access.
