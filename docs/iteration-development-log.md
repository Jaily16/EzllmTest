# EzllmTest Iteration Development Log

## 2026-08-19

### Completed

- Preserved the existing dirty worktree and established an inline, task-by-task iteration plan.
- Confirmed the current stable package baseline from official PyPI metadata:
  - `langchain==1.3.14`
  - `langchain-core==1.5.6`
  - `langchain-openai==1.5.2`
  - `langchain-text-splitters==1.1.2`
  - `langchain-chroma==1.1.0`
  - `langchain-community==0.4.2` is archived and should not remain a new architectural dependency.
- Confirmed all listed LangChain packages support Python 3.11 through their Python `>=3.10` metadata.
- Confirmed provider defaults and OpenAI-compatible endpoints from official vendor documentation:
  - Zhipu: public label `GLM-4.7`, model `glm-4.7`, base URL remains `https://open.bigmodel.cn/api/paas/v4/`.
  - Alibaba Model Studio: public label `通义千问`, model `qwen3.7-plus`, base URL `https://dashscope.aliyuncs.com/compatible-mode/v1`.
  - DeepSeek: public label `DeepSeek`, model `deepseek-v4-flash`, base URL `https://api.deepseek.com`. The former `deepseek-chat` alias was deprecated on 2026-07-24 and is not used as the default.
  - Moonshot: public label `Moonshot Kimi`, model `kimi-k3`, base URL `https://api.moonshot.ai/v1`.
