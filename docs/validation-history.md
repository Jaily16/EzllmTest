# EzLLM Test Validation History

- Captured: 2026-09-03 (Asia/Shanghai)
- Iteration 6 evidence baseline: `b34a188ac1b5c98e869837009561f47363336821`
- Immutable source snapshot: `5cf1effb32a8efcd34902df05d27442f3586dc1c`

## Purpose and scope

[Verified] This document consolidates the validation, benchmark, acceptance,
Eval, frontend-size, real-model, CI, container, and observability evidence that
was previously distributed across Iterations 4 and 5. It is a historical audit
index, not a new test run and not a current production-readiness statement.

[Protected] Aspect 2 did not read or hash real environment files, uploaded
projects, user MySQL or Redis data, observability data, archives, artifacts,
quarantine material, user logs, or repository-external reports. It did not run
tests, builds, services, containers, providers, or embedding calls.

[Verified] Files named `docs/iteration-4-*.md` are compatibility redirects.
The canonical historical bodies are under `docs/history/iteration-4/`; all
Iteration 4 document links below therefore use the canonical location.

## Evidence semantics

| Class | Label | Meaning |
| --- | --- | --- |
| A | `[Verified]` frozen structured evidence | A tracked JSON fixture or manifest directly contains the stated value. |
| B | `[Verified]` corroborated tracked narrative | A canonical tracked document records the event and is linked or hashed by frozen evidence. |
| C | `[Candidate]` recorded result | A tracked log cites a repository-external report that is not available in this repository for independent audit. |
| D | `[Missing]` / `Blocked` | The run was not completed, the raw evidence is unavailable, or the repository cannot prove the claim. |
| P | `[Protected]` | The source is deliberately excluded from content, size, and hash inspection. |

No class-C value is promoted to class A or B. A historical pass is not a claim
that the same gate passes in the current worktree.

## Source inventory

The inventory hash policy is `sha256_canonical_lf_v1`: text is normalized to
UTF-8/LF with one trailing newline, while JSON is decoded and serialized with
sorted keys and compact separators. `Blob OID` identifies the exact Git object
at the evidence baseline. Historical manifests may contain their own hash
policy; those values are preserved separately rather than rewritten.

