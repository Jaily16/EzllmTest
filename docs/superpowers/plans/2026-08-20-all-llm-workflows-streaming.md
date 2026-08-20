# All LLM Workflows Streaming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace every remaining blocking LLM spinner in unit, integration, API, UI, database, functional, nonfunctional, and acceptance testing with real stage progress, streamed reasoning, streamed final content, token usage, and cancellation.

**Architecture:** Preserve all legacy REST endpoints and add one operation-dispatched POST SSE endpoint. A shared backend stream core performs provider-aware raw streaming, document map/reduce, structured JSON parsing, RAG retrieval, usage aggregation, disconnect checks, and delayed atomic cache writes; Vue pages share one typed stream composable and one execution panel while retaining their current multi-step business choices and result shapes.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, Pydantic, LangChain document/retriever utilities, OpenAI-compatible async streams, Vue 3 Composition API, TypeScript, Element Plus, pytest.

## Global Constraints

- Cover `unit_menu`, `unit_info`, `unit_case`, `integration_menu`, `integration_info`, `integration_case`, `api_info`, `api_case`, `ui_info`, `ui_case`, `db_info`, `db_case`, `functional_info`, `functional_case`, `nonfunctional_info`, `nonfunctional_case`, `acceptance_info`, and `acceptance_case`.
- Preserve every existing `/project/llm/...` GET/POST/PUT endpoint and its legacy response envelope.
- Use `POST /project/llm/workflow/stream` with `text/event-stream`; do not convert POST request bodies to query strings.
- Emit `meta`, `progress`, `reasoning_delta`, `answer_delta`, `result`, `usage`, `completed`, and sanitized `error` events.
- Use the selected stable frontend model label and the current provider/model registry; do not add provider SDK dependencies.
- Retrieve real project documents and knowledge-base context; progress labels must reflect actual read, split, retrieval, map, reduce, final generation, and persistence stages.
- Do not persist reasoning. Delay new knowledge/summary cache writes until the operation completes; cancellation or failure must not partially write cache values.
- Never call real model or embedding APIs from automated tests.
- Do not read or modify `.env`, commit Git, or disturb unrelated user changes.

---

### Task 1: Generic workflow request and stream core

**Files:**
- Modify: `ez_back_dev/model/HttpModel.py`
- Create: `ez_back_dev/service/llmWorkflowStreamCore.py`
- Modify: `ez_back_dev/dao/testProjectDao.py`
- Test: `ez_back_dev/tests/test_llm_workflow_stream_core.py`

**Interfaces:**
- Consumes: `stream_chat_completion(name, prompt, max_tokens)`, project document helpers, provider errors, and `TestProjectInfo`.
- Produces: `WorkflowStreamRequest(operation: str, pid: str, llm_name: str, regenerate: bool, payload: dict[str, Any])`, `WorkflowContext`, `stream_model_call`, `stream_map_reduce`, `stream_rag_answer`, `parse_structured_result`, and `save_project_info_values(pid, values) -> bool`.

- [ ] **Step 1: Write failing core tests**

```python
async def test_model_call_forwards_reasoning_and_final_content():
    events = [event async for event in stream_model_call(ctx, "prompt", stage="final", output=True)]
    assert [event["event"] for event in events] == ["reasoning_delta", "answer_delta"]

def test_structured_parser_accepts_fenced_json():
    assert parse_structured_result("```json\n{\"api_list\":[\"/v1\"]}\n```", ApiList).api_list == ["/v1"]

def test_atomic_info_values_rollback(monkeypatch):
    assert not save_project_info_values("Ez1", {11: "new", 12: None})
    assert read_values("Ez1") == {11: "old", 12: "old"}
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests/test_llm_workflow_stream_core.py -q`
Expected: FAIL because the request/core/DAO APIs do not exist.

- [ ] **Step 3: Implement typed request and reusable stream helpers**

```python
class WorkflowStreamRequest(BaseModel):
    operation: str
    pid: str
    llm_name: str
    regenerate: bool = False
    payload: dict[str, Any] = Field(default_factory=dict)

async def stream_model_call(ctx, prompt_text, *, stage, label, output_event=None):
    async for chunk in stream_chat_completion(ctx.llm_name, prompt_text, max_tokens):
        if chunk.kind == "reasoning":
            yield event("reasoning_delta", stage=stage, label=label, text=chunk.text)
        elif chunk.kind == "content":
            if output_event:
                yield event(output_event, text=chunk.text)
```

- [ ] **Step 4: Implement arbitrary atomic cache upsert**

```python
def save_project_info_values(pid, values):
    session = Session()
    try:
        for info_type, info in values.items():
            row = session.query(TestProjectInfo).filter(...).first()
            session.add(TestProjectInfo(id=pid, info_type=info_type, info=info)) if row is None else setattr(row, "info", info)
        session.commit()
        return True
    except Exception:
        session.rollback()
        return False
    finally:
        session.close()
