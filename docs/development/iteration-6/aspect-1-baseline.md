# Aspect 1 Immutable Baseline

> Temporary development record. Remove this file before the Aspect 7 final GitHub `main` consolidation.

## Execution identity

- [Verified] Execution timestamp: `2026-09-03T20:55:23+08:00`
- [Verified] Time zone: `Asia/Shanghai`
- [Verified] Repository: `https://github.com/Jaily16/EzllmTest.git`
- [Verified] Git implementation: `git version 2.55.0.windows.3`
- [Verified] PowerShell implementation: `7.6.4`

## Immutable source snapshot

- [Verified] Live execution-time `refs/heads/main`: `5cf1effb32a8efcd34902df05d27442f3586dc1c`
- [Verified] Takeover reference SHA: `5cf1effb32a8efcd34902df05d27442f3586dc1c`
- [Verified] Drift result: no drift
- [Verified] Commit object type: `commit`
- [Verified] Complete tree SHA: `a95eab1e7563cd6af2ae284a1c7f16da9b80594c`
- [Verified] Reachable-object check: no missing object
- [Verified] Checkout-boundary check: no gitlink, sparse checkout, or checkout filter

## Branch and worktree refs

- [Verified] Remote archive ref: `refs/heads/codex/iteration5-main-archive`
- [Verified] Remote archive SHA: `5cf1effb32a8efcd34902df05d27442f3586dc1c`
- [Verified] Remote archive tree: `a95eab1e7563cd6af2ae284a1c7f16da9b80594c`
- [Verified] Development ref: `refs/heads/codex/iteration6`
- [Verified] Development branch creation point: `5cf1effb32a8efcd34902df05d27442f3586dc1c`
- [Verified] Development worktree: `D:\codex\EzllmTest_v6`
- [Verified] Common repository owner: `D:\codex\EzllmTest_v2\.git`
- [Approved] The development ref is published at the commit containing this baseline; that commit must have the snapshot SHA as its direct parent and is independently verifiable with `git ls-remote`.

## V2 protection snapshot

- [Protected] V2 path: `D:\codex\EzllmTest_v2`
- [Verified] V2 branch: `codex/iteration5-source-preview`
- [Verified] V2 HEAD: `68754c74bcd4c28ed42323883fb6f0813e56a9e2`
- [Verified] V2 staged paths: none
- [Protected] Existing tracked modification: `docs/development/README.md`
- [Protected] Existing ordinary untracked development documents were retained in place and were not copied.
- [Protected] Real environment files, uploaded projects, `_archive`, `artifacts`, quarantine, database/Redis/observability data, and user logs are protected categories. No value, content, hash, size, or protected subpath is recorded here.
- [Approved] Aspect 1 completion requires the complete V2 Git-visible status captured before mutation to equal the final status exactly.

## Local tool baseline

- [Verified] Conda environment: `D:\tool\anaconda3\envs\ezllmtest`
- [Verified] Python: `3.11.15`
- [Verified] Node.js: `v24.18.0`
- [Verified] npm: `11.16.0`

## Execution exclusions

[Verified] No test, build, formatter, application service, Docker, Compose, WSL, MySQL, Redis, provider, or embedding workload was run while establishing this baseline, and no provider or embedding cost was incurred.

## Subsequent entry

[Approved] The only subsequent dependency entry is a separately authorized Aspect 2 prompt. This baseline does not plan or start Aspect 2 through Aspect 7.

## Lifecycle

[Approved] This baseline and the other Iteration 6 development-process documents must be removed before Aspect 7 finalizes GitHub `main`.
