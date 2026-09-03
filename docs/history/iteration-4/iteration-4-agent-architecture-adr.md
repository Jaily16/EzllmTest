# ADR: Iteration 4 Agent architecture contract

- Status: **Accepted for Aspect 1 contracts; runtime adoption deferred**
- Date: 2026-08-27
- Scope: Iteration 4 Aspect 1 only

## Decision

EzllmTest remains a Python 3.11 and FastAPI application. The only approved
future orchestration runtime is LangGraph, used for one single Agent. This ADR
rejects a Java rewrite, multi-Agent design, Agent-to-Agent hand-offs, and a
separate planner service. Aspect 1 installs or enables none of these runtime
components.

The existing 19-entry workflow catalog remains the business capability,
prerequisite, persistence, corpus, prompt-version, and budget source of truth.
A model may select only an operation already present in that workflow catalog.
It cannot create an arbitrary capability.

The future Agent executes a catalog operation through the in-process
application service layer. It must not call itself through HTTP or MCP. Public
routes and the REST/SSE formats remain adapters for existing clients, not an
internal tool bus.

The user workbench and loopback MCP adapter will consume the same typed tool
definition and approval metadata. MCP is only an adapter at the trust
boundary; it cannot have a larger capability set than the workbench or bypass
the application service layer. No MCP server is added in Aspect 1.

## State and state machine

`AgentRunState` is a versioned, JSON-safe reference contract containing a
trusted project scope, source revision, goal, structured plan, current step,
approval bindings, tool attempt summaries, artifact references, run budget,
usage counters, cancellation state, event sequence, safe error category, and
checkpoint recovery reference.

The status graph is:

1. `created -> planning`.
2. `planning -> executing | awaiting_approval | failed | cancelled`.
3. `awaiting_approval -> executing | planning | cancelled`.
4. `executing -> validating | failed | cancelled`.
5. `validating -> planning | completed | failed | cancelled`.
6. `failed -> recovering` only for an explicitly retryable error within the
   unchanged budget.
7. `recovering -> awaiting_approval | executing | validating | failed |
   cancelled` after idempotency reconciliation.
8. `completed` and `cancelled` are terminal.

Recovery must query the idempotency result before attempting the operation
again. If the side effect already committed, recovery goes to validation and
must not repeat it. A stale source revision invalidates the plan and approval
and returns to planning.

## Tool risk and human approval

Every typed tool call has one or more of these risks:

- `read_only`: no cost or persistence side effect and no approval required.
- `paid`: can make a metered provider call and requires approval.
- `persistent`: can change a durable business artifact and requires approval.
- `regenerate`: replaces a valid artifact and must also carry `paid` and
  `persistent`; it requires explicit approval.

Approval is bound to the run, plan version, step, operation, normalized
arguments, risks, trusted project, source revision, model label, and complete
budget. An edited plan, changed arguments, changed revision, changed model,
changed project, changed risks, or changed budget invalidates it. Rejection,
expiry, cancellation, or a missing binding prohibits tool execution.

The project scope is injected by a trusted runtime from authenticated request
context. It is not accepted from model output. Model-supplied `pid`,
`project_id`, user identity, or scope arguments are rejected before dispatch.

## Data ownership

MySQL remains the authority for projects, source revisions, and valid durable
artifacts. Existing atomic replacement, delayed save, stale marking, rollback,
and regeneration-lock behavior remains unchanged.

Redis is reserved for Agent thread/checkpoint state, leases, idempotency
records, cancellation signals, and bounded short-term event replay. Redis is
not an artifact authority. Redis loss may make an unfinished run unavailable,
but must not delete, invalidate, or silently replace a valid MySQL artifact.
Recovery always reconciles MySQL and idempotency state before another side
effect.

## Budgets

Every run receives non-null trusted ceilings for plan steps, elapsed time,
input tokens, output tokens, model calls, embedding calls, tool calls, and
versioned synthetic estimated cost units. Counters are monotonic. A model
cannot raise a ceiling. Exhaustion fails safely before the next side effect.
Aspect 1 defines dimensions and enforcement semantics, not production default
values.

## Security, privacy, and observability

Checkpoint state is serialized as validated JSON. Pickle, arbitrary Python
objects, executable deserialization, and fallback object codecs are forbidden.
The future MCP listener defaults to loopback MCP on `127.0.0.1`; non-loopback
binding requires a later explicit security decision.

The capability set contains no arbitrary file, Shell, network, SQL, or dynamic Python tool.
There is no raw filesystem browser, command runner, general URL
fetcher, arbitrary SQL executor, or eval facility.

The Agent does not save, emit, trace, or display chain-of-thought. Raw prompt,
completion, reasoning, scratchpad, credential, authorization value, cookie,
or document body is excluded from checkpoint and telemetry contracts. Existing
`reasoning_delta` remains frozen only as a legacy wire name; no Aspect 1 code
changes or expands it. Logs and spans use structured status, safe summaries,
hashes, counts, IDs, and redacted error classes.

The hard security gates are zero approval bypass, zero duplicate side effects,
and zero cross-project leakage.

## Compatibility and rollback

Aspect 1 adds no public route, REST/SSE event, SQL migration, dependency,
runtime switch, worker, UI, MCP listener, Redis connection, or telemetry
exporter. Its rollback boundary is the new ADR/baseline/protocol documents,
fixtures, tests, and two pure Python contract modules. Existing user-owned
dirty files must never be reset or overwritten during rollback.