```

- [ ] **Step 5: Run core tests**

Run: `python -m pytest tests/test_llm_workflow_stream_core.py -q`
Expected: PASS.

### Task 2: Analysis/menu workflow operations

**Files:**
- Create: `ez_back_dev/service/llmWorkflowAnalysisStreamService.py`
- Create: `ez_back_dev/service/llmWorkflowStreamService.py`
- Test: `ez_back_dev/tests/test_llm_workflow_analysis_stream.py`

**Interfaces:**
- Consumes: the stream core, existing prompts/templates/splitters/retrievers, and Pydantic menu/list models.
- Produces: async operations for `unit_menu`, `unit_info`, `integration_menu`, `integration_info`, `api_info`, `ui_info`, `db_info`, `functional_info`, `nonfunctional_info`, and `acceptance_info`.

- [ ] **Step 1: Add parameterized failing operation tests**

```python
@pytest.mark.parametrize("operation", ["unit_menu", "api_info", "ui_info", "db_info", "functional_info", "nonfunctional_info", "acceptance_info"])
async def test_analysis_operation_emits_real_progress_reasoning_answer_and_result(operation):
    events = await collect(operation)
    assert monotonic_progress(events) == sorted(monotonic_progress(events))
    assert "reasoning_delta" in event_names(events)
    assert "answer_delta" in event_names(events)
    assert events[-1]["event"] == "completed"
```

- [ ] **Step 2: Implement configurable document analysis**

```python
ANALYSIS_SPECS = {
    "api_info": AnalysisSpec("design", InfoType.PROJECT_APIS_SUMMARY, ApiList, prompt.API_TEST_SUMMARY_PROMPT_STR, ...),
    "functional_info": AnalysisSpec("requirements", InfoType.PROJECT_FUNCTIONAL_SUMMARY, UseCaseList, ...),
}
```

Load cache first; when absent, use the operation's actual document source and overflow rule, map/reduce large documents, stream only the reduce/stuff body as `answer_delta`, extract any structured list through a second streamed model call, then emit the legacy-compatible object in `result`.

- [ ] **Step 3: Implement unit/integration special analysis operations**

Use existing design/require retrievers for a selected unit or integration object. Emit retrieval progress before model generation and return exactly the frontend fields `unit_info`, `test_type`, or the integration description/menu structure.

- [ ] **Step 4: Verify analysis operations**

Run: `python -m pytest tests/test_llm_workflow_analysis_stream.py -q`
Expected: all operations pass with mocked models, documents, embeddings, and retrievers.

### Task 3: RAG and test-case workflow operations

**Files:**
- Create: `ez_back_dev/service/llmWorkflowCaseStreamService.py`
- Test: `ez_back_dev/tests/test_llm_workflow_case_stream.py`

**Interfaces:**
- Consumes: knowledge documents, knowledge retriever, cached `InfoType` values, existing case prompt templates, and frontend payload selections.
- Produces: `unit_case`, `integration_case`, `api_case`, `ui_case`, `db_case`, `functional_case`, `nonfunctional_case`, and `acceptance_case` streams.

- [ ] **Step 1: Write parameterized RAG/case tests**

```python
@pytest.mark.parametrize("operation", CASE_OPERATIONS)
async def test_case_operation_streams_rag_then_final_case(operation):
    events = await collect(operation)
    assert progress_stage(events, "knowledge_retrieval")
    assert progress_stage(events, "case_generate")
    assert streamed_answer(events) == "generated cases"
    assert next_result(events)["test_cases"] == "generated cases"
