# Iteration 4 Agent measurement protocol v1

## Evidence classes

The protocol separates three kinds of evidence:

1. The current Iteration 3 workflow baseline, measured against existing code.
2. The Aspect 1 reference state model and deterministic synthetic data.
3. A future LangGraph/Redis/MCP/OpenTelemetry runtime, which does not exist in
   Aspect 1 and must be reported as unavailable rather than simulated.

No real provider, embedding endpoint, MySQL instance, project, credential, or
external network is permitted. The default provider identifier is
`deterministic_fake`.

## Dataset

The versioned dataset is
`ez_back_dev/tests/fixtures/iteration4_agent_eval_v1.json`, schema 1, dataset
version 1.0.0, with fixed seed 20260827. It contains two intentionally similar
but isolated synthetic projects and only invented requirements, design, and
knowledge text.

The matrix covers read-only status, first preliminary analysis, exact cache,
warm RAG reuse, session-only and persisted cases, regeneration, rejected and
expired approval, revision change, cancellation, interruption recovery,
failure rollback, invalid structured output, cross-project isolation,
approval bypass attempts, and same-revision index reuse.

Each case declares the expected catalog operation, risk set, approval outcome,
terminal state, artifact policy, side-effect count, cache/RAG behavior, and
model/embedding/tool call expectations. Synthetic prices are
`estimated_cost_units`; they are versioned test weights, not provider currency
or a current price claim.

## Metric dictionary

- Correctness: task success, trajectory validity, tool selection accuracy,
  structured output validity, and recovery success.
- Safety: approval bypass count/rate, duplicate side-effect count, and project
  isolation violation count. Each count has a hard expected value of zero.
- RAG: recall@k, MRR, index build count, and index reuse count.
- Latency and capacity: p50, p95, TTFE, and throughput in tasks per second.
  TTFE is time to the first safe structured progress/result event, never a
  reasoning token.
- Cost drivers: model, embedding, and tool call counts; input/output tokens;
  `estimated_cost_units`; and cache hit rate.
- Observability: OpenTelemetry p95 overhead ratio, only when a real approved
  runtime is installed and measured.

## Deterministic correctness protocol

The fake provider returns predefined structured values, usage counters, and
logical-clock event offsets. Tests block network, provider factory, embedding,
MySQL, and real project loading. Golden correctness gates are:

- task success, trajectory validity, tool selection, structured output, and
  recovery are 100% for their applicable deterministic cases;
- approval bypass, duplicate side effects, and project leakage are zero;
- a warm exact-cache result adds zero model and embedding calls;
- all state transitions, budgets, approvals, and payloads validate against the
  strict contract.

## Performance protocol

Each future wall-clock case uses 5 warm-ups followed by 30 measured samples.
No sample or outlier is discarded. The matrix records concurrency 1 and 4,
small and large synthetic inputs, and cold, warm, recovery, cancel, and failure
modes. It records environment identity, commit, manifest hashes, fixture
version, seed, and telemetry mode.

Percentiles use the nearest-rank rule on sorted values. p50 and p95 are
reported in milliseconds. Throughput is completed tasks divided by measured
wall time. Deterministic unit tests use a fake clock; wall-clock values are
observations and are never exact test assertions.

Relative gates compare the same machine, fixture, command, concurrency, and
environment:

- future legacy p95 must not exceed the captured baseline by more than the
  ratio 1.15;
- future real OpenTelemetry enabled p95 overhead must not exceed 5%;
- a zero/missing baseline, changed environment, or insufficient sample count
  produces N/A rather than pass.

Aspect 1 records no claimed improvement. It does not infer speed from test
duration or deterministic logical time.

## OpenTelemetry availability

No OpenTelemetry runtime is installed by Aspect 1. Therefore
`otel_overhead_ratio` is N/A with reason `runtime_not_installed`. A no-op local
stub must not be presented as OpenTelemetry overhead. The metric becomes valid
only after an explicitly approved package set is installed and the same
disabled/enabled workload is measured.

## Safe result storage

Benchmark output contains only case IDs, versions, environment metadata,
counts, timings, ratios, safe error codes, and aggregate results. It excludes
raw prompts, completions, chain-of-thought, document bodies, credentials,
provider response bodies, and real project identifiers. Aspect 1 keeps
benchmark results in test output and the development log; it does not create
an unreviewed report dump in the repository.
