# EzllmTest Iteration 2 Workflow and Token Efficiency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn project creation, project analysis, test planning, test-menu navigation, and every test-type interaction into one resumable and internally consistent workflow while measurably reducing repeated embeddings, duplicated context, unnecessary reasoning, and redundant model calls.

**Architecture:** Introduce one backend workflow catalog and an additive persisted artifact layer keyed by project source revision, operation, selection payload, prompt version, and model. Derive a project lifecycle state from documents and artifacts, reuse revision-scoped retrieval indexes, apply operation-specific context/reasoning/output budgets, and let Vue pages resume saved steps through one workflow-state composable while preserving all Iteration 1 REST/SSE contracts.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2, MySQL 8, Pydantic 2, LangChain Core 1.x, OpenAI-compatible async streaming, Vue 3 Composition API, TypeScript, Element Plus, pytest, Vue CLI.

## Global Constraints

- Execute exactly one task at a time and update this file plus `docs/iteration-2-development-log.md` after every completed task.
- Preserve all existing public REST paths, `POST /project/llm/plan/stream`, `POST /project/llm/workflow/stream`, SSE event names, stable model labels, and legacy `{status, reason, data}` response envelopes.
- Database changes must be additive. Existing six tables, existing rows, project IDs, `InfoType` values 1–23, and legacy readers must remain valid.
- Never read, print, stage, or commit a real `.env`, API key, database password, raw provider exception, reasoning trace, or uploaded customer document content.
- Automated tests must mock chat and embedding calls. A real model, embedding, database migration, or paid benchmark requires separate explicit user approval immediately before execution.
- A selected frontend provider remains the final-answer provider. Efficiency policy may lower/disable thinking for mechanical intermediate stages but must expose that policy in `meta` and must not silently switch vendors.
- Cancellation, disconnect, invalid structured output, or persistence failure must not replace a previously valid artifact.
- Every optimization must have a before/after call-count or token-budget assertion; do not claim savings from elapsed time alone.
- Preserve contextual placement of progress, reasoning, streamed output, usage, cancellation, and retry panels below the button that started the active operation.

---

## Status Legend

- `[ ]` pending
- `[-]` in progress
- `[x]` completed and verified
- `[!]` blocked by an explicit user or external-system action

## Task 0: Establish the workflow catalog and measurable offline baseline

**Dependencies:** Iteration 1 closeout only.

**Files:**
- Create: `ez_back_dev/service/workflowCatalog.py`
- Create: `ez_back_dev/tests/test_workflow_catalog.py`
- Create: `ez_back_dev/tests/test_workflow_cost_baseline.py`
- Create: `docs/iteration-2-development-log.md`
- Create: `docs/iteration-2-token-baseline.md`

**Interfaces:**
- Produces `WorkflowDefinition(operation, phase, prerequisites, result_artifact, cache_artifacts, source_corpus, supports_regenerate)`.
- Produces `WORKFLOW_DEFINITIONS`, `get_workflow_definition(operation)`, and `list_workflow_definitions()` for the plan workflow plus all 18 generic operations.
- Produces an offline baseline fixture recording model-call count, embedding-build count, input-context token count, and output cap per operation without calling a provider.

- [x] **Step 1: Add a failing complete-inventory test**

```python
EXPECTED_OPERATIONS = {
    "project_analysis", "unit_menu", "unit_info", "unit_case",
    "integration_menu", "integration_info", "integration_case",
    "api_info", "api_case", "ui_info", "ui_case", "db_info", "db_case",
    "functional_info", "functional_case", "nonfunctional_info",
    "nonfunctional_case", "acceptance_info", "acceptance_case",
}

def test_workflow_catalog_is_complete_and_unique():
    definitions = list_workflow_definitions()
    assert {item.operation for item in definitions} == EXPECTED_OPERATIONS
    assert len({item.result_artifact for item in definitions}) == len(definitions)
```

- [x] **Step 2: Run the focused test and confirm failure**

Run: `D:\tool\anaconda3\envs\ezllmtest\python.exe -m pytest tests/test_workflow_catalog.py -q`

