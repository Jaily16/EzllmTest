# Iteration 4 Aspect 7: Observability, Performance, and Delivery Contract

Status: accepted and implemented for Aspect 7. Aspect 8 remains out of scope.

## Frozen compatibility boundary

Aspect 7 does not change the 19 workflow catalog entries, the 22 typed tools,
legacy or Agent REST/SSE event shapes, MCP tool/resource/prompt schemas,
artifact identity, revision-aware cache and RAG behavior, cancellation, stale
handling, rollback, regeneration lock, retention, or hard-budget semantics.
The legacy FastAPI application is not instrumented automatically and remains
unchanged. Agent instrumentation is manual and is a no-op without an Agent
telemetry context.

OpenTelemetry is disabled by default for ordinary local processes and enabled
explicitly by Compose. An unavailable exporter may change only safe telemetry
health counters and logs; it cannot change an Agent result, approval decision,
checkpoint, artifact, retry, or cancellation outcome.

## Telemetry and logging contract

`TelemetrySettings` accepts only an explicit enabled flag, a loopback OTLP/gRPC
endpoint or `otel-collector:4317`, a controlled service name, a bounded export
timeout, and a bounded metric interval. It accepts no OTLP headers or arbitrary
remote destination. The implementation uses `BatchSpanProcessor`,
`PeriodicExportingMetricReader`, and bounded shutdown/flush behavior.

The stable schema is `iteration4-aspect7-v1`; safe GenAI attributes use policy
`otel-genai-safe-v1`. Manual spans cover Agent API and MCP requests, command
enqueue/dequeue, worker processing, Agent run and graph nodes, planning,
provider chat/embedding calls, typed tools, retrieval, checkpoint operations,
validation/recovery, and Agent SSE. A validated `TraceCarrier` propagates W3C
trace context through Redis commands. Recovery uses a link when a new process
cannot preserve a direct parent relationship.

Spans, metrics, and JSON logs never record prompts, completions, reasoning,
messages, tool arguments/results, retrieval query text, project/document body,
absolute path, SQL, Redis URL/key, credential, traceback, or exception stack.
Failures record only a stable error type and span status. Logs use a fixed
allowlist of time, level, service, event, trace/span IDs, run/thread IDs,
operation, status, cache, stable error code, and numeric measurements.

Metric labels are restricted to operation, status, model label, retention,
cache, strategy, corpus, and command/checkpoint kind. Project, run, thread,
revision, URL, Redis key, and error text are forbidden labels. Metrics cover
run count/duration/active, planning and approval wait, command queue/reclaim,
tool/model/retrieval/checkpoint duration and counts, Token/context usage,
recovery/cancel/budget exhaustion, SSE connection/TTFE/replay reset, and
telemetry export/drop state.

## Public projection

No public route was added. `AgentRunView.trace_id` is either a validated
32-character lowercase hexadecimal value or null. `trace_status` is
`not_instrumented` or `instrumented`; the latter means the SDK recorded the
run, not that an exporter persisted it. Health and capabilities expose only
the telemetry mode, schema, and safe policy. They never expose traceparent,
span ID, sampling configuration, exporter address, or credentials.

The Agent workbench shows `未启用` when the run has no trace. A valid trace ID
can be copied and, only when a loopback Grafana base URL is configured, opened
in Grafana Explore. Page load remains GET-only and does not call a model,
embedding, retriever, tool, or index builder. MCP remains read-only by default
and uses only its existing safe trace-correlation metadata.

## Performance and Vite adoption

`python -m app.agentBenchmark --suite legacy|agent|all --telemetry
disabled|enabled|compare --format text|json` is the only benchmark entry point.
It accepts no provider, model, project, Redis URL, output path, host, or file
argument. It uses deterministic fake planner/provider/tool behavior, a fixed
synthetic workload, temporary SQLite, and a credential-free loopback Redis URL
from the environment. It performs five warmups and thirty measured samples,
keeps every sample, and reports only safe environment hashes and aggregates.

The first real pre-change wall-clock baseline is frozen in
`iteration4_aspect7_prechange_performance_v1.json`; Aspect 1 history was not
rewritten. The measured result is frozen in
`iteration4_aspect7_performance_gate_v1.json`. On the captured Windows host,
legacy p95 was 1.0394 times the parent baseline (limit 1.15), and telemetry-on
workload p95 was 1.0217 times telemetry-off (limit 1.05). Exact-cache cases
added zero model and embedding calls. These are environment-specific results,
not universal performance claims.

The Vite migration retained `serve`, `build`, and `lint`, added `type-check`,
uses typed `import.meta.env`, disables source maps, keeps static ESM assets and
lazy routes, and supports all three approved `VUE_APP_*` public variable names.
Build p95 improved by more than the required 5 percent and dev-ready p95 did
not regress. Initial JavaScript, initial CSS, initial total, and full build
ratios were 0.6624, 1.0361, 0.9236, and 0.9289 respectively, all within the
1.05 limit. Select component CSS is attached to its lazy test-target chunk so
the login path does not pay for it. No source map was emitted.

The requested `@eslint/js==10.8.0` does not exist in the registry. The isolated
resolver therefore selected the published exact compatible version 10.0.1;
all other approved toolchain versions remain exact. Vue, Element Plus, Axios,
and other runtime dependencies were not deliberately upgraded.

## Delivery and CI

The Compose topology and operational commands are documented in
`iteration-4-compose.md`. All external images and Dockerfile bases use exact
tag-and-digest references. Only frontend 8080, legacy API 8130, Agent API 8131,
Grafana 3000, and Prometheus 9090 are published, all on `127.0.0.1`. MySQL,
Redis, Collector, and Tempo remain internal. MySQL, project files, Prometheus,
Tempo, and Grafana use named volumes; ordinary operational volumes are never
automatically deleted.

Collector processors delete content-bearing HTTP, database, Redis, GenAI,
tool, and retrieval attributes before export. Prometheus scrapes only the
Collector endpoint. Tempo is local single-tenant storage. Grafana provisions
the Prometheus and Tempo data sources and the `ezllm-agent-overview` dashboard.
No Loki or debug exporter is presented as a stable logging solution.

`.github/workflows/iteration4-offline.yml` defines the Ubuntu gate for pull
requests, main pushes, and manual dispatch. It uses read-only contents
permission, cancellation concurrency, empty provider keys, no repository
secrets, fixed Redis, immutable action commit SHAs, Python 3.11, Node 24,
pytest, Eval, benchmark, frontend lint/type/build/bundle, and a real Compose
trace/metric/Grafana smoke test. It uploads no trace, database, Redis dump,
coverage, screenshot, or Eval report. The workflow is structurally and locally
validated; its hosted status remains `awaiting_explicit_push` and is not
reported as passed.

## Security and cost evidence

Tests prove disabled telemetry is a no-op, exporter failure is fail-open only
for telemetry, trace propagation crosses API/Redis/worker/graph/tool/recovery,
and sensitive sentinels cannot enter spans, metrics, logs, API, SSE, MCP, or
benchmark reports. The five viewport matrix has no horizontal overflow or
browser console error; the approval dialog traps focus, closes with Escape,
and restores focus. The Trace UI covers honest disabled and synthetic
instrumented fixture states; the Compose gate separately proves real Tempo
traces.

All Eval and benchmark providers were deterministic fakes. No real provider,
embedding, MySQL, project document, or non-required remote service was used,
and no model currency cost was incurred.