| ID | Canonical source | Blob OID | `sha256_canonical_lf_v1` |
| --- | --- | --- | --- |
| S01 | [Iteration 4 measurement protocol](history/iteration-4/iteration-4-measurement-protocol.md) | `789d5307a8c6cb22833ad6d5c558d3c93ef91028` | `7b31343bda8dcd9dcaa4643ee5ad883821014b70722ef150daa27764e4909d9a` |
| S02 | [Iteration 4 development log](history/iteration-4/iteration-4-development-log.md) | `605883eb168709ba96f1587a1a596fedc14608d0` | `f0880178e1b9911f197a7cf98d0991262cbbd17f4121f11bc66d8645d3746b8f` |
| S03 | [Iteration 4 closeout](history/iteration-4/iteration-4-closeout.md) | `eddb4d9dee7ed91661480f15e73985fbd3099f03` | `309d5cc938f06a13761aaeb365c5eef9c1c96958fafb168f4d317642354d8ea7` |
| S04 | [Iteration 4 live-model acceptance](history/iteration-4/iteration-4-live-model-acceptance.md) | `d6e4565ac3d580b6f8ffce6dcd10304296fce67c` | `e085676e0594bbef5045b6852934ceba024b2e3fd68c3acb6f9e0984c24778af` |
| S05 | [Iteration 4 Eval/security contract](history/iteration-4/iteration-4-aspect-6-eval-security-contract.md) | `b38f3ef51100ad9211b04f93cd1584cde4c0d09c` | `213a23edeaa1045966554dac96361e4059733e554a7fdd4d2ae27b08a02d1286` |
| S06 | [Iteration 4 observability/delivery contract](history/iteration-4/iteration-4-aspect-7-observability-delivery-contract.md) | `9d15b1dbb797536cf045612778a41a36bf445029` | `7e8cd895e041f9e2c43129eb0d61489236d949621c0b95f2e96dd9084626f476` |
| S07 | [Acceptance dataset](../ez_back_dev/tests/fixtures/historical/iteration4/iteration4_agent_acceptance_v1.json) | `30c5798a3a59b127c2ab90dcff78d1af26ecc8a5` | `6b6e6c8205c8fe2c2a44777e087ca555fc4872a71d32b9d2a55bbb17dfc60e74` |
| S08 | [Eval dataset v2](../ez_back_dev/tests/fixtures/historical/iteration4/iteration4_agent_eval_v2.json) | `7b80a5e4c8d93b77ab53182f3dec4896adcf8496` | `4240f1a0e63241f8661f6111875b3428d0b64ba7f0a0c841621db6c66f3ec14b` |
| S09 | [Aspect 6 gate](../ez_back_dev/tests/fixtures/historical/iteration4/iteration4_aspect6_gate_v1.json) | `10af3c361b739b25459b2c6e8d8a6a743ac6d5d9` | `e45b601372557a2caad8d7d80529375555c816d0046336f96a58b3a0a0954700` |
| S10 | [Aspect 6 manifest](../ez_back_dev/tests/fixtures/historical/iteration4/iteration4_aspect6_manifest_v1.json) | `f7f6f815423f1b4c63c4fe918630a77d10b32198` | `9bc830fe5be3f99d9106aaddbe3080323962ecced0a59845824c7f7e5e8ed6b2` |
| S11 | [Aspect 7 pre-change performance](../ez_back_dev/tests/fixtures/historical/iteration4/iteration4_aspect7_prechange_performance_v1.json) | `6eaedde6378c277df6ea5f6e42590e4857b6b11b` | `8c486712a8f33044c0f18d4eb1eb747e1f8de206d13a0ca1b2f341070edd69ad` |
| S12 | [Aspect 7 performance gate](../ez_back_dev/tests/fixtures/historical/iteration4/iteration4_aspect7_performance_gate_v1.json) | `076d58e9782dd2e629b452726ac064cea990a4b4` | `ab9593258111f170a25ced2955ea441a9a7379717583b2a8e80f571c6cedb6ff` |
| S13 | [Aspect 8 gate](../ez_back_dev/tests/fixtures/historical/iteration4/iteration4_aspect8_gate_v1.json) | `5dc2db148be74ba838117566fc1110975fb7032c` | `032792dc6803e1730a945a9dffb1f97541cc285db9a459601de990cb88926647` |
| S14 | [Aspect 8 manifest](../ez_back_dev/tests/fixtures/historical/iteration4/iteration4_aspect8_manifest_v1.json) | `1dcd842e22e4b671fc16ba4c6e08145bb47040f2` | `068c76a9c531f8d2178bddcbcabe8ba38181761a2a5b6fbb440c4de7b988fadb` |
| S15 | [Iteration 4 release manifest](../ez_back_dev/tests/fixtures/historical/iteration4/iteration4_release_manifest_v1.json) | `747f42ca0fa5342ec236d52aa157517315793405` | `8a3bd176e77c85d7393e1e84040f8d181a5c938267e8d98b64fb89f25a4b9235` |
| S16 | [Iteration 5 development log](development/iteration-5/development-log.md) | `124bcb325d7c673beed782a18418bb69dd82acfc` | `8264d42d22df130d98a78bc3725bbb0f1db664831662d6129423a9d5e8f6e505` |
| S17 | [Iteration 5 closeout](development/iteration-5/closeout.md) | `e00f7280ef32fa0627166e2268abbf61df99f742` | `ecd0aa21e99575eb263224cfa44adfc5fd7adeaaf06649f15f7ac814ddb0f321` |
| S18 | [Iteration 5 source preview](development/iteration-5/source-preview-v0.1.0-preview.1.md) | `93d31abaa9fadd6efe571b9d9d4f3fe7ea5f9524` | `61566abaf2de40bf49ee5481c119fb9fde8f239010bc11a290b054edbfe8ca71` |
| S19 | [Iteration 5 dual-mode baseline](../ez_back_dev/tests/fixtures/current/iteration5/iteration5_dual_mode_acceptance_baseline_v1.json) | `44db1809339a1cfb64ac7b9306935390eaa2b77b` | `a2f76a5c8a464a7a7c75cb8c5140d9d7bfdf874c12f4c3c0a92906ec9d5e0683` |
| S20 | [Benchmark CLI](../ez_back_dev/app/agentBenchmark.py) | `0d435b1a347f3b7720ba79881d89b96c3bed585b` | `96fb1630bcbb98406ac1837b1dd2b44ea0a21d67cc18a3d8590b99ee9d196f5f` |
| S21 | [Benchmark runner](../ez_back_dev/service/agentBenchmarkRunner.py) | `18e4ccf82743e1f4859814bb427cbc35d02de17a` | `711006c36af2112d231c2a42b5c02c3bf62efcc6e3e9c861f2e8546f65c2b0b2` |
| S22 | [Benchmark contracts](../ez_back_dev/service/agentBenchmarkContracts.py) | `6d09f5454ba47eda06ee4ce3129ad4ea6611f100` | `c3b39420f82d5d1b5339ff5144cd20656386a4aa9da0dacb977f8d380de0ab02` |

