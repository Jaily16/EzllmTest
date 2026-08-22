# EzllmTest Iteration 2 Development Log

## 2026-08-20 — Task 0

### Scope

- Executed only Task 0 from `docs/iteration-2-tasks.md`.
- Added a metadata-only catalog for the separate project-analysis stream and
  all 18 existing generic operations.
- Added a deterministic offline before-optimization cost baseline.
- Did not connect the catalog to dispatch, REST/SSE, persistence, retrieval,
  or frontend code.

### Test-first catalog implementation

- Added the complete-inventory, unique-artifact, dispatcher-parity,
  immutability, and lookup tests first.
- Confirmed the expected red state: collection failed with
  `ModuleNotFoundError` because `service.workflowCatalog` did not exist.
- Added the minimal frozen `WorkflowDefinition`, the 19 immutable definitions,
  `get_workflow_definition()`, and `list_workflow_definitions()`.
- Catalog-focused result after implementation: `4 passed`.

### Offline baseline implementation

- Drove the current plan stream and generic workflow service directly for all
  19 operations.
- Used fixed synthetic small/large document profiles, an in-memory DAO state,
  a deterministic chat stream, and deterministic embeddings.
- Blocked high-level socket connections and made provider-client construction
  an immediate test failure.
- Counted chat calls, document-embedding index builds, input-context tokens
  with the existing tokenizer, and summed configured output caps.
- Measured an identical repeated execution after each first execution and
  stored exact numeric expectations in the test suite.
- Stored only numeric metrics and stage names in
  `docs/iteration-2-token-baseline.md`; no prompt, document, reasoning, model
  output, credential, or raw provider error is present.

### Baseline conclusions

- Small isolated totals change from 40 chat calls / 13 index builds on first
  execution to 19 / 5 on identical repeats.
- Large isolated totals change from 71 chat calls / 13 index builds to 19 / 5.
- Complete project analysis, UI analysis, database analysis, and acceptance
  analysis already have zero-chat repeated paths.
- Unit/integration detail analysis still rebuild indexes and repeat chat work.
- API/functional selected-object cases still rebuild one document index on
  repeat.
- Nonfunctional case generation repeats its full two-call, one-index graph.
- Large functional analysis is the largest map-call multiplier in the fixed
  fixture.

### Safety

- No real `.env` was read or modified; test commands disabled dotenv and used
  empty provider keys plus an invalid placeholder database URL.
- No real chat model, embedding service, MySQL server, application service, or
  external network was accessed.
- No dependency was installed or upgraded.
- No commit or push was performed.

### Validation

- Expected catalog red state: one collection error because
  `service.workflowCatalog` did not yet exist.
- Catalog green state: `4 passed in 2.00s`.
- Baseline-only state after exact metrics were locked: `2 passed` as part of
  the combined gate.
- Final Task 0 focused gate:
  `tests/test_workflow_catalog.py tests/test_workflow_cost_baseline.py` →
  `6 passed in 2.83s`.
- The focused gate used no real provider, embedding API, database, service, or
  network connection.

## 2026-08-20 — Task 1

### Scope

- Executed only Task 1 from `docs/iteration-2-tasks.md` on top of the
  uncommitted Task 0 work.
- Added revision-aware artifact storage as a new seventh table while keeping
  all six legacy table definitions and every existing `testProjectDao` method
  unchanged.
- Did not connect the artifact DAO to a dispatcher, REST/SSE route, legacy
  `InfoType` read/write path, or frontend flow; those remain later-task work.
- Created but did not execute the MySQL migration.

### Test-first implementation

- Added source-revision and artifact DAO tests before implementation.
- Confirmed the expected red state: test collection failed because
  `service.projectRevisionService` and `dao.workflowArtifactDao` did not yet
  exist.
- Added deterministic source revisions over normalized relative path,
  document kind, byte size, and file SHA-256.
- Added canonical input hashes over compact, sorted UTF-8 JSON while excluding
  request IDs, timestamps, and UI-only labels.
- Added one-session artifact upsert, exact fresh-key lookup, rollback on
  failure, and revision markers that make older artifacts stale without
  deleting the historical final content needed by later lifecycle status.
- Supported both the immutable `WorkflowArtifactRecord` interface and the
  positional interface shown in the Task 1 test example.

### Persistence and safety

- Added `tb_project_workflow_artifact` with the required composite primary
  key, project/artifact index, final content, bounded metadata JSON, and
  timestamps.
- The migration contains one idempotent `CREATE TABLE IF NOT EXISTS` statement
  with an inline index and foreign key; it has no mutation of a legacy table.
- Artifact metadata rejects reasoning, prompt/document bodies, raw provider
  exceptions, and credential-shaped fields before opening a session.
- A failed upsert rolls back and leaves the previously committed artifact
  unchanged; DAO failures do not print raw exceptions.
- Updated the ORM compatibility test from an exact six-table set assertion to
  explicit preservation of all six legacy shapes plus validation of the new
  additive table.

### Validation

- Initial Task 1 red state: two collection errors for the missing service and
  DAO modules.
- First implementation gate: `13 passed, 1 failed`; the failure was a static
  test false positive that treated `ON UPDATE CURRENT_TIMESTAMP` as a DML
  statement.
- Corrected that test to reject only standalone ALTER/DROP/DML statements.
- A dependency review added one more red/green check proving invalidation keeps
  old revision rows for future stale-state derivation while excluding them
  from fresh lookup.
- Task 1 focused gate: `14 passed in 0.28s`.
- Offline compatibility gate covering Tasks 0–1, legacy project-info atomic
  writes, ORM/import contracts, and static repository data:
  `29 passed in 5.83s`.
- Test processes disabled dotenv, used an in-memory SQLite URL, cleared all
  provider keys, and did not access a real model, embedding API, MySQL,
  migration target, application service, or external network.
- No dependency was installed or upgraded. No file was staged, committed, or
  pushed.

## 2026-08-20 — Task 2

### Scope

- Executed only Task 2 on top of the uncommitted Task 0/1 work.
- Added recoverable setup status and finalization without changing an LLM
  dispatcher, stream event, workflow prompt, retrieval path, or test page.
- Did not begin the lifecycle/navigation work in Task 3.
- Did not execute the Task 1 MySQL migration or connect to a live database.

### Test-first backend implementation

- Added setup service, API, DAO-idempotency, and frontend source-contract tests
  first.
- Confirmed the initial red state: collection failed because
  `service.projectSetupService` did not exist.
- Added `GET /project/setup/status/{pid}` and
  `POST /project/setup/finalize/{pid}` with legacy-compatible response
  envelopes and sanitized 404/422/500 failures.
- Setup status returns explicit stages, counts, allowed actions, source
  revision when documents are ready, fixed user messages, and file names only.
- Finalize validates all three document groups, performs only local document
  loading/token counting, upserts the legacy project overflow type, marks
  prior revision artifacts stale, and saves one `project_setup` artifact.
- An identical repeated finalize returns the existing artifact and performs no
  second setup-artifact write, invalidation, or project-type analysis.
