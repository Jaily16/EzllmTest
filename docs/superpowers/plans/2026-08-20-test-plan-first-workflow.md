# Test Plan First Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make project analysis enter the test-plan page first, generate and persist the business summary, test plan, and test menu as one recoverable workflow, and keep downstream testing routes locked until that bundle exists.

**Architecture:** Extend the existing test-plan SSE workflow instead of replacing its public endpoint. Persist the three generated artifacts in the existing `test_project_info` table under distinct `info_type` values with a single database transaction, expose a lightweight readiness endpoint, and use a small Vue reactive state module as the shared source of truth for navigation locks and cached menu data.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, Pydantic, OpenAI-compatible async streaming, Vue 3 Composition API, Vue Router 4, Element Plus, TypeScript, pytest, Jest.

## Global Constraints

- Preserve `POST /project/llm/plan/stream` request and SSE compatibility; add events without removing `meta`, `progress`, `reasoning_delta`, `answer_delta`, `usage`, `completed`, or `error`.
- Preserve the legacy test-plan GET/PUT and legacy test-menu endpoints.
- Do not add a database table or column; use `TestProjectInfo.info_type = 23` for the persisted menu.
- Save the summary, plan, and menu only after all required generation completes; cancellation or failure must not partially overwrite the previous bundle.
- Do not call real model APIs in automated tests.
- Do not read or modify `.env` or expose credentials.
- Preserve all unrelated uncommitted user changes in the working tree.

---

### Task 1: Persisted analysis bundle

**Files:**
- Modify: `ez_back_dev/tools/InfoType.py`
- Modify: `ez_back_dev/dao/testProjectDao.py`
- Test: `ez_back_dev/tests/test_project_analysis_bundle.py`

**Interfaces:**
- Consumes: `TestProjectInfo(id: str, info_type: int, info: str)` and the existing SQLAlchemy `Session` factory.
- Produces: `InfoType.PROJECT_TEST_MENU = 23` and `save_project_analysis_bundle(pid: str, summary: str, plan: str, menu_json: str) -> bool`.

- [ ] **Step 1: Write failing transaction tests**

```python
def test_save_bundle_upserts_all_three_values_in_one_commit(monkeypatch):
    session = FakeSession(existing={InfoType.PROJECT_INITIAL_SUMMARY.value: FakeInfo()})
    monkeypatch.setattr(testProjectDao, "Session", lambda: session)
    assert testProjectDao.save_project_analysis_bundle("Ez1", "summary", "plan", '{"test_plan": true}')
    assert session.commit_count == 1
    assert session.values[InfoType.PROJECT_TEST_PLAN.value] == "plan"
    assert session.values[InfoType.PROJECT_TEST_MENU.value] == '{"test_plan": true}'

def test_save_bundle_rolls_back_on_failure(monkeypatch):
    session = FakeSession(fail_on_commit=True)
    monkeypatch.setattr(testProjectDao, "Session", lambda: session)
    assert not testProjectDao.save_project_analysis_bundle("Ez1", "s", "p", "{}")
    assert session.rollback_count == 1
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `python -m pytest ez_back_dev/tests/test_project_analysis_bundle.py -q`
Expected: FAIL because the enum and DAO function do not exist.

- [ ] **Step 3: Implement the enum and one-transaction upsert**

```python
def save_project_analysis_bundle(pid, summary, plan, menu_json):
    session = Session()
    try:
        for info_type, info in (
            (InfoType.PROJECT_INITIAL_SUMMARY.value, summary),
            (InfoType.PROJECT_TEST_PLAN.value, plan),
            (InfoType.PROJECT_TEST_MENU.value, menu_json),
        ):
            row = session.query(TestProjectInfo).filter(
                and_(TestProjectInfo.id == pid, TestProjectInfo.info_type == info_type)
            ).first()
            if row is None:
                session.add(TestProjectInfo(id=pid, info_type=info_type, info=info))
            else:
                row.info = info
        session.commit()
        return True
    except Exception:
        session.rollback()
        return False
    finally:
        session.close()