- Chose independent environment variables:
  - Zhipu: `ZHIPU_API_KEY`, `ZHIPU_BASE_URL`, `ZHIPU_CHAT_MODEL`, `ZHIPU_TIMEOUT_SECONDS`, `ZHIPU_EMBEDDING_MODEL`.
  - Alibaba: `DASHSCOPE_API_KEY`, `DASHSCOPE_BASE_URL`, `DASHSCOPE_CHAT_MODEL`, `DASHSCOPE_TIMEOUT_SECONDS`.
  - DeepSeek: `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, `DEEPSEEK_CHAT_MODEL`, `DEEPSEEK_TIMEOUT_SECONDS`.
  - Moonshot: `MOONSHOT_API_KEY`, `MOONSHOT_BASE_URL`, `MOONSHOT_CHAT_MODEL`, `MOONSHOT_TIMEOUT_SECONDS`.

### Code decisions

- Keep `GLM-4.7` byte-for-byte compatible as the existing public selector label.
- Use stable display labels as API identifiers; provider model IDs remain independently overrideable through environment variables.
- Keep Zhipu `embedding-3` as the only embedding provider in iteration 1.
- Prefer `langchain-core` runnables and project-scoped `InMemoryVectorStore` over legacy `langchain.chains`, `langchain.retrievers`, global Chroma collections, and FAISS wrappers. This removes cross-project vector contamination and avoids adding `langchain-classic`.
- Replace community document loaders with direct `pypdf`, `docx2txt`, and text reads while still returning `langchain_core.documents.Document` objects.
- Do not rewrite Git history. Historical keys remain a documented rotation/revocation responsibility.

### Validation evidence

- Documentation and package research only; no application import, database access, test suite, build, or paid API call was executed in this task.
- No real `.env` file or credential value was read or printed.

### Defects and risks discovered

- Kimi K3 fixes `temperature=1.0`; the common factory must omit the existing `temperature=0.5` setting for this provider.
- DeepSeek’s old `deepseek-chat` stable alias is now deprecated, so older examples must not drive the new default.
- Current installed local packages may still be the LangChain 0.2 reproduction set. Dependency installation is a later manual user gate after source and requirements changes are ready.

### Next step

- Task 2: add chain/retriever isolation tests, then replace legacy LangChain chains, loaders, and globally shared vector stores.

### Task 1 implementation

- Added the immutable four-provider registry and stable public labels in `llm/provider.py`.
- Added independent key, base URL, model ID, and timeout settings for Zhipu, Alibaba Model Studio, DeepSeek, and Moonshot.
- Kept Zhipu `embedding-3` as the sole embedding implementation.
- Added lazy runnable construction, per-provider cached clients, and typed errors for unsupported labels, missing configuration, timeout/connectivity, rate limits, provider failures, and empty responses.
- Avoided leaking raw SDK exception messages through the typed provider errors.
- Routed `tools/llmTools.py` and the legacy TongYi/MoonShot wrappers through their actual registry entries; all other compatibility wrappers continue selecting `GLM-4.7`.
- Expanded `.env.example` using placeholder-only values and environment-variable names.

### Task 1 validation evidence

- Wrote offline tests for registry ordering/defaults, missing selected credentials, client parameters, error translation, and configuration loading.
- `python -m py_compile` passed for every modified Task 1 Python file and its tests.
- `git diff --check` passed; only existing Windows line-ending normalization warnings were reported.
- Focused Pytest collection could not start because the current shell resolves to the Anaconda base Python, where `langchain_core` is absent. No dependency was installed or upgraded automatically. The suite must be rerun after the user activates the intended `ezllmtest` environment and installs the later pinned requirements.
- No model API, database, backend, frontend, or network service was invoked.

### Task 2 implementation

- Migrated structured-output models from `langchain_core.pydantic_v1` to Pydantic 2 and route serialization from `.dict()` to `.model_dump()`.
- Migrated the SQLAlchemy declarative base to `DeclarativeBase` without changing table names, columns, keys, or relationships.
- Replaced legacy retrieval-chain helpers with a local LCEL RAG runnable that preserves the `input`, `context`, and `answer` result keys.
- Added safe JSON validation that converts malformed model output into `LLMOutputParsingError` without exposing raw provider output.
- Replaced process-global Chroma/FAISS stores with request-scoped `InMemoryVectorStore` instances. Design and requirement retrieval still split parent/child documents and return the matched parents.
- Replaced `langchain-community` loaders with direct UTF-8 text/Markdown, `pypdf`, and `docx2txt` loaders.
- Removed runtime imports of `langchain`, `langchain-community`, Chroma, and FAISS, including the unused legacy helper.
- Pinned the directly used Python dependencies, including `langchain-core==1.5.6`, `langchain-openai==1.5.2`, and `langchain-text-splitters==1.1.2`.

### Task 2 validation evidence

- Added chain parsing/content tests and a deterministic fake-embedding test proving two project retrievers cannot see one another's documents.
- `python -m py_compile` passed for all modified Task 2 source and test files.
- Static searches found no remaining Python imports from the forbidden legacy LangChain, Chroma, FAISS, or community modules, and no remaining Pydantic `.dict()` calls.
- `git diff --check` passed with line-ending notices only.
- The existing `ezllmtest` environment is Python 3.11.15 but still contains `langchain-core==0.2.43`, `langchain-openai==0.1.25`, and `langchain-text-splitters==0.2.4`; it cannot validate the 1.x implementation until the user installs `ez_back_dev/requirements.txt`.
- No model request, database access, service startup, or paid operation was performed.

### Manual gate

- Resolved on 2026-08-19. The user installed the pinned requirements, removed the unused legacy `langchain` and `langchain-community` packages, and `python -m pip check` reported `No broken requirements found.`

### Task 1 completed validation

- Added an explicit provider identifier to each immutable registry entry (`zhipu`, `alibaba`, `deepseek`, and `moonshot`) so the registry centrally records both public label and vendor.
- Ran `tests/test_config.py`, `tests/test_model_registry.py`, and `tests/test_provider.py` in the Python 3.11 `ezllmtest` environment with deprecation warnings treated as errors.
- Result: `9 passed in 1.57s`; no network request or paid model call was made.
- `git diff --check` passed for the Task 1 files; only Windows line-ending notices remained.

### Task 2 completed validation

- Added direct-loader tests for UTF-8/BOM text, Markdown, PDF page metadata, minimal local DOCX content, and the legacy `False` result for unsupported extensions.
- Added an LCEL RAG contract test proving `knowledge_retrieval_chain()` preserves the existing `input`, `context`, and `answer` keys.
- Added a subprocess import-safety test that replaces socket connection functions with failures before importing `app.main`; application import completed without network access.
- Added a production-source gate for `pydantic_v1`, legacy `langchain` chains/retrievers/storage, `langchain-community`, Chroma, and FAISS imports.
- Added SQLAlchemy metadata checks proving the same six mapped table names and columns remain after migration to `DeclarativeBase`, including the composite project-info primary key.
- Ran all Task 2 tests under Python 3.11 with deprecation warnings treated as errors: `13 passed in 5.02s`.
- `python -m pip check` reported `No broken requirements found.`
- `git diff --check` passed for the Task 2 paths; only Windows line-ending notices remained.
- No model API, embedding API, database, backend service, or paid operation was invoked.

### Task 3 implementation and validation

- Added deterministic FastAPI mappings for unsupported model (400), missing provider configuration (503), timeout (504), rate limit (429), malformed output (502), empty output (502), and other provider failures (502).
- Preserved the existing `{status, reason, data}` response envelope for both successful and typed-error responses.
- Updated every broad exception boundary in the ten LLM service modules to re-raise `LLMError` before retaining the legacy fallback behavior for unrelated local failures.
- Captured all existing project and testing HTTP paths/methods through the generated OpenAPI contract. FastAPI 0.141 represents included routers internally, so the test deliberately uses the public OpenAPI surface instead of private route objects.
- Added mock success coverage for menu, plan, unit, integration, API, UI, database, functional, nonfunctional, and acceptance workflows, plus all eight case-generation request bodies.
- Added Pydantic request-field checks for every case-generation model.
- Corrected the integration case endpoint's copied unit-test success/failure reason text without changing its path, body, status code, or data field.
- Task 3 focused result: `29 passed in 2.36s` with deprecation warnings treated as errors.
- Complete backend offline result: `54 passed in 5.69s` with deprecation warnings treated as errors.
- `git diff --check` passed for Task 3 source and tests; only Windows line-ending notices remained.
- No real model, embedding, database, backend service, or paid operation was invoked.

### Task 4 implementation and validation

- Expanded the shared frontend registry to exactly `GLM-4.7`, `通义千问`, `DeepSeek`, and `Moonshot Kimi`, in the same order as the backend registry.
- Kept all existing `llm_name` path/body conventions in Test Menu, Test Plan, and all three Unit Test model selectors.
- Fixed Integration Test's unit-analysis fallback to append the required `GLM-4.7` model path segment.
- Prevented duplicate integration menu entries on repeated analysis and restored all four integration loading flags on typed failure responses.
- Configured Axios to resolve backend 4xx/5xx typed-error envelopes so every existing page continues displaying `reason` and clearing its local loading state instead of skipping `.then()`.
- Replaced the stale GLM-only Test Menu hint with provider-neutral selector text.
- Declared the directly imported `lodash` and `@types/lodash` packages instead of relying on Vue CLI's transitive copies; updated the lockfile offline. The lock operation reported `0 vulnerabilities`.
- Added cross-stack tests proving frontend labels match the backend registry, every selector uses the shared options, the integration fallback includes its model segment, and all ten feature pages retain their core API flow.
- Frontend contract result: `5 passed in 1.00s`.
- `npm run lint` passed with `0 errors` and the same 17 pre-existing warnings observed before Task 4.
- `npm run build` completed successfully. It reported only legacy toolchain/asset warnings: stale Browserslist metadata, Node 24 `fs.Stats` deprecation from Vue CLI dependencies, existing lint warnings, and large bundled assets.
- `npm ls lodash @types/lodash --depth=0` resolved the declared versions without errors.
- `git diff --check` passed for Task 4 files; only Windows line-ending notices remained.
- No backend service, model API, embedding API, or database was invoked.

### Task 5 implementation and validation

- Expanded the root `.gitignore` so all root and nested `.env` variants are ignored while root and nested `.env.example` files remain visible to Git.
- Added ignore coverage for Python/test caches, package/build output, frontend dependencies, IDE/editor metadata, operating-system metadata, and local FAISS/pickle vector indexes.
- Replaced the database value in `.env.example` with a visibly invalid `replace_with_...` password and kept every provider and optional LangSmith credential as an explicit placeholder.
- Added a standard-library-only scanner at `scripts/scan_credentials.py`. It scans tracked working-tree text, staged index blobs, and non-ignored untracked text as separate scopes.
- Added provider `sk-`, LangSmith `lsv2_`, database URL, and sensitive-assignment rules. Findings contain only scope, path, line number, rule name, and `[REDACTED]`; matched values, source lines, and hashes are never rendered.
- Added synthetic tests that assemble secret-like fixtures only at runtime, verify placeholder exemptions and redaction, exercise all three Git scopes, and prove ignored `.env` files are excluded.
- Refined the assignment rule after a redacted scan identified `forgetPassword` and `changePassword` API fields as false positives; exact sensitive identifiers and uppercase environment-variable names remain covered.
- Credential scanner tests: `10 passed in 0.32s`.
- Final repository scan: clean with `tracked=74`, `staged=0`, and `untracked=27` candidate text sources.
- With explicit user approval, removed exactly 50 generated cache, `.DS_Store`, and `.idea` entries from the Git index using index-only operations. All 50 local working copies remained present and the remaining tracked generated-artifact count is 0.
- `git check-ignore` verification proved root/nested `.env` paths are ignored and root/nested `.env.example` paths remain visible.
- No local cache or IDE file was physically deleted. No real `.env` value was read or printed, and no commit or push was performed.

### Task 6 implementation and validation

- Added a direct static assertion that `ezllmtest.sql` declares exactly the expected six tables.
- Added a fake-engine test for `scripts/verify_database.py`. It proves the verifier performs table metadata inspection and executes exactly `SELECT COUNT(*) FROM tb_test_project`; the test opens no database or network connection.
- Existing static-data checks continue proving exactly seven sample projects and all 47 SQL-referenced document files are present.
- Focused repository-data result with deprecation warnings treated as errors: `4 passed in 0.24s`.
- Complete backend result with every `DeprecationWarning` treated as an error: `72 passed in 5.86s`.
- The full suite includes configuration, four-provider registry and mocks, parsing, request-scoped retrieval, direct loaders, socket-blocked import safety, six-table SQLAlchemy metadata, FastAPI contracts, sample data, frontend contracts, and credential scanning.
- `python -m pip check` reported `No broken requirements found.`
- Final credential scan was clean with `tracked=74`, `staged=0`, and `untracked=28` candidate text sources.
- Git safety checks reported 0 generated artifacts still tracked, 50 authorized staged index-only deletions, ignored root/nested `.env` paths, and visible root/nested `.env.example` paths.
- `npm run lint` completed with exit code 0, 0 errors, and the existing 17 warnings.
- `npm run build` completed successfully. It retained the known stale Browserslist metadata, Vue CLI/Node `fs.Stats` deprecation, existing lint warning summary, and large-asset warnings; no new build error was introduced.
- The live database was not accessed. If live confirmation is desired, the exact read-only command is:

```powershell
Set-Location D:\codex\EzllmTest_v2\ez_back_dev
& 'D:\tool\anaconda3\envs\ezllmtest\python.exe' .\scripts\verify_database.py
```

- The verifier contains no INSERT, UPDATE, DELETE, DDL, commit, or migration operation. No model API, embedding API, service startup, dependency installation, commit, or push was performed during Task 6.

### Task 7 implementation and final audit

- Replaced the implicit GLM-plus-embedding smoke script with an argument-driven CLI. `--provider` is required, `--confirm-cost` is required before any model factory call, and `--with-embedding` is an additional Zhipu-only opt-in.
- Added offline tests for missing provider selection, missing cost confirmation, all four provider-to-public-label mappings, embedding gating, usage output, unexpected-error redaction, and README command safety.
- The smoke script truncates displayed model content, prints only numeric usage fields, and never renders raw unexpected SDK exceptions or credential values.
- Focused smoke/README result: `10 passed in 1.09s`.
- A local command without `--confirm-cost` exited 1 before model creation and instructed the caller to add the explicit flag. No paid CLI call was made during Task 7.
- Updated README setup for the pinned LangChain Core 1.x/Pydantic 2/SQLAlchemy 2 baseline, all four provider configurations, Zhipu-only embeddings, safe `.env` creation, Moonshot international/China endpoint pairing, credential scanning, explicit paid commands, migration notes, and known limitations.

#### Existing user-approved real-call evidence

- GLM-4.7 and Zhipu `embedding-3` had already passed the original local reproduction connectivity check.
- Alibaba `qwen3.7-plus` returned `QWEN_OK`: 17 input, 66 output, 83 total tokens; 57 output tokens were reported as reasoning.
- `deepseek-v4-flash` returned `DEEPSEEK_OK`: 94 input, 21 output, 115 total tokens; 15 output tokens were reported as reasoning.
- The first Kimi K3 call used the international `.ai` endpoint with a China-platform key and returned 401 before successful generation. After the user changed `MOONSHOT_BASE_URL` to `https://api.moonshot.cn/v1`, Kimi returned `MOONSHOT_OK`: 95 input, 205 output, 300 total tokens; 186 output tokens were reported as reasoning.
- All real calls were made only after the user explicitly confirmed cost and configured keys locally. No key value was read, printed, or copied into repository files.