Expected: FAIL because the catalog does not exist.

- [x] **Step 3: Implement immutable definitions without changing dispatch behavior**

```python
@dataclass(frozen=True)
class WorkflowDefinition:
    operation: str
    phase: Literal["project", "analysis", "case"]
    prerequisites: tuple[str, ...]
    result_artifact: str
    cache_artifacts: tuple[str, ...]
    source_corpus: Literal["all", "requirements", "design", "knowledge", "mixed"]
    supports_regenerate: bool = True
```

Use the catalog as metadata only in Task 0. Add a contract proving the existing dispatcher's operation set equals the catalog's 18 generic operations.

- [x] **Step 4: Add mocked baseline counters**

Create deterministic small-document and large-document fixtures. Patch `stream_chat_completion`, embedding construction, and document loaders; record calls by stage and count prompt input tokens with the existing tokenizer. Do not store prompt bodies or reasoning text in the report.

- [x] **Step 5: Write the baseline report and run current gates**

Document each operation's small/large call graph and repeated-run behavior in `docs/iteration-2-token-baseline.md`.

Run: `D:\tool\anaconda3\envs\ezllmtest\python.exe -m pytest tests/test_workflow_catalog.py tests/test_workflow_cost_baseline.py -q`

Expected: PASS with zero sockets/provider clients created.

## Task 1: Add revision-aware workflow artifact persistence

**Dependencies:** Task 0.

**Files:**
- Modify: `ez_back_dev/model/TestProject.py`
- Create: `ez_back_dev/migrations/iteration_2_workflow_artifacts.sql`
- Create: `ez_back_dev/dao/workflowArtifactDao.py`
- Create: `ez_back_dev/service/projectRevisionService.py`
- Create: `ez_back_dev/tests/test_workflow_artifact_dao.py`
- Create: `ez_back_dev/tests/test_project_revision_service.py`

**Interfaces:**
- Adds table `tb_project_workflow_artifact` without modifying the six legacy tables.
- Produces `compute_source_revision(entries) -> str`, `compute_project_source_revision(pid) -> str`, `artifact_input_hash(operation, payload) -> str`, `get_fresh_artifact(...)`, `save_artifact(...)`, and `invalidate_project_artifacts(pid, source_revision)`.

- [x] **Step 1: Add failing source-revision and artifact tests**

```python
def test_source_revision_is_order_independent(tmp_path):
    first = compute_source_revision([doc_b, doc_a])
    second = compute_source_revision([doc_a, doc_b])
    assert first == second

def test_changed_document_makes_artifact_stale(fake_session):
    save_artifact("Ez1", "api_info", "rev-1", "input-1", "prompt-v1", "DeepSeek", "value", {})
    assert get_fresh_artifact("Ez1", "api_info", "rev-2", "input-1", "prompt-v1", "DeepSeek") is None
```

- [x] **Step 2: Define the additive table and idempotent SQL migration**

Use a composite unique key on `(project_id, artifact_key, input_hash, source_revision, prompt_version, model_label)`. Store final content and a small metadata JSON object; never store reasoning. Include `created_at`/`updated_at` timestamps and an index on `(project_id, artifact_key)`.

```sql
CREATE TABLE IF NOT EXISTS tb_project_workflow_artifact (
  project_id VARCHAR(21) NOT NULL,
  artifact_key VARCHAR(80) NOT NULL,
  input_hash CHAR(64) NOT NULL,
  source_revision CHAR(64) NOT NULL,
  prompt_version VARCHAR(32) NOT NULL,
  model_label VARCHAR(32) NOT NULL,
  content LONGTEXT NOT NULL,
  metadata_json TEXT NOT NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  PRIMARY KEY (project_id, artifact_key, input_hash, source_revision, prompt_version, model_label),
  CONSTRAINT fk_workflow_artifact_project FOREIGN KEY (project_id) REFERENCES tb_test_project(id)
);
```

- [x] **Step 3: Implement canonical hashes**

