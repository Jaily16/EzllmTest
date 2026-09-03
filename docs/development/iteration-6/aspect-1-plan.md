# Aspect 1 Implementation Plan

> Temporary development record. Remove this file before the Aspect 7 final GitHub `main` consolidation.

## Goal

[Approved] Copy the exact execution-time GitHub `main` commit to an immutable archive ref, create the Iteration 6 development branch from the same commit, attach that branch to the existing empty V6 directory, and publish a docs-only baseline commit without changing V2 worktree paths or GitHub `main`.

## Immutable inputs and outputs

[Approved] The first valid execution-time `git ls-remote origin refs/heads/main` result is the only source SHA. The takeover value `5cf1effb32a8efcd34902df05d27442f3586dc1c` is a drift gate, not a substitute for the live query.

[Approved] The archive output is `refs/heads/codex/iteration5-main-archive`, which must resolve to the source SHA and therefore the same complete tree.

[Approved] The development output is `refs/heads/codex/iteration6`, created at the source SHA and then advanced by exactly one commit containing only the four Aspect 1 process documents.

[Approved] The worktree output path is exactly `D:\codex\EzllmTest_v6`. No alternate or additional top-level directory is permitted.

## Preflight gates

[Proposed] Before the first mutation, perform these checks in one PowerShell 7 session and stop on any failure:

1. Resolve V2 and V6 literally; require V6 to exist, be empty, be a normal directory, and not be a reparse point or registered worktree.
2. Require V2 branch `codex/iteration5-source-preview` at `68754c74bcd4c28ed42323883fb6f0813e56a9e2`.
3. Require origin fetch and push URLs to equal `https://github.com/Jaily16/EzllmTest.git`.
4. Capture complete V2 porcelain-v2 status, including tracked, untracked, and ignored paths, in memory only.
5. Require an empty V2 index, the known tracked modification, the known non-protected untracked set, and the existence-only protected categories.
6. Query exact local and remote archive, iteration6, and same-name tag refs.
7. Stop if iteration6 exists locally or remotely, a same-name tag exists, the archive points elsewhere, the branch is occupied, or stale worktree metadata conflicts.
8. Stop for merge/rebase/cherry-pick/revert state, relevant Git locks, custom hooks, commit signing, sparse checkout, submodules/gitlinks, or checkout filters.
9. Require configured Git author identity without changing configuration.

## Exact mutation sequence

[Approved] Fetch only remote main and no tags:

```powershell
git -C 'D:\codex\EzllmTest_v2' fetch `
    --no-tags `
    --no-write-fetch-head `
    --no-recurse-submodules `
    origin `
    refs/heads/main:refs/remotes/origin/main
```

[Proposed] Verify that `refs/remotes/origin/main` equals the live SHA, the object type is `commit`, `SHA^{tree}` resolves, no reachable object is missing, no gitlink exists, no checkout filter exists, tags are unchanged, and live main has not moved.

[Approved] Create the remote archive with a normal, non-force push only when it is missing:

```powershell
git -C 'D:\codex\EzllmTest_v2' push --porcelain origin `
    '<snapshot-sha>:refs/heads/codex/iteration5-main-archive'
```

[Proposed] Immediately prove with `git ls-remote` that the archive equals the snapshot SHA and main remains unchanged. Once verified, the remote archive is retained through every later failure.

[Approved] Recheck V2 status, V6 emptiness, iteration6 ref absence, and worktree ownership; then create the branch and worktree without force or branch reset:

```powershell
git -C 'D:\codex\EzllmTest_v2' worktree add `
    --no-track `
    -b codex/iteration6 `
    -- `
    'D:\codex\EzllmTest_v6' `
    '<snapshot-sha>'
```

[Proposed] Require the fresh V6 HEAD and tree to match the source snapshot, the branch to be `codex/iteration6`, the worktree to be clean and correctly registered, and V2 status to remain byte-for-byte identical to its in-memory status snapshot.

## Baseline-document commit

[Approved] Re-land, rather than copy from V2, exactly these files:

- `docs/development/iteration-6/overview.md`
- `docs/development/iteration-6/prompts.md`
- `docs/development/iteration-6/aspect-1-plan.md`
- `docs/development/iteration-6/aspect-1-baseline.md`

[Proposed] Record only source-control facts, protected-category summaries, local tool versions, no-cost execution, and the boundary for later authorization. Never record real `.env` values or user-data content, hashes, sizes, or protected subpaths.

[Approved] Stage only the four files, run `git diff --cached --check`, and require no unstaged or extra untracked changes:

```powershell
git -C 'D:\codex\EzllmTest_v6' add -- `
    docs/development/iteration-6/overview.md `
    docs/development/iteration-6/prompts.md `
    docs/development/iteration-6/aspect-1-plan.md `
    docs/development/iteration-6/aspect-1-baseline.md

git -C 'D:\codex\EzllmTest_v6' diff --cached --check
git -C 'D:\codex\EzllmTest_v6' commit `
    -m 'docs: establish iteration 6 immutable baseline'
```

[Proposed] Verify that the new commit is a direct child of the source snapshot and that its changed-path set is exactly the four documents.

[Approved] Recheck that the remote iteration6 ref is absent, then publish with a normal push:

```powershell
git -C 'D:\codex\EzllmTest_v6' push `
    --set-upstream `
    origin `
    refs/heads/codex/iteration6:refs/heads/codex/iteration6
```

## Final gates

[Proposed] Aspect 1 completes only when all of these remain true:

- Remote main equals the execution-time source SHA.
- Remote archive equals the source SHA.
- Local and remote iteration6 equal the docs-only baseline commit.
- The baseline commit parent equals the source SHA and its path set is exactly the four documents.
- V6 is the registered `codex/iteration6` worktree and is clean.
- V2 complete Git-visible status is identical to the pre-mutation in-memory snapshot.
- Local tags are unchanged and no same-name tags were created.
- No test, build, formatter, service, Docker, WSL, database, Redis, provider, or embedding command ran.

## Failure and rollback boundary

[Approved] Never delete, move, overwrite, or force-push a verified remote archive. Never reset or clean V2, and never roll back fetched objects or `origin/main`.

[Approved] No remote ref is deleted during rollback. Once remote iteration6 exists, later failure is reported as partial completion without remote cleanup.

[Proposed] Before remote iteration6 publication, a local rollback is allowed only when path, common-repository ownership, branch ref, expected HEAD, and changed paths all prove that the worktree and branch were created solely by this run. Remove the worktree with Git and delete the branch with an expected-old `update-ref`; otherwise preserve the scene and report the failed gate.

[Approved] Prohibited commands include `pull`, `reset --hard`, `checkout --`, `clean -fdx`, force-push, branch overwrite, recursive repository-root deletion, and cross-shell path transfer.

## Completion boundary

[Approved] Aspect 1 completion establishes only the historical snapshot, archive ref, V6 branch/worktree, and immutable source baseline. It does not migrate code, authorize Aspect 2 through Aspect 7, or complete Iteration 6.