- Missing documents return HTTP 422 and no project/document delete method is
  called.

### Recovery and legacy compatibility

- Changed the existing `add_project_type()` implementation to an atomic
  upsert, preserving its name and boolean return contract.
- Changed knowledge, requirement, and design path inserts to idempotent saves.
  A retry after an uncertain upload response no longer fails on the existing
  `(project_id, path)` primary key and never deletes the prior row.
- Added a one-session read-only project/document snapshot DAO for setup status.
- Preserved `GET /project/type/{pid}` and its existing `0 -> -1` response
  convention.
- Resolved the plan/code path mismatch by also adding the documented
  `GET /project/type/analyze/{pid}` alias; both paths use the same local-only
  implementation.
- Revision and document-read failures are converted to fixed messages without
  exposing a path, SQL detail, or underlying exception.

### Recoverable Vue setup flow

- Added a typed module-level reactive setup state following the existing
  frontend state pattern; no state-management dependency was added.
- Persisted only project id, stage, group states, source revision, and a fixed
  status message in local storage. File bodies, selected file objects, server
  paths, and credentials are never persisted.
- Replaced chained result booleans with an Element Plus stepper covering
  project registration, all three upload groups, and finalization.
- Successful groups are skipped on retry, failed groups remain retryable, and
  backend status is reloaded after refresh.
- A request-active guard disables duplicate submission, and navigation to
  `/plan` is exposed only after `setup_complete`.
- A user may clear only the browser recovery state to start another project;
  this action explicitly does not delete the prior server project or files.

### Validation

- Initial Task 2 red state: one collection error for the missing setup service.
- Backend service/API green checkpoint: `13 passed in 2.22s`.
- Frontend setup source contracts: `2 passed in 1.22s`.
- Additional red/green checks covered duplicate document-path retry and
  sanitized revision failures.
- Final Tasks 0–2 compatibility gate covering setup, all API/frontend
  contracts, revision/artifact persistence, legacy project-info writes, ORM
  import safety, and static repository data: `89 passed in 7.37s`.
- Frontend lint: no errors.
- Frontend production build: successful; only the pre-existing asset and
  entrypoint size warnings were reported.
- Test processes disabled dotenv, used an in-memory SQLite URL, and cleared all
  provider keys. No real model, embedding API, MySQL, migration target,
  application service, or external network was accessed.
- No dependency was installed or upgraded. No file was staged, committed, or
  pushed.

## 2026-08-20 — Task 3

### Scope

- Executed only Task 3 on top of the uncommitted Task 0–2 work.
- Added one read-only project workflow status and navigation policy without
  changing a dispatcher, model prompt, REST/SSE streaming contract, database
  schema, legacy `InfoType` writer, or test-page model action.
- Did not begin Task 4 call-graph optimization or any Task 5–9 work.

### Test-first lifecycle derivation

- Added the table-driven lifecycle test before the service existed and
  confirmed the expected collection failure for the missing
  `projectWorkflowStatusService` module.
- Added deterministic stages `setup_required`, `analysis_required`,
  `analysis_ready`, `testing_in_progress`, and `testing_ready`.
- The service derives state on every read from Task 2 setup status/current
  source revision, the complete legacy summary/plan/menu bundle, and Task 1
  artifact rows. It does not persist a mutable lifecycle flag.
- Current-revision artifacts populate `completed_operations`; mismatched or
  explicitly invalidated revisions populate `stale_operations`. Duplicate
  rows for one operation are collapsed in catalog order, and a fresh result
  wins over an older stale copy.
- `testing_ready` requires every test-case operation enabled by the persisted
  test menu. A partial set of fresh test artifacts remains
  `testing_in_progress`.
- Changed or unfinalized documents lock the project to `/create` and mark an
  existing legacy analysis bundle stale. A finalized project without a full,
  valid analysis bundle is restricted to `/plan`.

### API and frontend navigation

- Added `GET /project/workflow/status/{pid}` with the existing
  `{status, reason, data}` response envelope and sanitized setup/persistence
  errors.
- Preserved `GET /project/analysis/status/{pid}` for external compatibility;
  the frontend compatibility loader now delegates to the single workflow
  status request.
- Added a typed Vue `ProjectWorkflowStatus` state with one in-flight request
  per project, preventing MainView and a child page from issuing duplicate
  status reads during concurrent mounting.
- All ten project child routes now use the same `allowed_routes` guard. `/plan`
  is available only after setup; `/menu` and only the test types enabled by
  the current menu unlock after analysis is ready. A stale project is sent to
  `/create` or `/plan` with the backend's fixed explanation.
- MainView and TestMenu show completed, current/available, locked, and stale
  states from persisted status. Loading either view performs only the status
  GET and never starts an LLM or embedding workflow.

### Compatibility note for Task 4

- Legacy `InfoType` 1/22/23 rows have no source-revision column. Task 3 keeps
  them as the compatibility fallback while Task 2 reports the matching setup
  revision complete, and immediately treats them as stale when documents are
  changed/unfinalized.
- Task 4 must make `project_analysis_bundle` the authoritative revision-keyed
  analysis result. That closes the remaining ambiguity if changed documents
  are finalized again before a new revision-aware analysis artifact exists.

### Validation

- Initial lifecycle red state: one collection error for the missing workflow
  status service.
- Initial API red state: two failures for the absent workflow status path and
  its 404 response.
- Initial frontend red state: four failures for the old `analysisReady` route
  guard and legacy status loader.
- Task 3 focused dependency/API/frontend gate:
  `tests/test_project_workflow_status.py tests/test_project_setup_service.py
  tests/test_workflow_artifact_dao.py tests/test_api_contracts.py
  tests/test_frontend_contracts.py` → `85 passed in 2.33s`.
- Complete offline backend test gate: `183 passed in 7.13s`.
- Frontend lint: no errors.
- Frontend production build: successful; only the pre-existing asset and
  entrypoint size warnings were reported.
- Test processes disabled dotenv, used an in-memory SQLite URL, and cleared
  all provider keys. No real model, embedding API, MySQL, migration target,
  application service, or external network was accessed.
- No dependency was installed or upgraded. No file was staged, committed, or
  pushed.

## 2026-08-20 — Task 4

### Scope

- Executed only Task 4 on top of the uncommitted Task 0–3 work.
- Reduced only the initial project analysis/test-plan/test-menu call graph.
  No generic workflow dispatcher, retriever, embedding path, test-type
  artifact behavior, database schema, or Task 5–9 feature was changed.
- Preserved the selected frontend model as the provider for every map,
  digest/repair, and final-plan call.

### Test-first call graph

- Replaced the prior three-call small graph (summary, plan, menu) with one
  validated `ProjectAnalysisDigest(summary, menu)` call and one streamed plan
  call.
- Replaced the prior large summary map/reduce plus plan map/reduce plus menu
  graph with one compact evidence map per selected chunk, one structured
  digest reduce, and one final plan call from the digest only.