The source revision must hash sorted relative path, document kind, size, and file SHA-256. The input hash must use UTF-8 JSON with sorted keys and compact separators. Exclude request IDs, timestamps, and UI-only labels.

```python
def artifact_input_hash(operation: str, payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        {"operation": operation, "payload": payload},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

- [x] **Step 4: Implement atomic upsert and stale lookup**

Use one SQLAlchemy session and rollback on error. Keep all existing `testProjectDao` methods unchanged; later tasks may read legacy `InfoType` values as a compatibility fallback.

```python
def save_artifact(record: WorkflowArtifactRecord) -> bool: ...

def get_fresh_artifact(
    project_id: str,
    artifact_key: str,
    source_revision: str,
    input_hash: str,
    prompt_version: str,
    model_label: str,
) -> WorkflowArtifactRecord | None: ...
```

- [x] **Step 5: Verify without touching live MySQL**

Run DAO tests with a fake/in-memory-compatible session and statically assert the migration contains only additive `CREATE TABLE IF NOT EXISTS`/`CREATE INDEX` statements.

## Task 2: Make project creation idempotent, recoverable, and explicit

**Dependencies:** Task 1.

**Files:**
- Modify: `ez_back_dev/app/routers.py`
- Modify: `ez_back_dev/dao/testProjectDao.py`
- Create: `ez_back_dev/service/projectSetupService.py`
- Modify: `ez_front_dev/src/views/CreateView.vue`
- Create: `ez_front_dev/src/state/projectSetup.ts`
- Create: `ez_back_dev/tests/test_project_setup_service.py`
- Modify: `ez_back_dev/tests/test_api_contracts.py`
- Modify: `ez_back_dev/tests/test_frontend_contracts.py`

**Interfaces:**
- Adds `GET /project/setup/status/{pid}` and `POST /project/setup/finalize/{pid}`.
- Produces setup stages `project_created`, `knowledge_uploaded`, `requirements_uploaded`, `design_uploaded`, `documents_ready`, and `setup_complete`.
- Existing `/project/add`, `/uploadFile/{pid}/{doctype}`, and `/project/type/analyze/{pid}` remain valid.

- [x] **Step 1: Add failing setup-status and idempotency tests**

Assert that repeated finalize calls return the same source revision, missing required documents return 422 without deleting uploaded files, and retrying one failed document group does not re-upload successful groups.

```python
def test_finalize_is_idempotent(client, ready_project):
    first = client.post(f"/project/setup/finalize/{ready_project}")
    second = client.post(f"/project/setup/finalize/{ready_project}")
    assert first.json()["data"]["source_revision"] == second.json()["data"]["source_revision"]
    assert finalize_write_count() == 1
```

- [x] **Step 2: Implement read-only setup status**

Return project existence, counts for knowledge/requirements/design documents, allowed next actions, source revision when ready, and a sanitized user message. Return paths only as file names, never absolute server paths.

```python
class ProjectSetupStatus(BaseModel):
    pid: str
    stage: Literal[
        "project_created", "knowledge_uploaded", "requirements_uploaded",
        "design_uploaded", "documents_ready", "setup_complete"
    ]
    document_counts: dict[str, int]
    allowed_actions: list[str]
    source_revision: str | None = None
```

- [x] **Step 3: Implement idempotent finalize**

Validate required document groups, compute the source revision, persist the setup artifact, and mark prior workflow artifacts stale by revision. Do not call a chat or embedding model during finalize.

```python
@router.post("/project/setup/finalize/{pid}")
async def finalize_project_setup(pid: str):
    status = await asyncio.to_thread(projectSetupService.finalize, pid)
    return {"status": Status.SUCCESS.value, "reason": "项目资料已确认", "data": status.model_dump()}