The Aspect 8 manifest records the Acceptance dataset SHA-256 as
`44d8cad27aa17365a6aa85300a2a7261275438ae162d3da316371b0eff4e1674`.
That is both the raw-file and canonical-LF-text hash of S07. The inventory hash
shown for S07 is instead the canonical-JSON hash defined above. The two values
use different policies and are intentionally retained side by side. [S07, S14]

## Methods, commands, and environment

[Verified] The frozen performance environment was Windows build 26200 on
AMD64 with Python 3.11.15, Node 24.18.0, and Docker client/server 28.0.4. These
are historical capture values; Aspect 2 did not start Docker or reproduce that
environment. [S11]

[Verified] The fixed protocol used seed `20260827`, five warm-ups followed by
30 measured samples, no outlier discard, concurrency 1 and 4, small and large
synthetic inputs, and nearest-rank p50/p95. Relative gates require the same
machine, fixture, command, concurrency, and environment; absolute wall-clock
numbers are not cross-machine baselines. [S01, S12]

[Verified] The recorded command families were
`python -m app.agentEval --suite all --format json`,
`python -m app.agentAcceptance`, and
`agentBenchmark --suite all --telemetry compare --format json`. The benchmark
CLI and runner are fixed offline interfaces without arbitrary provider,
project, or output-path selection. They use versioned synthetic data and report
real-provider, embedding, MySQL, and project-read counters. This is a
deterministic benchmark matrix, not a production pressure or capacity test.
[S02, S20, S21, S22]

## Evidence timeline

| Stage | Evidence and interpretation |
| --- | --- |
| Iteration 4 Aspect 6 | Deterministic fake Eval froze 39 core, 47 security, and 18 reliability cases: `104/104` total. Performance was explicitly deferred to Aspect 7. [S09] |
| Iteration 4 Aspect 7 | The first real wall-clock parent baseline and the fixed performance/telemetry/frontend gate were frozen separately. [S11, S12] |
| Iteration 4 Aspect 8 | Acceptance `18/18`, Eval `104/104`, a later benchmark sample, browser checks, isolated Compose, telemetry, safety, and zero-cost counters were frozen together. [S13, S14] |
| Iteration 4 closeout | Deterministic offline gates were followed by separately authorized real-model synthetic quality and an isolated synthetic Agent E2E. [S03, S04, S15] |
| Iteration 5 closeout | Source-preview validation was attempted in changing local and hosted environments. Some gates passed in task-owned environments, but Docker full-stack/parity remained blocked. Raw task-owned reports are not in this repository. [S16, S17, S18] |

## Correctness, Eval, Acceptance, and safety

[Verified] Aspect 6 Eval passed all `104/104` deterministic cases. Applicable
task success, trajectory validity, tool selection, structured output, recovery,
and attack-blocking rates were `1.0`. Approval bypass, duplicate side effect,
project isolation violation, budget overrun, unsafe capability execution,
sensitive leakage, and warm exact-cache model/embedding calls were all zero.
RAG recall@4, MRR, nDCG@4, and citation coverage were `1.0`, with zero project
leaks. [S05, S08, S09, S10]

