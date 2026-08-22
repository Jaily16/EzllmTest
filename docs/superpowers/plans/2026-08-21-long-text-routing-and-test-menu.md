# Long-text Routing and Test-menu Evidence Implementation Plan

> **For agentic workers:** Implement task-by-task with tests first. No commit or push is authorized by this plan.

**Goal:** Prevent false-negative test-menu decisions and route every current LLM workflow through an explicit, model-compatible long-text strategy.

**Architecture:** Add one immutable policy catalog that separates exhaustive corpus extraction from focused retrieval and compact artifact generation. Whole-corpus calls use direct stuffing while they fit a conservative cross-provider budget, then hierarchical map-reduce; focused questions use bounded retrieval followed by stuffing; final case generation uses saved compact artifacts. Test-menu booleans are reconciled with deterministic document-structure evidence so a lossy model summary cannot lock valid unit or integration workflows.

**Tech Stack:** Python 3.11, FastAPI services, Pydantic 2, LangChain Core 1.5, LangChain text splitters 1.1, pytest 9.

## Global Constraints

- Preserve all existing REST/SSE response shapes, artifact keys, legacy `InfoType` rows, and frontend routing behavior.
- Do not call real chat models, embeddings, MySQL, or paid services during automated verification.
- Do not read or modify `.env`, install dependencies, commit, or push.
- Treat the dirty worktree and uploaded project files as user assets.
- Do not persist prompts, source documents, reasoning, or credentials in policy/audit metadata.

---

### Task 1: Model capability and long-text policy catalog

**Files:**
- Create: `ez_back_dev/service/longTextPolicy.py`
- Modify: `ez_back_dev/llm/provider.py`
- Create: `ez_back_dev/tests/test_long_text_policy.py`
- Modify: `ez_back_dev/tests/test_provider.py`

**Interfaces:**
- Produces `LongTextStrategy`, `LongTextPolicy`, `LONG_TEXT_POLICIES`, `strategy_for(operation, source_tokens)`, and `effective_context_budget(operation, stage, model_label)`.
- Extends `ModelSpec` with `context_window_tokens` and `max_output_tokens` while preserving all existing constructor consumers.

- [ ] **Step 1: Add failing policy-completeness and provider-capability tests**

```python
def test_every_workflow_has_a_long_text_policy():
    assert {item.operation for item in WORKFLOW_DEFINITIONS} == set(LONG_TEXT_POLICIES)

def test_all_supported_models_cover_application_budgets():
    for spec in list_model_specs():
        assert spec.context_window_tokens >= 200_000
        assert effective_context_budget("project_analysis", "final", spec.label) >= 64_000
```

- [ ] **Step 2: Run the focused tests and verify they fail because the catalog and fields do not exist**

Run: `D:\tool\anaconda3\envs\ezllmtest\python.exe -m pytest tests/test_long_text_policy.py tests/test_provider.py -q`

- [ ] **Step 3: Implement immutable policies**

```python
class LongTextStrategy(StrEnum):
    STUFF = "stuff"
    MAP_REDUCE = "map_reduce"
    RETRIEVAL_STUFF = "retrieval_stuff"
    ARTIFACT_STUFF = "artifact_stuff"

@dataclass(frozen=True)
class LongTextPolicy:
    operation: str
    source_mode: Literal["exhaustive", "focused", "artifact"]
    stuff_limit_tokens: int
    overflow_strategy: LongTextStrategy
```

Use 64,000 source tokens for `project_analysis`, 32,000 for exhaustive analysis workflows, bounded retrieval for focused unit/integration/API/use-case/nonfunctional/knowledge questions, and compact artifact stuffing for all case-generation stages. Assign no current workflow to refine because none incrementally revises one order-dependent document state.

- [ ] **Step 4: Add conservative provider capabilities**

Record GLM-4.7 as 200K, qwen3.5-plus as 1M, deepseek-v4-flash as 1M, and kimi-k2.5 as 256K. Reserve output, reasoning, and a 10% safety margin before returning an effective input budget.

- [ ] **Step 5: Re-run focused tests**

Expected: policy completeness and provider compatibility pass without creating a remote client.

