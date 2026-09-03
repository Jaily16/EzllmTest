# EzLLM Test v0.1.0-preview.1 — Iteration 5 Source Preview

Release channel: Source Preview
Product release: 0.1.0
Git tag: v0.1.0-preview.1
Docker images published: No
Iteration 5 status: Aspect 8 executed but incomplete (Blocked)

## Scope

This preview packages the reviewed Iteration 5 Aspect 1–8 source changes, tests,
contracts, architecture notes, operations documentation, and offline CI checks.
It is a source preview for review and reproducibility; it is not a stable or
production release.

The source preserves the 19 workflow definitions, 22 typed tools, legacy and
Agent REST/SSE entry points, and MCP schemas. The preview does not intentionally
change artifact, revision, cache, RAG, retention, budget, checkpoint, approval,
lease, idempotency, cancellation, recovery, or project-isolation behavior.

## Existing evidence

The reviewed offline evidence records:

- full pytest: `727 passed, 32 skipped`;
- Agent Eval: `104/104`;
- deterministic Agent Acceptance: `18/18`;
- Acceptance dataset SHA-256:
  `44D8CAD27AA17365A6AA85300A2A7261275438AE162D3DA316371B0EFF4E1674`;
- deterministic Agent Benchmark: two isolated runs completed;
- modular topology: task-owned dependency and process lifecycle checks completed;
- frontend source/type/build/bundle checks and external Prettier evidence completed.

`actual_topology_probe` and `deterministic_business_acceptance` are reported as
separate evidence classes. Readiness probes and controlled ASGI acceptance do
not claim a complete network Agent workflow journey.

## Explicit limitations

The Docker full-stack topology and dual-topology parity remain `Blocked`. The
Docker Engine/Desktop was unavailable for the final source-preview operation,
and no restart, build, up, down, pull, or registry operation was performed.
The local repository `npm run format:check` environment remains limited by the
ignored `node_modules` installation; the clean/external formatter evidence is
recorded separately.

These limitations mean that Aspect 8 and Iteration 5 must remain marked as
incomplete/blocked. This preview does not make a production-readiness claim.

## Docker publication boundary

The source may contain Dockerfiles, Compose files, container contracts, and
static delivery checks. The following product images are **not published**:

- `ezllmtest/backend:0.1.0`;
- `ezllmtest/frontend:0.1.0`.

No Docker registry login, image build, tag, push, manifest operation, or Docker
release asset is part of this preview. A future container release requires a
separate successful full-stack and parity acceptance.

## Safety and evidence boundaries

No real `.env`, uploaded project, user MySQL/Redis/observability data, ordinary
Compose volume, provider, embedding service, or paid call was accessed for this
preview. The SQL, prompt, historical fixture, and prior Aspect evidence hashes
remain protected. `removed_paths=[]`.

Release notes and reports contain no API keys, passwords, database or Redis
URLs, project IDs, request bodies, tracebacks, raw logs, screenshots, or user
content.

## Reproduction boundary

The source-only checks can be reproduced with the repository's documented
offline Python and frontend quality commands, using the existing isolated
environment where available. Docker runtime validation is intentionally not a
reproduction step for this preview and remains a separately blocked operation.

## Release classification

`v0.1.0-preview.1` is a GitHub **source preview** only. It is not a stable
release, production release, Docker image release, or declaration that
Iteration 5 is complete.