```

- [ ] **Step 4: Run the transaction tests**

Run: `python -m pytest ez_back_dev/tests/test_project_analysis_bundle.py -q`
Expected: PASS.

### Task 2: Unified streamed analysis and readiness endpoint

**Files:**
- Modify: `ez_back_dev/service/llmTestPlanStreamService.py`
- Modify: `ez_back_dev/app/routers.py`
- Test: `ez_back_dev/tests/test_test_plan_stream_service.py`
- Test: `ez_back_dev/tests/test_project_analysis_routes.py`

**Interfaces:**
- Consumes: `stream_chat_completion`, summary/test-plan/menu prompts, document splitters, `TestMenu` validation, and `save_project_analysis_bundle`.
- Produces: SSE `summary_delta` and `menu` events, `completed.data.ready`, plus `GET /project/analysis/status/{pid}` returning readiness flags and the parsed cached menu.

- [ ] **Step 1: Add failing cached, generated, and failure-path tests**

```python
async def test_complete_cached_bundle_does_not_call_model(monkeypatch):
    monkeypatch.setattr(testProjectDao, "get_project_info", cached_info)
    events = [event async for event in stream_test_plan("Ez1", "DeepSeek", False)]
    assert next(e for e in events if e["event"] == "summary_delta")["data"]["text"] == "summary"
    assert next(e for e in events if e["event"] == "menu")["data"]["menu"]["test_plan"] is True
    assert events[-1]["data"] == {"saved": True, "from_cache": True, "ready": True}

async def test_generated_bundle_is_saved_only_after_menu_is_valid(monkeypatch):
    saved = []
    monkeypatch.setattr(testProjectDao, "save_project_analysis_bundle", lambda *args: saved.append(args) or True)
    events = [event async for event in stream_test_plan("Ez1", "DeepSeek", True)]
    assert saved and saved[0][1] == "summary" and saved[0][2] == "plan"
    assert next(e for e in events if e["event"] == "menu")["data"]["menu"]["acceptance_test"] is True

async def test_invalid_menu_does_not_save(monkeypatch):
    monkeypatch.setattr(streaming_service, "_parse_test_menu", lambda _: (_ for _ in ()).throw(ValueError()))
    with pytest.raises(TestPlanStreamError):
        [event async for event in stream_test_plan("Ez1", "DeepSeek", True)]
    assert save_mock.call_count == 0
```

- [ ] **Step 2: Run the service tests and confirm they fail**

Run: `python -m pytest ez_back_dev/tests/test_test_plan_stream_service.py ez_back_dev/tests/test_project_analysis_routes.py -q`
Expected: FAIL because bundle events/status route are absent.

- [ ] **Step 3: Generate or reuse each artifact, validate menu JSON, then save once**

```python
menu = TestMenu.model_validate(json.loads(strip_markdown_fence(menu_text))).model_dump()
saved = await asyncio.to_thread(
    testProjectDao.save_project_analysis_bundle,
    pid,
    summary,
    final_content,
    json.dumps(menu, ensure_ascii=False),
)
yield _event("menu", menu=menu)
yield _event("completed", saved=True, from_cache=False, ready=True)
```

Use `regenerate=False` to reuse every cached artifact and generate only missing values. Stream cached summary and plan to the page; never issue a model call when all three artifacts already exist.

- [ ] **Step 4: Add the readiness endpoint**

```python
@router.get("/project/analysis/status/{pid}")
async def get_project_analysis_status(pid: str):
    summary, plan, menu_text = await asyncio.gather(...)
    menu = parse_cached_menu(menu_text)
    return {
        "summary_ready": bool(summary),
        "plan_ready": bool(plan),
        "menu_ready": menu is not None,
        "ready": bool(summary and plan and menu is not None),
        "menu": menu,
    }
```

- [ ] **Step 5: Run the backend tests**

Run: `python -m pytest ez_back_dev/tests/test_project_analysis_bundle.py ez_back_dev/tests/test_test_plan_stream_service.py ez_back_dev/tests/test_project_analysis_routes.py -q`
Expected: PASS without network access.

### Task 3: Shared Vue analysis state and test-plan-first navigation

**Files:**
- Create: `ez_front_dev/src/state/projectAnalysis.ts`
- Modify: `ez_front_dev/src/router/index.ts`
- Modify: `ez_front_dev/src/views/LoginView.vue`
- Modify: `ez_front_dev/src/views/CreateView.vue`
- Modify: `ez_front_dev/src/views/MainView.vue`
- Test: `ez_front_dev/tests/project-analysis-workflow.spec.js`

**Interfaces:**
- Consumes: `GET /project/analysis/status/{pid}` and existing app globals `$requestUrl`, `$id`, `$test_menu`.
- Produces: `analysisReady`, `analysisStatusLoaded`, `analysisMenu`, `loadProjectAnalysisStatus(baseUrl, pid)`, and `resetProjectAnalysisState()`.

- [ ] **Step 1: Add failing front-end workflow contract tests**

```javascript
expect(routerSource).toContain('redirect: "/plan"')
expect(loginSource).toContain("开始分析业务和生成测试计划")
expect(mainSource).toContain("测试计划")
expect(mainSource).toContain(':disabled="!analysisReady"')
expect(mainSource).toContain("/project/analysis/status/")
```

- [ ] **Step 2: Run the contract test and confirm it fails**

Run: `npm test -- --runInBand tests/project-analysis-workflow.spec.js`
Expected: FAIL because the old redirect is `/menu` and no readiness state exists.

- [ ] **Step 3: Add the shared reactive state**

```typescript
export const analysisReady = ref(false)
export const analysisStatusLoaded = ref(false)
export const analysisMenu = ref<TestMenuState | null>(null)