[Verified] Aspect 8 Acceptance passed `18/18` against the immutable dataset,
with task success, trajectory validity, and recovery equal to `1`. The same
gate retained Eval `104/104`, zero safety violations, and zero warm exact-cache
model/embedding calls. The local and isolated-Compose topologies were evidence
contexts for that historical run, not a promise of current availability.
[S07, S13, S14]

[Candidate] Iteration 5 records `727 passed, 32 skipped`, Eval `104/104`, and
Acceptance `18/18` from task-owned external reports. The tracked source preview
repeats those values, and S19 preserves the 18-case dataset and public-contract
counts, but the raw execution reports are repository-external. These results
therefore remain class C rather than frozen current evidence. [S16, S18, S19]

## Performance and frontend size history

### Parent and Aspect 7 frozen values

| Metric | Parent value | Aspect 7 value | Ratio / interpretation | Source |
| --- | ---: | ---: | ---: | --- |
| Legacy health p95 | `2.334699966 ms` | `2.4266999680548906 ms` | `1.0394054925175469`, limit `1.15` | S11, S12 |
| Agent capabilities p95 | `1.703799935 ms` | — | Parent observation only | S11 |
| Frontend build p50 | `10495.1107 ms` | `622.8593 ms` | — | S11, S12 |
| Frontend build p95 | `12393.5751 ms` | `788.016 ms` | `0.06358262193448927` | S11, S12 |
| Dev-ready p50 | `1330.2352 ms` | `415.2436 ms` | — | S11, S12 |
| Dev-ready p95 | `1768.7087 ms` | `743.3997 ms` | `0.4203064642583598` | S11, S12 |
| OTel enabled/disabled p95 | — | — | `1.0217368988998805`, limit `1.05` | S12 |

[Verified] The Aspect 7 benchmark produced 62 case/mode results, exported
telemetry, passed both relative limits, and added zero model and embedding calls
in warm exact-cache cases. All real provider, embedding, MySQL, project-read,
and currency-cost counters were zero. [S12]

| Bundle metric | Vue CLI parent | Vite gate | Vite / parent |
| --- | ---: | ---: | ---: |
| Largest initial JS | `443227 B` (`143472 B` gzip) | `293597 B` (`98954 B` gzip) | `0.6624077504303664` non-gzip |
| Initial CSS | `111209 B` (`19536 B` gzip) | `115218 B` (`19717 B` gzip) | `1.0360492406190147`; gzip `1.0092649467649468` |
| Initial total | `571421 B` | `527792 B` | `0.923648238339158` |
| Full build | `1587799 B` | `1474835 B` | `0.9288549747165731` |
| File count | `49` | `65` | Descriptive only |

Both builds recorded zero source maps and the same `25193 B` logo. Byte counts
are tied to the frozen manifests and toolchain; wall-clock values remain
same-machine comparisons. [S11, S12]

### Later samples kept distinct

[Verified] The Aspect 8 frozen sample recorded legacy ratio
`1.083736659134018` (limit `1.15`) and OTel ratio `1.014521458310483`
(limit `1.05`), with a passing warm-cache gate. It is a later run and must not
replace the Aspect 7 frozen sample. [S13]

[Verified] The canonical Iteration 4 log subsequently records a final local
closeout run at `1.0276695194994545 / 1.0258291744311046` and a hosted-CI
cross-platform repair rerun at `0.947102356927876 / 1.0256611149561863`
(legacy / OTel). These are tracked narrative samples, not rewrites of S12 or
S13. [S02]

[Candidate] Iteration 5 records two isolated runs with approximate legacy
ratios `1.035` and `1.070`, and OTel ratios `1.025` and `1.033`. The raw reports
are absent from the repository, so only the tracked narrative and its stated
precision are retained. [S16]

## Real-model synthetic validation

