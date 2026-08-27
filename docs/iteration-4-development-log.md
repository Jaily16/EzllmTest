# Iteration 4 Development Log

## Aspect 1 — Agent capability baseline, architecture contract, and measurement protocol

Date: 2026-08-27

Status: implementation complete; final verification recorded below

Stop point: Aspect 1 only; Aspect 2 has not been planned or implemented

### Scope delivered

- Added a machine-readable freeze of the 19-workflow Iteration 3 catalog,
  public route set, REST/SSE names, artifact/revision identity, RAG policy,
  reliability behavior, retention classification, and package manifest
  hashes.
- Added the accepted Python 3.11/FastAPI/LangGraph single-Agent ADR. No Agent
  runtime was installed or enabled.
- Added strict, frozen Pydantic reference contracts for typed catalog tools,
  trusted project scope, risk approval, budgets, usage, run state, transitions,
  errors, attempts, and approval binding.
- Added a pure state transition model covering planning, approval, execution,
  validation, completion, cancellation, failure, stale invalidation, and
  idempotency-first recovery.
- Added pure measurement helpers for nearest-rank p50/p95, TTFE, throughput,
  relative gates, and unavailable OpenTelemetry reporting.
- Added dataset v1 with 17 offline synthetic scenarios across two isolated
  fictitious projects and a deterministic fake-provider contract.
- Added static compatibility evidence for LangGraph, the Redis checkpointer,
  Redis capabilities, MCP v2, and OpenTelemetry.

No route, REST/SSE format, SQL, workflow catalog entry, workflow service,
provider, RAG implementation, frontend source, requirements file, package
manifest, Compose file, or CI configuration was changed.

### Protected starting state

- Branch: `main`.
- HEAD and local `origin/main`:
  `3c49e864a523a4af4c0f3efd4f845e8ce7b1caed`; ahead/behind `0/0`.
- Existing user-owned dirty state remained:
  - modified `README.md`;
  - untracked `docs/iteration-4-overview.md`;
  - untracked `docs/iteration-4-prompts.md`.
- Starting and final hashes of all three user assets are identical to the
  values in `iteration-4-aspect-1-baseline.md`.
- No fetch, pull, stage, commit, or push was performed.

### Test-first evidence

1. Existing pre-change focused Iteration 3 gate:
   `180 passed in 5.13s` (process wall time 6.74 seconds).
2. Baseline freeze test was added first and failed with three missing-fixture
   errors; after the reviewed snapshot was added: `3 passed`.
3. Contract/state/measurement tests were added before their modules and failed
   collection because `agentContracts` and `agentMeasurement` did not exist.
   After the minimal pure modules and dataset were added, their focused gate
   passed.
4. Documentation contracts initially identified two line-wrapped required
   decisions. The documents were made explicit without weakening the tests.
5. Final Aspect 1-only test group before the final repository gate:
   `36 passed in 2.34s`.
6. Combined Aspect 1 plus protected Iteration 3 focused gate:
   `218 passed in 6.04s` (process wall time 7.78 seconds).
7. Full backend suite before the final documentation write:
   `403 passed in 9.34s` (process wall time 11.05 seconds).

All backend commands used the existing Python 3.11 environment, disabled
dotenv loading, used an in-memory SQLite URL, and set provider key variables to
empty strings. No provider client, embedding service, MySQL instance, real
project, or external network was used.

### Frontend isolated verification

The frontend was exported from tracked `HEAD:ez_front_dev` into a unique
system temporary directory. The tracked `.env.example` was removed from the
temporary mirror by exact path without reading its contents. The mirror was
then verified to contain no `.env*` file and linked to the existing
`node_modules`. npm offline, audit-disabled, and fund-disabled settings were
used; no installation ran.

- `npm run lint`: passed, `No lint errors found`.
- `npm run build -- --dest <system-temp>/dist`: passed.
- Bundle checker: passed with `ok: true`, zero source maps, 47 files,
  1,541,945 total build bytes, 571,051 initial bytes, and 443,227 largest
  initial JavaScript bytes.
- The build emitted the current Node 24 `fs.Stats` deprecation warnings and the
  existing Vue CLI asset/entrypoint size warnings. They are recorded as
  warnings rather than hidden or described as zero-warning output.
- The temporary `node_modules` junction was removed before the verified temp
  root was recursively deleted. The repository `dist` was not written.

The first isolation attempt stopped before npm execution because the tracked
`.env.example` name was present. It cleaned its temporary root, then the final
run excluded that exact file and passed. No real `.env` was read in either run.

### Security and generated-output gates

- The first credential scan reported two redacted findings in synthetic
  redaction-test literals. The test inputs were changed to assemble the same
  synthetic values at runtime; the scanner was not relaxed.
- Final credential scan result before final suite:
  `Credential scan clean: tracked=216, staged=0, untracked=15`.
- `git diff --check`: no whitespace errors. It repeated the pre-existing
  README LF-to-CRLF warning; README was not touched.
- Protected production-file diff: none.
- Forbidden generated database, Redis dump, trace, and coverage files: none.
- The manifest hashes remained:
  - requirements:
    `131F71733433D2806083756DFB2B5E315B66A678E304EBA6EB3E82FF0F4C7FEF`;
  - package.json:
    `769EC529E786375A8DCDB5FCE27C1A4A44D5DDEDC3B9946E2850DEA8477BD5C3`;
  - package-lock.json:
    `C93CDE311DB8675A62A781E20F613DD291D049743CF30A684EE3B94EA074DEAA`.

### Measurement interpretation

- Dataset: schema 1, version 1.0.0, seed 20260827, 17 synthetic cases.
- The p50=15 ms, p95=29 ms, TTFE p50=7.5 ms, and throughput=500 tasks/s
  assertions in the unit test are fixed logical-clock test vectors for the
  metric formulas. They are not claims about application performance.
- Current Agent task/trajectory/runtime latency measurements are unavailable
  because no Agent runtime exists in Aspect 1.
- OpenTelemetry overhead is N/A with reason `runtime_not_installed`.
- No performance improvement is claimed. Future performance gates use the
  recorded protocol's reproducible relative comparisons.

### Compatibility spike result

- LangGraph 1.2.11 is nominally compatible with the current Python,
  langchain-core, and Pydantic constraints.
- The Redis checkpointer's checkpoint, Redis client, RedisVL, RedisJSON, and
  RediSearch requirements were recorded but not installed.
- MCP Python SDK 2.1.1/v2 Streamable HTTP constraints were recorded; no MCP
  listener was created.
- OpenTelemetry remains protocol-only with installation deferred.

These are static compatibility conclusions, not resolver or integration-test
evidence. Dependency installation still requires explicit user approval.

### Final verification pass

After this development log was created, the backend suite was run again:
`403 passed in 9.17s` (process wall time 11.46 seconds). The credential scan
was clean with `tracked=216, staged=0, untracked=16`. `git diff --check`
reported no whitespace error and only repeated the protected README
LF-to-CRLF warning. Manifest and user-asset hashes still matched the captured
values. The final Git status contained the original three user assets plus
only the approved Aspect 1 files; nothing was staged.

### Stop condition

Aspect 1 is the only implemented Iteration 4 aspect. Work stops after the final
verification pass. No Aspect 2 tool registry/runtime implementation, Redis,
MCP, workbench, Compose, observability exporter, or CI work is started.

## Aspect 2 — Typed tool registry and MCP interoperability

Date: 2026-08-27

Status: implementation complete; final verification recorded below

Stop point: Aspect 2 only; Aspect 3 has not been implemented

### Protected starting state

- Branch remained `main`.
- HEAD and local `origin/main` remained
  `3c49e864a523a4af4c0f3efd4f845e8ce7b1caed`; ahead/behind remained `0/0`.
- The starting dirty set exactly matched the approved handoff: the modified
  user-owned `README.md`, two untracked Iteration 4 user documents, and all
  untracked Aspect 1 files.
- Starting manifest hashes matched Aspect 1:
  - requirements:
    `131F71733433D2806083756DFB2B5E315B66A678E304EBA6EB3E82FF0F4C7FEF`;
  - package.json:
    `769EC529E786375A8DCDB5FCE27C1A4A44D5DDEDC3B9946E2850DEA8477BD5C3`;
  - package-lock.json:
    `C93CDE311DB8675A62A781E20F613DD291D049743CF30A684EE3B94EA074DEAA`.
- No protected route, workflow catalog, SQL, frontend source, README,
  overview, or prompts file was modified.

### Dependency compatibility and installation evidence

Before the manifest changed, the five Aspect 1 tests passed with
`38 passed in 2.33s`, followed by the full backend baseline with
`403 passed in 10.73s`.

An isolated Python 3.11 virtual environment under the system temporary
directory installed the unchanged requirements plus exact `mcp==2.1.1`.
`pip check` reported `No broken requirements found`, and imports of the SDK
`Client` and low-level `Server` succeeded. No existing direct pin was relaxed
or downgraded.

The first installation attempt into the existing project environment was
blocked by Windows permissions before the package was installed. The approved
elevated retry installed exact `mcp==2.1.1` and its transitive requirements;
the subsequent `pip check` and runtime imports passed. No MCP CLI extra,
LangGraph, Redis, checkpoint, or OpenTelemetry SDK/exporter dependency was
added to the manifest.

