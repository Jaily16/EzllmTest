# EzllmTest Iteration 1 Implementation Plan

> **For agentic workers:** Execute this plan task-by-task in the current worktree. Update this file and `docs/iteration-development-log.md` after every completed task. Do not commit or push unless the user explicitly requests it.

**Goal:** Modernize EzllmTest to the current LangChain ecosystem, add four-provider Chinese chat-model support, preserve public API and MySQL compatibility, and establish automated quality and credential-safety gates.

**Architecture:** Keep the existing FastAPI → service → LCEL/RAG → DAO flow and Vue component API contracts. Replace legacy LangChain compatibility modules with `langchain-core` runnables, Pydantic 2 models, project-scoped in-memory retrieval, and one registry-driven OpenAI-compatible chat factory. Keep Zhipu `embedding-3` as the only embedding provider.

**Tech Stack:** Python 3.11, FastAPI, Pydantic 2, SQLAlchemy, LangChain Core 1.x, langchain-openai 1.x, Vue 3, TypeScript, MySQL 8.

## Global constraints

- Preserve every existing uncommitted local-reproduction change; never reset, checkout, or overwrite unrelated user work.
- Preserve current API paths, request fields, response envelope, status meanings, MySQL schema, sample data, and the public model name `GLM-4.7`.
- Never read, print, stage, commit, or push real credentials. Do not run paid model calls without explicit user confirmation.
- Application import must not access the network or require any provider credential.
- Dependency installation and database commands are performed manually by the user.
- Keep `docs/superpowers/plans/2026-08-19-local-reproduction.md` unchanged.

---

## Status legend

- `[ ]` pending
- `[-]` in progress
- `[x]` completed and verified
- `[!]` blocked by a required user action

## Task 0: Establish the authoritative dependency and provider baseline

**Dependencies:** None.

**Files:**

- Create: `docs/iteration-1-tasks.md`
- Create: `docs/iteration-development-log.md`

**Acceptance conditions:**

- Official package sources confirm current stable LangChain versions and Python 3.11 support.
- Official vendor documentation confirms one stable default chat model and OpenAI-compatible base URL for each provider.
- No project runtime, database, or paid API is invoked during research.

- [x] Confirm LangChain ecosystem versions from PyPI and current LangChain migration guidance.
- [x] Confirm defaults: `glm-4.7`, `qwen3.7-plus`, `deepseek-v4-flash`, and `kimi-k3`.
- [x] Record provider environment-variable names without values.
- [x] Create the executable task list and development log.

## Task 1: Implement configuration, model registry, and provider error contracts

**Dependencies:** Task 0.

**Files:**

- Modify: `.env.example`
- Modify: `ez_back_dev/app/config.py`
- Replace: `ez_back_dev/llm/provider.py`
- Modify: `ez_back_dev/tools/llmTools.py`
- Modify: `ez_back_dev/llm/llm_*.py`
- Create: `ez_back_dev/tests/test_model_registry.py`
- Extend: `ez_back_dev/tests/test_config.py`
- Extend: `ez_back_dev/tests/test_provider.py`

**Interfaces:**

- Produces `ModelSpec`, `list_model_specs()`, `list_model_labels()`, `get_model_spec(label)`, `get_chat_client(label)`, `get_chat_model(label)`, and `get_embeddings()`.
- Produces typed errors for unsupported models, missing credentials, timeout, rate limit, provider failures, empty output, and output parsing.

**Acceptance conditions:**

- The stable public labels are exactly `GLM-4.7`, `通义千问`, `DeepSeek`, and `Moonshot Kimi`.
- Each provider uses independent API key, base URL, model, and timeout environment variables.
- No credential is validated until the selected client is invoked or explicitly requested.
- Mock tests prove client parameters and error translation without network access.

- [x] Write registry/config/error tests.
- [x] Implement configuration fields and immutable model registry.
- [x] Implement cached OpenAI-compatible clients and safe runnable wrappers.
- [x] Route every legacy model wrapper through the registry.
- [x] Run focused offline tests in the intended `ezllmtest` environment with deprecation warnings treated as errors.