```

- [ ] **Step 2: Implement cached RAG knowledge helper usage**

```python
knowledge = await ctx.cached_or_generate_knowledge(
    info_type=InfoType.PROJECT_API_TEST_KNOWLEDGE.value,
    question=prompt.API_TEST_KNOWLEDGE_STR,
)
```

Retrieve relevant context with the existing embedding retriever, stream the knowledge model's reasoning, hide its body from final `answer_delta`, and queue new cache values without writing them yet.

- [ ] **Step 3: Build and stream existing case prompts**

Format the current `ChatPromptTemplate` with the same fields and output templates. Stream the final case body through `answer_delta`; emit `result` with the same knowledge and `test_cases` keys expected by each current page.

- [ ] **Step 4: Save queued cache values only after final generation**

Call `save_project_info_values` once after the final response is nonempty and the client is still connected. Do not write nonfunctional method knowledge because it has no stable cache key.

- [ ] **Step 5: Verify all case operations and cancellation**

Run: `python -m pytest tests/test_llm_workflow_case_stream.py -q`
Expected: eight operations pass; cancellation and invalid payload tests prove no cache write.

### Task 4: SSE route and reusable Vue execution layer

**Files:**
- Modify: `ez_back_dev/app/routers.py`
- Modify: `ez_front_dev/src/composables/useLlmStream.ts`
- Create: `ez_front_dev/src/components/LlmWorkflowExecution.vue`
- Test: `ez_back_dev/tests/test_api_contracts.py`
- Test: `ez_back_dev/tests/test_frontend_contracts.py`

**Interfaces:**
- Consumes: `WorkflowStreamRequest`, workflow dispatcher events, and existing `LlmExecutionPanel` props/events.
- Produces: `/project/llm/workflow/stream`, generic request bodies, `result: Ref<Record<string, unknown> | null>`, `resetStream()`, and a reusable streamed-output panel.

- [ ] **Step 1: Add failing route and UI contracts**

```python
assert "POST" in openapi["/project/llm/workflow/stream"]
assert 'case "result"' in composable
assert "LlmExecutionPanel" in workflow_panel
assert "answer" in workflow_panel
```

- [ ] **Step 2: Add the sanitized SSE route**

Reuse the test-plan route's disconnect handling and `_stream_error`; validate the operation in the dispatcher before starting provider calls.

- [ ] **Step 3: Generalize the Vue composable and add wrapper component**

```typescript
interface WorkflowBody { operation: string; pid: string; llm_name: string; regenerate?: boolean; payload: Record<string, unknown> }
case "result": result.value = data.result as Record<string, unknown>
```

The wrapper renders the existing progress/reasoning/usage/cancel panel and a throttled read-only streamed answer while the operation is active or failed.

- [ ] **Step 4: Verify contracts**

Run: `python -m pytest tests/test_api_contracts.py tests/test_frontend_contracts.py -q`
Expected: PASS and legacy routes remain present.

### Task 5: Migrate all eight Vue testing pages

**Files:**
- Modify: `ez_front_dev/src/components/UnitTest.vue`
- Modify: `ez_front_dev/src/components/IntegrationTest.vue`
- Modify: `ez_front_dev/src/components/ApiTest.vue`
- Modify: `ez_front_dev/src/components/UITest.vue`
- Modify: `ez_front_dev/src/components/DatabaseTest.vue`
- Modify: `ez_front_dev/src/components/FounctionalTest.vue`
- Modify: `ez_front_dev/src/components/NonfunctionalTest.vue`
- Modify: `ez_front_dev/src/components/AcceptanceTest.vue`
- Test: `ez_back_dev/tests/test_frontend_contracts.py`

**Interfaces:**
- Consumes: `useLlmStream`, `LlmWorkflowExecution`, `MODEL_OPTIONS`, and workflow operation result objects.
- Produces: all current buttons using the workflow stream endpoint with visible progress, thought stream, final stream, token usage, and cancel.

- [ ] **Step 1: Add a contract requiring every page to use streaming and no spinner**

```python
for page in TEST_PAGES:
    source = read(page)
    assert 'start("/project/llm/workflow/stream"' in source
    assert "LlmWorkflowExecution" in source
    assert "v-loading" not in source
```

- [ ] **Step 2: Migrate API/UI/database/functional/nonfunctional/acceptance pages**

Add the shared model selector, route both analysis and case buttons through the generic stream, update current refs from `result`, preserve selection/output/reset behavior, and show the execution panel for the active operation.

- [ ] **Step 3: Migrate unit and integration multi-step pages**

Route menu, further-analysis, and final-case actions through the stream while preserving their current list/menu derivation, model choices, strategies, formats, and global compatibility values.

- [ ] **Step 4: Run frontend static verification**

Run: `npm run lint`
Expected: no warnings or errors.

Run: `npm run build`
Expected: successful build; existing asset-size warnings are acceptable.

### Task 6: Full completion audit

**Files:**
- Modify: `ez_back_dev/tests/test_frontend_contracts.py`
- Modify: `ez_back_dev/tests/test_api_contracts.py`

**Interfaces:**
- Consumes: all 18 operation names, eight page sources, new SSE endpoint, and legacy API manifest.
- Produces: explicit evidence that no blocking LLM spinner or direct legacy LLM call remains in the eight pages.

- [ ] **Step 1: Run backend full suite**

Run: `python -m pytest tests -q`
Expected: all tests pass without external calls.

- [ ] **Step 2: Search every page for unmigrated LLM calls**

Run: `rg -n "v-loading|/project/llm/(unit|integration|api|ui|db|functional|nfunctional|acceptance)" ez_front_dev/src/components`
Expected: no `v-loading` in the eight pages and no direct legacy LLM endpoint strings there.

- [ ] **Step 3: Run lint and build again after audit fixes**

Run: `npm run lint` and `npm run build`
Expected: lint clean and build successful.

- [ ] **Step 4: Review Git scope without exposing credentials**

Run: `git status --short` and `git diff --stat`
Expected: no `.env`, keys, generated cache, or unrelated user assets added or overwritten; no commit is created.