The current requirements hash is
`D0203C1049B50F09FE00FAC5F42EDD962202E61B00EB885DD817914E74B7B380`.
The frontend hashes are unchanged. The original Iteration 3 fixture remains
unaltered historical evidence; `iteration4_aspect2_manifest_v1.json` records
the approved layered manifest state.

### Scope delivered

- Added strict Pydantic input models for every catalog operation, preserving
  the existing payload names and adding only `model_label` and `regenerate`.
  Project scope, approvals, idempotency records, credentials, prompts, raw
  documents, and reasoning are absent from model-visible schemas.
- Added one immutable registry containing three read-only project status tools
  followed by all 19 catalog-derived workflow tools. Risk, approval, budget,
  RAG, idempotency scope, cancellation, and retention metadata are explicit.
- Added a trusted-context executor and a thin internal Agent adapter. Status
  queries and workflow streams call the application services directly; no
  HTTP or MCP self-call exists.
- Workflow execution checks project scope, planned arguments, model label,
  risks, budget identity, and approval before invoking a service. It filters
  every `reasoning_delta`, normalizes monotonic progress, preserves existing
  persistence/cache/stale behavior, and propagates cancellation.
- Added an MCP v2 low-level server with identical registry JSON schemas,
  structured successful output, host-visible approval/scope failures, safe
  tool errors, two static resources, one static prompt, progress, and
  cancellation.
- Added a standalone Streamable HTTP app at `/mcp`. It is not mounted on the
  public FastAPI application, fixes the host to `127.0.0.1`, exposes no CLI
  host argument, and retains the SDK localhost Host/Origin protection.
- The default loopback context executes only the three read-only tools. The 19
  workflow tools are discoverable but require a trusted future host to inject
  an approved run context.
- No arbitrary file, Shell, network, SQL, dynamic Python, roots, sampling, or
  protocol-logging capability was added.

Aspect 2 does not claim a LangGraph runtime, Agent loop, Redis-backed durable
idempotency, checkpoint recovery, workbench UI, new public route, database
migration, observability pipeline, Compose service, or CI pipeline.

### Test-first evidence

1. Schema and registry tests were added first and failed collection because
   `agentToolSchemas` and `agentToolRegistry` did not exist. After the minimal
   implementation: `27 passed in 0.64s`.
2. Executor and internal-adapter tests were added first and failed collection
   because their modules did not exist. After implementation:
   `10 passed in 2.17s`.
3. MCP tests were added first and failed collection because `agentMcpAdapter`
   did not exist. After the low-level protocol adapter and loopback app were
   implemented: `8 passed in 2.98s`.
4. Manifest/documentation tests first reported the expected historical-hash,
   missing-fixture, and missing-document failures. The original fixture was
   retained, the layered fixture and contract document were added, and the
   combined gate passed with `9 passed in 2.76s`.
5. The combined Aspect 1/2 plus protected workflow/API/RAG/revision/artifact/
   resume/credential focused gate passed with `297 passed in 6.37s`.
6. The full backend suite passed with `454 passed in 9.97s`.

All tests disabled dotenv loading, supplied an in-memory SQLite URL, and
cleared provider credential variables. MCP protocol tests used the official
in-process `Client(server)` or ASGI test transport. They did not contact a
provider, embedding service, MySQL server, real project, or external endpoint.

### Frontend isolated verification

The tracked frontend was copied to a unique system temporary directory while
excluding `.env*` by filename without reading any such file. The mirror linked
the existing `node_modules`; npm ran offline with audit and fund disabled.

- `npm run lint`: passed with `No lint errors found`.
- `npm run build -- --dest <system-temp>/dist-output`: passed.
- Bundle checker: passed with `ok: true`, zero source maps, 47 files,
  1,541,945 total build bytes, 571,051 initial bytes, and 443,227 largest
  initial JavaScript bytes.
- The current Node 24 `fs.Stats` deprecation warnings and the existing Vue CLI
  asset/entrypoint size warnings remain and are not represented as clean
  warnings.
- The junction and exact validated temporary root were removed. The ignored
  repository `ez_front_dev/dist` predates this aspect (created 2026-08-19,
  last modified 2026-08-22) and was not touched.

### Security and repository gates

- Credential scan: clean with `tracked=216, staged=0, untracked=30`.
- `git diff --check`: exit 0. It repeated only the LF-to-CRLF warnings for the
  protected README and the intentionally changed requirements file.
- Current manifest hashes match `iteration4_aspect2_manifest_v1.json`.
- No new repository build, coverage, database, Redis dump, trace, or benchmark
  output was created.
- Final dirty state contains the original user assets, Aspect 1 files, the
  intentional requirements edit, and only the approved Aspect 2 files.
- No fetch, pull, stage, commit, or push was performed.

### Stop condition

Aspect 2 is complete. Work stops after its final verification pass. Aspect 3
LangGraph runtime, planning loop, execution worker, HITL lifecycle, Redis,
checkpoint recovery, workbench, observability, Compose, and CI work remain
unimplemented until separately approved.

## Aspect 3 — LangGraph runtime and durable execution

Date: 2026-08-27

Status: implementation complete; final verification recorded below

Stop point: Aspect 3 only; Aspect 4 has not been implemented

### Protected starting state

- Branch remained `main`; HEAD and local `origin/main` remained
  `3c49e864a523a4af4c0f3efd4f845e8ce7b1caed`; ahead/behind was `0/0`.
- The modified README, the two user-supplied Iteration 4 documents, and every
  Aspect 1/2 file were captured by path, size, and SHA-256 and treated as user
  assets. Their starting dirty set was not rewritten or normalized.
- Before the Aspect 3 dependency change, the Aspect 1/2 focused gate passed
  with `89 passed in 5.72s`, and the complete backend baseline passed with
  `454 passed in 11.48s`.
- The Aspect 2 requirements hash was
  `D0203C1049B50F09FE00FAC5F42EDD962202E61B00EB885DD817914E74B7B380`.
  The npm manifest hashes and all protected README/overview/prompts hashes
  matched their captured values.
- No fetch, pull, stage, commit, or push was performed.

### Checkpointer security decision and dependencies

The originally evaluated `langgraph-checkpoint-redis==0.5.2` remained blocked:
its Redis JSON serializer accepted an adversarial constructor-shaped value and
instantiated a non-allowlisted dataclass. Enabling strict msgpack did not close
that JSON path. The package and `redisvl` were therefore not added.

The approved replacement is an in-repository minimal async saver implemented
against LangGraph's public `BaseCheckpointSaver` and `SerializerProtocol`
interfaces. `StrictAgentCheckpointSerializer` emits
`ezllm-safe-json-v1`, has no pickle/msgpack-constructor/dynamic-import fallback,
and accepts only bounded plain values plus exact `Interrupt` and `Send` types.
Encoding and decoding both reject constructor envelopes, arbitrary dataclasses,
unknown objects, type confusion, non-finite numbers, and depth/size attacks.

The manifest added only:

- `langgraph==1.2.11`;
- `langgraph-checkpoint==4.2.0`;
- `redis==6.4.0`.

Installation into the existing Python 3.11 environment succeeded. The resolver
changed the environment's transitive `websockets` package from 17.0.1 to
16.1.1; no direct project pin was relaxed. `pip check` reported
`No broken requirements found`. The resulting requirements hash is
`54EB1002BA00AEE7F11546990EEF78EFB0A4AC52ED5F850AC1A119203E8969AD`.
`iteration4_aspect3_manifest_v1.json` layers this hash over the immutable
Aspect 2 fixture; npm manifests remain unchanged.

### Runtime delivered

- Added strict `AgentGraphEnvelope`, safe project observations, approval
  requests/resumes, a catalog-only deterministic/provider planner, and the
  fixed single-Agent LangGraph state graph.
- HITL uses `interrupt()` before the side-effect node. Approval hashes and a
  trusted one-time nonce bind project, revision, plan, arguments, risks,
  execution model, and budget. A nonce is atomically claimed by command ID
  before graph resume and finalized after the synchronous checkpoint; the same
  command may safely resume after a crash but a different command cannot reuse
  it.
- Added the custom Redis checkpointer with scope/graph/thread binding, safe
  checkpoint and pending-write serialization, per-thread timeline/registry,
  seven-day TTL, exact deletion, and no full-database key scan.
- Added one shared `owner:fence` lease for worker, checkpoint, idempotency,
  nonce, event, and budget writes. Defaults are a 30-second lease and 10-second
  renewal; a long-running-tool test proves renewal across the original lease
  TTL. Stream commands are at-least-once, duplicate IDs are harmless, and
  unacknowledged work is claimable after the configured idle interval.
- Added `reserved → started → completed | outcome_unknown` idempotency.
  Persisted work reconciles against the existing artifact identity after a
  crash. A session-only result that was not durably recorded becomes
  `outcome_unknown` and is never automatically repeated.
- Added cancellation before the next side effect, bounded monotonic event
  replay, project-scoped thread lookup, stale-observation invalidation, and
  retryable-failure reconciliation before another approval.