```

- [x] **Step 4: Replace CreateView's chained booleans with a stepper state**

Show per-group upload success/failure, retry only failed groups, restore status after refresh, prevent duplicate submission while a request is active, and route to `/plan` only after `setup_complete`.

```typescript
export type SetupStepState = "pending" | "running" | "completed" | "failed";
export interface ProjectSetupState {
  pid: string;
  stage: string;
  groups: Record<"knowledge" | "requirements" | "design", SetupStepState>;
  sourceRevision: string | null;
}
```

- [x] **Step 5: Verify API compatibility and frontend behavior**

Run focused API/source contracts, lint, and build. Existing project creation paths must continue passing their prior envelope tests.

## Task 3: Introduce one derived project lifecycle and navigation guard

**Dependencies:** Task 2.

**Files:**
- Create: `ez_back_dev/service/projectWorkflowStatusService.py`
- Modify: `ez_back_dev/app/routers.py`
- Modify: `ez_front_dev/src/state/projectAnalysis.ts`
- Modify: `ez_front_dev/src/router/index.ts`
- Modify: `ez_front_dev/src/views/MainView.vue`
- Modify: `ez_front_dev/src/components/TestMenu.vue`
- Create: `ez_back_dev/tests/test_project_workflow_status.py`
- Modify: `ez_back_dev/tests/test_frontend_contracts.py`

**Interfaces:**
- Adds `GET /project/workflow/status/{pid}`.
- Produces stages `setup_required`, `analysis_required`, `analysis_ready`, `testing_in_progress`, and `testing_ready`, plus `allowed_routes`, `completed_operations`, and `stale_operations`.

- [x] **Step 1: Add a table-driven lifecycle test**

Cover no documents, finalized documents, partial analysis bundle, complete plan/menu bundle, saved test artifacts, and changed documents. Assert deterministic stage and allowed-route results.

```python
@pytest.mark.parametrize(
    ("setup", "analysis", "artifact_count", "expected"),
    [(False, False, 0, "setup_required"), (True, False, 0, "analysis_required"),
     (True, True, 0, "analysis_ready"), (True, True, 1, "testing_in_progress")],
)
def test_project_stage_is_derived(setup, analysis, artifact_count, expected):
    assert derive_project_stage(setup, analysis, artifact_count).value == expected
```

- [x] **Step 2: Derive lifecycle state from persisted facts**

Do not add a mutable status flag that can drift. Derive state from project setup, current source revision, fresh artifacts, and the legacy plan/menu bundle.

```python
class ProjectStage(str, Enum):
    SETUP_REQUIRED = "setup_required"
    ANALYSIS_REQUIRED = "analysis_required"
    ANALYSIS_READY = "analysis_ready"
    TESTING_IN_PROGRESS = "testing_in_progress"
    TESTING_READY = "testing_ready"
```

- [x] **Step 3: Unify frontend route authorization**

Replace scattered readiness checks with `loadProjectWorkflowStatus(baseUrl, pid)`. Keep `/plan` available after setup, unlock `/menu` and enabled test types only when the analysis bundle is fresh, and redirect stale projects to the first required step with an explanation.

```typescript
export interface ProjectWorkflowStatus {
  stage: "setup_required" | "analysis_required" | "analysis_ready" | "testing_in_progress" | "testing_ready";
  allowed_routes: string[];
  completed_operations: string[];
  stale_operations: string[];
}
```

- [x] **Step 4: Display resumable progress**

Show completed, current, locked, and stale states in the left navigation and test menu. Do not trigger an LLM request merely by loading status.

## Task 4: Reduce the initial analysis/plan/menu call graph

**Dependencies:** Tasks 1 and 3.

**Files:**
- Modify: `ez_back_dev/service/llmTestPlanStreamService.py`
- Modify: `ez_back_dev/prompt/promptStr.py`
- Modify: `ez_back_dev/model/ChainJsonModel.py`
- Modify: `ez_back_dev/dao/testProjectDao.py`
- Modify: `ez_front_dev/src/components/TestPlan.vue`
- Modify: `ez_back_dev/tests/test_test_plan_stream_service.py`
- Modify: `ez_back_dev/tests/test_workflow_cost_baseline.py`

**Interfaces:**
- Produces `ProjectAnalysisDigest(summary: str, menu: TestMenu)` from one structured analysis call.
- Reuses the digest as the only business context for final test-plan generation.
- Keeps existing SSE fields and adds additive `meta.budget_profile`, `meta.source_revision`, and `completed.artifact_key`.

- [x] **Step 1: Lock the target call counts in failing tests**

For a small document, assert at most two chat calls: one digest call and one streamed plan call. For a complete fresh cache, assert zero chat and zero embedding calls. For a large document, assert one map call per selected chunk, one digest reduce call, and one final plan call—never a separate test-menu call.

- [x] **Step 2: Combine summary and menu extraction**

Use one validated Pydantic schema. Keep map summaries compact and require evidence-oriented fields only. If parsing fails, allow one bounded repair call that receives only the invalid structured result and schema, not the source documents again.

```python
class ProjectAnalysisDigest(BaseModel):
    summary: str
    menu: TestMenu