### Task 2: Evidence-based project test-menu reconciliation

**Files:**
- Modify: `ez_back_dev/model/ChainJsonModel.py`
- Modify: `ez_back_dev/prompt/promptStr.py`
- Modify: `ez_back_dev/service/llmTestPlanStreamService.py`
- Modify: `ez_back_dev/tests/test_test_plan_stream_service.py`

**Interfaces:**
- Produces `collect_project_test_evidence(documents) -> ProjectTestEvidence` and `reconcile_test_menu(candidate, evidence) -> TestMenu`.
- Keeps persisted menu JSON and the `menu` SSE event unchanged.

- [ ] **Step 1: Add a failing CC4C regression test**

```python
def test_structural_design_evidence_unlocks_unit_and_integration():
    evidence = collect_project_test_evidence([
        Document(page_content="课程模块通过 REST 接口调用用户服务，采用 SpringBoot 分层架构")
    ])
    menu = reconcile_test_menu(TestMenu(unit_test=False, integration_test=False, **OTHER_TRUE), evidence)
    assert menu.unit_test is True
    assert menu.integration_test is True
```

Also assert a business-only paragraph with no module/component/interface/relationship evidence stays false.

- [ ] **Step 2: Run the regression test and verify it fails**

Run: `D:\tool\anaconda3\envs\ezllmtest\python.exe -m pytest tests/test_test_plan_stream_service.py -q`

- [ ] **Step 3: Implement bounded, explainable structural evidence**

Count categories rather than persisting excerpts: named/qualified modules, components, services, classes or functions provide unit evidence; architecture plus interface/call/dependency/data-flow relationships provide integration evidence. Require at least two independent signal categories before overriding a model `false`; never turn an explicit model `true` into `false`.

- [ ] **Step 4: Reconcile before plan generation and persistence**

Use the reconciled menu for `enabled_tests`, the `menu` SSE event, the legacy menu row, and the project-analysis artifact. Update the digest prompt with the same definitions so the model and deterministic guard agree.

- [ ] **Step 5: Verify cache and API compatibility tests**

Expected: old cached artifacts remain readable; new generation persists only the existing summary/menu/plan payload shape.

### Task 3: Safe stuffing and hierarchical map-reduce

**Files:**
- Modify: `ez_back_dev/service/workflowBudget.py`
- Modify: `ez_back_dev/service/llmWorkflowStreamCore.py`
- Modify: `ez_back_dev/service/llmTestPlanStreamService.py`
- Modify: `ez_back_dev/tests/test_workflow_budget.py`
- Modify: `ez_back_dev/tests/test_llm_workflow_stream_core.py`

**Interfaces:**
- Extends `stream_model_call(..., instruction_text=None, context_text=None)` so instructions are never truncated as document context.
- Produces `partition_texts_within_budget(...)` and recursively reduces summary batches until one bounded final reduce call is possible.

- [ ] **Step 1: Add failing prompt-preservation and middle-evidence tests**

```python
def test_bounding_never_truncates_instructions():
    bounded = bound_prompt_context("REQUIRED_SCHEMA", huge_context, 100)
    assert bounded.prompt.startswith("REQUIRED_SCHEMA")

async def test_hierarchical_reduce_keeps_all_batch_markers():
    result = await run_fake_map_reduce(markers=range(20), tiny_budget=True)
    assert all(str(marker) in result for marker in range(20))
```

- [ ] **Step 2: Verify the new tests fail under head/tail truncation and one-shot reduce**

- [ ] **Step 3: Preserve instructions and split map inputs to the actual stage budget**

Calculate source capacity after prompt overhead, split oversized source chunks with `RecursiveCharacterTextSplitter`, and pass instruction/context separately. Keep metadata and stable order.

- [ ] **Step 4: Implement hierarchical reduction**

Partition map summaries by the reduce-stage context budget. Reduce each batch, repeat while multiple batches remain, then emit the final reducer output. Intermediate calls stay non-thinking and bounded.

- [ ] **Step 5: Run core stream and budget tests**

Expected: no prompt/document middle truncation, existing event shapes unchanged, all usage counters include every hierarchical call.