export async function loadProjectAnalysisStatus(baseUrl: string, pid: string) {
  const response = await axios.get(`${baseUrl}/project/analysis/status/${pid}`)
  analysisReady.value = response.data.ready === true
  analysisMenu.value = response.data.menu ?? null
  analysisStatusLoaded.value = true
  return response.data
}
```

- [ ] **Step 4: Change entry routes and labels**

Set `/test` to redirect to `/plan`; make login and project-creation completion enter `/plan`; use “开始分析业务和生成测试计划” for the primary entry action.

- [ ] **Step 5: Add the test-plan item and lock downstream menu items**

Place `/plan` under “LLM智能测试分析” with the existing `Notebook` Element Plus icon. Keep `/plan` enabled, disable “测试菜单” and all manual test-type items while `analysisReady` is false, and route programmatic navigation through a guard that redirects locked destinations to `/plan`.

- [ ] **Step 6: Run the front-end workflow contract test**

Run: `npm test -- --runInBand tests/project-analysis-workflow.spec.js`
Expected: PASS.

### Task 4: Combined generation page and persisted test-menu consumption

**Files:**
- Modify: `ez_front_dev/src/composables/useLlmStream.ts`
- Modify: `ez_front_dev/src/components/TestPlan.vue`
- Modify: `ez_front_dev/src/components/TestMenu.vue`
- Test: `ez_front_dev/tests/project-analysis-workflow.spec.js`

**Interfaces:**
- Consumes: SSE `summary_delta`, `answer_delta`, `menu`, `completed.ready`, plus the shared analysis state.
- Produces: a combined summary/plan display and a test-menu view that reads persisted status rather than generating an independent transient menu.

- [ ] **Step 1: Add failing stream event and menu-consumption assertions**

```javascript
expect(streamSource).toContain('case "summary_delta"')
expect(streamSource).toContain('case "menu"')
expect(planSource).toContain("业务初步分析与总结")
expect(planSource).toContain("开始分析业务和生成测试计划")
expect(menuSource).not.toContain("/project/llm/menu/acquire")
```

- [ ] **Step 2: Extend the SSE composable**

```typescript
case "summary_delta":
  summary.value += String(data.text ?? "")
  break
case "menu":
  menu.value = (data.menu ?? null) as TestMenuState | null
  break
```

Reset both fields at the start of each stream and update `analysisReady` plus the existing `$test_menu` compatibility global only after `completed.ready === true`.

- [ ] **Step 3: Update the test-plan page**

Render the business summary and test plan in distinct result sections. Rename the primary button to “开始分析业务和生成测试计划”, keep a regeneration action after completion, and retain the existing progress/reasoning/token/cancel panel.

- [ ] **Step 4: Make the test-menu page read-only over persisted data**

Load `GET /project/analysis/status/{pid}` when shared menu state is empty. Render the existing test cards from the returned menu and direct users back to `/plan` when the bundle is absent; do not call `/project/llm/menu/acquire` or regeneration routes from this page.

- [ ] **Step 5: Run front-end tests, lint, and build**

Run: `npm test -- --runInBand tests/project-analysis-workflow.spec.js`
Expected: PASS.

Run: `npm run lint`
Expected: no ESLint warnings or errors.

Run: `npm run build`
Expected: successful production build; existing asset-size performance warnings are acceptable.

### Task 5: Compatibility regression

**Files:**
- Modify: `ez_back_dev/tests/test_test_plan_stream_route.py` only if event assertions require additive fields.
- Modify: `ez_front_dev/tests/streaming-ui-contracts.spec.js` only if the combined labels require updated exact text.

**Interfaces:**
- Consumes: all public endpoints and UI contracts changed above.
- Produces: evidence that legacy interfaces and offline model mocks remain compatible.

- [ ] **Step 1: Run the relevant backend suite**

Run: `python -m pytest ez_back_dev/tests -q`
Expected: all tests pass without real API calls.

- [ ] **Step 2: Run all front-end contract tests**

Run: `npm test -- --runInBand`
Expected: all tests pass.

- [ ] **Step 3: Inspect the final diff without exposing credentials**

Run: `git status --short`
Expected: only intended source/tests/plan changes are added to the user's existing dirty worktree; staged cache/IDE removals remain untouched.

Run: `git diff --stat`
Expected: no `.env`, credential file, generated cache, or dependency installation output is newly included.

- [ ] **Step 4: Commit only when explicitly authorized**

Do not commit in this task. The repository contains user-owned uncommitted reproduction changes, so report the changed files and test results for user review.