PROJECT_ANALYSIS_PROMPT_VERSION = "project-analysis-v2"
```

- [x] **Step 3: Generate the plan from the canonical digest**

Do not resend raw documents to the plan call. Stream reasoning and plan body as before. Save digest, plan, and menu only after both calls complete and the client remains connected.

```python
plan_prompt = TEST_PLAN_FROM_DIGEST_TEMPLATE.format(
    summary=digest.summary,
    enabled_tests=", ".join(name for name, enabled in digest.menu.model_dump().items() if enabled),
)
```

- [x] **Step 4: Reuse only fresh artifacts**

Key cache lookup by source revision, prompt version, and model. A normal page revisit must return the saved bundle with `from_cache=true`; explicit regeneration must create a new artifact before replacing the active one.

- [x] **Step 5: Verify compatibility and measured reduction**

Run plan stream, API contract, persistence, cancellation, and baseline tests. Record call-count and prompt-token changes in the Iteration 2 log.

## Task 5: Normalize and persist every test-type step

**Dependencies:** Tasks 1, 3, and 4.

**Files:**
- Modify: `ez_back_dev/service/workflowCatalog.py`
- Modify: `ez_back_dev/service/llmWorkflowStreamService.py`
- Modify: `ez_back_dev/service/llmWorkflowAnalysisStreamService.py`
- Modify: `ez_back_dev/service/llmWorkflowCaseStreamService.py`
- Create: `ez_back_dev/service/workflowArtifactService.py`
- Modify: `ez_back_dev/tests/test_llm_workflow_stream_service.py`
- Create: `ez_back_dev/tests/test_workflow_resume.py`

Implementation note: the analysis and case services already emit the complete
`_workflow_result` plus deferred legacy `pending_info` required by this task.
Task 5 therefore keeps those two files unchanged and normalizes/persists their
outputs at the shared dispatcher boundary.

**Interfaces:**
- Produces `WorkflowArtifactKey(operation, input_hash, source_revision, prompt_version, model_label)`.
- Adds additive SSE events `artifact` and `stale`; existing clients may ignore them.
- Persists final analysis, structured choices, user selections, knowledge answers, and final cases; reasoning remains session-only.

- [x] **Step 1: Add parameterized resume tests for all 18 operations**

For each operation, first execution may call mocked models and save once; an identical repeated request must stream the saved result with zero model/embedding calls. Changing a relevant selection, source revision, prompt version, model label, or `regenerate=true` must produce a cache miss.

```python
@pytest.mark.parametrize("operation", sorted(SUPPORTED_WORKFLOW_OPERATIONS))
def test_identical_workflow_request_resumes_without_provider_calls(operation):
    first = run_workflow(operation)
    second = run_workflow(operation)
    assert first.completed and second.from_cache
    assert provider_call_count(second) == 0
    assert embedding_call_count(second) == 0