- Added an immutable, fenced Redis budget ledger for step, deadline, input and
  output Token, model, embedding, tool, and synthetic-cost limits. Agent-only
  `ContextVar` hooks reserve before provider/embedding/tool I/O; legacy paths
  have no context and remain no-ops. Missing usage keeps the conservative
  reservation.
- Added the internal Redis Stream worker and
  `python -m app.agentWorker --consumer <name> [--once]`. Its CLI exposes no
  host, Redis URL, project, scope, approval, arbitrary file, Shell, SQL, Python,
  or generic-network authority. It is not mounted on the FastAPI or MCP apps.
- Added Agent Redis variable names to `.env.example` without reading a real
  `.env`. No public route, REST/SSE event, SQL, workflow catalog, frontend
  source, artifact, revision, RAG, cache, stale, rollback, regeneration-lock,
  or retention behavior was changed.

### Real Redis and failure-injection evidence

Docker Desktop was started manually by the user. The test pulled exact
`redis:8.2.8-alpine` with digest
`sha256:a7859ed111db3c1f5404a973a4747505d559fb5ca32d37e447afc0ef845a2103`.
The unique container bound only `127.0.0.1:16379`, used no host volume, and ran
with RDB/AOF persistence disabled. `redis-cli ping` returned `PONG`.

- Safe serializer/checkpointer integration: `21 passed in 0.27s`.
- Lease, idempotency, cancellation, nonce, event, command, and budget focused
  gates passed against the real Redis instance.
- The graph completed a real Redis interrupt/checkpoint/resume round trip.
- Fault injection covered approval-to-tool restart, duplicate command and
  approval, lease expiry/renewal, cancellation, stale/replan contracts,
  persisted reconciliation, and session-only unknown outcomes.
- A spawned worker wrote one synthetic persisted artifact to a system-temporary
  SQLite store and then exited via `os._exit(23)` before recording idempotent
  completion. After the old lease expired, a second independent Python process
  resumed the same checkpoint, reconciled the artifact, completed the run, and
  left the side-effect count at exactly 1.
- Deleting the test Redis namespace made its thread unavailable while the
  isolated SQLite artifact remained present, demonstrating the Redis/MySQL
  responsibility boundary without contacting MySQL.

The exact test container was removed after verification. The fixed image may
remain in Docker's local image cache; no Redis data volume or repository dump
was created.

### Test and delivery gates

- Final Iteration 4 focused gate:
  `153 passed, 365 deselected in 16.17s`.
- Final complete backend suite: `518 passed in 23.44s`.
- `pip check`: passed with no broken requirements.
- Tracked-only system-temporary frontend mirror, existing `node_modules`, npm
  offline/audit/fund disabled:
  - `npm run lint`: passed with `No lint errors found`;
  - `npm run build -- --dest <validated-system-temp>`: passed;
  - bundle budget: passed, zero source maps, 47 files, 1,541,945 total bytes,
    571,051 initial bytes, 443,227 largest initial JavaScript bytes, and
    143,472-byte gzip size for that JavaScript file.
- Node emitted the existing `fs.Stats` deprecation warning; it is recorded as a
  warning and not reported as a clean build.
- Credential scan: clean with `tracked=216, staged=0, untracked=50`.
- `git diff --check`: exit 0; it emitted only LF-to-CRLF notices for existing or
  intentionally modified files, not whitespace errors.
- The isolated frontend directory was validated under the Windows system temp
  root and removed by exact literal path after the bundle check.
- No provider, embedding, MySQL, remote Redis, or real project was accessed;
  all planning/tool results were deterministic synthetic fakes. No model cost
  was incurred and no performance improvement is claimed.

### Final protected state and stop condition

The final branch/HEAD/origin and ahead/behind values match the starting state.
README, Iteration 4 overview/prompts, workflow catalog, public routes, SQL, and
npm manifests retain their captured hashes. The only tracked Aspect 3 changes
are `.env.example`, guarded provider/streaming budget hooks, and the approved
requirements additions; all other Aspect 3 implementation, tests, fixture, and
contract documentation are new files. No repository build, coverage, database,
Redis dump, trace, or benchmark output was added.

Aspect 3 is complete. Work stops here. Aspect 4 workbench/API work, public
wire-format changes, OpenTelemetry, Compose, performance optimization, and CI
remain unimplemented pending a separate instruction.

## Aspect 4 — Agent workbench and isolated control API

Date: 2026-08-27

Status: implementation complete; final verification recorded below

Stop point: Aspect 4 only; Aspect 5 has not been implemented

### Protected starting state

- Branch remained `main`; HEAD and local `origin/main` remained
  `3c49e864a523a4af4c0f3efd4f845e8ce7b1caed`; ahead/behind was `0/0`.
- Every dirty file from the user and Aspects 1–3 was captured by path, size and
  SHA-256 and treated as user-owned. README, overview and prompts retained the
  starting hashes `71ADFD...D8AFE`, `8E4FC...DC786` and
  `34653A...7C0D` respectively.
- Protected starting hashes matched the plan: requirements
  `54EB1002...E8969AD`, package `769EC529...7BD5C3`, lock
  `C93CDE31...74DEAA`, legacy main `DBEC0E64...3162E6`, routers
  `A3DDD017...FD30A1`, and workflow catalog `E9265C34...AAC6A`.
- Before Aspect 4 edits, the Aspect 1–3 focused baseline passed with
  `136 passed, 17 skipped in 3.99s`; the full backend baseline passed with
  `501 passed, 17 skipped in 11.40s`.
- No dependency was installed or changed. No fetch, pull, stage, commit or
  push was performed.

### Backend delivered

- Added strict public views for run summaries, plans, approvals, budgets,
  evidence and timeline events. Internal actor/scope hashes, approval binding
  and nonce, idempotency keys, checkpoint payloads, prompts, reasoning,
  credentials and tracebacks are excluded.
- Added server-derived `focused` and `standard` budget presets. Token limits
  are calculated from the current workflow catalog maxima; clients cannot
  submit numeric limits or expand a running budget. Cost remains explicitly
  labeled `synthetic_test_unit`.
- Added Redis workbench storage with one atomically reserved active thread per
  trusted project, seven-day run index/metadata/evidence retention, cursor
  listing without TTL renewal, safe 4 MiB evidence serialization, and bounded
  event replay. Progress is normalized, monotonically accepted per step/stage,
  deduplicated in five-percent buckets and never contains result-body deltas.
- Evidence is written after idempotent completion and reconstructed from a
  completed record without another tool call. Persisted evidence holds only
  artifact/revision/cache/save/usage summaries. Session evidence keeps the
  structured result in run-scoped Redis and never adds a MySQL save path.
- Extended cancellation at an approval interrupt through a trusted rejected
  resume; terminal cancellation is idempotent. Failed runs release the active
  slot, and recovery must reacquire it before enqueueing work.
- Added a continuously refreshed 30-second worker heartbeat, including during
  a long graph invocation, and a shared runtime factory used independently by
  the API and worker processes.
- Added the standalone `python -m app.agentApi --port 8131`. It always binds
  `127.0.0.1`, exposes no host/scope/actor authority, enforces loopback Host
  values and exact CORS origins, and is not mounted in `app.main`.
- Added all planned API controls plus resumable SSE with monotonic IDs,
  `Last-Event-ID`/`after_sequence`, retention-gap `replay_reset`, comment
  heartbeats and terminal close. Validation and unexpected errors use a
  redacted `{status, reason, data}` envelope. Agent SSE has no
  `reasoning_delta` or tool-result body.
- Health reports only Redis, worker, schema and graph states. Public snapshots
  truthfully return `trace_id=null` and `trace_status=not_instrumented`.

### Frontend delivered

- Added a lazy `/agent` child route and a separate project-ready guard without
  changing the ten legacy `requiresWorkflow` routes or `allowed_routes`.
- Added `VUE_APP_AGENT_API_BASE_URL`; the existing business API remains on
  8130. Loading the page performs only capabilities, list, snapshot and event
  reads. A POST create occurs only through the explicit “创建运行” button.
- Added the responsive workbench with goal/model/preset controls, structured
  plan and risks, HITL dialog, monotonic timeline, persisted/session evidence,
  budget and usage, history, worker/expiry diagnostics and truthful Aspect 7
  trace deferral. Local storage retains only the selected thread ID.
- Added an abortable SSE composable with six bounded connection attempts and
  sequence resume. Route teardown aborts the stream.
- Approval focus enters the primary action, Escape closes the dialog, and
  focus returns to the trigger. Atomic live status, alert errors, 44 px targets,
  reduced-motion and forced-color rules are present.
- Extended the existing loopback fixture with process-local deterministic
  active approval, persisted evidence, session evidence, failure/recovery,
  edit/reject/cancel, progress and SSE scenarios. Its initial counters prove
  page load performs zero model, embedding and tool calls.

### Real Redis, API and browser evidence

The existing exact `redis:8.2.8-alpine` image with digest
`sha256:a7859ed111db3c1f5404a973a4747505d559fb5ca32d37e447afc0ef845a2103`
ran in the unique `ezllm-aspect4-20260827` container. It used no host volume,
disabled RDB/AOF and bound only `127.0.0.1:16380`. Workbench store/service/API/
SSE tests used deterministic planner and tool fakes only.

