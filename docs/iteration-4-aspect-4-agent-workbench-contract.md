# Iteration 4 Aspect 4 — Agent workbench contract

Status: implemented for Aspect 4. This contract adds the local user-facing workbench and its isolated control API. It does not implement Aspect 5–8, OpenTelemetry, Compose, CI, or a second Agent.

## Process and trust boundary

The legacy FastAPI application remains on port 8130 with its Iteration 3 routes and REST/SSE formats unchanged. The Agent API is a separate process started with `python -m app.agentApi --port 8131`; it has no host option and always binds `127.0.0.1`. The worker remains the only process that invokes the LangGraph graph. API and worker construct the runtime through the shared `agentRuntimeFactory` but own separate Redis connections.

The browser uses `VUE_APP_AGENT_API_BASE_URL`, while all existing workflows continue to use `VUE_APP_API_BASE_URL`. The API accepts only loopback Host values, exact configured CORS origins, no credentials, and GET/POST/OPTIONS. Project scope is constructed only after the path project is verified: actor is `local-workbench` and scope version is `iteration4-aspect4-v1`. Neither request bodies, query parameters, planner output nor tool arguments can supply these authority fields.

The workbench and MCP retain the same Aspect 2 typed tool registry. The runtime invokes the in-process application-service adapter. It never calls its own HTTP or MCP endpoint.

## API v1

All ordinary responses use `{status, reason, data}`. Validation, conflict, not-found/expired, unavailable and unexpected errors use stable, redacted Agent error statuses. FastAPI validation details, paths, Redis configuration, SQL, credentials and tracebacks are not returned.

| Method | Path | Contract |
|---|---|---|
| GET | `/health` | Redis, worker heartbeat, API schema and graph version only |
| GET | `/agent/v1/capabilities` | public models, two budget presets, risks and `not_instrumented` trace state |
| GET | `/agent/v1/projects/{pid}/runs` | project-scoped, maximum 50, cursor pagination |
| POST | `/agent/v1/projects/{pid}/runs` | explicit create and queue; one active run per project |
| GET | `/agent/v1/projects/{pid}/runs/{thread_id}` | redacted snapshot, plan, budget and evidence |
| GET | `/agent/v1/projects/{pid}/runs/{thread_id}/events` | resumable Agent SSE |
| POST | `.../{thread_id}/approval` | `approved` or `rejected` plus current plan hash |
| POST | `.../{thread_id}/edit` | edit goal only, then replan |
| POST | `.../{thread_id}/cancel` | idempotent for completed/cancelled runs |
| POST | `.../{thread_id}/recover` | retryable failed runs only, subject to active-slot fencing |

The SSE protocol uses `id: <sequence>` and `event: agent_event`. Durable kinds are queued, planning, approval required/submitted, replanning, cancel requested, executing, bounded progress, tool success/failure, stale, recovering, completed, cancelled and failed. `after_sequence` and `Last-Event-ID` resume from a known sequence. A retention gap emits `replay_reset`, after which the browser reloads the snapshot. Heartbeats are comments and terminal events close the stream. SSE never carries tool-result bodies, prompts, reasoning, `reasoning_delta`, chain-of-thought, approval nonce, idempotency keys, credentials or tracebacks.

## Run index, evidence and liveness

Each trusted project scope has one TTL-bound active key. Fixed Lua operations reserve, commit and release the slot with compare-and-delete semantics. Created/planning/awaiting approval/executing/validating/recovering are active. Completed, cancelled and failed release it; recovery must reacquire it. Run metadata and the project index expire after the configured 7 days, and read/list operations do not extend TTL. Missing Redis state is reported as not found or expired and never mutates the valid MySQL artifact.

The worker refreshes a 30-second heartbeat while idle polling and while a graph command is executing. The UI therefore distinguishes queued work from a temporarily unavailable worker without inventing a trace.

Evidence is written only after a completed idempotency record. A completed replay reconstructs missing evidence without another tool call. Persisted evidence contains only artifact key, revision, save/cache flags, usage and an existing workspace route; it does not copy the artifact body. Session-only evidence contains its structured result in run-scoped Redis, expires with the thread and never enters MySQL. Strict safe JSON applies a 4 MiB per-item limit and rejects constructors, pickle-like objects, non-finite numbers and sensitive keys. Progress is normalized to 0–100, accepted monotonically per step/stage and deduplicated in 5% buckets.

## Approval, cancellation and budget

Clients choose only `focused` or `standard`; numeric limits are derived server-side from current workflow budget profiles. Focused permits 3 steps/tools, 20 minutes, 12 model calls and 6 embedding calls. Standard permits 8, 45 minutes, 32 and 16. Token limits are model-call count multiplied by the current catalog maximum context/final-output budgets. Cost is labeled `synthetic_test_unit` and is not money. A run cannot expand its preset.

Every paid, persistent or regenerate step requires a server-validated approval binding. The browser sends only decision and expected plan hash. Project, revision, model, arguments, budget or plan changes invalidate approval. Expired approval cannot execute. Editing changes only the goal and returns to planning. Cancelling an interrupt submits a trusted rejected resume; other active states set the Redis cancellation flag. A committed side effect is reconciled, while the next side effect is blocked.

## Browser workbench

`/agent` is a lazy child route with a project-ready guard separate from the ten legacy workflow guards. Loading the page performs only capabilities, list, snapshot and event GET requests. Only the explicit “创建运行” button sends the create POST. Local storage remembers only a selected thread ID and is never the recovery source.

The page shows goal/model/preset controls, plan and risks, an accessible approval dialog, monotonic timeline, persisted/session evidence, limits/usage, recent runs and diagnostics. Session results are marked “仅 Agent thread 保留 7 天，不写入项目 artifact”. Diagnostics display run/thread IDs, worker and expiry, and exactly `Trace ID 尚未启用（Aspect 7）`; `trace_id` remains null. Layout is single-column from 360 px and two-column from 1024 px. Dialog focus enters and returns, Escape is provided by Element Plus, controls meet the 44 px target, status uses an atomic live region, errors use alerts, motion preferences and forced colors are respected, and leaving the route aborts the stream.

## Frozen and deferred behavior

No dependency, SQL, workflow catalog, legacy route, legacy REST/SSE, artifact, revision, RAG, cache, cancellation, stale, rollback, regeneration-lock or retention contract changed. No provider, embedding or MySQL call occurs merely by viewing the workbench. OpenTelemetry remains deferred to Aspect 7: `trace_id=null` and `trace_status=not_instrumented` are truthful protocol values, not fabricated telemetry.