## Task 2: Migrate LangChain chains, schemas, loaders, and retrieval

**Dependencies:** Task 1.

**Files:**

- Modify: `ez_back_dev/model/ChainJsonModel.py`
- Modify: `ez_back_dev/model/HttpModel.py`
- Modify: `ez_back_dev/model/TestProject.py`
- Modify: `ez_back_dev/chain/BasicChain.py`
- Replace: `ez_back_dev/chain/KnowledgeChain.py`
- Replace: `ez_back_dev/vectorstore/loader.py`
- Replace: `ez_back_dev/vectorstore/retrievers.py`
- Modify: affected service modules under `ez_back_dev/service/`
- Modify: `ez_back_dev/requirements.txt`
- Create: `ez_back_dev/tests/test_chains.py`
- Create: `ez_back_dev/tests/test_retrievers.py`

**Interfaces:**

- All generated chains remain synchronous `Runnable` objects supporting `.invoke()`.
- Knowledge RAG continues returning `{"answer": <text>}`.
- Project document retrieval becomes request/project scoped and never reuses another project’s vector store.

**Acceptance conditions:**

- No production import from `langchain_core.pydantic_v1`, `langchain.chains`, `langchain.retrievers`, `langchain.storage`, or legacy Chroma modules.
- No application import triggers network access, embeddings, or chat completion.
- Output parsers convert malformed/empty model output into typed, understandable errors.
- Focused tests pass with deprecation warnings treated as errors.

- [x] Add failing chain/retriever isolation and parsing tests.
- [x] Move schema models to Pydantic 2 and ORM base to SQLAlchemy 2 style.
- [x] Replace legacy chains with local LCEL composition.
- [x] Replace global Chroma/FAISS retrievers with project-scoped core retrieval.
- [x] Replace community document loaders with local direct loaders.
- [x] Pin the verified modern dependency set and run focused tests with deprecation warnings treated as errors.

## Task 3: Stabilize API errors and repair all testing workflows

**Dependencies:** Tasks 1–2.

**Files:**

- Modify: `ez_back_dev/app/main.py`
- Modify: `ez_back_dev/app/routers.py`
- Modify: all `ez_back_dev/service/llm*Service.py` modules
- Create: `ez_back_dev/tests/test_api_contracts.py`
- Create: `ez_back_dev/tests/test_service_errors.py`

**Acceptance conditions:**

- Existing successful response payloads remain unchanged.
- Illegal model, missing credential, timeout, rate limit, parse failure, and empty result produce deterministic HTTP status and compatible `{status, reason, data}` bodies.
- Tests cover menu, plan, unit, integration, API, UI, database, functional, nonfunctional, and acceptance routes with mocks.
- No service swallows typed provider/output exceptions into an unexplained `False`.

- [x] Capture all current API methods, paths, request models, and response envelopes in tests.
- [x] Add FastAPI exception handlers for typed LLM failures.
- [x] Preserve typed LLM failures across service boundaries.
- [x] Repair route/service defects discovered by the contract suite.
- [x] Run the complete backend offline suite.

## Task 4: Synchronize frontend model selection and repair page flows

**Dependencies:** Tasks 1 and 3.

**Files:**

- Modify: `ez_front_dev/src/config/models.ts`
- Modify: `ez_front_dev/src/components/TestMenu.vue`
- Modify: `ez_front_dev/src/components/TestPlan.vue`
- Modify: `ez_front_dev/src/components/UnitTest.vue`
- Modify: `ez_front_dev/src/components/IntegrationTest.vue`
- Modify other feature components when contract tests expose defects.
- Modify: `ez_front_dev/package.json` when a directly imported dependency is undeclared.

**Acceptance conditions:**

- All selectors expose the same four labels accepted by the backend.
- Existing `llm_name` path/body conventions remain intact.
- Integration fallback includes the required model path argument.
- All ten functional pages retain their core request flow.
- `npm run lint` and `npm run build` pass after the user-installed dependency baseline is available.

- [x] Update the central frontend model list.
- [x] Repair integration and shared-state flow defects.
- [x] Audit every Axios call against backend routes and request schemas.
- [x] Run lint/build and record results.