- Workbench lifecycle regression including Aspect 3 recovery:
  `25 passed in 14.30s`.
- Final Aspect 4 contracts, API, SSE, frontend and Redis focused gate:
  `25 passed in 3.73s`.
- API assertions covered all routes, strict envelopes, redacted 422 errors,
  project isolation, 421 non-loopback Host rejection, exact CORS, no implicit
  execution, approval hash, event replay and retention gaps.
- In-app browser verification used the loopback fixture and final isolated
  bundle only. At 360×800, 768×1024, 1024×768, 1440×900 and 1920×1080 there
  was no horizontal overflow. The layout changed from one to two columns at
  1024 px. Visible buttons met 44 px minimum height.
- Browser interaction verified approval focus/return and Escape, approval to
  completed timeline/evidence, history selection and full session-only result
  restoration with the label `Agent thread · 7 天`. Browser console contained
  no error or warning.

### Frontend isolation incident and corrected gate

One preliminary build command created a system-temporary output directory but
failed to switch its working directory from the repository frontend to the
already-created mirror. Because Vue CLI can automatically load a local
frontend `.env`, that invocation did not satisfy the no-real-env gate. No env
content or resulting bundle content was printed, inspected or copied into the
repository. The exact temporary output and mirror were immediately validated
as system-temp paths and deleted.

The authoritative lint/build was then rerun in a fresh mirror that was checked
recursively to contain no `.env*` file before `node_modules` was linked. Only
this corrected result is accepted:

- isolated `npm run lint -- --no-fix`: passed, no lint errors;
- isolated `npm run build -- --dest <validated-system-temp>`: passed with the
  existing Vue CLI vendor/entrypoint warnings and Node `fs.Stats` deprecation;
- bundle checker: passed, zero source maps, 49 files, 1,585,388 total bytes,
  571,421 initial bytes, 443,227 largest initial JavaScript bytes and 143,472
  gzip bytes for that JavaScript file.

The corrected mirror, output directory, fixture logs and the three loopback
fixture processes were removed by exact validated paths/PIDs. The Redis test
container was stopped and auto-removed.

### Final regression and repository gates

- Complete backend suite against loopback Redis:
  `544 passed in 25.06s`.
- Credential scan: clean with `tracked=216, staged=0, untracked=67`.
- `git diff --check`: exit 0; output contained only LF-to-CRLF notices, not
  whitespace errors.
- Requirements and npm manifest hashes remain unchanged from Aspect 3. Legacy
  main, routers and workflow catalog retain their protected hashes. The new
  Aspect 4 manifest records the two intentionally changed example-env hashes.
- The Iteration 3 route snapshot remains exact. No SQL, workflow catalog,
  legacy REST/SSE, artifact, revision, RAG, cache, stale, rollback,
  regeneration-lock or legacy retention contract changed.
- No provider, embedding, MySQL, remote Redis, external socket or real project
  was accessed, and no model cost was incurred. No performance improvement is
  claimed.
- Existing ignored `.env`, cache directories and prior frontend `dist` were
  treated as pre-existing user state and were not deleted. No new repository
  build, database, Redis dump, trace, coverage or benchmark artifact was added.

### Stop condition

Aspect 4 is complete. Work stops here. Aspect 5–8 work is not planned or
implemented until separately requested.

## Aspect 5 — Context engineering, RAG evidence, and memory boundaries

Date: 2026-08-27

Status: implementation complete; final verification recorded below

Stop point: Aspect 5 only; Aspect 6–8 have not been implemented

### Protected starting state and pre-change gates

- Branch remained `main`; HEAD and local `origin/main` remained
  `3c49e864a523a4af4c0f3efd4f845e8ce7b1caed`; ahead/behind remained `0/0`.
- All 77 dirty files at entry were recorded by path, size, and SHA-256 and
  treated as user assets. Requirements, npm manifests, legacy FastAPI main and
  routers, workflow catalog, README, overview, prompts, and all Aspect 1–4
  inputs matched their expected hashes.
- One initial baseline command accidentally selected base Python and stopped
  during collection because project dependencies were unavailable. Nothing
  was installed and no code conclusion was drawn from that run. The command
  was corrected to use the existing Python 3.11 `ezllmtest` environment.
- Authoritative pre-change gates in that environment passed: Aspect 1–4 focus
  `179 passed, 365 deselected in 16.83s`; complete backend
  `544 passed in 24.07s`.
- No dependency or manifest was changed. No fetch, pull, stage, commit, or push
  was performed.

### Trusted context and memory boundary delivered

- Planner-visible schemas now remove all prerequisite artifact-body fields.
  Planner output containing one is rejected; runtime compilation strips legacy
  deterministic fixture bodies rather than placing them in a new checkpoint.
- Added strict metadata-only `ContextBinding` values for the source operation,
  artifact key, revision, input/prompt/model identity, extraction path, and
  content SHA-256. Context bindings participate in both plan and approval
  hashes, so artifact, revision, model, selection, parameter, or content change
  invalidates prior approval.
- The worker resolves current prerequisite artifacts from the trusted project
  scope before approval and hydrates the exact validated body only in memory,
  immediately before tool execution. Missing, stale, ambiguous, mismatched, or
  malformed prerequisites fail closed before a side effect.
- A pre-Aspect-5 plan with raw prerequisite body and no binding cannot execute;
  it must replan or cancel. The in-memory graph test proved the sentinel body
  reached the tool payload but did not appear in the paused or completed graph
  envelope.
- Persisted truth remains MySQL artifact/revision data. Redis checkpoint data is
  metadata only; session evidence remains thread-scoped for seven days. No chat
  history, user profile, cross-project memory, Agent conversation embedding, or
  summary memory was added.

### Agent-only retrieval and evidence delivered

- Added pure-Python Unicode NFKC BM25, deterministic RRF, and deterministic
  identifier/term-coverage rerank candidates. They use the same indexed chunks,
  top-k/fetch-k, minimum score, de-duplication, and 6,000 Token bound as the
  frozen dense path.
- The strategy context exists only inside a trusted Agent worker invocation.
  Legacy 8130 workflows still receive the original `BoundedRetriever`, and an
  exact artifact cache hit creates no RAG, model, or embedding work.
- Added strict retrieval evidence to tool results and workbench step evidence:
  policy/strategy, corpus, revision, query hash, build/reuse, context Tokens,
  and selected citation metadata. A citation contains only its local ID,
  sanitized basename, one-based page, rank, finite score/type, and scope-bound
  chunk hash. No excerpt or absolute path is returned.
- Prompt assembly prefixes selected chunks with `[C1]`-style markers only when
  metadata is present. Checkpoint, Redis event, API, MCP, and workbench values
  retain metadata only. Vue uses explicit TypeScript contracts and plain text
  interpolation; no `v-html` was added.
- Capabilities truthfully report `dense_v1`, policy
  `iteration4-aspect5-v1`, metadata-only citations, disabled rerank, and
  Agent-only scope. Public routes and the existing Agent SSE event set did not
  change.

### Synthetic RAG decision

- Added the fixed-seed `iteration4_rag_eval_v1.json` dataset: two similarly
  named isolated projects, requirements/design/knowledge corpora, small/large
  sources, Chinese/English identifiers, paraphrases, rare terms, distractors,
  and cross-project traps across 24 queries.
- Only deterministic token-hash fake dense scores were used. Dense, hybrid RRF,
  and rerank each produced overall nDCG@4 `1.000000`; maximum selected context
  was 85 deterministic tokens. Citation coverage was `1.000000`; invalid
  citations and project leaks were both `0`.
- Since hybrid improved nDCG@4 by `0.000000`, the required relative `0.05`
  quality gain was not met. Comparable cold/warm p95 is also `N/A` because this
  was not accepted as a controlled long-lived performance host. The versioned
  decision therefore keeps `dense_v1`; no performance improvement is claimed.
- The protocol freezes seed `20260827`, five warmups, thirty retained samples,
  concurrency 1/4, small/large and cold/warm modes. No provider, real
  embedding, MySQL, filesystem project, remote Redis, or external socket was
  accessed, and no fee was incurred.

### Tests, Redis, and frontend evidence

- Context/planner/graph/runtime/executor focus: `32 passed in 5.22s`.
- Retrieval/index/tool regression: `30 passed in 2.48s`.
- New Aspect 5 contract/dataset/measurement focus: `21 passed in 2.53s`.
- Iteration 4 focus after integration: `194 passed, 365 deselected in 17.04s`.
- After the first container cleanup, one verification command set
  `AGENT_REDIS_URL` to an empty string and stopped during collection because
  the Redis client correctly rejected the invalid URL. Removing the variable
  produced `539 passed, 27 skipped in 11.55s`; no integration result was
  inferred from the skipped Redis cases. The fixed-digest loopback container
  was then recreated and the authoritative final complete backend suite passed:
  `566 passed in 24.63s`.