#### Requirement-to-evidence map

| Iteration requirement | Implementation and verification evidence |
| --- | --- |
| Modern Python/LangChain baseline | `requirements.txt` pins Python 3.11-compatible FastAPI/Pydantic/SQLAlchemy and LangChain Core/OpenAI 1.x packages; final `pip check` reported no broken requirements. |
| Four Chinese-provider chat models | `llm/provider.py` owns immutable Zhipu, Alibaba, DeepSeek, and Moonshot specs; registry/client/error/config tests cover all four, and each provider factory completed a real call. |
| LangChain/Pydantic/RAG migration | LCEL runnables, Pydantic 2 models, direct document loaders, and request-scoped in-memory vector stores are covered by parsing, loader, retrieval-isolation, and forbidden-import tests. |
| API and database compatibility | FastAPI contract tests preserve paths, fields, status envelope, and all ten feature flows; ORM/static SQL tests preserve six tables, seven projects, and 47 referenced files. |
| Import and read-only safety | The subprocess import test replaces socket connection functions with failures; database verification tests prove metadata inspection plus one `SELECT COUNT(*)` only. |
| Frontend provider selection | The shared Vue options display `glm-4.7`, `qwen3.7-plus`, `deepseek-v4-flash`, and `kimi-k3` while retaining stable backend public-label values; frontend contract tests, lint, and build pass. |
| Git and credential safety | `.gitignore`, the redacted multi-scope scanner, synthetic scanner tests, placeholder examples, and 50 authorized index-only generated-file removals satisfy the Git safety gate. |
| Explicit paid verification | `scripts/smoke_llm.py` requires both provider and cost confirmation; provider-level real-call results are recorded above without repeating paid requests in Task 7. |