- The final plan prompt receives only the canonical summary and enabled test
  names. It does not receive raw uploaded documents, map chunks, or the model's
  invalid structured output.
- Invalid digest JSON receives at most one repair call. The repair receives
  only the schema and at most 12,000 characters of invalid output; a second
  invalid result fails without saving.
- Existing progress, reasoning, summary, answer, menu, usage, cancellation,
  and completion SSE events remain. `meta` now adds `operation`,
  `budget_profile`, and `source_revision`; `completed` adds `artifact_key`.

### Revision cache and atomic compatibility writes

- Normal execution first checks `project_analysis_bundle` by project, current
  source revision, canonical input hash, `project-analysis-v2` prompt version,
  and selected model label. A valid hit streams the saved bundle with zero
  model and zero embedding calls.
- A legacy-only summary/plan/menu bundle is intentionally regenerated once so
  it obtains a revision/model-keyed artifact. The three legacy `InfoType` rows
  remain readable and are updated for compatibility after successful output.
- Once any revision-aware analysis artifact exists, lifecycle derivation uses
  its freshness as authoritative and no longer lets revisionless legacy rows
  mask a stale document revision. Projects with no artifact retain the legacy
  compatibility fallback.
- Added one transaction that upserts the artifact and all three legacy rows
  together. Cancellation, invalid structured output, or commit failure leaves
  the previous artifact and legacy bundle unchanged.
- Explicit regeneration bypasses cache lookup, builds the complete replacement
  in memory, then performs the same atomic upsert; it never deletes the active
  result first.
- Artifact content stores only final summary, menu, and plan. Metadata stores
  only operation, budget profile, and call count; prompt text, source document
  content, reasoning, credentials, and raw exceptions are excluded.

### Frontend recovery

- TestPlan preserves its existing stream panel and regeneration controls.
- After a successful saved or cached bundle, it immediately reloads the Task 3
  derived workflow status so navigation completion/staleness reflects the
  persisted artifact. The existing local ready-state update remains as a
  compatibility fallback if that read-only refresh fails.

### Measured reduction

- Small fixed document: `3/0/2560/73728 → 2/0/1486/40960`; chat calls -33.3%,
  input-context tokens -42.0%, summed output cap -44.4%.
- Large fixed document with four selected chunks:
  `9/0/60399/122880 → 6/0/38929/73728`; chat calls -33.3%, input-context
  tokens -35.5%, summed output cap -40.0%.
- Identical repeat for both profiles remains `0/0/0/0`, now through the exact
  revision/prompt/model artifact key rather than revisionless legacy rows.

### Validation

- Initial stream red state: collection failed because
  `ProjectAnalysisDigest` did not exist.
- Initial updated-baseline red state: the harness reached the unmocked source
  revision path, proving the new revision dependency was not yet represented.
- Initial frontend red state: TestPlan did not reload derived workflow status.
- Bounded-repair red state: the repair prompt accepted a 20,000-character
  invalid output before the 12,000-character cap was added.
- Task 4 stream tests: `11 passed in 2.03s` before the additional bounded-input
  assertion.
- Offline cost baseline: `2 passed in 2.88s`.
- Task 4 dependency/API/frontend compatibility gate: `92 passed in 3.26s`.
- Final Task 4/API/frontend/credential/repository gate:
  `107 passed in 3.46s`.
- Complete offline test gate after the revision-authority regression:
  `189 passed in 6.86s`.
- Frontend lint: no errors.
- Frontend production build: successful; only the pre-existing asset and
  entrypoint size warnings were reported.
- Test processes disabled dotenv, used an in-memory SQLite URL, cleared all
  provider keys, and blocked provider/network creation in the cost harness.
  No real model, embedding API, MySQL, migration target, application service,
  or external network was accessed.
- No dependency was installed or upgraded. No file was staged, committed, or
  pushed.

## 2026-08-20 — Task 5

### Scope

- Executed only Task 5 on top of the uncommitted Task 0–4 work. Task 6–9
  retriever reuse, token budgets, concurrency, and end-to-end features were
  not started.
- Normalized persistence at the shared generic dispatcher boundary. The
  analysis and case services already returned final analysis text, structured
  choices, knowledge answers, final cases, and deferred legacy values, so
  their behavior and files did not require changes.
- Existing REST/SSE paths and public `meta`, progress, reasoning, answer,
  usage, result, cancellation, error, and completed behavior remain valid.
  The new `artifact` and `stale` events and completed artifact fields are
  additive.

### Catalog and artifact identity

- The workflow catalog now supplies the generic dispatcher operation phase,
  prerequisites, source corpus, result artifact, regeneration support, prompt
  version, legacy `InfoType` mapping, normalized selection fields, and legacy
  prerequisite payload fields. The dispatcher no longer owns duplicated
  hand-written analysis/case inventories.
- Every generic request uses
  `WorkflowArtifactKey(operation, input_hash, source_revision, prompt_version,
  model_label)`. The input hash still includes every business-relevant payload
  value; the persisted selection contains only catalog-declared user choices.
- The catalog records `project-analysis-v2` for Task 4 and explicit `v1`
  versions for the 18 existing generic prompt families.

### Complete-step persistence and resume

- Added one strict JSON artifact envelope containing format version,
  operation, normalized selection, and final result. Analysis results retain
  structured choices; case results retain reusable knowledge answers and the
  final case body.
- Prompt text, source document bodies, reasoning, credentials, raw provider
  exceptions, and transport metadata are rejected or omitted. Metadata is
  limited to operation and model-call count.
- Artifact upsert and all deferred legacy `InfoType` writes now share one
  SQLAlchemy transaction. A failed commit rolls back both and preserves the
  previously readable artifact and legacy seed.
- A fresh exact artifact is checked before any operation service, document
  loader, retriever, embedding constructor, or model call. A hit streams the
  saved public result and completes with `from_cache=true`, zero usage, and no
  provider or embedding activity.

### Legacy and stale behavior

- Existing legacy analysis and knowledge values remain readable on the first
  Task 5 execution and are atomically carried forward with the completed
  revision-aware artifact.
- Legacy values are a one-time seed only while that operation has no
  revision-aware history. Once history exists, a non-exact input, revision,
  prompt, or model match forces regeneration rather than relabeling a legacy
  value as fresh.
- A revision-aware prerequisite is authoritative over revisionless legacy
  rows. A stale project-analysis artifact cannot be masked by legacy summary,
  plan, and menu values.
- A changed document revision emits `stale` and never resumes the old result.
  Disconnects, provider/parsing failures, and failed commits do not delete or
  replace the prior artifact.

### Test-first evidence and measured result

- Initial catalog red state failed because `WorkflowDefinition` lacked Task 5
  persistence metadata.
- Initial resume red state failed collection because
  `workflowArtifactService` did not exist. After the service was added, all 18
  parameterized operations failed against the legacy dispatcher until cache
  lookup and atomic persistence moved to the shared boundary.
- The same-revision stale-marker test and revision-authority prerequisite test
  both failed before their explicit protections were added.