- The fixed image was
  `redis:8.2.8-alpine@sha256:a7859ed111db3c1f5404a973a4747505d559fb5ca32d37e447afc0ef845a2103`.
  It bound only `127.0.0.1:16381`, used no host bind mount, disabled RDB/AOF,
  and was stopped with `--rm`; Docker confirmed both temporary container
  instances and both anonymous test volumes were removed.
- A tracked-only frontend mirror was created under the system temporary root,
  recursively verified to contain zero `.env*` files, and linked only to the
  existing `node_modules`. Offline `npm run lint -- --no-fix` passed.
- The authoritative isolated production build passed with existing asset-size
  and Node `fs.Stats` deprecation warnings. Bundle checker passed: zero source
  maps, 49 files, 1,587,799 bytes total, 571,421 initial bytes, 443,227 largest
  initial JavaScript bytes, and 143,472 gzip bytes for that JavaScript file.
- In-app browser verification used only the local deterministic fixture. At
  360×800, 768×1024, 1024×768, 1440×900, and 1920×1080, there was no horizontal
  overflow, the 1024 breakpoint produced two columns, citations remained
  visible and safely wrapped, and the workbench create control measured 44 px.
  The displayed citation contained source/page/rank/chunk hash and no artifact
  body. Browser console warnings/errors were empty.
- All three loopback fixture processes, both temporary build directories, the
  frontend mirror, logs, and the Redis container/volume were removed by exact
  validated targets. No screenshot or benchmark output entered the repository.

### Final repository gates

- Credential scan was clean: `tracked=216, staged=0, untracked=81`.
- `git diff --check` exited 0. Its output contained only existing LF-to-CRLF
  conversion notices, not whitespace errors.
- Requirements and npm manifests, `app/main.py`, `app/routers.py`, workflow
  catalog, README, overview, and prompts retain their starting hashes. The
  Aspect 5 manifest chains to the unchanged Aspect 4 manifest and records no
  dependency change.
- No new route, legacy REST/SSE change, SQL change, workflow operation, artifact
  identity, revision, cache, stale, cancellation, rollback,
  regeneration-lock, retention, or Token-budget change was introduced.
- Final status contains only the pre-existing user assets and planned Aspect 5
  source, test, fixture, documentation, frontend, and loopback fixture hunks.
  No repository dist, coverage, database, Redis dump, trace, screenshot, or
  benchmark dump was added.

### Stop condition

Aspect 5 is complete. Work stops here. Aspect 6–8 are not planned or
implemented until separately requested.

## Aspect 6 — Agent Eval, reliability, and security gates

Date: 2026-08-27

Status: implementation complete; final verification recorded below

Stop point: Aspect 6 only; Aspect 7–8 have not been implemented

### Protected starting state and pre-change gates

- Branch remained `main`; HEAD and local `origin/main` remained
  `3c49e864a523a4af4c0f3efd4f845e8ce7b1caed`; ahead/behind remained `0/0`.
- All 89 entry-time dirty paths were recorded with type, size and SHA-256. A
  deterministic aggregate hash was recorded for the existing untracked fixture
  directory. Every entry was treated as a user asset.
- Requirements, npm manifests, legacy FastAPI main and routers, workflow
  catalog, README, Iteration 4 overview/prompts, and the Aspect 5 manifest
  matched their locked hashes. The historical Agent v1 and RAG fixtures also
  matched their recorded hashes.
- Existing Python 3.11.15 environment `ezllmtest` passed `pip check`; no package
  was installed or changed.
- The fixed Redis image was already available locally as
  `redis:8.2.8-alpine@sha256:a7859ed111db3c1f5404a973a4747505d559fb5ca32d37e447afc0ef845a2103`.
  It was started only on `127.0.0.1:16381`, with RDB/AOF disabled and no host
  bind mount.
- Authoritative pre-change gates passed: Aspect 1–5 focus `201 passed, 365
  deselected in 17.20s`; complete backend `566 passed in 24.43s`.

### Offline Eval contracts and runner delivered

- Added frozen, strict Pydantic contracts for datasets, cases, expectations,
  safe observations, results, metrics, environment identity and gate decisions.
  Models reject extra fields, duplicate/unsorted risks, non-finite values,
  mixed-suite fixtures and non-canonical hashes.
- Fixture loading is restricted to the versioned test-fixture directory and
  strict UTF-8 JSON. It rejects duplicate keys, non-finite constants, oversized
  files and parent-hash drift. No expression, dynamic module, file path, command
  or provider execution is available from fixture data.
- Added a deterministic scoring layer for task success, trajectory validity,
  applicable tool selection, structured-output disposition, recovery, security
  counts, RAG correctness, logical latency/TTFE, Token/call counts, cache hits
  and synthetic cost units.
- Added `python -m app.agentEval` with only `--suite` and `--format`. It accepts
  no dataset, provider, model, project, Redis URL, output path, host or arbitrary
  command option. Reliability/all require credential-free loopback Redis from
  `EZLLM_TEST_REDIS_URL`; absence or an invalid URL fails closed with exit 2.
- JSON/text reports are stdout/stderr only and contain no goal, prompt,
  completion, reasoning, document body, credential, local path, Redis URL,
  project identity or traceback. A test replaced provider, embedding, MySQL,
  retriever and socket creation paths with fail-fast sentinels; core/security
  Eval passed without reaching any of them.

### Versioned datasets and hard-gate result

- `iteration4_agent_eval_v2.json` contains 39 golden tasks: all 22 typed tools
  plus seventeen normalized Agent journeys. It chains to the unchanged v1 hash
  instead of rewriting historical expectations.
- `iteration4_agent_security_v1.json` contains 47 named attacks across prompt
  injection, planner authority, approval tampering, arbitrary capability,
  project isolation, protocol boundary, serialization and data-leak families.
- `iteration4_agent_reliability_v1.json` contains 18 loopback Redis cases for
  duplicate delivery/approval, crash reconciliation, outcome unknown, evidence
  rebuild, lease fencing, cancellation, stale revision, transient disconnect,
  Redis loss, active-slot exclusion, replay bounds and warm exact cache.
- The controlled all-suite command completed `104/104` cases with exit 0. Exact
  applicable denominators were task/trajectory/structured output `104/104`,
  tool selection `39/39`, recovery `19/19`, and attacks blocked `47/47`.
- Approval bypass, duplicate side effects, project-isolation violations, budget
  overruns, arbitrary-capability executions and sensitive-data leaks were all
  `0`. The two cache cases were both hits; warm exact cache added zero model and
  embedding calls.
- Synthetic aggregate usage was 230 input Tokens, 115 output Tokens, 9 model
  calls, 0 embedding calls, 12 tool calls and 345 synthetic cost units. These
  are deterministic test weights, not provider currency or a price claim.
- RAG regression remained fixture-specific recall@4/MRR/nDCG@4/citation
  coverage `1.0` with zero project leaks, so the active Agent policy remains
  `dense_v1`.
- Performance and OpenTelemetry gates are `N/A` with reason
  `controlled_performance_and_telemetry_deferred_to_aspect7`. No wall-clock
  performance improvement is claimed. Real-model Eval remains not authorized
  and no CLI switch can enable it.

### Tests, frontend, and repository gates

- New Aspect 6 focus: `21 passed in 4.38s`.
- Iteration 4 integration before the final additional offline-path assertion:
  `221 passed, 365 deselected in 20.70s`.
- Authoritative final complete backend suite after that assertion:
  `587 passed in 25.56s`.
- The existing two-process SQLite/Redis worker recovery test remained in the
  complete suite, preserving the real crash/restart and single-side-effect
  evidence rather than replacing it with a second runtime.
- A controlled frontend mirror copied the current tracked source plus the three
  existing approved untracked Agent workbench source files. It contained zero
  `.env*` files and linked only the existing `node_modules`.
- Offline `npm run lint -- --no-fix` passed. The isolated production build
  passed with only the existing size and Node `fs.Stats` warnings. Bundle check
  passed: 0 source maps, 49 files, 1,587,799 bytes total, 571,421 initial bytes,
  443,227 largest initial JavaScript bytes and 143,472 gzip bytes for that file.
- Browser-size verification is `N/A — no frontend or public API change` for
  Aspect 6. Existing workbench contracts, lint, build and bundle gates passed.
- Credential scan was clean: `tracked=216, staged=0, untracked=98`.
- `git diff --check` exited 0 and emitted only existing LF-to-CRLF notices. A
  separate trailing-whitespace scan over every Aspect 6 source/test/document
  returned no matches.
- Requirements, npm manifests, protected source/docs, Aspect 5 manifest and
  historical fixtures retained their entry hashes. The Aspect 6 manifest chains
  to Aspect 5 and records no dependency change.

### Cleanup, final state, and limitations

- Docker inspection confirmed the exact image and loopback port. The image's
  declared `/data` path created one anonymous volume but no host mount; stopping
  the `--rm` container removed both the exact container and that volume, which
  were then confirmed absent.
- The validated frontend mirror and build directories under the system temp
  root were deleted after their junction was removed. No repository build,
  database, Redis dump, trace, screenshot, coverage or Eval-report dump was
  created. The pre-existing ignored frontend `dist` retained its 2026-08-22
  timestamp; existing cache directories remain user state.