#### Final offline gates

- Complete backend suite with deprecation warnings treated as errors: `82 passed in 6.00s`.
- Dependency consistency: `No broken requirements found.`
- Credential scan: clean with `tracked=74`, `staged=0`, and `untracked=30` candidate text sources.
- Git safety: 0 generated artifacts remain tracked and 50 authorized index-only deletions remain staged; every local copy remains ignored rather than physically deleted.
- Task 6 frontend gates remain valid: lint exit 0 with 0 errors/17 existing warnings; production build successful with only documented legacy toolchain and asset-size warnings.

#### Known limitations and next steps

- Provider-level real calls do not prove that every FastAPI business endpoint works end-to-end with every provider. Those flows remain covered by mocks; representative real endpoint verification would incur additional model and embedding cost.
- Zhipu `embedding-3` remains the only embedding implementation, including when another provider is selected for chat.
- The Task 6 live MySQL verifier was not executed automatically. The script is tested read-only and the exact optional command is documented in README and the Task 6 log.
- The new paid CLI itself was not run against live providers during Task 7; the recorded real-call evidence came from the earlier user-approved direct factory checks.
- Existing frontend lint/toolchain/asset warnings remain future cleanup work.
- Credential scanning covers current Git-visible text, not full history. Any historical LangSmith or provider key must be revoked/rotated; Git history was deliberately not rewritten.
- The 50 generated-file index deletions and all source changes remain uncommitted. The user should review the complete worktree before choosing a commit strategy; no commit or push was performed.