- All 18 operations now prove one first save and an identical repeat with zero
  mock chat calls and zero mock embedding builds. Selection, source revision,
  prompt version, model label, and explicit regeneration each prove a miss.
- First-execution small/large metrics are unchanged. Repeated metrics for all
  18 generic operations are now `0/0/0/0`; combined with Task 4, all 19
  workflows have zero chat, embedding, input-context, and output-cap cost on
  an identical repeat.

### Validation and offline safety

- Task 5 catalog/resume/dispatcher/analysis/case/baseline/API/status gate:
  `106 passed in 3.21s` before the final revision-authority regression was
  added.
- Final complete offline backend gate: `215 passed in 7.17s`.
- Focused offline cost baseline: `2 passed in 2.70s`.
- Python syntax compilation for all Task 5 production/test files: successful.
- `git diff --check`: no whitespace errors; only the existing LF-to-CRLF
  worktree warnings were reported.
- The environment does not contain `ruff`; it was not installed because this
  iteration forbids dependency changes.
- One early combined red run imported the prior placeholder MySQL URL before
  the old dispatcher path was replaced. Its localhost authentication was
  rejected before any SQL succeeded. The offline catalog/baseline tests were
  immediately changed to in-memory SQLite; every subsequent focused and full
  gate used SQLite with provider keys cleared.
- No real model or embedding provider, successful MySQL session, migration
  target, application service, or external network was used. No dependency
  was installed/upgraded, and no file was staged, committed, or pushed.

## 2026-08-20 — Task 6

### Scope

- Executed only Task 6 on top of the uncommitted Task 0–5 work. Task 7–9
  reasoning budgets, prompt changes, frontend workflow unification, and
  release work were not started.
- Existing dispatcher ordering, REST/SSE paths and event payloads, normalized
  workflow artifacts, legacy `InfoType` compatibility writes, and database
  transaction behavior remain unchanged.
- Added the source revision to the internal workflow context only after the
  final-artifact lookup. A complete fresh artifact still returns before any
  document load, embedding construction, index query, or model call.

### Revision-scoped index reuse

- Added an in-process registry keyed by project, corpus, source revision, and
  configured embedding model. Per-key async locks collapse concurrent builds;
  the registry has capacity 16, a 30-minute idle TTL, LRU eviction, and
  project-scoped invalidation.
- An invalidation generation prevents an index that finishes building during
  invalidation from being reinserted. Finalizing a changed project setup clears
  only that project's indexes after artifact invalidation succeeds.
- The registry stores vectors only in memory. It does not log or persist API
  keys, source bodies, chunk bodies, or vectors. The lazy embedding adapter now
  exposes the configured model name without constructing a provider client, so
  the real registry key is model-specific.

### Bounded retrieval and service integration

- Added explicit design, requirements, and knowledge policies with `top_k=4`,
  `fetch_k=8`, a 6,000-token per-retrieval context cap, and minimum similarity
  score 0.20.
- Selected chunks normalize whitespace, de-duplicate by SHA-256 content hash,
  retain source/page metadata, reject low-score results, and stop before the
  token cap would be exceeded.
- Unit detail, named integration detail, named API detail, named functional
  detail, nonfunctional analysis, and all test-knowledge lookups now share the
  project/revision index. Legacy synchronous retriever functions remain for
  compatibility callers outside the streamed Task 6 paths.

### Test-first evidence

- Registry tests first failed collection because `vectorstore.indexRegistry`
  did not exist. Retriever tests then failed because `BoundedRetriever` did
  not exist.
- Four service integration tests failed before implementation: analysis and
  case paths still invoked legacy per-request retrievers, the dispatcher did
  not pass a source revision, and project setup did not invalidate indexes.
- The lazy embedding identity test failed before `model_name` was exposed.
  The first attempt to run the four service red tests used the system Python
  and stopped at dependency collection; rerunning with the existing
  `ezllmtest` environment produced the intended four failures. No application
  or external service was started by either run.

### Offline measured result

- Exact artifact repeats for all 19 workflows remain `0/0/0/0` for chat
  calls, embedding builds, input-context tokens, and summed output cap.
- Same-revision forced regeneration proves index reuse independently from the
  final artifact: unit/API/functional/nonfunctional embedding builds change
  from `1/2/2/1` to `0/0/0/0`, with identical selected-context token counts.
- On the fixed large fixture, input-context tokens change from Task 5 values
  `8837 → 1929` (unit), `22243 → 7197` (named API), `19356 → 6844` (named
  functional), and `3490 → 1696` (nonfunctional).
- Across all isolated first executions, summed input context changes from
  `20730 → 20106` for the small fixture and `365709 → 260009` for the large
  fixture. Chat calls, first-build counts, and output caps are unchanged.
- The baseline report stores only operation/profile labels and numeric
  counters; it stores no prompts, source documents, model output, reasoning,
  credentials, exceptions, vectors, or embedding values.

### Validation and offline safety

- Registry/retriever/provider/baseline gate: `20 passed in 3.49s`.
- Analysis/case stream integration gate: `21 passed in 1.99s`.
- Focused Task 6 integration and setup gate: `45 passed in 2.22s` before the
  additional API/functional/integration coverage was added.
- Offline cost baseline: `3 passed in 2.78s`.
- Complete offline backend gate: `232 passed in 7.28s`.
- Python syntax compilation for all Task 6 production and test files:
  successful.
- Credential scan: clean across 129 tracked, zero staged, and 19 untracked
  Git-visible files; the scanner emitted no credential values.
- `git diff --check`: no whitespace errors; only existing LF-to-CRLF worktree
  warnings were reported.
- Test processes disabled dotenv, used an in-memory SQLite URL, cleared all
  provider keys, and blocked provider/network creation in the cost harness.
  No real model, embedding API, MySQL, migration, application service, or
  external network was accessed. No dependency was installed or upgraded, and
  no file was staged, committed, or pushed.

## 2026-08-20 — Task 7

### Scope

- Executed only Task 7 on top of the uncommitted Task 0–6 work. Task 8–9
  frontend step unification and release audit were not started.
- Preserved dispatcher ordering, revision-aware final artifacts, Task 6 index
  reuse, REST/SSE routes, legacy event names, database/`InfoType` behavior,
  atomic persistence, cancellation, and frontend rendering contracts.
- The planned `tests/test_streaming_adapter.py` did not exist; the repository's
  active adapter coverage is `tests/test_streaming.py`, so the Task 7 file list
  was corrected instead of creating a duplicate test module.

### Stage budgets and provider options

- Added `WorkflowBudgetProfile` and deterministic resolution for every catalog
  operation and `map`, `structured`, or `final` stage.
- Project analysis uses output caps `1024/2048/8192`; generic analysis uses
  `1024/1536/8192`; cases use `1024/1536/12288`. Project analysis context is
  capped at 12,000 tokens and generic workflows at 6,000 tokens.