```

- [x] **Step 2: Route dispatcher metadata through the catalog**

Validate prerequisites, source corpus, artifact name, and regeneration support from one definition. Remove duplicated operation sets after the catalog tests prove parity.

```python
definition = get_workflow_definition(operation)
validate_prerequisites(pid, definition.prerequisites)
```

- [x] **Step 3: Save complete step artifacts atomically**

Case artifacts include the normalized selection payload and final case body. Do not overwrite the previous active artifact until generation and persistence succeed.

```python
@dataclass(frozen=True)
class WorkflowArtifactKey:
    operation: str
    input_hash: str
    source_revision: str
    prompt_version: str
    model_label: str
```

- [x] **Step 4: Preserve legacy cache compatibility**

Read existing `InfoType` 1–23 values as seed artifacts when their source revision is known; keep legacy writes required by old GET/POST endpoints during the compatibility window.

- [x] **Step 5: Verify cancellation and stale-document behavior**

Disconnects, provider errors, parsing errors, and failed commits must leave the previous artifact readable. A changed document must show `stale` and never silently reuse the old answer.

## Task 6: Reuse retrieval indexes and reduce RAG context

**Dependencies:** Tasks 1 and 5.

**Files:**
- Create: `ez_back_dev/vectorstore/indexRegistry.py`
- Modify: `ez_back_dev/vectorstore/retrievers.py`
- Modify: `ez_back_dev/service/llmWorkflowAnalysisStreamService.py`
- Modify: `ez_back_dev/service/llmWorkflowCaseStreamService.py`
- Create: `ez_back_dev/tests/test_index_registry.py`
- Modify: `ez_back_dev/tests/test_retrievers.py`
- Modify: `ez_back_dev/tests/test_workflow_cost_baseline.py`

**Interfaces:**
- Produces `get_project_index(pid, corpus, source_revision, documents, embeddings)`, `invalidate_project_indexes(pid)`, and bounded `RetrievalPolicy(top_k, fetch_k, max_context_tokens, min_score)`.
- Registry keys are `(pid, corpus, source_revision, embedding_model)` and never cross projects.

- [x] **Step 1: Add isolation, concurrency, and reuse tests**

Assert one embedding build for concurrent identical requests, separate indexes for different projects/revisions/corpora, explicit invalidation after document changes, and zero embedding calls when a complete fresh artifact is returned.

```python
async def test_concurrent_requests_build_one_index():
    await asyncio.gather(*(get_index() for _ in range(5)))
    assert fake_embeddings.document_call_count == 1
```

- [x] **Step 2: Implement bounded in-process index reuse**

Use per-key async locks, LRU capacity 16, and a 30-minute idle TTL. Store no API keys or document bodies in logs. Do not persist vectors to Git-tracked paths.

```python
IndexKey = tuple[str, str, str, str]  # pid, corpus, source_revision, embedding_model
INDEX_CAPACITY = 16
INDEX_IDLE_TTL_SECONDS = 1800
```

- [x] **Step 3: Deduplicate retrieved context**

Normalize whitespace, remove chunks with identical content hashes, keep source/page metadata, apply a score threshold, and stop adding chunks when `max_context_tokens` is reached.

```python
@dataclass(frozen=True)
class RetrievalPolicy:
    top_k: int
    fetch_k: int
    max_context_tokens: int
    min_score: float