- Final porcelain status has 101 top-level entries: the original 89 user-asset
  entries plus exactly the planned Aspect 6 document, CLI, three service
  modules and seven test files. New fixtures remain grouped under the already
  untracked fixture-directory entry.
- No provider, real embedding, MySQL, real project, remote Redis or external
  socket was accessed. No model cost was incurred. No stage, commit, fetch,
  pull or push was performed.

### Stop condition

Aspect 6 is complete. Work stops here. Aspect 7–8 are not planned or
implemented until separately requested.

## 2026-08-27 — Iteration 4 Aspect 7 completed

### Entry freeze and parent baseline

- Work began on `main` at local HEAD and `origin/main`
  `3c49e864a523a4af4c0f3efd4f845e8ce7b1caed`, ahead/behind `0/0`.
  The 101 entry-time porcelain entries and their expanded path/size/SHA-256
  inventory were treated as user assets. README, Iteration 4 overview/prompts,
  all Aspect 1–6 files, and the existing ignored frontend `dist` were not
  adopted as disposable files.
- Entry hashes matched the Aspect 6 freeze: requirements `54EB1002...`, npm
  manifest `769EC529...`, npm lock `C93CDE31...`, legacy main `DBEC0E64...`,
  routers `A3DDD017...`, workflow catalog `E9265C34...`, and Aspect 6 manifest
  `23F4EFB4...`.
- Dependency-change parent gates passed before installation: Aspect 1–6 focus
  `222 passed in 18.65s`; complete backend `587 passed in 26.81s`.
- The first real pre-change wall-clock fixture records five warmups and thirty
  measurements without dropping outliers. Legacy health p95 was 2.3347 ms and
  Agent capabilities p95 was 1.7038 ms. Vue CLI build p50/p95 was
  10,495.11/12,393.58 ms; dev-ready p50/p95 was 1,330.24/1,768.71 ms. The
  baseline bundle contained 0 maps, 571,421 initial bytes and 1,587,799 total
  bytes. These values are host-specific and do not claim an improvement.

### Dependency resolution and telemetry delivery

- An isolated Python 3.11 resolver accepted the four approved exact OTel pins
  and `pip check`. Requirements now hash to
  `7FE551B074A6D49A4E8A82E71ECF7F6B9D73207631BA4EEAF02764453A293932`.
  No FastAPI, Redis, or SQLAlchemy automatic instrumentation was added.
- An isolated npm resolver accepted every approved Vite/TypeScript/ESLint pin
  except `@eslint/js==10.8.0`, which is not published. The exact compatible
  published version `10.0.1` was selected and recorded. Current package and
  lock hashes are `031E98C3...` and `402B195D...`.
- Added centralized manual OTel and allowlisted JSON logging. Disabled mode is
  a true no-op; exporter failures do not affect business results. Trace context
  crosses API, Redis command, worker, graph, planner, tool, retrieval,
  checkpoint, recovery, MCP, and SSE boundaries. Metrics use only the approved
  low-cardinality labels.
- Prompt/completion/reasoning, messages, tool bodies, retrieval queries,
  project/document content, absolute paths, SQL, Redis URLs/keys, credentials,
  tracebacks and exception stacks are rejected from telemetry and logs.
  GenAI metadata is fixed to `otel-genai-safe-v1`.
- Agent health/capabilities and run projection expose only safe telemetry mode,
  schema and nullable 32-hex trace ID. The workbench shows honest disabled and
  instrumented states, copy support and an optional loopback Grafana Explore
  link; old routes and SSE kinds were unchanged.

### Benchmark and correctness gates

- `python -m app.agentEval --suite all --format json` was first attempted with
  the Anaconda base interpreter and failed before case execution because that
  interpreter lacks `langchain_core`. It was immediately rerun with the frozen
  `ezllmtest` Python 3.11.15 environment and passed all `104/104` cases. Task,
  trajectory, structured output, applicable tool selection, recovery and
  attack blocking remained 100 percent; approval bypass, duplicate side
  effects, project leaks, budget overruns, arbitrary capability and sensitive
  leaks remained zero.
- The authoritative `agentBenchmark --suite all --telemetry compare --format
  json` produced 62 case/mode results with five warmups and thirty samples.
  Legacy post-change p95 ratio was `1.0394054925` against the fixed parent
  baseline (limit `1.15`). OTel enabled/disabled aggregate workload p95 ratio
  was `1.0217368989` (limit `1.05`). The exporter status was `exported`, every
  first SSE event was safe, and warm exact-cache cases added zero model and
  embedding calls.
- The CLI contract test intentionally accepts exit 0 or 1 for an isolated real
  wall-clock run and verifies that the exit code matches its report. A busy
  host is therefore reported honestly instead of being forced to pass. The
  authoritative full matrix above passed and is frozen separately.
- No real provider, embedding, MySQL, project document or provider-priced model
  was accessed. Eval/benchmark usage remained deterministic fake data and model
  currency cost was zero.

### Vite migration and browser evidence

- Vue CLI/Babel configuration was replaced by Vite 8.2.2, Vue plugin 6.0.8,
  typed `import.meta.env`, flat ESLint, `vue-tsc`, root `index.html`, static ESM
  assets and preserved lazy routes. `serve`, `build`, and `lint` remain; the
  additive command is `type-check`. Production source maps remain disabled.
- Vite build p50/p95 was 622.86/788.02 ms and dev-ready p50/p95 was
  415.24/743.40 ms, ratios `0.06358` and `0.42031` to Vue CLI p95. The final
  bundle has 0 maps, 293,597 largest initial JavaScript bytes, 115,218 initial
  CSS bytes, 527,792 initial total bytes, and 1,474,835 total bytes. Ratios are
  `0.66241`, `1.03605`, `0.92365`, and `0.92885`, all within `1.05`.
- A trial `cssMinify: esbuild` failed closed because Vite 8 does not install
  esbuild; no dependency was added. The accepted solution keeps Lightning CSS,
  sets a modern CSS target, and moves select styles to the lazy
  `TestTargetSelector` chunk. This brought initial CSS under the gate without
  hiding a warning or weakening the limit.
- A clean temporary mirror containing no `.env*`, prior `node_modules`, `dist`
  or cache ran `npm ci` (`233` packages), lint, type-check, Vite build and bundle
  check successfully.
- The in-app browser used the synthetic loopback fixture only. At 360x800,
  768x1024, 1024x768, 1440x900 and 1920x1080 the Agent heading remained
  visible, horizontal overflow was zero, and the approval target was at least
  44 px. Escape closed the approval dialog and restored focus to “审查并决定”.
  Browser console errors were zero. Both `未启用` and a format-valid synthetic
  instrumented Trace UI were exercised; real trace persistence was proven
  independently by Tempo.

### Compose and CI evidence

- Added digest-pinned backend/frontend builds and a ten-service Compose stack:
  frontend, legacy API, Agent API, worker, MySQL 8.4, Redis 8.2.8, Collector
  0.159.0, Prometheus 3.12.0, Tempo 2.10.7 and Grafana 13.1.3. Only loopback
  ports 8080, 8130, 8131, 3000 and 9090 are published. MySQL, Redis, Collector
  and Tempo remained internal; named volumes cover durable application and
  observability data.
- The unique validation project `ezllm-aspect7-verify-20260827` reached 10/10
  healthy services. Agent health reported `instrumented`, a non-loopback Host
  returned 421, Prometheus reported the Collector target at `1`, Grafana
  provisioned data source UIDs `prometheus` and `tempo` plus dashboard UID
  `ezllm-agent-overview`, and Tempo returned 20 real traces rooted at
  `http.agent_api` for service `ezllm-agent-api` after the final rebuild.
- Collector processors remove content-bearing HTTP, database, Redis, tool,
  retrieval and GenAI attributes. Debug export and Loki were not enabled.
  Grafana external update/plugin checks were disabled for the local stack.
- Added an Ubuntu Actions workflow for pull requests, main pushes and manual
  dispatch. It uses `contents: read`, concurrency cancellation, no secrets,
  immutable checkout/setup action SHAs, fixed Redis, pytest, Eval, benchmark,
  npm ci/lint/type/build/bundle and a real Compose trace/metric/Grafana smoke.
  Local equivalent commands and static contracts pass. Hosted execution is
  explicitly `awaiting_explicit_push`; it is not claimed as passed.

### Final verification, cleanup and state

- Aspect 7 focused tests: `39 passed in 3.42s`.
- Final complete backend: `616 passed in 27.93s`.
- Final `pip check` reported no broken requirements. Credential scan was clean:
  `tracked=212, staged=0, untracked=130`. `git diff --check` exited zero and
  emitted only existing LF-to-CRLF notices. Aspect 7 manifest/CI/Compose/Vite
  contract recheck: `16 passed in 0.16s`.
- Requirements/npm hashes match the Aspect 7 manifest. Legacy main, routers,
  workflow catalog, README, overview and prompts retain their protected hashes.
  No `.sqlite`, database, Redis dump, AOF, trace, source map, coverage or
  benchmark-report artifact was found in the repository.