- Map and structured/extraction/repair/knowledge/detail stages use reasoning
  mode `off`. DeepSeek receives its lowest request effort for these stages;
  GLM, Qwen, and Kimi receive disabled-thinking request fields. Final stages
  use balanced reasoning.
- Qwen final-stage thinking is capped at 4,096 tokens and also bounded by the
  call output limit. Provider-specific fields stay in the provider adapter;
  streaming accepts only the resolved request options and enforces the smaller
  of the caller and profile output caps.

### Context and prompt enforcement

- Every provider call counts its prompt before dispatch. Oversized input is
  reduced deterministically to the profile cap while retaining the instruction
  head and business-context tail. The emitted progress event exposes only
  before/after token counts and no source content.
- Added shared grounded and structured-output prompt builders. Structured
  schemas are placed ahead of variable input so they survive preflight
  reduction; RAG context is rendered exactly once in the single provider user
  message.
- Compacted the project digest grounding/JSON rules without changing its
  structured schema. Final project plans continue to receive only the
  canonical digest, and case workflows continue to receive saved/generated
  analysis and knowledge summaries rather than reattaching raw project source.

### Sanitized SSE counters

- Generic and project-analysis `meta` events now add the effective public
  budget fields. Existing project `budget_profile` and all prior metadata are
  retained.
- `usage` and `completed` now add `model_call_count`; `completed` also repeats
  the aggregate input, reasoning, output, and total Token counters. Cached
  artifacts report zero calls and unknown Token values.
- Budget metadata, request options, usage events, completion events, and
  artifact metadata contain no prompt, document, reasoning text, credential,
  provider exception, vector, or embedding value.

### Test-first evidence

- The first budget test failed collection because `provider_options` and
  `workflowBudget` did not exist. The minimal profile/provider implementation
  then passed six tests.
- The stream/core/event red gate produced six intended failures: no request
  options parameter, 32,768-token legacy caps, no preflight progress, no budget
  metadata, and no usage/completed call counters.
- Shared prompt tests failed before the builders existed. The edge-preserving
  preflight test then failed because the first implementation retained only
  the prompt prefix; the corrected implementation retains both instruction
  head and business tail.
- The offline baseline initially failed because its mock adapter did not accept
  stage request options, proving the new adapter boundary was exercised.

### Offline measured result

- Calls and first embedding builds do not increase. Exact repeats for all 19
  artifacts remain `0/0/0/0`; compared with the Task 0 generic repeated total,
  aggregate repeat calls/builds remain strictly lower (`19/5 → 0/0`).
- Versus Task 6, isolated first-execution input context changes from
  `20106 → 19911` for the small fixture and `260009 → 210836` for the large
  fixture.
- Summed output caps change from `1105920 → 219648` for the small fixture and
  `1343488 → 249344` for the large fixture. Every per-operation input total is
  lower or equal, all structured schemas still validate, and nonempty response
  enforcement remains active.

### Validation and offline safety

- Focused budget/stream/provider/project-plan/baseline gate:
  `23 passed in 3.32s`.
- Offline cost baseline: `3 passed in 3.18s`.
- Complete offline backend gate before documentation-only closeout:
  `242 passed in 7.81s`.
- Final complete offline backend gate: `242 passed in 7.88s`.
- Python syntax compilation for all Task 7 production and test files:
  successful.
- Credential scan: clean across 129 tracked, zero staged, and 21 untracked
  Git-visible files; the scanner emitted no credential values.
- Test processes disabled dotenv, used an in-memory SQLite URL, cleared every
  provider key, and blocked provider/network creation in the cost harness.
  No real model, embedding API, MySQL, migration, application service, or
  external network was accessed. No dependency was installed or upgraded, and
  no file was staged, committed, or pushed.

## 2026-08-20 — Task 8

### Scope

- Executed only Task 8 on top of the uncommitted Task 0–7 work. Task 9 release
  audit and closeout were not started.
- Preserved the generic workflow POST SSE endpoint, dispatcher operation names,
  REST/status contracts, artifact and legacy database behavior, model labels,
  cancellation, and contextual `LlmWorkflowExecution` placement.
- Used the repository's existing frontend and Python environments. No dependency
  was installed or upgraded, and no application or database service was started.

### Shared workflow state and recovery

- Added one typed `useTestWorkflow` controller with `locked`, `ready`, `running`,
  `completed`, `stale`, and `failed` states, normalized selections, allowed-next
  actions, prerequisite locking, and shared retry/reset helpers.
- Selection persistence is allow-listed from the workflow catalog semantics;
  upstream `info`, `unit_info`, and `integration_object_info` payload bodies are
  not duplicated into the saved selection map.
- Page mount performs only the existing project workflow-status GET. It never
  starts an LLM workflow. Completed/stale operation facts come from that status;
  results and normalized selections already displayed in the current browser
  session are restored from project/page-scoped `sessionStorage`. Persisted
  server artifacts remain authoritative and can still be explicitly recovered
  through the existing cached SSE path by pressing “继续”.
- Extended the generic stream consumer to retain sanitized artifact key, source
  revision, prompt version, model label, saved/resumed status, and stale flag.
  Prompt text, source documents, reasoning content, credentials, vectors, and
  provider exceptions are not stored in workflow state metadata.

### Shared stepper and page-specific flows

- Added `WorkflowStepper` and mounted it on all eight test pages. Unit and
  integration retain three stages; API, UI, database, functional,
  nonfunctional, and acceptance retain two stages.
- Preserved all business controls: unit type/object/method/output format,
  integration type/object/strategy/output format, API scope/name/output format,
  functional use case/output format, and nonfunctional method selection.
- Every case action is locked until its analysis prerequisite is usable. Each
  page distinguishes cached “继续” from explicit “重新生成”, renders stale-source
  warnings, and keeps the active execution panel directly under the action that
  started the operation.

### Scoped regeneration

- Replacing a completed or stale saved step requires explicit confirmation.
  Successful earlier-step regeneration marks only transitive later steps stale
  and leaves their old results visible for reference.
- A failed regeneration restores the prior step state, result, and artifact key;
  it does not erase the saved valid result. Changed unit/integration selections
  similarly mark only their dependent results stale.
- The frontend passes the existing `regenerate` flag and does not change backend
  artifact replacement, atomic database persistence, or cache lookup behavior.

### Test-first evidence

- The new cross-page contract gate first produced four intended failures: all
  pages lacked `useTestWorkflow`/`WorkflowStepper`, the two shared files did not
  exist, and the stream consumer did not expose artifact metadata.
- After the minimal implementation, the focused frontend contract gate passed
  `20 passed in 1.07s`. The strengthened contracts also require visible “继续”
  and “重新生成” actions on every test page.
- The first production build found a strict-TypeScript guard error in failed-run
  restoration. Tightening the previous-step existence check resolved it before
  the successful build.

### Validation and offline safety

- Final complete offline backend gate: `246 passed in 8.50s`.
- Frontend lint: zero errors and zero warnings.
- Frontend production build: successful. Webpack reported only the two existing
  asset/entrypoint size classes for the bundled font, logo, vendor CSS, and
  vendor JavaScript. Node 24 additionally emitted its dependency-level
  `DEP0180` deprecation notice before compilation; it did not affect the build.
