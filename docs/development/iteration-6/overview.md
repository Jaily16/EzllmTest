# Iteration 6 Development Overview

> Temporary development record. Remove this file before the Aspect 7 final GitHub `main` consolidation.

## Status

[Verified] Iteration 6 has an immutable source snapshot, a dedicated development worktree, and a consolidated historical validation record.

[Verified] Aspect 1 established the immutable Git/worktree baseline. Aspect 2 consolidated the Iteration 4 and 5 validation evidence without rerunning historical gates.

[Approved] Aspect 3 through Aspect 7 are neither authorized nor started here.

[Protected] The existing V2 tracked, untracked, ignored, environment, upload, archive, artifact, quarantine, database, Redis, observability, and log assets remain outside V6 and must not be copied or cleaned.

## Global constraints

[Approved] Local development uses the existing Conda, Node, MySQL, and Redis installations only.

[Approved] No new top-level directory may be created under `D:\codex`; the V6 worktree path is exactly `D:\codex\EzllmTest_v6`.

[Approved] Docker Desktop, Docker, Compose, containers, and WSL are excluded from Iteration 6 execution.

[Approved] Real `.env` values, uploaded projects, provider credentials, database content, Redis content, observability data, artifacts, quarantine data, and user logs must not be read into development records.

## Aspect dependency boundary

1. Aspect 1 — GitHub main historical snapshot, V6 worktree, and immutable baseline
2. Aspect 2 — Validation-history consolidation
3. Aspect 3 — Pure product-source migration
4. Aspect 4 — Directory and runtime-configuration convergence
5. Aspect 5 — Local Chinese observability backend and UI
6. Aspect 6 — Chinese functional comments
7. Aspect 7 — GitHub main finalization

[Approved] The dependency order is `Aspect 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7`. The presence of this list does not authorize or plan Aspect 2 through Aspect 7.

## Lifecycle

[Approved] This overview, the prompt register, the Aspect 1 plan and baseline, the Aspect 2 plan, and the Iteration 6 development log are development-process documents. They must be removed before Aspect 7 finalizes GitHub `main`.

[Approved] `docs/validation-history.md` is durable product/repository documentation and is retained by default during the Aspect 7 final consolidation.
