# Iteration 6 Development Log

> Temporary development record. Remove this file before the Aspect 7 final
> GitHub `main` consolidation.

## Aspect 2 — Historical validation evidence consolidation

- Execution date: 2026-09-03 (Asia/Shanghai)
- Authorized scope: Aspect 2 only
- Status: documentation and pre-commit static gates complete; commit, push,
  and post-push gates are necessarily reported after this self-contained
  commit.

### Immutable baseline and preflight

[Verified] V6 resolved to `D:\codex\EzllmTest_v6`, branch
`codex/iteration6`, clean HEAD
`b34a188ac1b5c98e869837009561f47363336821`, with direct parent
`5cf1effb32a8efcd34902df05d27442f3586dc1c` and upstream
`origin/codex/iteration6`.

[Verified] Read-only remote checks found `main` and
`codex/iteration5-main-archive` at `5cf1effb32a8efcd34902df05d27442f3586dc1c`,
and remote `codex/iteration6` at the Aspect 1 commit before Aspect 2.

[Verified] V6 was a registered ordinary worktree with no dirty or staged
paths, active Git operation, relevant lock, custom hook path, active lifecycle
hook, or forced commit-signing policy. Git identity was configured. The three
new Aspect 2 paths were absent and the two shared Iteration 6 process documents
were unchanged.

[Protected] A V2 Git-visible status snapshot was retained without printing
protected paths. No V2 file, environment value, upload, user persistence,
observability content, artifact, archive, quarantine item, or user log was read
or hashed.

### Evidence inventory and classification

[Verified] The implementation accepted exactly 22 tracked ordinary files:
canonical Iteration 4 documents, frozen Iteration 4 fixtures/manifests,
Iteration 5 tracked closeout records and baseline, and the fixed benchmark
CLI/runner/contracts. Every source was assigned a Git blob OID and
`sha256_canonical_lf_v1` hash in `docs/validation-history.md`.

[Verified] The root `docs/iteration-4-*.md` files were confirmed to be redirect
stubs. Only `docs/history/iteration-4/` was treated as canonical document
content.

[Verified] The Acceptance dataset hash boundary was preserved explicitly:
the historical raw/canonical-LF hash is
`44d8cad27aa17365a6aa85300a2a7261275438ae162d3da316371b0eff4e1674`,
while the current sorted-key canonical-JSON inventory hash is
`6b6e6c8205c8fe2c2a44777e087ca555fc4872a71d32b9d2a55bbb17dfc60e74`.
No false drift or hash substitution was claimed.

[Verified] Frozen structured facts are class A; canonical tracked narratives
corroborated by frozen evidence are class B; Iteration 5 values backed only by
repository-external reports are class C (`[Candidate]`); blocked, unavailable,
or unproven claims remain `[Missing]`; intentionally excluded data remains
`[Protected]`.

### Documentation result

[Verified] `docs/validation-history.md` now consolidates:

- the fixed seed, warm-up/sample matrix, percentile rule, environment, command
  families, thresholds, and same-machine comparability rule;
- Eval `104/104`, Acceptance `18/18`, safety and warm-cache zero counters;
- Aspect 7 and 8 performance samples, full Vue CLI/Vite size evidence, later
  Iteration 4 samples, and lower-confidence Iteration 5 samples;
- the bounded real-model planner/RAG and isolated synthetic Agent E2E evidence;
- browser, OpenTelemetry, Prometheus, Tempo, Grafana, Compose, and hosted-CI
  history with its original time and evidence boundaries;
- Docker/parity/report limitations, production-load unknowns, and protected
  data exclusions.

[Approved] The durable history is kept by default. This log, the Aspect 2 plan,
the overview, and the prompt register are temporary process records and must be
removed before Aspect 7 finalizes GitHub `main`.

### Static and Git gates

[Verified] The pre-commit implementation gate produced the following results:

- direct JSON assertions passed for the frozen numerical values;
- all 22 source blob/hash pairs matched the inventory;
- all 22 local Markdown links resolved to tracked files inside V6;
- target-only scanning found no credentials, connection URLs, raw tracebacks,
  repository-external report paths, or user content;
- `git diff --check` passed and the ordinary change set contained exactly the
  five approved Markdown files;
- the pre-stage V2 Git-visible status snapshot matched the initial snapshot.

[Verified] Importing the existing canonical-hash helper created one ignored
Python bytecode file under `scripts/__pycache__`. A path-verified PowerShell
removal was blocked by the execution safety layer and `apply_patch` cannot
decode binary bytecode, so no broader deletion mechanism was used. The file is
ignored, absent from the ordinary change set, and must not enter staging or the
commit.

The resulting commit SHA cannot be embedded in the commit that creates this
log without becoming self-referential. It is therefore reported by the final
local/remote verification and the completion response.

### Execution boundaries

[Verified] Aspect 2 did not run pytest, Eval, Acceptance, Benchmark, frontend
build, npm, services, Docker, WSL, MySQL, Redis, a provider, or embedding. It
did not install or modify an environment and produced no paid call.

[Verified] No product source, public API, 19-workflow catalog, 22-tool registry,
REST/SSE/MCP contract, persistence behavior, security behavior, or runtime
configuration was modified.

[Approved] Work stops after the Aspect 2 commit and remote verification.
Aspect 3 through Aspect 7 remain unauthorized and unstarted.
