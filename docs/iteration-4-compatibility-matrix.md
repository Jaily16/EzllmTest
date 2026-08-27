# Iteration 4 Aspect 1 compatibility matrix

Status: static compatibility spike only. **No dependency was installed. No integration test was run.**
No requirements, lockfile, Compose file, runtime
switch, Redis connection, MCP listener, or exporter was created.

| Component | Candidate / constraint checked | Current intersection | Aspect 1 status and risk |
| --- | --- | --- | --- |
| LangGraph 1.2.11 | Python >=3.10; `langchain-core >=1.4.7,<2`; Pydantic >=2.7.4 | Python 3.11.15, langchain-core 1.5.6, Pydantic 2.13.4 | Nominal static compatibility. Selected single-Agent runtime remains locked; executable validation is deferred. |
| langgraph-checkpoint-redis 0.5.2 | `langgraph-checkpoint >=4.1.1,<5`, Redis client >=5.2.1, RedisVL >=0.15,<1 | None of these Agent/Redis packages is in the current manifest | Constraint intersection recorded only. Serializer, setup/asetup, TTL, and recovery behavior require a later approved isolated spike. |
| Redis 8 capability | RedisJSON and RediSearch are required by the candidate checkpointer | No Redis service or image is configured | Redis 8 capability is the target; no mutable image tag or digest is selected in Aspect 1. MySQL remains artifact authority. |
| MCP Python SDK 2.1.1 | Python >=3.10, Pydantic >=2.12, Starlette >=0.27, Uvicorn >=0.31.1; protocol generation 2026-07-28 | Python/Pydantic/Uvicorn nominally intersect; package absent | Future adapter uses Streamable HTTP and binds to loopback. Old v1/FastMCP/SSE examples are not an implementation contract. |
| OpenTelemetry | Structured span/metric semantics, redaction, bounded attributes, OTLP only after approval | No SDK/exporter dependency exists | **protocol-only, install deferred**. SDK/exporter pinning and overhead evidence are intentionally not claimed. |

## Cross-component decisions

- Python 3.11 remains the runtime baseline even though the host also has a
  Python 3.12 command.
- Pydantic v2 strict JSON models are the checkpoint boundary. Pickle and
  arbitrary object serialization are prohibited even if a future library
  offers them.
- The checkpointer must preserve thread/checkpoint state only. Durable project
  and valid artifact authority remains MySQL.
- Redis loss must be recoverable by reconciling the trusted project/revision,
  MySQL artifact state, and idempotency result before another side effect.
- Workbench and MCP share typed definitions; MCP never calls local REST routes
  to execute a tool.
- MCP defaults to `127.0.0.1`. Authentication, non-loopback exposure, reverse
  proxying, and container publication are outside Aspect 1.
- OpenTelemetry attributes must exclude prompts, completions, reasoning,
  documents, credentials, and provider response bodies.

## Known compatibility risks

1. MCP v1-to-v2 examples and protocol transport names are breaking-change
   hazards; only the selected v2 generation may inform later implementation.
2. The Redis checkpointer requires search/JSON capabilities and explicit
   setup; a plain Redis compatibility assumption is insufficient.
3. LangGraph, checkpointer, Redis, MCP, and OpenTelemetry transitive ranges
   must be resolved together before a manifest edit. Nominal pairwise
   compatibility is not proof of an installable lock set.
4. Checkpoint serialization and encryption configuration can silently weaken
   safety if an implementation enables pickle or arbitrary types.
5. Telemetry packages and semantic conventions can move independently; an
   SDK version is not selected until an approved offline resolver spike.

## Gate for any later dependency proposal

A later Aspect 1 follow-up may propose exact pins only after explicit user
approval. It must use an isolated environment, preserve the three manifest
hashes in the frozen snapshot until the proposal is accepted, perform no
provider or database call, and report resolver output separately from runtime
integration evidence. This matrix does not grant installation authorization.