- Test processes disabled dotenv, used an in-memory SQLite URL, and cleared all
  provider keys. No real model, embedding API, MySQL, migration, application
  service, or external network was accessed. No file was staged, committed, or
  pushed.
- Credential scan: clean across 129 tracked, zero staged, and 23 untracked
  Git-visible files; the scanner emitted no credential values.
- `git diff --check`: no whitespace errors; only existing LF-to-CRLF worktree
  warnings were reported.

## 2026-08-20 — Task 9

### Scope and release decision

- Executed only Task 9 on top of the uncommitted Task 0–8 work. No migration,
  paid provider request, MySQL connection, application service, commit, or push
  was performed.
- Closed the offline implementation/audit portion of Iteration 2. Production
  database enablement remains gated on a separate user-approved backup and the
  additive migration; paid A/B checks remain optional and separately gated.
- Updated README runtime behavior, budgets, migration instructions, document
  links, and known limits. Added `docs/iteration-2-closeout.md` with
  compatibility evidence, numeric before/after measurements, migration and
  paid-validation status, known limits, and rollback instructions.

### Test-first release contracts

- Added API/migration and frontend/closeout publication contracts plus a
  consolidated efficiency threshold test.
- The first focused run produced the intended two documentation failures
  because `docs/iteration-2-closeout.md` did not yet exist. The efficiency
  contract passed immediately, proving the optimized code already met the
  Task 9 thresholds.
- After the minimal README/closeout implementation, the three focused release
  contracts passed in `3.26s`.

### Quantitative acceptance

- Current isolated first-execution totals are
  `39/13/19911/219648` (small) and `68/13/210836/249344` (large), compared with
  Task 0 values `40/13/21804/1138688` and `71/13/387179/1392640`.
- Identical-repeat totals change from Task 0
  `19/5/9319/475136` (small) and `19/5/51965/475136` (large) to `0/0/0/0` for
  both profiles.
- Small `project_analysis` is two chat calls. Every per-call input measurement
  is within its operation context profile, and the mock request recorder finds
  zero mechanical calls with high/medium reasoning or enabled thinking.
- Existing concurrent registry coverage proves identical
  project/corpus/revision/embedding-model requests build one index. Forced
  same-revision representative RAG regeneration adds zero embedding builds.
- The test/report path stores only operation/profile labels and numeric
  counters; it stores no prompt, document, output, reasoning, credential,
  provider exception, vector, or embedding value.

### Migration and paid-validation gate

- The additive migration remains **not executed**. README and closeout provide
  the exact `mysql.exe ... --execute="SOURCE ..."` command, but require a
  separate user approval, backup, target verification, and write window.
- Static release contracts reject destructive statements in the migration and
  confirm the six legacy table names remain documented. The optional rollback
  `DROP TABLE` is documented only and was not executed.
- No paid A/B request was run. The closeout requires one explicitly selected
  provider and at most one old/new representative request, with numeric usage
  only; prior Iteration 1 authorization is not treated as current approval.

### Validation and safety

- Complete offline backend gate: `249 passed in 9.46s`.
- Frontend lint: zero errors and zero warnings.
- Frontend production build: successful with only the existing `asset size
  limit` and `entrypoint size limit` warnings. The build used the existing Vue
  CLI because replacing the repository toolchain or adding Vitest/Vite would
  exceed Task 9 and require dependency changes.
- Credential scan: clean across 129 tracked, zero staged, and 24 untracked
  Git-visible files; no credential value was printed.
- Generated-artifact tracking gate: clean; two sanitized `.env.example` files
  are tracked, while real env files, Python caches, `node_modules`, and `dist`
  are not tracked.
- `git diff --check`: no whitespace errors; only existing LF-to-CRLF worktree
  warnings were reported.
- Tests disabled dotenv, used in-memory SQLite, cleared all provider keys, and
  blocked provider/network creation in the cost harness. No dependency was
  installed or upgraded and no file was staged, committed, or pushed.

## 2026-08-21 — Post-Iteration-2 test-menu and long-text correction

### Reported defect and root cause

- The CC4C project contained abundant subsystem, module, service, layered
  architecture, API, and call/dependency evidence, but the persisted project
  menu marked unit and integration testing unavailable.
- The old coarse project `overflow` value and 14,500-token threshold routed the
  roughly 42K-token corpus through several very short map summaries. Structural
  evidence could be lost before the model made the final menu decision, and the
  frontend correctly enforced that false persisted menu.

### Test-menu correction

- Added deterministic document-structure evidence for unit and integration
  eligibility. The guard requires multiple independent categories and an
  explicit relationship signal for integration; it only repairs supported
  false negatives and never disables a model-enabled test type.
- Reconciled the menu before plan generation, SSE publication, artifact/legacy
  persistence, and allowed-route calculation. Existing cached artifact JSON,
  REST/SSE event shapes, `InfoType` rows, and frontend route contracts remain
  unchanged.
- Strengthened the project-analysis prompt definitions so module/component/class
  evidence supports unit testing and cross-unit architecture/interface/call
  evidence supports integration testing even when a document does not contain
  the literal test-type name.

### Long-text strategy correction

- Added a complete policy catalog for all 19 operations. Exhaustive project
  analysis uses `stuff` through 64K source tokens; other exhaustive analyses use
  `stuff` through 32K; focused entity/question flows use bounded
  retrieval-plus-stuff; final case generation uses compact artifact stuffing
  through the 16K case budget.
- Added conservative context and output capabilities for GLM-4.7,
  qwen3.5-plus, deepseek-v4-flash, and kimi-k2.5. Effective input budgets reserve
  output, reasoning, and a provider-window safety margin. DeepSeek mechanical
  stages now explicitly disable thinking instead of sending an unsupported low
  reasoning mode.
- Separated instruction text from document context so bounding cannot remove
  schema or output requirements. Oversized exhaustive corpora now split within
  the actual stage budget and use hierarchical map-reduce without dropping
  middle evidence; focused retrieval results are not redundantly map-reduced.
- Routed synchronous legacy whole-corpus services through the same actual-token
  policy adapter and upgraded the public synchronous map-reduce helper to
  bounded hierarchical reduction without changing its signature.
- No current workflow uses refine because the tasks merge independent evidence
  rather than revise one order-dependent narrative. The complete per-operation
  rationale is recorded in `docs/long-text-strategy-audit.md`.

### Offline measurement and validation

- Updated the safe numeric baseline after the intentional routing change.
  First-run totals are `39/13/20063/219648` for the small fixture and
  `39/13/227243/219648` for the large fixture
  (`chat/embedding/input/output-cap`). Identical artifact repeats remain
  `0/0/0/0` for all 19 operations.
- Regression coverage includes CC4C-like positive structural evidence,
  business-only negative evidence, old-cache reconciliation, actual-token
  routing, focused-retrieval routing, instruction preservation, hierarchical
  partitioning, provider capability compatibility, and legacy-route scanning.
