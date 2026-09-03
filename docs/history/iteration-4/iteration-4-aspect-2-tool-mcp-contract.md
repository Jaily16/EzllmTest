# Iteration 4 Aspect 2 — Typed Tools and MCP Interoperability

## Status and boundary

Aspect 2 publishes a transport-neutral registry of **22 tools**: three
read-only project status queries and **19 workflow** tools derived from the
existing **workflow catalog**. The catalog remains the sole source of business
operations, ordering, prerequisites, artifact policy, and workflow budgets.

The internal Agent adapter invokes the existing **application service layer**
in process. It never calls this application through HTTP or MCP. **No public FastAPI route change**
is made, and the existing REST/SSE wire formats remain frozen. LangGraph
execution, Redis state, runtime HITL, and durable idempotency remain deferred
to **Aspect 3** and later approved aspects.

## Tool input and trusted authority

Every tool has a strict Pydantic input schema with unknown fields forbidden.
Workflow schemas preserve their existing payload fields and add only
`model_label` and `regenerate`. Project ID, actor, scope, approvals,
idempotency records, credentials, prompts, raw documents, and hidden reasoning
are never model-visible arguments.

The project scope comes from the **trusted runtime** as a
`TrustedProjectScope`. An internal or MCP invocation cannot replace it. A
workflow call must match the current structured plan, model label, canonical
arguments, risks, source revision, budget, and unexpired human approval. A
missing or invalid binding yields `approval_required` before any workflow
service is invoked.

Risk policy is fixed as follows:

- Read-only status tools use `read_only` and require no approval.
- Every workflow is `paid`; artifact workflows are also `persistent`.
- `regenerate=true` always means `paid + persistent + regenerate`.
- Persisted workflows retain the existing artifact identity, exact-cache, and
  regeneration-lock behavior. Session-only calls declare run-step
  idempotency; no Redis-backed guarantee is claimed in Aspect 2.

## Execution adapter

`workflow_project_analysis` consumes the existing `stream_test_plan` service;
the other 18 workflow tools consume `stream_llm_workflow`. The adapter forwards
only sanitized monotonic progress and aggregates structured result, artifact,
cache, revision, completion, and usage metadata. Every `reasoning_delta` is
dropped. It does not create a new save path, so delayed persistence,
cancellation, stale detection, failure rollback, and regeneration locking stay
inside their current services.

Cancellation propagates as `asyncio.CancelledError` into the existing async
generator. Expected service failures retain stable safe codes; unexpected
exceptions become `internal_error` without paths, SQL, provider bodies,
credentials, or tracebacks.

## MCP v2 surface

The standalone adapter uses the official MCP Python SDK v2 low-level `Server`
so the workbench registry and MCP publish identical JSON schemas. It implements
the protocol families **tools**, **resources**, **prompts**, **progress**,
**cancellation**, and **errors**:

- 22 typed tools with conservative annotations and structured success output.
- `ezllm://tool-catalog/v1`, containing only static schemas and metadata.
- `ezllm://approval-policy/v1`, containing only static HITL rules.
- `plan_test_workflow(goal)`, a user-selected static prompt template that does
  not invoke a model or reveal a project identifier.
- Server-to-client progress is monotonic and contains no reasoning content.
- Model-correctable failures use MCP tool errors; missing approval or scope
  mismatch is a host-visible protocol error that the model cannot self-fix.

The Streamable HTTP app is separate from the public FastAPI app, uses `/mcp`,
defaults to stateless streaming responses, and binds only to **127.0.0.1**. The
CLI has no host option, and the SDK's localhost Host/Origin protection remains
enabled. The default loopback context can execute only the three read-only
tools; workflow tools remain discoverable but blocked until a future trusted
host injects a valid approval context.

The server exposes no project document or artifact resource, no arbitrary file tool,
no arbitrary shell tool, no arbitrary network tool, no SQL tool, no dynamic
Python tool, no roots, no sampling, and no protocol logging.

## Dependency and compatibility evidence

The only new direct dependency is `mcp==2.1.1` without the CLI extra. Before
the manifest changed, the complete Iteration 3/Aspect 1 backend baseline passed.
An isolated Python 3.11 environment then resolved the original requirements
plus MCP, passed `pip check`, and imported the SDK Client and low-level Server.
The original Iteration 3 manifest hashes remain immutable historical evidence;
`iteration4_aspect2_manifest_v1.json` layers the approved requirements change
over that parent snapshot.

No real `.env`, provider API, embedding service, MySQL database, or project
document is used by Aspect 2 tests.
