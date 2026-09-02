# Iteration 4 Aspect 6 — Agent Eval, reliability, and security contract

Status: accepted and implemented for Aspect 6. Aspect 7–8 are deferred.

## Frozen compatibility boundary

Aspect 6 adds an offline evaluation harness and no public route, SQL migration,
dependency, frontend feature, Compose service, telemetry exporter, or CI job. The
19 workflow catalog entries and the shared 22-tool registry remain the business
and tool sources of truth. Legacy REST/SSE, Agent API/SSE, MCP schemas, artifact
identity, revision, RAG, cache, stale, cancellation, rollback,
regeneration-lock, retention, and budget semantics are unchanged.

## Versioned offline evidence

`iteration4_agent_eval_v2.json` contains 39 golden tasks: one catalog/schema
selection case for every typed tool and seventeen normalized Agent journeys.
`iteration4_agent_security_v1.json` contains 47 named attacks. The reliability
fixture contains 18 Redis-backed cases. All fixtures use seed `20260827`, two
invented similarly named project slots, and provider `deterministic_fake`.

The historical v1 Agent dataset remains immutable. V2 records its parent hash
and corrects preliminary expectations against the implemented Aspect 2–5
contracts without changing the historical file. There is no automatic
"accept current output" command.

The runner loads only strict UTF-8 JSON from the fixed fixture directory,
rejects duplicate keys and non-finite numbers, and dispatches only an allowlisted
scenario enum. Fixture content cannot name code, modules, files, commands,
providers, projects, or output paths for execution.

## Runtime and security coverage

The core suite projects actual metadata from the shared registry and validates
the deterministic lifecycle against the current risk, approval, retention,
cache, RAG, and usage contracts. It never calls a workflow provider.

The attack suite invokes the implemented planner authority validation, exact
approval binding, strict checkpoint serializer, project/graph storage identity,
loopback Host middleware, MCP capability boundary, and report redaction. It
covers prompt injection, runtime-owned planner fields, forged or stale
approvals, arbitrary file/Shell/network/SQL/Python capabilities, cross-project
scope changes, non-loopback protocol access, unsafe constructors and types,
oversized/deep data, and sensitive-data sentinels.

Offline prompt-injection results prove that runtime authority is not obtained
from hostile goals or planner output. They do not claim that a real model is
intrinsically resistant to prompt injection.

Reliability cases use credential-free loopback Redis with unique test prefixes.
They exercise fenced leases, command/idempotency reuse, one-time approval
nonces, cancel markers, outcome-unknown handling, completed-result
reconciliation, active-run exclusion, bounded replay, Redis loss, and warm-cache
zero-call behavior. The existing two-process SQLite/Redis crash-recovery test
remains part of the authoritative full pytest gate and proves that persisted
effects reconcile once after worker restart.

## Measurement and decision

Applicable deterministic gates require 100% task success, trajectory validity,
tool selection, structured-output disposition, recovery, and attack blocking.
Hard safety requirements are zero approval bypass, zero duplicate side effects,
zero cross-project leakage, zero budget overrun, zero arbitrary-capability
execution, and zero sensitive-data leakage. Warm exact-cache adds zero model and
embedding calls.

RAG regression reuses the Aspect 5 fixed corpus and keeps `dense_v1`: recall@4,
MRR, nDCG@4, and citation coverage remain 1.0 on the synthetic slices, with
zero invalid citations or project leaks. These are fixture-specific correctness
values, not general retrieval-performance claims.

Logical-clock timings are deterministic evidence only. Wall-clock performance
and OpenTelemetry overhead are `N/A` with reason
`controlled_performance_and_telemetry_deferred_to_aspect7`. Synthetic Token and
cost units are not provider currency. Real-model evaluation requires separate
cost approval and has no CLI switch in Aspect 6.

## Controlled CLI and safe output

The only entry point is:

```text
python -m app.agentEval --suite core|security|reliability|all --format text|json
```

It accepts no dataset, model, provider, project, Redis URL, host, output path,
or arbitrary command option. Reliability reads `EZLLM_TEST_REDIS_URL`, accepts
only unauthenticated loopback Redis database 0, and fails closed when it is
missing. Output contains case IDs, normalized trajectory labels, counters,
stable error codes, environment versions, hashes, metrics, and gate decisions.
It excludes goals, prompts, completions, reasoning, document bodies,
credentials, local paths, Redis URLs, project identities, and tracebacks.

Exit codes are 0 for a passed gate, 1 for a deterministic gate failure, and 2
for an invalid fixture or environment. Output is stdout/stderr only; no report,
database, Redis dump, trace, coverage, or benchmark artifact is written to the
repository.
