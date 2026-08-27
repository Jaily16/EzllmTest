# Iteration 4 Aspect 3 Runtime Contract

Status: Accepted for Aspect 3 implementation. Public API adoption and the Agent
workbench remain deferred.

## Scope and frozen boundaries

Aspect 3 adds a Python/LangGraph 1.2.11 single Agent runtime, durable human
approval, a Redis worker, checkpoint recovery, fenced leases, idempotency,
cancellation, bounded event replay, and hard budgets. It does not add a public
route, modify the 19-operation workflow catalog, or replace an existing workflow
service. No public REST/SSE change is permitted. The FastAPI application does
not mount the worker or the Agent graph, and the loopback MCP server remains
read-only by default.

The runtime invokes the existing application service adapter in process. It
does not call this application through HTTP, SSE, or MCP. MySQL remains the
authority for projects, revisions, and valid persisted artifacts. Redis holds
only resumable execution state. A lost Redis thread is explicitly
unrecoverable; Redis loss cannot delete, stale, or overwrite a valid MySQL
artifact. Workbench UI, public Agent endpoints, OpenTelemetry, Compose, CI, and
all Aspect 4–8 work remain out of scope.

## State graph and approval

The graph version is `iteration4-aspect3-v1` and its fixed nodes are `observe`,
`plan`, `validate_plan`, `request_approval`, `await_approval`, `execute`,
`validate_result`, `advance`, `complete`, `fail`, `recover`, and `reconcile`.
`await_approval` calls LangGraph `interrupt()` before any side effect. Resume
uses the same stable thread identity and synchronous checkpoint durability.
Framework retry is not placed around the side-effect node.

The planner may select only catalog-derived workflow tools. Project scope,
execution model, risk labels, step identity, idempotency key, budget, and
approval binding are supplied by the trusted runtime. Every paid, persistent,
or regenerate step is individually approved. An approval binds the project,
revision, plan version, operation, normalized arguments, risks, execution model,
and budget. The runtime issues a one-time approval nonce; a duplicate or expired
decision cannot authorize another execution. Cancellation is checked before the
next side effect. A changed source revision clears the old observation and
forces observation, planning, and approval again.

Only structured plans, safe observations, approval records, result summaries,
artifact references, usage, and classified errors are checkpointed. Prompt or
completion bodies, chain-of-thought, scratchpads, credentials, raw project
documents, tracebacks, and arbitrary Python objects are forbidden.

## Safe Redis checkpointer

`langgraph-checkpoint-redis==0.5.2` was rejected because its JSON serializer did
not satisfy the adversarial constructor rejection gate. `redisvl` is therefore
not installed. The in-repository implementation extends only the public
`BaseCheckpointSaver` and `SerializerProtocol` surfaces from
`langgraph-checkpoint==4.2.0`; it does not inherit, monkeypatch, or copy a private
upstream Redis saver.

`StrictAgentCheckpointSerializer` emits `ezllm-safe-json-v1`. Its explicit JSON
AST permits JSON primitives with finite numbers, bounded bytes/bytearray,
lists, tuples, string-key dictionaries, and exact LangGraph `Interrupt` and
`Send` values. Unknown classes, dataclasses, Pydantic objects that were not
explicitly dumped, sets, non-string keys, NaN/Infinity, excess depth/size, and
any LangChain-style constructor envelope are rejected during both encoding and
decoding. It performs no pickle, msgpack constructor, dynamic import, or object
construction outside the allowlist.

The saver implements the public async `aget_tuple`, `alist`, `aput`,
`aput_writes`, and `adelete_thread` protocol. Checkpoints and pending writes are
stored under a scope-hash, graph-version, and storage-thread identity. A
per-thread registry makes exact deletion and expiration possible without
database-wide `KEYS` calls. Reads do not renew retention.

## Redis coordination and retention

The namespace is `ezllm:agent:v1`. Production defaults are:

- checkpoint, descriptor, budget, idempotency, cancel, and session-only result:
  7 days;
- replay events: 1 hour and at most 2,000 entries per thread;
- lease: 30 seconds, renewed every 10 seconds;
- pending command claim: 45 seconds.

The storage identity is derived from the trusted scope hash and external thread
ID. A scope hash already includes graph version and the complete trusted project
scope. A caller that has only a thread ID cannot address another project.

Worker and checkpointer share one lease value in the exact `owner:fence` form.
Acquisition increments a monotonic fence; renew, checkpoint, idempotency, budget,
nonce, and event writes reject an obsolete owner or fence. Commands use a Redis
Stream consumer group and at-least-once delivery. Command IDs and terminal run
views make repeat delivery harmless; messages are acknowledged only after safe
processing.

Idempotency follows `reserved → started → completed | outcome_unknown`.
Completed results are replayed without another tool call. After a crash, a
persisted workflow first queries the existing artifact identity. A matching
artifact reconstructs a successful result without another save. If the
persisted result cannot be proven, or a session-only paid result was not safely
recorded, the result becomes `outcome_unknown`; the runtime does not guess or
repeat the paid call. Session-only results never enter MySQL.

## Hard budgets

The immutable run budget includes steps, absolute elapsed time/deadline, input
and output tokens, model calls, embedding calls, tool calls, and synthetic cost
units. A fenced Redis Lua ledger reserves these dimensions atomically before an
Agent provider, embedding, or tool call. Duplicate reservation IDs are
idempotent and budget definitions cannot be expanded during recovery. Missing
usage retains the conservative reservation. Existing provider, streaming, and
embedding hooks are `ContextVar`-guarded no-ops for legacy REST/SSE requests.

## Worker and security posture

`python -m app.agentWorker --consumer <name> [--once]` is an internal worker. Its
CLI deliberately has no Redis URL, host, project, scope, approval, file, Shell,
SQL, Python, or generic network option. Redis configuration is read directly
from process environment; the worker never loads a real `.env` itself. Default
configuration is loopback/private.

The local integration gate used `redis:8.2.8-alpine` at digest
`sha256:a7859ed111db3c1f5404a973a4747505d559fb5ca32d37e447afc0ef845a2103`,
bound only to `127.0.0.1:16379`, with no host volume and persistence disabled.
It validated real checkpoint/HITL round trips, fencing, budgets, event replay,
cancellation, duplicate commands, and two independent Python worker processes.
The crash/restart test writes a synthetic artifact to an isolated temporary
SQLite store, kills the first worker after the artifact write, lets the lease
expire, and proves that the second worker reconciles without a duplicate side
effect.

## Upstream replacement gate

An upstream Redis saver may replace this minimal implementation only after a
specific released version provides a stable serializer injection surface,
rejects the same malicious constructor/type-confusion/depth fixtures, uses no
pickle fallback, preserves the scope/fence/TTL contracts, and passes the same
two-process recovery suite. A package being newer is not sufficient evidence.