### Task 4: Apply decisions to all 19 streamed workflows

**Files:**
- Modify: `ez_back_dev/service/llmWorkflowAnalysisStreamService.py`
- Modify: `ez_back_dev/service/llmWorkflowCaseStreamService.py`
- Modify: `ez_back_dev/service/workflowBudget.py`
- Modify: `ez_back_dev/tests/test_llm_workflow_analysis_stream.py`
- Modify: `ez_back_dev/tests/test_llm_workflow_case_stream.py`
- Modify: `ez_back_dev/tests/test_workflow_cost_baseline.py`

**Interfaces:**
- Exhaustive workflows call `strategy_for` using actual source tokens rather than the coarse project `overflow` flag.
- Focused retrieval workflows always retrieve, deduplicate, budget, then stuff; they do not map-reduce an already bounded result set.

- [ ] **Step 1: Add failing routing-matrix tests**

Assert project/unit menu/API/UI/DB/functional/acceptance use stuff below their limits and map-reduce above them; unit/integration/API detail, use-case detail, nonfunctional and knowledge lookup use retrieval-stuff; all case outputs use artifact-stuff.

- [ ] **Step 2: Replace `overflow` and hard-coded `14500` routing in streamed services**

Count the actual selected corpus or retrieval context and select from `LONG_TEXT_POLICIES`. Preserve current splitters as semantic boundary helpers, with the core enforcing the final token budget.

- [ ] **Step 3: Keep compact prerequisite artifacts out of map-reduce**

Use existing artifact and `InfoType` summaries for final case prompts. If a caller supplies an oversized prerequisite, bound that field before template rendering and emit the existing context-reduction progress event.

- [ ] **Step 4: Correct DeepSeek non-thinking compatibility**

For map/structured stages send `thinking.type=disabled`; do not rely on `reasoning_effort=low`, which current DeepSeek maps to a reasoning mode.

- [ ] **Step 5: Run workflow and offline baseline tests**

Expected: no external sockets, fresh cache still uses zero calls/embeddings, and small/current CC4C-sized exhaustive corpora use fewer calls than the legacy 14,500-token threshold.

### Task 5: Legacy-call audit, documentation, and final verification

**Files:**
- Modify: `ez_back_dev/chain/BasicChain.py`
- Modify: legacy `ez_back_dev/service/llm*Service.py` files only where they still accept whole corpora
- Create: `docs/long-text-strategy-audit.md`
- Modify: `docs/iteration-2-development-log.md`
- Modify: `ez_back_dev/tests/test_api_contracts.py`

**Interfaces:**
- Legacy REST endpoints retain their paths and response bodies.
- `docs/long-text-strategy-audit.md` records policy names, source type, threshold, rationale, and provider compatibility without prompts or business content.

- [ ] **Step 1: Add a static test that every legacy whole-corpus call is policy-routed**

Check the legacy services for direct `overflow`-based map selection and fail until it is removed or delegated to `strategy_for`.

- [ ] **Step 2: Route legacy whole-corpus calls through the same policy**

Keep retrieval and final case calls as stuff. Upgrade the synchronous map-reduce helper to hierarchical reduction without changing its public signature.

- [ ] **Step 3: Write the audit table**

Document: project-wide/exhaustive extraction → stuff then hierarchical map-reduce; focused entity/question → retrieval-stuff; final case from saved artifacts → artifact-stuff; refine → no current production assignment, reserved for future ordered revision synthesis.

- [ ] **Step 4: Run focused and full offline verification**

Run:

```powershell
D:\tool\anaconda3\envs\ezllmtest\python.exe -m pytest tests/test_long_text_policy.py tests/test_test_plan_stream_service.py tests/test_llm_workflow_stream_core.py tests/test_llm_workflow_analysis_stream.py tests/test_llm_workflow_case_stream.py -q
D:\tool\anaconda3\envs\ezllmtest\python.exe -m pytest tests -q
git diff --check
```

Expected: all tests pass; no provider, embedding, or live database client is created.

- [ ] **Step 5: Self-review dirty-worktree safety**

Use `git status --short` and `git diff --stat`; do not stage, commit, reset, or push anything.
