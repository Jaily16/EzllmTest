# EzllmTest Iteration 1 Closeout

## Status

Iteration 1 is complete and ready for the GitHub `main` synchronization authorized on 2026-08-20.

## Delivered

- Reproduced the Windows local stack on Python 3.11, FastAPI 8130, Vue 3 on 8080, and MySQL `ezllmtest_dev`.
- Migrated production chains to LangChain Core 1.x/LCEL, Pydantic 2, SQLAlchemy 2, direct document loaders, and project-scoped retrieval.
- Added one registry for Zhipu, Alibaba Model Studio, DeepSeek, and Moonshot with stable frontend/backend labels and sanitized provider errors.
- Verified real connectivity for GLM, Zhipu `embedding-3`, Qwen, DeepSeek, and Kimi only after explicit user cost approval.
- Added credential-safe examples, a redacted repository scanner, ignore rules, and index-only removal of 50 generated cache/IDE files while retaining every local copy.
- Changed project entry to a test-plan-first lifecycle. Business summary, test plan, and test menu are generated/persisted as one recoverable bundle; downstream routes remain locked until it is ready.
- Added streamed plan generation with real progress, reasoning, final output, token usage, cancellation, sanitized errors, and delayed atomic persistence.
- Added `POST /project/llm/workflow/stream` for all 18 unit, integration, API, UI, database, functional, nonfunctional, and acceptance analysis/case operations.
- Replaced all LLM blocking spinners in the eight testing pages with contextual progress/reasoning/answer panels positioned below the button that starts the active step.
- Preserved legacy LLM endpoints, request bodies, response envelopes, project IDs, MySQL fields, and `InfoType` values.

## Final Verification

- Backend offline suite: `131 passed`.
- Frontend lint: zero errors and zero warnings.
- Frontend production build: successful.
- Production-build warnings are limited to existing Node `fs.Stats` deprecation notices and asset/entrypoint size recommendations.
- `git diff --check`: no whitespace errors; Windows LF-to-CRLF notices only.
- No real model or embedding call was made during the final streaming/UI regression runs.

## Git Safety

- Real `.env` files remain ignored and are not part of the release.
- Example configuration contains placeholder values only.
- The credential scanner reports findings by redacted category/path and never prints matching values.
- The 50 staged generated-file deletions are Git index cleanup: `.DS_Store`, `.idea`, `__pycache__`, and `*.pyc` local copies were not physically deleted by that operation.
- Git history was not rewritten. Any historical key previously exposed outside this iteration remains subject to provider-side revocation/rotation.

## Known Limits Carried into Iteration 2

- Existing workflow caches are mostly keyed by `InfoType`, not by document revision, prompt version, selection payload, and model. A changed document can therefore require explicit regeneration.
- Request-scoped vector stores prevent cross-project contamination but may repeat embedding work across separate workflow requests.
- Several workflows separately generate summaries, structured choices, knowledge answers, and final cases, which can resend overlapping context and consume unnecessary reasoning/output tokens.
- Final test cases and user selections are not uniformly persisted/resumed across all test types.
- Production assets remain large: the bundled font, logo, Element Plus/vendor CSS, and vendor JS trigger Vue CLI performance recommendations.
- Provider-level smoke checks do not constitute a paid end-to-end matrix of all 19 streamed workflows across all four providers.

## Next Iteration

Iteration 2 is defined in `docs/iteration-2-tasks.md`. It focuses on a revision-aware project lifecycle, resumable artifacts for every testing step, retrieval-index reuse, bounded RAG context, stage-specific thinking/output budgets, and measurable reductions in repeated chat/embedding calls.