## Task 5: Add Git and credential-safety automation

**Dependencies:** Task 0; may run alongside Tasks 1–4.

**Files:**

- Modify: `.gitignore`
- Create: `scripts/scan_credentials.py`
- Create: `ez_back_dev/tests/test_credential_scan.py`
- Update tracked index only for generated caches; do not delete local user data.

**Acceptance conditions:**

- All `.env` variants are ignored except `.env.example` files.
- Python caches, build output, IDE metadata, test caches, and local vector caches are ignored.
- Already tracked `__pycache__`, `*.pyc`, `.DS_Store`, and IDE metadata are removed from the Git index without deleting working copies.
- Credential scan checks tracked, staged, and untracked candidate text files and redacts all findings.
- Tests and examples use visibly invalid placeholder values.

- [x] Expand ignore rules and add explicit example exceptions.
- [x] Implement redacted credential scanning with provider/database/LangSmith patterns.
- [x] Add scanner tests using synthetic placeholder and secret-like fixtures.
- [x] Stop tracking generated caches with index-only Git operations.
- [x] Run scanner against tracked, staged, and untracked files before final handoff.

## Task 6: Complete offline, frontend, and read-only compatibility verification

**Dependencies:** Tasks 1–5.

**Files:**

- Extend existing tests under `ez_back_dev/tests/` as coverage gaps are found.
- Modify: `ez_back_dev/scripts/verify_database.py` only if read-only checks need clearer errors.

**Acceptance conditions:**

- Backend configuration, registry, provider mocks, parsing, import safety, API contracts, sample data, and credential scanner all pass.
- Import-safety test proves no socket/network function is called while importing the application.
- Read-only SQL/static-data checks prove six tables, seven sample projects, and referenced files remain compatible.
- If the user runs the live database verifier, it performs only metadata and `SELECT` operations.
- Frontend lint/build pass without new errors.

- [x] Run backend tests with deprecation warnings treated as errors.
- [x] Run credential and tracked-file checks.
- [x] Run frontend lint and build.
- [x] Provide the exact read-only database verification command if live verification is still required.

## Task 7: Optional paid/runtime verification and final audit

**Dependencies:** Task 6 and explicit user approval for any paid call.

**Files:**

- Modify: `ez_back_dev/scripts/smoke_llm.py`
- Modify: `README.md`
- Update: `docs/iteration-development-log.md`
- Update: `docs/iteration-1-tasks.md`

**Acceptance conditions:**

- Smoke script requires an explicit provider selection and never prints credentials.
- Real smoke tests remain unexecuted unless the user confirms cost and locally configures the relevant key.
- Final audit maps every requested requirement to concrete file/test evidence.
- Final report lists changes, commands/results, paid tests not run, known limitations, historical-key rotation requirement, and next steps.

- [x] Make smoke tests explicit and opt-in.
- [x] Update README configuration and migration instructions.
- [x] Perform requirement-by-requirement completion audit.
- [x] Record any user-only dependency/database/paid steps and deliver the final report.

## Post-plan product workflow completion (2026-08-20)

These additions were requested and completed after Tasks 0–7 while retaining their compatibility and safety constraints.

- [x] Make project analysis enter the test-plan page before the test menu and downstream test pages.
- [x] Generate and atomically persist the business summary, test plan, and test menu as one readiness bundle.
- [x] Lock downstream navigation until the persisted analysis bundle is ready.
- [x] Add provider-aware streamed progress, reasoning, answer, usage, cancellation, and delayed persistence to test-plan generation.
- [x] Add the generic `POST /project/llm/workflow/stream` SSE endpoint for all 18 non-plan analysis/case operations.
- [x] Replace all LLM blocking spinners on the eight test pages with the shared execution panel.
- [x] Position each multi-step execution panel below the button that starts its active operation.
- [x] Preserve legacy endpoints and database behavior through 131 offline backend tests, zero-warning frontend lint, and a successful production build.
- [x] Complete `docs/iteration-1-closeout.md`, the Iteration 2 task plan, and the two new-conversation prompts.