- Verification used mock chat, mock embedding, fixed synthetic documents,
  in-memory SQLite, cleared provider keys, and external-socket guards. No real
  model, embedding, MySQL, migration, external network, dependency install,
  staging, commit, or push was performed.
- Final complete backend gate: `268 passed in 8.54s`. Credential scan was clean
  across 129 tracked, zero staged, and 33 untracked Git-visible files.
  `git diff --check` reported no whitespace errors; only the existing Windows
  LF-to-CRLF notices were emitted.

## 2026-08-21 — Test-plan regeneration navigation lock

- Fixed a frontend state-consistency defect where starting an explicit project
  reanalysis left the previous saved `allowed_routes` active until the new plan
  completed. Users could therefore enter the test menu or individual test pages
  while their prerequisites were being replaced.
- Added one shared reactive regeneration flag. Explicit regeneration sets it
  synchronously before the SSE request; while set, `/plan` remains available for
  progress and cancellation, while `/menu` and all eight test-type routes are
  denied by the existing route guard and disabled in the left navigation.
- Successful completion applies the newly returned menu and refreshed workflow
  status before releasing the lock. Failure or cancellation releases only the
  transient flag, revealing the previous valid persisted status without deleting
  or rewriting it.
- Added a test-first frontend contract for the begin/finally lifecycle and shared
  route gate. Focused contracts passed `22 passed in 1.14s`; frontend lint passed
  with zero errors; the production build completed with only the existing asset
  and entrypoint size warnings plus Node's dependency-level `DEP0180` notice.
- The complete offline backend/contract gate passed `269 passed in 9.40s`, and
  `git diff --check` reported no whitespace errors beyond existing line-ending
  notices.
- No backend API, SSE payload, database behavior, model/embedding call, migration,
  dependency, commit, or push was involved in this correction.

## 2026-08-21 — Qualified unit references

### Same-name collision

- Confirmed that the previous unit workflow used a bare string as display text,
  retrieval query, saved selection, and cache identity. Classes in different
  packages and same-named methods in different classes—or overloads in one
  class—could therefore be indistinguishable.
- Added a model-facing qualified reference with `display_name`,
  `qualified_name`, and `source_hint`. Class references retain package/module or
  business hierarchy; functions retain module, owning class, and parameter
  signature. Source hints are locators such as document name, section, subsystem,
  or module and do not contain copied document bodies.
- The backend encodes references to a stable readable string and deduplicates only
  exact references. The public unit-menu result remains the existing four nested
  `string[]` lists, and old plain-string menus remain valid.

### Retrieval, cache, and frontend behavior

- Unit analysis parses the selected reference into a display label and a richer
  retrieval query. Unit-case prompts use the same qualified target. New clients
  send `unit_type` together with `unit`; both fields now participate in saved
  selection identity, so equal names across unit categories cannot share a
  cached result accidentally. Missing `unit_type` remains accepted for legacy
  callers.
- Bumped only `unit_menu` and `unit_info` prompt versions to v2 so previously
  saved ambiguous extraction artifacts are not presented as current generated
  output after the workflow is continued or regenerated.
- Vue now derives typed, deduplicated select options. The visible label shows the
  display name, qualified name, and source, while the canonical value is sent to
  the backend and restored from session/artifact selection. Old selections fall
  back to the original list-membership restoration logic.

### Tests and cost boundary

- Test-first coverage proves two `create` methods under different owning classes
  remain distinct, exact duplicates collapse, legacy strings parse, qualified
  retrieval is used, structured SSE output stays string-list compatible,
  `unit_type` enters selection metadata, and Vue uses unique typed option values.
- Qualified extraction adds 345 synthetic input tokens across the full small
  19-workflow first run (`20408` total) and the same fixed prompt overhead to the
  large run (`227588` total). Chat calls, embedding builds, output caps, and all
  exact-repeat zero-call behavior are unchanged.
- Focused backend/frontend contracts passed 79 tests; the cost baseline passed 4
  tests; frontend lint had zero errors; and the production build succeeded with
  only the existing size warnings and Node `DEP0180` notice.
- The unfiltered suite has one unrelated repository-data failure because the
  historical sample SQL still references 47 tracked sample documents that are
  currently deleted in the user's dirty worktree. Those user-owned deletions were
  preserved rather than restored or hidden by changing the repository-data test.
- The final gate with that single known asset assertion deselected passed
  `272 passed, 1 deselected in 8.81s`; credential scanning was clean across 129
  tracked, zero staged, and 36 untracked Git-visible files. `git diff --check`
  found no whitespace errors beyond existing Windows line-ending notices.
- No real model, embedding, MySQL, migration, external network, dependency
  install, staging, commit, or push was performed.

## 2026-08-21 — Unit-menu regeneration downstream lock

- Fixed a frontend state-consistency defect where explicitly regenerating the
  unit-test scope kept the previous unit-type selector, unit selector, further
  analysis controls, and generated-case results visible while the replacement
  scope was still streaming.
- Kept the previous in-memory result intact for the existing failure/cancellation
  rollback behavior, but added a Vue computed regeneration state and conditional
  rendering gate that temporarily hides every downstream unit-test section.
  During regeneration the page now shows a clear replacement-in-progress alert;
  success reveals the new scope, while failure or cancellation restores the
  previous valid result.
- Added the frontend contract first and observed the expected failure before the
  implementation. The focused regression passed, all 24 frontend contracts
  passed, frontend lint reported no errors, and the production build succeeded
  with only the existing bundle-size warnings and Node `DEP0180` notices.
- No backend dispatcher, REST/SSE contract, database behavior, persisted
  artifact, model/embedding call, dependency, staging, commit, or push was
  involved in this correction.

## 2026-08-21 — Large qualified unit-menu output budget

- Diagnosed a real CC4C `unit_menu` regeneration failure with Kimi: the complete
  prose analysis streamed successfully, but the exhaustive qualified-reference
  JSON failed final validation and was not saved. The previous valid menu was
  restored by the existing failure rollback behavior.
- The qualified menu requires three fields for every independently addressable
  subsystem, module, class, and function, while the structured stage still had
  the generic analysis cap of 1,536 output Tokens. A fixed synthetic large menu
  with 5 subsystems, 10 modules, 30 classes, and 100 functions measures above
  8,192 Tokens, proving that both the old cap and an 8,192 intermediate clamp
  could truncate valid JSON before the top-level object closed.
- Added the failing budget regression first, then introduced a single
  `unit_menu` structured-output override of 12,288 Tokens and removed the
  redundant generic 8,192 call-site clamp for configured structured analyses.
  All other workflow caps are unchanged, and structured reasoning remains off
  for GLM, Qwen, DeepSeek, and Kimi.
- The offline baseline keeps two chat calls and zero embedding builds for
  `unit_menu`; only its summed output ceiling changes from 9,728 to 20,480.
  Current 19-workflow first-run totals are therefore
  `39/13/20408/230400` (small) and `39/13/227588/230400` (large), while exact
  artifact repeats remain `0/0/0/0`.