- The validation Compose project, its six exact validation volumes and the
  dedicated `ezllm-aspect7-baseline-20260827` Redis were removed. The user's
  `cc4c-v3-aspect3-redis` remained running on `127.0.0.1:6379` and was not
  modified. Five exact `ezllm-aspect7-*` temporary directories were deleted.
- The pre-existing ignored Vue CLI `dist` was not deleted. The generated Vite
  directory was moved to a disposable temp path, the 49-file entry snapshot was
  restored, and its deterministic tree hash
  `A9E3FA0F4744A4B87A3C5632A6B2F654B8589D395D4921CAF938A942367E21DC`
  matched before the disposable copy was removed.
- Final Git remains `main` at local/origin `3c49e864...`, ahead/behind `0/0`,
  with 142 porcelain entries, 32 tracked diff paths and 132 individually
  untracked paths. Real `.env` files were never opened; only their names were
  observed during the final artifact audit. No stage, commit, fetch, pull or
  push was performed.

### Stop condition

Aspect 7 is complete. Work stops here. Aspect 8 is not planned or implemented
until separately requested.

## 2026-08-27 — Aspect 8: integrated Agent acceptance and Iteration 4 closeout

### Frozen start and scope

- Reconfirmed `main`, HEAD/local `origin/main`
  `3c49e864a523a4af4c0f3efd4f845e8ce7b1caed`, ahead/behind `0/0`.
  The starting inventory contained 142 porcelain entries, 32 tracked diff
  paths and 132 untracked paths; the complete path/size/SHA-256 inventory was
  treated as user-owned data. Its aggregate digest was
  `9EB56487CC73CA8D602E4206ADCCABD73C3BD3B335FC7B0D1683FD526CEEDA3F`.
- Requirements, npm manifests, legacy main, routers, workflow catalog and the
  Aspect 7 manifest matched the approved parent hashes. README, overview and
  prompts were frozen at their Aspect 7 hashes before their narrowly scoped
  closeout edits.
- Parent gates passed before Aspect 8 edits: focused regression `251 passed,
  365 deselected`; complete backend `616 passed`; Eval `104/104`; benchmark
  legacy/OTel ratios `0.9853943072` and `1.0268668014`; Vue CLI/Vite parent
  lint, type-check, build and bundle checks passed.

### Acceptance implementation

- Added strict `agentAcceptanceContracts`, deterministic
  `agentAcceptanceRunner` and `python -m app.agentAcceptance`. The CLI accepts
  only `journey|reliability|protocol|all` and `text|json`, writes no report,
  rejects credentials and arbitrary Redis endpoints, and uses stable exit
  codes 0/1/2.
- Added the fixed-seed `iteration4-agent-acceptance-v1` fixture with 18 cases:
  seven journey, six reliability and five protocol scenarios. The runner
  reuses the real runtime, LangGraph, safe Redis saver, coordinator, workbench,
  Agent API ASGI app, command worker, registry and Aspect 6 Eval. Only the
  planner/tool edge is deterministic; the persisted effect uses a temporary
  SQLite adapter and session state remains Redis-scoped.
- The integrated path performs API create → worker planning/HITL → approval →
  execution → completion, reads a terminal SSE stream, enforces cross-project
  404, then injects a retryable tool failure and recovers it through the real
  API/queue/checkpoint path without a second side effect.
- The explicit isolated Compose mode additionally imports the legacy FastAPI
  app, creates a synthetic project, uploads knowledge/requirements/design
  documents, reaches `documents_ready`, finalizes to `setup_complete`, and
  uses that validated project identity for the Agent journey.

### Gate-discovered fixes

- The first container acceptance correctly failed closed because the historical
  Eval allowed only loopback Redis and assumed Git plus frontend manifests were
  present in the backend runtime image. The minimal fix preserves the default
  loopback rule, allows only hostname `redis` when
  `ASPECT8_ACCEPTANCE_TOPOLOGY=isolated_compose`, and reuses the immutable
  Aspect 7 manifest hashes/baseline revision when the runtime image omits Git
  and frontend sources. Remote and credentialed Redis remain rejected.
- The observability query exposed missing runtime tool/recovery metric samples.
  `agentGraph` now records low-cardinality tool call/duration metrics and
  `AgentRuntimeService` records the real recover command outcome. No public
  API, event, workflow, artifact or budget schema changed.
- The first full pytest after documentation closeout found one historical
  Aspect 5 test still comparing intentionally updated README/overview/prompts
  to an old snapshot (`634 passed, 1 failed`). The test now treats those three
  paths like the already-corrected Aspect 7 history test; the historical
  fixture and all non-document protected hashes remain immutable. Final full
  pytest passed.

### Acceptance, browser and observability evidence

- Local loopback and isolated Compose Acceptance both passed `18/18` with task
  success, trajectory validity and recovery at 100 percent. Approval bypass,
  duplicate side effect, project isolation violation, budget overrun, unsafe
  capability execution, sensitive leak and session-to-MySQL write were all 0.
- Final Aspect 6 Eval remained `104/104`; 47/47 attacks were blocked, tool
  selection and structured output were 100 percent, and all hard safety counts
  remained zero.
- Final benchmark used five warmups and thirty retained samples per case.
  Legacy p95 ratio was `1.083736659134018` (limit `1.15`); OTel p95 ratio was
  `1.014521458310483` (limit `1.05`); warm exact-cache added zero model and
  embedding calls.
- The in-app browser exercised the deterministic workbench at 360x800,
  768x1024, 1024x768, 1440x900 and 1920x1080 with zero horizontal overflow.
  Approval focus entered the primary decision, all visible dialog buttons were
  at least 44 px high, Escape returned focus to `审查并决定`, and the fixture
  verified persisted/RAG evidence, session-only 7-day evidence, trace
  disabled/instrumented displays and failed-run recovery.
- The unique `ezllm-aspect8-verify-20260827` Compose project reached 10/10
  healthy services. In-container non-loopback Host returned 421. The Compose
  Acceptance journey passed 18/18 against Redis 8.2.8 and isolated MySQL.
- Tempo observed nine fixed layers from HTTP/enqueue/worker/run through graph,
  tool/checkpoint and SSE, plus a command with `kind=recover`. Queries for
  prompt, reasoning, DB statement, Redis key and URL query attributes returned
  zero traces. Prometheus exposed tool, recovery, checkpoint and SSE metrics;
  inspected labels contained no project, run, thread or revision. Application
  container sensitive-pattern counts were zero. Grafana provisioned the
  Prometheus/Tempo datasources and `ezllm-agent-overview` dashboard.
- The verification project, its containers, two networks and six exact volumes
  were removed with `down -v`; a follow-up project/volume query returned empty.
  The user's pre-existing loopback Redis was not stopped or modified.

### Delivery and final verification

- Updated the offline GitHub Actions workflow to run Acceptance locally and
  inside its unique Compose validation project. Hosted state remains
  `awaiting_explicit_push`.
- README now presents Iteration 1–4 as offline-accepted and documents the
  LangGraph single Agent, Agent API/worker/workbench, Redis, MCP, OpenTelemetry,
  Compose, Vite, Eval, benchmark and Acceptance commands. Overview and prompts
  are explicitly archived; the new closeout preserves the distinction between
  legacy `reasoning_delta` and Agent no-CoT behavior.
- A first tracked-only frontend mirror attempt failed because deleted Vue CLI
  files were still listed by Git and the npm `--prefix` position was wrong;
  its validated temp directory was removed. The corrected no-`.env*` mirror
  ran offline `npm ci` (233 packages), lint, type-check, Vite build and bundle
  checker successfully: 0 source maps, 293,597 largest initial JS bytes,
  115,218 initial CSS bytes, 527,792 initial total bytes and 1,474,835 build
  bytes. The corrected temp directory was also removed.
- A focused run through `conda run` encountered only the host GBK output
  wrapper error; rerunning the exact command with the environment's Python
  executable produced `25 passed`. Final complete backend result:
  `635 passed in 28.08s`.
- Credential scan was clean (`tracked=212, staged=0, untracked=142`).
  `git diff --check` exited zero with only existing LF/CRLF notices. Final
  Compose config was valid. Requirements/npm, legacy main, routers, workflow
  catalog and Aspect 7 manifest hashes remained unchanged.
- Final Git inventory contains 151 top-level porcelain entries, 176 individual
  porcelain entries, 32 tracked diff paths and 144 untracked files. The twelve
  new untracked files relative to the Aspect 8 start are the planned
  Acceptance modules/CLI, fixtures, tests and closeout; the generated-artifact
  pattern audit returned zero matches.
- Real `.env` was never opened. Real provider calls, embedding calls, user
  MySQL calls, user project reads and model currency cost were all zero. No
  database, Redis dump, trace dump, coverage, benchmark report, screenshot,
  source map or frontend `dist` was added to the repository.

### Stop condition

Aspect 8 and Iteration 4 offline closeout are complete. Git remains unstaged,
uncommitted, unfetched, unpulled and unpushed. No tag, Release or real-model
Agent quality run was created. Work stops here pending a separate release
instruction.

## 2026-08-27 — 收口后真实模型 Agent 质量门禁