## 2026-08-20

### Test-plan-first project workflow

- Changed project login/creation entry from the test menu to the test-plan page.
- Added a persisted analysis readiness state and route guard. The summary, test plan, and test menu are saved in one transaction; the test menu and all manual testing routes remain locked until the bundle is complete.
- Kept the legacy test-plan and test-menu routes while adding `GET /project/analysis/status/{pid}` for persisted readiness recovery.
- Updated the test-plan page to display the initial business summary and final plan separately and renamed the primary action to “开始分析业务和生成测试计划”.

### Streamed plan and all-test workflows

- Added raw provider-aware streaming that preserves third-party `reasoning_content`, final content deltas, and returned token usage.
- Added `POST /project/llm/plan/stream` progress for document load/split, map analysis, reduce/final generation, and database persistence. Cancellation and failure leave the prior plan bundle unchanged.
- Added `POST /project/llm/workflow/stream` with 18 operations covering unit, integration, API, UI, database, functional, nonfunctional, and acceptance analysis/case generation.
- Added one reusable Vue stream composable and execution panel with progress, chunk counts, session-only thinking sections, streamed answer, usage, cancel, retry/error state, and sanitized messages.
- Replaced the eight testing pages' blocking `v-loading` LLM overlays and direct multi-request orchestration with the generic SSE workflow.
- Moved each execution panel to the active step's action location, so menu analysis, further analysis, and final case generation render feedback immediately below their own button.

### Compatibility and safety evidence

- All legacy FastAPI endpoints and response envelopes remain covered by contract tests.
- Workflow analysis and case tests use fake provider streams, documents, retrievers, and embeddings; no final-regression test accessed a paid API.
- Unknown SSE failures return a sanitized generic message and never return an upstream body.
- New reusable analysis/knowledge values are queued and written only after complete generation and a final disconnect check.
- Authorized removal of 50 generated cache/IDE files remains index-only; local copies are retained and covered by `.gitignore`.

### Final gates

- Backend: `131 passed`.
- Frontend: `npm run lint` completed with zero errors and zero warnings.
- Frontend: `npm run build` completed successfully; only Node deprecation and existing asset/entrypoint size recommendations remain.
- Git: `git diff --check` reports no whitespace error, only Windows line-ending notices.
- Iteration 1 closeout: `docs/iteration-1-closeout.md`.
- Iteration 2 plan: `docs/iteration-2-tasks.md`.
- Iteration 2 handoff prompts: `docs/iteration-2-prompts.md`.

### Next step

- Start a new conversation with the first prompt in `docs/iteration-2-prompts.md`, accept its read-only report, then send the second prompt to execute Iteration 2 Task 0 only.