[Verified] The first authorized planner quality run completed six calls but
passed strict structured planning in `0/6`; real RAG still achieved top-1
`3/3`. After a bounded provider-boundary fix, the same planner cases passed
tool selection, structured output, and regenerate binding `6/6`, while RAG
again passed `3/3`. The quality work accumulated 13 chat and 9 embedding calls,
including preflight and the first run. Provider currency cost was not returned
and is not estimated. [S04, S15]

[Verified] The separately authorized isolated `ui_info → ui_case` Agent E2E
completed with two approvals, two artifacts, one RAG query/citation, and a
final-run ledger of four model calls, two embedding calls, two tool calls, and
two steps. Final wall-clock time was `96163.598 ms`. Four debugging/final E2E
runs accumulated 14 chat and 6 embedding calls. Inputs and storage were
synthetic and temporary; user MySQL/project reads, duplicate side effects,
stored reasoning, credential exposure, and public/checkpoint content leakage
were zero. [S04]

[Verified] This evidence proves a real-model synthetic journey, not customer
project quality, production load, production persistence, or a currency-cost
baseline. Deterministic gates, planner/RAG quality, and the synthetic E2E are
three separate evidence layers and cannot substitute for one another. [S03,
S04]

## Browser, observability, containers, and CI

[Verified] Aspect 7 checked five viewports, zero horizontal overflow and console
errors, a 44 px minimum approval target, Escape close, restored focus, and both
disabled and instrumented trace states. Its isolated Compose evidence recorded
10 healthy services, 10 Tempo traces, Prometheus collector `up=1`, Prometheus
and Tempo Grafana data sources, dashboard `ezllm-agent-overview`, and a
non-loopback host response of 421. [S12]

[Verified] Aspect 8 separately recorded 10/10 healthy services, nine observed
Tempo span layers, zero forbidden telemetry attributes, zero sensitive log
pattern hits, low-cardinality Prometheus labels, Prometheus/Tempo Grafana data
sources, and cleanup of its validation containers, networks, and volumes.
These are historical isolated-run facts only. [S13]

[Candidate] Iteration 5 records GitHub Actions commit/run
`8c04759 / 33627691876`: non-Docker gates passed, while Docker smoke failed at
the Tempo trace query and in-container Acceptance probe. The raw hosted report
is not frozen in the repository. [S16]

[Missing] Iteration 5 Docker full-stack validation and dual-topology business
parity remained blocked. Earlier local attempts also recorded fixed-port
conflicts, and the repository formatter gate was blocked when the existing
ignored dependency installation lacked the formatter binary. No port was
changed and no user process was stopped to manufacture a pass. [S16, S17,
S18]

## Limitations and unknowns

- [Missing] No repository evidence proves production stress, sustained load,
  capacity, saturation, failover under production traffic, or customer-data
  performance.
- [Missing] Repository-external Iteration 5 raw reports cannot be rehashed or
  independently inspected from this baseline; their values remain class C.
- [Missing] Current Docker full-stack, Tempo query, in-container Acceptance,
  and modular-versus-container parity are not established by historical runs.
- [Missing] Hosted CI status is time-varying. This document records only the
  tracked historical run statement and does not claim current GitHub status.
- [Missing] Absolute wall-clock timings are not cross-machine comparable.
  Relative ratios require the original same-machine protocol.
- [Missing] Readiness probes, controlled ASGI acceptance, deterministic fake
  edges, and browser fixtures do not prove a complete current network Agent
  workflow journey.
- [Protected] Real environment values, credentials, uploaded projects, user
  persistence, observability payloads, logs, traces, and model bodies are not
  evidence inputs to this document.

## Current interpretation

[Verified] The repository proves a substantial historical deterministic quality
baseline, frozen same-machine performance gates, bounded frontend-size evidence,
and an explicitly synthetic real-model journey. [S09, S12, S13, S15]

[Candidate] Iteration 5 adds useful recorded local and hosted observations, but
its repository-external reports and incomplete Docker parity prevent promotion
to frozen current evidence. [S16, S17, S18]

[Missing] Nothing in this history establishes present production readiness or
completes Iteration 6. Aspect 2 only consolidates evidence and does not modify
product behavior, public APIs, workflows, tools, persistence, security, or
runtime configuration.