```

- [x] **Step 4: Reorder cache checks ahead of retrieval**

Every workflow must look up its fresh final/knowledge artifact before loading documents, constructing embeddings, or querying the index.

- [x] **Step 5: Prove embedding and context reductions**

Record embedding-build counts and selected-context tokens for repeated unit, API, functional, and nonfunctional workflows using offline fixtures.

## Task 7: Apply stage-specific reasoning, prompt, and token budgets

**Dependencies:** Tasks 0, 4, and 6.

**Files:**
- Modify: `ez_back_dev/llm/streaming.py`
- Modify: `ez_back_dev/llm/provider.py`
- Create: `ez_back_dev/service/workflowBudget.py`
- Modify: `ez_back_dev/service/llmWorkflowStreamCore.py`
- Modify: `ez_back_dev/service/llmWorkflowStreamService.py`
- Modify: `ez_back_dev/service/llmTestPlanStreamService.py`
- Modify: `ez_back_dev/prompt/promptStr.py`
- Modify: `ez_back_dev/prompt/templates.py`
- Create: `ez_back_dev/tests/test_workflow_budget.py`
- Modify: `ez_back_dev/tests/test_streaming.py`
- Modify: `ez_back_dev/tests/test_llm_workflow_stream_core.py`
- Modify: `ez_back_dev/tests/test_llm_workflow_stream_service.py`
- Modify: `ez_back_dev/tests/test_test_plan_stream_service.py`
- Modify: `ez_back_dev/tests/test_workflow_cost_baseline.py`

**Interfaces:**
- Produces `WorkflowBudgetProfile(map_output_tokens, structured_output_tokens, final_output_tokens, max_context_tokens, reasoning_mode, reasoning_budget)` and stage-specific provider request options.
- Adds token/call counters to `usage` and `completed` without including prompt or reasoning text.

- [x] **Step 1: Add provider-parameter and hard-cap tests**

Assert mechanical map/extraction stages use `reasoning_mode="off"` or the provider's lowest supported effort, final analysis/case stages use the configured balanced mode, Qwen receives a bounded thinking budget, and no stage exceeds its profile's output cap.

```python
def test_structured_stage_never_uses_high_reasoning():
    options = provider_options(profile_for("api_info", "structured"), "通义千问")
    assert options["enable_thinking"] is False
    assert options["max_tokens"] <= 2048
```

- [x] **Step 2: Define explicit default profiles**

Use compact map summaries, small structured extraction caps, and larger final-answer caps. Keep provider quirks in the provider adapter, not in business services. Emit the effective profile in sanitized `meta`.

```python
@dataclass(frozen=True)
class WorkflowBudgetProfile:
    map_output_tokens: int
    structured_output_tokens: int
    final_output_tokens: int
    max_context_tokens: int
    reasoning_mode: Literal["off", "low", "balanced"]
    reasoning_budget: int | None
```

- [x] **Step 3: Compact prompts and eliminate duplicated instructions**

Move common role/output/safety instructions into shared builders. Send artifact summaries instead of raw source documents when a fresh prerequisite exists. Never include the same RAG context in both system and user messages.

- [x] **Step 4: Add preflight context enforcement**

Count selected context before the provider call. If over budget, reduce retrieved chunks or map summaries deterministically; do not rely on provider-side truncation. Emit progress describing reduction without displaying source content.

```python
selected = select_within_token_budget(chunks, profile.max_context_tokens)
assert num_tokens_from_string(join_chunks(selected)) <= profile.max_context_tokens
```

- [x] **Step 5: Verify savings and quality contracts**

Require nonempty outputs and existing structured schemas while asserting lower or equal input tokens and strictly lower calls/embeddings for the optimized repeated flows.

## Task 8: Unify the frontend step workflow and saved-result recovery

**Dependencies:** Tasks 3, 5, and 7.

**Files:**
- Create: `ez_front_dev/src/composables/useTestWorkflow.ts`
- Create: `ez_front_dev/src/components/WorkflowStepper.vue`
- Modify: `ez_front_dev/src/composables/useLlmWorkflow.ts`
- Modify: `ez_front_dev/src/components/UnitTest.vue`
- Modify: `ez_front_dev/src/components/IntegrationTest.vue`
- Modify: `ez_front_dev/src/components/ApiTest.vue`
- Modify: `ez_front_dev/src/components/UITest.vue`
- Modify: `ez_front_dev/src/components/DatabaseTest.vue`
- Modify: `ez_front_dev/src/components/FounctionalTest.vue`
- Modify: `ez_front_dev/src/components/NonfunctionalTest.vue`
- Modify: `ez_front_dev/src/components/AcceptanceTest.vue`
- Modify: `ez_back_dev/tests/test_frontend_contracts.py`

**Interfaces:**
- Produces step states `locked`, `ready`, `running`, `completed`, `stale`, and `failed`.
- Consumes workflow status/artifact SSE metadata and keeps the existing contextual `LlmWorkflowExecution` placement.

- [x] **Step 1: Add failing cross-page flow contracts**

Assert every page loads saved step state, prevents out-of-order case generation, distinguishes “继续” from “重新生成”, displays stale-source warnings, and mounts the active execution panel under its triggering button.

```python
for page in TEST_PAGES:
    source = read(page)
    assert "useTestWorkflow" in source
    assert "WorkflowStepper" in source
    assert "activeOperation" in source