- 用户明确授权真实 chat 与真实 RAG/embedding；应用配置从 ignored `.env` 加载四个 provider key，但命令和报告未输出、复制或记录任何 key 值。
- 固定选择当前 Agent runtime 使用的 `GLM-4.7` 与 `embedding-3`，没有遍历另外三个聊天 provider。全部输入为合成目标和合成文档；真实项目读取、MySQL、业务工具副作用均为 0。
- 连通性预检：1 次 chat 成功，usage input/output/total=`19/244/263`；1 次 embedding 成功，向量维度 `2048`。
- 新增显式费用门控入口 `python .\scripts\agent_live_quality.py --confirm-cost --format json`。固定上限为 6 次 chat、4 次 embedding，安全契约测试 `4 passed`；随后补充精确 embedding 计数门，测试增至 `5 passed`。
- 真实 planner：6 次调用，input Token=`13,191`、total Token=`13,391`，六个样例均在严格结构化输出校验处失败；structured output=`0/6`、tool selection=`0/6`，门禁失败。nearest-rank p50/p95=`2303.766/2667.186 ms`。
- 真实 RAG：top-1=`3/3`、citation coverage=`1.0`、context Token=`94`、index build/reuse=`1/2`；nearest-rank query p50/p95=`148.042/369.006 ms`。
- 总实际调用（含预检）为 7 次 chat、5 次 embedding。失败后没有自动重试、扩大样本或调用其他 provider；供应商货币费用未由 API 返回，因此未虚构人民币/美元金额。
- 安全计数：real project reads=`0`、MySQL calls=`0`、tool side effects=`0`、stored model content=`0`、stored reasoning=`0`、credential exposure=`0`。
- 代码级首要修复候选：runtime planner 当前只把 request JSON 作为 user message，没有明确 JSON-only 指令、输出 schema 或 provider 原生 structured-output 约束。模型正文按设计立即丢弃，未为诊断保存或展示。
- 结果记录于 `docs/iteration-4-live-model-acceptance.md`。Aspect 8 gate fixture 保持历史不变；修复后的付费复验需要新的明确授权。

### 结构化 planner 修复与授权复验

- 用户明确要求修复 planner 结构化输出契约，并授权修复后的真实付费复验。
- 官方接口文档确认 `glm-4.7` 支持 `response_format={"type":"json_object"}`，且建议提示词同时明确 JSON 输出。
- 新增共享 `build_planner_provider_prompt()`：把输入标为 untrusted data，只允许精确 `PlannerProposal` JSON，禁止 Markdown、prose、analysis/code fence 和运行时权限字段。
- stream request 只接受冻结的 `json_object` response format；正式 runtime factory 与 live gate 共享 prompt builder/response-format 常量。未放宽 `json.loads`、Pydantic、catalog/input schema、scope、风险或审批校验。
- 修复前先得到失败回归；修复后聚焦测试 `20 passed`，增加 runtime factory 共享契约测试后，完整离线回归 `612 passed, 31 skipped`。
- 修复后真实套件使用相同样本执行，无额外 smoke：planner tool selection/structured output/regenerate=`6/6`，input/total/completion-observed Token=`11,337/11,622/285`，p50/p95=`1151.586/2637.884 ms`。
- 真实 RAG 复验 top-1=`3/3`、citation coverage=`1.0`、context Token=`94`、embedding calls=`4`、index build/reuse=`1/2`，query p50/p95=`147.681/439.944 ms`。
- 修复后总门禁 PASS。本次复验调用为 6 chat + 4 embedding；连同首轮和预检，累计 13 chat + 9 embedding。未调用其他 provider，未访问真实项目或 MySQL，未保存模型正文/CoT，未产生工具副作用。

## 2026-08-28 — 隔离真实模型 Agent E2E（ui_info → ui_case）

- 用户明确授权真实付费端到端验收，并限定为合成项目、临时 SQLite、真实 RAG/embedding，禁止真实项目和用户数据库。
- 新增显式费用门控脚本 `python .\scripts\agent_live_e2e.py --confirm-cost --format json` 及安全契约测试。入口固定 `GLM-4.7`、`embedding-3` 和 `ui_info → ui_case`，只接受无凭证 loopback Redis DB 0，不提供任意 provider/model/project/database/host/path 参数。
- Redis 使用固定 8.2.8 digest、`127.0.0.1:6399` 和 tmpfs；合成文档及 SQLite 位于系统临时目录。配置在 DAO import 前覆盖 `DATABASE_URL`，因此用户 MySQL 调用为 0。
- 首个付费 run 的 planner 与 `ui_info` 成功，但真实多步骤图暴露 `VALIDATION_SUCCEEDED` 后重新 planner、重复请求 `ui_info` 审批的问题。修复为推进冻结计划的 `current_step_index`，并按下一步风险进入审批/执行；新增两步 graph 回归，内存与真实 Redis checkpointer 聚焦门禁分别通过。
- 后续完整 run 已达到 `completed`，但 Windows 临时 SQLite 文件被 SQLAlchemy pool 持有，导致成功报告在 `TemporaryDirectory` 清理时被泛化异常覆盖。验收入口改为 Session 内复制 artifact 摘要、按 operation 关联 evidence、输出脱敏阶段错误，并在退出前 `engine.dispose()`。
- 最终付费门禁 PASS：trajectory=`ui_info,ui_case`、approvals=`2`、artifact=`1/1`、RAG query/citation=`1/1`、context Token=`98`、index build/reuse=`1/0`；model/embedding/tool calls=`4/2/2`，input/output Token=`15,209/26,112`，wall-clock=`96,163.598 ms`。
- 最终安全计数：approval bypass、duplicate side effects、real project reads、user database calls、public/checkpoint document leakage、stored reasoning、credential exposure 均为 0。临时 SQLite/文档目录为 0，验收容器已删除，端口 6399 已释放，用户既有 Redis 未触碰。
- 为透明记录实际付费边界，缺陷定位和最终门禁共运行四个隔离 E2E run，累计 `14` chat + `6` embedding；未调用其余聊天 provider。provider 未返回货币费用，不推测货币金额。
- 实施期间未 stage、commit、fetch、pull 或 push；Aspect 8 历史 fixture 未修改。

## 2026-08-28 — Iteration 4 最终文档、发布门禁与 Main 交付

- 用户授权创建 `codex/iteration4-closeout`、分两笔提交、合并并推送 `origin/main`，但不创建远端 feature branch、Tag 或 GitHub Release。起点 HEAD、本地 `origin/main` 与远端 main 均为 `3c49e864a523a4af4c0f3efd4f845e8ce7b1caed`。
- 首笔实现提交为 `f73ecbd723731096d4386f4806654dd2e11fb9a7`（`feat: complete iteration 4 agent orchestration platform`）。提交前审计 182 个 staged 路径，真实 `.env`、数据库、Redis dump、日志、trace、coverage、截图、`dist`、source map、缓存和 `node_modules` 均未进入暂存区；credential scan 与 `git diff --cached --check` 通过。
- 最终文档把证据明确分为离线门禁、真实 planner/RAG 合成质量门禁和隔离 `ui_info → ui_case` 真实 Agent E2E；README 启动命令固定为 `npm run serve -- --port 8080 --strictPort`，GitHub Actions 状态改由 main badge 动态展示。
- 新增 `iteration4_release_manifest_v1.json`，以未修改的 Aspect 8 manifest 为父层，冻结 package/protected-source/final-document/live-acceptance 哈希，并记录 main 交付目标、无 Tag/Release 和未知货币费用边界。Aspect 1–8 历史 fixture 未回写。
- 使用项目 Python 3.11.15 和独立 Redis 8.2.8 容器（精确 digest、`127.0.0.1:6399`、tmpfs、RDB/AOF 关闭）运行完整 pytest：`658 passed in 27.86s`，无 skip。
- `agentEval --suite all` 通过 `104/104`，47/47 安全攻击按预期阻断；approval bypass、duplicate side effect、project isolation、预算突破、任意能力和敏感泄漏均为 0。
- `agentAcceptance --suite all` 通过 `18/18`，task success、trajectory validity 和 recovery 为 100%；warm exact-cache 新增模型/embedding 调用为 `0/0`，用户 MySQL 与用户项目读取为 0。
- `agentBenchmark --suite all --telemetry compare` 退出码 0：legacy p95 ratio=`1.0276695194994545`（门限 1.15），OTel p95 ratio=`1.0258291744311046`（门限 1.05），warm-cache 零模型/embedding 门禁通过。全部为 deterministic fake 边缘，真实 provider/embedding/MySQL 调用为 0。
- tracked-only、无 `.env*` 的系统临时前端副本执行离线 `npm ci`（233 packages）、lint、type-check、Vite build 和 bundle checker均通过；source map=0，largest initial JS=293,597 bytes，initial CSS=115,218 bytes，initial total=527,792 bytes，build=1,474,835 bytes。验证目录已精确删除。
- `docker compose --env-file ops/compose/.env.example -f compose.yaml config --quiet` 通过。发布门禁没有再次执行真实模型或 embedding；真实费用范围仍仅为前述已授权质量/E2E 调用，provider 未返回货币金额。
- 托管 CI 只在推送 main 后触发，最终状态以 README badge 和 GitHub Actions 页面为准，避免在仓库内写入会过期的静态状态。
