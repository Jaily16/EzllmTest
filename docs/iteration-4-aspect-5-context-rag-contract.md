# Iteration 4 Aspect 5 — Context, RAG evidence, and memory contract

Status: accepted and implemented for Aspect 5. Aspect 6–8 work is deferred.

## Frozen compatibility boundary

Aspect 5 adds no dependency, SQL migration, public route, or SSE event. The 19
workflow operations remain the business capability source of truth. Legacy
8130 REST/SSE and all eight existing test pages retain the existing dense
retrieval path, artifact identity, revision, cache, stale, cancellation,
rollback, regeneration-lock, retention, and Token limits.

## Trusted context assembly

Prerequisite artifact bodies such as `info`, `unit_info`, and
`integration_object_info` are runtime-owned. They are removed from the
model-visible planner schemas and cannot be supplied by planner output.

Before approval, the worker resolves each prerequisite against the trusted
project scope and source revision and stores only a `ContextBinding`: payload
field, source operation and artifact key, revision, input hash, prompt version,
model label, result path, and content SHA-256. The binding participates in the
plan and approval hashes. Any change to artifact content, revision, selection,
model, or plan invalidates the approval.

Immediately before a side effect, the worker reloads the exact valid MySQL
artifact, verifies all binding fields, extracts the required value, and injects
it into the existing workflow payload in process memory. Missing, stale,
ambiguous, mismatched, or malformed context is a fail-closed outcome with zero
tool side effects. A pre-Aspect-5 checkpoint with an unbound body cannot execute:
it must replan or be cancelled. Artifact bodies never enter LangGraph state,
Redis checkpoints, timeline events, evidence, MCP output, API output, logs, or
errors.

## Memory hierarchy

- LangGraph checkpoint: goal, structured plan, approval, metadata references,
  hashes, budgets, counters, and safe error categories only.
- Redis thread evidence: session-only structured results for seven days; never
  cross-thread or cross-project long-term memory.
- MySQL: the only long-term truth for project revision and valid persisted
  artifacts.
- RAG index: process-local, bounded by the existing capacity and idle TTL, and
  scoped by trusted project, corpus, revision, embedding identity, and policy.

No chat history, user profile, model-generated summary memory, cross-project
memory, or vectorized Agent conversation is added.

## Agent retrieval and citations

Three dependency-free policies are implemented for offline comparison:

- `dense_v1`: the frozen `InMemoryVectorStore` scoring and bounds.
- `hybrid_rrf_v1`: dense plus Unicode NFKC BM25, fused with deterministic RRF.
- `hybrid_rerank_v1`: deterministic identifier and term-coverage reranking of
  the hybrid candidate set; it performs no model call.

The Agent-only context variable is established inside an approved worker tool
invocation. Without it, `get_project_retriever()` returns the exact legacy
`BoundedRetriever`. All policies retain `top_k=4`, `fetch_k=8`, the existing
minimum score, de-duplication, and the 6,000 context-Token ceiling. An exact
artifact cache hit creates no retriever and therefore adds no model, embedding,
index, or citation work.

Only chunks actually supplied within the context budget receive citations.
Each citation contains `[C1]`-style step-local ID, corpus, sanitized basename,
one-based page, rank, finite six-decimal score and type, plus a SHA-256 binding
trusted scope, revision, corpus, source label, page, and normalized content.
Neither excerpt nor absolute path is stored or returned. Prompt text may carry
the citation ID, while checkpoints and evidence retain metadata only.

`ToolExecutionResult` and `AgentStepEvidence` add optional retrieval evidence.
The workbench renders source, page, rank, score kind, and chunk hash with normal
Vue text interpolation—never `v-html`. The Agent v1 route and SSE event set are
unchanged. Capabilities report the policy and metadata-only citation mode.

## Synthetic adoption protocol and decision

`iteration4_rag_eval_v1.json` is a fixed-seed (`20260827`) synthetic dataset
with two similarly named isolated projects, three corpora, small/large sources,
Chinese and English terms, identifiers, paraphrases, rare terms, distractors,
and cross-project traps. Deterministic fake token-hash embeddings are the only
dense source; provider, real embedding, MySQL, filesystem project, and network
paths are not used.

Correctness covers recall@4, MRR, nDCG@4, citation coverage, invalid citations,
project leakage, context Tokens, build/reuse counts, model calls, and embedding
builds. The frozen performance protocol uses five warmups and thirty retained
samples for concurrency 1/4, small/large, and cold/warm. Adoption requires every
slice to be no worse than dense, overall nDCG@4 improvement of at least 0.05,
100% citation coverage, zero invalid citations/leaks, bounded context and call
counts, and the specified relative p95 limits. Rerank additionally requires
0.03 nDCG@4 over a qualified hybrid and at most 1.10× query p95.

The deterministic fixture produced nDCG@4 `1.000000` for dense, hybrid, and
rerank, so neither candidate meets the required relative quality gain. The
Aspect 5 environment is also not accepted as a controlled long-lived
performance host, so comparable p95 values are `N/A`. The versioned decision
therefore keeps `dense_v1`; it does not claim hybrid performance or a general
improvement. Hybrid can be enabled only after the same fixture and protocol
pass every automatic gate on a comparable host.

## Security and recovery invariants

Project authority is injected by the trusted runtime. Retrieval rejects a
project mismatch before indexing or querying. Citation values are strict JSON;
non-finite scores, bodies, absolute paths, credentials, prompts, reasoning, and
tracebacks are excluded. Recovery reuses the bound context identity and the
existing idempotency result; it does not repeat a paid/session side effect or
turn Redis evidence into MySQL memory. Redis loss may expire the thread but
cannot delete or invalidate a MySQL artifact.