```

- [x] **Step 2: Implement one workflow-state composable**

Hydrate from the status API, normalize selections, expose allowed next actions, and retain results across refresh. The composable must not automatically call an LLM.

```typescript
export type WorkflowStepState = "locked" | "ready" | "running" | "completed" | "stale" | "failed";
export interface TestWorkflowStep<Result = unknown> {
  operation: string;
  state: WorkflowStepState;
  result: Result | null;
  artifactKey: string | null;
}
```

- [x] **Step 3: Add a shared stepper without flattening business-specific choices**

Unit and integration keep three stages; the other six keep analysis and case stages. Preserve API/use-case/method/strategy/output-format controls while moving shared status/retry/reset behavior into the composable.

- [x] **Step 4: Add scoped regeneration**

Regenerating an earlier step must mark only its dependent later steps stale. Ask for confirmation before replacing a saved valid result and keep the old result visible if regeneration fails.

```typescript
async function regenerateStep(operation: string): Promise<boolean> {
  if (!(await confirmReplacement(operation))) return false;
  return runStep(operation, { regenerate: true, keepPreviousOnFailure: true });
}
```

- [x] **Step 5: Run frontend contracts, lint, and build**

Expected: zero ESLint errors/warnings; production build succeeds with only explicitly documented asset-size warnings.

## Task 9: Full compatibility, efficiency, migration, and release audit

**Dependencies:** Tasks 0–8.

**Files:**
- Modify: `ez_back_dev/tests/test_api_contracts.py`
- Modify: `ez_back_dev/tests/test_frontend_contracts.py`
- Modify: `ez_back_dev/tests/test_workflow_cost_baseline.py`
- Modify: `README.md`
- Modify: `docs/iteration-2-development-log.md`
- Create: `docs/iteration-2-closeout.md`

**Interfaces:**
- Produces an offline before/after efficiency report and a user-approved migration/paid-validation checklist.

- [x] **Step 1: Run the full offline suite**

Run: `D:\tool\anaconda3\envs\ezllmtest\python.exe -m pytest .\tests -q`

Expected: all tests pass without socket, provider, embedding, or live database access.

- [x] **Step 2: Enforce measurable efficiency acceptance thresholds**

Require: fresh cached workflows use zero chat and zero embedding calls; identical project/corpus/revision retrieval builds one index; small initial analysis uses at most two chat calls; context passed to a model never exceeds the operation profile; and no intermediate stage uses high reasoning by default.

- [x] **Step 3: Run frontend and Git safety gates**

Run `npm run lint`, `npm run build`, `python scripts/scan_credentials.py`, generated-artifact tracking checks, and `git diff --check`. Do not print raw diffs that could contain historical secrets.

- [x] **Step 4: Gate live migration and optional paid A/B checks**

Provide the exact additive migration command but do not execute it without explicit approval. Run at most one representative old/new request per approved provider, record numeric usage only, and never run all providers automatically.

- [x] **Step 5: Close the iteration**

Document compatibility evidence, before/after call and token counts, migration status, paid checks actually performed, known limits, and rollback instructions. Commit/push only after a separate explicit user instruction.

## Target Outcomes

- Project refresh and navigation resume from persisted state instead of restarting the workflow.
- Changed documents deterministically mark dependent analysis/test artifacts stale.
- A fresh cached result incurs zero chat and zero embedding calls.
- Repeated RAG operations for the same project/corpus/revision reuse one bounded isolated index.
- Small-document project analysis requires no more than two chat calls.
- Mechanical intermediate stages do not consume high-effort reasoning tokens by default.
- All legacy API/database behavior remains available during migration.