- No prompt, business document, reasoning content, credential, or model output
  was added to tests or baseline reports. Diagnosis reused the already rendered
  browser state; no model, embedding, MySQL, external network, dependency,
  migration, staging, commit, or push was invoked.

## 2026-08-21 — Sidebar test-type availability labels

- Fixed a navigation semantics defect where leaving an enabled test page could
  label the entire test type as completed when its internal `*_case` operation
  appeared in `completed_operations`. Completion of an internal saved workflow
  is not completion of the test type itself.
- The eight test-type routes now use route availability as their persistent
  sidebar state: the active route is `当前`, every other unlocked route is
  `可进入`, and internal operation completion no longer changes that label.
  Existing project-analysis regeneration, locked-route, and stale-revision
  states retain their higher-priority `分析中`, `已锁定`, and `已过期` labels.
- Added the frontend contract first and observed the expected failure. The
  focused regression then passed; frontend lint reported no errors and the
  production build completed with only the existing bundle-size warnings and
  Node `DEP0180` notices.
- No backend status calculation, REST/SSE contract, database behavior,
  model/embedding call, migration, dependency, staging, commit, or push was
  involved.

## 2026-08-22 — Test-menu availability and persisted analysis resume

- Fixed the second navigation-status implementation in `TestMenu.vue`. Test
  menu cards no longer infer that an entire test type is finished from its
  terminal `*_case` operation. Every unlocked, non-stale card now remains
  `可进入`; locked and stale source states retain their existing priority.
- Confirmed that all ten generic preliminary-analysis operations (`unit_menu`,
  `unit_info`, `integration_menu`, `integration_info`, and the six remaining
  `*_info` operations) already persist their complete final result envelope in
  `tb_project_workflow_artifact`. Existing compatibility summaries continue to
  be written to `tb_project_info` where an `InfoType` mapping exists; reasoning
  is never persisted.
- Closed the observed revisit gap caused by the frontend model selector
  returning to a different default model after browser/session restoration.
  A normal analysis-step `继续` now falls back to the newest fresh artifact that
  matches project, operation artifact, normalized input selection, source
  revision, and prompt version, even when its producing model differs from the
  currently displayed selector. The resumed SSE artifact metadata reports the
  model that actually produced the stored row.
- Preserved model-specific artifact identities and replacement semantics.
  Explicit `重新生成` still bypasses cached content, invokes the selected model,
  and saves under that selected model's key. Case-generation artifacts remain
  model-specific; source-revision, input-selection, and prompt-version changes
  still force regeneration, and stale artifacts are never reused.
- Added the tests before implementation and observed the expected 12 failures:
  one test-menu contract plus all ten analysis operations and the cache-key /
  regeneration scenario. The focused red-to-green set then passed `12 passed`;
  artifact, dispatcher, catalog, status, and frontend regression checks passed
  `92 passed`.
- The complete offline suite passed `286 passed, 1 deselected in 8.81s`. The
  deselected repository-data assertion is the known user-owned dirty-worktree
  condition: historical sample SQL references tracked sample documents the user
  has deleted. Frontend lint passed with no errors, and the production build
  completed with only the existing asset/entrypoint size warnings and Node
  dependency `DEP0180` notices.
- Verification used mock workflow streams, in-memory SQLite, cleared provider
  keys, and no external network. No real model, embedding, MySQL, migration,
  dependency install, `.env` access, staging, commit, or push was performed.

## 2026-08-22 — Selected-target final cases are session-only

- Applied the product-policy override to final test cases that require a
  fine-grained selected target: `unit_case`, `integration_case`, `api_case`,
  `functional_case`, and `nonfunctional_case`. Their generated result remains
  reactive and visible on the currently mounted page, but is no longer written
  to `tb_project_workflow_artifact` or compatibility `InfoType` rows.
- Kept every preliminary analysis persisted, including unit/integration scope
  and detail analysis plus API, UI, database, functional, nonfunctional, and
  acceptance analysis. `ui_case`, `db_case`, and `acceptance_case` remain
  persisted because they do not select a fine-grained target.
- Added an immutable `artifact | session` policy to the workflow catalog. The
  generic dispatcher now skips artifact lookup and persistence for session-only
  operations, emits no `artifact` event, and completes with `saved=false`.
  Existing REST paths, request bodies, result events, cancellation, streaming,
  and current-page rendering remain unchanged.
- Historical rows were not deleted. Project lifecycle/status derivation ignores
  artifact keys for session-only operations, so an old saved performance case
  cannot make the page appear completed or restore the result. Vue also omits
  those five steps from `sessionStorage` and ignores legacy browser entries and
  old `completed_operations` values during hydration.
- Tests were added first and produced the expected eight failures. The focused
  red-to-green set passed `8 passed`; catalog, dispatcher, API, lifecycle,
  frontend, and cost regressions passed `129 passed`. The complete offline gate
  passed `288 passed, 1 deselected in 8.57s`; the deselection remains the known
  user-owned deleted sample-document assertion.
- The cost report now distinguishes persisted repeats from intentional
  session-only repeats. Persisted artifacts remain `0/0/0/0`. The five
  session-only cross-page repeats measure `15/0/6738/76800` for the small fixture
  and `15/0/46352/76800` for the large fixture (`chat/embedding/input/output
  cap`); retrieval indexes still prevent repeated embedding construction.
- Frontend lint passed without errors and the production build succeeded with
  only the existing asset/entrypoint size and Node `DEP0180` warnings. No real
  model, embedding, MySQL, migration, external network, dependency install,
  `.env` access, deletion, staging, commit, or push was performed.

## 2026-08-22 — Iteration 2 schema-only main release

- Prepared the repository database assets as schema-only deliverables. The
  base `ezllmtest.sql` retains its six table definitions but contains no sample
  rows; six historical `INSERT` statements were removed. The additive
  `iteration_2_workflow_artifacts.sql` migration creates the seventh workflow
  artifact table and likewise contains no `INSERT`, `REPLACE`, or `LOAD DATA`.
- Updated the repository-data contract and database verification script so a
  clean installation with zero project rows is valid. The migration remains
  additive and no existing runtime database was accessed or changed.
- Kept local reconstruction material outside Git: `/example/` and
  `/ez_back_dev/static/projects/` are ignored. Historical tracked sample
  project documents are removed from the repository, while current local
  project documents remain available only in the ignored runtime directory.
- The complete offline backend suite passed `289 passed in 13.03s` with mock
  providers, in-memory SQLite, disabled dotenv loading, and cleared provider
  variables. Frontend lint passed without errors; the production build passed
  with only the existing bundle-size warnings and Node `DEP0180` notice.
- `origin/main` was fetched before release preparation and was synchronized
  with the local pre-release head (`0` behind, `0` ahead). No real model,
  embedding, MySQL, external network service, dependency install, or `.env`
  access was used by the verification steps.
