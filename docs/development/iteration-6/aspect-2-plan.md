# Aspect 2 Historical Validation Evidence Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

> Temporary development record. Remove this file before the Aspect 7 final
> GitHub `main` consolidation.

**Goal:** Consolidate the Iteration 4 and 5 validation history into one
standalone, auditable Markdown document without rerunning any historical gate.

**Architecture:** Treat tracked frozen fixtures as primary evidence, canonical
tracked narratives as corroboration, repository-external report references as
lower-confidence recorded assertions, and blocked or unavailable evidence as
explicitly missing. Every cited source receives a repository path, Git blob
OID, and `sha256_canonical_lf_v1` value.

**Tech Stack:** Markdown, Git read-only plumbing, PowerShell 7, and the existing
Python 3.11.15 canonical-hash helper.

## Global constraints

- [Approved] Work only in `D:\codex\EzllmTest_v6` on `codex/iteration6`.
- [Approved] Do not fetch, pull, force-push, reset, checkout, clean, amend, or
  rewrite `main` or the archive ref.
- [Protected] Do not inspect or hash real environment files, uploads, user
  MySQL/Redis/observability data, archives, artifacts, quarantine data, logs,
  traces, or repository-external reports.
- [Approved] Do not run tests, Eval, Acceptance, Benchmark, builds, services,
  Docker, WSL, databases, Redis, providers, or embedding.
- [Approved] Do not change product source, public APIs, 19 workflows, 22 tools,
  REST/SSE/MCP, persistence, security, or runtime configuration.
- [Approved] Stop after Aspect 2; do not plan or start Aspect 3 through 7.

---

### Task 1: Lock the immutable Git and worktree baseline

**Files:** None.

**Interfaces:**

- Consumes: Aspect 1 commit
  `b34a188ac1b5c98e869837009561f47363336821` and source snapshot
  `5cf1effb32a8efcd34902df05d27442f3586dc1c`.
- Produces: A read-only go/no-go decision and an in-memory V2 Git-visible status
  snapshot.

- [x] Verify V6 path, branch, HEAD, parent, upstream, worktree registration,
  clean status, Git identity, hooks, signing policy, operation metadata, and
  locks.
- [x] Verify with `git ls-remote` that `main` and
  `codex/iteration5-main-archive` remain at the source snapshot and
  `codex/iteration6` remains at the Aspect 1 commit.
- [x] Verify the three new target files are absent and the two shared process
  documents are unchanged.
- [x] Capture V2 Git-visible status without emitting protected paths.

### Task 2: Build the explicit evidence inventory

**Files:** Read-only canonical Iteration 4/5 documents, structured fixtures,
manifests, and benchmark sources listed in `docs/validation-history.md`.

**Interfaces:**

- Consumes: Exactly 22 tracked, ordinary-file source paths.
- Produces: Source IDs S01–S22 with Git blob OIDs and
  `sha256_canonical_lf_v1` hashes.

- [x] Reject missing, untracked, symlink, reparse-point, or directory inputs.
- [x] Compute hashes only through the explicit allowlist; do not invoke a
  whole-repository inventory scan.
- [x] Distinguish the Acceptance dataset's historical raw/LF hash `44d8…` from
  its current canonical-JSON inventory hash `6b6e…`.
- [x] Extract the structured fixture facts and retain the original measurement
  stages rather than selecting one favorable run.

### Task 3: Write the durable validation history

**Files:**

- Create: `docs/validation-history.md`

**Interfaces:**

- Consumes: S01–S22 and the A/B/C/D/P evidence classification.
- Produces: A standalone human-readable audit history.

- [x] Record evidence semantics, source inventory, methodology, commands,
  historical environment, sampling, thresholds, results, and comparability.
- [x] Separate deterministic Eval/Acceptance, synthetic benchmark, frontend
  size, real-model synthetic quality, real-model synthetic E2E, and
  container/observability evidence.
- [x] Preserve `104/104`, `18/18`, the Aspect 7 and 8 ratios, all frozen bundle
  metrics, later narrative samples, and Iteration 5 recorded values with their
  correct evidence class.
- [x] State all Docker/parity/CI/report limitations and the absence of a
  production stress or capacity baseline.
- [x] Include no protected values, external report paths, raw logs, traces,
  model bodies, credentials, or user content.

### Task 4: Update temporary Iteration 6 process records

**Files:**

- Create: `docs/development/iteration-6/aspect-2-plan.md`
- Create: `docs/development/iteration-6/development-log.md`
- Modify: `docs/development/iteration-6/overview.md`
- Modify: `docs/development/iteration-6/prompts.md`

**Interfaces:**

- Consumes: The approved Aspect 2 scope and implementation facts.
- Produces: A temporary plan, execution record, and stop boundary.

- [x] Record that Aspect 1–2 are complete and Aspect 3–7 remain unauthorized
  and unstarted.
- [x] State that all Iteration 6 process records are removed before the Aspect 7
  final `main` consolidation; keep `docs/validation-history.md` by default.
- [x] Avoid a self-referential commit hash; report the resulting commit after
  it is created.

### Task 5: Static verification, commit, and normal push

**Files:** The exact five-document allowlist only.

**Interfaces:**

- Consumes: The completed documentation set.
- Produces: One docs-only commit and a matching remote
  `codex/iteration6` ref.

- [x] Validate every structured value with direct JSON assertions.
- [x] Recompute every source blob/hash and require it to match the inventory.
- [x] Resolve every local Markdown link inside the V6 worktree and reject
  protected-value patterns in the five target documents.
- [x] Require `git diff --check`, an exact pre-stage change allowlist, and no
  extra ordinary untracked changes.
- [ ] Require an exact staged allowlist, no unstaged or untracked extras,
  and a commit directly descending from the Aspect 1 commit.
- [ ] Commit once with `docs: consolidate validation history`.
- [ ] Before and after a normal fast-forward push, verify all three remote refs;
  do not force, delete, or roll back remote refs.
- [ ] Verify V6 clean and V2 Git-visible status unchanged, then stop.

## Failure and rollback boundary

[Approved] A failed pre-commit gate leaves the exact documentation changes in
place for diagnosis; it does not trigger clean, reset, checkout, or deletion.
A successful local commit is retained if push fails. A successful remote push
is never force-moved or deleted. Any concurrent user change stops execution and
is not overwritten.

## Completion definition

[Approved] Aspect 2 is complete only when the standalone history is traceable,
all static gates pass, the sole new commit changes exactly the five approved
documents, local and remote iteration6 match, V6 is clean, and V2 is unchanged.
This does not complete code migration, container delivery, production
readiness, Aspect 3–7, or Iteration 6.
