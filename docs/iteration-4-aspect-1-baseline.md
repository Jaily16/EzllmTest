# Iteration 4 Aspect 1 Baseline

Captured on 2026-08-27 before any Aspect 1 dependency or runtime change. This
document records facts; it does not claim an Agent runtime exists or that
performance improved.

## Git and user-owned worktree state

- Branch: `main`.
- HEAD: `3c49e864a523a4af4c0f3efd4f845e8ce7b1caed`.
- Local `origin/main`: `3c49e864a523a4af4c0f3efd4f845e8ce7b1caed`.
- Ahead/behind: `0/0`. No fetch or pull was performed.
- Existing modified user asset: `README.md`, SHA-256
  `71ADFD7358A4DFAF5F254CD5584BDB606C7CD4FFC0B045DB96F4391BAB7D8AFE`,
  18,728 bytes. Git reported the existing LF-to-CRLF warning; Aspect 1 does
  not edit or normalize the file.
- Existing untracked user asset: `docs/iteration-4-overview.md`, SHA-256
  `8E4FC33E3139E313BAA39E832D9D8CE765918383301E3135CFEB377BAB0DC786`,
  16,528 bytes.
- Existing untracked user asset: `docs/iteration-4-prompts.md`, SHA-256
  `34653AEFBECB2B4ACAE22311930929E21AA0F4C25881E40404629B5AA3247C0D`,
  6,254 bytes.

All three pre-existing dirty files are user assets. Aspect 1 must not alter,
stage, delete, reformat, or adopt them as generated output.

## Runtime and manifest identity

- Approved backend interpreter used for the baseline: Python 3.11.15 at the
  existing `ezllmtest` environment. No package was installed.
- Host default Python 3.12.7 was observed but not used for the backend gate.
- Node: v24.18.0; npm: 11.16.0; existing `node_modules` was present.
- `ez_back_dev/requirements.txt`:
  `131F71733433D2806083756DFB2B5E315B66A678E304EBA6EB3E82FF0F4C7FEF`.
- `ez_front_dev/package.json`:
  `769EC529E786375A8DCDB5FCE27C1A4A44D5DDEDC3B9946E2850DEA8477BD5C3`.
- `ez_front_dev/package-lock.json`:
  `C93CDE311DB8675A62A781E20F613DD291D049743CF30A684EE3B94EA074DEAA`.
- Root `.env.example`:
  `24A7CFD857E6CB9245B37EC8589D24499726321E9BF1952E609A8231CC6B67F6`.

Only `.env.example` variable names were inspected: database URL, four
provider families, backend host/port, CORS, and LangChain tracing settings.
No real `.env` file was read.

## Frozen Iteration 3 contract

The machine-readable source is
`ez_back_dev/tests/fixtures/iteration3_contract_baseline_v1.json`. It is a
manual review snapshot, not a self-updating golden file.

- Exactly 19 workflows, including their phase, prerequisites, artifact and
  cache identities, corpus, prompt version, selection fields, persistence,
  regeneration capability, and current token budget profile.
- All public routes, the REST `status/reason/data` envelope, and the current
  REST/SSE wire event names are frozen. The legacy `reasoning_delta` name is
  preserved as a compatibility fact; it is not authorization for a future
  Agent to emit chain-of-thought.
- Artifact identity remains project, artifact key, input hash, source
  revision, and model label. Delayed persistence, exact cache, stale
  detection, failed-regeneration rollback, cancellation, and regeneration
  locking remain protected.
- RAG index identity remains project, corpus, source revision, and embedding
  identity. Capacity remains 16 and idle TTL remains 1,800 seconds. Design,
  requirements, and knowledge retrieval policies remain top-k 4, fetch-k 8,
  6,000 context tokens, and minimum score 0.20.
- All preliminary analysis remains persisted.
- `unit_case`, `integration_case`, `api_case`, `functional_case`, and
  `nonfunctional_case` remain session-only.
- `ui_case`, `db_case`, and `acceptance_case` remain persisted.

## Pre-change verification evidence

The focused Iteration 3 gate was run with dotenv disabled, an in-memory SQLite
URL, empty provider key environment variables, and the existing test doubles.
It included workflow catalog, API/frontend contracts, cost baseline,
resume/cancel, revision, artifact DAO, RAG, budget, workflow status, Iteration
3 closeout, and credential scan tests.

Result: `180 passed in 5.13s`; process wall time 6.74 seconds. No provider,
embedding service, external network, MySQL, or real project was accessed.

The existing detailed safe cost/token matrices remain in
`docs/iteration-2-token-baseline.md` and are enforced by
`test_workflow_cost_baseline.py`. Aspect 1 does not duplicate raw prompts,
generated content, or project documents into its reports.

## Baseline interpretation

This is the Iteration 3 deterministic workflow baseline. Agent task success,
trajectory, approval, recovery, and OpenTelemetry overhead are not historical
Iteration 3 measurements. Aspect 1 defines their future protocol and uses a
reference model plus deterministic fake data; unavailable runtime metrics are
reported as N/A rather than inferred.
